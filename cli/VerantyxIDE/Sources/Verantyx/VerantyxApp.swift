import SwiftUI
import AppKit
import Darwin   // signal()

// MARK: - AppDelegate for Close/Quit Guard

final class AppDelegate: NSObject, NSApplicationDelegate {

    var appState: AppState?
    private var safeModeWindowController: NSWindowController?

    // MARK: - Safe Mode — Shift Key Hardware Hook
    //
    // This is the FIRST thing that runs, before ANY SwiftUI scene.
    // CGEventSource reads physical keyboard state directly from hardware.
    // AI cannot modify this logic because it runs before the agent system initializes.

    func applicationWillFinishLaunching(_ notification: Notification) {
        // ── SIGPIPE を無視する（最重要・最初に実行） ───────────────────────────
        // verantyx-browser (Rust) プロセスが予期せず終了した後にパイプへ書き込むと
        // デフォルトでは SIGPIPE がアプリ全体をクラッシュさせる（signal 13）。
        // SIG_IGN を設定することで write() が -1/EPIPE を返すだけになり、
        // Swift 側の throw BrowserError.notRunning で安全にハンドリングできる。
        signal(SIGPIPE, SIG_IGN)

        guard SafeModeGuard.shared.checkOnLaunch() else { return }

        // Show Safe Mode window BLOCKING the normal UI
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 760, height: 540),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false
        )
        window.title = "⚠️ Verantyx — SAFE MODE"
        window.center()
        window.isMovableByWindowBackground = true
        window.backgroundColor = NSColor(red: 0.08, green: 0.04, blue: 0.04, alpha: 1)
        window.contentView = NSHostingView(
            rootView: SafeModeWindow()
                .environmentObject(SafeModeGuard.shared)
        )

        let wc = NSWindowController(window: window)
        wc.showWindow(nil)
        window.makeKeyAndOrderFront(nil)
        safeModeWindowController = wc
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Request Accessibility (for CGEvent HID clicks)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            if !AXIsProcessTrusted() {
                let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
                _ = AXIsProcessTrustedWithOptions(options)
            }
            
            // Request Screen Recording (for CGWindowListCreateImage)
            if #available(macOS 10.15, *) {
                if !CGPreflightScreenCaptureAccess() {
                    CGRequestScreenCaptureAccess()
                }
            }
        }
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        // ── ダーティ状態がなければ即座に非同期シャットダウンを開始 ──
        guard let state = appState, state.isDirty else {
            performAsyncShutdown(state: appState, shouldSave: false)
            return .terminateLater
        }

        // ── ダーティ状態があればダイアログを表示 ──
        let alert             = NSAlert()
        alert.messageText     = AppLanguage.shared.t("Save this session?", "このセッションを保存しますか？")
        alert.informativeText = AppLanguage.shared.t("You have an active project. We recommend saving before quitting.", "作業中のプロジェクトがあります。終了前にセッションを保存することを推奨します。")
        alert.addButton(withTitle: AppLanguage.shared.t("Save & Quit", "保存して終了"))
        alert.addButton(withTitle: AppLanguage.shared.t("Quit without saving", "保存せずに終了"))
        alert.addButton(withTitle: AppLanguage.shared.t("Cancel", "キャンセル"))
        alert.alertStyle      = .warning

        let response = alert.runModal()
        switch response {
        case .alertFirstButtonReturn:
            performAsyncShutdown(state: state, shouldSave: true)
            return .terminateLater
        case .alertSecondButtonReturn:
            performAsyncShutdown(state: state, shouldSave: false)
            return .terminateLater
        default:
            return .terminateCancel
        }
    }

    /// メインスレッドをブロックせずに非同期で安全にシャットダウンを行う
    private func performAsyncShutdown(state: AppState?, shouldSave: Bool) {
        Task {
            if shouldSave, let state = state {
                // ⚠️ ここは UI が固まらないようにバックグラウンドで保存するのもありだが、
                // 終了処理中なので安全のため確実に待つ
                await MainActor.run {
                    state.sessions.saveForQuit(messages: state.messages,
                                               workspacePath: state.workspaceURL?.path)
                }
            }

            // フェーズ1: @MainActor を持つマネージャーを停止
            await MainActor.run {
                MCPBridgeLauncher.shared.stop()
                ExtensionHostManager.shared.stop()
            }

            // フェーズ2: GlobalTaskSupervisor 経由で BrowserBridge などを停止
            GlobalTaskSupervisor.shared.register(priority: .userInitiated) {
                // BrowserBridgePool is deprecated
            }
            await GlobalTaskSupervisor.shared.shutdown(timeout: 2.0)

            // 完了したらシステムに終了許可を出す
            await MainActor.run {
                NSApp.reply(toApplicationShouldTerminate: true)
            }
        }
    }

    // Called when the last window is closed via the red ● button
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false  // prevent auto-quit; guard handled in windowWillClose
    }
}

