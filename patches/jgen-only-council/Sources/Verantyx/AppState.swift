import Foundation
import Combine
import SwiftUI
import AppKit
import WebKit

// MARK: - Core data models

/// Tabs for the bottom slot of the editor's ResizableVSplit.
enum BottomPanelTab: String, CaseIterable, Identifiable {
    case terminal
    case memoryLayers

    var id: String { rawValue }

    @MainActor
    func displayName(_ app: AppState) -> String {
        switch self {
        case .terminal:     return app.t("Terminal", "ターミナル")
        case .memoryLayers: return app.t("Memory Layers", "記憶レイヤー")
        }
    }
}

struct ChatMessage: Identifiable, Equatable, Codable {
    var id: UUID
    var role: Role
    var content: String
    var timestamp = Date()
    var isSpotlight: Bool = false
    /// 推論中のプロセスログのスナップショット（折りたたみ可能な Thinking ブロックに表示）
    var thinkingLog: [ThinkingLogEntry] = []

    init(id: UUID = UUID(), role: Role, content: String, isSpotlight: Bool = false, thinkingLog: [ThinkingLogEntry] = []) {
        self.id = id
        self.role = role
        self.content = content
        self.isSpotlight = isSpotlight
        self.thinkingLog = thinkingLog
    }

    enum Role: String, Codable { case user, assistant, system }

    // ProcessLogEntry の Codable スナップショット（Color は保存しないためシンプル化）
    struct ThinkingLogEntry: Identifiable, Codable, Equatable {
        var id = UUID()
        var timestamp: Date
        var text: String
        var kind: String    // "memory" | "tool" | "browser" | "thinking" | "system" | "perf"
    }
}


struct FileDiff: Identifiable, Equatable {
    let id = UUID()
    let fileURL: URL
    let originalContent: String
    let modifiedContent: String
    var hunks: [DiffHunk]

    var hasChanges: Bool { originalContent != modifiedContent }

    // Equatable: same identity ↔ same diff (new FileDiff always has new UUID)
    static func == (lhs: FileDiff, rhs: FileDiff) -> Bool { lhs.id == rhs.id }
}

struct DiffHunk: Identifiable {
    let id = UUID()
    var lines: [DiffLine]
}

struct DiffLine: Identifiable {
    let id = UUID()
    var kind: Kind
    var text: String

    enum Kind { case context, added, removed }
}

// MARK: - AppState

@MainActor
final class AppState: ObservableObject {

    // ── Global weak reference — set at launch so AgentToolExecutor can call
    // ingestArtifact() from actor context without importing the full SwiftUI stack.
    @MainActor static weak var shared: AppState?

    // Workspace
    @Published var activeWebViews: [String: WKWebView] = [:]
    @Published var workspaceURL: URL?
    @Published var workspaceFiles: [URL] = []
    
    // ── Distributed Cortex Connectivity (Handshake) ──
    @Published var cortexWorkspacePath: String? = nil
    @Published var cortexSkillsPath: String? = nil
    @Published var cortexSwarmActive: Bool = false
    @Published var swarmNodeCount: Int = 0
    @Published var swarmStatusText: String = "Offline"
    @Published var isCortexConnected: Bool = false
    @Published var selectedFile: URL? {
        didSet {
            // Notify Extension Host that a new document was opened
            if let file = selectedFile {
                ExtensionHostManager.shared.sendNotification(method: "workspace.didOpenTextDocument", params: [
                    "uri": file.path,
                    "languageId": file.pathExtension,
                    "version": 1,
                    "text": selectedFileContent
                ])
            }
        }
    }
    @Published var selectedFileContent: String = "" {
        didSet {
            // Notify Extension Host that the document content changed
            if let file = selectedFile {
                ExtensionHostManager.shared.sendNotification(method: "workspace.didChangeTextDocument", params: [
                    "uri": file.path,
                    "text": selectedFileContent,
                    "range": [
                        "startLine": 0,
                        "endLine": max(0, oldValue.filter { $0 == "\n" }.count)
                    ]
                ])
            }
        }
    }

    // Model
    @Published var modelStatus: ModelStatus = .none
    /// Name of the `.jgen` model currently being loaded (nil = idle), and the
    /// last load failure. Shared by the model-selector bar and the JGEN
    /// settings section so both show the same spinner/error.
    @Published var jgenLoadingModel: String?
    @Published var jgenLoadError: String?
    @Published var ollamaModels: [String] = []
    // activeOllamaModel は下記(L412付近)でdidSetつきで宣言済み
    @Published var anthropicApiKey: String = "" {
        didSet {
            // Anthropic API キーを AnthropicClient に反映
            Task { await AnthropicClient.shared.configure(apiKey: anthropicApiKey) }
            UserDefaults.standard.set(anthropicApiKey, forKey: "anthropic_api_key")
        }
    }
    @Published var activeAnthropicModel: String = {
        UserDefaults.standard.string(forKey: "anthropic_model") ?? "claude-sonnet-4-5"
    }() {
        didSet { UserDefaults.standard.set(activeAnthropicModel, forKey: "anthropic_model") }
    }
    @Published var activeOpenAIModel: String = {
        UserDefaults.standard.string(forKey: "openai_model") ?? "gpt-4o"
    }() {
        didSet { UserDefaults.standard.set(activeOpenAIModel, forKey: "openai_model") }
    }
    @Published var activeGeminiModel: String = {
        UserDefaults.standard.string(forKey: "gemini_model") ?? "gemini-3.1-pro"
    }() {
        didSet { UserDefaults.standard.set(activeGeminiModel, forKey: "gemini_model") }
    }
    @Published var activeDeepSeekModel: String = {
        UserDefaults.standard.string(forKey: "deepseek_model") ?? "deepseek-coder"
    }() {
        didSet { UserDefaults.standard.set(activeDeepSeekModel, forKey: "deepseek_model") }
    }
    @Published var customHFRepoId: String = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
    @Published var downloadProgress: Double = 0

    // Chat
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""
    @Published var isGenerating = false

    // Self-Fix mode — when true, next message(s) target IDE self-modification
    // Must be explicitly toggled by user pressing the "Self Fix" button.
    @Published var selfFixMode: Bool = false
    @Published var persistentTaskAnchor: String = "" // 毎ターン自動注入されるタスクの画像アンカー
    /// Set to true when the AI calls [RESTART_IDE] — triggers a restart alert in the UI.
    @Published var showRestartAlert: Bool = false
    @Published var requiresHumanPuzzle: Bool = false
    @Published var isAgentControllingMouse: Bool = false
    @Published var isSwarmMode: Bool = false // 🐝 Swarm Pipeline Mode
    @Published var lastEntropy: [CGPoint]? = nil
    @Published var lastVideoFrames: [String]? = nil
    /// Set by `[DESKTOP_ACT]` click handling (`AgentTool.swift`) whenever
    /// `VisualDiffRegion` finds a changed region for the most recent click
    /// -- read (and cleared) by `AgentLoop.swift` right after the tool call
    /// so `UITestVectorTrace.recordMoment` can size/place the step's node.
    @Published var lastDesktopChangedRegion: CGRect? = nil
    @Published var lastKeyboardEntropy: [Double]? = nil
    @Published var lastEntropyTimestamp: Date? = nil
    @Published var searchCooldownUntil: Date? = nil
    var lastKeystrokeTime: Date? = nil

    // Attachments (images + files for multimodal inference)
    @Published var attachedImages: [AttachedImage] = []
    @Published var attachedFiles: [URL] = []

    // Inference task handle (for cancellation)
    private var inferenceTask: Task<Void, Never>? = nil

    // UUID of the assistant message bubble currently receiving streaming tokens.
    // Elevated to instance-level so restoreSession() can nil it on session switch,
    // preventing stale UUIDs from corrupting a newly-loaded session's first stream.
    var streamingMsgId: UUID? = nil

    // Agent-loop .streamToken buffering — the Ollama/MLX direct paths
    // already batch UI updates to ~25fps (40ms); the agent-loop path
    // (LoopEvent.streamToken, handled below) had no such throttle, so
    // `messages[idx].content += token` fired (and re-rendered the whole
    // ChatTranscriptView) once per token. Buffered the same way here.
    private var streamTokenBuffer: String = ""
    private var lastStreamFlush: Date = .distantPast

    private func flushStreamTokenBuffer() {
        guard !streamTokenBuffer.isEmpty else { return }
        if let sid = streamingMsgId, let idx = messages.firstIndex(where: { $0.id == sid }) {
            messages[idx].content += streamTokenBuffer
        } else {
            let msg = ChatMessage(role: .assistant, content: streamTokenBuffer)
            streamingMsgId = msg.id
            messages.append(msg)
        }
        streamTokenBuffer = ""
        lastStreamFlush = Date()
    }

    // ── Performance metrics (the "Apple Silicon violence" numbers) ──
    @Published var tokensPerSecond: Double = 0       // live tok/s display
    @Published var totalTokensGenerated: Int = 0     // session total
    @Published var streamingText: String = ""        // current token buffer for live render
    @Published var inferenceMs: Int = 0              // last response latency ms

    // ── Zero-Translation Steering Signal ──
    // Publisher that emits commands (like "^C", "cd src/auth") entered in the LiveTerminalView.
    // The AgentLoop will subscribe to this and interrupt its current task immediately.
    let steeringSubject = PassthroughSubject<String, Never>()
    
    func sendSteeringCommand(_ cmd: String) {
        logProcess("❯ \(cmd)", kind: .system)
        steeringSubject.send(cmd)
    }

    // ── Process log ("what is the AI thinking right now") ──
    @MainActor
    final class ProcessLogStore: ObservableObject {
        @Published var entries: [ProcessLogEntry] = []
    }
    let logStore = ProcessLogStore()
    
    @Published var showProcessLog: Bool = true

    struct ProcessLogEntry: Identifiable {
        let id = UUID()
        let timestamp: Date
        var text: String
        var kind: Kind

        enum Kind: String { case memory, tool, browser, thinking, system, perf }

        var prefix: String {
            switch kind {
            case .memory:   return "→ MEM  "
            case .tool:     return "→ TOOL "
            case .browser:  return "→ DOM  "
            case .thinking: return "▶ THINK"
            case .system:   return "⋯ SYS  "
            case .perf:     return "⚡ PERF "
            }
        }

        var color: Color {
            switch kind {
            case .memory:   return Color(red: 0.4, green: 0.9, blue: 0.6)
            case .tool:     return Color(red: 0.4, green: 0.8, blue: 1.0)
            case .browser:  return Color(red: 0.9, green: 0.7, blue: 0.3)
            case .thinking: return Color(red: 0.8, green: 0.8, blue: 1.0)
            case .system:   return Color(red: 0.6, green: 0.6, blue: 0.6)
            case .perf:     return Color(red: 0.3, green: 1.0, blue: 0.5)
            }
        }
    }

    // Diff
    @Published var pendingDiff: FileDiff?
    @Published var showDiff = false
    @Published var autoApproveDiffs: Bool = false

    // Human Mode: file write / create / edit approval
    @Published var pendingFileApproval: FileApprovalRequest? = nil

    // Vera-α layer: preview-before-save approval (see VeraMemoryBridge.swift)
    /// A 4-layer setup awaiting the user's approval. Presented as a sheet;
    /// nothing is applied until they press Apply.
    @Published var pendingSetupProposal: SetupProposal? = nil
    @Published var pendingVeraSave: VeraSaveApprovalRequest? = nil
    @Published var pendingVeraSaveQueue: [VeraSaveApprovalRequest] = []

    /// .perTurn (default): the agent loop blocks each turn until the
    /// human approves/rejects that turn's save -- what shipped originally.
    /// .batched: the agent keeps working uninterrupted; save requests
    /// queue up in pendingVeraSaveQueue for the human to review in bulk
    /// whenever they check back. See VeraMemoryBridge.requestSaveApproval.
    @Published var veraSaveApprovalMode: VeraSaveApprovalMode = .perTurn {
        didSet { UserDefaults.standard.set(veraSaveApprovalMode.rawValue, forKey: "vera_save_approval_mode") }
    }

    /// Stereo-cross 3D graph demo mode: replaces the code editor pane with
    /// a live SceneKit visualization of Vera's CrossStore (StereoCrossGraphView).
    /// While active, the Vera-α save-approval UI moves from a center-screen
    /// sheet into the chat transcript itself (see AgentChatView), and an
    /// approved save triggers a "connection" animation in the graph.
    @Published var showStereoCrossGraph: Bool = false
    /// Set by VeraMemoryBridge right after a save is approved while this
    /// mode is active; StereoCrossGraphView observes this to animate the
    /// new fact "connecting" into the structure, then clears it back to nil.
    @Published var pendingGraphConnection: String? = nil
    /// Real core key(s) VeraMemoryBridge.performSave actually saved under
    /// (from `remember`/`record_code_change`'s response), set alongside
    /// `pendingGraphConnection`. StereoCrossGraphView passes these as
    /// `focus_cores` when refreshing so a brand-new, low-pour-count fact is
    /// guaranteed to appear as a node instead of being crowded out by the
    /// top-ranked existing cores.
    @Published var pendingGraphFocusCores: [String] = []

