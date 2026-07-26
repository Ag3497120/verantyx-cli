import SwiftUI

// MARK: - SettingsView
// Functional settings — all controls are wired to live AppState values.
// Tabs: Model | API Keys | Tools | Agent | Memory | Privacy | MCP

struct SettingsView: View {
    @EnvironmentObject var app: AppState
    @State private var selectedTab: SettingsTab = .model
    @State private var testingConnection = false
    @State private var connectionTestResult: String? = nil
    @State private var testingAnthropic = false
    @State private var anthropicTestResult: String? = nil
    @State private var showAnthropicKey = false
    @State private var showOpenAIKey = false
    @State private var showDeepSeekKey = false
    @State private var showGeminiKey = false
    @State private var showAssetMap = false
    @ObservedObject private var updater = SelfUpdater.shared
    @ObservedObject private var vault = OSAssetMemoryVault.shared

    enum SettingsTab: String, CaseIterable {
        case general = "General"
        case model   = "Model"
        case apiKeys = "API Keys"
        case tools   = "Tools"
        case agent   = "Agent"
        case memory  = "Memory"
        case privacy = "Privacy"
        case mcp     = "MCP"
        case bitnet  = "BitNet"

        var icon: String {
            switch self {
            case .general: return "gearshape"
            case .model:   return "cpu"
            case .apiKeys: return "key.fill"
            case .tools:   return "puzzlepiece.extension"
            case .agent:   return "bolt.circle"
            case .memory:  return "brain"
            case .privacy: return "lock.shield"
            case .mcp:     return "network"
            case .bitnet:  return "cpu.fill"
            }
        }

        var color: Color {
            switch self {
            case .general: return Color(red: 0.7, green: 0.7, blue: 0.8)
            case .model:   return Color(red: 0.4, green: 0.7, blue: 1.0)
            case .apiKeys: return Color(red: 0.9, green: 0.7, blue: 0.3)
            case .tools:   return Color(red: 0.6, green: 0.4, blue: 1.0)
            case .agent:   return Color(red: 0.3, green: 0.9, blue: 0.6)
            case .memory:  return Color(red: 0.8, green: 0.5, blue: 1.0)
            case .privacy: return Color(red: 0.4, green: 0.9, blue: 0.5)
            case .mcp:     return Color(red: 0.3, green: 0.8, blue: 1.0)
            case .bitnet:  return Color(red: 0.7, green: 0.4, blue: 1.0)
            }
        }
    }

