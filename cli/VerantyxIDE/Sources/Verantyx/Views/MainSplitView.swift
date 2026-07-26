import SwiftUI
import UniformTypeIdentifiers

// MARK: - MainSplitView
// Verantyx IDE layout — switches between:
//   • Human Mode          → 4-pane IDE (Activity + File Tree + Chat + Diff/Terminal)
//   • AI Priority         → Full-screen 2-pane (Chat | Artifact) — AIModeLayoutView
//   • Human Priority Mode → VS Code-style (File Tree | Code Editor | AI Chat right)
//   • Gatekeeper Mode     → Human Priority layout + persistent green Gatekeeper border

struct MainSplitView: View {
    @EnvironmentObject var app: AppState
    @State private var activitySection: ActivityBarView.ActivitySection? = .explorer

    @State private var showSettings     = false
    @State private var showMCPQuick     = false
    @State private var showExtensionStore = false

    /// True once any non-system message exists — locks the mode toggle
    private var chatStarted: Bool {
        app.messages.contains { $0.role != .system }
    }

    var body: some View {
        ZStack {
            Group {
                    // ── Enterprise Gatekeeper Mode Layout ─
                    ZStack {
                        HumanPriorityModeView()
                            .environmentObject(app)
                        // Persistent green border — makes mode boundary unmistakable
                        RoundedRectangle(cornerRadius: 0)
                            .strokeBorder(
                                LinearGradient(
                                    colors: [Color(red: 0.1, green: 0.9, blue: 0.45).opacity(0.85),
                                             Color(red: 0.1, green: 0.6, blue: 0.35).opacity(0.5)],
                                    startPoint: .topLeading, endPoint: .bottomTrailing
                                ),
                                lineWidth: 2.5
                            )
                            .ignoresSafeArea()
                            .allowsHitTesting(false)
                        // (Gatekeeper status pill removed)
                    }

                // ── MCP Quick Panel global overlay (⌘⇧M) ────────────────────────
                if showMCPQuick {
                    MCPQuickPanel(isPresented: $showMCPQuick)
                        .environmentObject(app)
                        .zIndex(99)
                        .transition(.scale(scale: 0.96).combined(with: .opacity))
                }
            }
            .animation(.easeInOut(duration: 0.25), value: app.operationMode)

            // ── Settings overlay ──────────────────────────────────────────
            if showSettings {
                // Dim background — tap to close
                Color.black.opacity(0.55)
                    .ignoresSafeArea()
                    .onTapGesture { withAnimation(.easeOut(duration: 0.18)) { showSettings = false } }
                    .transition(.opacity)

                // Settings panel — centered, FIXED size, no resize
                SettingsView(onDismiss: {
                    withAnimation(.easeOut(duration: 0.18)) { showSettings = false }
                })
                .environmentObject(app)
                .transition(.scale(scale: 0.96).combined(with: .opacity))
                .zIndex(10)
            }
            
            // ── Extension Store overlay ───────────────────────────────────
            if showExtensionStore {
                Color.black.opacity(0.55)
                    .ignoresSafeArea()
                    .onTapGesture { withAnimation(.easeOut(duration: 0.18)) { showExtensionStore = false } }
                    .transition(.opacity)
                
                ExtensionStoreView(onDismiss: {
                    withAnimation(.easeOut(duration: 0.18)) { showExtensionStore = false }
                })
                .environmentObject(app)
                .transition(.scale(scale: 0.96).combined(with: .opacity))
                .zIndex(15)
            }
            
            // ── VS Code Extension UI Overlay ──────────────────────────────
            ExtensionUIPanelView()
                .zIndex(105)
                
            // ── Floating Action Button (Expert Bot) ───────────────────────
            ExpertBotFloatingView()
                .zIndex(200)
                
            // Removed Mode Selector Overlay
        }
        .toolbar { toolbarContent }
        .onAppear { app.connectOllama() }
        // ── Open Settings when gear is tapped ──────────────────────────────
        .onChange(of: activitySection) { _, section in
            if section == .settings {
                withAnimation(.easeOut(duration: 0.18)) { showSettings = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                    activitySection = .explorer
                }
            }
        }
        // ── "フル MCP パネルを開く" ボタンから送られる通知を受け取る ──────────
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("OpenMCPPanel"))) { _ in
            withAnimation(.easeOut(duration: 0.18)) {
                showSettings = false
                activitySection = .mcp
            }
        }
        // ── Human Mode: file write approval sheet ────────────────────────────
        .sheet(item: $app.pendingFileApproval) { req in
            FileApprovalView(req: req)
                .environmentObject(app)
        }
        // ── Vera-α layer: save-preview approval sheet ────────────────────────
        .sheet(item: $app.pendingVeraSave) { req in
            VeraSaveApprovalView(req: req)
                .environmentObject(app)
        }
    } // end body


    // MARK: - Human Mode (4-pane IDE)



    // MARK: - Human Mode (4-pane IDE)

    private var humanModeLayout: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {

                // ① Activity bar (fixed 48pt)
                ActivityBarView(selectedSection: $activitySection)
                    .frame(width: 48)

                // ② Left + Center + Right
                if let section = activitySection {
                    ResizableHSplit(
                        minLeft: 50, maxLeft: 99999, minRight: 100, initialLeft: 240
                    ) {
                        // ── Left pane ─────────────────────────────────────
                        Group {
                            switch section {
                            case .mcp:       MCPView()
                            case .evolution: SelfEvolutionView().environmentObject(app)
                            case .search:    GlobalSearchView().environmentObject(app)
                            case .git:       GitPanelView().environmentObject(app)
                            case .vrbridge:  VRBridgePanelView()
                            default:         FileTreeView()
                            }
                        }
                        .frame(maxHeight: .infinity)
                    } right: {
                        centerAndRightPanes
                    }
                } else {
                    centerAndRightPanes
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // ── Human Mode: pending approval banner ──────────────────
            if app.operationMode == .gatekeeper, let diff = app.pendingDiff {
                humanApprovalBanner(diff: diff)
            }



            Divider().opacity(0.4)
            StatusBarView(terminal: app.terminal)
        }
        .background(Color(red: 0.11, green: 0.11, blue: 0.14))
        .toastOverlay()
    }

    @ViewBuilder
    private var centerAndRightPanes: some View {
        ResizableHSplit(
            minLeft: 100, maxLeft: 99999, minRight: 100, initialLeft: 420
        ) {
            // ── Center: Chat ───────────────────────────────
            VStack(spacing: 0) {
                AgentChatView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                if app.showProcessLog {
                    ResizableVSplit(
                        minTop: 50, maxTop: 99999, minBottom: 50, initialTop: 9999
                    ) {
                        EmptyView()
                    } bottom: {
                        ThinkingLogView()
                    }
                    .frame(height: 180)
                }
            }
        } right: {
            // ── Right: Artifact/Diff (top) + Terminal (bottom) ──
            ResizableVSplit(
                minTop: 50, maxTop: 99999, minBottom: 50, initialTop: 400
            ) {
                // Artifact panel — has Diff tab built-in
                ArtifactPanelView()
                    .environmentObject(app)
            } bottom: {
                TerminalPanelView(terminal: app.terminal)
                    .environmentObject(app)
            }
        }
    }

    // MARK: - Human Mode: approval banner

    private func humanApprovalBanner(diff: FileDiff) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Color(red: 1.0, green: 0.75, blue: 0.2))
                .font(.system(size: 13))

            VStack(alignment: .leading, spacing: 2) {
                Text(app.t("Pending approval: ", "承認待ち: ") + diff.fileURL.lastPathComponent)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color(red: 0.95, green: 0.88, blue: 0.60))
                Text(app.t("AI has proposed changes. Review in the Diff tab.", "AIが変更を提案しています。Diffタブで内容を確認してください。"))
                    .font(.system(size: 11))
                    .foregroundStyle(Color(red: 0.65, green: 0.65, blue: 0.75))
            }

            Spacer()

            // Quick Reject
            Button {
                app.pendingDiff = nil
                app.showDiff    = false
                app.addSystemMessage("↩️ " + app.t("Change rejected", "変更を却下しました"))
            } label: {
                Text(app.t("Reject", "却下"))
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color(red: 0.9, green: 0.4, blue: 0.4))
                    .padding(.horizontal, 16).padding(.vertical, 5)
                    .background(Color(red: 0.35, green: 0.12, blue: 0.12).opacity(0.6),
                                in: RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6)
                        .stroke(Color(red: 0.9, green: 0.4, blue: 0.4).opacity(0.5), lineWidth: 1))
            }
            .contentShape(Rectangle())
            .buttonStyle(.plain)

            // Quick Approve
            Button {
                do {
                    try diff.modifiedContent.write(to: diff.fileURL, atomically: true, encoding: .utf8)
                    app.selectedFileContent = diff.modifiedContent
                    app.pendingDiff = nil
                    app.showDiff    = false
                    app.addSystemMessage("✅ " + app.t("Change approved & applied: ", "変更を承認・適用しました: ") + diff.fileURL.lastPathComponent)
                } catch {
                    app.addSystemMessage("❌ " + app.t("Write failed: ", "書き込み失敗: ") + error.localizedDescription)
                }
            } label: {
                Text(app.t("Approve", "承認"))
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color(red: 0.3, green: 0.9, blue: 0.45))
                    .padding(.horizontal, 16).padding(.vertical, 5)
                    .background(Color(red: 0.12, green: 0.30, blue: 0.18).opacity(0.7),
                                in: RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6)
                        .stroke(Color(red: 0.3, green: 0.9, blue: 0.45).opacity(0.5), lineWidth: 1))
            }
            .contentShape(Rectangle())
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color(red: 0.16, green: 0.14, blue: 0.08))
        .overlay(Rectangle().fill(Color(red: 1.0, green: 0.75, blue: 0.2).opacity(0.3)).frame(height: 1),
                 alignment: .top)
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .animation(.easeInOut(duration: 0.2), value: app.pendingDiff != nil)
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .navigation) {
            Button { app.openWorkspace() } label: {
                Image(systemName: "folder.badge.plus").help(app.t("Open Folder", "フォルダーを開く"))
            }
        }



        // ── MCP Quick Panel toggle (⌘⇧M) ───────────────────────────────────
        ToolbarItem(placement: .primaryAction) {
            Button {
                withAnimation(.easeOut(duration: 0.18)) { showMCPQuick.toggle() }
            } label: {
                ZStack(alignment: .topTrailing) {
                    Image(systemName: "puzzlepiece.extension")
                        .foregroundStyle(showMCPQuick
                                         ? Color(red: 0.4, green: 0.85, blue: 1.0)
                                         : MCPEngine.shared.activeCall != nil
                                             ? Color(red: 1.0, green: 0.4, blue: 0.4)
                                             : .secondary)
                    // Dot badge if MCP tool is running
                    if MCPEngine.shared.activeCall != nil {
                        Circle()
                            .fill(Color.red)
                            .frame(width: 6, height: 6)
                            .offset(x: 2, y: -2)
                    }
                }
            }
            .keyboardShortcut("m", modifiers: [.command, .shift])
            .help(app.t("MCP Quick Panel (⌘⇧M)", "MCP クイックパネル (⌘⇧M)"))
        }

        // ── Terminal toggle ─────────────────────────────────────────────────
        ToolbarItem(placement: .primaryAction) {
            Button {
                withAnimation(.easeInOut(duration: 0.15)) { app.showProcessLog.toggle() }
            } label: {
                Image(systemName: "terminal")
                    .symbolVariant(app.showProcessLog ? .fill : .none)
                    .foregroundStyle(app.showProcessLog
                                     ? Color(red: 0.3, green: 1.0, blue: 0.5)
                                     : .secondary)
            }
            .help(app.t("Toggle Terminal (⌘⇧L)", "ターミナル切替 (⌘⇧L)"))
        }

        // ── Load VS Code Extension ──────────────────────────────────────────
        ToolbarItem(placement: .primaryAction) {
            Menu {
                Button(app.t("Extension Store (Open VSX)", "拡張機能ストア (Open VSX)")) {
                    withAnimation(.easeOut(duration: 0.18)) { showExtensionStore = true }
                }
                Button(app.t("Install from VSIX...", "VSIXからインストール...")) {
                    let panel = NSOpenPanel()
                    panel.allowedContentTypes = [UTType(filenameExtension: "vsix")].compactMap { $0 }
                    panel.allowsMultipleSelection = false
                    panel.canChooseDirectories = false
                    if panel.runModal() == .OK, let url = panel.url {
                        Task {
                            do {
                                try await VSIXPackageManager.shared.installExtension(from: url)
                                app.addSystemMessage(app.t("✅ Loaded VS Code Extension: ", "✅ VS Code 拡張をロード: ") + url.lastPathComponent)
                            } catch {
                                app.addSystemMessage(app.t("❌ Failed to load extension: ", "❌ 拡張機能のロードに失敗: ") + error.localizedDescription)
                            }
                        }
                    }
                }
            } label: {
                Image(systemName: "shippingbox")
                    .foregroundStyle(.secondary)
            }
            .help(app.t("VS Code Extensions", "VS Code 拡張機能"))
        }


    }

    private var shortModelLabel: String {
        switch app.modelStatus {
        case .ollamaReady(let m):   return m.components(separatedBy: ":").first ?? m
        case .mlxReady(let m):      return "MLX:" + (m.components(separatedBy: "/").last ?? m)
        case .bitnetReady(let m):   return "⚡" + m.components(separatedBy: "-").prefix(3).joined(separator: "-")
        case .connecting:            return "connecting…"
        case .error:                 return "error"
        default:                     return "no model"
        }
    }
}