    /// Shows the live mirror of whatever window HiddenWindowAutomation has
    /// parked off-screen, so the user can watch autonomous OS-agent
    /// operation without it visually stealing focus or covering the IDE.
    @Published var showHiddenWindowMirror: Bool = false

    /// Shows the JGEN Vector Lab: text-in/text-out exploration of
    /// JCrossEngine's raw hidden-state operations (encode, resynthesize,
    /// puzzle_inference's confidence/entropy, optimize_thought_in_place's
    /// latent gradient descent) -- independent of the normal chat path.
    @Published var showVectorLab: Bool = false

    /// Which view occupies the bottom slot of the editor's ResizableVSplit:
    /// the real terminal, or the L1-L3 memory-injection preview.
    @Published var bottomPanelTab: BottomPanelTab = .terminal

    // Active tab in the center chat panel — driven by AppState so
    // SessionHistoryView can programmatically switch to .workspace
    // after restoring a session (the tab @State lives in AgentChatView).
    @Published var activeChatTab: Int = 0   // 0=workspace, 1=history, 2=thinking

    // Operation Mode (AI Priority vs Human)
    // Gatekeeper is no longer the default operating mode: its premise was
    // that source code must never reach a cloud LLM, but enterprise
    // contracts now routinely forbid training on submitted code, so the
    // obfuscation round-trip costs accuracy for a risk that is handled
    // contractually. The mode still exists (opt-in) — see OperationMode.
    @Published var operationMode: OperationMode = .automatic {
        didSet {
            UserDefaults.standard.set(operationMode.rawValue, forKey: "operation_mode")
            // Sync MCPEngine execution mode
            Task { MCPEngine.shared.setMode(.ai) }
            
            // Auto-toggle JCross view and Gatekeeper State
            if operationMode == .gatekeeper {
                GatekeeperModeState.shared.isEnabled = true
                showGatekeeperRawCode = false
            } else {
                GatekeeperModeState.shared.isEnabled = false
                showGatekeeperRawCode = true
            }
            

            // L2.5 変換の制御 (自動実行は削除し、UI側の明示的なアクションまたは確認ダイアログに委ねる)
        }
    }

    // ── Non-Coding Task Routing ──
    enum NonCodingTaskEngine: String, CaseIterable, Codable {
        case localAgent = "Local Agent (Safe)"
        case cloudDirect = "Cloud Direct (MCP Tools)"
    }
    
    @Published var nonCodingTaskEngine: NonCodingTaskEngine = {
        let raw = UserDefaults.standard.string(forKey: "non_coding_engine") ?? NonCodingTaskEngine.localAgent.rawValue
        return NonCodingTaskEngine(rawValue: raw) ?? .localAgent
    }() {
        didSet { UserDefaults.standard.set(nonCodingTaskEngine.rawValue, forKey: "non_coding_engine") }
    }

    // ── Swarm Strategy ──
    enum SwarmStrategy: String, CaseIterable, Codable, Identifiable {
        case auto      = "Auto"
        case ultrawork = "Ultrawork"
        case ralph     = "Ralph"
        var id: String { rawValue }

        var displayName: String {
            switch self {
            case .auto:      return "Auto"
            case .ultrawork: return "Ultrawork"
            case .ralph:     return "Ralph"
            }
        }
    }

    @Published var activeSwarmStrategy: SwarmStrategy = {
        let raw = UserDefaults.standard.string(forKey: "active_swarm_strategy") ?? SwarmStrategy.auto.rawValue
        return SwarmStrategy(rawValue: raw) ?? .auto
    }() {
        didSet { UserDefaults.standard.set(activeSwarmStrategy.rawValue, forKey: "active_swarm_strategy") }
    }

    // ── Auditor (監視役) ──
    @Published var activeAuditorModel: String = {
        UserDefaults.standard.string(forKey: "active_auditor_model") ?? "llama3.1:8b"
    }() {
        didSet { UserDefaults.standard.set(activeAuditorModel, forKey: "active_auditor_model") }
    }
    @Published var isAuditorEnabled: Bool = {
        UserDefaults.standard.bool(forKey: "is_auditor_enabled")
    }() {
        didSet { UserDefaults.standard.set(isAuditorEnabled, forKey: "is_auditor_enabled") }
    }

    // ── Fine-Tuning ──
    @Published var fineTuningBaseModel: String = {
        UserDefaults.standard.string(forKey: "fine_tuning_base_model") ?? "llama3.1:8b"
    }() {
        didSet { UserDefaults.standard.set(fineTuningBaseModel, forKey: "fine_tuning_base_model") }
    }

    func clearFineTuningData() {
        let cortexWs = UserDefaults.standard.string(forKey: "cortex_workspace_path") ?? UserDefaults.standard.string(forKey: "last_workspace_path") ?? "/tmp"
        let baseDir = URL(fileURLWithPath: cortexWs).appendingPathComponent(".openclaw/memory/training_data")
        let datasetURL = baseDir.appendingPathComponent("verantyx_dataset.jsonl")
        
        if FileManager.default.fileExists(atPath: datasetURL.path) {
            let timestamp = Int(Date().timeIntervalSince1970)
            let archiveURL = baseDir.appendingPathComponent("verantyx_dataset_archive_\(timestamp).jsonl")
            try? FileManager.default.moveItem(at: datasetURL, to: archiveURL)
            self.addSystemMessage("🧹 The fine-tuning data has been archived to prevent duplicate training.")
        }
    }

    // Artifacts (Claude-style live preview)
    @Published var currentArtifact: Artifact? = nil
    @Published var artifactHistory: [Artifact] = []
    @Published var showArtifactPanel: Bool = false

    // Privacy Shield / Hybrid mode
    @Published var inferenceMode: InferenceMode = .localOnly {
        didSet { UserDefaults.standard.set(inferenceMode.rawValue, forKey: "inference_mode") }
    }
    public enum ExoRole: String, Codable, CaseIterable {
        case idle = "Idle"
        case master = "Master"
        case worker = "Worker"
    }
    
    @Published var exoEndpoint: String = ""
    @Published var exoEnabled: Bool = false {
        didSet { UserDefaults.standard.set(exoEnabled, forKey: "exo_enabled") }
    }
    @Published var exoRole: ExoRole = .idle {
        didSet { UserDefaults.standard.set(exoRole.rawValue, forKey: "exo_role") }
    }
    @Published var exoDeviceId: String = {
        if let id = UserDefaults.standard.string(forKey: "exo_device_id") { return id }
        let newId = UUID().uuidString
        UserDefaults.standard.set(newId, forKey: "exo_device_id")
        return newId
    }()
    @Published var cloudProvider: CloudProvider = .claude {
        didSet { UserDefaults.standard.set(cloudProvider.rawValue, forKey: "cloud_provider") }
    }
    @Published var lastMaskingStats: MaskingStats?
    @Published var privacySteps: [String] = []
    @Published var paranoiaLogLines: [ParanoiaEngine.ParanoiaLogLine] = []  // Paranoia Mode live log

    // ── Model configuration (all persisted via UserDefaults) ──
    @Published var temperature: Double = 0.1 {
        didSet { UserDefaults.standard.set(temperature, forKey: "model_temperature") }
    }
    @Published var maxTokensOllama: Int = 2048 {
        didSet { UserDefaults.standard.set(maxTokensOllama, forKey: "max_tokens_ollama") }
    }
    @Published var maxTokensMLX: Int = 4096 {
        didSet { UserDefaults.standard.set(maxTokensMLX, forKey: "max_tokens_mlx") }
    }
    /// 0 = auto (use ModelTier.compressThreshold based on detected model
    /// size); any positive value overrides how much conversation history
    /// (chars) stays uncompressed before CortexEngine.compressIfNeeded
    /// kicks in. See AgentLoop.swift's `compressThreshold` computation.
    @Published var contextWindowOverride: Int = 0 {
        didSet { UserDefaults.standard.set(contextWindowOverride, forKey: "context_window_override") }
    }

    /// The model-name string used for tier/budget lookups (e.g.
    /// `ContextBudgetManager.budget(for:)`), extracted from whichever
    /// `ModelStatus` case is currently active. `nil` when no model is loaded.
    var activeModelName: String? {
        switch modelStatus {
        case .ready(let name): return name
        case .ollamaReady(let model): return model
        case .anthropicReady(let model, _): return model
        case .mlxReady(let model): return model
        case .mlxDownloading(let model): return model
        case .bitnetReady(let model): return model
        case .jcrossReady(let model): return model
        case .none, .connecting, .downloading, .error: return nil
        }
    }
    @Published var ollamaEndpoint: String = "http://localhost:11434" {
        didSet { UserDefaults.standard.set(ollamaEndpoint, forKey: "ollama_endpoint") }
    }
    @Published var systemPrompt: String = "You are Verantyx, an expert AI coding assistant running on Apple Silicon. Be concise and precise. Prefer code over prose." {
        didSet { UserDefaults.standard.set(systemPrompt, forKey: "system_prompt") }
    }
    @Published var streamingEnabled: Bool = true {
        didSet { UserDefaults.standard.set(streamingEnabled, forKey: "streaming_enabled") }
    }

    // ── Tool toggles ──
    @Published var toolBrowserEnabled: Bool = true {
        didSet { UserDefaults.standard.set(toolBrowserEnabled, forKey: "tool_browser") }
    }
    @Published var toolWebSearchEnabled: Bool = true {
        didSet { UserDefaults.standard.set(toolWebSearchEnabled, forKey: "tool_web_search") }
    }
    @Published var toolTerminalEnabled: Bool = true {
        didSet { UserDefaults.standard.set(toolTerminalEnabled, forKey: "tool_terminal") }
    }
    @Published var toolDiffEnabled: Bool = true {
        didSet { UserDefaults.standard.set(toolDiffEnabled, forKey: "tool_diff") }
    }
    @Published var toolJCrossEnabled: Bool = true {
        didSet { UserDefaults.standard.set(toolJCrossEnabled, forKey: "tool_jcross") }
    }

    // ── Privacy Gateway: Gemma semantic masking ──
    /// Gemmaによるセマンティックマスキング (Phase 2) の有効/無効
    /// OFF時は Phase 1 正規表現マスキングのみ使用（高速、Gemma不要）
    @Published var gemmaSemanticMaskingEnabled: Bool = true {
        didSet { UserDefaults.standard.set(gemmaSemanticMaskingEnabled, forKey: "gemma_semantic_masking") }
    }

    // ── UI Language ──
    enum UILanguage: String, CaseIterable, Codable {
        case system  = "System"
        case english = "English"
        case japanese = "日本語"

        var localeIdentifier: String {
            switch self {
            case .system:   return Locale.current.identifier
            case .english:  return "en"
            case .japanese: return "ja"
            }
        }

        var flag: String {
            switch self {
            case .system:   return "🌐"
            case .english:  return "🇺🇸"
            case .japanese: return "🇯🇵"
            }
        }
    }

    @Published var appLanguage: UILanguage = {
        let raw = UserDefaults.standard.string(forKey: "app_language") ?? UILanguage.system.rawValue
        return UILanguage(rawValue: raw) ?? .system
    }() {
        didSet {
            UserDefaults.standard.set(appLanguage.rawValue, forKey: "app_language")
            // Keep global AppLanguage singleton in sync for NSTextView/NSMenuItem code
            let isJA: Bool
            switch appLanguage {
            case .japanese: isJA = true
            case .english:  isJA = false
            case .system:   isJA = Locale.current.language.languageCode?.identifier == "ja"
            }
            AppLanguage.shared.isJapanese = isJA
        }
    }

    // MARK: - Localized string helper
    func t(_ en: String, _ ja: String) -> String {
        switch appLanguage {
        case .japanese: return ja
        case .english:  return en
        case .system:
            return Locale.current.language.languageCode?.identifier == "ja" ? ja : en
        }
    }

    // MARK: - UI Preferences

    @Published var codeFontSize: Int = {
        let v = UserDefaults.standard.integer(forKey: "code_font_size")
        return v > 0 ? v : 12
    }() {
        didSet { UserDefaults.standard.set(codeFontSize, forKey: "code_font_size") }
    }

    @Published var notifyOnDiffApply: Bool = UserDefaults.standard.bool(forKey: "notify_diff_apply") {
        didSet { UserDefaults.standard.set(notifyOnDiffApply, forKey: "notify_diff_apply") }
    }