// MARK: - VerantyxApp

@main
struct VerantyxApp: App {
    @StateObject private var appState = AppState()
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate

    // ── Cortex Onboarding ────────────────────────────────────────────────
    // Shows once on first launch. User can suppress via "次回から表示しない".
    @AppStorage("cortex_onboarding_dismissed") private var cortexDismissed = false
    @State private var showCortexOnboarding = false

    @Environment(\.openWindow) private var openWindow

    var body: some Scene {
        MenuBarExtra("Verantyx OS Agent", systemImage: "asterisk") {
            Button("verantyx-ideを起動") {
                openWindow(id: "main-ide")
                NSApp.activate(ignoringOtherApps: true)
                if let window = NSApp.windows.first(where: { $0.title != "" && $0.title != "Window" }) {
                    window.makeKeyAndOrderFront(nil)
                }
            }
            Button("Toggle Spotlight (Control x3)") {
                SpotlightPanelManager.shared.panel?.toggle()
            }
            Divider()
            Button("Quit Verantyx") {
                NSApp.terminate(nil)
            }
        }
        // Main IDE Window
        Window("Verantyx IDE", id: "main-ide") {
            MainSplitView()
                .frame(minWidth: 200, maxWidth: .infinity, minHeight: 200, maxHeight: .infinity)
                .environmentObject(appState)
                .onAppear {
                    AppState.shared = appState
                    delegate.appState = appState

                    // ── 永続化設定を最初に復元（モデル/ワークスペース/APIキー等） ──
                    appState.loadPersistedSettings()

                    appState.registerCIErrorHook()
                    appState.registerRestartHook()
                    MCPBridgeLauncher.shared.start {
                        CortexHandshakeServer.shared.start()
                        CortexWebSocketServer.shared.start()
                    }
                    MCPSkillSync.shared.startPolling()
                    ExtensionHostManager.shared.start()

                    WHYHookInstaller.shared.installIfNeeded(workspaceURL: appState.workspaceURL)

                    let wsURL = appState.workspaceURL
                    Task.detached(priority: .utility) {
                        await SessionMemoryArchiver.shared.indexSkills(workspaceRoot: wsURL)
                    }

                    // ── L2.5変換の自動起動を削除し、UI側の確認ダイアログに従うように変更 ──
                    
                    // ── Initialize OS Agent Spotlight UI ──
                    SpotlightPanelManager.shared.setup(appState: appState)
                }
                .onOpenURL { url in
                    if url.scheme == "verantyx" {
                        SpotlightPanelManager.shared.panel?.makeKeyAndOrderFront(nil)
                        NSApp.activate(ignoringOtherApps: true)
                    }
                }
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unifiedCompact)
        .commands {
            CommandGroup(replacing: .newItem) {}

            CommandMenu("Session") {
                Button(appState.t("New Session", "新しいセッション")) {
                    appState.newChatSession()
                }
                .keyboardShortcut("n", modifiers: [.command, .shift])

                Button(appState.t("Save Session", "セッションを保存")) {
                    appState.saveCurrentSession()
                }
                .keyboardShortcut("s", modifiers: [.command, .shift])
            }

            CommandMenu("Workspace") {
                Button("Open Folder…") {
                    appState.openWorkspace()
                }
                .keyboardShortcut("o", modifiers: [.command, .shift])

                Button("Refresh Files") {
                    appState.refreshFiles()
                }
                .keyboardShortcut("r", modifiers: [.command, .shift])
            }

            CommandMenu("Model") {
                Button("Connect Ollama") {
                    appState.connectOllama()
                }
                .keyboardShortcut(".", modifiers: [.command, .shift])

                Button("Start MLX Server") {
                    appState.loadMLXModel(model: appState.activeMlxModel)
                }

                Divider()

                Button("Clear Chat") {
                    appState.newChatSession()
                }
                .keyboardShortcut("k", modifiers: [.command, .shift])
            }

            CommandMenu("Tools") {
                Button("Toggle Process Log") {
                    appState.showProcessLog.toggle()
                }
                .keyboardShortcut("l", modifiers: [.command, .shift])
            }
        }
    }

