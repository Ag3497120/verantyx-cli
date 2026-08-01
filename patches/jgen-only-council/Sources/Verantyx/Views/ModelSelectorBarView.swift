import SwiftUI

/// The chip row sitting directly above the chat input: model selection,
/// auditor toggle, backend badge, operation mode.
///
/// Extracted from `AgentChatView.modelSelectorBar` so it has room to cover
/// all four local backends. Previously the picker only knew MLX and Ollama,
/// which meant:
///   - a loaded JGEN model had to be selected from Settings and then showed
///     up in the badge as "MLX" (the badge only distinguished Ollama vs
///     everything-else)
///   - BitNet model selection lived in `ModelPickerView`, a 600-line view
///     with zero call sites -- users could not reach it at all
/// Both are now reachable from here. Stop/Send stay in `AgentChatView` so
/// this file never touches `inputText`/`sendMessage`.
struct ModelSelectorBarView: View {
    @EnvironmentObject var app: AppState
    @ObservedObject private var jgen = JGenConverter.shared
    @ObservedObject private var bitnet = BitNetEngineManager.shared

    /// Models Ollama currently holds in VRAM, with an eject action. Carried
    /// over from the deleted `ModelPickerView` -- it was the only way to see
    /// or free VRAM, and that view had no call sites, so this capability was
    /// unreachable in practice.
    @State private var loadedModels: [OllamaClient.RunningModel] = []
    @State private var ejectingModel: String?
    @State private var showVRAM = false

    @ObservedObject private var council = CouncilSettingsStore.shared
    @State private var showJGenOptions = false
    @State private var includeWebRecommendations = true
    @State private var showPendingToolCalls = false
    @State private var showReasoningTimeline = false

    /// One selectable entry across every local backend. A plain `Picker` over
    /// `String` (what this used to be) can't express per-row spinners, size
    /// subtitles, or rows disabled with an explanation -- JGEN needs all
    /// three, so this is a `Menu` over a typed value instead.
    private enum SelectableModel: Hashable {
        case mlx(String)
        case ollama(String)
        case bitnet(String)
        case jgen(String)
    }

    private var currentSelection: SelectableModel? {
        switch app.modelStatus {
        case .mlxReady(let m), .mlxDownloading(let m): return .mlx(m)
        case .ollamaReady(let m): return .ollama(m)
        case .bitnetReady(let m): return .bitnet(m)
        case .jcrossReady(let m): return .jgen(m)
        default: return nil
        }
    }

    private var currentLabel: String {
        switch currentSelection {
        case .mlx(let m), .ollama(let m), .bitnet(let m), .jgen(let m): return m
        case nil:
            // Nothing loaded yet -- fall back to whatever Gatekeeper has
            // configured, matching the old picker's behavior.
            let cmd = GatekeeperModeState.shared.commanderModel
            return cmd.contains("mlx") ? app.activeMlxModel : app.getOllamaModel()
        }
    }