    @Published var notifyOnError: Bool = {
        let v = UserDefaults.standard.object(forKey: "notify_error") as? Bool
        return v ?? true
    }() {
        didSet { UserDefaults.standard.set(notifyOnError, forKey: "notify_error") }
    }

    // Manual override for the automatic per-turn Visual/Cognitive Anchor
    // images (searchForce/doubt/logic/etc, rendered by CognitiveAnchorEngine
    // and attached every turn to multimodal-classified models). Kept
    // separate from `isMultimodalModel` so turning this off doesn't change
    // multimodal *detection* -- it only stops those anchor images from being
    // attached, e.g. to A/B-test whether they're responsible for a given
    // model's degraded/garbled output without touching image attachments
    // (photo.badge.plus) or the model classification itself.
    @Published var autoVisualAnchorImagesEnabled: Bool = {
        let v = UserDefaults.standard.object(forKey: "auto_visual_anchor_images_enabled") as? Bool
        return v ?? true
    }() {
        didSet { UserDefaults.standard.set(autoVisualAnchorImagesEnabled, forKey: "auto_visual_anchor_images_enabled") }
    }

    // ── Multimodal capability detection ──
    var isMultimodalModel: Bool {
        switch modelStatus {
        case .ollamaReady(let m):
            let mm = m.lowercased()
            return mm.contains("llava") || mm.contains("vision")
                || (mm.contains("qwen") && mm.contains("vl"))
                || mm.contains("qwen3") || mm.contains("qwen-vl")
                || mm.contains("minicpm") || mm.contains("moondream")
                || mm.contains("bakllava") || mm.contains("cogvlm")
                || mm.contains("ornith")
                || (mm.contains("gemma") && !mm.contains("gemma2") && !mm.contains("gemma-2"))
        case .mlxReady(let m):
            let mm = m.lowercased()
            return mm.contains("vision") || mm.contains("gemma-4")
                || mm.contains("qwen-vl") || mm.contains("llava") || mm.contains("llm3.2")
                || mm.contains("ornith")
        default: return false
        }
    }

    enum ModelStatus: Equatable {
        case none
        case connecting
        case downloading(progress: Double)
        case ready(name: String)
        case ollamaReady(model: String)
        case anthropicReady(model: String, maskedKey: String)  // Anthropic API
        case mlxReady(model: String)          // MLX server running at localhost:8080
        case mlxDownloading(model: String)    // mlx_lm download in progress
        case bitnetReady(model: String)       // BitNet local subprocess
        case jcrossReady(model: String)       // JGEN/RustBrain in-process engine (JCrossEngine)
        case error(String)
    }

    // Workspace manager (lazy)
    private let workspace = WorkspaceManager()
    let agent = AgentEngine()
    let terminal = TerminalRunner()
    let cortex = CortexEngine()
    let sessions = SessionStore()

    // MARK: - Dirty state (close/quit guard)

    /// True when there is active work that should be saved before quitting.
    var isDirty: Bool {
        (workspaceURL != nil && (pendingDiff != nil || messages.count > 2))
        || isGenerating
    }

    // MARK: - Self-Admin API
    // AI agent calls this to modify IDE settings directly from chat instructions.
    // AllowList design: only known keys are accepted; unknown keys warn but don't crash.
    @discardableResult
    func applySetting(key: String, value: String) -> String {
        switch key {
        case "system_prompt":
            systemPrompt = value
        case "operation_mode":
            // Previously this ignored `value` and always forced .gatekeeper,
            // so the setting was unsettable. Honor the requested mode and
            // report invalid input instead of silently picking one.
            guard let mode = OperationMode(rawValue: value) else {
                let valid = OperationMode.allCases.map(\.rawValue).joined(separator: ", ")
                return "⚠️ Invalid operation_mode: '\(value)' (expected: \(valid))"
            }
            operationMode = mode
        case "temperature":
            if let d = Double(value) { temperature = max(0.0, min(2.0, d)) }
            else { return "⚠️ Invalid temperature: \(value) (expected 0.0–2.0)" }
        case "max_tokens_ollama":
            if let i = Int(value) { maxTokensOllama = max(64, min(32768, i)) }
            else { return "⚠️ Invalid max_tokens_ollama: \(value)" }
        case "max_tokens_mlx":
            if let i = Int(value) { maxTokensMLX = max(64, min(32768, i)) }
            else { return "⚠️ Invalid max_tokens_mlx: \(value)" }
        case "ollama_endpoint":
            ollamaEndpoint = value
        case "inference_mode":
            if let m = InferenceMode(rawValue: value) { inferenceMode = m }
            else { return "⚠️ Unknown inference_mode: \(value). Valid: localOnly, cloudDirect, privacyShield, paranoiaMode" }
        case "agent_loop_enabled":
            agentLoopEnabled = (value == "true" || value == "1" || value == "yes")
        case "streaming_enabled":
            streamingEnabled = (value == "true" || value == "1" || value == "yes")
        case "anthropic_api_key":
            anthropicApiKey = value
        case "active_ollama_model":
            activeOllamaModel = value
            modelStatus = .ollamaReady(model: value)
        case "active_auditor_model":
            activeAuditorModel = value
        case "is_auditor_enabled":
            isAuditorEnabled = (value == "true" || value == "1" || value == "yes")
        case "context_window_override":
            guard let n = Int(value) else { return "⚠️ context_window_override expects an integer (0 = auto)" }
            contextWindowOverride = n
        case "active_mlx_model":
            activeMlxModel = value
        case "council_execution_model":
            CouncilSettingsStore.shared.executionModel = value
        case "council_escalation_model":
            CouncilSettingsStore.shared.config.escalationModel = value
        case "council_use_for_chat":
            CouncilSettingsStore.shared.useCouncilForChat = (value == "true" || value == "1" || value == "yes")
        default:
            return "⚠️ Unknown setting key: '\(key)'. Valid keys: system_prompt, operation_mode, temperature, max_tokens_ollama, max_tokens_mlx, ollama_endpoint, inference_mode, agent_loop_enabled, streaming_enabled, anthropic_api_key, active_ollama_model, active_auditor_model, is_auditor_enabled, context_window_override, active_mlx_model, council_execution_model, council_escalation_model, council_use_for_chat"
        }
        return "✓ \(key) = \(value.prefix(80))"
    }

    // MLX state
    @Published var activeMlxModel: String = {
        UserDefaults.standard.string(forKey: "active_mlx_model")
            ?? "mlx-community/gemma-4-26b-a4b-it-4bit"
    }() {
        didSet { UserDefaults.standard.set(activeMlxModel, forKey: "active_mlx_model") }
    }
    @Published var mlxServerLogs: [String] = []

    // Agent loop
    @Published var agentLoopEnabled: Bool = true {
        didSet { UserDefaults.standard.set(agentLoopEnabled, forKey: "agent_loop_enabled") }
    }

    // ── VX-Loop: Chat session-level persistent ID for VXTimeline ─────────
    // nano/small モデル使用時、全ターンで同一IDを共有することで
    // VXTimeline内の履歴記録を次のターンで参照できる。
    // newChatSession() でリセットされる。
    var vxChatSessionId: String = String(UUID().uuidString.prefix(8))

    // nano/small モデル選択時に AI Priority を強制するフラグ
    @Published var isNanoSmallModelActive: Bool = false
    
    // Tracking spotlight generation
    var currentGenerationIsSpotlight: Bool = false

    // Talkie-1930 Mode (Blind Commander)
    @Published var isTalkieMode: Bool = false {
        didSet {
            if isTalkieMode {
                let talkieMLX = "kofdai/talkie-1930-13b-it-mlx-8bit"
                if activeMlxModel != talkieMLX {
                    activeMlxModel = talkieMLX
                    loadMLXModel(model: talkieMLX)
                } else if case .mlxReady = modelStatus {
                    // Already ready
                } else {
                    loadMLXModel(model: talkieMLX)
                }
            }
        }
    }

    // MARK: - Gatekeeper Model Sync

    func getOllamaModel() -> String {
        return GatekeeperPipelineState.shared.config.intentOllamaModel
    }

    func setOllamaModel(_ model: String) {
        var config = GatekeeperPipelineState.shared.config
        config.intentOllamaModel = model
        GatekeeperPipelineState.shared.config = config
        config.save()
        
        if activeOllamaModel != model {
            activeOllamaModel = model
        }
    }

    // Active Gatekeeper Local Model
    @Published var activeOllamaModel: String = {
        GatekeeperPipelineState.shared.config.intentOllamaModel.isEmpty ? "gemma4:26b" : GatekeeperPipelineState.shared.config.intentOllamaModel
    }() {
        didSet {
            var config = GatekeeperPipelineState.shared.config
            config.intentOllamaModel = activeOllamaModel
            GatekeeperPipelineState.shared.config = config
            config.save()
        }
    }

    // MARK: - Workspace actions

    func openWorkspace() {
        guard let url = workspace.pickFolder() else { return }
        workspaceURL = url
        workspaceFiles = []
        selectedFile = nil
        selectedFileContent = ""
        terminal.workingDirectory = url
        // 再起動後も最後のワークスペースを復元できるよう保存
        UserDefaults.standard.set(url.path, forKey: "last_workspace_path")
        addSystemMessage("📂 Workspace: \(url.lastPathComponent)")
        SelfEvolutionEngine.shared.setWorkspaceHint(url)
        GatekeeperModeState.shared.configure(workspaceURL: url)
        refreshFiles()
        // ── ワークスペース追加時に L2.5 地図を自動生成 ───────────────────
        // (UI側で確認ダイアログを出すため、自動実行は削除)
        }

    /// Progressive directory scan — yields partial results as they arrive.
    /// First batch appears in ~200ms for most workspaces. Tree shows before scan completes.
    func refreshFiles() {
        guard let root = workspaceURL else { return }

        // Broader extension set so all relevant source/config files appear
        let exts: Set<String> = [
            // Apple
            "swift", "m", "mm", "xib", "storyboard", "plist",
            // Python
            "py", "pyw", "pyi", "ipynb",
            // JS / TS / Web
            "ts", "tsx", "js", "jsx", "mjs", "cjs", "vue", "svelte",
            "html", "htm", "css", "scss", "sass", "less",
            // Rust
            "rs", "toml",
            // Go
            "go",
            // JVM
            "kt", "kts", "java", "scala", "gradle",
            // C family
            "c", "cpp", "cc", "cxx", "h", "hpp",
            // Ruby / PHP
            "rb", "rake", "gemspec", "php",
            // Shell
            "sh", "bash", "zsh", "fish", "ps1",
            // Docs / Config
            "md", "mdx", "markdown", "txt", "rst",
            "json", "jsonc", "yaml", "yml",
            "xml", "csv", "sql", "graphql",
            "env", "lock",
            // Bare filenames (extension-less) — handled by name match in _scanDirectory
            "makefile", "dockerfile", "gitignore", "gitattributes",
            "procfile", "rakefile",
        ]

        // Use non-detached Task so MainActor isolation is inherited and `workspace`
        // (a @MainActor property) can be accessed safely. The async for-await iterator
        // yields control between snapshots so UI rendering is not blocked.
        Task(priority: .userInitiated) { [weak self] in
            guard let self else { return }
            for await snapshot in self.workspace.scanStreaming(in: root, extensions: exts) {
                self.workspaceFiles = snapshot
            }
        }
    }


    /// Helper to safely read and truncate file content for UI preview
    nonisolated private func safePreview(for url: URL) -> String {
        do {
            let attr = try FileManager.default.attributesOfItem(atPath: url.path)
            if let size = attr[.size] as? UInt64, size > 2_000_000 { // >2MB is too big for SwiftUI Text
                return ";;; ⚠️ File is too large to preview (\(size / 1_000_000) MB)"
            }
            let text = try String(contentsOf: url, encoding: .utf8)
            return truncatePreview(text: text)
        } catch {
            if let text = try? String(contentsOf: url, encoding: .isoLatin1) {
                return truncatePreview(text: text)
            }
            return ";;; ⚠️ Unable to read file content (binary or unknown encoding)"
        }
    }

    nonisolated private func truncatePreview(text: String) -> String {
        let maxChars = 100_000 // Safe limit for SwiftUI Text
        if text.count > maxChars {
            return String(text.prefix(maxChars)) + "\n\n... (File truncated for preview limit) ..."
        }
        return text
    }

    @Published var showGatekeeperRawCode: Bool = {
        let raw = UserDefaults.standard.string(forKey: "operation_mode") ?? OperationMode.automatic.rawValue
        let mode = OperationMode(rawValue: raw) ?? .automatic
        return mode != .gatekeeper
    }() {
        didSet {
            if let file = selectedFile { selectFile(file) }
        }
    }

