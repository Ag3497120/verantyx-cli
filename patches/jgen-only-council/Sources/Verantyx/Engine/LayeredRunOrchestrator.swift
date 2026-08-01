import Foundation

/// Runs the user's 4-layer architecture end to end:
///
///   Layer 0  memory        — Vera facts / L1-L3 zone memory / eternal vectors
///   Layer 1  council core  — same-arch JGEN roles deliberating in vector space
///   Layer 2  execution     — jgen-native speak (preferred) or a tool-using agent
///   Layer 3  escalation    — a stronger model, only when explicitly enabled
///
/// Layer 0 needs no code here: `CouncilOrchestrator.deliberate` already
/// assembles the memory prefix from the same `Config` flags this passes in.
/// The point of this type is the L1 → L2 → L3 sequencing and the fallbacks,
/// so no single missing piece (no JGEN model, no execution model configured)
/// leaves the user with nothing.
@MainActor
enum LayeredRunOrchestrator {

    /// True when the layered path can actually run: it needs the JGEN engine
    /// loaded, because the council deliberates on hidden states.
    static var isAvailable: Bool {
        if case .jcrossReady = AppState.shared?.modelStatus { return true }
        return false
    }

    /// - Returns: true if the layered path ran. False means the caller should
    ///   fall back to its normal agent loop (e.g. no JGEN model loaded).
    @discardableResult
    static func run(
        question: String,
        app: AppState,
        onProgress: @escaping @Sendable (LoopEvent) async -> Void
    ) async -> Bool {

        guard isAvailable else {
            await onProgress(.systemLog(AppLanguage.shared.t(
                "⚠️ Council needs a JGEN model loaded — falling back to the normal agent.",
                "⚠️ 合議にはJGENモデルのロードが必要です — 通常のエージェントで実行します。")))
            return false
        }

        let store = CouncilSettingsStore.shared
        var config = store.config
        // This orchestrator owns Layers 2 and 3; tell the council not to do
        // its own one-shot execution call.
        config.executionMode = .external

        // ── Layer 1: council ──────────────────────────────────────────────
        await onProgress(.systemLog(AppLanguage.shared.t(
            "🧠 [L1 Council] deliberating (\(config.roleCount) roles, up to \(config.roundsCap) rounds)…",
            "🧠 [L1 合議] 審議中 (\(config.roleCount)役割・最大\(config.roundsCap)ラウンド)…")))

        let result: CouncilOrchestrator.Result
        do {
            result = try await CouncilOrchestrator.shared.deliberate(question: question, config: config, onProgress: onProgress)
        } catch {
            await onProgress(.systemLog(AppLanguage.shared.t(
                "⚠️ [L1 Council] failed: \(error.localizedDescription) — falling back to the normal agent.",
                "⚠️ [L1 合議] 失敗: \(error.localizedDescription) — 通常のエージェントで実行します。")))
            return false
        }

        let handoff = result.handoff
        await onProgress(.aiMessage(AppLanguage.shared.t(
            "**[L1 合議 → 手渡し]**\n```\n\(handoff.asText)\n```",
            "**[L1 合議 → 手渡し]**\n```\n\(handoff.asText)\n```")))

        // ── Layer 2: execution ────────────────────────────────────────────
        let executionModel = store.executionModel.trimmingCharacters(in: .whitespaces)
        var outcome: ExecutionAgent.Outcome?
        var jgenSpoke = false

        // Preferred path for the jgen-vector-bus architecture: same engine as
        // L1, soft/eternal memory conditioning, **no AgentLoop** (avoids
        // Nano `[MEM:check]` prompt collapse on 0.5B–2B JGENs).
        let wantJGenNative = store.executionUseJGEN
            || store.templateId == "jgen-vector-bus"
        if wantJGenNative, case .jcrossReady = app.modelStatus {
            await onProgress(.systemLog(AppLanguage.shared.t(
                "🛠 [L2 Execution — JGEN native] same model as council — speak via vector bus (no AgentLoop)…",
                "🛠 [L2 実行 — JGENネイティブ] 合議と同一モデル — ベクトルバス発話（AgentLoopなし）…")))
            let speak = await JGenSpeakAgent.shared.run(
                handoff: handoff,
                question: question,
                useEternalMemory: config.useEternalMemory,
                onProgress: onProgress
            )
            outcome = .completed(speak.text)
            jgenSpoke = true
        } else if executionModel.isEmpty {
            await onProgress(.systemLog(AppLanguage.shared.t(
                "ℹ️ [L2] No execution model set — stopping at the council handoff. Set one in the JGEN options popover, or enable “JGEN for Layer 2”.",
                "ℹ️ [L2] 実行モデル未設定 — 合議の手渡しで停止します。JGENオプションで設定するか「L2もJGEN」を有効にしてください。")))
        } else {
            await onProgress(.systemLog(AppLanguage.shared.t(
                "🛠 [L2 Execution] \(executionModel) — acting on the handoff…",
                "🛠 [L2 実行] \(executionModel) — 手渡しに基づき実行中…")))

            let spec = ExecutionAgent.Spec(
                modelStatus: .ollamaReady(model: executionModel),
                activeModel: executionModel,
                workspaceURL: app.workspaceURL,
                operationMode: app.operationMode,
                chatSessionId: app.vxChatSessionId
            )
            outcome = await ExecutionAgent.shared.run(
                handoff: handoff,
                question: question,
                spec: spec,
                cortex: app.cortex,
                onProgress: onProgress
            )
        }

        // ── Layer 3: escalation (only when explicitly enabled) ───────────
        // jgen-vector-bus / escalateOnLowConfidence=false never enters here.
        let lowConfidence = handoff.confidence < config.escalationConfidenceThreshold
        let executionFailed = outcome?.isFailure ?? false
        let escalationModel = config.escalationModel.trimmingCharacters(in: .whitespaces)
        let allowEscalate = config.escalateOnLowConfidence && !jgenSpoke

        if allowEscalate, lowConfidence || executionFailed, !escalationModel.isEmpty {
            let reason = executionFailed
                ? AppLanguage.shared.t("execution failed", "実行が失敗")
                : AppLanguage.shared.t("confidence \(String(format: "%.2f", handoff.confidence)) below threshold", "確信度 \(String(format: "%.2f", handoff.confidence)) が閾値未満")
            await onProgress(.systemLog(AppLanguage.shared.t(
                "⬆️ [L3 Escalation] \(escalationModel) — \(reason).",
                "⬆️ [L3 エスカレ] \(escalationModel) — \(reason)。")))

            let digest = outcome.map { "\n[EXECUTION RESULT] \($0.text.prefix(1500))" } ?? ""
            if let answer = await OllamaClient.shared.generateConversation(
                model: escalationModel,
                messages: [
                    ("system", "You are the escalation layer. A council deliberated and an execution agent attempted the work; both are summarized below. Give the final, direct answer."),
                    ("user", handoff.asText + digest + "\n\n[ORIGINAL QUESTION] \(question)")
                ]
            ), !answer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                await onProgress(.done(message: answer, workspace: app.workspaceURL))
                return true
            }
            await onProgress(.systemLog(AppLanguage.shared.t(
                "⚠️ [L3] Escalation produced no answer.", "⚠️ [L3] エスカレーションは回答を返しませんでした。")))
        }

        // Terminal message: JGenSpeakAgent / ExecutionAgent already emit .done
        // through onProgress when they run; only close the turn when L2 never ran.
        if outcome == nil {
            await onProgress(.done(
                message: handoff.detail.isEmpty ? handoff.asText : handoff.detail,
                workspace: app.workspaceURL))
        }
        return true
    }
}
