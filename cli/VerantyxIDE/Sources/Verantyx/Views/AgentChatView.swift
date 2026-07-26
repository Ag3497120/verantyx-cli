import SwiftUI

// MARK: - AgentChatView
// Center panel: "Vibe Coding Workspace" + "Thinking Log" tabs
// Shows AntigravityAgent with <think> rendering in teal

struct AgentChatView: View {
    @EnvironmentObject var app: AppState
    @State private var showingHistory: Bool = false
    @State private var inputText: String = ""
    @FocusState private var inputFocused: Bool
    
    @State private var showVisualAnchorPrompt: Bool = false
    @State private var visualAnchorText: String = ""
    @State private var showSpotlightPrompt: Bool = false
    
    @State private var showAgentPromptAnchorPrompt: Bool = false
    @State private var agentPromptAnchorText: String = ""

    var body: some View {
        VStack(spacing: 0) {
            // ── Tab bar ─────────────────────────────────────────────
            tabBar

            Divider().opacity(0.3)

            // ── Content ─────────────────────────────────────────────
            ZStack {
                chatTranscriptArea
                    .opacity(showingHistory ? 0 : 1)
                    .offset(x: showingHistory ? 20 : 0)
                
                if showingHistory {
                    SessionHistoryView()
                        .environmentObject(app)
                        .opacity(showingHistory ? 1 : 0)
                        .offset(x: showingHistory ? 0 : -20)
                        .transition(.move(edge: .leading).combined(with: .opacity))
                }
            }
            .animation(.spring(response: 0.4, dampingFraction: 0.8), value: showingHistory)

            Divider().opacity(0.3)

            // ── Model selector bar ───────────────────────────────────
            modelSelectorBar

            Divider().opacity(0.3)

            // ── Puzzle Overlay ───────────────────────────────────────
            if app.requiresHumanPuzzle {
                HumanProofPuzzleView { entropy, duration, frames in
                    print("Puzzle solved in \(duration)s with \(entropy.count) entropy points.")
                    app.lastEntropy = entropy
                    app.lastVideoFrames = frames
                    app.lastEntropyTimestamp = Date()
                    // Hide puzzle after solve
                    app.requiresHumanPuzzle = false
                    
                    // Proceed with background botguard bypass using this entropy
                    // ... (send entropy to backend via AppState logic if needed)
                }
                .padding()
            }
            
            // ── Input ────────────────────────────────────────────────
            inputBar
        }
        .overlay(
            Group {
                if app.isAgentControllingMouse {
                    ZStack {
                        // Semi-transparent black background
                        Color.black.opacity(0.85)
                            .edgesIgnoringSafeArea(.all)
                        
                        VStack(spacing: 20) {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: Color(red: 0.0, green: 1.0, blue: 0.8)))
                                .scaleEffect(2.0)
                            
                            Text(AppLanguage.shared.t("🧩 Injecting biometric trajectory...", "🧩 生体データを注入中... (Injecting trajectory...)"))
                                .font(.system(size: 24, weight: .bold, design: .monospaced))
                                .foregroundColor(Color(red: 0.0, green: 1.0, blue: 0.8))
                                .shadow(color: Color(red: 0.0, green: 1.0, blue: 0.8).opacity(0.5), radius: 10, x: 0, y: 0)
                            
                            Text(AppLanguage.shared.t("Physical mouse input temporarily blocked", "物理的なマウス入力を一時的に遮断しています"))
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(.gray)
                        }
                    }
                    .transition(.opacity)
                    .animation(.easeInOut(duration: 0.3), value: app.isAgentControllingMouse)
                }
            }
        )
        .background(Color(red: 0.13, green: 0.13, blue: 0.16))
        // ─ Sync state with AppState (for session restore programmatic switch) ─
        .onChange(of: app.activeChatTab) { _, newVal in
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                showingHistory = (newVal == 1)
            }
        }
        .onChange(of: showingHistory) { _, isHistory in
            let idx = isHistory ? 1 : 0
            if app.activeChatTab != idx { app.activeChatTab = idx }
        }
        .onChange(of: app.sessions.activeSessionId) { _, _ in
            // When a session is selected from history, automatically switch back to chat view
            if showingHistory {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                    showingHistory = false
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("ChatTranscriptClicked"))) { _ in
            if !SpotlightPanelManager.shared.isPresented {
                showSpotlightPrompt = true
            }
        }
        .alert(app.t("Open Spotlight Agent?", "Spotlightエージェントを起動しますか？"), isPresented: $showSpotlightPrompt) {
            Button(app.t("Open (Control x3)", "起動する (Control x3)")) {
                SpotlightPanelManager.shared.show()
            }
            Button(app.t("Cancel", "キャンセル"), role: .cancel) {}
        } message: {
            Text(app.t(
                "The Control x3 agent is currently running in the background. Would you like to open the Spotlight panel to continue?",
                "現在、Control x3 のエージェントがバックグラウンドで待機しています。Spotlightエージェントを起動してチャットを継続しますか？"
            ))
        }
    }

    // MARK: - Top Chat Button

    private var tabBar: some View {
        HStack {
            Spacer()
            Button {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                    showingHistory.toggle()
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "bubble.left.and.bubble.right.fill")
                        .font(.system(size: 11))
                        .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))
                    Text(app.t("Chat", "チャット"))
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(Color.white)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(Color.white.opacity(0.6))
                        .rotationEffect(.degrees(showingHistory ? 180 : 0))
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(
                    Capsule()
                        .fill(Color(red: 0.2, green: 0.2, blue: 0.25))
                        .overlay(
                            Capsule().stroke(Color.white.opacity(0.1), lineWidth: 1)
                        )
                )
            }
            .buttonStyle(.plain)
            Spacer()
        }
        .padding(.vertical, 8)
        .background(Color(red: 0.15, green: 0.15, blue: 0.19))
    }

    // MARK: - Workspace (main chat)

    private var chatTranscriptArea: some View {
        ZStack(alignment: .bottomLeading) {
            // NSTextView ベースのトランスクリプト。
            // 単一テキストストレージのためメッセージをまたいでドラッグ選択・コピーができる。
            ChatTranscriptView(messages: app.messages.filter { !$0.isSpotlight }, isGenerating: app.isGenerating)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            
            if app.isGenerating && !app.currentGenerationIsSpotlight {
                LiveTerminalView()
                    .frame(height: 180)
                    .transition(AnyTransition.move(edge: .bottom).combined(with: .opacity))
                    .animation(Animation.spring(response: 0.35, dampingFraction: 0.8), value: app.isGenerating)
            }
        }
    }


    // MARK: - Model selector bar

    private var modelSelectorBar: some View {
        HStack(spacing: 8) {
            // ── Gatekeeper Local Model Configuration ──────────────
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    Text("Gatekeeper")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(Color.green)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 4)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(4)
                    
                    // Unified MLX & Ollama model picker
                    let unifiedBinding = Binding<String>(
                        get: {
                            if case .mlxReady(let m) = app.modelStatus { return m }
                            if case .ollamaReady(let m) = app.modelStatus { return m }
                            let cmd = GatekeeperModeState.shared.commanderModel
                            if cmd.contains("mlx") { return app.activeMlxModel }
                            return app.getOllamaModel()
                        },
                        set: { newVal in
                            GatekeeperModeState.shared.commanderModel = newVal
                            if newVal.contains("mlx") {
                                app.activeMlxModel = newVal
                                app.loadMLXModel(model: newVal)
                            } else {
                                app.setOllamaModel(newVal)
                                app.connectOllama()
                            }
                        }
                    )
                    
                    Picker("", selection: unifiedBinding) {
                        if !MLXRunner.popularModels.isEmpty {
                            Section(header: Text("MLX (Native)")) {
                                ForEach(MLXRunner.popularModels) { m in
                                    Text(m.displayName).tag(m.id)
                                }
                            }
                        }
                        if !app.ollamaModels.isEmpty {
                            Section(header: Text("Ollama (Local)")) {
                                ForEach(app.ollamaModels, id: \.self) { m in
                                    Text(m).tag(m)
                                }
                            }
                        } else {
                            Section(header: Text("Ollama (Not Connected)")) {
                                Text("gemma4:26b").tag("gemma4:26b")
                            }
                        }
                    }
                    .labelsHidden()
                    .frame(width: 170)
                    
                    Divider().frame(height: 16).opacity(0.5)
                    
                    // ── Auditor (監視役) Settings ──
                    Toggle(isOn: $app.isAuditorEnabled) {
                        Text("監視 (Auditor)")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(app.isAuditorEnabled ? Color.yellow : Color.gray)
                    }
                    .toggleStyle(.checkbox)
                    
                    if app.isAuditorEnabled {
                        if app.ollamaModels.isEmpty {
                            TextField("llama3.1:8b", text: $app.activeAuditorModel)
                                .textFieldStyle(.roundedBorder)
                                .font(.system(size: 11, design: .monospaced))
                                .frame(width: 110)
                        } else {
                            Picker("", selection: $app.activeAuditorModel) {
                                ForEach(app.ollamaModels, id: \.self) { m in
                                    Text(m).tag(m)
                                }
                            }
                            .labelsHidden()
                            .frame(width: 120)
                        }
                    }
                    
                    Divider().frame(height: 16).opacity(0.5)
                    
                    // Active Backend Badge
                    let isOllama: Bool = {
                        if case .ollamaReady = app.modelStatus { return true }
                        return false
                    }()
                    Text(isOllama ? "OLLAMA" : "MLX")
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundStyle(Color(red: 0.15, green: 0.15, blue: 0.18))
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(
                            isOllama
                                ? Color(red: 0.45, green: 0.9, blue: 0.6)   // green for Ollama
                                : Color(red: 0.65, green: 0.5, blue: 1.0),  // purple for MLX
                            in: RoundedRectangle(cornerRadius: 3)
                        )
                    
                    if app.isMultimodalModel {
                        Text("👁")
                            .font(.system(size: 10))
                            .help("Multimodal — images supported")
                    }
                    
                    Divider().frame(height: 16).opacity(0.5)
                    
                    // ── Operation Mode Picker ──
                    // Gatekeeper is deliberately absent here: it is retired
                    // from the normal workflow (its IR round-trip costs
                    // accuracy for a risk enterprises now cover by contract).
                    // The mode still exists in the enum and remains settable
                    // via `applySetting(key: "operation_mode", ...)` so any
                    // user who had it enabled keeps a working escape hatch.
                    Picker("", selection: $app.operationMode) {
                        Text(OperationMode.automatic.displayName).tag(OperationMode.automatic)
                        Text(OperationMode.detailed.displayName).tag(OperationMode.detailed)
                    }
                    .labelsHidden()
                    .frame(width: 100)
                    .help("Agent Operation Mode")
                    
                    RateLimitStatusView()
                }
            }

            Spacer()

            // ── Stop button (visible only while generating) ───────────
            if app.isGenerating {
                Button {
                    app.cancelGeneration()
                } label: {
                    HStack(spacing: 5) {
                        Image(systemName: "stop.fill").font(.system(size: 11))
                        Text(app.t("Stop", "停止")).font(.system(size: 11, weight: .semibold))
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Color(red: 0.8, green: 0.2, blue: 0.2))
                    )
                    .contentShape(Rectangle())
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .transition(.scale.combined(with: .opacity))
            }

            // ── Send button ───────────────────────────────────────────
            if !app.isGenerating {
                Button { sendMessage() } label: {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 13))
                        .foregroundStyle(
                            (inputText.isEmpty && app.attachedImages.isEmpty && app.attachedFiles.isEmpty)
                            ? Color(red: 0.4, green: 0.4, blue: 0.5)
                            : Color(red: 0.4, green: 0.7, blue: 1.0)
                        )
                        .padding(8)
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty
                          && app.attachedImages.isEmpty
                          && app.attachedFiles.isEmpty)
            }
        }
        .padding(.horizontal, 10).padding(.vertical, 4)
        .background(Color(red: 0.15, green: 0.15, blue: 0.19))
        .animation(.easeInOut(duration: 0.15), value: app.isGenerating)
    }

    // MARK: - Input bar

    private var inputBar: some View {
        VStack(spacing: 0) {
            // ── Attachment preview strip ──────────────────────────────
            if !app.attachedImages.isEmpty || !app.attachedFiles.isEmpty {
                attachmentStrip
                Divider().opacity(0.3)
            }

            // ── IDE Fix mode banner / normal file badge ───────────────
            if app.selfFixMode {
                // Persistent IDE Fix banner — always visible while mode is active
                HStack(spacing: 8) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(Color(red: 1.0, green: 0.65, blue: 0.15))

                    Text("🔧 IDE Fix Mode")
                        .font(.system(size: 11, weight: .bold, design: .monospaced))
                        .foregroundStyle(Color(red: 1.0, green: 0.75, blue: 0.30))

                    if let file = app.selectedFile {
                        Text("▸ \(file.lastPathComponent)")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(Color(red: 0.9, green: 0.6, blue: 0.2).opacity(0.8))
                            .lineLimit(1)
                            .truncationMode(.middle)
                    } else {
                        Text("▸ IDE Source Index")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(Color(red: 0.9, green: 0.6, blue: 0.2).opacity(0.8))
                    }

                    Spacer()

                    // Exit button — explicitly exits IDE Fix mode
                    Button {
                        app.selfFixMode = false
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "xmark")
                                .font(.system(size: 9, weight: .bold))
                            Text(app.t("Exit Mode", "モード終了"))
                                .font(.system(size: 10, weight: .semibold))
                        }
                        .foregroundStyle(Color(red: 1.0, green: 0.65, blue: 0.15))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(
                            RoundedRectangle(cornerRadius: 4)
                                .stroke(Color(red: 1.0, green: 0.65, blue: 0.15).opacity(0.5), lineWidth: 1)
                        )
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(
                    LinearGradient(
                        colors: [
                            Color(red: 0.28, green: 0.18, blue: 0.04),
                            Color(red: 0.22, green: 0.14, blue: 0.02)
                        ],
                        startPoint: .leading, endPoint: .trailing
                    )
                )
                .overlay(
                    Rectangle()
                        .fill(Color(red: 1.0, green: 0.60, blue: 0.10).opacity(0.6))
                        .frame(height: 1),
                    alignment: .bottom
                )
            }

            // ── Text input + action buttons ───────────────────────────
            HStack(alignment: .bottom, spacing: 8) {

                // ── Fixed-width action button group ──────────────────────
                // IMPORTANT: fixed frame prevents Self Fix toggle from
                // shifting the TextEditor to the right
                HStack(spacing: 2) {
                    // Attach image
                    Button {
                        let picked = AttachmentManager.pickImages()
                        app.attachedImages.append(contentsOf: picked)
                    } label: {
                        Image(systemName: "photo.badge.plus")
                            .font(.system(size: 15))
                            .foregroundStyle(
                                app.isMultimodalModel
                                ? Color(red: 0.6, green: 0.8, blue: 1.0)
                                : Color(red: 0.35, green: 0.35, blue: 0.45)
                            )
                            .frame(width: 26, height: 26)
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .disabled(!app.isMultimodalModel)
                    .help(app.isMultimodalModel ? app.t("Attach image", "画像を添付") : app.t("Multimodal not supported by this model", "このモデルはマルチモーダル非対応です"))

                    // Attach file
                    Button {
                        let picked = AttachmentManager.pickFiles()
                        app.attachedFiles.append(contentsOf: picked)
                    } label: {
                        Image(systemName: "paperclip")
                            .font(.system(size: 15))
                            .foregroundStyle(Color(red: 0.6, green: 0.7, blue: 0.85))
                            .frame(width: 26, height: 26)
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .help(app.t("Attach file", "ファイルを添付"))
                    
                    // ── Visual Anchor Insertion ──
                    Button {
                        showVisualAnchorPrompt = true
                    } label: {
                        ZStack(alignment: .topTrailing) {
                            Image(systemName: "exclamationmark.lock.fill")
                                .font(.system(size: 15))
                                .foregroundStyle(app.persistentTaskAnchor.isEmpty ? Color(red: 0.9, green: 0.3, blue: 0.3) : Color.orange)
                                .frame(width: 26, height: 26)
                            
                            if !app.persistentTaskAnchor.isEmpty {
                                Circle().fill(Color.orange).frame(width: 6, height: 6).offset(x: -2, y: 2)
                            }
                        }
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .help(app.t("Insert Visual Anchor", "Visual Anchorを注入"))
                    .popover(isPresented: $showVisualAnchorPrompt) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Visual Anchor 注入")
                                .font(.headline)
                            Text("1回のみ注入するか、毎ターン自動注入（Persistent Task）するか選択できます。\n空欄でSet Persistentを押すと解除されます。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            
                            TextEditor(text: $visualAnchorText)
                                .frame(width: 300, height: 100)
                                .font(.system(size: 12, design: .monospaced))
                                .border(Color.gray.opacity(0.3))
                            
                            HStack {
                                Spacer()
                                Button("Cancel") {
                                    showVisualAnchorPrompt = false
                                }
                                Button(app.persistentTaskAnchor.isEmpty ? "Set Persistent" : "Clear Persistent") {
                                    app.persistentTaskAnchor = visualAnchorText
                                    showVisualAnchorPrompt = false
                                    visualAnchorText = ""
                                }
                                .buttonStyle(.bordered)
                                .tint(app.persistentTaskAnchor.isEmpty ? .orange : .gray)
                                
                                Button("Inject Once") {
                                    guard !visualAnchorText.isEmpty else { return }
                                    let anchorBase64 = CognitiveAnchorEngine.shared.getCustomAnchor(text: visualAnchorText)
                                    // Base64からローカルファイルに書き出して添付する
                                    if let data = Data(base64Encoded: anchorBase64),
                                       let img = NSImage(data: data) {
                                        let tempUrl = FileManager.default.temporaryDirectory.appendingPathComponent("anchor_\(UUID().uuidString).png")
                                        if let tiff = img.tiffRepresentation,
                                           let bitmap = NSBitmapImageRep(data: tiff),
                                           let png = bitmap.representation(using: .png, properties: [:]) {
                                            try? png.write(to: tempUrl)
                                            let attached = AttachedImage(name: "VisualAnchor.png", url: tempUrl, nsImage: img)
                                            app.attachedImages.append(attached)
                                        }
                                    }
                                    showVisualAnchorPrompt = false
                                    visualAnchorText = ""
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(.red)
                            }
                        }
                        .padding()
                    }

                    // ── Agent Prompt Visual Anchor Insertion ──
                    Button {
                        showAgentPromptAnchorPrompt = true
                    } label: {
                        Image(systemName: "wand.and.stars")
                            .font(.system(size: 15))
                            .foregroundStyle(Color(red: 0.4, green: 0.8, blue: 0.9))
                            .frame(width: 26, height: 26)
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .help(app.t("Insert Instruction as Image", "テキスト指示を画像として注入"))
                    .popover(isPresented: $showAgentPromptAnchorPrompt) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Agent Instruction 注入")
                                .font(.headline)
                            Text("テキスト指示を画像に変換してAIのテキスト偏重を回避します。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            
                            TextEditor(text: $agentPromptAnchorText)
                                .frame(width: 300, height: 100)
                                .font(.system(size: 12, design: .monospaced))
                                .border(Color.gray.opacity(0.3))
                            
                            HStack {
                                Spacer()
                                Button("Cancel") {
                                    showAgentPromptAnchorPrompt = false
                                }
                                Button("Inject") {
                                    guard !agentPromptAnchorText.isEmpty else { return }
                                    let anchorBase64 = CognitiveAnchorEngine.shared.getUserPromptAnchor(text: agentPromptAnchorText)
                                    if let data = Data(base64Encoded: anchorBase64),
                                       let img = NSImage(data: data) {
                                        let tempUrl = FileManager.default.temporaryDirectory.appendingPathComponent("agent_anchor_\\(UUID().uuidString).png")
                                        if let tiff = img.tiffRepresentation,
                                           let bitmap = NSBitmapImageRep(data: tiff),
                                           let png = bitmap.representation(using: .png, properties: [:]) {
                                            try? png.write(to: tempUrl)
                                            let attached = AttachedImage(name: "InstructionAnchor.png", url: tempUrl, nsImage: img)
                                            app.attachedImages.append(attached)
                                        }
                                    }
                                    showAgentPromptAnchorPrompt = false
                                    agentPromptAnchorText = ""
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(.blue)
                            }
                        }
                        .padding()
                    }


                    // ── Self Fix — icon-only, fixed frame ────────────────
                    // Using just the icon + background color (no expanding text)
                    // so width never changes and TextEditor stays in place.
                    Button {
                        app.selfFixMode.toggle()
                    } label: {
                        Image(systemName: app.selfFixMode
                              ? "wrench.and.screwdriver.fill"
                              : "wrench.and.screwdriver")
                            .font(.system(size: 13))
                            .foregroundStyle(app.selfFixMode
                                             ? Color.black
                                             : Color(red: 0.55, green: 0.55, blue: 0.65))
                            .frame(width: 26, height: 26)
                            .background(
                                app.selfFixMode
                                    ? Color(red: 1.0, green: 0.65, blue: 0.15)
                                    : Color.white.opacity(0.06),
                                in: RoundedRectangle(cornerRadius: 5)
                            )
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .help(app.selfFixMode
                          ? app.t("Self Fix Mode ON — tap to disable", "Self Fix モード ON — タップで解除")
                          : app.t("Self Fix: auto-fix IDE source", "Self Fix: IDEソースを自己修正"))
                    // ── L3.5 OS Asset Build Button ──
                    @ObservedObject var assetVault = OSAssetMemoryVault.shared
                    
                    Button {
                        app.addSystemMessage(app.t("🔄 Starting L3.5 PC Asset Map generation...", "🔄 L3.5 PC資産マップの生成を開始します..."))
                        assetVault.scanBackground()
                    } label: {
                        Image(systemName: "macwindow.badge.plus")
                            .font(.system(size: 13))
                            .foregroundStyle(assetVault.isScanning ? Color.gray : Color(red: 0.35, green: 0.75, blue: 0.9))
                            .frame(width: 26, height: 26)
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .disabled(assetVault.isScanning)
                    .help(app.t("Generate L3.5 PC Asset Map", "PC内資産マップ(L3.5)を生成する"))
                    .onChange(of: assetVault.scanProgress) { newValue in
                        if !newValue.isEmpty {
                            app.addSystemMessage(newValue)
                        }
                    }
                }
                // FIXED width — never changes regardless of selfFixMode
                .frame(width: 142, alignment: .leading)

                // ── TextEditor + placeholder ───────────────────────────
                // Placeholder padding must match NSTextView's internal insets:
                //   lineFragmentPadding ≈ 5pt (leading)
                //   textContainerInset.y ≈ 5-7pt (top)
                ZStack(alignment: .topLeading) {
                    if inputText.isEmpty {
                        Text(app.selfFixMode
                             ? app.t("Fix this IDE… (Self Fix Mode)", "このIDEを修正… (Self Fix モード)")
                             : (app.selectedFile == nil
                                ? app.t("Ask VerantyxAgent anything…", "Ask VerantyxAgent anything…")
                                : app.t("Describe the changes you want…", "Describe the changes you want…")))
                            .font(.system(size: 13))
                            .foregroundStyle(
                                app.selfFixMode
                                    ? Color(red: 1.0, green: 0.65, blue: 0.15).opacity(0.55)
                                    : Color(red: 0.38, green: 0.38, blue: 0.45)
                            )
                            // Matches NSTextView's default lineFragmentPadding (5) + inset (~6)
                            .padding(.leading, 5)
                            .padding(.top, 6)
                            // No pointer interaction so clicks pass through to TextEditor
                            .allowsHitTesting(false)
                    }
                    ChatInputTextView(
                        text: $inputText,
                        onSend: { sendMessage() },
                        isFocused: $inputFocused
                    )
                    .frame(maxWidth: .infinity, minHeight: 44, maxHeight: 110)
                }
            }
            .padding(.horizontal, 10).padding(.vertical, 6)
        }
        .background(
            app.selfFixMode
                ? Color(red: 0.22, green: 0.16, blue: 0.08)  // warm amber tint in self-fix mode
                : Color(red: 0.17, green: 0.17, blue: 0.21),
            in: RoundedRectangle(cornerRadius: 16, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(app.selfFixMode
                        ? Color(red: 1.0, green: 0.60, blue: 0.10).opacity(0.8)
                        : Color.white.opacity(0.12), lineWidth: 1)
        )
        .padding(.horizontal, 16)
        .padding(.bottom, 16)
        .padding(.top, 8)
        .animation(.easeInOut(duration: 0.2), value: app.selfFixMode)
        // Drag-and-drop images onto the input bar
        .onDrop(of: [.image, .fileURL], isTargeted: nil) { providers in
            handleDrop(providers: providers)
            return true
        }
    }

    // MARK: - Attachment Strip

    private var attachmentStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                // Image thumbnails
                ForEach(app.attachedImages) { img in
                    ZStack(alignment: .topTrailing) {
                        img.swiftUIImage
                            .resizable().scaledToFill()
                            .frame(width: 56, height: 56)
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                            .overlay(
                                RoundedRectangle(cornerRadius: 6)
                                    .stroke(Color.white.opacity(0.15), lineWidth: 0.5)
                            )

                        Button {
                            app.attachedImages.removeAll { $0.id == img.id }
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 13))
                                .foregroundStyle(.white)
                                .background(Circle().fill(Color.black.opacity(0.55)))
                        }
                        .contentShape(Rectangle())
                        .buttonStyle(.plain)
                        .offset(x: 4, y: -4)
                    }
                }

                // File chips
                ForEach(app.attachedFiles, id: \.absoluteString) { url in
                    HStack(spacing: 5) {
                        Image(systemName: FileIcons.icon(for: url))
                            .font(.system(size: 10))
                            .foregroundStyle(FileIcons.color(for: url))
                        Text(url.lastPathComponent)
                            .font(.system(size: 10, design: .monospaced))
                            .lineLimit(1)
                        Button {
                            app.attachedFiles.removeAll { $0 == url }
                        } label: {
                            Image(systemName: "xmark").font(.system(size: 8))
                        }
                        .contentShape(Rectangle())
                        .buttonStyle(.plain)
                    }
                    .foregroundStyle(Color(red: 0.75, green: 0.75, blue: 0.85))
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(
                        RoundedRectangle(cornerRadius: 5)
                            .fill(Color.white.opacity(0.07))
                    )
                }
            }
            .padding(.horizontal, 10).padding(.vertical, 6)
        }
    }

    // MARK: - Drag-and-drop handler

    private func handleDrop(providers: [NSItemProvider]) {
        for provider in providers {
            if provider.hasItemConformingToTypeIdentifier("public.image") {
                _ = provider.loadDataRepresentation(forTypeIdentifier: "public.image") { data, _ in
                    guard let data, let img = AttachmentManager.loadImage(from: data) else { return }
                    Task { @MainActor in
                        guard app.isMultimodalModel else { return }
                        app.attachedImages.append(img)
                    }
                }
            } else if provider.hasItemConformingToTypeIdentifier("public.file-url") {
                _ = provider.loadItem(forTypeIdentifier: "public.file-url") { item, _ in
                    guard let data = item as? Data,
                          let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                    Task { @MainActor in
                        // If it's an image and model supports multimodal, attach as image
                        let imgExts: Set<String> = ["png","jpg","jpeg","gif","webp","heic","tiff"]
                        if imgExts.contains(url.pathExtension.lowercased()), app.isMultimodalModel,
                           let img = AttachmentManager.loadImage(from: url) {
                            app.attachedImages.append(img)
                        } else {
                            app.attachedFiles.append(url)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !app.isGenerating else { return }
        inputText = ""          // ローカル state を即時クリア（@Published を触る前）
        app.sendMessage(with: text)
    }

    private var modelDisplayName: String {
        switch app.modelStatus {
        case .ollamaReady(let m):              return m
        case .mlxReady(let m):                 return m.components(separatedBy: "/").last ?? m
        case .anthropicReady(let m, _):        return m
        case .ready(let n):                    return n
        case .mlxDownloading(let m):           return "↓ \(m.components(separatedBy: "/").last ?? m)…"
        case .connecting:                      return "Connecting…"
        default:                               return "Select model ↓"
        }
    }

    private func extractThinking(from text: String) -> String {
        let pattern = #"<think>([\s\S]*?)</think>"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let range = Range(match.range(at: 1), in: text)
        else { return "" }
        return String(text[range]).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

// MARK: - AgentMessageView

struct AgentMessageView: View, Equatable {
    let message: ChatMessage

    // Equatable: SwiftUI の .equatable() モディファイアがこれを使って
    // content/role が同一なら再描画をスキップする
    static func == (lhs: AgentMessageView, rhs: AgentMessageView) -> Bool {
        lhs.message.id == rhs.message.id &&
        lhs.message.content == rhs.message.content &&
        lhs.message.role == rhs.message.role
    }

    // Parse <think>...</think> from content
    private var parts: [(isThinking: Bool, text: String)] {
        guard message.role == .assistant else {
            return [(false, message.content)]
        }
        var result: [(Bool, String)] = []
        
        // 1. Fully closed think tags
        let pattern = #"<think>([\s\S]*?)</think>"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return [(false, message.content)]
        }
        var cursor = message.content.startIndex
        let matches = regex.matches(in: message.content, range: NSRange(message.content.startIndex..., in: message.content))

        for match in matches {
            if let r = Range(match.range, in: message.content), r.lowerBound > cursor {
                let text = String(message.content[cursor..<r.lowerBound]).trimmingCharacters(in: .newlines)
                if !text.isEmpty { result.append((false, text)) }
            }
            if let r2 = Range(match.range(at: 1), in: message.content) {
                result.append((true, String(message.content[r2])))
            }
            if let r = Range(match.range, in: message.content) { cursor = r.upperBound }
        }
        
        // 2. Unclosed think tag (streaming)
        if cursor < message.content.endIndex {
            let remainder = String(message.content[cursor...])
            if let unclosedRange = remainder.range(of: "<think>") {
                // Text before the <think>
                let before = String(remainder[..<unclosedRange.lowerBound]).trimmingCharacters(in: .newlines)
                if !before.isEmpty { result.append((false, before)) }
                
                // The unclosed <think> content
                let thinking = String(remainder[unclosedRange.upperBound...]).trimmingCharacters(in: .newlines)
                // Append as thinking even if it's empty (to show the thinking indicator)
                result.append((true, thinking))
            } else {
                let text = remainder.trimmingCharacters(in: .newlines)
                if !text.isEmpty { result.append((false, text)) }
            }
        }
        return result.isEmpty ? [(false, message.content)] : result
    }

    @State private var isHovered   = false
    @State private var copied       = false

    var body: some View {
        switch message.role {
        case .user:
            HStack(alignment: .top, spacing: 6) {
                // Copy button — always visible (dimmed when not hovered)
                copyButton
                    .opacity(isHovered ? 1.0 : 0.35)
                Spacer(minLength: 20)
                Text(message.content)
                    .font(.system(size: 13))
                    .foregroundStyle(Color.white)
                    .textSelection(.enabled)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color(red: 0.2, green: 0.35, blue: 0.7),
                                in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .onHover { isHovered = $0 }
            .animation(.easeInOut(duration: 0.12), value: isHovered)

        case .assistant:
            HStack(alignment: .top, spacing: 10) {
                // Agent avatar
                ZStack {
                    Circle().fill(Color(red: 0.2, green: 0.4, blue: 0.8))
                    Image(systemName: "atom")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(.white)
                }
                .frame(width: 28, height: 28)

                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text("VerantyxAgent")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))
                        Spacer()
                        // Copy button — always visible (dimmed when not hovered)
                        copyButton
                            .opacity(isHovered ? 1.0 : 0.35)
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(parts.enumerated()), id: \.offset) { _, part in
                            if part.isThinking {
                                thinkingTag(part.text)
                            } else {
                                plainText(part.text)
                            }
                        }
                    }
                }
                Spacer(minLength: 20)
            }
            .onHover { isHovered = $0 }
            .animation(.easeInOut(duration: 0.12), value: isHovered)

        case .system:
            HStack(spacing: 6) {
                Image(systemName: "info.circle").font(.caption2)
                Text(message.content)
                    .font(.system(size: 11))
                    .textSelection(.enabled)
            }
            .foregroundStyle(Color(red: 0.45, green: 0.45, blue: 0.6))
            .frame(maxWidth: .infinity, alignment: .center)
        }
    }

    // MARK: - Copy button

    private var copyButton: some View {
        Button {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(message.content, forType: .string)
            withAnimation { copied = true }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                withAnimation { copied = false }
            }
        } label: {
            Image(systemName: copied ? "checkmark" : "doc.on.doc")
                .font(.system(size: 10))
                .foregroundStyle(copied
                    ? Color(red: 0.3, green: 0.9, blue: 0.5)
                    : Color(red: 0.45, green: 0.45, blue: 0.6))
                .frame(width: 22, height: 22)
                .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 5))
        }
        .contentShape(Rectangle())
        .buttonStyle(.plain)
        .help(copied ? L("Copied!", "コピーしました！") : L("Copy message", "メッセージをコピー"))
    }

    private func thinkingTag(_ text: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Text("<think>")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(Color(red: 0.35, green: 0.75, blue: 0.70))
            }
            Text(text)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Color(red: 0.35, green: 0.85, blue: 0.80))
                .lineSpacing(3)
                .textSelection(.enabled)
            Text("</think>")
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Color(red: 0.35, green: 0.75, blue: 0.70))
        }
        .padding(8)
        .background(Color(red: 0.12, green: 0.22, blue: 0.22).opacity(0.6), in: RoundedRectangle(cornerRadius: 6))
    }

    private func plainText(_ text: String) -> some View {
        AssistantText(content: text)
            .font(.system(size: 13))
    }
}