    /// Instant selection — show name immediately, read content async.
    func selectFile(_ url: URL) {
        selectedFile = url          // highlight instantly (no wait)
        selectedFileContent = ""    // clear old content immediately

        // ── Gatekeeper Mode: Vault の JCross IR を表示 ────────────────
        // 有効な場合は実コードの代わりに JCross 変換済みコンテンツを表示する。
        // Vault 未登録ファイルは実コード + 警告バナーで表示。
        let gatekeeperEnabled = GatekeeperModeState.shared.isEnabled
        if gatekeeperEnabled && !showGatekeeperRawCode {
            let relativePath: String
            if let wsPath = workspaceURL?.path,
               url.path.hasPrefix(wsPath + "/") {
                relativePath = String(url.path.dropFirst(wsPath.count + 1))
            } else {
                relativePath = url.lastPathComponent
            }

            Task.detached { [weak self] in
                guard let self else { return }
                let vault = await MainActor.run { GatekeeperModeState.shared.vault }
                let result = await MainActor.run { vault.read(relativePath: relativePath) }

                await MainActor.run {
                    guard self.selectedFile == url else { return }
                    if let vaultResult = result {
                        // JCross IR を表示（先頭にバナーを付ける）
                        let banner = """
                        ;;; 🛡️ GATEKEEPER MODE — JCross IR View
                        ;;; Real identifiers have been replaced with node IDs.
                        ;;; Schema: \(vaultResult.entry.schemaSessionID.prefix(12))
                        ;;; Nodes: \(vaultResult.entry.nodeCount) | Secrets redacted: \(vaultResult.entry.secretCount)
                        ;;; Source: \(relativePath)
                        ;;; 
                        ;;; (To view raw code, toggle "Show Raw Code" above)
                        ;;;
                        """
                        self.selectedFileContent = banner + "\n" + self.truncatePreview(text: vaultResult.jcrossContent)
                    } else {
                        // Vault 未変換: 実コードを読み込み + 警告バナー
                        let raw = self.safePreview(for: url)
                        let warning = """
                        ;;; ⚠️ GATEKEEPER MODE — このファイルはまだ JCross 変換されていません
                        ;;; [Gatekeeper 設定] → [一括変換を開始] でVaultを更新してください
                        ;;; ※ 以下は実コードです。このビューは一時的なものです
                        ;;;
                        
                        """
                        self.selectedFileContent = warning + raw
                    }
                }
            }
            return
        }

        // ── 通常モード: 実ファイルを読み込む ─────────────────────────
        Task.detached { [weak self] in
            guard let self else { return }
            // Read on background thread — never blocks UI
            let content = self.safePreview(for: url)
            await MainActor.run {
                // Only update if this file is still selected
                guard self.selectedFile == url else { return }
                self.selectedFileContent = content
            }
        }
    }

    // MARK: - Session management

    /// Save the current chat to the session store.
    func saveCurrentSession() {
        if sessions.activeSessionId == nil, messages.count > 1 {
            _ = sessions.newSession(messages: messages, workspacePath: workspaceURL?.path)
        } else {
            sessions.updateActiveSession(messages: messages, workspacePath: workspaceURL?.path)
        }
    }

    /// Start a fresh chat  (old session saved automatically).
    func newChatSession() {
        // 新規セッション開始時は常にフォルダ選択ダイアログを開く処理を削除（FileTreeViewのボタンに一本化）

        // Before clearing, archive the current session progressively
        if let currentId = sessions.activeSessionId,
           let current = sessions.sessions.first(where: { $0.id == currentId }),
           !current.messages.filter({ $0.role != .system }).isEmpty {
            SessionMemoryArchiver.shared.archiveProgressively(session: current)
        }

        saveCurrentSession()
        messages.removeAll()
        pendingDiff = nil
        showDiff    = false
        autoApproveDiffs = false
        // 新セッション開始時に VXTimeline ID をリセット
        vxChatSessionId = String(UUID().uuidString.prefix(8))
        let newSession = sessions.newSession(messages: [], workspacePath: workspaceURL?.path)

        // ── Cross-session memory injection ───────────────────────────
        // Inject past sessions' JCross memory at the correct layer depth.
        let currentId = newSession.id
        let layer = sessions.activeSession?.activeLayer ?? .l2
        Task {
            let useNanoStore = self.isNanoSmallModelActive
            let injection = SessionMemoryArchiver.shared.buildZonePriorityInjection(
                layer: layer,
                useNanoStore: useNanoStore
            )
            if !injection.isEmpty {
                await MainActor.run {
                    self.messages.insert(
                        ChatMessage(role: .system, content: injection),
                        at: 0
                    )
                    self.addSystemMessage(self.t("🧠 Injected memory from past session (\(layer.rawValue) layer)", "🧠 過去セッションの記憶を注入しました (\(layer.rawValue) レイヤー)"))
                }
            }
        }
    }

