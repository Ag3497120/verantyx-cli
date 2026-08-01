import Foundation

/// Swift port of `divergence_exchange.py`'s `sharpen_dist` and
/// `dist_to_soft_sequence` -- converts a role's/consensus's vocabulary
/// distribution into a **sequence** of soft/virtual token embeddings
/// (rather than a single averaged vector), which is what actually gets fed
/// to `encode_soft` for the next Council round. This is the multi-token
/// soft-injection Milestone D explicitly skipped in favor of a single
/// averaged vector.
enum SoftSequence {
    /// Distribution entries considered too generic to carry meaning, ported
    /// from `_DIST_STOP` -- pure discourse markers that shouldn't become
    /// soft tokens on their own.
    static let stopwords: Set<String> = [
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "to", "of", "in", "on", "at", "for", "and", "or", "but", "so", "if",
        "it", "this", "that", "these", "those", "as", "with", "by", "from",
        "answer", "the answer", "i", "you", "we", "they", "he", "she",
    ]

    static func alnumCount(_ s: String) -> Int {
        s.unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }.count
    }

    /// Content length for ranking/filtering. Latin uses alphanumeric count;
    /// CJK / kana must not be dropped by an ASCII-centric `>= 3` rule (a
    /// single kanji or a short Japanese greeting is a real consensus token).
    static func contentCount(_ s: String) -> Int {
        let alnum = alnumCount(s)
        if alnum > 0 { return alnum }
        return s.unicodeScalars.filter { scalar in
            let v = scalar.value
            // Hiragana, Katakana, CJK Unified Ideographs (+ ext A), Hangul
            return (0x3040...0x30FF).contains(v)
                || (0x3400...0x9FFF).contains(v)
                || (0xAC00...0xD7AF).contains(v)
        }.count
    }

    /// Port of `sharpen_dist`: drop stopwords/short candidates, merge
    /// duplicate normalized keys by summing mass, keep the top `topN`,
    /// renormalize to sum 1.
    static func sharpenDist(_ distribution: [JCrossChatManager.TopKText], topN: Int) -> [(text: String, weight: Float)] {
        var merged: [String: Float] = [:]
        for entry in distribution {
            let key = entry.text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let cc = contentCount(key)
            // Latin needs >=3 letters; CJK/kana accept a single content glyph.
            let minLen = alnumCount(key) > 0 ? 3 : 1
            guard !key.isEmpty, !stopwords.contains(key), cc >= minLen else { continue }
            merged[key, default: 0] += entry.prob
        }
        let sorted = merged.sorted { $0.value > $1.value }.prefix(topN)
        let total = sorted.reduce(Float(0)) { $0 + $1.value }
        guard total > 0 else { return [] }
        return sorted.map { (text: $0.key, weight: $0.value / total) }
    }

    /// Port of `dist_to_soft_sequence`: rank sharpened candidates by
    /// content length (long words first, ties by weight desc), tokenize
    /// each, and emit the raw embedding row of each unique subtoken id (via
    /// `JCrossChatManager.embeddingRow`) up to `maxSoft` rows -- no
    /// averaging or magnitude-blending, the distribution only affects
    /// ordering/dedup, matching the Python original exactly.
    static func distToSoftSequence(
        distribution: [JCrossChatManager.TopKText],
        maxSoft: Int = 12,
        sharpen: Bool = true,
        chat: JCrossChatManager
    ) async throws -> [[Float]] {
        let candidates: [(text: String, weight: Float)]
        if sharpen {
            candidates = sharpenDist(distribution, topN: max(16, maxSoft))
        } else {
            candidates = distribution.map { (text: $0.text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased(), weight: $0.prob) }
        }
        let ranked = candidates.sorted { a, b in
            let la = contentCount(a.text), lb = contentCount(b.text)
            if la != lb { return la > lb }
            return a.weight > b.weight
        }

        var rows: [[Float]] = []
        var seenIds = Set<UInt32>()
        for candidate in ranked {
            guard !candidate.text.isEmpty else { continue }
            let ids = try await chat.tokenize(candidate.text)
            for id in ids {
                guard !seenIds.contains(id) else { continue }
                seenIds.insert(id)
                rows.append(try await chat.embeddingRow(tokenId: id))
                if rows.count >= maxSoft { break }
            }
            if rows.count >= maxSoft { break }
        }

        if rows.isEmpty, let fallback = distribution.first {
            // Single-row fallback matching `dist_to_soft_numpy`'s simpler
            // path: mean embedding of the top candidate's subtokens.
            let ids = try await chat.tokenize(fallback.text)
            if !ids.isEmpty {
                var acc = [Float](repeating: 0, count: 1)
                var initialized = false
                for id in ids {
                    let row = try await chat.embeddingRow(tokenId: id)
                    if !initialized { acc = row; initialized = true } else {
                        for i in 0..<row.count { acc[i] += row[i] }
                    }
                }
                for i in 0..<acc.count { acc[i] /= Float(ids.count) }
                rows = [acc]
            }
        }

        return rows
    }
}