    var onDismiss: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 0) {

            // ── Header bar ─────────────────────────────────────────────────
            HStack(spacing: 10) {
                // Close button
                Button {
                    onDismiss?()
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Color(red: 0.6, green: 0.6, blue: 0.7))
                        .frame(width: 22, height: 22)
                        .background(Color.white.opacity(0.07), in: Circle())
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .keyboardShortcut(.escape, modifiers: [])
                .help(app.t("Close Settings (Esc)", "設定を閉じる (Esc)"))

                Spacer()

                Text("Settings")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color(red: 0.75, green: 0.75, blue: 0.88))

                Spacer()

                // Version badge
                Text("v0.1")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(.quaternary)
                    .frame(width: 22)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Color(red: 0.10, green: 0.10, blue: 0.13))
            .overlay(Rectangle().fill(Color.white.opacity(0.07)).frame(height: 0.5), alignment: .bottom)

            // ── Main body (sidebar + content) — FIXED HEIGHT ───────────────
            HStack(spacing: 0) {

                // ── Sidebar ─────────────────────────────────────────────────
                VStack(alignment: .leading, spacing: 2) {
                    Text("SETTINGS")
                        .font(.system(size: 9, weight: .semibold, design: .monospaced))
                        .foregroundStyle(.tertiary)
                        .padding(.horizontal, 12)
                        .padding(.top, 14)
                        .padding(.bottom, 6)

                    ForEach(SettingsTab.allCases, id: \.self) { tab in
                        Button {
                            // Do NOT animate size — just switch content
                            selectedTab = tab
                        } label: {
                            HStack(spacing: 8) {
                                Image(systemName: tab.icon)
                                    .font(.system(size: 11))
                                    .frame(width: 16)
                                    .foregroundStyle(selectedTab == tab ? tab.color : .secondary)
                                Text(tab.rawValue)
                                    .font(.system(size: 12, weight: .medium))

                                if tab == .apiKeys &&
                                   (app.anthropicApiKey.isEmpty || app.activeAnthropicModel.isEmpty) {
                                    Spacer()
                                    Circle()
                                        .fill(Color(red: 0.9, green: 0.4, blue: 0.2))
                                        .frame(width: 6, height: 6)
                                }
                                // BitNet not-installed indicator
                                if tab == .bitnet {
                                    let gkStatus = BitNetEngineManager.shared.status
                                    if case .notInstalled = gkStatus {
                                        Spacer()
                                        Circle()
                                            .fill(Color(red: 0.7, green: 0.4, blue: 1.0))
                                            .frame(width: 6, height: 6)
                                    }
                                }
                            }
                            .foregroundStyle(selectedTab == tab ? .white : Color(red: 0.6, green: 0.6, blue: 0.7))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(
                                selectedTab == tab
                                    ? tab.color.opacity(0.15)
                                    : Color.clear,
                                in: RoundedRectangle(cornerRadius: 6)
                            )
                            .overlay(
                                selectedTab == tab
                                    ? RoundedRectangle(cornerRadius: 6)
                                        .strokeBorder(tab.color.opacity(0.3), lineWidth: 0.5)
                                    : nil
                            )
                        }
                        .contentShape(Rectangle())
                        .buttonStyle(.plain)
                        .padding(.horizontal, 6)
                    }

                    Spacer()
                }
                // FIXED width — tab clicks must NOT change sidebar size
                .frame(width: 155, alignment: .topLeading)
                .background(Color(red: 0.09, green: 0.09, blue: 0.12))

                Divider().opacity(0.3)

                // ── Content area — FIXED width, scrolls internally ──────────
                // All tabs use the same ScrollView+VStack structure so the
                // container size never changes between tab switches.
                // (MCPView was replaced by mcpSettings to avoid HSplitView
                //  layout conflicts inside the fixed 525pt panel width.)
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        switch selectedTab {
                        case .general: generalSettings
                        case .model:   modelSettings
                        case .apiKeys: apiKeysSettings
                        case .tools:   toolsSettings
                        case .agent:   agentSettings
                        case .memory:  memorySettings
                        case .privacy: privacySettings
                        case .mcp:     mcpSettings
                        case .bitnet:  bitnetSettings
                        }
                    }
                    .padding(22)
                    .frame(width: 521, alignment: .topLeading)
                }
                // FIXED width — prevents any expansion when scrolling content
                .frame(width: 525, alignment: .topLeading)
                .background(Color(red: 0.11, green: 0.11, blue: 0.15))
            }
            // This height = total 560 - 44 (header) - 46 (footer)
            .frame(width: 680, height: 470)

            // ── Footer bar ─────────────────────────────────────────────────
            HStack(spacing: 10) {
                Spacer()
                Button(app.t("Cancel", "キャンセル")) {
                    onDismiss?()
                }
                .keyboardShortcut(.escape, modifiers: [])
                .buttonStyle(.bordered)
                .controlSize(.regular)

                Button(app.t("Done", "完了")) {
                    onDismiss?()
                }
                .keyboardShortcut(.return, modifiers: [.command])
                .buttonStyle(.borderedProminent)
                .controlSize(.regular)
                .tint(Color(red: 0.25, green: 0.45, blue: 0.85))
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color(red: 0.10, green: 0.10, blue: 0.13))
            .overlay(Rectangle().fill(Color.white.opacity(0.07)).frame(height: 0.5), alignment: .top)
        }
        // FIXED total size — prevents any window resize
        .frame(width: 680, height: 560)
        .background(Color(red: 0.10, green: 0.10, blue: 0.13))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .sheet(isPresented: $showAssetMap) { AssetMapView(vault: vault) }
    }

    // MARK: - General Settings (Language, Appearance)

    private var generalSettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("Software Update", icon: "arrow.triangle.2.circlepath")

            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Verantyx \(updater.currentVersion)")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(.white)
                            
                            if updater.isChecking {
                                Text("Checking for updates...")
                                    .font(.system(size: 11))
                                    .foregroundStyle(.secondary)
                            } else if updater.updateAvailable {
                                Text("Update available: v\(updater.latestVersion)")
                                    .font(.system(size: 11, weight: .semibold))
                                    .foregroundStyle(Color(red: 0.4, green: 0.9, blue: 0.5))
                            } else {
                                Text("Verantyx is up to date.")
                                    .font(.system(size: 11))
                                    .foregroundStyle(.secondary)
                            }
                            
                            if let error = updater.errorMessage {
                                Text(error)
                                    .font(.system(size: 10))
                                    .foregroundStyle(.red)
                            }
                        }
                        
                        Spacer()
                        
                        if updater.updateAvailable {
                            Button {
                                updater.downloadAndInstallUpdate()
                            } label: {
                                if updater.isDownloading {
                                    HStack(spacing: 6) {
                                        ProgressView().scaleEffect(0.6).frame(width: 12, height: 12)
                                        Text("Downloading...")
                                    }
                                } else {
                                    Text("Update Now")
                                        .bold()
                                }
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(Color(red: 0.3, green: 0.6, blue: 1.0))
                            .disabled(updater.isDownloading)
                        } else {
                            Button("Check for Updates") {
                                Task { await updater.checkForUpdates() }
                            }
                            .buttonStyle(.bordered)
                            .disabled(updater.isChecking)
                        }
                    }
                }
            }
            .onAppear {
                Task { await updater.checkForUpdates(background: true) }
            }

            sectionHeader("Language / 言語", icon: "globe")

            settingsCard {
                VStack(alignment: .leading, spacing: 16) {
                    // Language selector - big cards
                    HStack(spacing: 10) {
                        ForEach(AppState.UILanguage.allCases, id: \.self) { lang in
                            Button {
                                withAnimation(.easeInOut(duration: 0.15)) {
                                    app.appLanguage = lang
                                }
                            } label: {
                                VStack(spacing: 8) {
                                    Text(lang.flag)
                                        .font(.system(size: 28))
                                    Text(lang.rawValue)
                                        .font(.system(size: 11, weight: .semibold))
                                        .foregroundStyle(app.appLanguage == lang ? .white : Color(red: 0.55, green: 0.55, blue: 0.7))
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(
                                    app.appLanguage == lang
                                        ? Color(red: 0.25, green: 0.35, blue: 0.60).opacity(0.7)
                                        : Color.white.opacity(0.04),
                                    in: RoundedRectangle(cornerRadius: 8)
                                )
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8)
                                        .strokeBorder(
                                            app.appLanguage == lang
                                                ? Color(red: 0.4, green: 0.6, blue: 1.0).opacity(0.6)
                                                : Color.white.opacity(0.06),
                                            lineWidth: 1
                                        )
                                )
                            }
                            .contentShape(Rectangle())
                            .buttonStyle(.plain)
                        }
                    }

                    if app.appLanguage == .system {
                        HStack(spacing: 6) {
                            Image(systemName: "info.circle")
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                            Text("System language: \(Locale.current.localizedString(forLanguageCode: Locale.current.language.languageCode?.identifier ?? "en") ?? "Unknown")")
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            sectionHeader("Appearance", icon: "paintbrush")

            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    rowLabel("Theme") {
                        Text("Dark (fixed)")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                    Text("Verantyx uses a fixed high-contrast dark theme optimised for code editing.")
                        .font(.system(size: 10)).foregroundStyle(.tertiary)

                    Divider().opacity(0.2)

                    rowLabel("Font size (code)") {
                        Text("\(app.codeFontSize)pt")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundStyle(Color(red: 0.4, green: 0.8, blue: 0.5))
                            .frame(width: 40)
                    }
                    Slider(value: Binding(
                        get: { Double(app.codeFontSize) },
                        set: { app.codeFontSize = Int($0) }
                    ), in: 9...18, step: 1)
                    .tint(Color(red: 0.4, green: 0.7, blue: 1.0))
                }
            }

            sectionHeader("Notifications", icon: "bell")

            settingsCard {
                VStack(alignment: .leading, spacing: 0) {
                    toolToggleRow(
                        icon: "checkmark.circle.fill",
                        iconColor: Color(red: 0.3, green: 0.9, blue: 0.5),
                        title: "Diff applied",
                        description: "Notify when AI changes are applied to a file",
                        isOn: $app.notifyOnDiffApply
                    )
                    Divider().opacity(0.15)
                    toolToggleRow(
                        icon: "exclamationmark.triangle.fill",
                        iconColor: Color(red: 0.9, green: 0.7, blue: 0.2),
                        title: "Agent errors",
                        description: "Notify when the agent loop encounters an error",
                        isOn: $app.notifyOnError
                    )
                }
            }

            sectionHeader(app.t("External Integration", "外部連携 (追加機能)"), icon: "network")

            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    Text(app.t(
                        "You can connect the verantyx-compiler to Antigravity or Claude Desktop to let external AIs access the Verantyx Spatial Memory and Gatekeeper tools.",
                        "Antigravity や Claude Desktop に verantyx-compiler を追加することで、外部の AI が Verantyx の空間記憶や Gatekeeper ツールにアクセスできるようになります。"
                    ))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    
                    Text(app.t("1. Open your MCP config file (e.g., claude_desktop_config.json)", "1. MCP の設定ファイル (claude_desktop_config.json など) を開きます"))
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(.white)
                    
                    Text(app.t("2. Add the verantyx-compiler server:", "2. 以下の通り verantyx-compiler サーバーを追加します:"))
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(.white)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        let ws = app.cortexWorkspacePath ?? app.workspaceURL?.path ?? ""
                        let base = ws.hasSuffix("VerantyxIDE") ? URL(fileURLWithPath: ws).deletingLastPathComponent().path : (ws.isEmpty ? "/path/to/verantyx-cli" : ws)
                        
                        Text("\"verantyx-compiler\": {\n  \"command\": \"node\",\n  \"args\": [\n    \"--import\", \"tsx\",\n    \"\(base)/src/verantyx/mcp/server.ts\"\n  ]\n}")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Color(red: 0.8, green: 0.85, blue: 0.95))
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(red: 0.08, green: 0.08, blue: 0.1), in: RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(Color.white.opacity(0.1), lineWidth: 1))
                    
                    Text(app.t(
                        "3. Restart your external AI client. It will automatically sync with this IDE via the shared workspace.",
                        "3. 外部の AI クライアントを再起動してください。共有ワークスペースを通じて、この IDE と自動的に連携・同期します。"
                    ))
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.white)
                }
            }
        }
    }

    // MARK: - Model Settings


    private var modelSettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("Model Configuration", icon: "cpu")
            modelConfigurationCard
            
            sectionHeader("Inference Parameters", icon: "slider.horizontal.3")
            inferenceParametersCard
            
            sectionHeader("Exo Distributed Cluster", icon: "bolt.horizontal.circle.fill")
            exoClusterCard
            
            sectionHeader("System Prompt", icon: "text.bubble")
            systemPromptCard
            
            sectionHeader(app.t("Fine-Tuning (Dual-Track Growth)", "ファインチューニング (Dual-Track Growth)"), icon: "brain")
            fineTuningCard
        }
    }

    private var modelConfigurationCard: some View {
        settingsCard {
            VStack(alignment: .leading, spacing: 12) {
                rowLabel("Ollama endpoint") {
                    TextField("http://localhost:11434", text: $app.ollamaEndpoint)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 11, design: .monospaced))
                        .frame(width: 200)
                        .onSubmit { app.connectOllama() }
                }

                if let result = connectionTestResult {
                    Text(result)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(result.contains("✓") ? .green : .red)
                }

                Divider().opacity(0.2)
                mlxModelSelector
            }
        }
    }

    private var mlxModelSelector: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("MLX model")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.secondary)
                Spacer()
                // Show currently loaded MLX model
                if case .mlxReady(let m) = app.modelStatus {
                    HStack(spacing: 4) {
                        Circle().fill(Color.green).frame(width: 6, height: 6)
                        Text(m.components(separatedBy: "/").last ?? m)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(.green)
                    }
                }
            }

            // Popular models list
            VStack(spacing: 4) {
                ForEach(MLXRunner.popularModels) { model in
                    mlxModelRow(model: model)
                }
            }

            // Load button
            HStack(spacing: 8) {
                Button {
                    app.loadMLXModel(model: app.activeMlxModel)
                } label: {
                    HStack(spacing: 6) {
                        if case .connecting = app.modelStatus {
                            ProgressView().scaleEffect(0.65).frame(width: 12, height: 12)
                            Text("Loading…")
                        } else {
                            Image(systemName: "bolt.fill")
                            Text(app.t("Launch MLX", "MLXを起動"))
                        }
                    }
                    .font(.system(size: 12, weight: .semibold))
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.regular)
                .tint(Color(red: 0.25, green: 0.55, blue: 0.35))
                .disabled({
                    if case .connecting = app.modelStatus { return true }
                    return false
                }())

                // Custom path field
                TextField(app.t("or enter HF ID directly…", "または HF ID を直接入力…"), text: $app.activeMlxModel)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 10, design: .monospaced))
            }
        }
    }

    private func mlxModelRow(model: MLXModel) -> some View {
        let isSelected = app.activeMlxModel == model.id
        let isLoaded: Bool = {
            if case .mlxReady(let m) = app.modelStatus { return m == model.id }
            return false
        }()
        
        let bgColor: Color = isLoaded 
            ? Color(red: 0.15, green: 0.30, blue: 0.18).opacity(0.7) 
            : (isSelected ? Color(red: 0.18, green: 0.22, blue: 0.35).opacity(0.7) : Color.white.opacity(0.03))
            
        let strokeColor: Color = isLoaded
            ? Color(red: 0.3, green: 0.8, blue: 0.45).opacity(0.5)
            : (isSelected ? Color(red: 0.4, green: 0.6, blue: 1.0).opacity(0.4) : Color.white.opacity(0.05))
            
        let strokeWidth: CGFloat = (isSelected || isLoaded) ? 1 : 0.5
        let downloadIconColor: Color = model.isDownloaded ? Color(red: 0.35, green: 0.85, blue: 0.5) : Color(red: 0.45, green: 0.45, blue: 0.6)
        let titleColor: Color = isSelected ? .white : Color(red: 0.75, green: 0.75, blue: 0.88)
        let indicatorStrokeColor: Color = isSelected ? Color(red: 0.4, green: 0.7, blue: 1.0) : Color.white.opacity(0.2)
        
        return Button {
            app.activeMlxModel = model.id
        } label: {
            HStack(spacing: 10) {
                // Selection indicator
                ZStack {
                    Circle()
                        .stroke(indicatorStrokeColor, lineWidth: isSelected ? 2 : 1)
                        .frame(width: 14, height: 14)
                    if isSelected {
                        Circle()
                            .fill(Color(red: 0.4, green: 0.7, blue: 1.0))
                            .frame(width: 8, height: 8)
                    }
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(model.displayName)
                        .font(.system(size: 11, weight: isSelected ? .semibold : .regular))
                        .foregroundStyle(titleColor)
                        .lineLimit(1)
                    Text(model.id)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                }

                Spacer()

                // Tags
                HStack(spacing: 3) {
                    ForEach(model.tags.prefix(2), id: \.self) { tag in
                        Text(tag)
                            .font(.system(size: 8, weight: .medium))
                            .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .background(Color(red: 0.4, green: 0.7, blue: 1.0).opacity(0.12),
                                        in: Capsule())
                    }
                }

                // Size badge
                Text("\(String(format: "%.0f", model.sizeGB))GB")
                    .font(.system(size: 9, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Color(red: 0.5, green: 0.5, blue: 0.65))
                    .frame(width: 30)

                // Download status
                Image(systemName: model.isDownloaded ? "checkmark.circle.fill" : "arrow.down.circle")
                    .font(.system(size: 11))
                    .foregroundStyle(downloadIconColor)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(bgColor, in: RoundedRectangle(cornerRadius: 7))
            .overlay(
                RoundedRectangle(cornerRadius: 7)
                    .strokeBorder(strokeColor, lineWidth: strokeWidth)
            )
        }
        .contentShape(Rectangle())
        .buttonStyle(.plain)
    }

    private var inferenceParametersCard: some View {
        settingsCard {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 6) {
                    rowLabel("Temperature") {
                        Text(String(format: "%.2f", app.temperature))
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundStyle(tempColor)
                            .frame(width: 40)
                    }
                    Slider(value: $app.temperature, in: 0...1.5, step: 0.05)
                        .tint(tempColor)
                    HStack {
                        Text("0 = deterministic").font(.system(size: 9)).foregroundStyle(.tertiary)
                        Spacer()
                        Text("0.1–0.3 = coding  ·  0.7–1.0 = creative").font(.system(size: 9)).foregroundStyle(.tertiary)
                    }
                }

                Divider().opacity(0.2)

                VStack(alignment: .leading, spacing: 6) {
                    rowLabel("Max tokens (Ollama)") {
                        Text("\(app.maxTokensOllama)").font(.system(size: 11, design: .monospaced)).foregroundStyle(.secondary).frame(width: 48)
                    }
                    Slider(value: Binding(get: { Double(app.maxTokensOllama) }, set: { app.maxTokensOllama = Int($0) }), in: 256...8192, step: 256)
                        .tint(Color(red: 0.4, green: 0.7, blue: 1.0))
                }

                Divider().opacity(0.2)

                VStack(alignment: .leading, spacing: 6) {
                    rowLabel("Max tokens (MLX)") {
                        Text("\(app.maxTokensMLX)").font(.system(size: 11, design: .monospaced)).foregroundStyle(.secondary).frame(width: 48)
                    }
                    Slider(value: Binding(get: { Double(app.maxTokensMLX) }, set: { app.maxTokensMLX = Int($0) }), in: 512...16384, step: 512)
                        .tint(Color(red: 0.4, green: 0.9, blue: 0.6))
                }

                Divider().opacity(0.2)

                rowLabel("Streaming output") {
                    Toggle("", isOn: $app.streamingEnabled).toggleStyle(.switch).scaleEffect(0.8)
                }
                Text("Token-by-token streaming display. Disable only for debugging.")
                    .font(.system(size: 10)).foregroundStyle(.tertiary)
            }
        }
    }

    private var exoClusterCard: some View {
        settingsCard {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Enable Exo Cluster (Thunderbolt)")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(Color.white.opacity(0.9))
                        Text("Distribute inference across multiple Macs.")
                            .font(.system(size: 11))
                            .foregroundStyle(Color.white.opacity(0.5))
                    }
                    Spacer()
                    
                    Picker("Role", selection: $app.exoRole) {
                        Text("Idle").tag(AppState.ExoRole.idle)
                        Text("Master 👑").tag(AppState.ExoRole.master)
                        Text("Worker 🛠️").tag(AppState.ExoRole.worker)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 200)
                    .onChange(of: app.exoRole) { newValue in
                        if newValue == .idle {
                            app.exoEnabled = false
                            ExoEngine.shared.stop()
                        } else {
                            app.exoEnabled = true
                            ExoEngine.shared.start()
                        }
                        ExoClusterSync.shared.updateRole(newValue)
                    }
                    
                    Button("Setup Wizard") {
                        // Handled by parent view passing state, here we trigger defaults
                        let process = Process()
                        process.executableURL = URL(fileURLWithPath: "/usr/bin/defaults")
                        process.arguments = ["write", "com.verantyx.ide", "trigger_setup", "exo"]
                        try? process.run()
                    }
                    .buttonStyle(.bordered)
                    .font(.system(size: 11))
                }
                
                if app.exoRole != .idle {
                    Divider().opacity(0.2)
                    rowLabel("Exo Endpoint") {
                        Text(app.exoEndpoint.isEmpty ? "Starting / Connecting..." : app.exoEndpoint)
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(app.exoEndpoint.isEmpty ? Color.gray : Color.green)
                    }
                }
            }
        }
    }

    private var systemPromptCard: some View {
        settingsCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Injected at the start of every request").font(.system(size: 11)).foregroundStyle(.secondary)
                    Spacer()
                    Button("Reset") {
                        app.systemPrompt = "You are Verantyx, an expert AI coding assistant running on Apple Silicon. Be concise and precise. Prefer code over prose."
                    }
                    .buttonStyle(.bordered).controlSize(.small)
                }
                TextEditor(text: $app.systemPrompt)
                    .font(.system(size: 11, design: .monospaced))
                    .frame(minHeight: 80, maxHeight: 120)
                    .scrollContentBackground(.hidden)
                    .background(Color(red: 0.08, green: 0.08, blue: 0.12))
            }
        }
    }

    private var fineTuningCard: some View {
        settingsCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(app.t("Select the base model that will be fine-tuned using the automatically collected training data.", "自動収集された学習データを用いてファインチューニング（重みの更新）を行う際のベースモデルを選択します。"))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                
                rowLabel("Base Model") {
                    TextField("e.g. llama3.1:8b", text: $app.fineTuningBaseModel)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 11, design: .monospaced))
                        .frame(width: 200)
                }
                
                HStack(spacing: 8) {
                    Image(systemName: "info.circle")
                        .font(.system(size: 10))
                        .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))
                    Text(app.t("Data is collected at ~/.openclaw/memory/training_data/verantyx_dataset.jsonl", "~/.openclaw/memory/training_data/verantyx_dataset.jsonl にデータが蓄積されます。"))
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                    
                    Spacer()
                    
                    Button {
                        app.clearFineTuningData()
                    } label: {
                        Text(app.t("Archive Dataset", "データをアーカイブ"))
                            .font(.system(size: 10))
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .help(app.t("Archive the current dataset to prevent duplicate fine-tuning.", "現在のデータセットを退避し、重複した学習を防ぎます。"))
                }
            }
        }
    }

    // MARK: - API Keys Settings

    private var apiKeysSettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("Cloud API Keys", icon: "key.fill")

            infoBlock("🔐 API keys are stored in UserDefaults (sandboxed local storage). They are never sent to any server other than the respective API endpoint.")

            // ── Anthropic ──────────────────────────────────────────────
            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 10) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 6)
                                .fill(Color(red: 0.9, green: 0.6, blue: 0.3).opacity(0.15))
                                .frame(width: 32, height: 32)
                            Text("A")
                                .font(.system(size: 16, weight: .bold, design: .rounded))
                                .foregroundStyle(Color(red: 0.9, green: 0.6, blue: 0.3))
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Anthropic").font(.system(size: 13, weight: .semibold)).foregroundStyle(.white)
                            Text("Claude 3.5 / 3.7 Sonnet, claude-opus-4-5")
                                .font(.system(size: 10)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if !app.anthropicApiKey.isEmpty {
                            Text("✓ Configured")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundStyle(Color(red: 0.3, green: 0.9, blue: 0.5))
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(Color(red: 0.3, green: 0.9, blue: 0.5).opacity(0.1), in: Capsule())
                        }
                    }

                    Divider().opacity(0.2)

                    rowLabel("API Key") {
                        HStack(spacing: 6) {
                            if showAnthropicKey {
                                TextField("sk-ant-...", text: $app.anthropicApiKey)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            } else {
                                SecureField("sk-ant-...", text: $app.anthropicApiKey)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            }
                            Button {
                                showAnthropicKey.toggle()
                            } label: {
                                Image(systemName: showAnthropicKey ? "eye.slash" : "eye")
                                    .font(.system(size: 11))
                            }
                            .contentShape(Rectangle())
                            .buttonStyle(.plain)
                            .foregroundStyle(.secondary)
                        }
                    }

                    rowLabel("Model") {
                        Picker("", selection: $app.activeAnthropicModel) {
                            Text("claude-sonnet-4-5").tag("claude-sonnet-4-5")
                            Text("claude-3-7-sonnet-20250219").tag("claude-3-7-sonnet-20250219")
                            Text("claude-opus-4-5").tag("claude-opus-4-5")
                            Text("claude-3-5-haiku-20241022").tag("claude-3-5-haiku-20241022")
                        }
                        .frame(width: 240)
                    }

                    HStack(spacing: 8) {
                        Button {
                            testAnthropic()
                        } label: {
                            if testingAnthropic {
                                HStack(spacing: 4) {
                                    ProgressView().scaleEffect(0.6).frame(width: 12, height: 12)
                                    Text("Testing…")
                                }
                            } else {
                                Label("Test Connection", systemImage: "network")
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                        .disabled(app.anthropicApiKey.isEmpty || testingAnthropic)

                        if let result = anthropicTestResult {
                            Text(result)
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundStyle(result.contains("✓") ? .green : .red)
                        }
                    }
                }
            }

            // ── OpenAI ─────────────────────────────────────────────────
            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 10) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 6)
                                .fill(Color(red: 0.4, green: 0.9, blue: 0.6).opacity(0.15))
                                .frame(width: 32, height: 32)
                            Image(systemName: "sparkle")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Color(red: 0.4, green: 0.9, blue: 0.6))
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text("OpenAI").font(.system(size: 13, weight: .semibold)).foregroundStyle(.white)
                            Text("GPT-4o, GPT-4 Turbo, o1, o3-mini")
                                .font(.system(size: 10)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if let key = UserDefaults.standard.string(forKey: "openai_api_key"), !key.isEmpty {
                            Text("✓ Configured")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundStyle(Color(red: 0.3, green: 0.9, blue: 0.5))
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(Color(red: 0.3, green: 0.9, blue: 0.5).opacity(0.1), in: Capsule())
                        }
                    }

                    Divider().opacity(0.2)

                    rowLabel("API Key") {
                        HStack(spacing: 6) {
                            let binding = Binding<String>(
                                get: { UserDefaults.standard.string(forKey: "openai_api_key") ?? "" },
                                set: { UserDefaults.standard.set($0, forKey: "openai_api_key") }
                            )
                            if showOpenAIKey {
                                TextField("sk-...", text: binding)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            } else {
                                SecureField("sk-...", text: binding)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            }
                            Button { showOpenAIKey.toggle() } label: {
                                Image(systemName: showOpenAIKey ? "eye.slash" : "eye")
                                    .font(.system(size: 11))
                            }
                            .contentShape(Rectangle())
                            .buttonStyle(.plain).foregroundStyle(.secondary)
                        }
                    }

                    rowLabel("Model") {
                        Picker("", selection: $app.activeOpenAIModel) {
                            Text("gpt-4o").tag("gpt-4o")
                            Text("gpt-4-turbo").tag("gpt-4-turbo")
                            Text("o1").tag("o1")
                            Text("o3-mini").tag("o3-mini")
                        }
                        .frame(width: 240)
                    }
                }
            }

            // ── DeepSeek ──────────────────────────────────────────────
            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 10) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 6)
                                .fill(Color(red: 0.3, green: 0.5, blue: 0.9).opacity(0.15))
                                .frame(width: 32, height: 32)
                            Image(systemName: "waveform.circle")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Color(red: 0.3, green: 0.5, blue: 0.9))
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text("DeepSeek").font(.system(size: 13, weight: .semibold)).foregroundStyle(.white)
                            Text("deepseek-coder, deepseek-chat")
                                .font(.system(size: 10)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if let key = UserDefaults.standard.string(forKey: "api_key_DeepSeek"), !key.isEmpty {
                            Text("✓ Configured")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundStyle(Color(red: 0.3, green: 0.9, blue: 0.5))
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(Color(red: 0.3, green: 0.9, blue: 0.5).opacity(0.1), in: Capsule())
                        }
                    }

                    Divider().opacity(0.2)

                    rowLabel("API Key") {
                        HStack(spacing: 6) {
                            let binding = Binding<String>(
                                get: { UserDefaults.standard.string(forKey: "api_key_DeepSeek") ?? "" },
                                set: { UserDefaults.standard.set($0, forKey: "api_key_DeepSeek") }
                            )
                            if showDeepSeekKey {
                                TextField("sk-...", text: binding)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            } else {
                                SecureField("sk-...", text: binding)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            }
                            Button { showDeepSeekKey.toggle() } label: {
                                Image(systemName: showDeepSeekKey ? "eye.slash" : "eye")
                                    .font(.system(size: 11))
                            }
                            .contentShape(Rectangle())
                            .buttonStyle(.plain).foregroundStyle(.secondary)
                        }
                    }

                    rowLabel("Model") {
                        Picker("", selection: $app.activeDeepSeekModel) {
                            Text("deepseek-coder").tag("deepseek-coder")
                            Text("deepseek-chat").tag("deepseek-chat")
                            Text("deepseek-reasoner").tag("deepseek-reasoner")
                        }
                        .frame(width: 240)
                    }
                }
            }

            // ── Gemini ────────────────────────────────────────────────
            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 10) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 6)
                                .fill(Color(red: 0.2, green: 0.6, blue: 0.8).opacity(0.15))
                                .frame(width: 32, height: 32)
                            Image(systemName: "star.circle")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Color(red: 0.2, green: 0.6, blue: 0.8))
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Gemini").font(.system(size: 13, weight: .semibold)).foregroundStyle(.white)
                            Text("gemini-2.5-pro, gemini-1.5-flash")
                                .font(.system(size: 10)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if let key = UserDefaults.standard.string(forKey: "gemini_api_key"), !key.isEmpty {
                            Text("✓ Configured")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundStyle(Color(red: 0.3, green: 0.9, blue: 0.5))
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(Color(red: 0.3, green: 0.9, blue: 0.5).opacity(0.1), in: Capsule())
                        }
                    }

                    Divider().opacity(0.2)

                    rowLabel("API Key") {
                        HStack(spacing: 6) {
                            let binding = Binding<String>(
                                get: { UserDefaults.standard.string(forKey: "gemini_api_key") ?? "" },
                                set: { UserDefaults.standard.set($0, forKey: "gemini_api_key") }
                            )
                            if showGeminiKey {
                                TextField("AIza...", text: binding)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            } else {
                                SecureField("AIza...", text: binding)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                                    .frame(width: 220)
                            }
                            Button { showGeminiKey.toggle() } label: {
                                Image(systemName: showGeminiKey ? "eye.slash" : "eye")
                                    .font(.system(size: 11))
                            }
                            .contentShape(Rectangle())
                            .buttonStyle(.plain).foregroundStyle(.secondary)
                        }
                    }

                    rowLabel("Model") {
                        Picker("", selection: $app.activeGeminiModel) {
                            Text("gemini-3.1-pro").tag("gemini-3.1-pro")
                            Text("gemini-2.5-pro").tag("gemini-2.5-pro")
                            Text("gemini-2.5-flash").tag("gemini-2.5-flash")
                            Text("gemini-1.5-pro").tag("gemini-1.5-pro")
                        }
                        .frame(width: 240)
                    }
                }
            }

            // ── Usage tip ──────────────────────────────────────────────
            settingsCard {
                HStack(spacing: 12) {
                    Image(systemName: "lightbulb.fill")
                        .foregroundStyle(Color(red: 0.9, green: 0.8, blue: 0.3))
                        .font(.system(size: 16))
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Cloud provider selection")
                            .font(.system(size: 11, weight: .semibold)).foregroundStyle(.white)
                        Text("Switch between providers in Privacy → Cloud provider. Each provider uses the API key configured above.")
                            .font(.system(size: 10)).foregroundStyle(.secondary).lineSpacing(2)
                    }
                }
            }
        }
    }

    // MARK: - Tools Settings

    private var toolsSettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("Tool Toggles", icon: "puzzlepiece.extension")
            Text("Enable or disable each tool the AI can use. Changes take effect on the next request.")
                .font(.system(size: 11)).foregroundStyle(.secondary)

            settingsCard {
                VStack(alignment: .leading, spacing: 0) {
                    toolToggleRow(icon: "globe",          iconColor: Color(red: 0.3, green: 0.7, blue: 1.0),
                                  title: "Web Browser",   description: "AI can browse URLs using the Rust browser engine or system browser",
                                  isOn: $app.toolBrowserEnabled)
                    Divider().opacity(0.15)
                    toolToggleRow(icon: "magnifyingglass", iconColor: Color(red: 0.4, green: 0.9, blue: 0.6),
                                  title: "Web Search",    description: "AI can search the web for documentation, code examples, and answers",
                                  isOn: $app.toolWebSearchEnabled)
                    Divider().opacity(0.15)
                    toolToggleRow(icon: "terminal",       iconColor: Color(red: 0.9, green: 0.6, blue: 0.2),
                                  title: "Terminal",      description: "AI can run shell commands, build scripts, and tests",
                                  isOn: $app.toolTerminalEnabled)
                    Divider().opacity(0.15)
                    toolToggleRow(icon: "arrow.left.arrow.right", iconColor: Color(red: 0.7, green: 0.4, blue: 1.0),
                                  title: "Diff & Apply",  description: "AI can propose file changes via side-by-side diff viewer",
                                  isOn: $app.toolDiffEnabled)
                    Divider().opacity(0.15)
                    toolToggleRow(icon: "brain",          iconColor: Color(red: 0.4, green: 0.9, blue: 0.6),
                                  title: "JCross Memory", description: "AI can read/write long-term memory nodes (JCross spatial index)",
                                  isOn: $app.toolJCrossEnabled)
                }
            }

            settingsCard {
                HStack(spacing: 12) {
                    Button("Enable All") {
                        app.toolBrowserEnabled = true; app.toolWebSearchEnabled = true
                        app.toolTerminalEnabled = true; app.toolDiffEnabled = true; app.toolJCrossEnabled = true
                    }
                    .buttonStyle(.borderedProminent).controlSize(.small)

                    Button("Disable All") {
                        app.toolBrowserEnabled = false; app.toolWebSearchEnabled = false
                        app.toolTerminalEnabled = false; app.toolDiffEnabled = false; app.toolJCrossEnabled = false
                    }
                    .buttonStyle(.bordered).controlSize(.small).tint(.red)

                    Spacer()

                    let n = [app.toolBrowserEnabled, app.toolWebSearchEnabled,
                             app.toolTerminalEnabled, app.toolDiffEnabled, app.toolJCrossEnabled]
                        .filter { $0 }.count
                    Text("\(n)/5 tools enabled")
                        .font(.system(size: 10, design: .monospaced)).foregroundStyle(.secondary)
                }
            }
        }
    }

    // MARK: - Agent Settings

    private var agentSettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("Agent Loop", icon: "bolt.circle")

            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    rowLabel("Autonomous Mode") {
                        Toggle("", isOn: $app.agentLoopEnabled).toggleStyle(.switch).scaleEffect(0.85)
                    }
                    Text("Agent can create files, scaffold projects, run build commands, and fix errors autonomously across multiple turns.")
                        .font(.system(size: 11)).foregroundStyle(.secondary).lineSpacing(2)

                    if app.agentLoopEnabled {
                        Divider().opacity(0.2)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Example prompts:")
                                .font(.system(size: 10, weight: .semibold)).foregroundStyle(.tertiary)
                            Group {
                                Text("• \"Create a new Python calculator app\"")
                                Text("• \"Scaffold a Rust CLI project called 'todo'\"")
                                Text("• \"Set up a React TypeScript project\"")
                                Text("• \"Fix all build errors and run tests\"")
                            }
                            .font(.system(size: 10, design: .monospaced)).foregroundStyle(.secondary)
                        }
                    }

                    Divider().opacity(0.2)
                    
                    rowLabel("Non-Coding Tasks (e.g. Q&A, Search)") {
                        Picker("", selection: $app.nonCodingTaskEngine) {
                            ForEach(AppState.NonCodingTaskEngine.allCases, id: \.self) { engine in
                                Text(engine.rawValue).tag(engine)
                            }
                        }
                        .frame(width: 220)
                    }
                    Text("Choose how simple tasks that do not modify the codebase are handled.")
                        .font(.system(size: 11)).foregroundStyle(.secondary)
                }
            }
        }
    }

    // MARK: - Memory Settings

    private var memorySettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("Cortex Memory", icon: "brain")

            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    rowLabel("Enable Cortex") {
                        Toggle("", isOn: Binding(
                            get: { app.cortex.isEnabled },
                            set: { app.cortex.isEnabled = $0 }
                        ))
                        .toggleStyle(.switch).scaleEffect(0.85)
                    }
                    Text("Prevents context overflow by compressing old conversation turns into persistent memory nodes.")
                        .font(.system(size: 11)).foregroundStyle(.secondary)

                    if app.cortex.isEnabled {
                        Divider().opacity(0.2)

                        VStack(alignment: .leading, spacing: 6) {
                            rowLabel("Compression threshold") {
                                Text("\(app.cortex.contextThreshold) tokens")
                                    .font(.system(size: 11, design: .monospaced))
                                    .foregroundStyle(Color(red: 0.4, green: 0.9, blue: 0.5))
                                    .frame(width: 80)
                            }
                            Slider(value: Binding(
                                get: { Double(app.cortex.contextThreshold) },
                                set: { app.cortex.contextThreshold = Int($0) }
                            ), in: 500...8000, step: 500)
                            .tint(Color(red: 0.4, green: 0.7, blue: 1.0))
                            Text("Lower = more aggressive. Recommended: 3000 for 8B, 6000 for 27B+")
                                .font(.system(size: 9)).foregroundStyle(.tertiary)
                        }

                        Divider().opacity(0.2)

                        HStack(spacing: 16) {
                            statCard("Nodes",     value: "\(app.cortex.nodes.count)",
                                     icon: "square.stack.3d.up", color: Color(red: 0.4, green: 0.7, blue: 1.0))
                            statCard("Compressed", value: "\(app.cortex.compressedCount)",
                                     icon: "arrow.compress", color: Color(red: 0.7, green: 0.5, blue: 1.0))
                            statCard("Active",    value: "\(app.cortex.nodes.filter { $0.zone == .front || $0.zone == .near }.count)",
                                     icon: "bolt.fill", color: Color(red: 0.4, green: 0.9, blue: 0.5))
                        }

                        if !app.cortex.nodes.isEmpty {
                            Divider().opacity(0.2)
                            VStack(alignment: .leading, spacing: 3) {
                                Text("Memory nodes")
                                    .font(.system(size: 10, weight: .semibold)).foregroundStyle(.tertiary)
                                ForEach(app.cortex.nodes.prefix(15)) { node in memoryNodeRow(node) }
                                if app.cortex.nodes.count > 15 {
                                    Text("… and \(app.cortex.nodes.count - 15) more")
                                        .font(.system(size: 9)).foregroundStyle(.tertiary)
                                }
                            }
                        }

                        Divider().opacity(0.2)

                        Button(role: .destructive) { app.cortex.clearAll() } label: {
                            Label("Clear All Memory", systemImage: "trash").font(.system(size: 11))
                        }
                        .buttonStyle(.bordered).controlSize(.small).tint(.red)
                    }
                }
            }
            
            sectionHeader("L3.5 PC Asset Map (System Memory)", icon: "macwindow")
            
            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    if vault.isScanning {
                        VStack(alignment: .leading, spacing: 6) {
                            ProgressView(value: vault.scanProgressValue)
                                .tint(.orange)
                            HStack {
                                Text(vault.currentProcessingFile)
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                                Spacer()
                                if vault.totalFilesToScan > 0 {
                                    Text("\(vault.processedFilesCount) / \(vault.totalFilesToScan) (\(Int(vault.scanProgressValue * 100))%)")
                                        .font(.caption2)
                                } else {
                                    Text("\(Int(vault.scanProgressValue * 100))%")
                                        .font(.caption2)
                                }
                            }
                            if !vault.estimatedTimeRemaining.isEmpty {
                                Text("Estimated time: \(vault.estimatedTimeRemaining)")
                                    .font(.caption2)
                                    .foregroundStyle(.orange)
                            }
                            if !vault.conversionLog.isEmpty {
                                ScrollView {
                                    LazyVStack(alignment: .leading) {
                                        ForEach(vault.conversionLog.suffix(8), id: \.self) { line in
                                            Text(line)
                                                .font(.caption2.monospaced())
                                                .foregroundStyle(line.contains("✓") ? .green : .primary)
                                        }
                                    }
                                    .padding(6)
                                }
                                .frame(height: 100)
                                .background(Color.black.opacity(0.6))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        }
                    } else {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("User Directories (Scan Targets)")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundStyle(.secondary)
                            
                            VStack(spacing: 1) {
                                ForEach($vault.scanTargets) { $target in
                                    HStack {
                                        Toggle(target.name, isOn: $target.isEnabled)
                                            .toggleStyle(.switch)
                                            .controlSize(.mini)
                                        
                                        Spacer()
                                        
                                        if target.isEnabled {
                                            HStack(spacing: 8) {
                                                Text("Depth: \(target.scanDepth)")
                                                    .font(.system(size: 11, design: .monospaced))
                                                    .foregroundStyle(.secondary)
                                                Stepper("", value: $target.scanDepth, in: 1...10)
                                                    .labelsHidden()
                                            }
                                        }
                                    }
                                    .padding(.vertical, 4)
                                    .padding(.horizontal, 8)
                                    .background(Color.white.opacity(0.03))
                                }
                            }
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                        }
                        
                        Divider().opacity(0.2)
                        
                        VStack(alignment: .leading, spacing: 6) {
                            Toggle(isOn: $vault.isBitNetModeEnabled) {
                                Text("BitNet Semantic Scan (Deep Content Analysis)")
                                    .font(.system(size: 11, weight: .semibold))
                            }
                            .tint(.purple)
                            
                            if vault.isBitNetModeEnabled {
                                Text("⚠️ 警告: ファイルの中身をLLMで解釈するため、スキャンに数十分〜数時間かかる場合があります。")
                                    .font(.system(size: 10))
                                    .foregroundStyle(.orange)
                            } else {
                                Text("ファイルの中身をLLMで読み取り、実装目的を要約して地図に記録します。非常に時間がかかります。")
                                    .font(.system(size: 10))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        
                        Divider().opacity(0.2)
                        
                        HStack(spacing: 12) {
                            Button {
                                addCustomFolder()
                            } label: {
                                Label("フォルダを追加", systemImage: "folder.badge.plus")
                                    .font(.system(size: 11))
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(.blue)
                            
                            Button {
                                vault.scanBackground()
                            } label: {
                                Label("再変換 (フルスキャン)", systemImage: "arrow.triangle.2.circlepath")
                                    .font(.system(size: 11))
                            }
                            .buttonStyle(.bordered)
                            
                            Button(role: .destructive) {
                                vault.deleteMap()
                            } label: {
                                Label("削除", systemImage: "trash")
                                    .font(.system(size: 11))
                            }
                            .buttonStyle(.bordered).tint(.red)
                            
                            if vault.assetMap != nil {
                                Button {
                                    showAssetMap = true
                                } label: {
                                    Label("地図を見る", systemImage: "map")
                                        .font(.system(size: 11))
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        }
                        
                        if let map = vault.assetMap {
                            let stats = Dictionary(grouping: map.entries.values, by: { $0.category })
                                .map { "\($0.key) (\($0.value.count)件)" }
                                .joined(separator: ", ")
                            
                            VStack(alignment: .leading, spacing: 4) {
                                Text("変換済み対象:")
                                    .font(.caption).foregroundStyle(.secondary)
                                Text("• /Applications\n• /System/Applications\n• Safari History\n• 起動中プロセス\n• システム設定")
                                    .font(.caption2).foregroundStyle(.tertiary)
                                Text("詳細: \(stats)")
                                    .font(.caption2).foregroundStyle(.secondary)
                                    .padding(.top, 2)
                            }
                            .padding(.top, 4)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Privacy Settings

    private var privacySettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("Privacy & Mode", icon: "lock.shield")

            // ── Inference mode ─────────────────────────────────────────
            settingsCard {
                VStack(alignment: .leading, spacing: 14) {
                    rowLabel("Inference mode") {
                        Picker("", selection: $app.inferenceMode) {
                            Text("Local Only").tag(InferenceMode.localOnly)
                            Text("Privacy Shield").tag(InferenceMode.privacyShield)
                            Text("Cloud Direct").tag(InferenceMode.cloudDirect)
                        }
                        .pickerStyle(.segmented).frame(width: 320)
                    }

                    switch app.inferenceMode {
                    case .localOnly:
                        infoBlock("🔒 100% offline. No data leaves your machine. Runs on Apple Silicon via Ollama or MLX.")
                    case .privacyShield:
                        infoBlock("🛡 Code is anonymized before being sent to cloud. Real identifiers stay on your Mac. Cloud only sees abstract logic.")
                    case .cloudDirect:
                        infoBlock("☁️ Direct cloud inference. Fastest responses, but code is sent as-is to the provider.")
                    case .paranoiaMode:
                        infoBlock("🔴 Paranoia Mode: AST-level symbol extraction + Gemma 4 classification + Rust byte-offset masking. Maximum privacy.")
                    }

                    if app.inferenceMode != .localOnly {
                        Divider().opacity(0.2)
                        rowLabel("Cloud provider") {
                            Picker("", selection: $app.cloudProvider) {
                                Text("Claude").tag(CloudProvider.claude)
                                Text("GPT-4").tag(CloudProvider.openai)
                                Text("Gemini").tag(CloudProvider.gemini)
                                Text("DeepSeek").tag(CloudProvider.deepseek)
                            }
                            .pickerStyle(.segmented).frame(width: 340)
                        }
                    }
                }
            }

            // ── Privacy Gateway settings (Privacy Shield only) ─────────
            if app.inferenceMode == .privacyShield {
                sectionHeader("Privacy Gateway Configuration", icon: "shield.lefthalf.filled")

                settingsCard {
                    VStack(alignment: .leading, spacing: 0) {
                        // Phase 1: Always on
                        HStack(spacing: 12) {
                            ZStack {
                                Circle()
                                    .fill(Color(red: 0.4, green: 0.9, blue: 0.5).opacity(0.15))
                                    .frame(width: 32, height: 32)
                                Text("P1")
                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                    .foregroundStyle(Color(red: 0.4, green: 0.9, blue: 0.5))
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                HStack(spacing: 6) {
                                    Text("Regex Masking")
                                        .font(.system(size: 12, weight: .semibold)).foregroundStyle(.white)
                                    Text("Always ON")
                                        .font(.system(size: 9, weight: .semibold))
                                        .foregroundStyle(Color(red: 0.4, green: 0.9, blue: 0.5))
                                        .padding(.horizontal, 6).padding(.vertical, 2)
                                        .background(Color(red: 0.4, green: 0.9, blue: 0.5).opacity(0.1), in: Capsule())
                                }
                                Text("Detects FUNC_xxx, CLASS_xxx, VAR_xxx, secrets via regex patterns. Fast, deterministic.")
                                    .font(.system(size: 10)).foregroundStyle(.secondary).lineSpacing(2)
                            }
                            Spacer()
                        }
                        .padding(.vertical, 12)

                        Divider().opacity(0.15)

                        // Phase 2: Togglable
                        HStack(spacing: 12) {
                            ZStack {
                                Circle()
                                    .fill(app.gemmaSemanticMaskingEnabled
                                          ? Color(red: 0.8, green: 0.5, blue: 1.0).opacity(0.15)
                                          : Color.white.opacity(0.05))
                                    .frame(width: 32, height: 32)
                                Text("P2")
                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                    .foregroundStyle(app.gemmaSemanticMaskingEnabled
                                                     ? Color(red: 0.8, green: 0.5, blue: 1.0)
                                                     : .secondary)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Gemma Semantic Scan")
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(app.gemmaSemanticMaskingEnabled ? .white : .secondary)
                                Text("Local Gemma LLM detects domain-specific identifiers missed by regex (e.g. paymentGatewayURL → SEMID_000). Slower but more thorough.")
                                    .font(.system(size: 10)).foregroundStyle(.secondary).lineSpacing(2)
                            }
                            Spacer()
                            Toggle("", isOn: $app.gemmaSemanticMaskingEnabled)
                                .toggleStyle(.switch).scaleEffect(0.85)
                        }
                        .padding(.vertical, 12)
                        .opacity(app.gemmaSemanticMaskingEnabled ? 1.0 : 0.6)
                        .animation(.easeInOut(duration: 0.15), value: app.gemmaSemanticMaskingEnabled)

                        if !app.gemmaSemanticMaskingEnabled {
                            infoBlock("⚡️ Regex-only mode: ~3× faster. Recommended when Ollama is not loaded or for large files. Some domain-specific identifiers may not be masked.")
                        }
                    }
                }

                // Processing pipeline visual
                settingsCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Processing Pipeline")
                            .font(.system(size: 11, weight: .semibold)).foregroundStyle(.secondary)

                        HStack(spacing: 4) {
                            pipelineStep("JCross\nQuery",   color: Color(red: 0.8, green: 0.5, blue: 1.0), number: 1)
                            pipelineArrow()
                            pipelineStep("Regex\nMask",     color: Color(red: 0.4, green: 0.9, blue: 0.5), number: 2)
                            pipelineArrow()
                            if app.gemmaSemanticMaskingEnabled {
                                pipelineStep("Gemma\nScan", color: Color(red: 0.9, green: 0.6, blue: 0.2), number: 3)
                                pipelineArrow()
                            }
                            pipelineStep("Cloud\nAPI",      color: Color(red: 0.4, green: 0.7, blue: 1.0), number: app.gemmaSemanticMaskingEnabled ? 4 : 3)
                            pipelineArrow()
                            pipelineStep("Gemma\nRestore",  color: Color(red: 0.9, green: 0.4, blue: 0.4), number: app.gemmaSemanticMaskingEnabled ? 5 : 4)
                        }
                        .animation(.easeInOut(duration: 0.2), value: app.gemmaSemanticMaskingEnabled)

                        Text("★ Your real code never reaches external APIs — only abstract logic identifiers.")
                            .font(.system(size: 10)).foregroundStyle(Color(red: 0.4, green: 0.9, blue: 0.5))
                            .padding(.top, 4)
                    }
                }
            }

            // ── Airplane mode indicator ────────────────────────────────
            settingsCard {
                HStack(spacing: 12) {
                    Image(systemName: "airplane")
                        .font(.system(size: 20))
                        .foregroundStyle(app.inferenceMode == .localOnly
                                         ? Color(red: 0.3, green: 1.0, blue: 0.5) : .secondary)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(app.inferenceMode == .localOnly ? "Airplane-mode capable ✓" : "Requires internet connection")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(app.inferenceMode == .localOnly ? .white : .secondary)
                        Text("Local Only mode works with Wi-Fi completely disabled")
                            .font(.system(size: 10)).foregroundStyle(.tertiary)
                    }
                    Spacer()
                }
            }

            // ── Gatekeeper（統合セクション）──────────────────────────────
            sectionHeader("Gatekeeper Mode", icon: "shield.lefthalf.filled")

            Text(AppLanguage.shared.t("Use local LLM as commander, sending only zero-semantic JCross IR to Cloud LLM without showing source code. If conversion fails, error info is resent to request fixes.", "ローカル LLM を司令官にし、Cloud LLM にはソースコードを一切見せず意味ゼロの JCross IR のみを送信します。変換が失敗した場合はエラー情報を Cloud LLM に再送して修正を依頼します。"))
                .font(.system(size: 11)).foregroundStyle(.secondary)

            // 統合カード（Mode + Retry + Pipeline を1か所に集約）
            UnifiedGatekeeperCard()
        }
    }

    // MARK: - Unified Gatekeeper Card
    // Gatekeeper Mode + リトライ（失敗時再送）+ Pipeline を1つのカードに統合
    // 旧: GatekeeperQuickSettingsCard + GatekeeperPipelineSettingsView が別々に存在して混乱を招いていた

    private struct UnifiedGatekeeperCard: View {
        @EnvironmentObject var app: AppState
        @ObservedObject private var gk = GatekeeperModeState.shared
        @State private var availableModels: [String] = []
        @State private var showPipelineDetail = false
        @State private var showFullView = false

        var body: some View {
            VStack(alignment: .leading, spacing: 0) {
                // ── Enable toggle ──────────────────────────────────────
                HStack(spacing: 12) {
                    ZStack {
                        Circle()
                            .fill(gk.isEnabled
                                  ? Color.green.opacity(0.15)
                                  : Color.white.opacity(0.05))
                            .frame(width: 36, height: 36)
                        Image(systemName: gk.isEnabled ? "shield.lefthalf.filled" : "shield")
                            .font(.system(size: 16))
                            .foregroundStyle(gk.isEnabled ? .green : .secondary)
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Gatekeeper Mode")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(.white)
                        Text(gk.isEnabled
                             ? app.t("🟢 Enabled — Local LLM commands. APIs only see JCross IR.", "🟢 有効 — ローカル LLM が司令官。外部 API は JCross IR しか見えない")
                             : app.t("Set Local LLM as commander to hide source code from APIs", "局所 LLM を司令官にして外部 API からソースコードを隠す"))
                            .font(.system(size: 10))
                            .foregroundStyle(gk.isEnabled ? Color.green : .secondary)
                            .lineSpacing(2)
                    }
                    Spacer()
                    Toggle("", isOn: $gk.isEnabled)
                        .toggleStyle(.switch)
                        .scaleEffect(0.85)
                        .tint(.green)
                }
                .padding(.vertical, 12)

                if gk.isEnabled {
                    Divider().opacity(0.15)

                    // ── Commander model ────────────────────────────────
                    HStack(spacing: 8) {
                        Image(systemName: "cpu").font(.system(size: 11)).foregroundStyle(.green)
                        Text("Commander")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                        Spacer()
                        Picker("", selection: $gk.commanderModel) {
                            ForEach(availableModels.isEmpty ? [gk.commanderModel] : availableModels, id: \.self) { m in
                                Text(m).tag(m)
                            }
                        }
                        .pickerStyle(.menu)
                        .frame(width: 240)
                    }
                    .padding(.vertical, 10)

                    Divider().opacity(0.15)

                    // ── 失敗時 Cloud LLM 再送回数（旧: Max Worker Retries）────
                    // 変換が失敗した際にエラー内容を Cloud LLM へ再送して修正を依頼する回数
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(spacing: 8) {
                            Image(systemName: "arrow.triangle.2.circlepath")
                                .font(.system(size: 11)).foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(AppLanguage.shared.t("Cloud LLM Resend Count on Failure", "失敗時 Cloud LLM 再送回数"))
                                    .font(.system(size: 11)).foregroundStyle(.white)
                                Text(AppLanguage.shared.t("Max times to send bug info back to Cloud LLM to request fixes on conversion error", "変換エラー発生時にバグ内容を Cloud LLM に返して修正を依頼する最大回数"))
                                    .font(.system(size: 9)).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(gk.maxWorkerRetries == -1 ? "無制限" : "\(gk.maxWorkerRetries) 回")
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .foregroundStyle(gk.maxWorkerRetries == -1 ? .orange : .white)
                        }
                        Slider(value: Binding(
                            get: { gk.maxWorkerRetries == -1 ? 20 : Double(gk.maxWorkerRetries) },
                            set: { val in gk.maxWorkerRetries = Int(val) == 20 ? -1 : Int(val) }
                        ), in: 0...20, step: 1)
                        .tint(Color(red: 0.4, green: 0.7, blue: 1.0))
                        HStack {
                            Text(AppLanguage.shared.t("0 (No resends)", "0（再送なし）"))
                            Spacer()
                            Text(AppLanguage.shared.t("Unlimited", "無制限"))
                        }
                        .font(.system(size: 8)).foregroundStyle(.tertiary)
                    }
                    .padding(.vertical, 10)

                    Divider().opacity(0.15)

                    // ── External LLM Toggle ────────────────────────────────
                    HStack(spacing: 8) {
                        Image(systemName: "cpu").font(.system(size: 11)).foregroundStyle(.blue)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(app.t("Allow External LLM Commander", "外部LLM司令官の許可"))
                                .font(.system(size: 11)).foregroundStyle(.white)
                            Text(app.t("If OFF, BitNet forces as Commander", "オフ時はBitNetが強制的にCommanderとして動作"))
                                .font(.system(size: 9)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Toggle("", isOn: $gk.allowExternalLLMForCommander).toggleStyle(.switch).scaleEffect(0.85)
                    }
                    .padding(.vertical, 5)

                    if !gk.allowExternalLLMForCommander {
                        HStack(spacing: 8) {
                            Image(systemName: "brain").font(.system(size: 11)).foregroundStyle(.purple)
                            Text(app.t("BitNet Memory", "BitNet 記憶階層"))
                                .font(.system(size: 11)).foregroundStyle(.secondary)
                            Spacer()
                            Picker("", selection: $gk.bitnetMemoryLayerMode) {
                                Text("L1 Only (2B)").tag(GatekeeperModeState.MemoryLayerMode.l1Only)
                                Text("L1-L3 (Large)").tag(GatekeeperModeState.MemoryLayerMode.l1ToL3)
                            }.pickerStyle(.segmented).frame(width: 160)
                        }
                        .padding(.vertical, 5)
                    }

                    Divider().opacity(0.15)

                    // ── Ollama NER Engine ──────────────────────────────────
                    HStack(spacing: 8) {
                        Image(systemName: "bolt.fill").font(.system(size: 11)).foregroundStyle(gk.useOllamaNER ? .yellow : .secondary)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(app.t("Use Ollama NER Engine", "Ollama NER エンジンを使用"))
                                .font(.system(size: 11)).foregroundStyle(.white)
                            Text(app.t("Requires local Ollama. Disable to fix timeouts if Ollama is off.", "ローカルOllama必須。未起動時のフリーズを防ぐにはオフにしてください"))
                                .font(.system(size: 9)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Toggle("", isOn: $gk.useOllamaNER).toggleStyle(.switch).scaleEffect(0.85)
                    }
                    .padding(.vertical, 5)

                    Divider().opacity(0.15)

                    // ── Vault status ───────────────────────────────────
                    HStack(spacing: 8) {
                        Image(systemName: "externaldrive.fill")
                            .font(.system(size: 11))
                            .foregroundStyle(.orange)
                        Group {
                            switch gk.vault.vaultStatus {
                            case .notInitialized:
                                Text(app.t("Vault Uninitialized — Auto-conversion on enable", "Vault 未初期化 — 有効化すると自動変換開始"))
                                    .foregroundStyle(.secondary)
                            case .converting(let p, _):
                                Text(app.t("Converting \(Int(p * 100))%...", "変換中 \(Int(p * 100))%..."))
                                    .foregroundStyle(.orange)
                            case .ready(let n, _):
                                Text(app.t("\(n) files converted ✓", "\(n) ファイル変換済み ✓"))
                                    .foregroundStyle(.green)
                            case .error(let e):
                                Text(e).foregroundStyle(.red)
                            }
                        }
                        .font(.system(size: 10))
                        Spacer()
                        Button("詳細") { showFullView = true }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                            .font(.system(size: 10))
                    }
                    .padding(.vertical, 10)

                    Divider().opacity(0.15)

                    // ── Pipeline 折りたたみサマリー ──────────────────────────
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) { showPipelineDetail.toggle() }
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "arrow.triangle.branch")
                                .font(.system(size: 11)).foregroundStyle(.cyan)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(AppLanguage.shared.t("Processing Pipeline", "処理パイプライン"))
                                    .font(.system(size: 11, weight: .semibold)).foregroundStyle(.white)
                                Text(AppLanguage.shared.t("IR Gen → Vault Split → Cloud LLM → Apply Patch", "IR生成 → Vault分離 → Cloud LLM → パッチ適用"))
                                    .font(.system(size: 9)).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: showPipelineDetail ? "chevron.up" : "chevron.down")
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                    .buttonStyle(.plain)
                    .padding(.vertical, 8)

                    if showPipelineDetail {
                        GatekeeperPipelineSettingsView()
                            .padding(.top, 4)
                            .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                }
            }
            .padding(.horizontal, 14)
            .background(Color.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 10))
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(gk.isEnabled ? Color.green.opacity(0.3) : Color.white.opacity(0.07), lineWidth: 1)
            )
            .task { await loadModels() }
            .sheet(isPresented: $showFullView) {
                GatekeeperModeView()
                    .frame(width: 540, height: 750)
            }
        }

        private func loadModels() async {
            var models: [String] = []
            
            // 1. Fetch Ollama models
            struct TagsResp: Decodable {
                struct M: Decodable { let name: String }
                let models: [M]
            }
            if let url = URL(string: "http://localhost:11434/api/tags"),
               let (data, _) = try? await URLSession.shared.data(from: url),
               let json = try? JSONDecoder().decode(TagsResp.self, from: data) {
                models.append(contentsOf: json.models.map { $0.name })
            }
            
            // 2. Add MLX models
            models.append(contentsOf: MLXRunner.popularModels.map { $0.id })
            
            self.availableModels = models
        }
    }

    // MARK: - MCP Settings (inline — avoids HSplitView layout conflict)

    @ObservedObject private var mcp = MCPEngine.shared

    private var mcpSettings: some View {
        VStack(alignment: .leading, spacing: 20) {
            sectionHeader("MCP Servers", icon: "network")

            infoBlock(app.t(
                "Manage Model Context Protocol servers. Full configuration is available in the Activity Bar \"🔗\" panel.",
                "Model Context Protocol サーバーを管理します。詳細な設定は左のアクティビティバー「🔗」から開けます。"
            ))

            // ── Server list ──────────────────────────────────────────────
            settingsCard {
                VStack(alignment: .leading, spacing: 0) {
                    if mcp.servers.isEmpty {
                        mcpEmptyState
                    } else {
                        mcpServerRows
                    }
                }
            }

            // ── Open full MCP panel ──────────────────────────────────────
            settingsCard {
                HStack(spacing: 12) {
                    Image(systemName: "arrow.up.right.square")
                        .font(.system(size: 16))
                        .foregroundStyle(Color(red: 0.3, green: 0.8, blue: 1.0))
                    VStack(alignment: .leading, spacing: 3) {
                        Text(app.t("Open Full MCP Panel", "フル MCP パネルを開く"))
                            .font(.system(size: 12, weight: .semibold)).foregroundStyle(.white)
                        Text(app.t(
                            "Add/edit servers and browse tools in the Activity Bar MCP section.",
                            "サーバーの追加・編集・ツール一覧はアクティビティバーの MCP セクションから操作できます"
                        ))
                            .font(.system(size: 10)).foregroundStyle(.secondary).lineSpacing(2)
                    }
                    Spacer()
                    Button(app.t("Close & Open", "設定を閉じて開く")) {
                        onDismiss?()
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                            NotificationCenter.default.post(name: Notification.Name("OpenMCPPanel"), object: nil)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .tint(Color(red: 0.2, green: 0.5, blue: 0.85))
                }
            }

            // ── Global kill switch (visible only when a call is active) ──
            if mcp.activeCall != nil {
                settingsCard {
                    HStack(spacing: 12) {
                        Circle().fill(Color.red).frame(width: 8, height: 8)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("MCP RUNNING")
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .foregroundStyle(Color(red: 1.0, green: 0.4, blue: 0.4))
                            if let call = mcp.activeCall {
                                Text("\(call.serverName) → \(call.toolName)  [\(call.elapsedSeconds)s]")
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                        Button {
                            mcp.killActiveCall()
                        } label: {
                            Label("KILL", systemImage: "exclamationmark.octagon.fill")
                                .font(.system(size: 11, weight: .bold))
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.red)
                        .controlSize(.regular)
                    }
                }
            }
        }
    }

    @ViewBuilder private var mcpEmptyState: some View {
        HStack {
            Spacer()
            VStack(spacing: 8) {
                Image(systemName: "network.slash")
                    .font(.system(size: 28))
                    .foregroundStyle(.tertiary)
                Text(app.t("No MCP servers registered", "MCPサーバーが未登録です"))
                    .font(.system(size: 12)).foregroundStyle(.secondary)
                Text(app.t("Add servers from the MCP panel in the Activity Bar.", "アクティビティバーの MCP パネルから追加できます"))
                    .font(.system(size: 10)).foregroundStyle(.tertiary)
            }
            .padding(.vertical, 24)
            Spacer()
        }
    }

    /// One row per server — dedicated @ViewBuilder avoids ForEach Binding overload.
    @ViewBuilder private var mcpServerRows: some View {
        ForEach(mcp.servers, id: \.id) { server in
            mcpServerRow(server)
        }
    }

    private func mcpServerRow(_ server: MCPServerConfig) -> some View {
        let isFirst   = mcp.servers.first?.id == server.id
        let isRunning = mcp.activeCall?.serverName == server.name
        let cmdLabel  = server.transport == .stdio
            ? (server.command.components(separatedBy: " ").first ?? server.command)
            : (server.url.isEmpty ? "http://…" : server.url)
        let modeColor = server.mode == .ai
            ? Color(red: 0.4, green: 0.8, blue: 1.0)
            : Color(red: 0.9, green: 0.7, blue: 0.3)

        return VStack(alignment: .leading, spacing: 0) {
            if !isFirst { Divider().opacity(0.15) }
            HStack(spacing: 10) {
                Circle()
                    .fill(isRunning ? Color.green : Color(red: 0.4, green: 0.4, blue: 0.5))
                    .frame(width: 7, height: 7)
                VStack(alignment: .leading, spacing: 2) {
                    Text(server.name)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(.white)
                    Text(cmdLabel)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                }
                Spacer()
                Text(server.mode == .ai ? "AI" : "Human")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(modeColor)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(modeColor.opacity(0.12), in: Capsule())
                if isRunning {
                    Button { mcp.killActiveCall() } label: {
                        Label(app.t("Stop", "停止"), systemImage: "stop.fill")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(Color(red: 1.0, green: 0.4, blue: 0.4))
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .tint(Color(red: 1.0, green: 0.4, blue: 0.4))
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
        }
    }



    // MARK: - Pipeline step helpers

    private func pipelineStep(_ label: String, color: Color, number: Int) -> some View {
        VStack(spacing: 3) {
            ZStack {
                Circle().fill(color.opacity(0.2)).frame(width: 28, height: 28)
                Text("\(number)").font(.system(size: 10, weight: .bold, design: .monospaced)).foregroundStyle(color)
            }
            Text(label)
                .font(.system(size: 8, design: .monospaced))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(minWidth: 36)
    }

    private func pipelineArrow() -> some View {
        Image(systemName: "arrow.right")
            .font(.system(size: 8))
            .foregroundStyle(.tertiary)
            .frame(maxWidth: .infinity)
    }

    // MARK: - Components

    private func sectionHeader(_ title: String, icon: String) -> some View {
        HStack(spacing: 7) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))
            Text(title)
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(.white)
        }
    }

    private func settingsCard<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content()
            .padding(14)
            .background(Color.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 9))
            .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(Color.white.opacity(0.08), lineWidth: 0.5))
    }

    private func rowLabel<Content: View>(_ label: String, @ViewBuilder trailing: () -> Content) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 12))
                .foregroundStyle(Color(red: 0.75, green: 0.75, blue: 0.88))
            Spacer()
            trailing()
        }
    }

    private func toolToggleRow(icon: String, iconColor: Color, title: String,
                                description: String, isOn: Binding<Bool>) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundStyle(isOn.wrappedValue ? iconColor : .secondary)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(size: 12, weight: .medium))
                    .foregroundStyle(isOn.wrappedValue ? .white : .secondary)
                Text(description).font(.system(size: 10)).foregroundStyle(.tertiary).lineLimit(2)
            }
            Spacer()
            Toggle("", isOn: isOn).toggleStyle(.switch).scaleEffect(0.8)
        }
        .padding(.vertical, 10)
        .opacity(isOn.wrappedValue ? 1.0 : 0.6)
        .animation(.easeInOut(duration: 0.15), value: isOn.wrappedValue)
    }

    private func statCard(_ label: String, value: String, icon: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).font(.system(size: 14)).foregroundStyle(color)
            Text(value).font(.system(size: 16, weight: .bold, design: .monospaced)).foregroundStyle(.white)
            Text(label).font(.system(size: 9)).foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity).padding(10)
        .background(Color.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 7))
    }

    private func memoryNodeRow(_ node: MemoryNode) -> some View {
        HStack(spacing: 8) {
            Circle().fill(zoneColor(node.zone)).frame(width: 5, height: 5)
            Text(node.key)
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundStyle(Color(red: 0.7, green: 0.7, blue: 0.9))
                .frame(width: 130, alignment: .leading)
            Text(node.value.prefix(60) + (node.value.count > 60 ? "…" : ""))
                .font(.system(size: 9)).foregroundStyle(.secondary).lineLimit(1)
            Spacer()
        }
        .padding(.horizontal, 6).padding(.vertical, 2)
    }

    private func infoBlock(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(Color(red: 0.6, green: 0.75, blue: 0.9))
            .lineSpacing(3).padding(10)
            .background(Color(red: 0.12, green: 0.20, blue: 0.30).opacity(0.8),
                        in: RoundedRectangle(cornerRadius: 6))
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func zoneColor(_ zone: MemoryNode.Zone) -> Color {
        switch zone {
        case .front: return Color(red: 0.4, green: 0.9, blue: 0.5)
        case .near:  return Color(red: 0.4, green: 0.7, blue: 1.0)
        case .mid:   return Color(red: 0.8, green: 0.6, blue: 1.0)
        case .deep:  return Color(red: 0.5, green: 0.5, blue: 0.7)
        }
    }

    private var tempColor: Color {
        app.temperature < 0.3 ? Color(red: 0.3, green: 0.9, blue: 0.5)
        : app.temperature < 0.7 ? Color(red: 0.9, green: 0.8, blue: 0.3)
        : Color(red: 0.9, green: 0.5, blue: 0.3)
    }

    // MARK: - Actions

    private func testConnection() {
        testingConnection = true
        connectionTestResult = nil
        Task {
            let models = await OllamaClient.shared.listModels()
            await MainActor.run {
                testingConnection = false
                if models.isEmpty {
                    connectionTestResult = "✗ No models found at \(app.ollamaEndpoint)"
                } else {
                    connectionTestResult = "✓ \(models.count) model(s): \(models.prefix(3).joined(separator: ", "))"
                    app.ollamaModels = models
                    if models.contains(app.activeOllamaModel) {
                        app.modelStatus = .ollamaReady(model: app.activeOllamaModel)
                    }
                }
            }
        }
    }

    private func testAnthropic() {
        testingAnthropic = true
        anthropicTestResult = nil
        Task {
            await AnthropicClient.shared.configure(apiKey: app.anthropicApiKey)
            // Send a minimal ping request
            let stream = AnthropicClient.shared.streamGenerate(
                model: app.activeAnthropicModel,
                systemPrompt: "You are a test assistant.",
                messages: [("user", "Respond with exactly: OK")],
                maxTokens: 10
            )
            var result = ""
            do {
                for try await event in stream {
                    if case .token(let t) = event { result += t }
                    if case .done = event { break }
                    if case .error(let e) = event { result = "ERROR: \(e)"; break }
                }
            } catch {
                result = "ERROR: \(error.localizedDescription)"
            }
            await MainActor.run {
                testingAnthropic = false
                if result.lowercased().contains("ok") || result.lowercased().contains("error") == false {
                    anthropicTestResult = "✓ Connected (\(app.activeAnthropicModel))"
                    app.modelStatus = .anthropicReady(model: app.activeAnthropicModel, maskedKey: "sk-ant-***")
                } else {
                    anthropicTestResult = "✗ \(result.prefix(60))"
                }
            }
        }
    }

    // MARK: - BitNet Settings

    private var bitnetSettings: some View {
        VStack(alignment: .leading, spacing: 20) {

            // ── Gatekeeper Commander 説明 ─────────────────────────────────
            sectionHeader("Gatekeeper Commander", icon: "lock.shield")

            settingsCard {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 12) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Color(red: 0.7, green: 0.4, blue: 1.0).opacity(0.15))
                                .frame(width: 36, height: 36)
                            Image(systemName: "cpu.fill")
                                .font(.system(size: 16))
                                .foregroundStyle(Color(red: 0.7, green: 0.4, blue: 1.0))
                        }
                        VStack(alignment: .leading, spacing: 3) {
                            Text(app.t("BitNet b1.58 — Local Commander LLM", "BitNet b1.58 — ローカル Commander LLM"))
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(.white)
                            Text(app.t("Gatekeeper Mode exclusive. Zero-network, privacy-first inference.", "Gatekeeper Mode 専用。ゼロネットワーク・プライバシー優先推論"))
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                        }
                        Spacer()

                        // ステータスバッジ
                        Group {
                            switch BitNetEngineManager.shared.status {
                            case .ready(let name, _):
                                Label(name, systemImage: "circle.fill")
                                    .foregroundStyle(Color(red: 0.3, green: 0.9, blue: 0.5))
                                    .font(.system(size: 10, weight: .semibold))
                                    .padding(.horizontal, 8).padding(.vertical, 3)
                                    .background(Color(red: 0.3, green: 0.9, blue: 0.5).opacity(0.1),
                                                in: Capsule())
                            case .notInstalled:
                                Label(app.t("Not Installed", "未インストール"), systemImage: "circle")
                                    .foregroundStyle(Color(red: 0.7, green: 0.4, blue: 1.0))
                                    .font(.system(size: 10, weight: .semibold))
                                    .padding(.horizontal, 8).padding(.vertical, 3)
                                    .background(Color(red: 0.7, green: 0.4, blue: 1.0).opacity(0.1),
                                                in: Capsule())
                            default:
                                EmptyView()
                            }
                        }
                    }

                    Divider().opacity(0.2)

                    // フロー説明
                    VStack(alignment: .leading, spacing: 6) {
                        Text(app.t("Priority:", "優先順位:"))
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(.secondary)

                        HStack(spacing: 8) {
                            Text("①")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundStyle(Color(red: 0.7, green: 0.4, blue: 1.0))
                            Text(app.t("BitNet b1.58 (If installed)", "BitNet b1.58 (インストール済みの場合)"))
                                .font(.system(size: 10))
                                .foregroundStyle(Color(red: 0.85, green: 0.85, blue: 0.95))
                        }
                        HStack(spacing: 8) {
                            Text("②")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundStyle(Color(red: 0.5, green: 0.7, blue: 1.0))
                            Text(app.t("Ollama (localhost:11434) — Auto Fallback", "Ollama (localhost:11434) — 自動フォールバック"))
                                .font(.system(size: 10))
                                .foregroundStyle(Color(red: 0.65, green: 0.65, blue: 0.75))
                        }
                    }
                    .padding(10)
                    .background(Color(red: 0.7, green: 0.4, blue: 1.0).opacity(0.05),
                                in: RoundedRectangle(cornerRadius: 8))
                }
            }

            // ── BitNetSetupView を埋め込み ──────────────────────────────────
            sectionHeader(app.t("BitNet b1.58 Setup", "BitNet b1.58 セットアップ"), icon: "arrow.down.circle")

            BitNetSetupView()
                .frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(Color(red: 0.7, green: 0.4, blue: 1.0).opacity(0.25), lineWidth: 1)
                )
        }
    }

    @MainActor
    private func addCustomFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        panel.canCreateDirectories = false
        
        if panel.runModal() == .OK {
            for url in panel.urls {
                if !vault.scanTargets.contains(where: { $0.url == url }) {
                    vault.scanTargets.append(ScanTarget(
                        url: url,
                        name: url.lastPathComponent,
                        isEnabled: true,
                        scanDepth: 3
                    ))
                }
            }
        }
    }
}

// MARK: - AssetMapView

struct AssetMapView: View {
    @ObservedObject var vault: OSAssetMemoryVault
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("L3.5 PC Asset Map (JCross)")
                    .font(.headline)
                Spacer()
                Button("閉じる") { dismiss() }
            }
            .padding()
            .background(Color(NSColor.windowBackgroundColor))
            
            Divider()
            
            TextEditor(text: .constant(vault.assetMap?.toJCrossString() ?? "No map available."))
                .font(.system(size: 11, design: .monospaced))
                .padding()
        }
        .frame(minWidth: 500, minHeight: 600)
    }
}