// MARK: - AgentThinkingView (animated)

struct AgentThinkingView: View {
    @State private var thinkingText = "Analyzing…"

    private let thinkingSteps = [
        "Reading context files…",
        "Analyzing project structure…",
        "Running steps…",
        "Diff generation…",
        "Verifying changes…"
    ]
    @State private var stepIndex = 0

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            ZStack {
                Circle().fill(Color(red: 0.2, green: 0.4, blue: 0.8))
                Image(systemName: "atom")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(.white)
            }
            .frame(width: 28, height: 28)

            VStack(alignment: .leading, spacing: 4) {
                Text("VerantyxAgent")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))

                VStack(alignment: .leading, spacing: 2) {
                    Text("<think>")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Color(red: 0.35, green: 0.75, blue: 0.70))

                    ForEach(Array(thinkingSteps[0...stepIndex].enumerated()), id: \.offset) { i, step in
                        HStack(spacing: 6) {
                            Image(systemName: i < stepIndex ? "checkmark" : "circle.fill")
                                .font(.system(size: 8))
                                .foregroundStyle(i < stepIndex
                                    ? Color(red: 0.4, green: 0.85, blue: 0.5)
                                    : Color(red: 0.4, green: 0.7, blue: 1.0))
                            Text((i < stepIndex ? "- " : "+ ") + step)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(i < stepIndex
                                    ? Color(red: 0.35, green: 0.85, blue: 0.5).opacity(0.8)
                                    : Color(red: 0.35, green: 0.85, blue: 0.80))
                        }
                    }

                    ProgressView()
                        .controlSize(.small)
                }
                .padding(8)
                .background(Color(red: 0.12, green: 0.22, blue: 0.22).opacity(0.6), in: RoundedRectangle(cornerRadius: 6))
            }
        }
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 1.2, repeats: true) { _ in
                withAnimation {
                    if stepIndex < thinkingSteps.count - 1 { stepIndex += 1 }
                }
            }
        }
    }
}

