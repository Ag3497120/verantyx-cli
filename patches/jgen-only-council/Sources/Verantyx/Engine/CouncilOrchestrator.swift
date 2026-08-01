import Foundation

/// Milestone E: a faithful Swift port of `verantyx_council.py`'s
/// `Council.deliberate()`, superseding Milestone D's deliberately
/// simplified "essence" port. Uses `DivergencePacket`/`DivergenceExchange`
/// (the `S = A·C+B·E−C·R+D·N` scoring system), `SoftSequence`
/// (`dist_to_soft_sequence`'s multi-token soft injection), and a
/// `_perturb_test`-style fragility probe before accepting convergence.
///
/// Remaining, explicitly-stated simplifications vs. the Python original:
/// - No external "sage"/"worker"/"bridge" participant tiers (a 3-level
///   escalation ladder that recruits progressively stronger models
///   mid-deliberation). Escalation here is binary: once triggered, it's
///   recorded as a fragility/uncertainty signal that keeps the loop going
///   rather than accepting early convergence, and the actual hand-off to a
///   stronger backend (`escalationModel`) happens once, after the loop, as
///   in Milestone D.
/// - `_plan_steal`'s "donor" is always the configured `escalationModel`
///   (Ollama) rather than a same-architecture JGEN worker/sage -- the
///   stolen "plan" is encoded back into JGEN's hidden space via
///   `JCrossChatManager.encodeText` before use, so it's still a real JGEN
///   hidden vector by the time it's injected.
/// - The reinfer step's reconciliation "hint" is the highest-confidence
///   packet's own distribution (soft-sequence-injected into the split/
///   divergent roles), rather than `proposition_hint_text`'s bespoke
///   summary string. `protect_dist_mass` is approximated: a reinfer/round
///   update is only kept if it doesn't collapse the role's top-candidate
///   probability by more than half; otherwise the prior opinion is kept.
/// - No `ConceptLexicon` soft-lock (a learned per-concept direction) --
///   no equivalent learned-concept store exists on the Swift side.
/// - No cross-machine "2台" council -- all roles share one `JCrossEngine`.
actor CouncilOrchestrator {
    static let shared = CouncilOrchestrator()

    private init() {}

    enum InjectionPolicy: String, Codable, CaseIterable, Identifiable {
        case none, planSteal, earlySteal, deepRounds
        var id: String { rawValue }

        var displayName: String {
            switch self {
            case .none:       return "none"
            case .planSteal:  return "plan_steal"
            case .earlySteal: return "early_steal"
            case .deepRounds: return "deep_rounds"
            }
        }
    }

    /// `Codable` so `CouncilSettingsStore` can persist the user's council
    /// setup across launches (all members are already Codable: `JCrossLayer`
    /// in SessionStore.swift, `InjectionPolicy` above).
    struct Config: Codable {
        var roleCount: Int = 3               // 2-5
        var roundsCap: Int = 4
        var injectionPolicy: InjectionPolicy = .none
        var useVeraMemory: Bool = true
        /// Independent multi-select L1/L1.5/L2/L3 zone-memory sources
        /// (empty = none). Replaces Milestone D's single-select
        /// `useZoneMemory` + `zoneLayer`.
        var zoneLayers: Set<JCrossLayer> = []
        /// Milestone C's JGEN-hidden-state eternal memory.
        var useEternalMemory: Bool = false
        var escalateOnLowConfidence: Bool = true
        var escalationConfidenceThreshold: Float = 0.6
        /// Ollama model name to hand the council's conclusion off to when
        /// escalating, and (for `.planSteal`/`.earlySteal`) the "donor" for
        /// the stolen-plan vector. Empty = escalation is reported but no
        /// call is made, and plan-steal is skipped.
        var escalationModel: String = ""
        /// Who runs Layer 2 (execution).
        ///
        /// `.inlineOllama` (default, and what the Vector Lab uses) keeps the
        /// original behavior: one non-agentic `OllamaClient` call at the end
        /// of `deliberate`. `.external` returns the handoff and lets the
        /// caller run a real tool-using agent -- see `LayeredRunOrchestrator`.
        var executionMode: ExecutionMode = .inlineOllama
    }

    enum ExecutionMode: String, Codable {
        case inlineOllama
        case external
    }

    struct Handoff {
        let conclusion: String
        let evidence: [String]
        let nextAction: String
        let confidence: Float
        /// A real sentence expanding on `conclusion`.
        ///
        /// `conclusion` is the council's consensus *token* (the top-1 decode
        /// of the consensus vector), which is fine as a convergence signal but
        /// nearly contentless as an instruction. Layer 2 is a tool-using agent
        /// that needs something actionable, so after the deliberation loop the
        /// same JGEN model decodes a short prose statement of what the council
        /// settled on. Empty when generation failed -- `asText` then falls back
        /// to the token alone, i.e. exactly the old behavior.
        var detail: String = ""

        var asText: String {
            var lines = ["[COUNCIL CONCLUSION] \(conclusion)"]
            if !detail.isEmpty { lines.append("[DETAIL] \(detail)") }
            lines.append("[EVIDENCE] \(evidence.joined(separator: " | "))")
            lines.append("[NEXT ACTION] \(nextAction)")
            lines.append("[CONFIDENCE] \(String(format: "%.2f", confidence))")
            return lines.joined(separator: "\n")
        }
    }

    struct RoleTrace {
        let role: String
        let answer: String
        let entropy: Float
    }

    struct RoundTrace {
        let round: Int
        let roles: [RoleTrace]
        let converged: Bool
        let divergence: Float?
        let action: String?
        let perturbRecovered: Bool?
    }

    struct Result {
        let handoff: Handoff
        let roundTraces: [RoundTrace]
        let escalated: Bool
        let finalAnswer: String?
    }

    enum CouncilError: Error, LocalizedError {
        case notLoaded
        var errorDescription: String? {
            "No JGEN model loaded -- load one in Settings → JGEN first, then it doubles as the council's shared engine."
        }
    }

    /// Fixed 5-role cast, ported verbatim from `verantyx_council.py`'s
    /// `ROLES`. Role *count* (2-5) is configurable by taking a prefix of
    /// this cast, matching the existing UI control.
    private static let fullRoleCast: [(name: String, directive: String)] = [
        ("Commander", "You lead this analysis. State the single decisive answer."),
        ("Scout-A",   "Explore alternative interpretations and hidden assumptions."),
        ("Scout-B",   "Consider the opposite conclusion and test it."),
        ("Worker-1",  "Work through the problem step by step precisely."),
        ("Worker-2",  "Verify the reasoning and correct any mistake."),
    ]

    private static let scoutUncertainThreshold: Float = 8.0

    /// `onProgress`, when supplied, receives one `.systemLog` event per
    /// semantic milestone (memory recalled, candidates generated, a round
    /// of vector deliberation run, a candidate rejected, a robustness
    /// check run) tagged with the `§TL:` marker `ReasoningTimeline.swift`
    /// looks for. This is what makes a >10-minute council run legible as
    /// "generating and verifying multiple hypotheses" instead of an opaque
    /// wait -- see ReasoningTimelineView. Optional and additive: existing
    /// callers (VectorLabView) that don't pass one see no behavior change.
    func deliberate(
        question: String, config: Config,
        onProgress: (@Sendable (LoopEvent) async -> Void)? = nil
    ) async throws -> Result {
        let chat = JCrossChatManager.shared
        guard await chat.isLoaded else { throw CouncilError.notLoaded }
        @Sendable func tick(_ category: String, _ label: String) async {
            await onProgress?(.systemLog("§TL:\(category):\(label)"))
        }
        await tick("task", "タスクを受理 (\(question.prefix(60)))")

        // ── Memory prefix ──
        var memoryPrefix = ""
        if config.useVeraMemory {
            let veraText = await VeraMemoryBridge.recall(for: question)
            if !veraText.isEmpty { memoryPrefix += veraText + "\n" }
        }
        for layer in config.zoneLayers {
            let zoneText = SessionMemoryArchiver.shared.buildZonePriorityInjection(layer: layer)
            if !zoneText.isEmpty { memoryPrefix += zoneText + "\n" }
        }
        if config.useEternalMemory {
            let eternalText = await EternalMemoryStore.shared.recallBlock(for: question)
            if !eternalText.isEmpty { memoryPrefix += eternalText + "\n" }
        }
        // Milestone L: pseudo-multimodal visual memory. This is
        // screen-to-screen recall, not text-to-screen -- it only produces
        // anything when there's a *current* screen to compare against
        // (a live HiddenWindowAutomation session), so it's a no-op for a
        // plain text question with no window target. That's the correct
        // fallback, not a bug: a Vision feature print cannot be produced
        // from words alone.
        if await MainActor.run(body: { CouncilSettingsStore.shared.useVisualMemory }),
           let img = await HiddenWindowAutomation.shared.captureWindowImage() {
            let visualText = await VisualMemoryStore.shared.recallBlock(base64Image: img)
            if !visualText.isEmpty { memoryPrefix += visualText + "\n" }
        }

        await tick("memory", "記憶・画面状態を確認")

        let roleCount = min(max(config.roleCount, 2), Self.fullRoleCast.count)
        let roles = Array(Self.fullRoleCast.prefix(roleCount))

        func rolePrompt(_ role: (name: String, directive: String)) -> String {
            "<|im_start|>system\n\(memoryPrefix)\(role.directive)<|im_end|>\n" +
            "<|im_start|>user\n\(question)<|im_end|>\n" +
            "<|im_start|>assistant\nThe answer is"
        }

        var roundsCap = config.roundsCap
        if config.injectionPolicy == .deepRounds { roundsCap = max(roundsCap, 5) }

        // ── Round 0: independent forward pass per role ──
        var opinions: [String: [Float]] = [:]
        var distributions: [String: [JCrossChatManager.TopKText]] = [:]
        var packets: [DivergencePacket] = []
        for role in roles {
            let tokens = try await chat.tokenize(rolePrompt(role))
            let z = try await chat.encodeTokens(tokens)
            let dist = try await chat.topKDistributionText(vector: z, k: 32)
            opinions[role.name] = z
            distributions[role.name] = dist
            packets.append(DivergencePacketBuilder.packet(role: role.name, vector: z, distribution: dist))
        }

        await tick("candidates", "\(roles.count)役割が独立に候補を生成")

        guard let commanderVec = opinions[roles[0].name] else { throw CouncilError.notLoaded }
        let baseNorm = sqrt(commanderVec.reduce(Float(0)) { $0 + $1 * $1 })
        let intentN = Self.normalize(commanderVec)

        var exchange = DivergenceExchange.exchange(packets: packets, reinferDone: false)

        // ── Optional single reinfer pass on split/divergent roles ──
        if exchange.action == .reinfer, !exchange.splitRoles.isEmpty,
           let hintRole = packets.max(by: { $0.confidence < $1.confidence })?.role,
           let hintDist = distributions[hintRole] {
            let soft = try await SoftSequence.distToSoftSequence(distribution: hintDist, maxSoft: 16, chat: chat)
            for name in exchange.splitRoles {
                guard let role = roles.first(where: { $0.name == name }) else { continue }
                let tokens = try await chat.tokenize(rolePrompt(role))
                let newZ = try await chat.encodeSoftTokens(softVectors: soft, tokens: tokens)
                let newDist = try await chat.topKDistributionText(vector: newZ, k: 32)
                let oldTop = distributions[name]?.first?.prob ?? 0
                let newTop = newDist.first?.prob ?? 0
                // protect_dist_mass approximation: keep the update only if
                // it didn't collapse the top-candidate mass by more than
                // half; otherwise keep the pre-reinfer opinion.
                if oldTop <= 0 || newTop >= 0.5 * oldTop {
                    opinions[name] = newZ
                    distributions[name] = newDist
                }
            }
            packets = roles.compactMap { role in
                guard let z = opinions[role.name], let dist = distributions[role.name] else { return nil }
                return DivergencePacketBuilder.packet(role: role.name, vector: z, distribution: dist)
            }
            exchange = DivergenceExchange.exchange(packets: packets, reinferDone: true)
        }

        var roundTraces: [RoundTrace] = [
            RoundTrace(
                round: 0,
                roles: roles.map { role in
                    RoleTrace(
                        role: role.name,
                        answer: distributions[role.name]?.first?.text ?? "",
                        entropy: DivergencePacketBuilder.shannonEntropy((distributions[role.name] ?? []).map(\.prob))
                    )
                },
                converged: false,
                divergence: exchange.meanDivergence,
                action: exchange.action.rawValue,
                perturbRecovered: nil
            )
        ]

        var round = 0
        var prevTop1: String? = nil
        var lastConsensusTop1: String = ""
        var perturbDone = false
        var fragile = false
        var escalated = false
        var zPlan: [Float]? = nil
        var planDone = false

        if config.injectionPolicy == .earlySteal {
            zPlan = try? await planSteal(question: question, escalationModel: config.escalationModel, chat: chat)
            planDone = true
        }

        mainLoop: while round < roundsCap {
            round += 1
            await tick("council", "ベクトル合議を実行 (ラウンド\(round)/\(roundsCap))")
            var vecs: [String: [Float]] = [:]
            var weights: [String: Float] = [:]
            var confidentTop1: [String] = []
            var roleTraces: [RoleTrace] = []

            for role in roles {
                let z = opinions[role.name] ?? commanderVec
                let dist = try await chat.topKDistributionText(vector: z, k: 32)
                distributions[role.name] = dist
                let entropy = DivergencePacketBuilder.shannonEntropy(dist.map(\.prob))
                let top1 = dist.first?.text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
                let zn = Self.normalize(z)
                let coherence = Self.dot(zn, intentN)
                var w = max(coherence, 0.05) / (1.0 + entropy)
                if let si = exchange.weights[role.name] {
                    w = 0.5 * w + 0.5 * si * (w + 0.1)
                }
                vecs[role.name] = zn
                weights[role.name] = w
                if entropy < 4.0 { confidentTop1.append(top1) }
                roleTraces.append(RoleTrace(role: role.name, answer: top1, entropy: entropy))
            }

            let totalW = max(weights.values.reduce(0, +), 0.0001)
            var consensus = [Float](repeating: 0, count: commanderVec.count)
            for (name, zn) in vecs {
                let w = (weights[name] ?? 0) / totalW
                for i in 0..<consensus.count { consensus[i] += w * zn[i] }
            }
            let consensusNorm = sqrt(consensus.reduce(Float(0)) { $0 + $1 * $1 })
            if consensusNorm > 0 { consensus = consensus.map { $0 / consensusNorm * baseNorm } }
            let consensusDist = try await chat.topKDistributionText(vector: consensus, k: 32)
            let consensusTop1 = consensusDist.first?.text.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if !consensusTop1.isEmpty { lastConsensusTop1 = consensusTop1 }
            let consensusTop1Key = consensusTop1.lowercased()

            let allVecs = Array(vecs.values)
            var pairSum: Float = 0
            var pairCount = 0
            for i in 0..<allVecs.count {
                for j in (i + 1)..<allVecs.count {
                    pairSum += Self.dot(allVecs[i], allVecs[j])
                    pairCount += 1
                }
            }
            _ = pairCount > 0 ? pairSum / Float(pairCount) : 1  // agreement cosine (trace-only, not gating)

            let unanimous = !confidentTop1.isEmpty && confidentTop1.allSatisfy { Self.answersAgree($0, consensusTop1Key) }

            let scoutEntropies = ["Scout-A", "Scout-B"].compactMap { name -> Float? in
                guard roles.contains(where: { $0.name == name }) else { return nil }
                return DivergencePacketBuilder.shannonEntropy((distributions[name] ?? []).map(\.prob))
            }
            let scoutUncertain = !scoutEntropies.isEmpty
                && (scoutEntropies.reduce(0, +) / Float(scoutEntropies.count)) > Self.scoutUncertainThreshold

            let converged = unanimous && !(scoutUncertain && config.escalateOnLowConfidence && !escalated)
            let stable = escalated && prevTop1 != nil && consensusTop1Key == prevTop1
            prevTop1 = consensusTop1Key

            if converged || stable {
                if !perturbDone && round < roundsCap {
                    perturbDone = true
                    await tick("verify", "候補「\(consensusTop1)」の頑健性を検証中 (perturbテスト)")
                    let (recovered, _, _) = try await perturbTest(
                        roles: roles, rolePrompt: rolePrompt, consensus: consensus,
                        consensusDist: consensusDist, chat: chat
                    )
                    roundTraces.append(RoundTrace(round: round, roles: roleTraces, converged: true, divergence: nil, action: nil, perturbRecovered: recovered))
                    if recovered {
                        await tick("accept", "候補「\(consensusTop1)」が頑健性検証を通過")
                        break mainLoop
                    }
                    await tick("reject", "候補「\(consensusTop1)」を棄却 (perturbテストで不安定)")
                    fragile = true
                } else {
                    roundTraces.append(RoundTrace(round: round, roles: roleTraces, converged: true, divergence: nil, action: nil, perturbRecovered: nil))
                    await tick("accept", "候補「\(consensusTop1)」で収束")
                    break mainLoop
                }
            } else {
                roundTraces.append(RoundTrace(round: round, roles: roleTraces, converged: false, divergence: nil, action: nil, perturbRecovered: nil))
                await tick("reject", "候補「\(consensusTop1)」を棄却 (役割間で未合意)")
            }

            if round == roundsCap { break mainLoop }

            let needHelp = !unanimous || scoutUncertain || fragile
            if config.escalateOnLowConfidence && needHelp && !escalated {
                escalated = true
            }

            let wantSteal = !unanimous || config.injectionPolicy == .planSteal
            if !planDone && wantSteal {
                planDone = true
                zPlan = try? await planSteal(question: question, escalationModel: config.escalationModel, chat: chat)
            }

            var soft = try await SoftSequence.distToSoftSequence(distribution: consensusDist, maxSoft: 12, chat: chat)
            if let zPlan,
               let planDist = try? await chat.topKDistributionText(vector: zPlan, layerName: "lm_head", k: 1),
               let planTop = planDist.first {
                let planTokens = try await chat.tokenize(planTop.text)
                if let firstId = planTokens.first {
                    soft.insert(try await chat.embeddingRow(tokenId: firstId), at: 0)
                }
            }

            for role in roles {
                let tokens = try await chat.tokenize(rolePrompt(role))
                opinions[role.name] = try await chat.encodeSoftTokens(softVectors: soft, tokens: tokens)
            }
        }

        let finalRoles = roundTraces.last?.roles ?? []
        let avgEntropy = finalRoles.isEmpty ? 0 : finalRoles.map(\.entropy).reduce(0, +) / Float(finalRoles.count)
        let confidence = 1.0 / (1.0 + avgEntropy)
        let answers = finalRoles.map(\.answer).filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        // Prefer a non-empty majority vote; fall back to the last consensus
        // top-1 (preserves casing) so jgen-only handoffs aren't blank when
        // role traces decoded empty / stopword-only strings.
        let conclusion = Self.mostCommonAnswer(answers)
            ?? answers.first
            ?? (lastConsensusTop1.isEmpty ? "" : lastConsensusTop1)
        let lowConfidence = confidence < config.escalationConfidenceThreshold
        let shouldEscalate = config.escalateOnLowConfidence && lowConfidence

        // Expand the consensus token into an actual sentence -- see
        // Handoff.detail. Best-effort: a failure here degrades the handoff
        // back to the token-only form rather than failing the deliberation.
        // Prompt is deliberately free of bracketed ROLE/TOKEN placeholders
        // that small JGENs tend to parrot (Hello, world! / [CONSENSUS TOKEN]).
        let detailPromptUser: String
        if conclusion.isEmpty {
            detailPromptUser = "User said: \(question)\nWrite one short reply in the user's language."
        } else {
            detailPromptUser = "User: \(question)\nCouncil settled on: \(conclusion)\nRole notes: \(answers.joined(separator: ", "))\nWrite one or two concrete sentences stating that conclusion. No labels, no brackets."
        }
        let detail = (try? await chat.generate(
            conversation: [
                ("system", "You restate a council decision briefly. No control tags. Match the user's language."),
                ("user", detailPromptUser)
            ],
            maxTokens: 96
        ))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        let handoff = Handoff(
            conclusion: conclusion,
            evidence: finalRoles.map { "\($0.role): \($0.answer)" },
            nextAction: shouldEscalate
                ? "Escalate -- council confidence below threshold or roles disagree."
                : "Proceed with council conclusion on JGEN (no escalation).",
            confidence: confidence,
            detail: detail
        )

        var finalAnswer: String? = nil
        if shouldEscalate {
            escalated = true
            // `.external` means the caller (LayeredRunOrchestrator) owns
            // Layer 2/3 and will run a real tool-using agent instead; doing
            // the one-shot call here too would duplicate the work.
            if config.executionMode == .inlineOllama,
               !config.escalationModel.trimmingCharacters(in: .whitespaces).isEmpty {
                finalAnswer = await OllamaClient.shared.generateConversation(
                    model: config.escalationModel,
                    messages: [
                        ("system", "You are the execution agent. The council below has deliberated and handed off its conclusion. Use it to give a final, direct answer."),
                        ("user", handoff.asText + "\n\n[ORIGINAL QUESTION] \(question)")
                    ]
                )
            }
        }

        await tick("done", escalated ? "結論を確定 → 上位モデルへ引き継ぎ" : "結論を確定（JGEN継続）")

        return Result(handoff: handoff, roundTraces: roundTraces, escalated: escalated, finalAnswer: finalAnswer)
    }

    // MARK: - Helpers

    private func planSteal(question: String, escalationModel: String, chat: JCrossChatManager) async throws -> [Float]? {
        let model = escalationModel.trimmingCharacters(in: .whitespaces)
        guard !model.isEmpty else { return nil }
        let planQuestion = "What single concept, method, or first step is key to solving this? Answer with one word.\n\(question)"
        guard let answerText = await OllamaClient.shared.generateConversation(model: model, messages: [("user", planQuestion)]),
              !answerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
        // Encode the donor's answer back into JGEN hidden space so the
        // "stolen plan" is a real JGEN vector by the time it's injected.
        return try? await chat.encodeText(answerText)
    }

    /// Port of `_perturb_test`: blend the consensus with its strongest
    /// disagreeing rival as a synthetic "lie," inject it into every role's
    /// ORIGINAL prompt (not the accumulated opinions), and check whether
    /// the true winner survives.
    private func perturbTest(
        roles: [(name: String, directive: String)],
        rolePrompt: (_ role: (name: String, directive: String)) -> String,
        consensus: [Float],
        consensusDist: [JCrossChatManager.TopKText],
        chat: JCrossChatManager
    ) async throws -> (recovered: Bool, drift: Float, testTop1: String?) {
        guard consensusDist.count > 1 else { return (true, 1.0, nil) }
        let winner = consensusDist[0].text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard let rival = consensusDist.dropFirst().first(where: {
            !Self.answersAgree($0.text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased(), winner)
        }) else {
            return (true, 1.0, nil)
        }

        let rivalVector = try await chat.encodeText(rival.text)
        let baseNorm = sqrt(consensus.reduce(Float(0)) { $0 + $1 * $1 })
        let blended = zip(Self.normalize(consensus), Self.normalize(rivalVector)).map { 0.4 * $0 + 0.6 * $1 }
        let blendedNorm = sqrt(blended.reduce(Float(0)) { $0 + $1 * $1 })
        let lie = blendedNorm > 0 ? blended.map { $0 / blendedNorm * baseNorm } : blended

        var testVecs: [[Float]] = []
        for role in roles {
            let tokens = try await chat.tokenize(rolePrompt(role))
            let z = try await chat.encodeSoftTokens(softVectors: [lie], tokens: tokens)
            testVecs.append(Self.normalize(z))
        }
        guard !testVecs.isEmpty else { return (true, 1.0, nil) }
        var testConsensus = [Float](repeating: 0, count: testVecs[0].count)
        for v in testVecs { for i in 0..<testConsensus.count { testConsensus[i] += v[i] / Float(testVecs.count) } }
        let testNorm = sqrt(testConsensus.reduce(Float(0)) { $0 + $1 * $1 })
        if testNorm > 0 { testConsensus = testConsensus.map { $0 / testNorm * baseNorm } }

        let testDist = try await chat.topKDistributionText(vector: testConsensus, k: 8)
        let testTop1 = testDist.first?.text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let drift = Self.dot(Self.normalize(testConsensus), Self.normalize(consensus))
        let recovered = testTop1.map { Self.answersAgree($0, winner) } ?? false
        return (recovered, drift, testTop1)
    }

    private static func normalize(_ v: [Float]) -> [Float] {
        let n = sqrt(v.reduce(Float(0)) { $0 + $1 * $1 })
        guard n > 0 else { return v }
        return v.map { $0 / n }
    }

    private static func dot(_ a: [Float], _ b: [Float]) -> Float {
        guard a.count == b.count else { return 0 }
        var s: Float = 0
        for i in 0..<a.count { s += a[i] * b[i] }
        return s
    }

    /// Substring-containment agreement check, matching the Python
    /// original's `answers_agree` (subword tokenization can split answers
    /// unevenly across roles, so exact match alone is too strict).
    private static func answersAgree(_ a: String, _ b: String) -> Bool {
        let na = a.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let nb = b.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if na.isEmpty || nb.isEmpty { return false }
        if na == nb { return true }
        let (shorter, longer) = na.count <= nb.count ? (na, nb) : (nb, na)
        return shorter.count >= 3 && longer.contains(shorter)
    }

    private static func mostCommonAnswer(_ answers: [String]) -> String? {
        var counts: [String: Int] = [:]
        for a in answers { counts[a, default: 0] += 1 }
        return counts.max(by: { $0.value < $1.value })?.key
    }
}