// MARK: - FileApprovalView
// A polished modal that shows what the AI wants to write.
// Suspends AgentLoop via CheckedContinuation until user decides.

struct FileApprovalView: View {
    @EnvironmentObject var app: AppState
    let req: FileApprovalRequest

    var body: some View {
        VStack(spacing: 0) {

            // ─ Header ───────────────────────────────────────────────────
            HStack(spacing: 12) {
                // Operation icon
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(req.isNewFile
                              ? Color(red: 0.2, green: 0.5, blue: 0.9).opacity(0.18)
                              : Color(red: 0.9, green: 0.55, blue: 0.1).opacity(0.18))
                        .frame(width: 40, height: 40)
                    Image(systemName: req.isNewFile ? "doc.badge.plus" : "pencil.line")
                        .font(.system(size: 18))
                        .foregroundStyle(req.isNewFile
                                         ? Color(red: 0.4, green: 0.7, blue: 1.0)
                                         : Color(red: 1.0, green: 0.65, blue: 0.2))
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text(req.displayTitle)
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Color(red: 0.92, green: 0.92, blue: 0.98))
                    Text(req.shortPath)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(Color(red: 0.55, green: 0.65, blue: 0.85))
                        .lineLimit(1)
                }

                Spacer()

                // 小さいベッジ
                Text(req.isNewFile ? "NEW" : "EDIT")
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .foregroundStyle(req.isNewFile
                                     ? Color(red: 0.3, green: 0.85, blue: 0.55)
                                     : Color(red: 1.0, green: 0.65, blue: 0.2))
                    .padding(.horizontal, 7).padding(.vertical, 3)
                    .background(
                        Capsule()
                            .fill(req.isNewFile
                                  ? Color(red: 0.3, green: 0.85, blue: 0.55).opacity(0.15)
                                  : Color(red: 1.0, green: 0.65, blue: 0.2).opacity(0.15))
                            .overlay(Capsule()
                                .stroke(req.isNewFile
                                        ? Color(red: 0.3, green: 0.85, blue: 0.55).opacity(0.4)
                                        : Color(red: 1.0, green: 0.65, blue: 0.2).opacity(0.4),
                                        lineWidth: 0.8))
                    )
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 14)