// MARK: - ChatInputTextView (IME-aware Enter-to-send)
// NSViewRepresentable wrapping NSTextView for reliable Japanese IME handling.
//
// Behavior:
//   • Enter (no modifier):
//       - If IME has markedText (未確定文字) → confirms composition (default NSTextView behavior)
//       - If no markedText → sends the message
//   • Shift+Enter: inserts newline (multi-line input)
//   • ⌘+Enter: also sends the message (legacy shortcut)

struct ChatInputTextView: NSViewRepresentable {
    @Binding var text: String
    var onSend: () -> Void
    var isFocused: FocusState<Bool>.Binding

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autohidesScrollers = true
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = false

        let textView = IMEAwareTextView()
        textView.delegate = context.coordinator
        textView.onSend = onSend
        textView.isRichText = false
        textView.allowsUndo = true
        textView.font = NSFont.systemFont(ofSize: 13)
        textView.textColor = NSColor(red: 0.88, green: 0.88, blue: 0.92, alpha: 1.0)
        textView.backgroundColor = .clear
        textView.drawsBackground = false
        textView.minSize = NSSize(width: 0, height: 0)
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.textContainerInset = NSSize(width: 0, height: 5)
        textView.textContainer?.lineFragmentPadding = 5
        textView.textContainer?.widthTracksTextView = true