    /// Restore a past session by its ID (loads messages + memory injection).
    func restoreSession(_ sessionId: UUID) {
        guard let session = sessions.sessions.first(where: { $0.id == sessionId }) else { return }

        // ── Cancel any in-flight inference from the previous session ────
        // This ensures: (a) isGenerating is reset, (b) no stale onToken
        // callbacks write into the newly-restored messages array.
        inferenceTask?.cancel()
        inferenceTask = nil
        isGenerating  = false
        // ⚠️ MUST nil streamingMsgId BEFORE replacing messages.
        // If it remains non-nil, the next .streamToken will search for the
        // old UUID in the restored session's messages, fail to find it,
        // and create a NEW orphan bubble instead of tracking correctly.
        self.streamingMsgId = nil

        saveCurrentSession()
        sessions.selectSession(sessionId)

        // Restore messages — filter out any empty assistant bubbles that were
        // saved mid-stream before a previous fix (corrupt streaming artifacts).
        messages    = session.messages.filter { msg in
            !(msg.role == .assistant && msg.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        pendingDiff = nil
        showDiff    = false
        if let path = session.workspacePath {
            let url = URL(fileURLWithPath: path)
            if workspaceURL != url {
                workspaceURL = url
                terminal.workingDirectory = url
                refreshFiles()
            }
        }
        // Inject JCross memory for this session in background
        Task {
            let injection = await sessions.buildMemoryInjection(for: sessionId)
            if !injection.isEmpty {
                await MainActor.run {
                    self.messages.insert(ChatMessage(role: .system, content: injection), at: 0)
                }
            }
        }
        addSystemMessage(self.t("📂 Restored session '\(session.title)'", "📂 セッション「\(session.title)」を復元しました"))
        activeChatTab = 0
    }

    // MARK: - Agent actions

    func sendMessage(with overrideText: String? = nil, forceBypassGatekeeper: Bool = false, isSpotlight: Bool = false) {
        let text = (overrideText ?? inputText).trimmingCharacters(in: .whitespacesAndNewlines)
        let hasAttachments = !attachedImages.isEmpty || !attachedFiles.isEmpty
        guard !text.isEmpty || hasAttachments, !isGenerating else { return }
        inputText = ""

        // Build the user message (with attachment summary if present)
        var displayContent = text
        if !attachedImages.isEmpty {
            displayContent += attachedImages.count == 1
                ? "\n📎 [Image: \(attachedImages[0].name)]"
                : "\n📎 [\(attachedImages.count) images attached]"
        }
        if !attachedFiles.isEmpty {
            for f in attachedFiles { displayContent += "\n📎 [File: \(f.lastPathComponent)]" }
        }

        let snapshotImages = attachedImages
        let snapshotFiles  = attachedFiles
        attachedImages.removeAll()
        attachedFiles.removeAll()

        messages.append(ChatMessage(role: .user, content: displayContent, isSpotlight: isSpotlight))
        currentGenerationIsSpotlight = isSpotlight
        isGenerating = true

        // Auto-create session if there isn't one yet
        if sessions.activeSessionId == nil {
            _ = sessions.newSession(messages: messages, workspacePath: workspaceURL?.path)
        }

        inferenceTask = Task {
            // ── BENCHMARK INTEGRATION ────────────────────────────────────────
            if text.starts(with: "/benchmark") {
                let parts = text.split(separator: " ")
                
                if parts.count >= 2 && parts[1] == "status" {
                    await MainActor.run { self.addSystemMessage("📊 取得中: Benchmark Status...") }
                    let result = await MCPEngine.shared.callTool(
                        serverName: "verantyx-compiler",
                        toolName: "benchmark_status",
                        arguments: [:]
                    )
                    await MainActor.run {
                        self.isGenerating = false
                        self.addSystemMessage("✅ Benchmark Complete")
                        self.messages.append(ChatMessage(role: .assistant, content: "📈 Benchmark Status:\n\n\(result)", isSpotlight: self.currentGenerationIsSpotlight))
                        self.saveCurrentSession()
                    }
                    return
                }
                
                await MainActor.run { self.addSystemMessage("🚀 起動中: LongMemEval Benchmark...") }
                
                // Parse arguments like "/benchmark batch=5 total=10"
                var args: [String: Any] = [:]
                for part in parts.dropFirst() {
                    let kv = part.split(separator: "=")
                    if kv.count == 2, let v = Int(String(kv[1])) {
                        args[String(kv[0])] = v
                    }
                }
                
                let result = await MCPEngine.shared.callTool(
                    serverName: "verantyx-compiler",
                    toolName: "solve_all",
                    arguments: args
                )
                
                await MainActor.run {
                    self.isGenerating = false
                    self.addSystemMessage("✅ Benchmark Complete")
                    self.messages.append(ChatMessage(role: .assistant, content: "📈 Benchmark Result:\n\n\(result)", isSpotlight: self.currentGenerationIsSpotlight))
                    self.saveCurrentSession()
                }
                return
            }

            // ── PIPELINE INTENT DETECTION ───────────────────────────────────
            // NOTE: Gatekeeper Mode ON の場合は CommanderOrchestrator が全処理を担うため
            //       ここでの旧フロー (BitNetCommanderLoop) ルーティングは完全に廃止しました。

            // ── SYSTEM STATUS INJECTION ──────────────────────────────────────
            // 状態確認系の質問 or バックグラウンドプロセスが動いているとき、
            // AI の systemPrompt にリアルタイムの状態ブロックを注入する。
            // → AI は「L2.5 が今 45% 完了」などを自律的に答えられる。
            let statusBlock = await MainActor.run {
                SystemStatusProvider.shared.systemStatusBlock()
            }
            if let status = statusBlock {
                await MainActor.run { self.systemPrompt += "\n\n" + status }
                // 返答後にステータスブロックを除去 (永続汚染しない)
                defer {
                    Task { @MainActor in
                        if let range = self.systemPrompt.range(of: "\n\n[SYSTEM STATUS") {
                            self.systemPrompt = String(self.systemPrompt[..<range.lowerBound])
                        }
                    }
                }
            }
            // 状態確認系の質問なら fullStatusReport を先にチャットに挿入
            if SystemStatusProvider.isStatusQuery(text) {
                let report = await MainActor.run {
                    SystemStatusProvider.shared.fullStatusReport()
                }
                await MainActor.run {
                    self.addSystemMessage(AppLanguage.shared.t("📊 System state snapshot:\n\(report)", "📊 システム状態スナップショット:\n\(report)"))
                }
            }
            // ── END STATUS INJECTION ─────────────────────────────────────────

            // Compress context if needed (Cortex anti-Alzheimer's)
            let trimmed = cortex.compressIfNeeded(messages: messages)
            if trimmed.count < messages.count {
                await MainActor.run { self.messages = trimmed }
            }

            // Route: UI-based Router
            let isGatekeeperEnabled = forceBypassGatekeeper ? false : await MainActor.run(body: { GatekeeperModeState.shared.isEnabled })
            // UI determines task type: IDE input -> Programming, Spotlight -> General
            let isProgrammingTask = !isSpotlight

            if isGatekeeperEnabled && isProgrammingTask {
                // Gatekeeper Mode → 新フロー (6軸IR → GraphPatch JSON → Vault復元)
                await GatekeeperChatBridge.shared.run(instruction: text, images: snapshotImages as! [String], appState: self)
            } else if isGatekeeperEnabled && !isProgrammingTask {
                // General Task during Gatekeeper Mode (Spotlight)
                await MainActor.run {
                    let msg = self.t("🧭 Spotlight Agent: Routing general task to \(self.nonCodingTaskEngine.rawValue)",
                                     "🧭 Spotlight Agent: 汎用タスクとして \(self.nonCodingTaskEngine.rawValue) にルーティングします")
                    self.addSystemMessage(msg)
                }
                
                let engine = await MainActor.run { self.nonCodingTaskEngine }
                if engine == .cloudDirect {
                    // Bypass Gatekeeper, send to Cloud Model
                    await runHybrid(instruction: text)
                } else {
                    // Local Agent
                    let history = Array(self.messages.dropLast())
                    await runAgentLoop(instruction: text,
                                       images: snapshotImages,
                                       files: snapshotFiles,
                                       previousMessages: history)
                }
            } else if inferenceMode == .cloudDirect || inferenceMode == .privacyShield || inferenceMode == .paranoiaMode {
                await runHybrid(instruction: text)
            } else if CouncilSettingsStore.shared.useVeraHarnessForChat {
                // Milestone N: Vera-alpha's own Agent.run() drives the turn
                // over HTTP+SSE (vera_server.py) instead of this app's
                // AgentLoop/CouncilOrchestrator -- Vera is the controller
                // here, not a tool this app calls.
                await runVeraHarness(instruction: text, files: snapshotFiles)
            } else if agentLoopEnabled {
                // 4-layer path: explicit `/council <question>`, or every turn
                // when the JGEN options popover has "use the council for
                // normal chat" on. Falls back to the plain loop by itself if
                // no JGEN model is loaded.
                let trimmed = text.trimmingCharacters(in: .whitespaces)
                let isCouncilCommand = trimmed.lowercased().hasPrefix("/council")
                let question = isCouncilCommand
                    ? String(trimmed.dropFirst("/council".count)).trimmingCharacters(in: .whitespaces)
                    : text
                let useLayered = isCouncilCommand || CouncilSettingsStore.shared.useCouncilForChat

                let history = Array(self.messages.dropLast())
                await runAgentLoop(instruction: question.isEmpty ? text : question,
                                   images: snapshotImages,
                                   files: snapshotFiles,
                                   previousMessages: history,
                                   useLayered: useLayered)
            } else {
                await runSinglePass(instruction: text,
                                    images: snapshotImages,
                                    files: snapshotFiles)
            }

            // Persist session after each exchange
            sessions.updateActiveSession(messages: messages, workspacePath: workspaceURL?.path)
        }
    }

    // Pipeline Intent Classifier removed (Routing is now strictly UI-based)

    // (sendMessage本体のクロージングブレースはここに続く)
    // MARK: - Cancel generation
    func cancelGeneration() {
        inferenceTask?.cancel()
        inferenceTask = nil
        isGenerating = false
        addSystemMessage(self.t("⏹ Inference aborted", "⏹ 推論を中断しました"))

        // ── [NEW] INTERRUPT SNAPSHOT ──
        // Capture incomplete state and move origin task to far/
        let currentMessages = self.messages
        let sid = self.vxChatSessionId
        Task.detached {
            let userIntent = currentMessages.last(where: { $0.role == .user })?.content ?? "Unknown task"
            let l2Lines = [
                "OP.FACT(\"status\", \"incomplete_suspended\")",
                "OP.FACT(\"last_intent\", \"\(String(userIntent.prefix(200)).replacingOccurrences(of: "\n", with: " "))\")",
                "OP.FACT(\"origin_task_id\", \"\(sid)\")"
            ]
            let ts = Int(Date().timeIntervalSince1970)
            SessionMemoryArchiver.shared.archiveConversationChunk(
                chunkId: "INTERRUPT_\(sid)_\(ts)",
                taskTitle: "Suspended Task Snapshot",
                l1: "[中断] 未完了スナップショット",
                l2: l2Lines.joined(separator: "\n"),
                l3: ""
            )
            // Move the original PROG/CONV chunks to far/
            SessionMemoryArchiver.shared.moveToFarZone(shortId: sid)
        }
    }

    // MARK: - Hybrid Engine (Privacy Shield / Cloud Direct)

    private func runHybrid(instruction: String) async {
        let context = selectedFileContent.isEmpty ? nil : selectedFileContent
        let contextFile = selectedFile
        await MainActor.run { self.privacySteps = [] }

        let snap_mode     = inferenceMode
        let snap_provider = cloudProvider
        let snap_model    = activeOllamaModel
        let snap_status   = modelStatus

        // ── Privacy Shield / Paranoia Mode: PrivacyGateway (Phase 1 + Phase 2 + JCross) ──
        // cloudDirect: HybridEngine (マスキングなし、直接送信)
        // paranoiaMode: PrivacyGateway → ParanoiaEngine (AST-surgical phase 3)
        if (snap_mode == .privacyShield || snap_mode == .paranoiaMode),
           let fileContent = context, let fileName = contextFile?.lastPathComponent {

            let snap_gemma = gemmaSemanticMaskingEnabled

            let gatewayResult = await PrivacyGateway.shared.processWithGateway(
                instruction: instruction,
                fileContent: fileContent,
                fileName: fileName,
                fileURL: contextFile,
                modelStatus: snap_status,
                activeModel: snap_model,
                provider: snap_provider,
                cortex: cortex,
                useGemmaSemanticMasking: snap_gemma
            ) { [weak self] step in
                guard let self else { return }
                await MainActor.run {
                    self.privacySteps.append(step)
                    self.messages.append(ChatMessage(role: .system, content: step))
                }
            }

            await MainActor.run {
                isGenerating = false
                // GatewayStats → MaskingStats 変換 (UI表示用)
                lastMaskingStats = MaskingStats(
                    functions: gatewayResult.maskingStats.phase1RegexMasked,
                    classes:   0,
                    variables: gatewayResult.maskingStats.phase2SemanticMasked,
                    strings:   gatewayResult.maskingStats.secretsBlocked,
                    paths:     gatewayResult.maskingStats.pathsProtected
                )
                messages.append(ChatMessage(role: .assistant, content: gatewayResult.explanation, isSpotlight: currentGenerationIsSpotlight))
                if let code = gatewayResult.restoredCode, !code.isEmpty, let fileURL = contextFile {
                    let diff = FileDiff(
                        fileURL: fileURL,
                        originalContent: selectedFileContent,
                        modifiedContent: code,
                        hunks: DiffEngine.compute(original: selectedFileContent, modified: code)
                    )
                    pendingDiff = diff; showDiff = true
                }
            }
            return
        }

        // ── Cloud Direct (or no file selected in Shield mode): HybridEngine ──
        let result = await HybridEngine.shared.process(
            instruction: instruction,
            fileContent: context,
            fileName: contextFile?.lastPathComponent,
            fileURL: contextFile,
            mode: snap_mode,
            modelStatus: snap_status,
            activeOllamaModel: snap_model,
            cloudProvider: snap_provider,
            cortex: cortex
        ) { [weak self] step in
            guard let self else { return }
            await MainActor.run {
                self.privacySteps.append(step)
                self.messages.append(ChatMessage(role: .system, content: step))
            }
        }

        await MainActor.run {
            isGenerating = false
            lastMaskingStats = result.maskingStats
            let rawContent = result.explanation
            // Strip artifact tags from chat display
            let displayContent = ArtifactParser.stripArtifactTags(from: rawContent)
            messages.append(ChatMessage(role: .assistant, content: displayContent, isSpotlight: currentGenerationIsSpotlight))

            // Artifact detection
            if let artifact = ArtifactParser.extract(from: rawContent) {
                ingestArtifact(artifact)
            }

            if let code = result.modifiedCode, !code.isEmpty, let fileURL = contextFile {
                let diff = FileDiff(
                    fileURL: fileURL,
                    originalContent: selectedFileContent,
                    modifiedContent: code,
                    hunks: DiffEngine.compute(original: selectedFileContent, modified: code)
                )
                pendingDiff = diff
                showDiff = true
            }
        }
    }

    /// Apply a diff immediately (AI Priority mode — no confirmation).
    func autoApplyDiff(_ diff: FileDiff) {
        do {
            try diff.modifiedContent.write(to: diff.fileURL, atomically: true, encoding: .utf8)
            selectedFileContent = diff.modifiedContent
            addSystemMessage(self.t("⚡ [AI Priority] Auto-applied diff: \(diff.fileURL.lastPathComponent)", "⚡ [AI Priority] 差分を自動適用: \(diff.fileURL.lastPathComponent)"))
        } catch {
            addSystemMessage(self.t("❌ Auto-apply failed: \(error.localizedDescription)", "❌ 自動適用失敗: \(error.localizedDescription)"))
        }
        pendingDiff = nil
        showDiff = false
    }

    /// Save artifact and show panel.
    func ingestArtifact(_ artifact: Artifact) {
        currentArtifact = artifact
        artifactHistory.insert(artifact, at: 0)
        showArtifactPanel = true
    }

    // MARK: - Agent Loop (multi-turn, scaffolding)

    /// Milestone N: hands the turn to Vera-alpha's own Agent.run() ReAct
    /// loop over HTTP+SSE (see VeraAgentClient.swift / vera_server.py).
    /// Deliberately minimal compared to runAgentLoop's LoopEvent handler --
    /// Vera's on_step events are its own JSON shapes (action/observation),
    /// not this app's `LoopEvent`, so this renders them as system-message
    /// progress lines rather than trying to unify the two event models.
    private func runVeraHarness(instruction: String, files: [URL] = []) async {
        isGenerating = true
        defer { isGenerating = false }

        // Real bug found live: the 📎 attachment chip in the chat input
        // (`attachedFiles`) was silently dropped on this path -- unlike
        // `runAgentLoop`/`runHybrid`, this function never took a `files`
        // parameter at all, so a user who attached a folder and just said
        // "analyze this" got "which file did you mean?" back from Vera,
        // even though something WAS attached. Vera's own tools
        // (list_dir/read_file) expect to actively explore a path, not
        // receive pre-loaded content, so the fix is the same thing the
        // user had to do manually to work around it: put the attached
        // path(s) directly into the task text Vera actually receives.
        var instruction = instruction
        if !files.isEmpty {
            let pathList = files.map { $0.path }.joined(separator: "\n")
            instruction += "\n\n" + t("Attached path(s):", "添付されたパス:") + "\n" + pathList
        }

        let mode = CouncilSettingsStore.shared.cognitionMode
        if mode != .normal {
            // Milestone O: required warning banner -- shown every time a
            // non-normal mode is active, not just once on toggle, so it
            // can't scroll out of sight and be forgotten mid-session.
            addSystemMessage(t(
                "⚠️ Experimental cognition is enabled.\nVera may: inspect additional local files · create persistent knowledge-gap nodes · run read-only analysis tools · propose new facts and skills.\nVera will not: modify project files without approval · access unapproved sources · treat acquired knowledge as trusted without verification.",
                "⚠️ 実験的な認知モードが有効です。\nVeraは: 追加のローカルファイルを調べる・永続的な知識ギャップノードを作成する・読み取り専用の解析ツールを実行する・新しい事実やスキルを提案する、ことがあります。\nVeraは: 承認なしにプロジェクトファイルを変更する・未承認の情報源へアクセスする・検証なしに取得した知識を信頼済みとして扱う、ことはありません。"
            ))
        }
        addSystemMessage(t("🧭 Vera harness: taking over this turn…", "🧭 Veraハーネス: このターンを引き継ぎます…"))

        await VeraAgentClient.shared.ensureServerRunning()
        // Vera's planner LLM step needs a real Ollama model name -- without
        // this, vera_server.py falls back to its own (usually unset)
        // default_model, sends an empty model string to Ollama's
        // /api/generate, and gets back exactly the 404 this app's own
        // testing surfaced. The IDE's already-selected chat model is the
        // right default (not a new setting the user has to duplicate).
        let harnessModel = activeOllamaModel
        do {
            let result = try await VeraAgentClient.shared.runAgent(
                task: instruction, model: harnessModel, cognitionMode: mode.rawValue
            ) { [weak self] event in
                guard let self else { return }
                Task { @MainActor in
                    switch event.source {
                    case "react_step":
                        if let action = event.raw["action"] as? [String: Any],
                           let tool = action["tool"] as? String {
                            self.addSystemMessage(self.t("🔧 Vera called: \(tool)", "🔧 Veraが呼び出し: \(tool)"))
                        }
                    case "vera_direct":
                        self.addSystemMessage(self.t("🧩 Vera answered directly (no LLM step needed)", "🧩 Veraが直接回答(LLM不要)"))
                    case "llm_error":
                        self.addSystemMessage(self.t("⚠️ Vera's LLM step failed", "⚠️ VeraのLLM手順が失敗しました"))
                    default:
                        break
                    }
                }
            }

            // `result["final"]` is NOT always a dict: agent.py's own ReAct
            // loop returns the LLM's plain-string answer verbatim when it
            // completes via `{"thought": ..., "final": "<answer>"}` (see
            // agent.py:163) -- only the vera_direct/vera_only/llm_error
            // paths wrap it in a dict. Treating it as dict-only silently
            // dropped every successful plain-text answer (confirmed via a
            // real "こんにちは" turn that Vera answered correctly but the
            // IDE rendered as "no final answer returned").
            let finalText: String
            if let text = result["final"] as? String {
                finalText = text
            } else if let final = result["final"] as? [String: Any] {
                if let text = final["text"] as? String {
                    finalText = text
                } else if let error = final["error"] as? String {
                    finalText = t("(Vera error: \(error))", "(Veraエラー: \(error))")
                } else if let data = try? JSONSerialization.data(withJSONObject: final, options: [.prettyPrinted]),
                          let json = String(data: data, encoding: .utf8) {
                    finalText = json
                } else {
                    finalText = String(describing: final)
                }
            } else {
                finalText = t("(no final answer returned)", "(最終回答が返りませんでした)")
            }
            messages.append(ChatMessage(role: .assistant, content: finalText))
        } catch {
            addSystemMessage(t("❌ Vera harness error: \(error.localizedDescription)",
                               "❌ Veraハーネスエラー: \(error.localizedDescription)"))
        }
    }

    private func runAgentLoop(instruction: String,
                              images: [AttachedImage] = [],
                              files: [URL] = [],
                              previousMessages: [ChatMessage] = [],
                              useLayered: Bool = false) async {
        let context = selectedFileContent.isEmpty ? nil : selectedFileContent
        let contextFile = selectedFile
        let snap_workspace = workspaceURL
        let snap_model = isTalkieMode ? "kofdai/talkie-1930-13b-it-mlx-8bit" : activeOllamaModel
        let snap_status = modelStatus

        // selfFixMode persists until the user explicitly toggles it off.
        // We only snapshot the current value to pass into AgentLoop.
        let snap_selfFix = selfFixMode

        // nano/small モデルはユーザーが operationMode を手動変更していても
        // 常に AI Priority ループで動作させる（VX-Loop + ConfusionDetector が必須なため）
        // ただし、Swarm Mode は特別に維持する
        let snap_operationMode: OperationMode = .gatekeeper

        // Build image context suffix so models that read text still see the filename
        var imageContext = ""
        if !images.isEmpty {
            imageContext = "\n\n[Attached images: " +
                images.map { $0.name }.joined(separator: ", ") + "]"
        }
        let fullInstruction = instruction + imageContext

        // ── Per-turn streaming message tracker ─────────────────────────
        // Reset at the start of each agent loop run so previous sessions'
        // stale UUIDs are never carried forward.
        streamingMsgId = nil

        // One handler, two runners: the layered (4-layer) path and the
        // plain agent loop both report through exactly the same event
        // stream, so chat rendering, streaming and approvals behave
        // identically either way.
        let handler: @Sendable (LoopEvent) async -> Void = { [weak self] event in
            guard let self else { return }
            await MainActor.run {
                // Any event other than streamToken represents (or precedes)
                // a turn boundary -- flush whatever's buffered first so
                // nothing is lost and downstream handling (e.g. .start
                // resetting streamingMsgId) sees the buffer already applied.
                if case .streamToken = event {} else {
                    self.flushStreamTokenBuffer()
                }
                if case .start = event {
                    ReasoningTimelineStore.shared.beginSession()
                }
                ReasoningTimelineStore.shared.ingest(event)
                switch event {
                case .start:
                    // Reset per-turn streaming ID when a new loop turn starts
                    self.streamingMsgId = nil

                case .streamToken(let token):
                    self.streamTokenBuffer += token
                    if Date().timeIntervalSince(self.lastStreamFlush) >= 0.04 {
                        self.flushStreamTokenBuffer()
                    }

                case .thinking(let t):
                    if t > 1 {
                        self.messages.append(ChatMessage(role: .system,
                            content: "<think>\n🔄 Agent loop turn \(t)…\n</think>"))
                    }

                case .aiMessage(let text):
                    if !text.isEmpty {
                        // Detect PATCH_FILE blocks → register in SelfEvolutionEngine
                        let patches = PatchFileParser.extract(from: text)
                        for (relPath, content) in patches {
                            SelfEvolutionEngine.shared.registerPatch(for: relPath, newContent: content)
                        }
                        // Detect <artifact> tags
                        if let artifact = ArtifactParser.extract(from: text) {
                            self.ingestArtifact(artifact)
                        }
                        // Strip patch/artifact markup from display text
                        let stripped = PatchFileParser.strip(
                            from: ArtifactParser.stripArtifactTags(from: text)
                        ).trimmingCharacters(in: .whitespacesAndNewlines)

                        if !stripped.isEmpty {
                            // ── UUID-based anti-duplicate guard ─────────────
                            // Find the exact streaming message by its UUID.
                            // This is safe even when tool/system messages follow
                            // the streaming message ("last role" check would fail).

                            // Snapshot processLog → thinkingLog for post-completion display
                            let logSnapshot = self.logStore.entries.map { e in
                                ChatMessage.ThinkingLogEntry(
                                    timestamp: e.timestamp,
                                    text:      e.text,
                                    kind:      e.kind.rawValue
                                )
                            }

                            if let sid = self.streamingMsgId,
                               let idx = self.messages.firstIndex(where: { $0.id == sid }) {
                                // Finalise in-place with the clean stripped version
                                self.messages[idx].content      = stripped
                                self.messages[idx].thinkingLog  = logSnapshot
                            } else {
                                // No streaming message for this turn → new bubble
                                self.messages.append(ChatMessage(role: .assistant,
                                                               content: stripped,
                                                               isSpotlight: self.currentGenerationIsSpotlight))
                            }
                            // Reset ID after finalising so next turn starts fresh
                            self.streamingMsgId = nil
                        }
                        // Notify if patches detected
                        if !patches.isEmpty {
                            self.addSystemMessage(self.t("🧬 Detected \(patches.count) patches — check Self-Evolution panel", "🧬 \(patches.count) 個のパッチを検出 — Self-Evolution パネルで確認できます"))
                        }
                    }

                case .systemLog(let text):
                    // §TL: markers are timeline-only (ReasoningTimelineStore
                    // above already consumed them) -- they'd be unreadable
                    // noise if shown as a raw chat bubble.
                    if !text.hasPrefix("§TL:") {
                        self.messages.append(ChatMessage(role: .system, content: text))
                    }

                case .toolCall(let call):
                    self.messages.append(ChatMessage(role: .system,
                        content: "<think>\n⚙️ \(call.displayLabel)\n</think>"))
                    if case .runCommand(let cmd) = call.tool {
                        Task { await self.terminal.run(cmd, in: self.workspaceURL, initiatedByAI: true) }
                    }

                case .toolResult(let call):
                    if !call.result.isEmpty {
                        let icon = call.succeeded ? "✅" : "❌"
                        self.messages.append(ChatMessage(role: .system,
                            content: "<think>\n\(icon) \(call.result.prefix(120))\n</think>"))
                    }

                case .workspaceChanged(let url):
                    self.workspaceURL = url
                    self.terminal.workingDirectory = url
                    self.refreshFiles()
                    self.addSystemMessage("📂 Workspace: \(url.lastPathComponent)")

                case .done(let msg, let ws):
                    self.isGenerating = false
                    ReasoningTimelineStore.shared.endSession()
                    if let ws = ws, self.workspaceURL == nil {
                        self.workspaceURL = ws
                        self.terminal.workingDirectory = ws
                        self.refreshFiles()
                    }
                    // ── Anti-duplicate guard ────────────────────────────────
                    // If a streaming message exists (streamingMsgId != nil),
                    // the content is already displayed — do NOT add another bubble.
                    // Only show .done text when there was no streaming at all
                    // (e.g. non-streaming model or tool-only turns with no text).
                    if !msg.isEmpty && self.streamingMsgId == nil {
                        let lastContent = self.messages.last?.content ?? ""
                        if !lastContent.hasSuffix(msg) {
                            self.messages.append(ChatMessage(role: .assistant,
                                                            content: "✅ \(msg)",
                                                            isSpotlight: self.currentGenerationIsSpotlight))
                        }
                    }
                    self.streamingMsgId = nil  // Always reset at turn end

                case .error(let err):
                    self.isGenerating = false
                    self.addSystemMessage("❌ Agent error: \(err)")
                }
            }
        }

        // Layer 1 council -> Layer 2 execution agent -> Layer 3 escalation.
        // Returns false when it can't run (e.g. no JGEN model loaded), in
        // which case we fall through to the normal loop below.
        if useLayered,
           await LayeredRunOrchestrator.run(question: fullInstruction, app: self, onProgress: handler) {
            await MainActor.run { self.isGenerating = false }
            return
        }

        await AgentLoop.shared.run(
            instruction: fullInstruction,
            contextFile: context,
            contextFileName: contextFile?.lastPathComponent,
            workspaceURL: snap_workspace,
            modelStatus: snap_status,
            activeModel: snap_model,
            cortex: cortex,
            selfFixMode: snap_selfFix,
            operationMode: snap_operationMode,
            memoryLayer: sessions.activeSession?.activeLayer ?? .l2,
            chatSessionId: vxChatSessionId,
            previousMessages: previousMessages,
            onProgress: handler
        )

        await MainActor.run { self.isGenerating = false }
    }

    // MARK: - Single pass (original behavior)

    // MARK: - Single pass (streaming)
    // Streams tokens directly into the chat bubble in real-time.
    // Tracks tok/s and emits process log entries.

    private func runSinglePass(instruction: String,
                               images: [AttachedImage] = [],
                               files: [URL] = []) async {
        let context = selectedFileContent.isEmpty ? nil : selectedFileContent
        let contextFile = selectedFile

        let snap_status = modelStatus

        // Build prompt (same as AgentEngine)
        let fileSection = context.map { content in
            let name = contextFile?.lastPathComponent ?? "file"
            return "FILE: \(name)\n```\n\(content.prefix(8000))\n```\n\n"
        } ?? ""

        let prompt = """
        You are Verantyx, an expert AI coding assistant running on Apple Silicon.

        \(fileSection)USER: \(instruction)

        ASSISTANT:
        """

        // Reset streaming state
        streamingText = ""
        tokensPerSecond = 0
        var tokenCount = 0
        let startTime = Date()
        var lastPerfLog = Date()

        logProcess("inference start [", kind: .system)
        logProcess("prompt \(prompt.count) chars", kind: .system)

        // Build the stream based on active model — use live settings
        switch snap_status {

        // ── Ollama path (unchanged) ─────────────────────────────────────────
        case .ollamaReady(let model):
            logProcess("Ollama/\(model)  temp=\(temperature)  maxTok=\(maxTokensOllama)", kind: .system)
            let msgId = UUID()
            messages.append(ChatMessage(id: msgId, role: .assistant, content: ""))
            let simpleMessages: [(role: String, content: String)] = [(role: "user", content: prompt)]
            let stream = OllamaClient.shared.streamGenerate(
                model: model,
                messages: simpleMessages,
                maxTokens: maxTokensOllama,
                temperature: temperature
            )
            do {
                // トークンをバッファして ~25fps (40ms) で UI を更新—※messagesの @Published 発火回数を 1/5 に削減
                var tokenBuffer = ""
                var lastUIFlush = Date.distantPast
                for try await event in stream {
                    guard case .token(let token) = event else { continue }
                    tokenCount += 1; totalTokensGenerated += 1
                    tokenBuffer += token
                    let now = Date()
                    let elapsed = now.timeIntervalSince(startTime)
                    // 40ms ごとにバッチフラッシュ（ポーリング連続で同一スレッドなので Date() で OK）
                    if now.timeIntervalSince(lastUIFlush) >= 0.04 {
                        if let idx = self.messages.firstIndex(where: { $0.id == msgId }) {
                            self.messages[idx].content += tokenBuffer
                        }
                        if elapsed > 0.1 { tokensPerSecond = Double(tokenCount) / elapsed }
                        tokenBuffer = ""
                        lastUIFlush = now
                    }
                    if now.timeIntervalSince(lastPerfLog) > 2 {
                        logProcess(String(format: "%.1f tok/s  │  %d tokens",
                                         Double(tokenCount)/max(elapsed,0.001), tokenCount), kind: .perf)
                        lastPerfLog = now
                    }
                }
                // 末尾バッファをフラッシュ
                if !tokenBuffer.isEmpty,
                   let idx = self.messages.firstIndex(where: { $0.id == msgId }) {
                    self.messages[idx].content += tokenBuffer
                }
            } catch { logProcess("stream error: \(error.localizedDescription)", kind: .system) }

            let elapsed1 = Date().timeIntervalSince(startTime)
            inferenceMs = Int(elapsed1 * 1000); tokensPerSecond = Double(tokenCount)/max(elapsed1,0.001)
            logProcess(String(format: "done  %.1f tok/s  │  %d tok  │  %.1fs",
                              tokensPerSecond, tokenCount, elapsed1), kind: .perf)
            let finalContent1 = messages.first(where: { $0.id == msgId })?.content ?? ""
            if agentLoopEnabled {
                let (toolCalls, _) = AgentToolParser.parse(from: finalContent1)
                let executor = AgentToolExecutor()
                for tool in toolCalls {
                    logProcess("\(tool)", kind: .tool)
                    let result = await executor.execute(tool, workspaceURL: workspaceURL)
                    if case .setWorkspace(let path) = tool {
                        let url = URL(fileURLWithPath: path)
                        workspaceURL = url; terminal.workingDirectory = url; refreshFiles()
                    }
                    addSystemMessage(result)
                }
            }

        // ── MLX direct in-process (new) ─────────────────────────────────────
        case .mlxReady:
            let m = activeMlxModel.components(separatedBy: "/").last ?? activeMlxModel
            logProcess("MLX/\(m) (direct)  temp=\(temperature)  maxTok=\(maxTokensMLX)", kind: .system)
            let msgId = UUID()
            messages.append(ChatMessage(id: msgId, role: .assistant, content: ""))
            // Nonisolated counter captured by ref via class box
            let counter = Counter()

            do {
                // MLX: nonisolated バッファ + 40ms ゲートで MainActor dispatch 回数を削減
                // 毎トークンに Task{@MainActor} を作るのは 40tok/s で 40 Tasks/s が生まれ非効率
                final class TokenBatch: @unchecked Sendable {
                    var buffer = ""
                    var lastFlush = Date.distantPast
                    let lock = NSLock()
                }
                let batch = TokenBatch()

                try await MLXRunner.shared.streamGenerateTokens(
                    prompt: prompt,
                    maxTokens: maxTokensMLX,
                    temperature: temperature,
                    onToken: { @Sendable [weak self] piece in
                        guard let self else { return }
                        counter.increment()
                        batch.lock.lock()
                        batch.buffer += piece
                        let shouldFlush = Date().timeIntervalSince(batch.lastFlush) >= 0.04
                        if shouldFlush { batch.lastFlush = Date() }
                        let flushed = shouldFlush ? batch.buffer : ""
                        if shouldFlush { batch.buffer = "" }
                        batch.lock.unlock()

                        guard shouldFlush, !flushed.isEmpty else { return }
                        Task { @MainActor in
                            if let idx = self.messages.firstIndex(where: { $0.id == msgId }) {
                                self.messages[idx].content += flushed
                            }
                            self.totalTokensGenerated += flushed.count  // approximate
                            let elapsed = Date().timeIntervalSince(startTime)
                            if elapsed > 0.1 {
                                self.tokensPerSecond = Double(counter.value) / elapsed
                            }
                        }
                    },
                    onFinish: { @Sendable [weak self] fullText in
                        guard let self else { return }
                        Task { @MainActor in
                            // 残バッファをフラッシュ
                            // NSLock は async コンテキストで使用不可 (Swift 6)。
                            // onFinish は全 onToken 完了後に呼ばれるため、
                            // この時点で concurrent アクセスは発生しない → lock 不要。
                            let remaining = batch.buffer
                            batch.buffer = ""
                            if !remaining.isEmpty,
                               let idx = self.messages.firstIndex(where: { $0.id == msgId }) {
                                self.messages[idx].content += remaining
                            }
                            let elapsed = Date().timeIntervalSince(startTime)
                            self.inferenceMs = Int(elapsed * 1000)
                            self.tokensPerSecond = Double(counter.value) / max(elapsed, 0.001)
                            self.logProcess(String(format: "done  %.1f tok/s  │  %d tok  │  %.1fs",
                                                   self.tokensPerSecond, counter.value, elapsed), kind: .perf)
                            // Agent tool parsing (same as Ollama path)
                            if self.agentLoopEnabled {
                                let (toolCalls, _) = AgentToolParser.parse(from: fullText)
                                let executor = AgentToolExecutor()
                                for tool in toolCalls {
                                    self.logProcess("\(tool)", kind: .tool)
                                    let result = await executor.execute(tool, workspaceURL: self.workspaceURL)
                                    if case .setWorkspace(let path) = tool {
                                        let url = URL(fileURLWithPath: path)
                                        self.workspaceURL = url
                                        self.terminal.workingDirectory = url
                                        self.refreshFiles()
                                    }
                                    self.addSystemMessage(result)
                                }
                            }
                            self.isGenerating = false
                        }
                    }
                )
            } catch {
                logProcess("MLX error: \(error.localizedDescription)", kind: .system)
                messages.append(ChatMessage(role: .assistant,
                    content: "⚠️ MLX error: \(error.localizedDescription)"))
            }

            isGenerating = false
            return

        default:
            messages.append(ChatMessage(role: .assistant,
                content: "⚠️ No model loaded. Load an MLX model or connect Ollama first."))
            isGenerating = false
            return
        }
        isGenerating = false
    }

    // MARK: - Process log helpers

    func logProcess(_ text: String, kind: ProcessLogEntry.Kind) {
        let entry = ProcessLogEntry(timestamp: Date(), text: text, kind: kind)
        Task { @MainActor in
            if self.logStore.entries.count > 500 { self.logStore.entries.removeFirst(100) }
            self.logStore.entries.append(entry)
        }
    }

    func clearProcessLog() { logStore.entries.removeAll() }

    func applyDiff() {
        guard let diff = pendingDiff else { return }
        do {
            try diff.modifiedContent.write(to: diff.fileURL, atomically: true, encoding: .utf8)
            selectedFileContent = diff.modifiedContent
            addSystemMessage("✅ Applied changes to \(diff.fileURL.lastPathComponent)")
        } catch {
            addSystemMessage("❌ Failed to write: \(error.localizedDescription)")
        }
        pendingDiff = nil
        showDiff = false
    }

    func skipDiff() {
        pendingDiff = nil
        showDiff = false
        addSystemMessage("⏭ Changes discarded.")
    }

    // MARK: - Human Mode: File write approval

    /// User tapped "承認" — resume the AgentLoop continuation so the write executes.
    func approveFileWrite() {
        guard let req = pendingFileApproval else { return }
        pendingFileApproval = nil
        req.approve()
        addSystemMessage(self.t("✅ Approved: \(req.displayFileName)", "✅ 承認しました: \(req.displayFileName)"))
    }

    /// User tapped "拒否" — resume the AgentLoop continuation with false, skip write.
    func rejectFileWrite() {
        guard let req = pendingFileApproval else { return }
        let name = req.displayFileName
        pendingFileApproval = nil
        req.reject()
        addSystemMessage(self.t("⏸ Rejected: \(name)", "⏸ 拒否しました: \(name)"))
    }

    // MARK: - Vera-α: save-preview approval

    /// Adds a request to the review queue. If nothing is currently being
    /// reviewed, it shows immediately (matches the old single-item
    /// behavior in .perTurn mode, where there's normally never more than
    /// one at a time); otherwise it waits behind whatever's already
    /// pending (this is what accumulates in .batched mode, where
    /// VeraMemoryBridge doesn't block the agent loop waiting for each
    /// one to be resolved).
    func enqueueVeraSave(_ req: VeraSaveApprovalRequest) {
        if pendingVeraSave == nil {
            pendingVeraSave = req
        } else {
            pendingVeraSaveQueue.append(req)
        }
    }

    /// User tapped "保存" — resume the continuation so VeraMemoryBridge
    /// actually calls `remember`/`propose_ai_facts`.
    func approveVeraSave() {
        guard let req = pendingVeraSave else { return }
        req.approve()
        advanceVeraSaveQueue()
        addSystemMessage(self.t("✅ Saved to Vera", "✅ Vera に保存しました"))
    }

    /// User tapped "破棄" — resume with false, nothing is written to Vera.
    func rejectVeraSave() {
        guard let req = pendingVeraSave else { return }
        req.reject()
        advanceVeraSaveQueue()
        addSystemMessage(self.t("⏸ Discarded (not saved to Vera)", "⏸ 破棄しました（Vera には保存されません）"))
    }

    private func advanceVeraSaveQueue() {
        pendingVeraSave = pendingVeraSaveQueue.isEmpty ? nil : pendingVeraSaveQueue.removeFirst()
    }



    // MARK: - Model actions

    func connectOllama() {
        // Wire CI/CD error → agent auto-reply loop (once)
        registerCIErrorHook()
        Task {
            modelStatus = .connecting
            let models = await OllamaClient.shared.listModels()
            await MainActor.run {
                ollamaModels = models
                if models.contains(activeOllamaModel) {
                    modelStatus = .ollamaReady(model: activeOllamaModel)
                    ToastManager.shared.show("\(activeOllamaModel) ready", icon: "checkmark.circle.fill", color: .green)
                } else if models.contains("gemma4:26b") {
                    activeOllamaModel = "gemma4:26b"
                    modelStatus = .ollamaReady(model: "gemma4:26b")
                    ToastManager.shared.show("gemma4:26b ready", icon: "checkmark.circle.fill", color: .green)
                } else if !models.isEmpty {
                    let m = models.first!
                    activeOllamaModel = m
                    modelStatus = .ollamaReady(model: m)
                    ToastManager.shared.show("\(m) ready", icon: "checkmark.circle.fill", color: .green)
                } else {
                    modelStatus = .error("No Ollama models found")
                    ToastManager.shared.show("No Ollama models. Run: ollama pull gemma4:26b",
                                            icon: "exclamationmark.triangle.fill", color: .orange, duration: 4.5)
                }
            }
        }
    }

    // MARK: - Model Eject (from LoadedModelPanel)

    /// Unload the currently active model, freeing all memory.
    ///
    /// • MLX: releases ModelContainer via MLXRunner.unloadModel() → deinit path frees GPU/ANE.
    /// • Ollama: sends DELETE /api/delete or keep-alive=0 to unload from RAM.
    ///
    /// After ejection, modelStatus → .none and a Deep→Front topology alias is persisted
    /// so the cognitive engine remembers which models have been used.
    func ejectModel() {
        let snap = modelStatus
        switch snap {
        case .mlxReady(let m), .mlxDownloading(let m):
            modelStatus = .none
            addSystemMessage(self.t("⏏ Ejected MLX Model: \(m)", "⏏ MLX モデルをリジェクト: \(m)"))
            Task.detached(priority: .userInitiated) {
                await MLXRunner.shared.unloadModel()
                // Write a topology alias into front/ for future reference
                Task.detached(priority: .utility) {
                    SessionMemoryArchiver.shared.writeDeepAlias(
                        modelId: m,
                        backend: "MLX",
                        kanjiTags: "[技:1.0] [速:0.8] [軽:0.7]"
                    )
                }
            }
        case .ollamaReady(let m):
            modelStatus = .none
            addSystemMessage(self.t("⏏ Ejected Ollama Model: \(m)", "⏏ Ollama モデルをリジェクト: \(m)"))
            let endpoint = ollamaEndpoint   // capture on MainActor before detaching
            Task.detached(priority: .userInitiated) {
                // Ollama: unload via generate API with keep_alive=0
                if let url = URL(string: "\(endpoint)/api/generate") {
                    var req = URLRequest(url: url)
                    req.httpMethod = "POST"
                    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    req.httpBody = try? JSONSerialization.data(withJSONObject: [
                        "model": m, "keep_alive": 0
                    ])
                    _ = try? await URLSession.shared.data(for: req)
                }
                Task.detached(priority: .utility) {
                    SessionMemoryArchiver.shared.writeDeepAlias(
                        modelId: m,
                        backend: "Ollama",
                        kanjiTags: "[技:1.0] [通:0.8] [外:0.6]"
                    )
                }
            }
        default:
            // Nothing loaded — just reset
            modelStatus = .none
        }
        // Toast notification
        ToastManager.shared.show(
            self.t("Model ejected", "モデルをリジェクトしました"),
            icon: "eject.fill",
            color: Color(red: 1.0, green: 0.55, blue: 0.2)
        )
    }


    // MARK: - Helpers

    func addSystemMessage(_ text: String) {
        // Only show agent-loop tool events — NOT model load events (those use Toast)
        guard !text.hasPrefix("🟢") && !text.hasPrefix("🔌") else { return }
        messages.append(ChatMessage(role: .system, content: text))
    }

    // MARK: - Settings Persistence (Startup Restore)
    //
    // activeOllamaModel と activeMlxModel は宣言時のデフォルト値として
    // UserDefaults から直接復元される（上記の ={ UserDefaults... }() パターン）。
    // その他の設定も同様に didSet で自動保存されるが、
    // 起動時のデフォルト値が UserDefaults を参照していない項目をここで補完する。

    func loadPersistedSettings() {
        let ud = UserDefaults.standard

        // ── Workspace ──────────────────────────────────────────────────────
        if let path = ud.string(forKey: "last_workspace_path") {
            let url = URL(fileURLWithPath: path)
            var isDir: ObjCBool = false
            if FileManager.default.fileExists(atPath: path, isDirectory: &isDir), isDir.boolValue {
                workspaceURL = url
                terminal.workingDirectory = url
                GatekeeperModeState.shared.configure(workspaceURL: url)
                refreshFiles()
                // ⚠️ L2.5インデックスの起動は VerantyxApp.onAppear (0.3秒後) で一元管理。
                // ここで呼ぶと onAppear 側と二重起動になり MainActor デッドロックが発生する。
            }

        }

        // ── Anthropic ──────────────────────────────────────────────────────
        if let key = ud.string(forKey: "anthropic_api_key"), !key.isEmpty {
            anthropicApiKey = key                       // didSet → AnthropicClient.configure
        }
        if let model = ud.string(forKey: "anthropic_model"), !model.isEmpty {
            activeAnthropicModel = model
        }

        // ── Model config ───────────────────────────────────────────────────
        // temperature/maxTokens/systemPrompt 等は宣言時のデフォルトが UD を見ていない
        // ため、ここで上書きする（didSet による二重保存は無害）。
        if let t = ud.object(forKey: "model_temperature") as? Double { temperature = t }
        if let n = ud.object(forKey: "max_tokens_ollama") as? Int    { maxTokensOllama = n }
        if let n = ud.object(forKey: "max_tokens_mlx") as? Int       { maxTokensMLX = n }
        if let n = ud.object(forKey: "context_window_override") as? Int { contextWindowOverride = n }
        if let raw = ud.string(forKey: "vera_save_approval_mode"),
           let mode = VeraSaveApprovalMode(rawValue: raw) { veraSaveApprovalMode = mode }
        if let e = ud.string(forKey: "ollama_endpoint"), !e.isEmpty  { ollamaEndpoint = e }
        if let s = ud.string(forKey: "system_prompt"), !s.isEmpty    { systemPrompt = s }

        // ── Toggles ────────────────────────────────────────────────────────
        if let v = ud.object(forKey: "agent_loop_enabled") as? Bool  { agentLoopEnabled = v }
        if let v = ud.object(forKey: "streaming_enabled")  as? Bool  { streamingEnabled = v }
        if let v = ud.object(forKey: "tool_browser")       as? Bool  { toolBrowserEnabled = v }
        if let v = ud.object(forKey: "tool_web_search")    as? Bool  { toolWebSearchEnabled = v }
        if let v = ud.object(forKey: "tool_terminal")      as? Bool  { toolTerminalEnabled = v }
        if let v = ud.object(forKey: "tool_diff")          as? Bool  { toolDiffEnabled = v }
        if let v = ud.object(forKey: "tool_jcross")        as? Bool  { toolJCrossEnabled = v }
        if let v = ud.object(forKey: "gemma_semantic_masking") as? Bool { gemmaSemanticMaskingEnabled = v }

        // ── Modes ──────────────────────────────────────────────────────────
        if let raw = ud.string(forKey: "inference_mode"),
           let m = InferenceMode(rawValue: raw) { inferenceMode = m }
        if let raw = ud.string(forKey: "cloud_provider"),
           let p = CloudProvider(rawValue: raw) { cloudProvider = p }
        if let raw = ud.string(forKey: "operation_mode"),
           let o = OperationMode(rawValue: raw) {
            // Migrate users whose saved mode is .gatekeeper: it is no longer
            // offered in the mode Picker, and a SwiftUI Picker bound to a
            // selection with no matching tag renders blank and cannot be
            // changed — so restoring it verbatim would strand those users
            // with an unusable control.
            operationMode = (o == .gatekeeper) ? .automatic : o
        }

        // ── Notification ───────────────────────────────────────────────────
        if let v = ud.object(forKey: "notify_diff_apply") as? Bool { notifyOnDiffApply = v }
        if let v = ud.object(forKey: "notify_error")      as? Bool { notifyOnError = v }
    }

    // MARK: - CI/CD Auto-Reply Hook
    //
    // When CIValidationEngine detects a compile error after an AI-generated patch,
    // it broadcasts selfEvolutionCIError. We automatically feed the error digest
    // back to the agent as a new user message, so the agent self-corrects.

    func registerCIErrorHook() {
        NotificationCenter.default.addObserver(
            forName: .selfEvolutionCIError,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            guard let self,
                  let digest = notification.userInfo?["digest"] as? String else { return }

            // Hop to MainActor for all @MainActor-isolated mutations.
            // sendMessage is a sync func that internally spawns a Task — no await needed.
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.messages.append(ChatMessage(
                    role: .system,
                    content: "🔬 CI エラー検出 — AI が自動修正を試みます"
                ))
                self.sendMessage(with: digest)
            }
        }
    }

    /// Subscribe to the [RESTART_IDE] agent event.
    /// Call from VerantyxApp.onAppear once.
    func registerRestartHook() {
        NotificationCenter.default.addObserver(
            forName: .agentRequestsRestart,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            // Wrap in Task { @MainActor } so Swift 6 sees the mutation as actor-safe.
            Task { @MainActor [weak self] in
                self?.showRestartAlert = true
            }
        }
    }

    /// Apply pending patches then quit; rebuild.sh relaunches the app.
    func performRestart() {
        try? SelfEvolutionEngine.shared.applyAllPatches()
        guard let wsPath = cortexWorkspacePath ?? workspaceURL?.path else { return }
        let rebuildScript = wsPath + "/rebuild.sh"
        if FileManager.default.fileExists(atPath: rebuildScript) {
            Task.detached {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: "/bin/zsh")
                process.arguments = ["-c", "sleep 0.5 && bash '\(rebuildScript)'"]
                try? process.run()
            }
        }
        NSApplication.shared.terminate(nil)
    }