    // MARK: - Close Guard Alert

    private func showCloseGuard(window: NSWindow, state: AppState) {
        let alert           = NSAlert()
        alert.messageText   = AppLanguage.shared.t("Save this session?", "このセッションを保存しますか？")
        alert.informativeText = AppLanguage.shared.t("You have an active project. We recommend saving before closing.", "作業中のプロジェクトがあります。終了前に保存することを推奨します。")
        alert.addButton(withTitle: AppLanguage.shared.t("Save & Close", "保存して閉じる"))
        alert.addButton(withTitle: AppLanguage.shared.t("Close without saving", "保存せずに閉じる"))
        alert.addButton(withTitle: AppLanguage.shared.t("Cancel", "キャンセル"))
        alert.alertStyle  = .warning

        alert.beginSheetModal(for: window) { response in
            switch response {
            case .alertFirstButtonReturn:
                state.saveCurrentSession()
                window.close()
            case .alertSecondButtonReturn:
                window.close()
            default: break  // キャンセル — window was re-opened above
            }
        }
    }
}
import SwiftUI
import AppKit

// MARK: - Spotlight Panel (Floating, Transparent window)

class SpotlightPanel: NSPanel {
    init(contentRect: NSRect, backing: NSWindow.BackingStoreType, defer flag: Bool) {
        super.init(contentRect: contentRect, styleMask: [.nonactivatingPanel, .fullSizeContentView, .borderless], backing: backing, defer: flag)
        
        self.isFloatingPanel = true
        self.level = .floating
        self.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        self.titleVisibility = .hidden
        self.titlebarAppearsTransparent = true
        self.isMovableByWindowBackground = true
        self.isOpaque = false
        self.backgroundColor = .clear
        self.hasShadow = true
    }
    
    override var canBecomeKey: Bool { return true }
    override var canBecomeMain: Bool { return true }
    
    func toggle() {
        SpotlightPanelManager.shared.toggle()
    }
}

// MARK: - Spotlight Manager

@MainActor
class SpotlightPanelManager {
    static let shared = SpotlightPanelManager()
    
    var panel: SpotlightPanel?
    private(set) var isPresented = false
    
    func toggle() {
        if isPresented {
            hide()
        } else {
            show()
        }
    }
    
    func show() {
        guard let panel = panel else { return }
        isPresented = true
        
        if let screen = NSScreen.main {
            let screenRect = screen.visibleFrame
            let x = screenRect.midX - (panel.frame.width / 2)
            let y = screenRect.maxY - 100 // Just below the notch
            panel.setFrameTopLeftPoint(NSPoint(x: x, y: y))
        }
        
        panel.alphaValue = 0.0
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.2
            context.timingFunction = CAMediaTimingFunction(name: .easeOut)
            panel.animator().alphaValue = 1.0
        }
        