        // Caret color
        textView.insertionPointColor = NSColor(red: 0.4, green: 0.7, blue: 1.0, alpha: 1.0)

        scrollView.documentView = textView
        context.coordinator.textView = textView

        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? IMEAwareTextView else { return }

        // ── GUARD 1: Never interrupt active IME composition ──────────
        // Setting textView.string during composition destroys the markedText.
        if textView.hasMarkedText() {
            textView.onSend = onSend
            return
        }

        // ── GUARD 2: Prevent feedback loop ──────────────────────────
        // textDidChange sets parent.text → triggers updateNSView → must not set string again
        let coordinator = context.coordinator
        guard !coordinator.isSyncingToBinding else {
            textView.onSend = onSend
            return
        }

        // ── Only apply external changes (e.g., clearing after send) ─
        if textView.string != text {
            coordinator.isSyncingFromBinding = true
            textView.string = text
            textView.setSelectedRange(NSRange(location: textView.string.count, length: 0))
            coordinator.isSyncingFromBinding = false
        }

        textView.onSend = onSend
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, NSTextViewDelegate {
        var parent: ChatInputTextView
        weak var textView: IMEAwareTextView?

        /// True while textDidChange is propagating to the binding.
        /// Prevents updateNSView from re-entering.
        var isSyncingToBinding = false

        /// True while updateNSView is writing to textView.string.
        /// Prevents textDidChange from re-entering.
        var isSyncingFromBinding = false

        init(parent: ChatInputTextView) {
            self.parent = parent
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            // Don't propagate if WE set the string programmatically
            guard !isSyncingFromBinding else { return }

            isSyncingToBinding = true
            parent.text = textView.string
            isSyncingToBinding = false
        }

        func textDidBeginEditing(_ notification: Notification) {
            parent.isFocused.wrappedValue = true
        }

        func textDidEndEditing(_ notification: Notification) {
            parent.isFocused.wrappedValue = false
        }
    }
}