    var isReady: Bool {
        switch modelStatus {
        case .ready, .ollamaReady, .mlxReady, .bitnetReady: return true
        default: return false
        }
    }

    var statusLabel: String {
        switch modelStatus {
        case .none:                          return "No model"
        case .connecting:                    return "Connecting…"
        case .downloading(let p):            return "Downloading \(Int(p * 100))%"
        case .ready(let n):                  return n
        case .ollamaReady(let m):            return "Ollama: \(m.components(separatedBy: ":").first ?? m)"
        case .anthropicReady(let m, _):      return "Claude: \(m)"
        case .mlxReady(let m):              return "MLX: \(m.components(separatedBy: "/").last ?? m)"
        case .mlxDownloading(let m):        return "⏬ \(m.components(separatedBy: "/").last ?? m)"
        case .bitnetReady(let m):           return "BitNet: \(m)"
        case .jcrossReady(let m):           return "JGEN: \(m)"
        case .error(let e):                  return "Error: \(e)"
        }
    }

    var statusColor: Color {
        switch modelStatus {
        case .ready, .ollamaReady, .mlxReady, .anthropicReady, .bitnetReady, .jcrossReady: return .green
        case .error:                           return .red
        case .downloading, .connecting,
             .mlxDownloading:                  return .orange
        case .none:                            return .gray
        }
    }


