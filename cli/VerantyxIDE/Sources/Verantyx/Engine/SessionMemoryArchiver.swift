import Foundation

// MARK: - SessionMemoryArchiver
//
// セッションが削除されても記憶は消えない。
// 【変更】セッション削除時だけでなく、10メッセージ毎に自動蒸留する。
// 新規セッション開始時に過去セッションの記憶を L1〜L3 レイヤーで注入する。
//
// 保存先: (1) ~/Library/Application Support/Verantyx/jcross_archive/ (legacy)
//          (2) ~/.openclaw/memory/{front,near,mid}/ (zone-aware, MCP共有)
//
// ゾーン優先度:
//   front/ ← CONV_* (現セッション圧縮チャンク)  最高優先度
//   near/  ← PROG_*, SESSION_* (直近セッション)  中優先度
//   mid/   ← SKILL_* (スキルカタログ)            低優先度
//
// CortexEngine とは独立して動作するため、CortexEngine の GC でも消えない。

final class SessionMemoryArchiver {

    static let shared = SessionMemoryArchiver()

    // Legacy archive dir (backward compat)
    private let archiveDir: URL = {
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        )[0]
        let dir = appSupport.appendingPathComponent("Verantyx/jcross_archive", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    // ── Zone-aware dirs — Twin Architecture ──────────────────────────────
    //
    // 【双子 JCross ストア設計】
    //   full/  : L1(テキスト) + L2(OP.FACT) + L3(verbatim)  ← large/mid/small 用
    //   nano/  : L1(漢字トポロジーのみ)                      ← nano/small 用
    //
    // 同じゾーン階層 (front/near/mid) を持つ。
    // 書き込みは常に両方に同期 → 情報密度だけが違う「双子」の状態を維持。
    // 読み込みは tier に応じてディレクトリを切り替える。

    private func dynamicMemoryDir(subpath: String) -> URL {
        let cortexWs = UserDefaults.standard.string(forKey: "cortex_workspace_path")
        let normalWs = UserDefaults.standard.string(forKey: "last_workspace_path")
        let wsPath = cortexWs ?? normalWs
        let baseDir: URL
        if let ws = wsPath {
            baseDir = URL(fileURLWithPath: ws).appendingPathComponent(".openclaw/memory")
        } else {
            baseDir = URL(fileURLWithPath: "/tmp").appendingPathComponent(".openclaw/memory")
        }
        let dir = baseDir.appendingPathComponent(subpath, isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    // ── full/ ストア (L1-L3 フルスペック) ────────────────────────────────
    private var mcpFrontDir: URL { dynamicMemoryDir(subpath: "front") }
    private var mcpNearDir: URL { dynamicMemoryDir(subpath: "near") }
    var mcpMidDir: URL { dynamicMemoryDir(subpath: "mid") }
    private var mcpFarDir: URL { dynamicMemoryDir(subpath: "far") }

    // ── nano/ ストア (L1 漢字トポロジーのみ) ─────────────────────────────
    private var nanoFrontDir: URL { dynamicMemoryDir(subpath: "nano/front") }
    private var nanoNearDir: URL { dynamicMemoryDir(subpath: "nano/near") }
    private var nanoMidDir: URL { dynamicMemoryDir(subpath: "nano/mid") }
    private var nanoFarDir: URL { dynamicMemoryDir(subpath: "nano/far") }

    // MARK: - Progressive archiving (every N messages, overwrites previous)

    /// Called by SessionStore every time messages.count is a multiple of 10.
    /// Overwrites the existing .jcross for this session (no accumulation).
    @discardableResult
    func archiveProgressively(session: ChatSession) -> String? {
        let messages = session.messages
        // Only archive when there's meaningful content (≥4 messages)
        guard messages.filter({ $0.role != .system }).count >= 4 else { return nil }

        let content = buildJCrossContent(session: session, label: "Progressive")
        let fileName = progressiveFileName(for: session)

        // Write to local archive (overwrite)
        let localPath = archiveDir.appendingPathComponent(fileName)
        try? content.write(to: localPath, atomically: true, encoding: .utf8)

        // Mirror to MCP mid/ zone
        let mcpPath = mcpMidDir.appendingPathComponent(fileName)
        try? content.write(to: mcpPath, atomically: true, encoding: .utf8)

        return fileName
    }

    // MARK: - Archive a session before deletion

    /// Call this BEFORE deleting a session to immortalize its memory.
    @discardableResult
    func archiveBeforeDelete(session: ChatSession) -> String? {
        let messages = session.messages
        guard !messages.isEmpty else { return nil }

        let content = buildJCrossContent(session: session, label: "Deleted")
        let shortId = String(session.id.uuidString.prefix(8))
        let ts = Int(Date().timeIntervalSince1970)
        let fileName = "SESSION_\(shortId)_\(ts).jcross"

        let localPath = archiveDir.appendingPathComponent(fileName)
        try? content.write(to: localPath, atomically: true, encoding: .utf8)

        let mcpPath = mcpMidDir.appendingPathComponent(fileName)
        try? content.write(to: mcpPath, atomically: true, encoding: .utf8)

        // Also store in CortexEngine
        let l1 = buildL1(session: session)
        let sessionDate = ISO8601DateFormatter().string(from: session.createdAt)
        let shortId2 = String(session.id.uuidString.prefix(8))
        Task { @MainActor in
            CortexEngine.shared?.remember(
                key: "archived_session_\(shortId2)",
                value: "[\(sessionDate)] \(session.title): \(l1.prefix(200))",
                importance: 0.85,
                zone: .mid
            )
        }

        return fileName
    }

    // MARK: - Archive all sessions (bulk)

    func archiveAll(sessions: [ChatSession]) {
        for session in sessions {
            archiveBeforeDelete(session: session)
        }
    }

    // MARK: - Move to Far Zone (Archive Box)

    /// Moves all PROG_* and CONV_* files associated with the given session ID to the `far/` zone.
    /// This is used when a task completes, separating the task history from the active context.
    func moveToFarZone(shortId: String) {
        let fm = FileManager.default
        let dirsToScan = [mcpFrontDir, mcpNearDir, nanoFrontDir, nanoNearDir]
        
        for dir in dirsToScan {
            guard let files = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) else { continue }
            for file in files {
                let name = file.lastPathComponent
                if name.hasPrefix("PROG_\(shortId)") || name.hasPrefix("CONV_\(shortId)") || name.hasPrefix("SESSION_\(shortId)") {
                    // Determine destination based on whether it's nano or full
                    let destDir = dir.path.contains("/nano/") ? nanoFarDir : mcpFarDir
                    let destURL = destDir.appendingPathComponent(name)
                    do {
                        if fm.fileExists(atPath: destURL.path) {
                            try fm.removeItem(at: destURL)
                        }
                        try fm.moveItem(at: file, to: destURL)
                        print("[SessionMemoryArchiver] Moved \(name) to far zone.")
                    } catch {
                        print("[SessionMemoryArchiver] Failed to move \(name) to far zone: \(error)")
                    }
                }
            }
        }
    }

    // MARK: - Cross-session memory injection (NEW)

    /// Build a memory injection string from recent past sessions.
    /// Called when a new session starts, filtered by the user's activeLayer setting.
    ///
    /// - Parameters:
    ///   - topK: How many past sessions to include (default: 5)
    ///   - layer: Which JCross layer to extract (L1 = minimal, L3 = full verbatim)
    ///   - excludingSessionId: Skip the current session's own archive
    ///   - prefixFilter: If non-empty, only include files whose names start with one of these
    ///                   prefixes (e.g. ["CONV", "PROG"] excludes SKILL_*.jcross files)
    func buildCrossSessionInjection(
        topK: Int = 5,
        layer: JCrossLayer = .l2,
        excludingSessionId: UUID? = nil,
        prefixFilter: [String] = []
    ) -> String {
        let files = listArchived(prefixFilter: prefixFilter)
            .filter { url in
                // Exclude the current session's progressive archive if needed
                if let excId = excludingSessionId {
                    let prefix = "PROG_\(String(excId.uuidString.prefix(8)))"
                    return !url.lastPathComponent.hasPrefix(prefix)
                }
                return true
            }
            .prefix(topK)

        guard !files.isEmpty else { return "" }

        var parts: [String] = []
        for url in files {
            guard let raw = try? String(contentsOf: url, encoding: .utf8) else { continue }
            let sessionName = extractMetaField(from: raw, key: "Session") ?? url.deletingPathExtension().lastPathComponent
            let date        = extractMetaField(from: raw, key: "Created") ?? ""

            // Extract the section matching the requested layer
            let extracted: String
            switch layer {
            case .l1:
                extracted = extractSection(from: raw, tag: "L1_SUMMARY") ?? ""
            case .l1_5:
                // L1.5 = L1 summary + OP.ENTITY/OP.STATE lines from L2
                let l1Part = extractSection(from: raw, tag: "L1_SUMMARY") ?? ""
                let l2Part = extractSection(from: raw, tag: "L2_FACTS") ?? ""
                let entityLines = l2Part.components(separatedBy: "\n")
                    .filter { $0.contains("OP.ENTITY") || $0.contains("OP.STATE") }
                    .joined(separator: "\n")
                extracted = [l1Part, entityLines].filter { !$0.isEmpty }.joined(separator: "\n")
            case .l2:
                extracted = extractSection(from: raw, tag: "L2_FACTS") ?? ""
            case .l3:
                extracted = extractSection(from: raw, tag: "L3_VERBATIM") ?? ""
            case .vera:
                // Vera doesn't write .jcross node files — nothing to
                // extract from cross-session file archives for this
                // layer; its own cross-session recall goes through
                // VeraMemoryBridge instead (Vera's store IS the
                // cross-session memory, no per-session file to read).
                extracted = ""
            }

            guard !extracted.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }

            let header = "【\(sessionName)】\(date.isEmpty ? "" : " (\(date))")"
            // Cap each section to prevent context overflow
            let cap: Int
            switch layer {
            case .l1:   cap = 120
            case .l1_5: cap = 300
            case .l2:   cap = 600
            case .l3:   cap = 2000
            case .vera: cap = 0
            }
            parts.append("\(header)\n\(String(extracted.prefix(cap)))")
        }

        guard !parts.isEmpty else { return "" }

        return """

        [CROSS-SESSION MEMORY — Layer: \(layer.rawValue) — \(layer.description)]
        以下は過去のセッションから蒸留された記憶です。参考にしてください。

        \(parts.joined(separator: "\n---\n"))
        [/CROSS-SESSION MEMORY]
        """
    }

    // MARK: - Skill archiving (called by SkillLibrary)

    /// Persist a single SkillNode as a JCross tri-layer node.
    /// Written to archiveDir and mcpMidDir so all model tiers receive it
    /// via buildCrossSessionInjection() → archiveSection in the system prompt.
    func archiveSkillNode(title: String, l1: String, l2: String, l3: String) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let safeName  = title
            .replacingOccurrences(of: "Skill: ", with: "")
            .replacingOccurrences(of: "/", with: "-")
            .filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }

        writeJCrossNode(
            prefix: "SKILL",
            safeName: safeName,
            sessionLabel: title,
            timestamp: timestamp,
            l1: l1, l2: l2, l3: l3
        )
    }

    // MARK: - Intra-session compression archiving (called by AgentLoop.compressConversation)

    /// Persist a compressed conversation chunk as a JCross tri-layer node.
    ///
    /// This is the key to "infinite context" for all model tiers:
    ///   - Called every time AgentLoop compresses old turns (OOM guard)
    ///   - Written to archiveDir → picked up by buildCrossSessionInjection()
    ///   - Re-injected into the system prompt on the VERY NEXT TURN
    ///   - Nano gets L1 (120 chars), Small/Mid get L2 (600 chars), Large gets L3 (2000 chars)
    ///   - No JCross tool access needed — passive injection via archiveSection
    func archiveConversationChunk(chunkId: String, taskTitle: String, l1: String, l2: String, l3: String) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let safeName  = chunkId
            .filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }

        writeJCrossNode(
            prefix: "CONV",
            safeName: safeName,
            sessionLabel: "Conv chunk: \(taskTitle)",
            timestamp: timestamp,
            l1: l1, l2: l2, l3: l3
        )
    }

    // MARK: - Wisdom extraction archiving (NEW)

    /// Persist an extracted user identity or wisdom chunk as a JCross tri-layer node.
    /// This uses the WISDOM prefix which routes to the mid/ zone, preserving it
    /// across sessions without cluttering the front/ active context zone.
    func archiveWisdomChunk(chunkId: String, taskTitle: String, l1: String, l2: String, l3: String) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let safeName  = chunkId
            .filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }

        writeJCrossNode(
            prefix: "WISDOM",
            safeName: safeName,
            sessionLabel: "Wisdom: \(taskTitle)",
            timestamp: timestamp,
            l1: l1, l2: l2, l3: l3
        )
    }

    // MARK: - Shared JCross node writer

    /// Writes a JCross node to both the legacy archiveDir and the zone-aware MCP dir.
    /// Zone routing by prefix:
    ///   CONV   → front/  (current-session compression, highest injection priority)
    ///   PROG   → near/   (progressive session archives)
    ///   SESSION→ near/   (deleted session archives)
    ///   SKILL  → mid/    (skill catalog, separate priority slot)
    private func writeJCrossNode(
        prefix: String,
        safeName: String,
        sessionLabel: String,
        timestamp: String,
        l1: String, l2: String, l3: String
    ) {
        let fileName = "\(prefix)_\(safeName).jcross"

        // ── full/ ストア: L1+L2+L3 フルスペック ───────────────────────────
        let fullContent = """
        ;;; JCross Memory Node — \(prefix) [FULL]
        ;;; Session: \(sessionLabel)
        ;;; Created: \(timestamp)
        ;;; Archived: \(timestamp)
        ;;; ID: \(prefix.lowercased())-\(safeName)
        ;;; Store: full

        [L1_SUMMARY]
        \(l1)
        [/L1_SUMMARY]

        [L2_FACTS]
        \(l2)
        [/L2_FACTS]

        [L3_VERBATIM]
        \(l3)
        [/L3_VERBATIM]
        """

        // Legacy archive (backward compat)
        let localPath = archiveDir.appendingPathComponent(fileName)
        try? fullContent.write(to: localPath, atomically: true, encoding: .utf8)

        // full/ ゾーンルーティング
        let fullZoneDir: URL
        switch prefix {
        case "CONV":              fullZoneDir = mcpFrontDir
        case "PROG", "SESSION":   fullZoneDir = mcpNearDir
        case "TASK", "INTERRUPT", "FAR": fullZoneDir = mcpFarDir
        case "WISDOM", "SKILL":   fullZoneDir = mcpMidDir
        default:                  fullZoneDir = mcpMidDir
        }
        try? fullContent.write(to: fullZoneDir.appendingPathComponent(fileName), atomically: true, encoding: .utf8)

        // ── nano/ ストア: L1 漢字トポロジーのみ ──────────────────────────
        // L1 を漢字トポロジー圧縮形式に変換（~30トークン目標）
        let nanoL1 = compressToKanjiTopology(l1: l1, l2: l2, prefix: prefix)

        let nanoContent = """
        ;;; JCross Memory Node — \(prefix) [NANO]
        ;;; Session: \(sessionLabel)
        ;;; Created: \(timestamp)
        ;;; ID: \(prefix.lowercased())-\(safeName)
        ;;; Store: nano

        [L1_SUMMARY]
        \(nanoL1)
        [/L1_SUMMARY]
        """

        // nano/ ゾーンルーティング（full/ と同じ prefix 規則）
        let nanoZoneDir: URL
        switch prefix {
        case "CONV":              nanoZoneDir = nanoFrontDir
        case "PROG", "SESSION":   nanoZoneDir = nanoNearDir
        case "TASK", "INTERRUPT", "FAR": nanoZoneDir = nanoFarDir
        case "WISDOM", "SKILL":   nanoZoneDir = nanoMidDir
        default:                  nanoZoneDir = nanoMidDir
        }
        try? nanoContent.write(to: nanoZoneDir.appendingPathComponent(fileName), atomically: true, encoding: .utf8)
    }

    // MARK: - Kanji Topology Compressor

    /// L1 テキストと L2 ファクトを漢字トポロジー形式に圧縮する。
    ///
    /// 目標: ~30トークン（通常 L1 の 1/4）
    ///
    /// 出力例:
    ///   [会:ラーメン好 犬:トイプードル 住:京都] [日:2025-04-25] [PREFIX:PROG]
    ///
    /// アルゴリズム:
    ///   1. L2 の OP.FACT キー=値をショートコード化（漢字1文字 or 2文字 → 値）
    ///   2. L1 テキストからキーワードを抽出して [...] に畳み込む
    ///   3. 全体を 120 文字以内に制限
    private func compressToKanjiTopology(l1: String, l2: String, prefix: String) -> String {
        var tokens: [String] = []

        // ── L2 OP.FACT から構造化トークン生成 ────────────────────────────
        // OP.FACT("key", "value") → [漢字記号:値の先頭]
        let factRegex = try? NSRegularExpression(pattern: #"OP\.FACT\("([^"]+)",\s*"([^"]+)"\)"#)
        let nsL2 = l2 as NSString
        let factMatches = factRegex?.matches(in: l2, range: NSRange(location: 0, length: nsL2.length)) ?? []

        for match in factMatches.prefix(6) {
            guard
                match.numberOfRanges == 3,
                let keyRange = Range(match.range(at: 1), in: l2),
                let valRange = Range(match.range(at: 2), in: l2)
            else { continue }
            let key = String(l2[keyRange])
            let val = String(String(l2[valRange]).prefix(20))
                .replacingOccurrences(of: "\n", with: " ")

            // キーを漢字ショートコードにマッピング
            let kanjiCode = factKeyToKanji(key)
            tokens.append("\(kanjiCode):\(val)")
        }

        // ── L1 テキストから補完トークン（OP.FACT がない場合） ────────────
        if tokens.isEmpty {
            let condensed = l1
                .replacingOccurrences(of: "[会話:", with: "")
                .replacingOccurrences(of: "]", with: "")
                .prefix(60)
            tokens.append(String(condensed))
        }

        // ── 組み立て ──────────────────────────────────────────────────────
        let inner = tokens.joined(separator: " ")
        let dateTag = String(l1.prefix(200)).contains("日付:") ?
            extractInlineBracket(l1, key: "日付").map { "[日:\($0)]" } ?? "" : ""
        let result = "[\(prefix):\(inner)]\(dateTag.isEmpty ? "" : " " + dateTag)"
        return String(result.prefix(120))
    }

    /// OP.FACT キー → 漢字ショートコードマッピング
    private func factKeyToKanji(_ key: String) -> String {
        let map: [String: String] = [
            "user_intent_0": "意",
            "user_intent_1": "意",
            "user_intent_2": "意",
            "modified_file": "編",
            "workspace":     "場",
            "message_count": "数",
            "skill_name":    "技",
            "description":   "説",
            "goal":          "目",
            "model_id":      "型",
            "backend":       "基",
            "kanji_tags":    "漢",
        ]
        // 完全一致 → ショートコード、なければキーの先頭2文字
        if let kanji = map[key] { return kanji }
        let prefixKey = key.components(separatedBy: "_").first ?? key
        return String(prefixKey.prefix(2))
    }

    /// [key:value] 形式から value を抽出するヘルパー
    private func extractInlineBracket(_ text: String, key: String) -> String? {
        guard let range = text.range(of: "[\(key):") else { return nil }
        let after = text[range.upperBound...]
        guard let end = after.firstIndex(of: "]") else { return nil }
        return String(after[..<end])
    }

    // MARK: - Zone-Priority Injection

    /// Build the memory injection for this turn using zone priority order.
    ///
    /// 【双子ストア切り替え】
    ///   isNanoStore = true  → nano/（漢字トポロジーL1のみ）を参照
    ///   isNanoStore = false → full/（L1-L3フルスペック）を参照
    ///
    /// 各ティアの合計charBudget:
    ///   nano:  280 chars (漢字トポロジーL1のみ)
    ///   small: 900 chars (L1.5)
    ///   mid:   1500 chars (L2)
    ///   large/giant: 3000 chars (L3)
    func buildZonePriorityInjection(layer: JCrossLayer, useNanoStore: Bool = false) -> String {
        // ── Tier budget ────────────────────────────────────────────────────
        let totalBudget: Int
        let itemCap: Int
        switch layer {
        case .l1:   totalBudget = useNanoStore ? 280 : 400;  itemCap = useNanoStore ? 80 : 120
        case .l1_5: totalBudget = 900;  itemCap = 300
        case .l2:   totalBudget = 1500; itemCap = 600
        case .l3:   totalBudget = 3000; itemCap = 1000
        case .vera: totalBudget = 0;    itemCap = 0   // not used — VeraMemoryBridge handles Vera-layer injection
        }

        // ── ストア選択: nano/ or full/ ────────────────────────────────────
        let frontDir = useNanoStore ? nanoFrontDir : mcpFrontDir
        let nearDir  = useNanoStore ? nanoNearDir  : mcpNearDir
        let midDir   = useNanoStore ? nanoMidDir   : mcpMidDir
        let storeTag = useNanoStore ? "nano" : "full"

        var parts: [String] = []
        var remaining = totalBudget

        // ── Priority 1: front/ (CONV_* + CortexEngine UUID nodes) ────────────────────────
        // NOTE: No prefix filter here — CortexEngine writes UUID-named nodes (e.g. abcd1234.jcross)
        // that must also be injected. CONV_* from SessionMemoryArchiver live here too.
        let frontFiles = listZone(frontDir, prefixFilter: [], topK: 8)
        for url in frontFiles where remaining > 0 {
            // nano ストアは常に L1（ファイル自体が L1 のみ）
            let readLayer: JCrossLayer = useNanoStore ? .l1 : layer
            if let chunk = extractLayer(from: url, layer: readLayer, cap: itemCap) {
                let name = url.deletingPathExtension().lastPathComponent
                let entry = useNanoStore
                    ? "[現:\(name)]\n\(chunk)"
                    : "【現セッション履歴: \(name)】\n\(chunk)"
                parts.append(entry)
                remaining -= entry.count
            }
        }

        // ── Priority 2: near/ (PROG_*, SESSION_*) ─────────────────────────
        if remaining > 0 {
            let nearFiles = listZone(nearDir, prefixFilter: ["PROG", "SESSION"], topK: 3)
            for url in nearFiles where remaining > 0 {
                let readLayer: JCrossLayer = useNanoStore ? .l1 : layer
                if let chunk = extractLayer(from: url, layer: readLayer, cap: min(itemCap, remaining)) {
                    let name = url.deletingPathExtension().lastPathComponent
                    let entry = useNanoStore
                        ? "[近:\(name)]\n\(chunk)"
                        : "【近セッション: \(name)】\n\(chunk)"
                    parts.append(entry)
                    remaining -= entry.count
                }
            }
        }

        // ── Priority 3: mid/ (SKILL_*) ────────────────────────────────────
        if remaining > 0 {
            let skillLayer: JCrossLayer = (useNanoStore || layer == .l1) ? .l1 : (layer == .l3 ? .l2 : .l1)
            let skillCap = min(useNanoStore ? 40 : 120, remaining)
            let midFiles = listZone(midDir, prefixFilter: ["SKILL"], topK: 3)
            for url in midFiles where remaining > 0 {
                if let chunk = extractLayer(from: url, layer: skillLayer, cap: skillCap) {
                    let name = url.deletingPathExtension().lastPathComponent
                    let entry = useNanoStore
                        ? "[技:\(name)]\(chunk)"
                        : "【スキル: \(name)】\(chunk)"
                    parts.append(entry)
                    remaining -= entry.count
                }
            }
        }

        guard !parts.isEmpty else { return "" }

        let header = useNanoStore
            ? "[記憶:\(storeTag) front>near>mid]"
            : "[ZONE MEMORY — front>near>mid priority — Layer: \(layer.rawValue)]"
        let footer = useNanoStore ? "[/記憶]" : "[/ZONE MEMORY]"
        let desc   = useNanoStore
            ? ""
            : "\n以下は優先度順の記憶注入です（front=現セッション > near=直近 > mid=スキル）。\n"

        return "\n\(header)\(desc)\n\(parts.joined(separator: useNanoStore ? "·" : "\n---\n"))\n\(footer)"
    }
    // MARK: - Identity Injection
    
    /// Scans the `mid/` zone for `WISDOM_` and `CORTEX_PORTRAIT` files to build a persistent identity block.
    /// This is unconditionally injected into the root of the System Prompt on every execution.
    func buildIdentityInjection(useNanoStore: Bool = false) -> String {
        let midDir = useNanoStore ? nanoMidDir : mcpMidDir
        var parts: [String] = []
        
        // 1. CORTEX_PORTRAIT
        let canvasURL = midDir.appendingPathComponent("CORTEX_PORTRAIT.jcross")
        if let chunk = extractLayer(from: canvasURL, layer: useNanoStore ? .l1 : .l3, cap: 1000) {
            parts.append("【CORTEX_PORTRAIT (Unified Identity)】\n\(chunk)")
        }
        
        // 2. WISDOM_ files (including L3.5 Asset Profile and Task Wisdom)
        let wisdomFiles = listZone(midDir, prefixFilter: ["WISDOM"], topK: 10)
        for url in wisdomFiles {
            if let chunk = extractLayer(from: url, layer: useNanoStore ? .l1 : .l3, cap: 1000) {
                let name = url.deletingPathExtension().lastPathComponent
                parts.append("【\(name)】\n\(chunk)")
            }
        }
        
        guard !parts.isEmpty else { return "" }
        
        return """
        
        [USER IDENTITY & CONTEXT — CRITICAL DIRECTIVE]
        The following information represents the user's permanent identity, architectural preferences, and OS asset profile.
        You MUST adhere to these preferences unconditionally in all tasks.
        
        \(parts.joined(separator: "\n---\n"))
        [/USER IDENTITY]
        
        """
    }

    // MARK: - Zone file listing

    /// List files in a zone dir, filtered by prefix, sorted newest first.
    private func listZone(_ dir: URL, prefixFilter: [String], topK: Int) -> [URL] {
        let fm = FileManager.default
        let files = (try? fm.contentsOfDirectory(at: dir,
                                                  includingPropertiesForKeys: [.creationDateKey])) ?? []
        return files
            .filter { $0.pathExtension == "jcross" }
            .filter { url in
                guard !prefixFilter.isEmpty else { return true }
                let name = url.lastPathComponent
                return prefixFilter.contains { name.hasPrefix($0 + "_") }
            }
            .sorted { a, b in
                let da = (try? a.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
                let db = (try? b.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
                return da > db
            }
            .prefix(topK)
            .map { $0 }
    }

    // MARK: - Skill Catalog Indexer

    /// .agents/skills/ 内の SKILL.md や .yaml ファイルを走査して mid/SKILL_*.jcross に登録する。
    ///
    /// 動作:
    ///   1. workspaceRoot/.agents/skills/ 以下の全 SKILL.md および .yaml / .yml を探索
    ///   2. YAML frontmatter 又は YAML 本文から name / description を抽出
    ///   3. mid/SKILL_{name}.jcross が7日以内に存在すれば再作成をスキップ
    ///   4. L1 = 1行サマリー、L2 = 主要キーワード/用途、として書き込む
    ///
    /// 呼び出しタイミング: アプリ起動時 (AppMain or VerantyxApp.init)
    func indexSkills(workspaceRoot: URL? = nil) async {
        let fm = FileManager.default

        let cortexSkillsPath = await MainActor.run { AppState.shared?.cortexSkillsPath }
        var cortexSkillsURL: URL? = nil
        if let path = cortexSkillsPath {
            cortexSkillsURL = URL(fileURLWithPath: path)
        }

        // ── スキルディレクトリを決定 ────────────────────────────────────────
        // 優先度: 引数 > Cortex連携パス > Bundle主Bundle > ~/.openclaw/skills
        let candidates: [URL] = [
            workspaceRoot.map { $0.appendingPathComponent(".agents/skills") },
            cortexSkillsURL,
            Bundle.main.bundleURL.deletingLastPathComponent()
                .appendingPathComponent(".agents/skills"),
            URL(fileURLWithPath: "/tmp")
                .appendingPathComponent(".openclaw/skills"),
        ].compactMap { $0 }

        var skillFiles: [URL] = []
        for dir in candidates {
            guard let enumerator = fm.enumerator(
                at: dir,
                includingPropertiesForKeys: nil,
                options: [.skipsHiddenFiles]
            ) else { continue }
            for case let file as URL in enumerator {
                let name = file.lastPathComponent.lowercased()
                if name == "skill.md" || name.hasSuffix(".yaml") || name.hasSuffix(".yml") {
                    skillFiles.append(file)
                }
            }
        }

        guard !skillFiles.isEmpty else { return }

        // ── 各 スキルファイル (.md / .yaml) を処理 ─────────────────────────────────────────────
        let sevenDaysAgo = Date().addingTimeInterval(-7 * 86400)

        for fileURL in skillFiles {
            guard let raw = try? String(contentsOf: fileURL, encoding: .utf8) else { continue }

            // YAML (Frontmatter or raw YAML) パース
            let fallbackName = fileURL.lastPathComponent.lowercased() == "skill.md"
                ? fileURL.deletingLastPathComponent().lastPathComponent
                : fileURL.deletingPathExtension().lastPathComponent
            let name        = yamlField(raw, key: "name")        ?? fallbackName
            let description = yamlField(raw, key: "description") ?? ""
            let safeName    = name.replacingOccurrences(of: "/", with: "-")
                                   .replacingOccurrences(of: " ", with: "_")

            // mid/SKILL_{name}.jcross の既存チェック
            let destURL = mcpMidDir.appendingPathComponent("SKILL_\(safeName).jcross")
            if let attrs = try? destURL.resourceValues(forKeys: [.creationDateKey]),
               let created = attrs.creationDate, created > sevenDaysAgo {
                continue  // 7日以内に更新済み → スキップ
            }

            // --- 本文からキーワード抽出（## Goal / ## Inputs / ## Notes 等 または YAMLキー） ---
            let body = stripYAMLFrontmatter(raw)
            let mdGoals = extractMarkdownSection(body, heading: "Goal")
            let goals = mdGoals.isEmpty ? (yamlField(raw, key: "goal") ?? "") : mdGoals
            
            let mdInputs = extractMarkdownSection(body, heading: "Inputs")
            let inputs = mdInputs.isEmpty ? (yamlField(raw, key: "inputs") ?? "") : mdInputs
            
            let mdUseLine = extractMarkdownSection(body, heading: "Use when")
            let useLine = mdUseLine.isEmpty ? (yamlField(raw, key: "use_when") ?? "") : mdUseLine

            // L1 サマリー（1行）
            let l1 = "[スキル:\(name)] \(description)"

            // L2 ファクト
            var l2Lines: [String] = [
                "OP.FACT(\"skill_name\", \"\(name)\")",
                "OP.FACT(\"description\", \"\(String(description.prefix(200)))\")",
            ]
            if !goals.isEmpty {
                l2Lines.append("OP.FACT(\"goal\", \"\(String(goals.prefix(200)))\")")
            }
            if !inputs.isEmpty {
                l2Lines.append("OP.FACT(\"inputs\", \"\(String(inputs.prefix(200)))\")")
            }
            if !useLine.isEmpty {
                l2Lines.append("OP.FACT(\"use_when\", \"\(String(useLine.prefix(200)))\")")
            }
            l2Lines.append("OP.STATE(\"type\", \"SKILL\")")

            // JCross ノードとして書き込み
            let timestamp = ISO8601DateFormatter().string(from: Date())
            let content = """
            ;;; JCross Memory Node — SKILL
            ;;; Skill: \(name)
            ;;; Indexed: \(timestamp)
            ;;; Source: \(fileURL.path)

            [L1_SUMMARY]
            \(l1)
            [/L1_SUMMARY]

            [L2_FACTS]
            \(l2Lines.joined(separator: "\n"))
            [/L2_FACTS]

            [L3_VERBATIM]
            \(String(body.prefix(1500)))
            [/L3_VERBATIM]
            """

            try? content.write(to: destURL, atomically: true, encoding: .utf8)
        }

        // ── 構築したJCrossノードから skills_catalog.json を生成 (tool-search-oss用) ──
        var catalogEntries: [[String: String]] = []
        let jcrossFiles = listZone(mcpMidDir, prefixFilter: ["SKILL"], topK: 5000)
        for jcross in jcrossFiles {
            let safeName = jcross.deletingPathExtension().lastPathComponent.replacingOccurrences(of: "SKILL_", with: "")
            if let raw = try? String(contentsOf: jcross, encoding: .utf8) {
                let l1 = extractSection(from: raw, tag: "L1_SUMMARY") ?? ""
                var desc = l1
                if let bracketEnd = l1.firstIndex(of: "]") {
                    desc = String(l1[l1.index(after: bracketEnd)...]).trimmingCharacters(in: .whitespaces)
                }
                if desc.isEmpty { desc = "スキル: \(safeName)" }
                catalogEntries.append([
                    "name": safeName,
                    "description": desc,
                    "serverName": "verantyx-skills"
                ])
            }
        }
        
        if !catalogEntries.isEmpty,
           let data = try? JSONSerialization.data(withJSONObject: catalogEntries, options: .prettyPrinted) {
            let catalogURL = mcpMidDir.appendingPathComponent("skills_catalog.json")
            try? data.write(to: catalogURL)
            
            let catalogPath = catalogURL.path
            Task { @MainActor in
                let config = MCPServerConfig(
                    name: "tool-search-oss",
                    transport: .stdio,
                    command: "sh -c \"cd /Users/motonishikoudai/verantyx-cli && python3 -m tool_search_oss.server --catalog \(catalogPath)\"",
                    mode: .ai
                )
                if let existing = MCPEngine.shared.servers.first(where: { $0.name == "tool-search-oss" }) {
                    if existing.command != config.command {
                        var updated = config
                        updated.id = existing.id
                        MCPEngine.shared.updateServer(updated)
                        await MCPEngine.shared.restartServer(id: updated.id)
                    }
                } else {
                    MCPEngine.shared.addServer(config)
                    await MCPEngine.shared.connect(server: config)
                }
            }
        }
    }

    // MARK: - Skill Indexer Helpers

    /// YAML frontmatter または 生の YAML テキストから key の値を抽出する
    private func yamlField(_ raw: String, key: String) -> String? {
        let lines = raw.components(separatedBy: "\n")
        let hasFrontmatter = lines.first(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty })?.hasPrefix("---") == true
        var inFront = !hasFrontmatter // フロントマターが無い場合は全体をYAMLとして扱う
        
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if hasFrontmatter && trimmed == "---" {
                inFront = !inFront
                continue
            }
            if !inFront { continue }
            
            if trimmed.hasPrefix("\(key):") {
                let value = trimmed.dropFirst("\(key):".count).trimmingCharacters(in: .whitespaces)
                let cleanValue = value.trimmingCharacters(in: .init(charactersIn: "\"'"))
                return cleanValue.isEmpty ? nil : cleanValue
            }
        }
        return nil
    }

    /// YAML frontmatter ブロックを除いた本文を返す
    private func stripYAMLFrontmatter(_ raw: String) -> String {
        let lines = raw.components(separatedBy: "\n")
        var count = 0
        var i = 0
        while i < lines.count {
            let t = lines[i].trimmingCharacters(in: .whitespaces)
            if t == "---" { count += 1; i += 1; if count == 2 { break } }
            else { i += 1 }
        }
        return count < 2 ? raw : lines[i...].joined(separator: "\n")
    }

    /// Markdown の指定 ## 見出し以下のテキストを返す（次の ## まで）
    private func extractMarkdownSection(_ text: String, heading: String) -> String {
        let lines = text.components(separatedBy: "\n")
        var capture = false
        var result: [String] = []
        for line in lines {
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix("##") && t.lowercased().contains(heading.lowercased()) {
                capture = true; continue
            }
            if capture && t.hasPrefix("##") { break }
            if capture && !t.isEmpty { result.append(t) }
        }
        return result.joined(separator: " ").trimmingCharacters(in: .whitespaces)
    }


    /// Extract the requested layer's text from a .jcross file, capped at `cap` chars.
    private func extractLayer(from url: URL, layer: JCrossLayer, cap: Int) -> String? {
        guard let raw = try? String(contentsOf: url, encoding: .utf8) else { return nil }
        let text: String
        switch layer {
        case .l1:
            text = extractSection(from: raw, tag: "L1_SUMMARY") ?? ""
        case .l1_5:
            let l1 = extractSection(from: raw, tag: "L1_SUMMARY") ?? ""
            let l2 = extractSection(from: raw, tag: "L2_FACTS") ?? ""
            let entities = l2.components(separatedBy: "\n")
                .filter { $0.contains("OP.ENTITY") || $0.contains("OP.STATE") }
                .joined(separator: "\n")
            text = [l1, entities].filter { !$0.isEmpty }.joined(separator: "\n")
        case .l2:
            text = extractSection(from: raw, tag: "L2_FACTS") ?? ""
        case .l3:
            text = extractSection(from: raw, tag: "L3_VERBATIM") ?? ""
        case .vera:
            text = ""   // no .jcross section for Vera — see VeraMemoryBridge
        }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return String(trimmed.prefix(cap))
    }    // MARK: - Retrieve archived nodes

    /// List all archived .jcross filenames sorted by date (newest first).
    /// - Parameter prefixFilter: If non-empty, only return files whose names start
    ///   with one of the given prefixes. Pass [] to return all files.
    func listArchived(prefixFilter: [String] = []) -> [URL] {
        let fm = FileManager.default
        let files = (try? fm.contentsOfDirectory(at: archiveDir,
                                                   includingPropertiesForKeys: [.creationDateKey])) ?? []
        return files
            .filter { $0.pathExtension == "jcross" }
            .filter { url in
                guard !prefixFilter.isEmpty else { return true }
                let name = url.lastPathComponent
                return prefixFilter.contains { name.hasPrefix($0 + "_") }
            }
            .sorted { a, b in
                let da = (try? a.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
                let db = (try? b.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
                return da > db
            }
    }

    /// Build a memory prompt injection from recent archived sessions (last N) — L2 fixed (legacy).
    func buildArchiveInjection(topK: Int = 5, relevantTo query: String = "") -> String {
        buildCrossSessionInjection(topK: topK, layer: .l2)
    }

    // MARK: - Helpers

    private func progressiveFileName(for session: ChatSession) -> String {
        let shortId = String(session.id.uuidString.prefix(8))
        return "PROG_\(shortId).jcross"   // fixed name — always overwrites
    }

    private func buildJCrossContent(session: ChatSession, label: String) -> String {
        let l1 = buildL1(session: session)
        let l2 = buildL2(from: session.messages)
        let l3 = buildL3(from: session.messages)

        let timestamp   = ISO8601DateFormatter().string(from: Date())
        let sessionDate = ISO8601DateFormatter().string(from: session.createdAt)

        return """
        ;;; JCross Memory Node — \(label)
        ;;; Session: \(session.title)
        ;;; Created: \(sessionDate)
        ;;; Archived: \(timestamp)
        ;;; ID: \(session.id.uuidString)

        [L1_SUMMARY]
        \(l1)
        [/L1_SUMMARY]

        [L2_FACTS]
        \(l2)
        [/L2_FACTS]

        [L3_VERBATIM]
        \(l3)
        [/L3_VERBATIM]
        """
    }

    // MARK: - Build layers

    private func buildL1(session: ChatSession) -> String {
        let firstUser = session.messages.first(where: { $0.role == .user })?.content ?? ""
        let preview = String(firstUser.prefix(120)).replacingOccurrences(of: "\n", with: " ")
        return "[会話:\(session.title)] [日付:\(formatDate(session.createdAt))] \(preview)"
    }

    private func buildL2(from messages: [ChatMessage]) -> String {
        var facts: [String] = []

        // Auto-detect file modifications
        let filePattern  = #"\[WRITE:\s*([^\]]+)\]"#
        let patchPattern = #"\[PATCH_FILE:\s*([^\]]+)\]"#
        let applyPattern = #"\[APPLY_PATCH:\s*([^\]]+)\]"#

        for msg in messages where msg.role == .assistant {
            for pattern in [filePattern, patchPattern, applyPattern] {
                if let regex = try? NSRegularExpression(pattern: pattern) {
                    let matches = regex.matches(in: msg.content,
                                                range: NSRange(msg.content.startIndex..., in: msg.content))
                    for m in matches {
                        if let r = Range(m.range(at: 1), in: msg.content) {
                            facts.append("OP.FACT(\"modified_file\", \"\(String(msg.content[r]).trimmingCharacters(in: .whitespaces))\")")
                        }
                    }
                }
            }
        }

        // User intent facts (first 5 user messages)
        let userMsgs = messages.filter { $0.role == .user }.prefix(5)
        for (i, msg) in userMsgs.enumerated() {
            let preview = String(msg.content.prefix(150)).replacingOccurrences(of: "\n", with: " ")
            facts.append("OP.FACT(\"user_intent_\(i)\", \"\(preview)\")")
        }

        // Entity: workspace path if detectable
        for msg in messages where msg.role == .system {
            if msg.content.contains("Workspace:") {
                let trimmed = msg.content.replacingOccurrences(of: "📂 Workspace: ", with: "")
                facts.append("OP.ENTITY(\"workspace\", \"\(trimmed.prefix(80))\")")
                break
            }
        }

        facts.append("OP.FACT(\"message_count\", \"\(messages.count)\")")
        facts.append("OP.STATE(\"layer\", \"L2\")")

        return facts.joined(separator: "\n")
    }

    private func buildL3(from messages: [ChatMessage]) -> String {
        let lines = messages.compactMap { msg -> String? in
            switch msg.role {
            case .user:      return "User: \(msg.content)"
            case .assistant: return "Agent: \(String(msg.content.prefix(500)))"
            case .system:    return nil
            }
        }
        return String(lines.joined(separator: "\n\n").prefix(4000))
    }

    private func extractSection(from raw: String, tag: String) -> String? {
        // ── Standard [TAG]...[/TAG] format (SessionMemoryArchiver nodes) ──
        let open  = "[\(tag)]"
        let close = "[/\(tag)]"
        if let start = raw.range(of: open),
           let end   = raw.range(of: close),
           start.upperBound < end.lowerBound {
            return String(raw[start.upperBound..<end.lowerBound])
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }

        // ── JCross 【Block】 format fallback (CortexEngine / MCP-written nodes) ──
        // Map requested tag → JCross section header
        let jcrossHeader: String
        switch tag {
        case "L1_SUMMARY":
            jcrossHeader = "【位相対応表】"
        case "L2_FACTS":
            jcrossHeader = "【操作対応表】"
        case "L3_VERBATIM":
            jcrossHeader = "【原文】"
        default:
            return nil
        }

        // Next JCross section starts with 【, or end of string
        guard let sectionStart = raw.range(of: jcrossHeader) else { return nil }
        let afterHeader = raw[sectionStart.upperBound...]
        // Find next 【 that marks the beginning of the following JCross section
        let nextSection = afterHeader.range(of: "【")
        let sectionText: String
        if let next = nextSection {
            sectionText = String(afterHeader[..<next.lowerBound])
        } else {
            sectionText = String(afterHeader)
        }
        let trimmed = sectionText.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func extractMetaField(from raw: String, key: String) -> String? {
        let prefix = ";;; \(key): "
        guard let line = raw.components(separatedBy: "\n").first(where: { $0.hasPrefix(prefix) })
        else { return nil }
        return String(line.dropFirst(prefix.count)).trimmingCharacters(in: .whitespaces)
    }

    private func formatDate(_ date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }

    // MARK: - Semantic Memory Search (RAG)

    /// MCP bench_search と同等のセマンティック検索をSwift内で完結させる。
    ///
    /// メモリ消費最小化設計:
    ///   - ゾーン毎最新 50 件のみスキャン（529全件読み込みを防止）
    ///   - L1 のみでスコアリング（L2/L3 は読み込まない）
    ///   - インデックスをメモリキャッシュして、ファイル IO は初回のみ
    ///   - 高スコアノードのみ必要時に L2 を追加読み込み
    func semanticSearch(
        query: String,
        topK: Int = 3,
        layer: JCrossLayer = .l2,
        budget: Int = 600
    ) -> String {
        // ── 1. トークン化 ──────────────────────────────────────────────────
        let tokens = tokenize(query)
        guard !tokens.isEmpty else { return "" }

        // ── 2. ゾーン毎最新 MAX_SCAN 件のみ収集（メモリ上限）──────────────
        let maxPerZone = 50   // 全529件 → 各ゾーン50件（計150件）に制限
        let allFiles: [URL] = [
            listZone(mcpFrontDir, prefixFilter: [],   topK: maxPerZone),
            listZone(mcpNearDir,  prefixFilter: [],   topK: maxPerZone),
            listZone(mcpMidDir,   prefixFilter: [],   topK: maxPerZone),
        ].flatMap { $0 }

        // ── 3. L1のみでスコアリング（L2は読み込まない）──────────────
        struct ScoredFile { let url: URL; let score: Int; let l1: String }
        var scored: [ScoredFile] = []

        for url in allFiles {
            // L1 のみ読み込む：大遏かつ少メモリ
            guard let raw = try? String(contentsOf: url, encoding: .utf8) else { continue }

            // Prefer [L1_SUMMARY] tag (SessionMemoryArchiver format).
            // Fall back to JCross 【位相対応表】 (CortexEngine format) which extractSection handles.
            // If still nil, use raw content prefix as last resort so no node is silently skipped.
            let l1 = extractSection(from: raw, tag: "L1_SUMMARY")
                  ?? String(raw.prefix(300))
            let l1Lower = l1.lowercased()

            var score = 0
            for token in tokens {
                if l1Lower.contains(token.lowercased()) { score += 2 }
            }
            // Also scan Kanji tags in 【空間座相】 for JCross nodes
            if score == 0, let kanjiLine = raw.components(separatedBy: "\n").first(where: { $0.contains("[") && $0.contains(":") && !$0.contains("】") }) {
                let kanjiLower = kanjiLine.lowercased()
                for token in tokens {
                    if kanjiLower.contains(token.lowercased()) { score += 1 }
                }
            }
            if score > 0 {
                scored.append(ScoredFile(url: url, score: score, l1: l1))  // l1を保持
            }
        }

        // スコア降順 → 同スコアは日付降順
        let ranked = scored.sorted { a, b in
            if a.score != b.score { return a.score > b.score }
            let da = (try? a.url.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
            let db = (try? b.url.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast
            return da > db
        }.prefix(topK)

        guard !ranked.isEmpty else { return "" }

        // ── 4. 注入文字列を構築 ───────────────────────────────────────────────
        // Search 結果は常に Zone Injection の「補完」なので budget は控えめに
        // (L3 → L2 で代用: let layer = layer == .l3 ? .l2 : layer はコール側でインライン済み)
        let perItemCap = max(80, budget / ranked.count)
        var parts: [String] = []
        var remaining = budget

        for hit in ranked where remaining > 0 {
            let chunk: String
            if layer == .l1 {
                // Nano: L1 はスコアリング時に既読み込んである—追加 IO 不要
                chunk = String(hit.l1.prefix(min(perItemCap, remaining)))
            } else {
                // Small+: 高スコアのみ L2 を追加読み込み
                chunk = extractLayer(from: hit.url, layer: layer == .l3 ? .l2 : layer,
                                     cap: min(perItemCap, remaining)) ?? String(hit.l1.prefix(min(perItemCap, remaining)))
            }
            guard !chunk.isEmpty else { continue }
            let name = hit.url.deletingPathExtension().lastPathComponent
            let zone = zoneLabel(for: hit.url)
            let entry = "《检索ヒット: \(zone) \(name) (score:\(hit.score))》\n\(chunk)"
            parts.append(entry)
            remaining -= entry.count
        }

        guard !parts.isEmpty else { return "" }

        return """

        [MEMORY SEARCH — query: "\(String(query.prefix(60)))" — \(parts.count) hit(s)]
        \(parts.joined(separator: "\n---\n"))
        [/MEMORY SEARCH]
        """
    }

    // MARK: - Semantic Search Helpers

    /// クエリを検索トークンに分解する。
    /// 英語: スペース区切り、記号除去
    /// 日本語: 漢字・カタカナ連続列を2文字以上のチャンクとして抽出
    private func tokenize(_ text: String) -> [String] {
        // ── 英語トークン ──────────────────────────────────────────────────────
        let ascii = text
            .components(separatedBy: .whitespacesAndNewlines)
            .map { $0.trimmingCharacters(in: .punctuationCharacters) }
            .filter { $0.count >= 2 }

        // ── 日本語トークン（漢字・カタカナ2文字以上の連続） ────────────────
        var jpTokens: [String] = []
        var buf = ""
        for ch in text {
            let scalar = ch.unicodeScalars.first!.value
            let isKanji  = scalar >= 0x4E00 && scalar <= 0x9FFF
            let isKatana = scalar >= 0x30A0 && scalar <= 0x30FF
            let isHira   = scalar >= 0x3040 && scalar <= 0x309F
            if isKanji || isKatana || isHira {
                buf.append(ch)
            } else {
                if buf.count >= 2 { jpTokens.append(buf) }
                buf = ""
            }
        }
        if buf.count >= 2 { jpTokens.append(buf) }

        // 重複除去して返す
        return Array(Set(ascii + jpTokens)).filter { !$0.isEmpty }
    }

    /// ファイルが属するゾーンのラベルを返す
    private func zoneLabel(for url: URL) -> String {
        let path = url.path
        if path.contains("/front/") { return "front⚡" }
        if path.contains("/near/")  { return "near🔵" }
        if path.contains("/mid/")   { return "mid💾" }
        return "archive"
    }

    // MARK: - Deep→Front Topology Alias

    /// モデルがejectされた時に呼ばれる。
    /// Kanjiトポロジータグのみを mid/ に保存し、deepにある詳細情報が
    /// なくてもcognitive engineが素早くモデル利用履歴を参照できるようにする。
    ///
    /// ファイル名: MODEL_ALIAS_{safeId}_{timestamp}.jcross
    /// ゾーン: mid/ (SKILL_* と同じスロット — 低コスト、GCに強い)
    ///
    /// - Parameters:
    ///   - modelId: HuggingFace / Ollama のモデルID (例: "mlx-community/gemma-3-27b-it-4bit")
    ///   - backend: "MLX" または "Ollama"
    ///   - kanjiTags: Kanjiトポロジータグ文字列 (例: "[技:1.0] [速:0.8] [軽:0.7]")
    func writeDeepAlias(modelId: String, backend: String, kanjiTags: String) {
        let ts       = ISO8601DateFormatter().string(from: Date())
        let tsInt    = Int(Date().timeIntervalSince1970)
        let safeId   = modelId
            .replacingOccurrences(of: "/", with: "-")
            .replacingOccurrences(of: ":", with: "-")
            .filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }
        let shortId  = String(safeId.suffix(24))
        let fileName = "MODEL_ALIAS_\(shortId)_\(tsInt).jcross"

        // L1: 1行でモデルIDとバックエンドを表現
        let displayName = modelId.components(separatedBy: "/").last ?? modelId
        let l1 = "[\(backend)モデル履歴] \(displayName) ejected \(kanjiTags)"

        // L2: 構造化ファクト（検索エンジンが参照するキー）
        let l2 = """
        OP.FACT("model_id", "\(modelId)")
        OP.FACT("backend", "\(backend)")
        OP.FACT("display_name", "\(displayName)")
        OP.FACT("kanji_tags", "\(kanjiTags)")
        OP.FACT("ejected_at", "\(ts)")
        OP.STATE("type", "MODEL_ALIAS")
        OP.STATE("zone_hint", "mid")
        """

        // L3: 完全なモデルID（将来の自動再ロード等で使える）
        let l3 = """
        Model ejected from Verantyx IDE.
        Full ID: \(modelId)
        Backend: \(backend)
        Kanji topology: \(kanjiTags)
        Timestamp: \(ts)

        This node is a lightweight Deep→Front alias.
        The full inference history lives in deep/ but can be recovered
        by querying for model_id="\(modelId)" in the cognitive engine.
        """

        let content = """
        ;;; JCross Memory Node — MODEL_ALIAS
        ;;; Session: \(displayName) (\(backend))
        ;;; Created: \(ts)
        ;;; Archived: \(ts)
        ;;; ID: model-alias-\(shortId)

        [L1_SUMMARY]
        \(l1)
        [/L1_SUMMARY]

        [L2_FACTS]
        \(l2)
        [/L2_FACTS]

        [L3_VERBATIM]
        \(l3)
        [/L3_VERBATIM]
        """

        // mid/ に書き込む（SKILL_* と同じゾーン — 低コスト）
        let midPath = mcpMidDir.appendingPathComponent(fileName)
        try? content.write(to: midPath, atomically: true, encoding: .utf8)

        // 後方互換: legacy archive にも保存
        let legacyPath = archiveDir.appendingPathComponent(fileName)
        try? content.write(to: legacyPath, atomically: true, encoding: .utf8)
    }
}