// MARK: - IMEAwareTextView
// Custom NSTextView subclass that intercepts Enter key events
// and checks IME composition state before deciding to send.

final class IMEAwareTextView: NSTextView {
    var onSend: (() -> Void)?

    override func insertNewline(_ sender: Any?) {
        // ── IME composition active → let default behavior confirm it ──
        if hasMarkedText() {
            super.insertNewline(sender)
            return
        }

        // ── Shift+Enter → insert actual newline (multi-line input) ──
        if NSEvent.modifierFlags.contains(.shift) {
            super.insertNewline(sender)
            return
        }

        // ── Plain Enter (no IME, no Shift) → send message ──
        onSend?()
    }

    // Also support ⌘+Enter as a legacy send shortcut
    override func keyDown(with event: NSEvent) {
        let now = Date()
        Task { @MainActor in
            if let app = AppState.shared {
                if let last = app.lastKeystrokeTime {
                    let interval = now.timeIntervalSince(last)
                    if interval < 2.0 { // only capture continuous typing
                        var current = app.lastKeyboardEntropy ?? []
                        current.append(interval)
                        if current.count > 100 { current.removeFirst(current.count - 100) }
                        app.lastKeyboardEntropy = current
                    }
                }
                app.lastKeystrokeTime = now
            }
        }

        if event.keyCode == 36,  // Return key
           event.modifierFlags.contains(.command) {
            onSend?()
            return
        }
        super.keyDown(with: event)
    }
}