    // MARK: - Architecture template setup

    /// Builds a plan for `template` and queues it for approval. Runs the
    /// planner to completion *before* presenting the sheet, so any web lookup
    /// can't leave a spinner (or a verification puzzle) stuck behind a modal.
    func proposeSetup(template: ArchitectureTemplate, allowWeb: Bool = true) {
        Task { @MainActor in
            let machine = MachineProfile.current()
            let inventory = await ModelInventory.snapshot(app: self)
            let proposal = await TemplateSetupPlanner.shared.plan(
                template: template, machine: machine,
                inventory: inventory,
                hasAnthropicKey: !self.anthropicApiKey.isEmpty,
                allowWeb: allowWeb
            )
            self.pendingSetupProposal = proposal
        }
    }

    /// Applies an approved plan. Deliberately does *not* touch
    /// `activeOllamaModel`: the chat model and the execution model are
    /// different roles, and silently swapping the user's chat model is the
    /// most likely surprise here.
    func applySetupProposal(_ proposal: SetupProposal) {
        let store = CouncilSettingsStore.shared
        store.config = proposal.template.councilConfig
        store.templateId = proposal.template.id

        if let exec = proposal.assignment(.execution), exec.backend != .none {
            store.executionModel = exec.model == "—" ? "" : exec.model
        } else {
            store.executionModel = ""
        }
        // JGEN vector-bus / any template whose execution layer is JGEN:
        // keep Layer 2 on the same engine and skip AgentLoop.
        if let exec = proposal.assignment(.execution), exec.backend == .jgen {
            store.executionUseJGEN = true
        } else if proposal.template.id == "jgen-vector-bus" {
            store.executionUseJGEN = true
        } else if proposal.template.layers.contains(where: { $0.role == .execution && $0.backend == .jgen }) {
            store.executionUseJGEN = true
        } else {
            // Don't force-off: user may have toggled JGEN L2 independently.
        }
        if let esc = proposal.assignment(.escalation), esc.backend != .none, esc.model != "—" {
            store.config.escalationModel = esc.model
        } else {
            store.config.escalationModel = ""
            // Templates that disable L3 must not keep a stale escalate flag
            // from a previous "strongest" config sitting only in escalationModel.
            if proposal.template.layer(.escalation)?.enabled == false {
                store.config.escalateOnLowConfidence = false
            }
        }

        // Layer 1 runs on JGEN; load it if the plan named one that isn't
        // already active.
        if let core = proposal.assignment(.councilCore), core.backend == .jgen, core.model != "—" {
            let alreadyLoaded: Bool
            if case .jcrossReady(let m) = modelStatus { alreadyLoaded = (m == core.model) } else { alreadyLoaded = false }
            if !alreadyLoaded { loadJGenModel(core.model) }
        }

        pendingSetupProposal = nil
        let name = AppLanguage.shared.isJapanese ? proposal.template.nameJA : proposal.template.name
        addSystemMessage(t("🧩 Applied setup: \(name)", "🧩 構成を適用しました: \(name)"))
    }