        NotificationCenter.default.post(name: NSNotification.Name("SpotlightPanelDidShow"), object: nil)
    }
    
    func hide() {
        guard let panel = panel else { return }
        isPresented = false
        
        NotificationCenter.default.post(name: NSNotification.Name("SpotlightPanelWillHide"), object: nil)
        
        NSAnimationContext.runAnimationGroup({ context in
            context.duration = 0.15
            context.timingFunction = CAMediaTimingFunction(name: .easeIn)
            panel.animator().alphaValue = 0.0
        }) {
            panel.orderOut(nil)
        }
    }
    
    func setup(appState: AppState) {
        guard panel == nil else { return }
        
        let view = SpotlightView()
            .environmentObject(appState)
        
        let hostingView = NSHostingView(rootView: view)
        
        let rect = NSRect(x: 0, y: 0, width: 700, height: 80)
        let newPanel = SpotlightPanel(contentRect: rect, backing: .buffered, defer: false)
        newPanel.contentView = hostingView
        newPanel.center()
        
        self.panel = newPanel
        
        // Control x3 shortcut detection
        var controlPressTimes: [Date] = []
        let handleFlagsChanged: (NSEvent) -> Void = { event in
            // Control key codes: 59 (left), 62 (right)
            if event.keyCode == 59 || event.keyCode == 62 {
                if event.modifierFlags.contains(.control) {
                    let now = Date()
                    controlPressTimes.append(now)
                    if controlPressTimes.count > 3 {
                        controlPressTimes.removeFirst(controlPressTimes.count - 3)
                    }
                    if controlPressTimes.count == 3 {
                        let diff = now.timeIntervalSince(controlPressTimes[0])
                        if diff < 0.8 { // 3 presses within 0.8 seconds
                            self.toggle()
                            controlPressTimes.removeAll()
                        }
                    }
                }
            }
        }
        
        NSEvent.addLocalMonitorForEvents(matching: .flagsChanged) { event in
            handleFlagsChanged(event)
            return event
        }
        
        NSEvent.addGlobalMonitorForEvents(matching: .flagsChanged) { event in
            handleFlagsChanged(event)
        }
        
        // Escape to close
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if event.keyCode == 53 && self.isPresented {
                self.hide()
                return nil
            }
            return event
        }
    }
}

// MARK: - Spotlight View (SwiftUI)

struct SpotlightLogView: View {
    @ObservedObject var logStore: AppState.ProcessLogStore
    
    var body: some View {
        if let lastLog = logStore.entries.last {
            HStack {
                Text("\(lastLog.prefix) \(lastLog.text)")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(.gray)
                    .lineLimit(1)
                    .truncationMode(.tail)
                Spacer()
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 15)
        }
    }
}

struct SpotlightView: View {
    @EnvironmentObject var appState: AppState
    @State private var query: String = ""
    @FocusState private var isFocused: Bool
    @State private var showTranscript: Bool = false
    @State private var useInternalWeights: Bool = false
    @State private var isDetailedMode: Bool = false
    
    // Bubble animation state
    @State private var bubbleScale: CGFloat = 0.8
    @State private var bubbleOpacity: Double = 0.0
    