    private func select(_ model: SelectableModel) {
        switch model {
        case .mlx(let m):
            GatekeeperModeState.shared.commanderModel = m
            app.activeMlxModel = m
            app.loadMLXModel(model: m)
        case .ollama(let m):
            GatekeeperModeState.shared.commanderModel = m
            app.setOllamaModel(m)
            app.connectOllama()
        case .bitnet(let name):
            if let cfg = bitnet.installedConfigs.first(where: { $0.modelName == name }) {
                bitnet.activate(cfg)
                app.addSystemMessage("⚡ BitNet \(name) を有効化しました")
            }
        case .jgen(let name):
            app.loadJGenModel(name)
        }
    }

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                Text("Gatekeeper")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(Color.green)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 4)
                    .background(Color.green.opacity(0.1))
                    .cornerRadius(4)

                modelMenu

                // JGEN-only: the memory sources and layer knobs only mean
                // anything when the hidden-state engine is actually driving
                // the model, so this chip appears only for .jcrossReady.
                if case .jcrossReady = app.modelStatus {
                    Button {
                        showJGenOptions = true
                    } label: {
                        Image(systemName: "slider.horizontal.3")
                            .font(.system(size: 11))
                            .foregroundStyle(Color(red: 1.0, green: 0.72, blue: 0.35))
                    }
                    .buttonStyle(.plain)
                    .help(app.t("JGEN memory & layer options", "JGENの記憶・層オプション"))
                    .popover(isPresented: $showJGenOptions) { jgenOptionsPopover }
                    .sheet(isPresented: $showPendingToolCalls) { PendingToolCallsView() }
                    .sheet(isPresented: $showReasoningTimeline) { ReasoningTimelineView() }
                }

                Divider().frame(height: 16).opacity(0.5)

                auditorControls

                Divider().frame(height: 16).opacity(0.5)

                backendBadge

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
        .task {
            // BitNet models are discovered from disk sidecars; without this
            // the section would stay empty until the user opened Settings.
            if bitnet.installedConfigs.isEmpty { await bitnet.checkInstallation() }
            jgen.refreshConvertedModelsList()
        }
    }

    // MARK: - Model menu

    private var modelMenu: some View {
        Menu {
            if !MLXRunner.popularModels.isEmpty {
                Section("MLX (Native)") {
                    ForEach(MLXRunner.popularModels) { m in
                        Button(m.displayName) { select(.mlx(m.id)) }
                    }
                }
            }
            if !app.ollamaModels.isEmpty {
                Section("Ollama (Local)") {
                    ForEach(app.ollamaModels, id: \.self) { m in
                        Button(m) { select(.ollama(m)) }
                    }
                }
            }
            if !bitnet.installedConfigs.isEmpty {
                Section("BitNet (1-bit)") {
                    ForEach(bitnet.installedConfigs, id: \.modelName) { cfg in
                        Button(cfg.modelName) { select(.bitnet(cfg.modelName)) }
                    }
                }
            }
            if !jgen.convertedModels.isEmpty {
                Section("JGEN (hidden-state)") {
                    ForEach(jgen.convertedModels, id: \.self) { name in
                        // Architectures the Rust engine can't run forward
                        // (hybrid SSM etc.) still convert as a static weight
                        // lexicon, so they appear here but must not be
                        // loadable for chat -- same rule and wording as the
                        // JGEN settings section.
                        Button(name) { select(.jgen(name)) }
                            .disabled(!jgen.isArchSupported(name))
                    }
                }
            }
            if app.ollamaModels.isEmpty && jgen.convertedModels.isEmpty && bitnet.installedConfigs.isEmpty {
                Section("Ollama (Not Connected)") {
                    Button("gemma4:26b") { select(.ollama("gemma4:26b")) }
                }
            }
        } label: {
            HStack(spacing: 4) {
                if app.jgenLoadingModel != nil {
                    ProgressView().controlSize(.mini)
                }
                Text(currentLabel)
                    .font(.system(size: 11, design: .monospaced))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            .frame(width: 170, alignment: .leading)
        }
        .menuStyle(.borderlessButton)
        .help(app.jgenLoadError.map { "JGEN load failed: \($0)" }
              ?? app.t("Select a model (MLX / Ollama / BitNet / JGEN)",
                       "モデルを選択 (MLX / Ollama / BitNet / JGEN)"))
    }

    // MARK: - Auditor

    @ViewBuilder
    private var auditorControls: some View {
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
    }

    // MARK: - Backend badge

    /// Previously this only asked "is it Ollama?" and labeled everything else
    /// "MLX", so a loaded JGEN or BitNet model was actively mislabeled.
    private var backendBadge: some View {
        let (label, color): (String, Color) = {
            switch app.modelStatus {
            case .ollamaReady:
                return ("OLLAMA", Color(red: 0.45, green: 0.9, blue: 0.6))
            case .mlxReady, .mlxDownloading:
                return ("MLX", Color(red: 0.65, green: 0.5, blue: 1.0))
            case .bitnetReady:
                return ("BITNET", Color(red: 0.4, green: 0.75, blue: 1.0))
            case .jcrossReady:
                return ("JGEN", Color(red: 1.0, green: 0.72, blue: 0.35))
            case .anthropicReady:
                return ("API", Color(red: 0.9, green: 0.6, blue: 0.4))
            case .ready:
                return ("LOCAL", Color(red: 0.7, green: 0.7, blue: 0.75))
            case .connecting, .downloading:
                return ("…", Color(red: 0.6, green: 0.6, blue: 0.65))
            case .error:
                return ("ERROR", Color(red: 0.95, green: 0.45, blue: 0.45))
            case .none:
                return ("—", Color(red: 0.5, green: 0.5, blue: 0.55))
            }
        }()
        return Button {
            showVRAM = true
            Task { loadedModels = await OllamaClient.shared.loadedModels() }
        } label: {
            Text(label)
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundStyle(Color(red: 0.15, green: 0.15, blue: 0.18))
                .padding(.horizontal, 6).padding(.vertical, 2)
                .background(color, in: RoundedRectangle(cornerRadius: 3))
        }
        .buttonStyle(.plain)
        .help(app.t("Active backend — click for VRAM usage",
                    "使用中のバックエンド — クリックでVRAM使用状況"))
        .popover(isPresented: $showVRAM) { vramPopover }
    }

    private var vramPopover: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label(app.t("Loaded in VRAM", "VRAMに読み込み中"), systemImage: "memorychip")
                    .font(.system(size: 11, weight: .semibold))
                Spacer()
                Button {
                    Task { loadedModels = await OllamaClient.shared.loadedModels() }
                } label: {
                    Image(systemName: "arrow.clockwise").font(.system(size: 10))
                }
                .buttonStyle(.plain)
            }

            if loadedModels.isEmpty {
                Text(app.t("No models currently held in VRAM.",
                           "現在VRAMに保持されているモデルはありません。"))
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            } else {
                ForEach(loadedModels, id: \.name) { running in
                    let isActive = app.activeOllamaModel == running.name
                    HStack(spacing: 8) {
                        Circle().fill(isActive ? Color.green : Color.orange)
                            .frame(width: 6, height: 6)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(running.name)
                                .font(.system(size: 10, design: .monospaced)).lineLimit(1)
                            Text(String(format: "%.2f GB", running.sizeGB))
                                .font(.system(size: 9)).foregroundStyle(.tertiary)
                        }
                        Spacer()
                        Button {
                            Task { await eject(running.name) }
                        } label: {
                            if ejectingModel == running.name {
                                ProgressView().controlSize(.mini)
                            } else {
                                Image(systemName: "eject.fill").font(.system(size: 10))
                            }
                        }
                        .buttonStyle(.plain)
                        .disabled(ejectingModel != nil || isActive)
                        .help(isActive
                              ? app.t("Cannot unload the active model", "アクティブなモデルはアンロードできません")
                              : app.t("Unload from VRAM", "VRAMからアンロード"))
                    }
                    .padding(.horizontal, 6).padding(.vertical, 4)
                    .background(RoundedRectangle(cornerRadius: 5).fill(Color.orange.opacity(0.07)))
                }
            }
        }
        .padding(12)
        .frame(width: 280)
    }

    // MARK: - JGEN options (4-layer)

    private var jgenOptionsPopover: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Text(app.t("JGEN Options", "JGENオプション"))
                        .font(.system(size: 13, weight: .bold))
                    Spacer()
                    Text(council.templateId == "custom"
                         ? app.t("Custom", "カスタム")
                         : council.templateId)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.tertiary)
                }

                layerBlock(
                    "Layer 0 — " + app.t("Memory", "記憶"),
                    color: Color(red: 0.5, green: 0.85, blue: 0.6)
                ) {
                    Toggle(app.t("Vera-α verified facts", "Vera-α 確定事実"), isOn: Binding(
                        get: { council.config.useVeraMemory },
                        set: { council.config.useVeraMemory = $0; council.markCustom() }
                    )).toggleStyle(.checkbox)

                    Toggle(app.t("Eternal (vector) memory", "永遠記憶(ベクトル)"), isOn: Binding(
                        get: { council.config.useEternalMemory },
                        set: { council.config.useEternalMemory = $0; council.markCustom() }
                    )).toggleStyle(.checkbox)

                    Toggle(app.t("Visual memory (screen recall)", "視覚記憶(画面リコール)"), isOn: Binding(
                        get: { council.useVisualMemory },
                        set: { council.useVisualMemory = $0 }
                    )).toggleStyle(.checkbox)

                    Toggle(app.t("Vera as harness (Vera drives the turn)", "Veraをハーネスにする(Veraが主導)"), isOn: Binding(
                        get: { council.useVeraHarnessForChat },
                        set: { council.useVeraHarnessForChat = $0 }
                    )).toggleStyle(.checkbox)

                    if council.useVeraHarnessForChat {
                        Picker(app.t("Cognition mode", "認知モード"), selection: Binding(
                            get: { council.cognitionMode },
                            set: { council.cognitionMode = $0 }
                        )) {
                            ForEach(CouncilSettingsStore.CognitionMode.allCases) { mode in
                                Text(app.t(mode.title, mode.titleJA)).tag(mode)
                            }
                        }
                        .pickerStyle(.segmented)
                        .font(.system(size: 10))

                        if council.cognitionMode != .normal {
                            Text(app.t(
                                "⚠️ Experimental cognition is enabled. Vera may create persistent knowledge-gap nodes and propose new facts/skills for review — never applied without approval.",
                                "⚠️ 実験的な認知モードが有効です。Veraは永続的な知識ギャップノードを作成し、新しい事実/スキルをレビュー用に提案することがあります — 承認なしには適用されません。"
                            ))
                            .font(.system(size: 9))
                            .foregroundStyle(.orange)
                            .fixedSize(horizontal: false, vertical: true)
                        }

                        // Milestone R4: mutating tool calls (write_file,
                        // run_command, vera_remember, vera_code_ingest, ...)
                        // the Vera-harness chat proposed but couldn't run
                        // without a human -- review queue, same button
                        // regardless of cognition mode since normal-mode
                        // chat can propose these too.
                        Button {
                            showPendingToolCalls = true
                        } label: {
                            Label(app.t("Pending tool-call approvals…", "承認待ちのツール呼び出し…"),
                                  systemImage: "checkmark.shield")
                                .font(.system(size: 10))
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(Color.orange)

                        // A Council/L1-L4 run can genuinely take 10+ minutes;
                        // this is the "why" behind that wait, not just a
                        // spinner -- see ReasoningTimelineView.
                        Button {
                            showReasoningTimeline = true
                        } label: {
                            Label(app.t("Reasoning timeline…", "推論タイムライン…"),
                                  systemImage: "timeline.selection")
                                .font(.system(size: 10))
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(Color.indigo)
                    }

                    Text(app.t("Zone memory layers", "ゾーン記憶レイヤ"))
                        .font(.system(size: 10)).foregroundStyle(.secondary)
                    HStack(spacing: 6) {
                        ForEach(JCrossLayer.allCases) { layer in
                            let on = council.config.zoneLayers.contains(layer)
                            Button(layer.rawValue.uppercased()) {
                                if on { council.config.zoneLayers.remove(layer) }
                                else { council.config.zoneLayers.insert(layer) }
                                council.markCustom()
                            }
                            .buttonStyle(.plain)
                            .font(.system(size: 9, weight: .semibold, design: .monospaced))
                            .padding(.horizontal, 6).padding(.vertical, 3)
                            .background(
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(on ? Color(red: 0.5, green: 0.85, blue: 0.6).opacity(0.25)
                                             : Color.white.opacity(0.06))
                            )
                        }
                    }
                }

                layerBlock(
                    "Layer 1 — " + app.t("Council core (same-arch JGEN)", "合議核(同型JGEN)"),
                    color: Color(red: 1.0, green: 0.72, blue: 0.35)
                ) {
                    Stepper(app.t("Roles: \(council.config.roleCount)", "役割数: \(council.config.roleCount)"),
                            value: Binding(
                                get: { council.config.roleCount },
                                set: { council.config.roleCount = $0; council.markCustom() }
                            ), in: 2...5)
                        .font(.system(size: 10))
                    Stepper(app.t("Rounds cap: \(council.config.roundsCap)", "最大ラウンド: \(council.config.roundsCap)"),
                            value: Binding(
                                get: { council.config.roundsCap },
                                set: { council.config.roundsCap = $0; council.markCustom() }
                            ), in: 1...8)
                        .font(.system(size: 10))
                    Picker(app.t("Injection", "注入方針"), selection: Binding(
                        get: { council.config.injectionPolicy },
                        set: { council.config.injectionPolicy = $0; council.markCustom() }
                    )) {
                        ForEach(CouncilOrchestrator.InjectionPolicy.allCases) { p in
                            Text(p.displayName).tag(p)
                        }
                    }
                    .font(.system(size: 10))
                }

                layerBlock(
                    "Layer 2 — " + app.t("Execution agent (tools)", "実行エージェント(ツール)"),
                    color: Color(red: 0.5, green: 0.7, blue: 1.0)
                ) {
                    Toggle(isOn: Binding(
                        get: { council.executionUseJGEN },
                        set: { council.executionUseJGEN = $0 }
                    )) {
                        HStack(spacing: 4) {
                            Text("BETA")
                                .font(.system(size: 8, weight: .bold))
                                .padding(.horizontal, 4).padding(.vertical, 1)
                                .background(Color.orange.opacity(0.25))
                                .foregroundStyle(.orange)
                                .clipShape(Capsule())
                            Text(app.t("Run Layer 2 on JGEN too (same model as council)",
                                       "Layer 2もJGENで実行(合議と同一モデル)"))
                                .font(.system(size: 10))
                        }
                    }
                    .toggleStyle(.checkbox)

                    if council.executionUseJGEN {
                        Text(app.t(
                            "Uses JGenSpeakAgent on the same JGEN as the council: eternal-memory recall + soft-token steer, then a short generate. Skips AgentLoop (no MEM/CTRL tag collapse) and Layer-3 escalation. Vision can still use VisualHiddenStateBridge injection as an experiment.",
                            "合議と同一JGEN上のJGenSpeakAgentを使います: 永遠記憶の想起＋ソフトトークン誘導のあと短い生成。AgentLoopを通さないためMEM/CTRLタグ崩壊を避け、L3エスカレーションもしません。画面は実験的にVisualHiddenStateBridge注入も使えます。"))
                            .font(.system(size: 9)).foregroundStyle(.orange)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    ollamaModelPicker(
                        label: app.t("Execution model", "実行モデル"),
                        selection: Binding(
                            get: { council.executionModel },
                            set: { council.executionModel = $0; council.markCustom() }
                        )
                    )
                    .disabled(council.executionUseJGEN)
                    .opacity(council.executionUseJGEN ? 0.4 : 1.0)
                    Text(app.t("Receives one short structured handoff (conclusion / evidence / next action / confidence) and runs tools on it.",
                               "短い構造化ハンドオフ(結論・根拠・次アクション・confidence)を受け取り、ツールを実行します。"))
                        .font(.system(size: 9)).foregroundStyle(.tertiary)
                }

                layerBlock(
                    "Layer 3 — " + app.t("Escalation", "エスカレーション"),
                    color: Color(red: 1.0, green: 0.55, blue: 0.75)
                ) {
                    Toggle(app.t("Escalate on low confidence", "低確信度でエスカレート"), isOn: Binding(
                        get: { council.config.escalateOnLowConfidence },
                        set: { council.config.escalateOnLowConfidence = $0; council.markCustom() }
                    )).toggleStyle(.checkbox)

                    if council.config.escalateOnLowConfidence {
                        HStack {
                            Text(app.t("Threshold", "閾値")).font(.system(size: 10))
                            Slider(value: Binding(
                                get: { Double(council.config.escalationConfidenceThreshold) },
                                set: { council.config.escalationConfidenceThreshold = Float($0); council.markCustom() }
                            ), in: 0.3...0.95)
                            Text(String(format: "%.2f", council.config.escalationConfidenceThreshold))
                                .font(.system(size: 9, design: .monospaced)).foregroundStyle(.secondary)
                        }
                        ollamaModelPicker(
                            label: app.t("Escalation model", "エスカレ先モデル"),
                            selection: Binding(
                                get: { council.config.escalationModel },
                                set: { council.config.escalationModel = $0; council.markCustom() }
                            )
                        )
                    }
                }

                Divider().opacity(0.2)

                Toggle(app.t("Use the council for normal chat turns",
                             "通常のチャットでも合議を使う"),
                       isOn: $council.useCouncilForChat)
                    .toggleStyle(.checkbox)
                    .font(.system(size: 10))
                Text(app.t("Otherwise the council only runs via /council. Requires a loaded JGEN model.",
                           "オフの場合、合議は /council でのみ実行されます。JGENモデルのロードが必要です。"))
                    .font(.system(size: 9)).foregroundStyle(.tertiary)

                Divider().opacity(0.2)

                // Whole-architecture templates: picking one inspects this
                // Mac and the installed models, then shows a plan to approve
                // rather than silently rewriting the settings.
                Text(app.t("Architecture template", "アーキテクチャ構成"))
                    .font(.system(size: 10, weight: .semibold)).foregroundStyle(.secondary)
                Menu {
                    ForEach(ArchitectureTemplate.builtins) { template in
                        Button(AppLanguage.shared.isJapanese ? template.nameJA : template.name) {
                            showJGenOptions = false
                            app.proposeSetup(template: template, allowWeb: includeWebRecommendations)
                        }
                    }
                } label: {
                    Label(app.t("Choose a template…", "構成を選ぶ…"), systemImage: "square.3.layers.3d")
                        .font(.system(size: 10))
                }
                .menuStyle(.borderlessButton)

                Toggle(app.t("Include web recommendations", "Webの推奨も参照する"),
                       isOn: $includeWebRecommendations)
                    .toggleStyle(.checkbox)
                    .font(.system(size: 9))
                Text(app.t("Checks this Mac's RAM and free disk plus your installed models first; the web lookup only fills gaps and is skipped if it can't complete.",
                           "まずこのMacのRAM・空き容量とインストール済みモデルを確認します。Web検索は不足分の補足のみで、失敗しても処理は続行します。"))
                    .font(.system(size: 9)).foregroundStyle(.tertiary)
            }
            .padding(14)
        }
        .frame(width: 330, height: 520)
    }

    @ViewBuilder
    private func layerBlock<Content: View>(_ title: String, color: Color,
                                           @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 5) {
                RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 3, height: 11)
                Text(title).font(.system(size: 10, weight: .semibold)).foregroundStyle(.secondary)
            }
            content()
        }
    }

    /// Layers 2 and 3 both call Ollama, so both pick from the same live list.
    @ViewBuilder
    private func ollamaModelPicker(label: String, selection: Binding<String>) -> some View {
        if app.ollamaModels.isEmpty {
            TextField(label, text: selection)
                .textFieldStyle(.roundedBorder)
                .font(.system(size: 10, design: .monospaced))
        } else {
            Picker(label, selection: selection) {
                Text(app.t("(none)", "(なし)")).tag("")
                ForEach(app.ollamaModels, id: \.self) { m in Text(m).tag(m) }
            }
            .font(.system(size: 10))
        }
    }

    @MainActor
    private func eject(_ model: String) async {
        ejectingModel = model
        let ok = await OllamaClient.shared.unloadModel(model)
        ejectingModel = nil
        if ok {
            app.addSystemMessage("⏏️ Unloaded \(model) from VRAM")
            if app.activeOllamaModel == model { app.modelStatus = .none }
        } else {
            app.addSystemMessage("⚠️ Failed to unload \(model)")
        }
        loadedModels = await OllamaClient.shared.loadedModels()
    }
}