    // MARK: - JGEN Actions

    /// Loads a converted `.jgen` model into `JCrossChatManager` and flips
    /// `modelStatus` to `.jcrossReady` so `AgentLoop.callModel` routes chat
    /// through the JGEN engine.
    ///
    /// Lives here rather than in `JGenSettingsSection` (where it used to be)
    /// because the model-selector bar above the chat input now loads JGEN
    /// models too -- two copies of this would let the bar and Settings show
    /// contradictory state. Both surfaces observe `jgenLoadingModel` /
    /// `jgenLoadError`.
    func loadJGenModel(_ name: String) {
        jgenLoadingModel = name
        jgenLoadError = nil
        Task {
            do {
                try await JCrossChatManager.shared.load(modelFileName: name)
                await MainActor.run {
                    self.jgenLoadingModel = nil
                    self.modelStatus = .jcrossReady(model: name)
                    self.addSystemMessage("🧠 JGEN \(name) をロードしました")
                }
            } catch {
                await MainActor.run {
                    self.jgenLoadingModel = nil
                    self.jgenLoadError = error.localizedDescription
                }
            }
        }
    }

    // MARK: - MLX Actions (Direct in-process — no HTTP server)

    func loadMLXModel(model: String? = nil) {
        let modelId = model ?? activeMlxModel
        modelStatus = .connecting
        mlxServerLogs.removeAll()

        Task {
            do {
                try await MLXRunner.shared.loadModel(id: modelId) { @Sendable log in
                    Task { @MainActor in
                        self.mlxServerLogs.append(log)
                        self.logProcess(log, kind: .system)
                    }
                }
                await MainActor.run {
                    self.modelStatus = .mlxReady(model: modelId)
                    self.activeMlxModel = modelId
                    ToastManager.shared.show(
                        "MLX: \(modelId.components(separatedBy: "/").last ?? modelId) ready 🚀",
                        icon: "cpu",
                        color: Color(red: 0.4, green: 0.85, blue: 0.6)
                    )
                }
            } catch {
                await MainActor.run {
                    self.modelStatus = .error(error.localizedDescription)
                    ToastManager.shared.show(
                        "MLX error: \(error.localizedDescription)",
                        icon: "exclamationmark.triangle.fill",
                        color: .orange, duration: 5
                    )
                }
            }
        }
    }

    /// Legacy alias so old call sites keep compiling.
    @available(*, deprecated, renamed: "loadMLXModel")
    func startMLXServer(model: String? = nil) { loadMLXModel(model: model) }

    func downloadMLXModel(repoId: String) {
        modelStatus = .mlxDownloading(model: repoId)
        mlxServerLogs.removeAll()

        Task {
            do {
                try await MLXRunner.shared.downloadModel(repoId: repoId) { @Sendable log in
                    Task { @MainActor in
                        self.mlxServerLogs.append(log)
                    }
                }
                await MainActor.run {
                    ToastManager.shared.show(
                        "Downloaded: \(repoId.components(separatedBy: "/").last ?? repoId)",
                        icon: "checkmark.circle.fill",
                        color: .green, duration: 4
                    )
                    self.loadMLXModel(model: repoId)
                }
            } catch {
                await MainActor.run {
                    self.modelStatus = .error("Download failed: \(error.localizedDescription)")
                }
            }
        }
    }
}