            Divider().opacity(0.25)

            // ─ Content diff ──────────────────────────────────────────────
            ScrollView([.vertical, .horizontal]) {
                VStack(alignment: .leading, spacing: 0) {
                    if req.isNewFile {
                        // New file — show full content with green "+" markers
                        ForEach(Array(req.newContent.components(separatedBy: "\n").enumerated()), id: \.offset) { i, line in
                            approvalDiffLine("+", text: "  " + line,
                                            bg: Color(red: 0.1, green: 0.3, blue: 0.15).opacity(0.6),
                                            fg: Color(red: 0.5, green: 0.95, blue: 0.65))
                        }
                    } else {
                        // Existing file — minimal unified diff (context ±3 lines)
                        let diffLines = buildUnifiedDiff(original: req.originalContent,
                                                         modified: req.newContent)
                        ForEach(Array(diffLines.enumerated()), id: \.offset) { _, entry in
                            approvalDiffLine(entry.marker, text: entry.text,
                                            bg: entry.bg, fg: entry.fg)
                        }
                    }
                }
                .padding(.vertical, 8)
                .padding(.horizontal, 4)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Color(red: 0.06, green: 0.06, blue: 0.09))
            .frame(maxHeight: .infinity)

            Divider().opacity(0.25)

            // ─ Action buttons ───────────────────────────────────────────
            HStack(spacing: 12) {
                Spacer()

                // Reject
                Button {
                    app.rejectFileWrite()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "xmark")
                            .font(.system(size: 11, weight: .semibold))
                        Text(app.t("Cancel", "キャンセル"))
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .foregroundStyle(Color(red: 0.9, green: 0.4, blue: 0.4))
                    .padding(.horizontal, 20).padding(.vertical, 9)
                    .contentShape(Rectangle())
                    .background(Color(red: 0.32, green: 0.10, blue: 0.10).opacity(0.7),
                                in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .stroke(Color(red: 0.9, green: 0.4, blue: 0.4).opacity(0.5), lineWidth: 1))
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .keyboardShortcut(.escape)

                // Approve
                Button {
                    app.approveFileWrite()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark")
                            .font(.system(size: 11, weight: .semibold))
                        Text(app.t("Approve & Apply", "承認して適用"))
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .foregroundStyle(Color(red: 0.3, green: 0.92, blue: 0.5))
                    .padding(.horizontal, 20).padding(.vertical, 9)
                    .contentShape(Rectangle())
                    .background(Color(red: 0.10, green: 0.28, blue: 0.15).opacity(0.8),
                                in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .stroke(Color(red: 0.3, green: 0.92, blue: 0.5).opacity(0.5), lineWidth: 1))
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .keyboardShortcut(.return, modifiers: .command)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
            .background(Color(red: 0.11, green: 0.11, blue: 0.15))
        }
        .background(Color(red: 0.09, green: 0.09, blue: 0.12))
        .frame(minWidth: 640, idealWidth: 760, maxWidth: 960,
               minHeight: 420, idealHeight: 560, maxHeight: 720)
    }

