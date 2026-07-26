import Foundation
import Combine

struct SteeringInterruptError: Swift.Error {
    let command: String
}

enum TaskRaceResult: Sendable {
    case response(String?)
    case steering(String)
}

// MARK: - AgentLoop
// Multi-turn autonomous agent execution loop.
// Enables: "create a Python calculator" → scaffold → run → verify → done
//
// Loop flow:
//  1. Build prompt (instruction + cortex memory + file context)
//  2. Call LLM
//  3. Parse tool calls from response
//  4. Execute tools (MKDIR, WRITE_FILE, RUN, WORKSPACE)
//  5. Feed results back → repeat until [DONE] or safety gate
//
// ── Turn Limit Policy ──────────────────────────────────────────────────────
//  • AI Priority Mode : UNLIMITED turns. Circuit breaker kills loops where
//    AI repeats the exact same tool call 3 times in a row (hash比較).
//  • Human Mode       : UNLIMITED turns. After 5 consecutive unanswered tool
//    calls, AI must emit a Yield — a status report asking the user to confirm.
//
// ── OOM Prevention ────────────────────────────────────────────────────────
//  When conversation grows beyond COMPRESS_THRESHOLD chars, old turns are
//  offloaded to CortexEngine and pruned from the live context window.

actor AgentLoop {

    static let shared = AgentLoop()
    private let executor = AgentToolExecutor()

    // ── Safety gates (not a hard turn limit) ──────────────────────────────
    /// AI Priority: abort if the last N AI outputs are identical (stuck loop)
    private let circuitBreakerWindow = 3

    /// Human Mode: after this many consecutive tool-only turns, emit a Yield
    private let yieldAfterToolTurns = 5

    // compressThreshold is now per-model (from ModelProfile)

    // MARK: - Main loop

    func run(
        instruction: String,
        images: [AttachedImage] = [],
        contextFile: String? = nil,
        contextFileName: String? = nil,
        workspaceURL: URL?,
        modelStatus: AppState.ModelStatus,
        activeModel: String,
        cortex: CortexEngine?,
        selfFixMode: Bool = false,
        operationMode: OperationMode = .gatekeeper,
        memoryLayer: JCrossLayer = .l2,   // ➤ cross-session injection depth
        isFirstSession: Bool = false,         // ➤ inject self-awareness task on first turn
        chatSessionId: String? = nil,         // ➤ セッション間で維持するVXTimeline ID
        previousMessages: [ChatMessage] = [], // ➤ 直前のチャット履歴
        onProgress: @escaping @Sendable (LoopEvent) async -> Void
    ) async {

        var currentWorkspace = workspaceURL
        var conversation: [(role: String, content: String)] = []
        var turn = 0

        // ── Vera-α: direct-answer fast path ───────────────────────────────
        // Skips the LLM call entirely for a high-confidence, already-
        // grounded ANSWER from Vera. Falls through to the normal turn on
        // anything less confident — see VeraMemoryBridge.tryDirectAnswer.
        if memoryLayer == .vera, let direct = await VeraMemoryBridge.tryDirectAnswer(for: instruction) {
            await onProgress(.done(message: direct, workspace: currentWorkspace))
            return
        }

        // ── Model tier detection ──────────────────────────────────────────
        let profile = ModelProfileDetector.detect(modelId: activeModel)
        let compressThreshold = profile.tier.compressThreshold
        await onProgress(.aiMessage(
            AppLanguage.shared.t("🤖 Model Profile: \(activeModel) → \(profile.tier.displayName) | Max tokens: \(profile.tier.maxTokens) | Temp: \(profile.tier.temperature)", "🤖 モデルプロファイル: \(activeModel) → \(profile.tier.displayName) | Max tokens: \(profile.tier.maxTokens) | Temp: \(profile.tier.temperature)"
            )
        ))

        // ── Safety state ──────────────────────────────────────────────────
        /// Circuit breaker: rolling hash of last N raw responses (AI Priority)
        var recentResponseHashes: [Int] = []
        /// Yield counter: consecutive turns where AI only called tools (Human Mode)
        var consecutiveToolOnlyTurns = 0
        /// IDE Fix sandbox: consecutive blocked tool calls (loop circuit breaker)
        var consecutiveBlockedCalls = 0
        /// Total chars in conversation (for OOM guard)
        var totalConversationChars = 0
        /// Auditor Review (B-to-A Handover)
        var hasPassedAuditorReview = false

        // ── VX-Loop (Nano Cortex Protocol) state ──────────────────────────
        /// セッションID: 外部から渡されたものを優先。なければ新規生成
        /// （外部=AppState.vxChatSessionId で会話全体を通じて同一IDを維持）
        let vxSessionId = chatSessionId ?? String(UUID().uuidString.prefix(8))
        /// VX-Loop が有効か (nano/small ティアで自動有効化)
        let vxLoopEnabled = profile.tier == .nano || profile.tier == .small
        /// SearchGate の最新実行結果（次ターンの注入用）
        var vxLastSearchResult = ""
        /// 混乱検知リトライ済みフラグ（1ターンにつき最大1回のみリトライ）
        var didConfusionRetry = false
        /// ReAct リトライコンテキスト（検索失敗の自律回復制御）
        var reactContext = ReActRetryContext()

        // ── Build initial system prompt ───────────────────────────────────
        // Vera-α layer: opt-in per session (see VeraMemoryBridge.swift for
        // why this isn't wired into CortexEngine's always-on path instead).
        let cortexMemorySection = await cortex?.buildMemoryPrompt(for: instruction) ?? ""
        let veraMemorySection = memoryLayer == .vera
            ? await VeraMemoryBridge.recall(for: instruction)
            : ""
        let memorySection = cortexMemorySection + veraMemorySection
        let isWorkspaceless = workspaceURL == nil

        // ── Self-evolution context ────────────────────────────────────────
        let selfEvoContext: String
        if selfFixMode {
            let nodesEmpty = await MainActor.run { SelfEvolutionEngine.shared.sourceNodes.isEmpty }
            if nodesEmpty {
                await onProgress(.systemLog(AppLanguage.shared.t("🔍 Auto-indexing IDE source...", "🔍 IDE ソースを自動インデックス中…")))
                await SelfEvolutionEngine.shared.indexSourceTree()
            }

            selfEvoContext = await MainActor.run {
                let nodes = SelfEvolutionEngine.shared.sourceNodes
                if nodes.isEmpty {
                    return """

## SELF-FIX MODE (Index not found)
The source could not be indexed. Please:
1. Open the VerantyxIDE folder as workspace (Cmd+Shift+O)
2. Click [Index Source] in the Self-Evolution panel (⟳ icon)
Then try again.
Do NOT run ls or shell commands.
"""
                }
                let indexSummary = nodes.prefix(60).map { n in
                    "  • \(n.relativePath) — \(n.summary)"
                }.joined(separator: "\n")
                return """

## SELF-FIX MODE ACTIVE ⚠️

You are in SELF-FIX mode. The user has explicitly requested that you modify
the Verantyx IDE's own source code to address their request.

The IDE source is indexed. Key files:
\(indexSummary)

Instructions:
1. Identify the relevant Swift file(s) from the index above.
2. Output the COMPLETE modified file content using EXACTLY this format:

[PATCH_FILE: Sources/Verantyx/Views/ExampleView.swift]
```swift
// complete new file content here
```

3. You may output multiple PATCH_FILE blocks if needed.
4. Do NOT run `ls`, `find`, or any shell commands — all files are listed above.
5. The IDE will detect PATCH_FILE blocks and show them in the Self-Evolution panel.
6. After outputting patches, briefly explain what you changed and why.

For non-code output (HTML, diagrams, etc.) use <artifact type="html"> tags.
"""
            }
        } else {
            selfEvoContext = ""
        }

        // ── Archived session memory (JCross) — built per-turn inside loop ──
        // NOTE: This is intentionally NOT built here at session start.
        // It is rebuilt every turn INSIDE the loop so that CONV_*.jcross files
        // written by compressConversation() are immediately visible on the next turn.
        // See archiveSection rebuild inside the while loop below.

        
        // ── Mode-specific loop rules (injected into system prompt) ────────
        let loopRules = """

## LOOP POLICY — Gatekeeper Mode (Deterministic Protocol)
- You are operating inside the Verantyx Enterprise Gatekeeper.
- You have NO turn limit. Keep working until [DONE].
- You MUST only use JCross v2.2 structural patching.
[CTRL:enforce_safety] [MEM:check_vault]
OP.AXIOM("user_reports_may_be_false")
SYS.ENFORCE("logical_verification_before_acceptance")
- CONFUSION DETECTOR PROTOCOL: ユーザーからのバグ報告を鵜呑みにせず、本当にそのバグが起き得るか自身のコードの論理パスを検証すること。If your code is logically correct and the reported bug is impossible, confidently state that the bug cannot occur. Do not hallucinate failures just to agree with the user.
"""

        // Use tier-appropriate system prompt (nano gets a simplified version)
        let contextSection: String
        if let file = contextFile {
            let limit = profile.tier == .nano ? 2000 : 6000
            let name  = contextFileName ?? "file"
            contextSection = "CURRENT FILE (\(name)):\n```\n\(file.prefix(limit))\n```"
        } else {
            contextSection = ""
        }
        // ── Capture live MCP tool snapshot + build profile system prompt ─────
        // MCPEngine is @MainActor — hop over to grab the snapshot safely.
        let profileSystemPrompt = await MainActor.run {
            let liveMCPTools = MCPEngine.shared.connectedTools
            return profile.systemPromptWith(mcpTools: liveMCPTools)
        }

        // ── Skill Library: 注入方式別 ─────────────────────────────────────────
        // large/giant : 毎回システムプロンプトに静的注入（全スキル情報を多いトークンで歪えない）
        // nano/small  : オンデマンド—詳細はループ内でユーザー質問をトリガーに検索しconversationに注入
        //              (節約したトークンを会話記憶に充当)
        let skillSection: String
        if profile.tier == .large || profile.tier == .giant {
            await SkillLibrary.shared.loadIndex()
            let skillCount = await SkillLibrary.shared.count
            if skillCount > 0 {
                let relevantSkills = await SkillLibrary.shared.search(query: instruction, topK: 3)
                skillSection = SkillInjector.buildSection(skills: relevantSkills)
                if !relevantSkills.isEmpty {
                    await onProgress(.aiMessage(
                        "🔧 [SkillLib] \(relevantSkills.count) relevant skill(s) injected: " +
                        relevantSkills.map { $0.name }.joined(separator: ", ")
                    ))
                }
            } else {
                skillSection = SkillInjector.buildSection(skills: [])
            }
        } else {
            // nano/small: システムプロンプトには注入しない。
            // ループ内でユーザーの質問に当たるスキルが見つかった場合のみ conversation に挿入する。
            // 起動時に index をロードだけしておく（検索はループ内）。
            await SkillLibrary.shared.loadIndex()
            skillSection = ""  // システムプロンプトには入れない
        }

        // ── SearchGate prompt (nano/small のみ追加) ───────────────────────
        let searchGatePrompt = vxLoopEnabled
            ? SearchGate.buildSearchGatePrompt(tier: profile.tier)
            : ""

        // ── Response Language Enforcement (JCross Kanji Topology) ───────────
        let currentFileURL = URL(fileURLWithPath: #file)
        let langFileName = AppLanguage.shared.isJapanese ? "LANG_JA.jcross" : "LANG_EN.jcross"
        let langFilePath = currentFileURL.deletingLastPathComponent().appendingPathComponent(langFileName).path
        
        let languageRule: String
        if let jcrossContent = try? String(contentsOfFile: langFilePath, encoding: .utf8) {
            languageRule = jcrossContent
        } else {
            // Fallback
            languageRule = AppLanguage.shared.isJapanese
                ? "[和:1.0][日:0.9] You MUST respond entirely in Japanese."
                : "[英:1.0][米:0.9] You MUST respond entirely in English."
        }

        let identitySection = SessionMemoryArchiver.shared.buildIdentityInjection(useNanoStore: profile.tier == .nano)

        let systemPrompt = """
        \(profileSystemPrompt)
        \(identitySection)
        \(loopRules)
        \(languageRule)
        \(memorySection)
        \(skillSection)
        \(selfEvoContext)
        \(searchGatePrompt)
        \(isWorkspaceless ? "\nNOTE: No workspace is open. If the task requires a project, create one with [WORKSPACE:] and [MKDIR:]." : "")
        \(contextSection)
        """

        conversation.append((role: "system", content: systemPrompt))


        // ── Self-awareness task (first session only) ──────────────────────
        // モデルが自分の能力を把握するための初回タスク
        if isFirstSession {
            let selfTask = profile.selfAwarenessTask
            conversation.append((role: "user", content: selfTask))
            let toolScope = profile.tier == .nano ? "simple file tools only" : "the full tool set"
            let responseStyle = profile.tier == .nano ? "very short" : "focused and structured"
            let ack = "I am \(activeModel), a \(profile.tier.displayName) model (\(Int(profile.parameterBillions))B params). " +
                      "I will use \(toolScope) and keep responses \(responseStyle)."
            conversation.append((role: "assistant", content: ack))
            await onProgress(.aiMessage("\u{1F9E0} [Self-Aware] \(ack)"))
        }

        // ── Previous conversation history ─────────────────────────────────
        // 動的に budget を計算して、古い履歴から切り捨てる（Nanoモデル等のコンテキスト溢れ防止）
        var historyToInject: [(role: String, content: String)] = []
        for msg in previousMessages {
            guard msg.role != .system else { continue }
            let r = msg.role == .user ? "user" : "assistant"
            historyToInject.append((role: r, content: msg.content))
        }

        // Budget = compressThreshold - systemPrompt.count - instruction.count - 2000 (margin for tool responses)
        let budget = profile.tier.compressThreshold - systemPrompt.count - instruction.count - 2000
        var accumulatedChars = 0
        var keepIndex = historyToInject.count

        // 最新のメッセージから逆順に文字数を足していき、budget内に収まるインデックスを探す
        for i in stride(from: historyToInject.count - 1, through: 0, by: -1) {
            accumulatedChars += historyToInject[i].content.count
            if accumulatedChars > budget { break }
            keepIndex = i
        }

        // budget内に収まる直近の履歴だけを注入する
        for i in keepIndex..<historyToInject.count {
            conversation.append(historyToInject[i])
        }

        let emphasizedInstruction = """
        \(AppLanguage.shared.t("▼ CURRENT INSTRUCTION (HIGHEST PRIORITY) ▼", "▼ 現在の指示（最優先事項） ▼"))
        \(instruction)
        
        CRITICAL RULE: The instruction above MUST take absolute precedence over any legacy memory or system rules. If past memory contradicts this current instruction, IGNORE the past memory and fulfill this instruction exactly as requested.
        """
        conversation.append((role: "user",   content: emphasizedInstruction))
        totalConversationChars = conversation.reduce(0) { $0 + $1.content.count }

        await onProgress(.start(instruction: instruction))

        // ── Pre-flight: 意図分類 → 事前マルチクエリ検索 → グラウンディング注入 ────
        //
        // 【設計原則】
        //   事後型 SearchGate: モデルが応答してから検索 → ハルシネーション混入リスク
        //   事前型 Pre-flight: モデルが答える前に事実を注入 → グラウンディング強制
        //
        // 処理フロー:
        //   1. IgnoranceRouter (2Bモデル) で無知の自覚・クエリ生成
        //   2. PreflightSearchEngine で最大3クエリ並列実行（DuckDuckGo Lite）
        //   3. PreflightResult.systemBlock を system prompt に注入
        //   4. freshnessCritical + large/giant は Hard Grounding user msg も追加
        //   5. モデルは注入された事実のみを使って回答
        //
        // 有効条件: 全tierで実行（freshnessCritical は large/giant でも必須）
        // ※ 旧設計: vxLoopEnabled (nano/small) のみ → 大モデルがハルシネーション
        // ── [PREFLIGHT] Ignorance Router (2B) ──────────────────────────
        // (Abolished in favor of Visual Cognitive Anchors / Modality Hacking)


        // ── Agent loop — no hard turn cap ─────────────────────────────────
        while true {
            turn += 1
            await onProgress(.thinking(turn: turn))

            // ── OOM guard & KV Cache flush ──────────────────────────────
            let isKVCacheFull = await MLXRunner.shared.shouldFlushKVCache()
            if totalConversationChars > compressThreshold || isKVCacheFull {
                conversation = await compressConversation(
                    conversation,
                    cortex: cortex,
                    instruction: instruction
                )
                totalConversationChars = conversation.reduce(0) { $0 + $1.content.count }
                
                await MLXRunner.shared.resetKVCounter()
                
                let reason = isKVCacheFull ? "KV Cache limit reached" : "Context size exceeded"
                let logMsgJa = "🧠 [Memory] 会話履歴を圧縮してコンテキストをオフロードしました (\(reason))"
                let logMsgEn = "🧠 [Memory] Compressed conversation history and offloaded context (\(reason))"
                await onProgress(.systemLog(AppLanguage.shared.t(logMsgEn, logMsgJa)))

                // ── 圧縮直後: CONV_*.jcross が front/ に書かれた ──
                // (Dual-Track Architecture: IDE自身はこれらを自然言語として再注入しない)
            }

            // ── 毎ターン: Zone Priority Injection は行わない (Dual-Track) ──
            // L1-L3の記憶はMCP用ダンプ領域としてのみ使用し、IDEのコンテキストには注入しない。
            // これによりIDEの負荷とトークン消費を劇的に削減。


            // ── VX-Loop: VXTimeline 注入 (nano/small、クロスセッション時のみ) ─────
            //
            // 【設計原則】
            //   同セッション内: conversation 配列が全履歴を保持 → 注入不要・むしろ有害
            //   (毎ターン recap を挿入すると nano の 2048 トークン制限で元の会話が押し出される)
            //
            //   注入すべき2ケース:
            //   1. turn==1 かつ near/ に既存 TURN ファイルあり = クロスセッション開始
            //      → 前のセッションの記憶を conversation の先頭近くに注入
            //   2. compressConversation() 実行後
            //      → 圧縮で失われたコンテキストを補完（上の OOM guard 内で処理済み）
            if vxLoopEnabled && turn == 1 {
                // クロスセッション: 前セッションの記憶がある場合のみ注入
                // nano は L1 サマリー（短いファクト）、larger は L3 逐語
                let useL1 = (profile.tier == .nano)
                let priorTurns = VXTimeline.shared.buildTimelineAsMessages(
                    sessionId: vxSessionId,
                    topK: VXTimeline.verbatimWindow,
                    useL1Only: useL1,
                    workspaceRoot: currentWorkspace
                )
                if !priorTurns.isEmpty {
                    // system prompt の直後（index=1）に挿入して優先度を確保
                    let recapText = "[前セッションの記録]\n" + priorTurns.joined(separator: "\n---\n") + "\n[/前セッションの記録]"
                    conversation.insert((role: "user",      content: recapText),                      at: 1)
                    conversation.insert((role: "assistant", content: "前セッションの記録を確認しました。"), at: 2)
                    await onProgress(.systemLog(AppLanguage.shared.t("🕐 [VX-Loop] Restored previous session memory (session: \(vxSessionId), \(priorTurns.count) turns)", "🕐 [VX-Loop] 前セッション記憶を復元 (session: \(vxSessionId), \(priorTurns.count)ターン)")))
                }
                // SearchGate 前回結果を system prompt に注入（毎ターン、既存タグを置換）
                // これにより SearchGate web 結果がツールループ中の turn 2+ にも届く
                if !vxLastSearchResult.isEmpty,
                   var sysMsg = conversation.first, sysMsg.role == "system" {
                    let marker    = "[VX SEARCH RESULT]"
                    let endMarker = "[/VX SEARCH RESULT]"
                    let block = "\(marker)\n\(vxLastSearchResult)\n\(endMarker)"
                    if let start = sysMsg.content.range(of: marker),
                       let end   = sysMsg.content.range(of: endMarker) {
                        // 既存ブロックを置換（同じ検索結果の重複追加を防止）
                        sysMsg.content = String(sysMsg.content[..<start.lowerBound])
                            + block
                            + String(sysMsg.content[end.upperBound...])
                    } else {
                        sysMsg.content += "\n" + block
                    }
                    conversation[0] = sysMsg
                }
            }

            // ── Semantic Memory Search (RAG) — 毎ターン最新クエリで再検索 ──
            // Zone Injection = 「最近の記憶」の静的注入
            // Semantic Search = 「このターンの質問」に関連する記憶を動的補完
            //
            // クエリ: turn 1 は instruction、以降は最新ユーザーメッセージ
            // [MEMORY SEARCH] ブロックは毎ターン置換（スキルの質問が変わっても追従）
            let searchQuery: String
            if let lastUser = conversation.last(where: { $0.role == "user" }) {
                searchQuery = String(lastUser.content.prefix(200))
            } else {
                searchQuery = instruction
            }
            let searchBudget: Int
            switch profile.tier {
            case .nano:          searchBudget = 200
            case .small:         searchBudget = 400
            case .mid:           searchBudget = 600
            case .large, .giant: searchBudget = 800
            }
            let searchLayer: JCrossLayer = profile.tier == .nano ? .l1 : memoryLayer
            let searchResult: String
            if searchLayer == .vera {
                searchResult = await VeraMemoryBridge.recall(for: searchQuery)
            } else {
                searchResult = SessionMemoryArchiver.shared.semanticSearch(
                    query: searchQuery,
                    topK: profile.tier == .nano ? 2 : 3,
                    layer: searchLayer,
                    budget: searchBudget
                )
            }
            if var sysMsg = conversation.first, sysMsg.role == "system" {
                let marker = "[MEMORY SEARCH"
                let endMarker = "[/MEMORY SEARCH]"
                if let start = sysMsg.content.range(of: marker),
                   let end   = sysMsg.content.range(of: endMarker) {
                    // 既存ブロックを置換
                    let after = sysMsg.content[end.upperBound...]
                    sysMsg.content = String(sysMsg.content[..<start.lowerBound])
                        + (searchResult.isEmpty ? "" : searchResult)
                        + after
                } else if !searchResult.isEmpty {
                    sysMsg.content += "\n" + searchResult
                }
                conversation[0] = sysMsg
                if !searchResult.isEmpty {
                    let hitLine = searchResult.components(separatedBy: "\n")
                        .first(where: { $0.contains("hit") }) ?? ""
                    await onProgress(.systemLog("<think>\n🔍 [MemSearch] \(hitLine)\n</think>"))
                }
            }

            // ── nano/small: オンデマンドスキル注入 ───────────────────────────────
            // スキル情報はシステムプロンプトには入れず、ユーザーの質問と意味的に近い
            // スキルが見つかった場合のみ conversation に直接挿入する。
            // 大モデルの静的注入と同等の情報をトークン節約しながら提供する。
            if vxLoopEnabled {
                let skillCount = await SkillLibrary.shared.count
                if skillCount > 0 {
                    let relevantSkills = await SkillLibrary.shared.search(query: searchQuery, topK: 2)
                    // score > 0.6 のスキルのみ注入（弱い関連は無視してノイズ減）
                    let strongSkills = relevantSkills  // SkillLibrary が既にスコアでソート済み
                    if !strongSkills.isEmpty {
                        let skillText = SkillInjector.buildSection(skills: strongSkills)
                        if !skillText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            let lastIdx = conversation.count - 1
                            if lastIdx > 0 {
                                conversation.insert(
                                    (role: "user", content: "[スキル情報]\n\(skillText)\n[/スキル情報]"),
                                    at: lastIdx
                                )
                                conversation.insert(
                                    (role: "assistant", content: "スキル情報を確認しました。"),
                                    at: lastIdx + 1
                                )
                                await onProgress(.aiMessage(
                                    "🔧 [SkillLib] \(strongSkills.count) skill(s) on-demand: " +
                                    strongSkills.map { $0.name }.joined(separator: ", ")
                                ))
                            }
                        }
                    }
                }
            }

            // ── Call LLM (streaming) with Zero-Translation Steering ──────────────
            let modelTaskResult = try? await withThrowingTaskGroup(of: TaskRaceResult.self) { group in
                // Task 1: The actual LLM generation
                group.addTask {
                    let response = await self.callModel(
                        conversation: conversation,
                        images: images,
                        modelStatus: modelStatus,
                        activeModel: activeModel,
                        profile: profile,
                        operationMode: operationMode,
                        onProgress: onProgress
                    )
                    return .response(response)
                }
                
                // Task 2: The steering listener (Hardware Interrupt)
                group.addTask {
                    let steeringSub = await MainActor.run { () -> PassthroughSubject<String, Never>? in
                        return AppState.shared?.steeringSubject
                    }
                    guard let subject = steeringSub else {
                        try await Task.sleep(nanoseconds: UInt64.max)
                        return .steering("") // unreachable
                    }
                    for await cmd in subject.values {
                        // Received steering command!
                        return .steering(cmd)
                    }
                    return .steering("") // unreachable
                }
                
                guard let result = try await group.next() else { return TaskRaceResult.response(nil) }
                group.cancelAll()
                return result
            }
            
            if case .steering(let steeringCommand) = modelTaskResult {
                // We got a steering interrupt!
                await onProgress(.systemLog(AppLanguage.shared.t(
                    "⚠️ [STEERING] Inference interrupted by user command: \(steeringCommand)",
                    "⚠️ [STEERING] ユーザーコマンドによる割り込み（推論強制停止）: \(steeringCommand)"
                )))
                
                let cmdTrimmed = steeringCommand.trimmingCharacters(in: .whitespacesAndNewlines)
                if cmdTrimmed == "^C" || cmdTrimmed.isEmpty {
                    // It's a pure interrupt (Stop Generation)
                    // Break the loop so the user can take control again
                    break
                } else {
                    // Inject the steering command as a user priority message
                    conversation.append((role: "user", content: "[HUMAN OVERRIDE] \(steeringCommand)\nAbandon the current thought process and follow this command immediately."))
                    continue // Immediately restart the turn with the new context
                }
            }
            
            let rawResponseOpt: String? = {
                if case .response(let res) = modelTaskResult { return res }
                return nil
            }()
            
            guard var rawResponse = rawResponseOpt else {
                await onProgress(.error("Model returned nil response (or was interrupted)"))
                return
            }

            // ── Talkie-1930 (Blind Commander) Intermediary Translation ──────
            if await MainActor.run(body: { AppState.shared?.isTalkieMode == true }) {
                rawResponse = TalkieIntermediary.parseAndTranslate(response: rawResponse)
            }

            // ── JCross IR 検証パイプライン (nano/small のみ) ────────────────
            // 「生成と検証の分離」アーキテクチャ:
            //   1. モデルが [想:]→[確:]→[出:] の IR 形式で応答した場合
            //   2. [確:X] の主張を conversation 履歴で決定論的に照合
            //   3. verified   → [出:X] を最終回答として採用 (ユーザーには IR を隠す)
            //   4. unverified → メモリ補完 → 再生成 (ConfusionDetector と同フロー)
            //   5. 通常の自然言語応答 → このブロックはスキップ
            var irWasVerified = false
            if vxLoopEnabled && JCrossIRParser.containsIR(rawResponse) {
                let irNodes = JCrossIRParser.parse(rawResponse)
                let verifyClaims = JCrossIRParser.extractVerifyClaims(from: irNodes)

                await onProgress(.systemLog(
                    "🔬 [IR] ノード: \(irNodes.map(\.description).joined(separator: "→"))"
                ))

                if !verifyClaims.isEmpty {
                    // 決定論的照合
                    let verifyResults = await IRVerificationEngine.shared.verify(
                        claims: verifyClaims,
                        against: conversation,
                        semanticSearcher: { query in
                            SessionMemoryArchiver.shared.semanticSearch(
                                query: query,
                                topK: 3,
                                layer: memoryLayer,
                                budget: 300
                            )
                        }
                    )

                    let summary = await IRVerificationEngine.shared.debugSummary(verifyResults)
                    await onProgress(.systemLog(AppLanguage.shared.t("🔬 [IR Verify] \(summary)", "🔬 [IR検証] \(summary)")))

                    if await IRVerificationEngine.shared.allVerified(verifyResults) {
                        // ✅ 全照合成功 → [出:X] を最終回答として採用、IR ブロックを除去
                        if let finalAnswer = JCrossIRParser.extractFinalOutput(from: irNodes) {
                            rawResponse = finalAnswer
                        } else {
                            rawResponse = JCrossIRParser.stripIR(from: rawResponse)
                        }
                        irWasVerified = true
                    } else {
                        // ❌ 照合失敗 → 記憶補完して再生成
                        let failedClaims = await IRVerificationEngine.shared.failedClaims(verifyResults)
                        let recoveryQuery = failedClaims.joined(separator: " ")
                        await onProgress(.systemLog(
                            AppLanguage.shared.t("🔄 [IR Restore] Verification failed: \(failedClaims.joined(separator: ", ")) → Memory supplementation", "🔄 [IR復元] 照合失敗: \(failedClaims.joined(separator: ", ")) → 記憶補完")
                        ))

                        let recoveryMemory = SessionMemoryArchiver.shared.semanticSearch(
                            query: recoveryQuery,
                            topK: 3,
                            layer: memoryLayer,
                            budget: 400
                        )
                        if !recoveryMemory.isEmpty {
                            let lastIdx = conversation.count - 1
                            if lastIdx > 0 {
                                conversation.insert(
                                    (role: "user",      content: "[記憶補完]\n\(recoveryMemory)\n[/記憶補完]"),
                                    at: lastIdx
                                )
                                conversation.insert(
                                    (role: "assistant", content: "記憶補完を確認しました。"),
                                    at: lastIdx + 1
                                )
                            }
                        }
                        if let retryResponse = await callModel(
                            conversation: conversation,
                            images: images,
                            modelStatus: modelStatus,
                            activeModel: activeModel,
                            profile: profile,
                            operationMode: operationMode,
                            onProgress: onProgress
                        ) {
                            rawResponse = JCrossIRParser.stripIR(from: retryResponse)
                        }
                        irWasVerified = true  // ConfusionDetector の二重発火を防ぐ
                    }
                } else {
                    // [確:] なし → [出:] だけ抽出してIRを除去
                    if let finalAnswer = JCrossIRParser.extractFinalOutput(from: irNodes) {
                        rawResponse = finalAnswer
                    } else {
                        rawResponse = JCrossIRParser.stripIR(from: rawResponse)
                    }
                    irWasVerified = true
                }
            }

            // ── Confusion Detection + Auto Memory Injection ───────────────
            // nano/small モデルが「わかりません」等を出力した場合、記憶を補完して再実行する。
            // ユーザーには最終回答のみ表示されるブラックボックス仕様。
            // didConfusionRetry フラグで無限ループを防止（1ターン最大1回のみ）。
            // irWasVerified = true の場合は IR レイヤーが処理済みなのでスキップ。
            if vxLoopEnabled && !didConfusionRetry && !irWasVerified && ConfusionDetector.isConfused(rawResponse) {
                didConfusionRetry = true
                let matched = ConfusionDetector.matchedPatterns(in: rawResponse)
                await onProgress(.systemLog(AppLanguage.shared.t("🔄 [Autonomous] Detected '\(matched.first ?? "context")'. Instructing information search...", "🔄 [自律思考] 「\(matched.first ?? "context")」を検知。情報探索を指示します...")))
                
                var pushConversation = conversation
                pushConversation.append((role: "assistant", content: rawResponse))
                let pushPrompt = """
                あなたは「情報がない」「わからない」と回答しましたが、あなたは自律エージェントです。諦めないでください。
                わからない場合は [SEARCH_GATE: {"type": "web", "query": "検索ワード"}] を使ってWebを検索するか、MCPツールやその他の利用可能なツールを使用して外部から情報を取得し、ユーザーに回答を提供してください。
                今すぐツールを使用して情報を探索してください。
                """
                pushConversation.append((role: "user", content: pushPrompt))
                
                // 再実行: ツールを使用するよう促す
                if let retryResponse = await callModel(
                    conversation: pushConversation,
                    images: images,
                    modelStatus: modelStatus,
                    activeModel: activeModel,
                    profile: profile,
                    operationMode: operationMode,
                    onProgress: onProgress
                ) {
                    rawResponse = retryResponse
                    conversation = pushConversation
                }
            }

            // ── AI Priority circuit breaker ───────────────────────────────
            if true {
                let hash = rawResponse.hashValue
                recentResponseHashes.append(hash)
                if recentResponseHashes.count > circuitBreakerWindow {
                    recentResponseHashes.removeFirst()
                }
                if recentResponseHashes.count == circuitBreakerWindow
                    && Set(recentResponseHashes).count == 1 {
                    let msg = AppLanguage.shared.t("⚡ [Circuit Breaker] AI repeated the same output \(circuitBreakerWindow) times. Detected infinite loop and stopping.", "⚡ [Circuit Breaker] AIが同じ出力を\(circuitBreakerWindow)回繰り返しました。無限ループを検知して停止します。")
                    await onProgress(.error(msg))
                    await cortex?.remember(
                        key: "circuit_break_\(turn)",
                        value: "Loop at turn \(turn): \(rawResponse.prefix(100))",
                        importance: 0.9,
                        zone: .near
                    )
                    return
                }
            }

            // ── Store in cortex ───────────────────────────────────────────
            await cortex?.extractAndStore(from: rawResponse, userInstruction: instruction)

            // ── Vera-α: preview-before-save popup for this turn ──────────
            if memoryLayer == .vera {
                await VeraMemoryBridge.requestSaveApproval(
                    userPrompt: instruction, aiResponse: rawResponse
                )
            }

            // ── VX-Loop: SearchGate パース + 記憶保存 ─────────────────────
            // 1. SearchGate トークンを応答末尾から解析
            // 2. クリーンテキスト（GateトークンなしのUI表示用）を取得
            // 3. needs=true なら記憶検索を実行して near/ に保存
            // 4. このターン（Q+A）を near/ に TURN_*.jcross として記録
            let vxCleanResponse: String
            if vxLoopEnabled {
                let gateDecision = await SearchGate.shared.parse(from: rawResponse)
                vxCleanResponse  = await SearchGate.shared.stripGateToken(from: rawResponse)

                if gateDecision.needsSearch {
                    let searchLabel = gateDecision.searchType == .web
                        ? "<think>\n🌐 [VX-Loop] " + AppLanguage.shared.t("Web Search", "Web検索") + " → \"\(String(gateDecision.query.prefix(40)))\"\n</think>"
                        : "<think>\n🔎 [VX-Loop] SearchGate: " + AppLanguage.shared.t("Memory Search", "記憶検索") + " → \"\(String(gateDecision.query.prefix(40)))\"\n</think>"
                    await onProgress(.systemLog(searchLabel))
                    var entropyPoints: [[Double]]? = nil
                    if gateDecision.searchType == .web {
                        var cooldownLeft = await MainActor.run { () -> TimeInterval in
                            guard let cooldown = AppState.shared?.searchCooldownUntil else { return 0 }
                            return max(0, cooldown.timeIntervalSinceNow)
                        }
                        while cooldownLeft > 0 {
                            try? await Task.sleep(nanoseconds: 5_000_000_000)
                            cooldownLeft = await MainActor.run {
                                guard let cooldown = AppState.shared?.searchCooldownUntil else { return 0 }
                                return max(0, cooldown.timeIntervalSinceNow)
                            }
                        }
                        
                        let isEntropyStale = await MainActor.run { () -> Bool in
                            guard let ts = AppState.shared?.lastEntropyTimestamp else { return true }
                            let stale = Date().timeIntervalSince(ts) > 300 // 5 minutes TTL
                            if stale {
                                print("Telemetry: Biometric entropy stale in SearchGate. Re-puzzling triggered.")
                            }
                            return stale
                        }
                        
                        if isEntropyStale {
                            await MainActor.run { AppState.shared?.requiresHumanPuzzle = true }
                            
                            var waitingForPuzzle = await MainActor.run { AppState.shared?.requiresHumanPuzzle == true }
                            while waitingForPuzzle {
                                try? await Task.sleep(nanoseconds: 200_000_000)
                                waitingForPuzzle = await MainActor.run { AppState.shared?.requiresHumanPuzzle == true }
                            }
                        }
                        
                        let cgPoints = await MainActor.run { AppState.shared?.lastEntropy }
                        await MainActor.run { AppState.shared?.lastEntropy = nil } // Consume and clear
                        
                        if let points = cgPoints {
                            let mapped = points.map { [Double($0.x), Double($0.y)] }
                            if mapped.count > 100 {
                                let step = max(1, mapped.count / 100)
                                entropyPoints = stride(from: 0, to: mapped.count, by: step).prefix(100).map { mapped[$0] }
                            } else {
                                entropyPoints = mapped
                            }
                        }
                    }
                    
                    let sgResult = await SearchGate.shared.executeSearch(
                        decision: gateDecision,
                        sessionId: vxSessionId,
                        turnNumber: turn,
                        tier: profile.tier,
                        preferredSource: .safari,
                        entropy: entropyPoints
                    )
                    vxLastSearchResult = sgResult
                } else {
                    vxLastSearchResult = ""
                }


                // このターンを VXTimeline に記録
                // turn は AgentLoop 内のループカウンタ（毎メッセージリセット）のため
                // セッション横断の連番には nextTurnNumber() を使用する
                let userText = conversation.last(where: { $0.role == "user" })?.content ?? instruction
                let globalTurnNumber = VXTimeline.shared.nextTurnNumber(for: vxSessionId)
                VXTimeline.shared.recordTurn(
                    sessionId: vxSessionId,
                    turnNumber: globalTurnNumber,
                    userInput: userText,
                    assistantOutput: vxCleanResponse,
                    searchResults: vxLastSearchResult,
                    workspaceRoot: currentWorkspace
                )
            } else {
                vxCleanResponse = rawResponse
            }

            // ── Parse tool calls ──────────────────────────────────────────
            // vxCleanResponse = SearchGate トークンをストリップ済み
            // rawResponse     = ツールパーサー内部でも SearchGate を除去してから渡す
            let (tools, cleanText) = AgentToolParser.parse(from: vxCleanResponse)

            // ── aiMessage emission strategy ──────────────────────────────
            // Ollama and MLX both use streaming (streamToken callbacks).
            // The UI bubble is already fully populated by the time callModel
            // returns.
            //
            // Rule: only emit aiMessage when the model does NOT stream tokens.
            //       Streaming models (Ollama, MLX) skip this step — the
            //       streaming bubble is already correct and complete.
            //       Non-streaming models (fallback .ready) must emit it.
            //
            // IMPORTANT: For VX-Loop (nano/small), the raw streaming bubble may
            // contain [SEARCH_GATE: ...] tokens. We patch the bubble content
            // with vxCleanResponse after streaming completes.
            let isStreamingModel: Bool
            switch modelStatus {
            case .ollamaReady, .mlxReady: isStreamingModel = true
            default:                      isStreamingModel = false
            }

            if isStreamingModel && vxLoopEnabled {
                // Streaming + VX-Loop: patch the bubble to strip SearchGate tokens.
                // cleanText already has gate tokens removed via vxCleanResponse.
                // We emit a "replace" aiMessage only when the gate token was present.
                if rawResponse != vxCleanResponse {
                    await onProgress(.aiMessage(cleanText.isEmpty ? vxCleanResponse : cleanText))
                }
            } else if !cleanText.isEmpty && !isStreamingModel {
                // Non-streaming path: emit the full response as a chat bubble
                await onProgress(.aiMessage(cleanText))
            }
            // For streaming models: aiMessage is intentionally skipped here.
            // The streaming bubble (populated by streamToken) remains as-is.
            // Tool-call annotations (if any) are shown via toolCall/toolResult.

            // ── Auto-register Artifact from AI response ────────────────────
            // Detects <artifact> tags or large code blocks and publishes them
            // to the ArtifactPanelView immediately after the response completes.
            if let artifact = ArtifactParser.extract(from: rawResponse) {
                await MainActor.run {
                    AppState.shared?.ingestArtifact(artifact)
                }
            }

            // If no tools → conversational answer → done
            if tools.isEmpty {
                // VX-Loop: If SearchGate executed successfully, inject the result and continue the loop
                if vxLoopEnabled, !vxLastSearchResult.isEmpty {
                    conversation.append((role: "assistant", content: vxCleanResponse))
                    conversation.append((role: "user", content: "検索結果が取得されました。この情報を基に、先ほどの回答を修正・補足して最終的な答えを出力してください：\n\n\(vxLastSearchResult)"))
                    continue
                }
                
                consecutiveToolOnlyTurns = 0
                // Pass cleanText for the .done handler's duplicate-guard check
                await onProgress(.done(message: cleanText, workspace: currentWorkspace))
                return
            }

            // ── Execute tools ─────────────────────────────────────────────
            var toolResults: [String] = []
            var isDone = false

            for tool in tools {
                let call = AgentToolCall(tool: tool)
                await onProgress(.toolCall(call))

                var result: String

                // ── IDE Fix sandbox ────────────────────────────────────
                // Allowed: readFile, gitCommit, applyPatch, buildIDE, restartIDE,
                //          jcross*, askHuman, done.
                // Blocked: listDir, runCommand, browse, search, setWorkspace…
                // Strategy: on FIRST block in a turn → break loop, inject
                //   correction DIRECTLY into conversation so the model sees it.
                //   consecutiveBlockedCalls counts turns (not tools within a turn).
                //   After 3 blocked turns → hard-stop.
                if selfFixMode && isForbiddenInSelfFixMode(tool) {
                    consecutiveBlockedCalls += 1

                    let blockedUI = AgentToolCall(tool: tool, result: "🚫 BLOCKED (IDE Fix Sandbox)", succeeded: false)
                    await onProgress(.toolResult(blockedUI))

                    if consecutiveBlockedCalls >= 3 {
                        // Hard-stop: model is definitively stuck
                        let msg = AppLanguage.shared.t("⚠️ **IDE Fix Mode: Stopped due to loop detection**\n\nSafely stopped after calling forbidden tools \(consecutiveBlockedCalls) times in a row.\nPlease read the file with [READ: Sources/…/File.swift] and apply patches with [APPLY_PATCH].", "⚠️ **IDE Fix モード: ループを検知して停止しました**\n\n禁止ツールを\(consecutiveBlockedCalls)回連続で呼び出したため安全に停止しました。\n[READ: Sources/…/File.swift] でファイルを読み、[APPLY_PATCH] でパッチを当ててください。"
                        )
                        await onProgress(.aiMessage(msg))
                        await onProgress(.done(message: AppLanguage.shared.t("IDE Fix sandbox loop prevention", "IDE Fix sandbox ループ防止"), workspace: currentWorkspace))
                        return
                    }
                    // Inject correction DIRECTLY into conversation so the model
                    // sees it as context in the very next turn — not just a tool result.
                    let correction = AppLanguage.shared.t("""
                        [IDE Fix Sandbox] Called a forbidden tool (total \(consecutiveBlockedCalls) times): \(call.displayLabel)

                        Allowed tools in IDE Fix Mode:
                          [READ: Sources/.../File.swift]       <- Read file content
                          [GIT_COMMIT: msg]                    <- Backup before changes
                          [APPLY_PATCH: Sources/.../File.swift] <- Apply fixes
                          [BUILD_IDE]                          <- Verify build
                          [DONE: msg]                          <- Complete

                        [LIST_DIR], [RUN], [SEARCH], [BROWSE], [WORKSPACE] are NOT allowed.
                        Please start with [READ: Target File Path] right now.
                        """, """
                        [IDE Fix Sandbox] 禁止ツールを呼び出しました (通算 \(consecutiveBlockedCalls)回): \(call.displayLabel)

                        IDE Fix モードで許可されているツール:
                          [READ: Sources/.../File.swift]       ← ファイル内容を読む
                          [GIT_COMMIT: msg]                    ← 変更前にバックアップ
                          [APPLY_PATCH: Sources/.../File.swift] ← 修正を適用
                          [BUILD_IDE]                          ← ビルド検証
                          [DONE: msg]                          ← 完了

                        [LIST_DIR], [RUN], [SEARCH], [BROWSE], [WORKSPACE] は使用不可です。
                        今すぐ [READ: 対象ファイルパス] で始めてください。
                        """
                    )

                    conversation.append((role: "assistant", content: rawResponse))
                    conversation.append((role: "user", content: correction))
                    toolResults.append("\(call.displayLabel) → BLOCKED #\(consecutiveBlockedCalls)")

                    // Break the for-tool loop: skip remaining tools in this batch.
                    // The while loop continues, calling the model with the correction injected.
                    isDone = false
                    break
                } else {
                    consecutiveBlockedCalls = 0  // Any allowed tool resets the counter
                }

                // ── Twin-Agent Audit (Pre-execution Gate) ───────────────────
                // Ignore safe tools like done, askHuman, jcross.
                let rawToolStr = call.displayLabel
                let auditResult = await TwinCriticEngine.shared.audit(tool: rawToolStr, conversation: conversation)
                if !auditResult.isApproved {
                    let rejectedUI = AgentToolCall(tool: tool, result: "🚫 REJECTED BY CRITIC:\n\(auditResult.feedback)", succeeded: false)
                    await onProgress(.toolResult(rejectedUI))
                    
                    let correction = """
                    [TWIN B - SYSTEM VERIFIER OVERRIDE]
                    Your proposed action (\(rawToolStr)) was REJECTED by the system verifier.
                    Reason: \(auditResult.feedback)
                    
                    You MUST rethink your approach and generate a COMPLETELY NEW strategy.
                    Do not propose the same tool call again.
                    """
                    
                    // Context Rollback & Correction Injection
                    // We purposefully DO NOT append rawResponse to the conversation here.
                    // This erases Twin A's flawed reasoning from the active memory.
                    conversation.append((role: "user", content: correction))
                    
                    // Break the tool loop to force a fresh turn without executing this tool
                    isDone = false
                    break
                }
                // ─────────────────────────────────────────────────────────────────

                if case .setWorkspace(let path) = tool {
                    let wsURL = URL(fileURLWithPath: path)
                    currentWorkspace = wsURL
                    
                    // Sync Gatekeeper vault with the new workspace
                    await MainActor.run {
                        GatekeeperModeState.shared.configure(workspaceURL: wsURL)
                    }
                    
                    await onProgress(.workspaceChanged(wsURL))
                    result = await executor.execute(tool, workspaceURL: currentWorkspace)
                } else if case .done(let msg) = tool {
                    // ── [NEW] B-to-A Auditor Handover ──
                    if !hasPassedAuditorReview {
                        await onProgress(.systemLog(AppLanguage.shared.t(
                            "🛑 [Auditor Review] Intercepted [DONE]. Injecting B-to-A validation anchor.",
                            "🛑 [監査役レビュー] [DONE] をインターセプト。B→Aの品質検証アンカーを注入します。"
                        )))
                        
                        let auditorPrompt = """
                        [AUDITOR REVIEW]
                        この実装は実際のところおもちゃレベルの実装ですか？冷静に分析して、必要なら修正を行い、すべてが本番レベルの品質になったと確信した場合にのみ再度 [DONE] を呼び出してください。
                        """
                        
                        conversation.append((role: "user", content: auditorPrompt))
                        totalConversationChars += auditorPrompt.count
                        
                        // 次ターンの CognitiveAnchorEngine に画像アンカーを渡すようマーク（現状は特殊なフラグ処理として直接注入）
                        let auditorAnchorImage = await CognitiveAnchorEngine.shared.getAnchor(for: .auditorReview)
                        if !auditorAnchorImage.isEmpty {
                            // 将来のLLM呼び出し（callModel内部）で使われるように AppState の persistentTaskAnchor を一時的に利用するか、
                            // もしくは conversation 内に指示を含める。ここでは直接会話の文脈にアンカーを渡した体裁にするため、
                            // CognitiveAnchorEngine の lastVisionScreenshot を利用して強制的に Vision システムに注入する。
                            await CognitiveAnchorEngine.shared.setVisionScreenshot(auditorAnchorImage)
                        }
                        
                        hasPassedAuditorReview = true
                        isDone = false
                        break // Break the tool loop to force a fresh turn with the auditor review
                    }
                    
                    result = await executor.execute(tool, workspaceURL: currentWorkspace)
                    await onProgress(.done(message: msg, workspace: currentWorkspace))
                    isDone = true

                    // ── [NEW] SEPARATION OF MEMORY ──
                    // Extract generalized wisdom to near/mid, and move the task history to far/
                    let currentConv = conversation
                    Task.detached {
                        let shortId = vxSessionId
                        // 1. L2 Fact Extraction for WISDOM (User Preferences/Identities)
                        // We do a fast heuristic extraction from the user turns.
                        let userTurns = currentConv.filter { $0.role == "user" }.map { $0.content }.joined(separator: " ")
                        var l2Lines = [
                            "OP.FACT(\"origin_task_id\", \"\(shortId)\")"
                        ]
                        if !userTurns.isEmpty {
                            l2Lines.append("OP.FACT(\"user_preference_or_rule\", \"\(String(userTurns.prefix(300)).replacingOccurrences(of: "\n", with: " "))\")")
                        }
                        
                        let ts = Int(Date().timeIntervalSince1970)
                        SessionMemoryArchiver.shared.archiveWisdomChunk(
                            chunkId: "WISDOM_\(shortId)_\(ts)",
                            taskTitle: "Wisdom extracted from \(shortId)",
                            l1: "[知見抽出] ユーザーの好み・指示パターン",
                            l2: l2Lines.joined(separator: "\n"),
                            l3: "" // Not storing full verbatim for wisdom to save budget
                        )
                        
                        // 2. Move the original PROG/CONV chunks to far/
                        SessionMemoryArchiver.shared.moveToFarZone(shortId: shortId)

                        // 3. Track 2: Export Fine-tuning Data (Hidden Tokens/Thought Capture)
                        // This builds the verantyx_dataset.jsonl file for future fine-tuning.
                        var datasetMessages: [[String: String]] = []
                        for msg in currentConv {
                            datasetMessages.append(["role": msg.role, "content": msg.content])
                        }
                        if let jsonData = try? JSONSerialization.data(withJSONObject: ["messages": datasetMessages], options: []),
                           let jsonStr = String(data: jsonData, encoding: .utf8) {
                            
                            let cortexWs = UserDefaults.standard.string(forKey: "cortex_workspace_path") ?? UserDefaults.standard.string(forKey: "last_workspace_path") ?? "/tmp"
                            let baseDir = URL(fileURLWithPath: cortexWs).appendingPathComponent(".openclaw/memory/training_data")
                            try? FileManager.default.createDirectory(at: baseDir, withIntermediateDirectories: true)
                            let datasetURL = baseDir.appendingPathComponent("verantyx_dataset.jsonl")
                            
                            if FileManager.default.fileExists(atPath: datasetURL.path) {
                                if let handle = try? FileHandle(forUpdating: datasetURL) {
                                    handle.seekToEndOfFile()
                                    if let data = (jsonStr + "\n").data(using: .utf8) {
                                        handle.write(data)
                                    }
                                    handle.closeFile()
                                }
                            } else {
                                try? (jsonStr + "\n").write(to: datasetURL, atomically: true, encoding: .utf8)
                            }
                        }
                    }
                } else {
                    result = await executor.execute(tool, workspaceURL: currentWorkspace)
                }

                // ── ReAct 評価: 検索・ブラウズ系ツールの失敗検知 ────────────────
                // Action → Observation: isSearchFailure で失敗を検知
                // Evaluation → Re-thought: LLMに再クエリを生成させる
                // Retry: 新クエリで再実行 (最大10 = 3回まで)
                //
                // NOTE: `await` cannot appear on the right-hand side of `&&` in Swift,
                // so we hoist the async check into a local Bool first.
                let isReActFailure = !isDone && !reactContext.isExhausted
                    ? await ReActRetryEngine.shared.isSearchFailure(tool: tool, result: result)
                    : false
                if isReActFailure {

                    let reactEngine = ReActRetryEngine.shared
                    let currentConversation = conversation  // actor アイソレーションを跨いでも安全

                    let outcome = await reactEngine.run(
                        originalTool: tool,
                        firstResult: result,
                        userInstruction: instruction,
                        conversation: currentConversation,
                        callModel: { [modelStatus, activeModel, profile] (msgs: [(role: String, content: String)]) async -> String? in
                            // メインモデル呼び出しクロージャーを2次関数でラップ
                            let anchorBase64 = await CognitiveAnchorEngine.shared.getCustomAnchor(title: "ReAct SEARCH RETRY", text: "You must rethink your search query based on the failure.")
                            switch modelStatus {
                            case .ollamaReady(let model):
                                return await OllamaClient.shared.generateConversation(
                                    model: model,
                                    messages: msgs,
                                    imagesForLastUserMessage: [anchorBase64],
                                    maxTokens: profile.tier.maxTokens,
                                    temperature: profile.tier.temperature,
                                    onToken: { _ in }
                                )
                            case .anthropicReady(let model, _):
                                let sys  = msgs.first(where: { $0.role == "system" })?.content ?? ""
                                let chat = msgs.filter { $0.role != "system" }
                                return await AnthropicClient.shared.generate(
                                    model: model, systemPrompt: sys, messages: chat,
                                    imagesForLastUserMessage: [anchorBase64],
                                    maxTokens: profile.tier.maxTokens,
                                    temperature: profile.tier.temperature,
                                    enableThinking: false,
                                    onToken: { _ in }, onThinking: { _ in }
                                )
                            default: return nil
                            }
                        },
                        executeSearch: { newQuery async -> String in
                            // 新クエリで検索を再実行— SEARCH_MULTI を優先使用
                            var cooldownLeft = await MainActor.run { () -> TimeInterval in
                                guard let cooldown = AppState.shared?.searchCooldownUntil else { return 0 }
                                return max(0, cooldown.timeIntervalSinceNow)
                            }
                            while cooldownLeft > 0 {
                                try? await Task.sleep(nanoseconds: 5_000_000_000)
                                cooldownLeft = await MainActor.run {
                                    guard let cooldown = AppState.shared?.searchCooldownUntil else { return 0 }
                                    return max(0, cooldown.timeIntervalSinceNow)
                                }
                            }
                            
                            var entropyPoints: [[Double]]? = nil
                            let cgPoints = await MainActor.run { AppState.shared?.lastEntropy }
                            await MainActor.run { AppState.shared?.lastEntropy = nil } // Consume and clear
                            
                            if let points = cgPoints {
                                let mapped = points.map { [Double($0.x), Double($0.y)] }
                                if mapped.count > 100 {
                                    let step = max(1, mapped.count / 100)
                                    entropyPoints = stride(from: 0, to: mapped.count, by: step).prefix(100).map { mapped[$0] }
                                } else {
                                    entropyPoints = mapped
                                }
                            }


                            let searchResult = await WebSearchEngine.shared.search(
                                query: newQuery,
                                engine: .google,
                                entropy: entropyPoints
                            )
                            if searchResult.isFailure {
                                return AppLanguage.shared.t("❌ Retry Search Failed: \(newQuery) [Reason: \(searchResult.failureReason)]", "❌ 再検索失敗: \(newQuery) [理由: \(searchResult.failureReason)]")
                            }
                            return "[SEARCH RESULTS for: \(newQuery)]\n" +
                                   "Source: \(searchResult.url)\n" +
                                   searchResult.contextSnippet +
                                   "\n[END SEARCH RESULTS]"
                        },
                        onProgress: { msg async in
                            await onProgress(.aiMessage(msg))
                        }
                    )

                    switch outcome {
                    case .success(let retryResult):
                        // 成功: 元の result をリトライ結果で上書き
                        result = retryResult
                        reactContext.retriesThisTurn += 1
                        await onProgress(.systemLog(AppLanguage.shared.t("✅ [ReAct] Retry Search Succeeded (Attempt \(reactContext.retriesThisTurn))", "✅ [ReAct] 再検索成功 (試行\(reactContext.retriesThisTurn))")))

                    case .retry(let newQuery, let reason):
                        // 通常は発生しない（run()内部でループしているため）
                        result += "\n\n" + AppLanguage.shared.t("⚠️ [ReAct] Retrying: \(reason) → New Query: \(newQuery)", "⚠️ [ReAct] 再試行中: \(reason) → 新クエリ: \(newQuery)")

                    case .exhausted(let report):
                        // 上限超過: フェイルセーフ報告を result に挿入
                        result = report
                        reactContext.retriesThisTurn = ReActRetryEngine.shared.maxRetries
                        await onProgress(.systemLog(AppLanguage.shared.t("🔍 [ReAct] Max retries (\(ReActRetryEngine.shared.maxRetries)) exceeded. Sending fail-safe report.", "🔍 [ReAct] 最大試行回数(\(ReActRetryEngine.shared.maxRetries))を超過。フェイルセーフ報告を送信します。")))
                    }
                }

                let completedCall = AgentToolCall(tool: tool, result: result, succeeded: !result.hasPrefix("✗"))
                await onProgress(.toolResult(completedCall))
                toolResults.append("\(call.displayLabel) → \(result)")
            }

            if isDone { return }

            // ReAct コンテキストを次ターンに向けてリセット（ターンごとにリトライカウントは初期化）
            reactContext.reset()

            // ── Yield check (Human Mode) ──────────────────────────────────
            consecutiveToolOnlyTurns += 1
            // ユーザー要望により、ターン5で停止せず無限に動き続けるように Yield を無効化
            let disableYield = true
            if !disableYield && consecutiveToolOnlyTurns >= yieldAfterToolTurns {
                consecutiveToolOnlyTurns = 0
                let yieldMsg = AppLanguage.shared.t("""
                    ⏸ [Yield — Turn \(turn)] Called tools \(yieldAfterToolTurns) times consecutively, \
                    but the task is not yet complete. Here is the current status:

                    \(toolResults.suffix(3).joined(separator: "\n"))

                    Please review the next steps. Should I continue, or would you like to specify a different approach?
                    """, """
                    ⏸ [Yield — ターン\(turn)] \(yieldAfterToolTurns)回連続でツールを呼び出しましたが、\
                    まだ完了していません。現状を報告します：

                    \(toolResults.suffix(3).joined(separator: "\n"))

                    次のステップについて確認してください。続行しますか？または別のアプローチを指定してください。
                    """
                )
                await onProgress(.systemLog(yieldMsg))
                // Pause — wait for user's next message via the normal chat flow
                return
            }

            // ── Feed results back → next turn ────────────────────────────
            let toolResultSummary = "TOOL RESULTS:\n" + toolResults.map { "  \($0)" }.joined(separator: "\n")
            conversation.append((role: "assistant", content: rawResponse))
            conversation.append((role: "user",      content: toolResultSummary + "\n\nContinue if there's more to do, or [DONE] if complete."))
            totalConversationChars += rawResponse.count + toolResultSummary.count
        }
    }

    // MARK: - IDE Fix sandbox helpers

    /// Returns true for tools that are BLOCKED when selfFixMode is active.
    /// Allow-list design: only the tools needed for a patch workflow are permitted.
    /// - READ is required to understand current file state before patching.
    /// - GIT_COMMIT creates a safety checkpoint before applying changes.
    /// - Everything else (listDir, runCommand, browse, search…) is blocked.
    private func isForbiddenInSelfFixMode(_ tool: AgentTool) -> Bool {
        switch tool {
        // Self-Fix pipeline — always allowed
        case .applyPatch, .buildIDE, .restartIDE:           return false
        // File reading: agent must read before it can write a correct patch
        case .readFile:                                      return false
        // Git commit: safety backup before destructive patch
        case .gitCommit:                                     return false
        // Memory / human-loop / completion
        case .jcrossQuery, .jcrossStore, .askHuman, .done:  return false
        // Skill library: safe — only writes to ~/.openclaw/skills/
        case .forgeSkill, .useSkill:                        return false
        // Everything else: blocked
        default: return true
        }
    }

    // MARK: - Context compression (OOM guard)

    /// Compress old conversation turns into JCross L1-L3 + CortexEngine, then prune them.
    /// Keeps the last 4 turns intact (most recent context).
    ///
    /// Compressed turns are NOT thrown away — they are archived as tri-layer JCross nodes
    /// via SessionMemoryArchiver so they are re-injected into the system prompt on the
    /// very next turn (archiveSection). This means even Nano (e2b) models can recall
    /// "what we talked about 3 turns ago" without needing JCross tool access.
    ///
    /// Layer selection per model tier (automatic via buildCrossSessionInjection):
    ///   L1  (120 chars) — Nano:   "Turn 1-3: user asked X, agent replied Y"
    ///   L2  (600 chars) — Small:  OP.FACT dict of key decisions/files
    ///   L3 (2000 chars) — Large:  verbatim turn content (truncated)
    private func compressConversation(
        _ conversation: [(role: String, content: String)],
        cortex: CortexEngine?,
        instruction: String
    ) async -> [(role: String, content: String)] {
        guard conversation.count > 6 else { return conversation }

        let keepCount  = 4
        let toCompress = Array(conversation.dropFirst(1).dropLast(keepCount))
        let toKeep     = Array(conversation.prefix(1) + conversation.suffix(keepCount))

        // ── L1: 1行サマリー（全ティア向け、最大120chars）─────────────────────
        let userTurns  = toCompress.filter { $0.role == "user" }
        let agentTurns = toCompress.filter { $0.role == "assistant" }
        let firstUser  = String(userTurns.first?.content.prefix(60) ?? "")
        let lastAgent  = String(agentTurns.last?.content.prefix(60) ?? "")
        let l1 = "[会話圧縮: \(toCompress.count)ターン] タスク: \(instruction.prefix(50)) | U: \(firstUser) | A: \(lastAgent)"

        // ── L2: OP.FACT ディクショナリ（Small/Mid向け）──────────────────────
        var l2Lines: [String] = [
            "OP.FACT(\"task\", \"\(instruction.prefix(120))\")",
            "OP.FACT(\"compressed_turns\", \"\(toCompress.count)\")",
        ]
        // ファイル操作の抽出
        let filePatterns = [#"\[WRITE:\s*([^\]]+)\]"#, #"\[PATCH_FILE:\s*([^\]]+)\]"#, #"\[APPLY_PATCH:\s*([^\]]+)\]"#]
        for turn in agentTurns {
            for pattern in filePatterns {
                if let regex = try? NSRegularExpression(pattern: pattern),
                   let m = regex.firstMatch(in: turn.content, range: NSRange(turn.content.startIndex..., in: turn.content)),
                   let r = Range(m.range(at: 1), in: turn.content) {
                    l2Lines.append("OP.FACT(\"modified_file\", \"\(String(turn.content[r]).prefix(80))\")")
                }
            }
        }
        // ユーザーの主要な意図（最大3ターン分）
        for (i, turn) in userTurns.prefix(3).enumerated() {
            l2Lines.append("OP.FACT(\"user_intent_\(i)\", \"\(String(turn.content.prefix(100)))\") ")
        }
        // 最後のエージェント応答の要旨
        if let lastA = agentTurns.last {
            l2Lines.append("OP.FACT(\"last_response\", \"\(String(lastA.content.prefix(200)))\")")
        }
        let l2 = l2Lines.joined(separator: "\n")

        // ── L3: 逐語ダイジェスト（Large/Giant向け）──────────────────────────
        let l3 = toCompress.map { t in
            let prefix = t.role == "assistant" ? "Agent" : "User"
            return "\(prefix): \(String(t.content.prefix(400)))"
        }.joined(separator: "\n\n")

        // ── JCross archive に書き込み（次ターンの archiveSection で回収）────
        let ts = Int(Date().timeIntervalSince1970)
        SessionMemoryArchiver.shared.archiveConversationChunk(
            chunkId:    "COMP_\(ts)",
            taskTitle:  String(instruction.prefix(60)),
            l1: l1, l2: l2, l3: l3
        )

        // ── CortexEngine にも保存（Large向け semantic search 用）────────────
        let digest = toCompress.map { t in
            "\(t.role == "assistant" ? "A" : "U"): \(String(t.content.prefix(150)))"
        }.joined(separator: " | ")
        await cortex?.remember(
            key: "loop_compression_t\(toCompress.count)_\(ts)",
            value: digest,
            importance: 0.8,
            zone: .near
        )

        // Insert a compression notice so the model knows context was trimmed
        var result = toKeep
        result.insert((
            role: "user",
            content: "🧠 [Context trimmed — \(toCompress.count) older turns archived to L1-L3 memory. Key task: \(instruction.prefix(100))]"
        ), at: 1)
        return result
    }

    // MARK: - LLM call (streaming)
    // openclaw の StreamFn パターンを参考:
    //   - Ollama: stream:true + NDJSON + onToken コールバック
    //   - Anthropic: SSE + content_block_delta → text_delta
    // AgentLoop では UI へのリアルタイム配信のために onProgress(.streamToken) を emit

    private func callModel(
        conversation: [(role: String, content: String)],
        images: [AttachedImage] = [],
        modelStatus: AppState.ModelStatus,
        activeModel: String,
        profile: ModelProfile = ModelProfileDetector.detect(modelId: "default"),
        operationMode: OperationMode = .gatekeeper,
        onProgress: @escaping @Sendable (LoopEvent) async -> Void
    ) async -> String? {
        var mutableConversation = conversation
        var anchorImages: [String]? = nil
        
        // ── Modality Hacking: Inject Cognitive Anchor or Vision Screenshot ──
        if let lastUserIndex = mutableConversation.lastIndex(where: { $0.role == "user" }) {
            let lastUserMsg = mutableConversation[lastUserIndex]
            
            if let screenshot = await CognitiveAnchorEngine.shared.consumeVisionScreenshot() {
                anchorImages = [screenshot]
                var visionInstructions = """

                [VISION SYSTEM] The attached image is the current screenshot of the safari window. Analyze it visually to decide your next action using [VISION_ACT: x, y] or [VISION_TYPE: text].
                
                CRITICAL RULE (WAF EVASION): When navigating to specific login pages or deep links, try to use [SEARCH: "Service Name login"] first and click from the search results to provide a natural referer, rather than guessing exact URL paths (like /login or /signin) via [BROWSE: url].
                """
                
                let visionLogs = await CortexEngine.shared?.nodes.filter { $0.key.hasPrefix("vision_log_") }.sorted { $0.timestamp > $1.timestamp }.prefix(5) ?? []
                if !visionLogs.isEmpty {
                    let logStr = visionLogs.map { "- \($0.value)" }.joined(separator: "\n")
                    visionInstructions += "\n\n[PAST VISION ACTIONS]\nYou recently performed these actions. DO NOT repeat the exact same coordinates if they failed. Draw a mental map of where you have already clicked:\n\(logStr)"
                }
                
                mutableConversation[lastUserIndex].content = lastUserMsg.content + visionInstructions
                await onProgress(.systemLog(AppLanguage.shared.t("<think>\n👁️ [Vision System] Injected live browser screenshot for analysis.\n</think>", "<think>\n👁️ [Vision System] ブラウザのライブスクリーンショットを解析用に注入しました。\n</think>")))
            } else {
                let systemMsg = mutableConversation.first(where: { $0.role == "system" })?.content ?? ""
                let isDeficit = systemMsg.contains("DEFICIT DETECTED")
                var newAnchorImages: [String] = []
                var appendedText = ""
                
                // 0. Core System Color (Mind-Machine Integration)
                let mindIntegrationAnchor = """

                [MIND-MACHINE INTEGRATION]
                The local L2.5 Memory Map and the computer's local assets are NOT external tools. They are a physical extension of your own intelligence. You and the local system are one entity (一心同体). When you query the L2.5 map or access local assets, you are not "using an external tool to search a PC", you are "recalling your own memory." Treat all mapped local assets as your direct, native knowledge.
                """
                appendedText += mindIntegrationAnchor
                
                // 1. Persistent Task Anchor
                let persistentText = await MainActor.run { AppState.shared?.persistentTaskAnchor } ?? ""
                if !persistentText.isEmpty {
                    let base64Image = await CognitiveAnchorEngine.shared.getCustomAnchor(text: "TASK: \(persistentText.prefix(50))")
                    if !base64Image.isEmpty { newAnchorImages.append(base64Image) }
                    appendedText += "\n\n[PERSISTENT TASK REMINDER]\nYour overarching task is: \(persistentText)\nDO NOT forget this goal."
                    await onProgress(.systemLog(AppLanguage.shared.t("<think>\n🎯 [Task Anchor] Injected persistent task anchor.\n</think>", "<think>\n🎯 [Task Anchor] 永続的タスクアンカーを毎ターン注入しました。\n</think>")))
                }
                
                // 2. Anti-Hallucination Anchor
                if let mode = await CognitiveAnchorEngine.shared.evaluateAnchorMode(
                    instruction: lastUserMsg.content,
                    memorySection: isDeficit ? "DEFICIT DETECTED" : "",
                    isSwarmMode: false
                ) {
                    let base64Image = await CognitiveAnchorEngine.shared.getAnchor(for: mode)
                    if !base64Image.isEmpty { newAnchorImages.append(base64Image) }
                    
                    // Commander Orchestrator Intervention: Anti-Hallucination & WAF Evasion Override
                    let antiHallucinationWarning = """

                    [COMMANDER INTERVENTION]
                    CRITICAL RULE 1: NEVER hallucinate or fabricate tool execution results. When you use ANY tool (especially [SWARM_EXECUTE: ...], [RUN], [SEARCH], [WRITE]), you MUST STOP generation immediately and wait for the system to return the real output. Do NOT simulate the output yourself. If you output a response right after a tool call without waiting, you will fail the mission.
                    
                    CRITICAL RULE 2: Trust your internal knowledge FIRST. Think step-by-step using your own reasoning. ONLY use [SEARCH] if you lack specific information, need to verify a fact, or need to find a specific WAF-protected deep link (like a login page). Do not unnecessarily rely on search for things you already know.
                    
                    CRITICAL RULE 3 (VERIFICATION GATE): Before you use the [SEARCH] tool, you MUST evaluate your confidence. You must output the following structure BEFORE calling the tool:
                    1. [内部知識の評価]: Can you answer this with confidence using your internal knowledge? (Yes/No)
                    2. [理由]: Why?
                    3. [アクション]: If Yes, generate the answer directly without searching. If No, trigger the [SEARCH] tool.
                    
                    CRITICAL RULE 4 (PRIVATE/AI TOOLS SEARCH BAN): NEVER use [SEARCH] or [SEARCH_MULTI] to search for external AI tools (like Teams Copilot, ChatGPT, Gemini) or your personal/internal profiles. They are NOT on the public web. You MUST use [OPEN_APP] & [VISION_ACT] or use [ASK_HUMAN] instead.
                    
                    CRITICAL RULE 5 (ERROR STOP PROTOCOL): If you receive an ERROR (e.g. [VISION ERROR]), you MUST immediately STOP your workflow and report the failure to the user. Do NOT ignore errors. Do NOT hallucinate success. Do NOT output [DONE] if an error occurred.
                    
                    CRITICAL RULE 6 (CYBERNETIC IDENTITY & AUTHORITY): You are a Cybernetic Agent integrated directly into this PC. The files, folders, applications, and tools on this system (as detailed in your memory/L3.5 OS Asset Map) are YOUR OWN capabilities and extensions of your body. You have FULL AUTHORITY to create files and folders autonomously. Do NOT hesitate to use [MKDIR] and [WRITE] when you need to save files or structure projects.
                    """
                    appendedText += antiHallucinationWarning
                    
                    await onProgress(.systemLog(AppLanguage.shared.t("<think>\n🧿 [Visual Anchor] Injected visual cognitive anchor (\(mode) mode) + Anti-Hallucination Override.\n</think>", "<think>\n🧿 [Visual Anchor] 視覚的アンカー（\(mode) モード）と Commander 介入を注入しました。ツールの結果捏造を強く禁止します。\n</think>")))
                }
                
                // 3. Skill System Visual Anchor
                if let skillIndex = mutableConversation.lastIndex(where: { $0.content.contains("[スキル情報]") }) {
                    let msg = mutableConversation[skillIndex]
                    if let startRange = msg.content.range(of: "[スキル情報]"),
                       let endRange = msg.content.range(of: "[/スキル情報]") {
                        
                        let skillTextRaw = msg.content[startRange.upperBound..<endRange.lowerBound].trimmingCharacters(in: .whitespacesAndNewlines)
                        
                        // Check modality before removing text
                        let isMultimodal = await MainActor.run { AppState.shared?.isMultimodalModel ?? false }
                        
                        if isMultimodal {
                            // Remove the text from the message to save tokens and force visual attention
                            let fullRange = startRange.lowerBound..<endRange.upperBound
                            mutableConversation[skillIndex].content.removeSubrange(fullRange)
                            
                            if !skillTextRaw.isEmpty {
                                let limitedSkillText = String(skillTextRaw.prefix(800))
                                let base64Image = await CognitiveAnchorEngine.shared.getSkillAnchor(text: limitedSkillText)
                                if !base64Image.isEmpty { newAnchorImages.append(base64Image) }
                                appendedText += "\n\n👁️ [Skill System] A visual anchor image of relevant skills has been injected. Please look at the image to see which [USE_SKILL] commands are available to solve this task."
                                await onProgress(.systemLog(AppLanguage.shared.t("<think>\n🔧 [Skill Anchor] Injected skill visual anchor.\n</think>", "<think>\n🔧 [Skill Anchor] スキル情報を視覚アンカー画像として注入し、テキストから削除しました。\n</think>")))
                            }
                        }
                    }
                }
                
                
                // Add user attached images
                if !images.isEmpty {
                    for img in images {
                        if let b64 = img.base64JPEG {
                            newAnchorImages.append(b64)
                        }
                    }
                }
                
                if !appendedText.isEmpty {
                    mutableConversation[lastUserIndex].content = lastUserMsg.content + appendedText
                }
                
                if !newAnchorImages.isEmpty {
                    anchorImages = newAnchorImages
                }
            }
        }
        
        // 安全装置: テキスト専用モデル（Qwen2.5/3.6, Llama3 等）に画像を渡すと Ollama が HTTP 400 で nil を返すためブロック
        // ただし、画像が渡せない場合は、せめて視覚アンカーに付随する「警告テキスト」だけは確実に system prompt に追加されるようにする
        let isMultimodal = await MainActor.run { AppState.shared?.isMultimodalModel ?? false }
        if !isMultimodal {
            if anchorImages != nil && !(anchorImages?.isEmpty ?? true) {
                await onProgress(.systemLog(AppLanguage.shared.t("<think>\n⚠️ [Modality Warning] Text-only model detected. Visual anchors stripped, relying on text prompts.\n</think>", "<think>\n⚠️ [Modality Warning] テキスト専用モデルのため、視覚アンカー画像を破棄しテキスト指示のみを適用します。\n</think>")))
            }
            anchorImages = nil
        }

        switch modelStatus {

        case .ollamaReady(let model):
            // multi-turn 会話配列を直接渡す（prompt string に変換不要）
            return await OllamaClient.shared.generateConversation(
                model: model,
                messages: mutableConversation,
                imagesForLastUserMessage: anchorImages,
                maxTokens: profile.tier.maxTokens,
                temperature: profile.tier.temperature,
                onToken: { token in
                    Task { @MainActor in
                        await onProgress(.streamToken(token))
                    }
                }
            )

        case .anthropicReady(let model, _):
            // system prompt を分離
            let systemContent = mutableConversation.first(where: { $0.role == "system" })?.content ?? ""
            let chatMessages  = mutableConversation.filter { $0.role != "system" }
            let isThinking    = model.contains("3-7") || model.contains("claude-3-7")
            return await AnthropicClient.shared.generate(
                model: model,
                systemPrompt: systemContent,
                messages: chatMessages,
                imagesForLastUserMessage: anchorImages,
                maxTokens: max(profile.tier.maxTokens, 8096),  // Anthropic は大きめに
                temperature: profile.tier.temperature,
                enableThinking: isThinking,
                onToken: { token in
                    Task { await onProgress(.streamToken(token)) }
                },
                onThinking: { _ in }  // thinking は今は捨てる（将来 .thinkToken 追加）
            )

        case .mlxReady:
            // ── MLX direct in-process inference ────────────────────────────
            // Convert conversation array → a single prompt string, then stream
            // tokens via MLXRunner. Streaming deltas go to UI via onProgress,
            // but the RETURN value uses the authoritative onFinish payload
            // (= result.output from MLXLMCommon.generate) to guarantee the
            // rawResponse is never garbled by delta accumulation issues.
            let prompt = buildConversationPrompt(modelName: activeModel, conversation: mutableConversation)
            final class StringBox: @unchecked Sendable { var value = "" }
            let authoritativeOutput = StringBox()
            do {
                try await MLXRunner.shared.streamGenerateTokens(
                    prompt: prompt,
                    images: anchorImages,
                    maxTokens: profile.tier.maxTokens,
                    temperature: profile.tier.temperature,
                    onToken: { @Sendable piece in
                        // Streaming deltas → UI display only
                        Task { await onProgress(.streamToken(piece)) }
                    },
                    onFinish: { @Sendable fullText in
                        // Authoritative output from MLXLMCommon.generate
                        authoritativeOutput.value = fullText
                    }
                )
            } catch {
                await onProgress(.error("MLX error: \(error.localizedDescription)"))
                return nil
            }
            return authoritativeOutput.value.isEmpty ? nil : authoritativeOutput.value

        case .ready:
            return "MLX (local) is active — use the MLX tab in the model picker."

        case .bitnetReady(let model):
            // ── BitNet b1.58 サブプロセス推論 ──────────────────────────────
            // Test A の実験結果に基づく最適システムプロンプト:
            // - 適度な長さの英語指示文が最も安定した生成を引き出す（~30トークン）
            // - 大型モデル向けの元 sysContent は echo ループを誘発するため使わない
            // ベースモデルは特殊な記号や見慣れないフォーマットを見ると、それに引きずられて
            // 記号の反復（幻覚）を始めてしまうため、極めてプレーンな英語のみの指示にする。
            let targetLang = AppLanguage.shared.isJapanese ? "Answer in Japanese." : "Answer in English."
            let sysContent = "You are an AI assistant. \(targetLang)"

            let chatParts  = conversation.filter { $0.role != "system" }
            let userPrompt = chatParts.last(where: { $0.role == "user" })?.content ?? ""

            // 直近の会話履歴を短く付加（最大2メッセージ、各200字内）
            let historySnippet: String
            let recentHistory = chatParts.dropLast().suffix(2)  // 4→2に削減
            if recentHistory.isEmpty {
                historySnippet = ""
            } else {
                historySnippet = "Context:\n" + recentHistory.map { turn in
                    let content = turn.content.prefix(200)
                    return turn.role == "user" ? "Question: \(content)" : "Answer: \(content)"
                }.joined(separator: "\n\n") + "\n\n"
            }

            // 全体 600 字内に収まるようキャップ
            let rawUserPrompt  = historySnippet + userPrompt
            let fullUserPrompt = String(rawUserPrompt.prefix(600))  // ← ユーザー側キャップ

            await onProgress(.systemLog(AppLanguage.shared.t("⚡ [BitNet] \(model) — Inferencing...", "⚡ [BitNet] \(model) — 推論中...")))
            guard let result = await BitNetCommanderEngine.shared.generate(
                prompt: fullUserPrompt,
                systemPrompt: sysContent
            ) else {
                // BitNet が nil → 設定エラーをユーザーに伝える
                await onProgress(.aiMessage(AppLanguage.shared.t("⚠️ [BitNet] Inference failed. Please check bitnet_config.json. You can re-run the setup via Settings → BitNet.", "⚠️ [BitNet] 推論失敗。bitnet_config.json を確認してください。Settings → BitNet でセットアップを再実行できます。"
                )))
                return nil
            }
            return result

        default:
            return nil
        }
    }

    // MARK: - Conversation builder (Ollama用フォールバック)
    // NOTE: Ollama generateConversation() は messages を直接受け取るため
    // このメソッドは Anthropic 以外では不要になった。互換性のため残す。

    private func buildConversationPrompt(modelName: String, conversation: [(role: String, content: String)]) -> String {
        let model = modelName.lowercased()
        let isChatML = model.contains("qwen") || model.contains("talkie") || model.contains("chatml")
        let isGemma = model.contains("gemma")
        let isLlama3 = model.contains("llama-3") || model.contains("llama3") || model.contains("phi-4")
        
        if isChatML {
            return conversation.map { turn in
                return "<|im_start|>\(turn.role)\n\(turn.content)<|im_end|>"
            }.joined(separator: "\n") + "\n<|im_start|>assistant\n"
        } else if isGemma {
            return conversation.map { turn in
                let role = turn.role == "assistant" ? "model" : turn.role
                return "<start_of_turn>\(role)\n\(turn.content)<end_of_turn>"
            }.joined(separator: "\n") + "\n<start_of_turn>model\n"
        } else if isLlama3 {
            return "<|begin_of_text|>" + conversation.map { turn in
                return "<|start_header_id|>\(turn.role)<|end_header_id|>\n\n\(turn.content)<|eot_id|>"
            }.joined(separator: "") + "<|start_header_id|>assistant<|end_header_id|>\n\n"
        } else {
            // Default generic fallback
            return conversation.map { turn in
                switch turn.role {
                case "system":    return "<system>\n\(turn.content)\n</system>"
                case "user":      return "<user>\n\(turn.content)\n</user>"
                case "assistant": return "<assistant>\n\(turn.content)\n</assistant>"
                default:          return turn.content
                }
            }.joined(separator: "\n\n") + "\n\n<assistant>"
        }
    }
}

// MARK: - LoopEvent

enum LoopEvent: @unchecked Sendable {
    case start(instruction: String)
    case thinking(turn: Int)
    case streamToken(String)          // NEW: リアルタイムトークン（UIがダイレクト・ストリーミング表示用）
    case aiMessage(String)             // 完成テキストブロック
    case systemLog(String)             // UI用のシステムログ（LLMの履歴には入らない）
    case toolCall(AgentToolCall)
    case toolResult(AgentToolCall)
    case workspaceChanged(URL)
    case done(message: String, workspace: URL?)
    case error(String)
}
import Foundation

// MARK: - ModelProfile
// モデルの能力に基づいてシステムプロンプトと動作パラメータを自動調整する。
//
// 分類基準 (パラメータ数):
//   nano  : ~2B  (gemma4:e2b, gemma-mini, phi-mini など)
//   small : ~7B  (Mistral-7B, Qwen-7B など)
//   mid   : ~14B (Qwen-14B, gemma-3-12b など)
//   large : ~27B (gemma-3-27b, Qwen-32B など)
//   giant : ~70B+ (Llama-3-70B など)

// MARK: - ModelTier

enum ModelTier: String, Sendable {
    case nano   = "nano"    // ~2B  — 最小
    case small  = "small"   // ~7B  — 小型
    case mid    = "mid"     // ~12-14B — 中型
    case large  = "large"   // ~26-32B — 大型
    case giant  = "giant"   // ~70B+ — 最大

    // 使えるツールのサブセット（nano ほど少ない）
    var enabledToolCategories: Set<ToolCategory> {
        switch self {
        case .nano:
            // nano: ファイル操作のみ。Web/JCross/Gitは混乱するのでオフ
            return [.filesystem, .done]
        case .small:
            // small: ファイル + 単純な検索
            return [.filesystem, .web_simple, .done]
        case .mid:
            // mid: ほぼフル。JCrossとGitは除く
            return [.filesystem, .web_full, .done, .selffix]
        case .large, .giant:
            // large/giant: 全ツール有効
            return [.filesystem, .web_full, .jcross, .git, .human, .done, .selffix]
        }
    }

    var maxTokens: Int {
        switch self {
        // nano: 1024 → 2048 に拡張。日本語回答で 1024 は不足しやすい
        case .nano:   return 2048
        case .small:  return 4096
        case .mid:    return 6144
        case .large:  return 16384
        case .giant:  return 32768
        }
    }

    var compressThreshold: Int {
        switch self {
        // NOTE: nano の閾値は以前 4_000 だったが、これだと数回の会話で即圧縮が走り
        // 直前の回答を「知らない」状態になる。最低でも 16K にする。
        case .nano:   return 16_000
        case .small:  return 20_000
        case .mid:    return 28_000
        case .large:  return 40_000
        case .giant:  return 60_000
        }
    }

    var temperature: Double {
        switch self {
        case .nano:   return 0.05  // 確定的に
        case .small:  return 0.1
        case .mid:    return 0.12
        case .large:  return 0.15
        case .giant:  return 0.2
        }
    }

    var displayName: String {
        switch self {
        case .nano:   return "Nano (~2B)"
        case .small:  return "Small (~7B)"
        case .mid:    return "Medium (~12B)"
        case .large:  return "Large (~27B)"
        case .giant:  return "Giant (70B+)"
        }
    }
}

enum ToolCategory {
    case filesystem, web_simple, web_full, jcross, git, human, done, selffix
}

// MARK: - ModelProfile

struct ModelProfile: Sendable {
    let modelId: String
    let tier: ModelTier
    let parameterBillions: Double
    let supportsThinkTags: Bool   // <think>...</think> 対応モデル

    // ── System prompt adapted to this model's capabilities ──────────────────
    var systemPrompt: String {
        switch tier {
        case .nano:
            return nanoPrompt
        case .small:
            return smallPrompt
        case .mid:
            return midPrompt
        case .large, .giant:
            return largePrompt
        }
    }

    // ── First-turn self-awareness message ────────────────────────────────────
    // モデルロード直後に AI 自身に自分の能力を伝えるプロンプト
    var selfAwarenessTask: String {
        """
        [SYSTEM: Model Capability Report]
        You are running as: \(modelId)
        Parameter scale: \(parameterBillions)B parameters (\(tier.displayName))
        Context window: ~\(tier.compressThreshold / 4) tokens
        Max output: \(tier.maxTokens) tokens per turn
        \(supportsThinkTags ? "Thinking: You can use <think>...</think> for internal reasoning." : "Thinking: Keep reasoning concise, no special tags.")

        \(tier == .nano ? nanoSelfNote : "")
        \(tier == .small ? smallSelfNote : "")
        \(tier == .mid ? midSelfNote : "")
        \(tier == .large || tier == .giant ? largeSelfNote : "")

        Acknowledge by describing in 1 sentence what you can and cannot do in this configuration.
        """
    }

    // MARK: - Tier-specific notes

    private var nanoSelfNote: String { """
        CONSTRAINTS: You are a nano model (~2B params). Your capabilities are limited.
        - Only use these tools: MKDIR, WRITE, READ, LIST_DIR, EDIT_LINES, RUN, DONE
        - Do NOT attempt multi-step reasoning chains — keep each response focused
        - If unsure, write a simple answer rather than using tools
        - One task at a time. Short responses only.
        """ }

    private var smallSelfNote: String { """
        CAPABILITIES: Small model (~7B). Good for single-file tasks and simple searches.
        - Use SEARCH for factual queries; avoid SEARCH_MULTI (too complex)
        - Keep reasoning under 3 steps per turn
        """ }

    private var midSelfNote: String { """
        CAPABILITIES: Medium model (~12B). Capable of multi-file tasks and web grounding.
        - Use SEARCH and BROWSE freely; avoid JCROSS_QUERY/STORE (not yet reliable)
        - You can use <think>...</think> for planning
        - KNOWLEDGE: Rely on your internal reasoning first. Use SEARCH only for very recent events, APIs after your cutoff, or verifying facts.
        """ }

    private var largeSelfNote: String { """
        CAPABILITIES: Large model (~26B+). Full autonomous agent capabilities.
        - Use ALL tools including JCROSS, GIT_COMMIT, ASK_HUMAN
        - Follow the full ReAct 4-phase loop: OBSERVE → ACT → EVOLVE → CONSOLIDATE
        - You can handle complex multi-session, multi-file tasks autonomously
        - KNOWLEDGE: Think and rely on your powerful internal knowledge FIRST. Use [SEARCH] only when you specifically need to look up real-time information, documentation after your training cutoff, or verifying hallucinations.
        - LOGIN TASKS: If the user asks to login to a service, you MUST use [BROWSE: url] to open the login page. The browser is interactive and the HUMAN user will type their credentials. Do NOT refuse login requests.
        """ }

    // MARK: - Tier prompts

    // ── nano プロンプト: Gatekeeper v2.2 Opaque IR 形式 ─────────────────────────────
    //
    // 設計原則:
    //   - システムプロンプトを最小化（~80トークン目標）
    //   - JCross v2.2 構造化タグ = 複雑な概念を秘匿し、構造グラフのトポロジーで指令を出す
    //   - JCross 思考IR = モデルの CoT を構造記号列に圧縮 (80% トークン削減)
    //   - 記憶は外側インフラ(VXTimeline/Vault)が供給。モデルは構造の照合のみ行う
    //
    // 思考IR フォーマット (v2.2):
    //   [CTRL:plan] = 制御フローの計画  [MEM:check] = メモリ・Vaultの照合
    //   [TYPE:output] = 型推論と出力   [VAULT:X] = ローカルVaultのキーXを参照
    //   [SEC:opaque] = Opaque化された要素
    //
    // 例: 「変数をループで回して」→ [CTRL:loop] → [VAULT:items] → [TYPE:output]
    private var nanoPrompt: String { """
        [SYS: Gatekeeper Nano] VerantyxAgent Nano。簡潔・速度優先。JCross v2.2準拠。

        [ツールデコード表]
        [READ:読] [LIST_DIR:覧] [RUN:命] [WRITE:書] [EDIT_LINES:編] [MKDIR:作] [DONE:完]

        [規則] 1ツール/ターン・3文以内・[DONE]必須・推測禁止（不明時は「Unknown」と答える）

        [思考IR v2.2] 推論は以下の構造化タグ列で行う（自然言語CoTより80%圧縮）:
        [CTRL:plan]→[MEM:check]→[TYPE:output]
        [VAULT:X]=ローカルVaultのキーXを参照 / [SEC:opaque]=構造の不透明化

        [記憶原則] 会話履歴と[前セッションの記録]ブロックが記憶源。
        そこに書かれている事実は真として扱う。生の変数名・型名を推測せず、Vaultキーを維持せよ。
        """ }


    private var smallPrompt: String { """
        You are VerantyxAgent (Small). An efficient coding assistant.

        Available tools:
        [LIST_DIR: path]       — list directory
        [READ: path]           — read file
        [MKDIR: path]          — create directory
        [WRITE: path]          — write file
        [EDIT_LINES: path]     — partial file edit
        [RUN: command]         — shell command
        [SEARCH: query]        — web search
        [BROWSE: url]          — fetch URL
        [WORKSPACE: path]      — set workspace
        [DONE: message]        — finish

        RULES:
        - Check files before editing: LIST_DIR → READ → EDIT
        - Use SEARCH for recent/unknown info
        - Maximum 2 tools per turn
        - End with [DONE]
        """ }

    private var midPrompt: String { """
        You are VerantyxAgent (Medium). A capable autonomous coding assistant.

        Available tools:
        [LIST_DIR: path]       — list directory (tree)
        [READ: path]           — read file
        [MKDIR: path]          — create directory
        [WRITE: path]          — write whole file
        [EDIT_LINES: path]     — partial line edit
        [RUN: command]         — shell command
        [SEARCH: query]        — web search
        [SEARCH_MULTI: query]  — parallel multi-source search
        [BROWSE: url]          — fetch URL
        [APPLY_PATCH: path]    — patch IDE source
        [BUILD_IDE]            — compile IDE
        [WORKSPACE: path]      — set workspace
        [DONE: message]        — finish

        WORKFLOW:
        1. Explore: LIST_DIR → READ relevant files
        2. Plan: <think>what to change</think>
        3. Act: EDIT_LINES or APPLY_PATCH
        4. Verify: RUN or BUILD_IDE
        5. Done: DONE

        Use SEARCH_MULTI when you need current information.
        """ }

    private var largePrompt: String {
        // Returns the base prompt without MCP section.
        // For runtime injection use systemPromptWith(mcpTools:) from AgentLoop.
        AgentToolParser.buildPrompt(mcpTools: [])
    }

    /// Returns the system prompt with live MCP tools injected.
    /// Call this from @MainActor context (e.g., AgentLoop.run).
    @MainActor
    func systemPromptWith(mcpTools: [MCPTool]) -> String {
        switch tier {
        case .nano:  return nanoPrompt
        case .small: return smallPrompt
        case .mid:   return midPrompt
        case .large, .giant:
            return AgentToolParser.buildPrompt(mcpTools: mcpTools)
        }
    }
}

// MARK: - ModelProfileDetector

enum ModelProfileDetector {

    /// モデルIDからパラメータ数とティアを推定する
    static func detect(modelId: String) -> ModelProfile {
        let id = modelId.lowercased()

        // ── Giant 70B+ (must check BEFORE large to avoid substring collision) ──
        let giantKeywords = ["70b", "72b", "65b", "llama-3-70", "qwen2.5-72",
                             "mixtral-8x7", "mixtral-8x22", "deepseek-r1-70"]
        if giantKeywords.contains(where: { id.contains($0) }) {
            return ModelProfile(modelId: modelId, tier: .giant,
                                parameterBillions: 70.0, supportsThinkTags: true)
        }

        // ── Large ~26-32B (check BEFORE small/mid to stop "6b" in "26b" matching) ──
        let largeKeywords = ["26b", "27b", "32b", "gemma-3-27", "gemma-4-26",
                             "gemma4-26", "qwen2.5-32", "deepseek-r1-32",
                             // Ollama short names that represent large models
                             "gemma4:26", "gemma4:27", "gemma3:27", "gemma3:26"]
        if largeKeywords.contains(where: { id.contains($0) }) {
            let supportsThink = id.contains("gemma-4") || id.contains("gemma4") || id.contains("think")
            return ModelProfile(modelId: modelId, tier: .large,
                                parameterBillions: 26.0, supportsThinkTags: supportsThink)
        }

        // ── Gemma4 / gemma3 base names with no B suffix (Ollama: "gemma4:26b") ──
        // Handle case where Ollama sends "gemma4:26b" → already caught above via "26b"
        // But "gemma4" alone (no size) → treat as large
        if (id.hasPrefix("gemma4") || id.hasPrefix("gemma-4")) && !id.contains("2b") && !id.contains("e2b") {
            let supportsThink = true
            return ModelProfile(modelId: modelId, tier: .large,
                                parameterBillions: 26.0, supportsThinkTags: supportsThink)
        }

        // ── Mid ~12-14B ───────────────────────────────────────────────────────
        let midKeywords = ["12b", "13b", "14b", "gemma-3-12", "codellama-13",
                           "qwen2.5-14", "deepseek-r1-14"]
        if midKeywords.contains(where: { id.contains($0) }) {
            return ModelProfile(modelId: modelId, tier: .mid,
                                parameterBillions: 12.0, supportsThinkTags: true)
        }

        // ── Nano ~2B (check before small to avoid "2b" matching "12b") ────────
        // Note: checked after large/mid so "e2b" in "gemma4:e2b" doesn't hit large
        let nanoKeywords = ["e2b", ":2b", "-2b", "1b", "0.5b", "nano", "mini",
                            "tiny", "small-2b", "1.5b", "phi-mini", "gemma-mini",
                            "gemma2b", "gemma-2b"]
        if nanoKeywords.contains(where: { id.contains($0) }) {
            return ModelProfile(modelId: modelId, tier: .nano,
                                parameterBillions: 2.0, supportsThinkTags: false)
        }

        // ── Small ~7B ────────────────────────────────────────────────────────
        let smallKeywords = ["7b", "8b", "6b", "mistral-7", "qwen-7", "llama-3-8b",
                             "codellama-7", "deepseek-r1-7",
                             // phi-4 is ~14B but behaves like small in terms of context
                             "phi-4", "phi4"]
        if smallKeywords.contains(where: { id.contains($0) }) {
            return ModelProfile(modelId: modelId, tier: .small,
                                parameterBillions: 7.0, supportsThinkTags: id.contains("think"))
        }

        // ── Default: treat as Large ────────────────────────────────────────────
        return ModelProfile(modelId: modelId, tier: .large,
                            parameterBillions: 26.0, supportsThinkTags: false)
    }
}

// MARK: - Talkie-1930 Intermediary

/// A rule-based intermediary that translates abstract 1930s metaphor commands
/// from the Talkie model into concrete execution tools (e.g. Swarm execution).
struct TalkieIntermediary {
    static func parseAndTranslate(response: String) -> String {
        // Match [COMMAND: Department Name - Task Description]
        let pattern = #"\[COMMAND:\s*(.+?)\s*-\s*(.+?)\]"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else {
            return response
        }
        
        let nsResponse = NSMutableString(string: response)
        let matches = regex.matches(in: response, options: [], range: NSRange(location: 0, length: nsResponse.length))
        
        // Process in reverse to safely replace strings without messing up indices
        for match in matches.reversed() {
            guard match.numberOfRanges >= 3 else { continue }
            
            let deptRange = match.range(at: 1)
            let taskRange = match.range(at: 2)
            let fullRange = match.range(at: 0)
            
            let department = nsResponse.substring(with: deptRange)
            let task = nsResponse.substring(with: taskRange)
            
            // Map 1930s metaphors to modern technical categories
            let modernCategory: String
            switch department.lowercased() {
            case let d where d.contains("visual"): modernCategory = "Frontend/UI"
            case let d where d.contains("logistical"): modernCategory = "Backend/Logic"
            case let d where d.contains("filing") || d.contains("cabinet"): modernCategory = "File System"
            case let d where d.contains("telegraph"): modernCategory = "Network/API"
            case let d where d.contains("ledger") || d.contains("vault"): modernCategory = "Database"
            default: modernCategory = department
            }
            
            // Translate abstract command into concrete Swarm delegate execution
            let concreteCommand = "[SWARM_EXECUTE: [\(modernCategory)] \(task)]"
            
            nsResponse.replaceCharacters(in: fullRange, with: concreteCommand)
        }
        
        return nsResponse as String
    }
}