// MARK: - RateLimitStatusView

struct RateLimitStatusView: View {
    @EnvironmentObject var app: AppState
    
    var body: some View {
        TimelineView(.periodic(from: .now, by: 1.0)) { timeline in
            HStack(spacing: 6) {
                // Rate Limit Cooldown
                if let cooldown = app.searchCooldownUntil {
                    let remaining = cooldown.timeIntervalSince(timeline.date)
                    if remaining > 0 {
                        HStack(spacing: 4) {
                            Image(systemName: "timer")
                            Text("Cooldown: \(Int(remaining))s")
                        }
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Color.red.opacity(0.8), in: RoundedRectangle(cornerRadius: 3))
                    }
                }
                
                // Entropy Freshness
                if let ts = app.lastEntropyTimestamp {
                    let elapsed = timeline.date.timeIntervalSince(ts)
                    let remaining = 300 - elapsed
                    if remaining > 0 {
                        HStack(spacing: 4) {
                            Image(systemName: "shield.fill")
                            Text("Fresh: \(Int(remaining))s")
                        }
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Color.green.opacity(0.8), in: RoundedRectangle(cornerRadius: 3))
                    }
                }
            }
        }
    }
}
import SwiftUI
import AppKit

// MARK: - LiveTerminalView
// The in-line Zero-Translation Steering Terminal.
// Displayed inside the chat stream (or as an island) when the agent is inferring/executing.