    // MARK: - Diff line helper

    private struct DiffEntry {
        let marker: String
        let text: String
        let bg: Color
        let fg: Color
    }

    @ViewBuilder
    private func approvalDiffLine(_ marker: String, text: String, bg: Color, fg: Color) -> some View {
        HStack(spacing: 0) {
            Text(marker)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(fg)
                .frame(width: 18, alignment: .center)
            Text(text)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(marker == " " ? Color(red: 0.55, green: 0.55, blue: 0.68) : fg)
                .lineLimit(1)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.vertical, 1)
        .background(bg)
    }

    /// Build a lightweight unified diff (context ±3 lines) without Foundation Diff.
    private func buildUnifiedDiff(original: String, modified: String) -> [DiffEntry] {
        let oLines = original.components(separatedBy: "\n")
        let mLines = modified.components(separatedBy: "\n")
        var entries: [DiffEntry] = []

        // 簡易LCS：行単位で差分を計算
        var oIdx = 0, mIdx = 0
        while oIdx < oLines.count || mIdx < mLines.count {
            let ol = oIdx < oLines.count ? oLines[oIdx] : nil
            let ml = mIdx < mLines.count ? mLines[mIdx] : nil

            if ol == ml {
                entries.append(DiffEntry(marker: " ", text: "  " + (ol ?? ""),
                                         bg: .clear, fg: .secondary))
                oIdx += 1; mIdx += 1
            } else {
                if let ol { // removed
                    entries.append(DiffEntry(marker: "-", text: "  " + ol,
                                             bg: Color(red: 0.35, green: 0.08, blue: 0.08).opacity(0.5),
                                             fg: Color(red: 1.0, green: 0.45, blue: 0.45)))
                    oIdx += 1
                }
                if let ml { // added
                    entries.append(DiffEntry(marker: "+", text: "  " + ml,
                                             bg: Color(red: 0.08, green: 0.28, blue: 0.12).opacity(0.5),
                                             fg: Color(red: 0.45, green: 0.95, blue: 0.60)))
                    mIdx += 1
                }
            }
        }
        return entries
    }
}