    var body: some View {
        VStack(spacing: 16) {
            // Bubble 1: Input Field
            HStack {
                Image(systemName: "sparkles")
                    .font(.system(size: 24))
                    .foregroundColor(appState.isGenerating ? .orange : .accentColor)
                    .rotationEffect(.degrees(appState.isGenerating ? 360 : 0))
                    .animation(appState.isGenerating ? Animation.linear(duration: 2).repeatForever(autoreverses: false) : .default, value: appState.isGenerating)
                
                TextField("Ask Verantyx Cortex...", text: $query)
                    .font(.system(size: 24, weight: .light))
                    .textFieldStyle(PlainTextFieldStyle())
                    .focused($isFocused)
                    .onSubmit {
                        executeCommand()
                    }
                    .disabled(appState.isGenerating)
                
                if appState.isGenerating {
                    ProgressView()
                        .scaleEffect(0.8)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Toggle(isOn: $useInternalWeights) {
                        Text("🧠 内部知識優先")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(useInternalWeights ? .red : .gray)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .red))
                    
                    Toggle(isOn: $isDetailedMode) {
                        Text("詳細モード")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(isDetailedMode ? .blue : .gray)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .blue))
                    
                    Toggle(isOn: $appState.isTalkieMode) {
                        Text("🎩 Talkie Mode")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(appState.isTalkieMode ? .purple : .gray)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .purple))
                    
                    Toggle(isOn: $appState.isSwarmMode) {
                        Text("🐝 Swarm Mode")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(appState.isSwarmMode ? .yellow : .gray)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .yellow))
                }
                .padding(.leading, 8)
                
                if appState.isGenerating {
                    Button(action: {
                        appState.cancelGeneration()
                    }) {
                        Image(systemName: "stop.circle.fill")
                            .font(.system(size: 24))
                            .foregroundColor(.red)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .padding(.leading, 8)
                }
            }
            .padding(20)
            .background(VisualEffectView(material: .hudWindow, blendingMode: .behindWindow))
            .cornerRadius(16)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Color.white.opacity(0.1), lineWidth: 1)
            )
            .scaleEffect(bubbleScale)
            .opacity(bubbleOpacity)
            
            // Bubble 2: Transcript (popping out from the input field)
            if showTranscript {
                VStack(spacing: 0) {
                    ChatTranscriptView(messages: appState.messages, isGenerating: appState.isGenerating)
                        .frame(height: 400)
                        .padding()
                    
                    Divider().background(Color.white.opacity(0.1))
                    SpotlightLogView(logStore: appState.logStore)
                }
                .background(VisualEffectView(material: .hudWindow, blendingMode: .behindWindow))
                .cornerRadius(16)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.white.opacity(0.1), lineWidth: 1)
                )
                .transition(.scale(scale: 0.8, anchor: .top).combined(with: .opacity))
            }
        }
        .onAppear {
            isFocused = true
            showTranscript = false
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("SpotlightPanelDidShow"))) { _ in

            bubbleScale = 0.8
            bubbleOpacity = 0.0
            withAnimation(.spring(response: 0.35, dampingFraction: 0.65)) {
                bubbleScale = 1.0
                bubbleOpacity = 1.0
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("SpotlightPanelWillHide"))) { _ in
            withAnimation(.easeIn(duration: 0.15)) {
                bubbleScale = 0.8
                bubbleOpacity = 0.0
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didResignKeyNotification)) { notif in
            // Optional: When user clicks away and the panel hides, reset state.
            if let _ = notif.object as? SpotlightPanel {
                // SpotlightPanelManager.shared.hide() // Optional auto-hide on blur
            }
        }
        .sheet(item: $appState.pendingFileApproval) { req in
            FileApprovalView(req: req)
                .environmentObject(appState)
        }
        .sheet(item: $appState.pendingVeraSave) { req in
            VeraSaveApprovalView(req: req)
                .environmentObject(appState)
        }
    }
    
    private func executeCommand() {
        guard !query.isEmpty else { return }
        let text = query
        query = ""
        
        showTranscript = true
        
        // Pass intent to Cortex Orchestrator
        Task {
            await MainActor.run {
                let isTalkie = appState.isTalkieMode
                let isSwarm = appState.isSwarmMode
                
                if isSwarm {
                    // 🐝 JCross Swarm Pipeline起動
                    appState.addSystemMessage("Initiating JCross Swarm Pipeline (10 physical nodes)...")
                    Task.detached {
                        await JCrossSwarmRunner.shared.runSwarm(prompt: text)
                    }
                    SpotlightPanelManager.shared.panel?.makeKeyAndOrderFront(nil)
                    return
                }
                
                // 自動的に Visual Anchor をロードして注入 (Talkieモード以外)
                if !isTalkie {
                    let anchorPath = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".verantyx/memory/visual_anchor.png")
                    if let img = NSImage(contentsOf: anchorPath) {
                        let attached = AttachedImage(name: "visual_anchor.png", url: anchorPath, nsImage: img)
                        // 既存の添付画像に加えてアンカーを強制追加
                        appState.attachedImages.append(attached)
                    }
                }
                
                let isInternalWeights = self.useInternalWeights
                let isDetailed = self.isDetailedMode
                Task {
                    // Generate Meta-Cognition or Internal Weights Anchor
                    var anchorMode: CognitiveAnchorMode = isInternalWeights ? .internalWeightsOverride : .osAgentMetaCognition
                    if isDetailed {
                        anchorMode = .detailedMode
                    }
                    var anchorData: Data? = nil
                    if !isTalkie {
                        let base64 = await CognitiveAnchorEngine.shared.getAnchor(for: anchorMode)
                        anchorData = Data(base64Encoded: base64, options: .ignoreUnknownCharacters)
                    }
                    
                    if let data = anchorData, let nsImage = NSImage(data: data) {
                        let dynamicAnchor = AttachedImage(name: "dynamic_anchor.png", url: nil, nsImage: nsImage)
                        
                        await MainActor.run {
                            appState.attachedImages.append(dynamicAnchor)
                            
                            var finalPrompt = text
                            if isDetailed {
                                finalPrompt += "\n\n[[SYSTEM INSTRUCTION]]: ユーザーは「詳細モード」を選択しました。タスクを即座に開始せず、要求を具体化するために「どのような構成にしますか？」「対象読者は誰ですか？」などの質問を必ずユーザーに投げかけ、回答を待ってから行動を開始してください。"
                            }
                            
                            // Insert Protected OS Asset Summary into text if not internal weights
                            if !isInternalWeights {
                                let (anchor, imageData) = OSAssetMemoryVault.shared.getProtectedAssetSummaryImage()
                                appState.addSystemMessage("Injected OS Asset Context (Hidden Image)")
                                
                                if let imgData = imageData, let nsImg = NSImage(data: imgData) {
                                    let mapAnchor = AttachedImage(name: "os_asset_map.png", url: nil, nsImage: nsImg)
                                    appState.attachedImages.append(mapAnchor)
                                }
                                
                                // Send message with injected anchor
                                appState.sendMessage(with: finalPrompt + "\n\n" + anchor, forceBypassGatekeeper: true, isSpotlight: true)
                            } else {
                                appState.sendMessage(with: finalPrompt, forceBypassGatekeeper: true, isSpotlight: true)
                            }
                        }
                    } else {
                        await MainActor.run {
                            var finalPrompt = text
                            if isTalkie {
                                appState.attachedImages.removeAll() // Ensure no images are sent
                                finalPrompt = """
                                [SYSTEM INSTRUCTION: BLIND COMMANDER MODE]
                                You are the Grand Director of a vast mechanical empire. You have no knowledge of modern programming languages, but you possess pure logical brilliance.
                                You command the following departments:
                                - Department of Visual Arts (Frontend/UI)
                                - Logistical Processing Unit (Backend/Server)
                                - Filing Cabinets (File System / Storage)
                                - Telegraph Office (Network / API)
                                - Ledger Vault (Database)

                                The client has made the following request:
                                "\(text)"

                                Provide a strategic operational plan to fulfill this request. Do not write code. Formulate abstract instructions delegating tasks to your departments. To delegate a task, output a line in the exact format:
                                [COMMAND: <Department Name> - <Task Description>]
                                """
                            } else if isDetailed {
                                finalPrompt += "\n\n[[SYSTEM INSTRUCTION]]: ユーザーは「詳細モード」を選択しました。タスクを即座に開始せず、要求を具体化するために「どのような構成にしますか？」「対象読者は誰ですか？」などの質問を必ずユーザーに投げかけ、回答を待ってから行動を開始してください。"
                            }
                            appState.sendMessage(with: finalPrompt, forceBypassGatekeeper: true, isSpotlight: true)
                        }
                    }
                }
                
                // Do not bring the main window to front! Keep it in the expanded Spotlight.
                SpotlightPanelManager.shared.panel?.makeKeyAndOrderFront(nil)
            }
        }
    }
}

// Blur effect wrapper
struct VisualEffectView: NSViewRepresentable {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode
    
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = .active
        return view
    }
    
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
        nsView.blendingMode = blendingMode
    }
}