struct LiveTerminalView: View {
    @EnvironmentObject var app: AppState
    @State private var commandInput: String = ""
    @FocusState private var isInputFocused: Bool
    
    // Auto-scroll anchor
    @Namespace private var bottomID

    var body: some View {
        VStack(spacing: 0) {
            // ── Header ──
            HStack(spacing: 8) {
                Circle()
                    .fill(Color(red: 0.3, green: 1.0, blue: 0.5))
                    .frame(width: 6, height: 6)
                    .opacity(0.9)
                
                Text("LIVE TERMINAL — STEERING")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundStyle(Color(red: 0.5, green: 0.9, blue: 0.6))
                
                Spacer()
                
                Text("Ctrl+C to Abort")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(Color.gray)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(Color(red: 0.08, green: 0.10, blue: 0.12))
            
            Divider().opacity(0.3)
            
            // ── Log Body ──
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(app.logStore.entries) { entry in
                            HStack(alignment: .top, spacing: 6) {
                                Text(entry.prefix)
                                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                                    .foregroundStyle(colorForKind(entry.kind))
                                
                                Text(entry.text)
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(Color(red: 0.85, green: 0.85, blue: 0.9))
                            }
                            .padding(.horizontal, 8)
                        }
                        
                        // Invisible anchor for auto-scroll
                        Color.clear.frame(height: 1).id(bottomID)
                    }
                    .padding(.vertical, 4)
                }
                .frame(maxHeight: 200)
                .onChange(of: app.logStore.entries.count) { _ in
                    withAnimation(.easeOut(duration: 0.1)) {
                        proxy.scrollTo(bottomID, anchor: .bottom)
                    }
                }
            }
            .background(Color(red: 0.06, green: 0.08, blue: 0.10))
            
            Divider().opacity(0.3)
            
            // ── Command Input (Steering) ──
            HStack(spacing: 6) {
                Text("❯")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .foregroundStyle(Color(red: 0.3, green: 1.0, blue: 0.5))
                
                TextField("vtx-steer (or Ctrl+C)...", text: $commandInput)
                    .textFieldStyle(.plain)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.white)
                    .focused($isInputFocused)
                    .onSubmit {
                        submitSteeringCommand()
                    }
                
                Button {
                    app.sendSteeringCommand("^C")
                } label: {
                    Text("^C")
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundStyle(.red)
                        .padding(.horizontal, 4).padding(.vertical, 2)
                        .background(Color.red.opacity(0.2), in: RoundedRectangle(cornerRadius: 4))
                }
                .buttonStyle(.plain)
                .help("Send SIGINT (Interrupt Agent)")
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(Color(red: 0.08, green: 0.10, blue: 0.12))
        }
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.white.opacity(0.15), lineWidth: 1)
        )
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }
    
    private func submitSteeringCommand() {
        let cmd = commandInput.trimmingCharacters(in: .whitespaces)
        guard !cmd.isEmpty else { return }
        app.sendSteeringCommand(cmd)
        commandInput = ""
    }
    
    private func colorForKind(_ kind: AppState.ProcessLogEntry.Kind) -> Color {
        switch kind {
        case .memory:   return Color(red: 0.40, green: 0.90, blue: 0.60)
        case .tool:     return Color(red: 0.40, green: 0.80, blue: 1.00)
        case .browser:  return Color(red: 0.90, green: 0.70, blue: 0.30)
        case .thinking: return Color(red: 0.80, green: 0.80, blue: 1.00)
        case .system:   return Color(red: 0.60, green: 0.60, blue: 0.60)
        case .perf:     return Color(red: 0.30, green: 1.00, blue: 0.50)
        }
    }
}
