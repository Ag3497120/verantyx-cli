import Foundation

/// What a template's layer resolved to on this machine.
struct LayerAssignment: Identifiable, Sendable {
    enum Source: Sendable {
        case local                 // already installed
        case suggestedDownload     // not installed; user must fetch it
        case unavailable           // nothing suitable, and nothing to suggest
        case notApplicable         // layer disabled, or needs no model (Layer 0)
    }
    enum Status: Sendable {
        case ok
        case warning(String)
        case blocked(String)

        var isBlocked: Bool { if case .blocked = self { return true }; return false }
        var message: String? {
            switch self {
            case .ok: return nil
            case .warning(let m), .blocked(let m): return m
            }
        }
    }

    let role: LayerSpec.Role
    var model: String
    var backend: ModelBackend
    var source: Source
    var sizeGB: Double?
    var status: Status
    /// Shown verbatim when the user needs to fetch something themselves.
    var installHint: String?

    var id: String { role.rawValue }
}

/// A complete, reviewable setup proposal awaiting the user's approval.
struct SetupProposal: Identifiable, Sendable {
    let id = UUID()
    let template: ArchitectureTemplate
    let machine: MachineProfile
    var assignments: [LayerAssignment]
    var warnings: [String]
    /// Advisory only -- free text from a web search is never turned into a
    /// chosen model.
    var webNotes: [String]
    var webSearchAttempted: Bool
    var webSearchFailed: Bool

    /// False when any enabled layer is blocked; the approve button is
    /// disabled in that case.
    var isApplicable: Bool {
        !assignments.contains { $0.status.isBlocked }
    }

    func assignment(_ role: LayerSpec.Role) -> LayerAssignment? {
        assignments.first { $0.role == role }
    }
}

/// Turns a template into a concrete, machine-checked plan.
///
/// Order matters: the machine profile and the local inventory are instant and
/// work offline, so a usable plan always exists before the network is touched.
/// A web search only ever *enriches* it, and only for layers that had no local
/// candidate — if it fails or times out the proposal is still returned.
actor TemplateSetupPlanner {

    static let shared = TemplateSetupPlanner()
    private init() {}

    /// JGEN conversion writes a file roughly the size of the source weights,
    /// plus working space -- the same 1.15x margin jgen_forge's own
    /// pre-flight disk check uses.
    private static let diskMargin = 1.15
    private static let webTimeoutSeconds: UInt64 = 12

    /// `hasAnthropicKey` is passed in rather than read from `AppState` here:
    /// this is a plain actor, and reaching for MainActor-isolated app state
    /// from inside it is exactly the kind of cross-isolation access Swift
    /// concurrency rejects. The caller already runs on the MainActor.
    func plan(template: ArchitectureTemplate,
              machine: MachineProfile,
              inventory: [InventoryEntry],
              hasAnthropicKey: Bool,
              allowWeb: Bool) async -> SetupProposal {

        var assignments: [LayerAssignment] = []
        var warnings: [String] = []

        if machine.totalRAMGB < template.requirements.minRAMGB {
            warnings.append(String(format:
                "This template expects ~%.0f GB RAM; this Mac has %.0f GB. Expect swapping.",
                template.requirements.minRAMGB, machine.totalRAMGB))
        }
        if machine.freeDiskGB < template.requirements.minFreeDiskGB {
            warnings.append(String(format:
                "Only %.1f GB free — this template wants at least %.0f GB.",
                machine.freeDiskGB, template.requirements.minFreeDiskGB))
        }
        if template.requirements.needsBitNet && !inventory.contains(where: { $0.backend == .bitnet }) {
            warnings.append("No BitNet model is installed; the execution layer can't run as specified.")
        }

        for layer in template.layers {
            assignments.append(assign(layer: layer, machine: machine, inventory: inventory,
                                      hasAnthropicKey: hasAnthropicKey))
        }

        // ── Total concurrent footprint, not just per-layer ────────────────
        // Each layer above was checked against usableModelRAMGB in
        // isolation, which never catches "each layer fits alone, but they
        // don't all fit at once" -- confirmed via a real proposal (JGEN
        // 24.1GB + two ~21GB Ollama layers = ~66GB on a 64GB Mac, every
        // individual layer passing its own 38.4GB-budget check). JGEN
        // (JCrossChatManager) stays resident in-process once loaded, so its
        // size always counts; Ollama layers sharing the exact same model
        // name only cost once (Ollama itself won't double-load one model),
        // but different Ollama models each need their own share since
        // Ollama's own eviction isn't coordinated by this app at all.
        var footprintGB = 0.0
        var seenOllamaModels = Set<String>()
        var seenJGenModels = Set<String>()
        for assignment in assignments {
            guard let size = assignment.sizeGB else { continue }
            if assignment.backend == .ollama {
                guard !seenOllamaModels.contains(assignment.model) else { continue }
                seenOllamaModels.insert(assignment.model)
            }
            // Same JCrossChatManager handle serves council + jgen-native L2.
            if assignment.backend == .jgen {
                guard !seenJGenModels.contains(assignment.model) else { continue }
                seenJGenModels.insert(assignment.model)
            }
            footprintGB += size
        }
        if footprintGB > machine.usableModelRAMGB {
            warnings.append(String(format:
                "This proposal's layers total ~%.1f GB if all loaded at once — more than the ~%.1f GB "
                + "of this Mac's %.0f GB RAM comfortably usable for weights. JGEN stays resident once "
                + "loaded and doesn't unload for Ollama layers (or vice versa); expect swapping or OOM "
                + "if multiple heavy layers are actually exercised in the same session.",
                footprintGB, machine.usableModelRAMGB, machine.totalRAMGB))
        }

        // ── Optional web enrichment (never blocking) ──────────────────────
        var webNotes: [String] = []
        var webFailed = false
        let needsHelp = assignments.contains {
            if case .local = $0.source { return false }
            if case .notApplicable = $0.source { return false }
            return true
        }

        if allowWeb && needsHelp {
            let query = webQuery(for: template, machine: machine)
            let searched = await withTimeout(seconds: Self.webTimeoutSeconds) {
                await WebSearchEngine.shared.search(query: query)
            }
            if let result = searched, !result.isFailure {
                webNotes = Self.advisoryLines(from: result.contextSnippet)
                if webNotes.isEmpty {
                    webNotes = ["Search returned no clearly usable model recommendations."]
                }
            } else {
                webFailed = true
            }
        }

        return SetupProposal(
            template: template,
            machine: machine,
            assignments: assignments,
            warnings: warnings,
            webNotes: webNotes,
            webSearchAttempted: allowWeb && needsHelp,
            webSearchFailed: webFailed
        )
    }

    // MARK: - Per-layer assignment

    private func assign(layer: LayerSpec,
                        machine: MachineProfile,
                        inventory: [InventoryEntry],
                        hasAnthropicKey: Bool) -> LayerAssignment {

        guard layer.enabled, layer.backend != .none else {
            return LayerAssignment(role: layer.role, model: "—", backend: .none,
                                   source: .notApplicable, sizeGB: nil, status: .ok)
        }

        // Layer 0 is pure configuration -- memory sources are switches on the
        // council config, not a model.
        if layer.role == .memory {
            return LayerAssignment(role: layer.role, model: "—", backend: .none,
                                   source: .notApplicable, sizeGB: nil, status: .ok)
        }

        // Anthropic needs a key, not a local model.
        if layer.backend == .anthropic {
            let hasKey = hasAnthropicKey
            return LayerAssignment(
                role: layer.role, model: "Anthropic API", backend: .anthropic,
                source: hasKey ? .local : .unavailable, sizeGB: nil,
                status: hasKey ? .ok : .blocked("No Anthropic API key configured (Settings → Model)."),
                installHint: hasKey ? nil : "Add an API key in Settings → Model."
            )
        }

        let candidates = inventory.filter { $0.backend == layer.backend && $0.isLoadable }

        // Prefer an explicit hint, then fall back to the full local pool.
        //
        // Sort direction depends on the role, not just "biggest that fits":
        // escalation genuinely wants the strongest available model, but
        // execution should stay light/fast -- when modelHint doesn't match
        // anything installed (e.g. no "8b" model present), falling back to
        // "biggest that fits" for BOTH roles was a real bug: with nothing
        // mid-sized in the inventory, execution and escalation converged on
        // the exact same single largest model (confirmed against a user
        // report -- their "Balanced (16GB)" proposal on a 64GB Mac put the
        // same ~21GB model in both Layer 2 and Layer 3 because there was
        // nothing smaller than that installed). Preferring the SMALLEST
        // model that still fits for execution means it degrades to a lean
        // pick instead of quietly matching escalation's size.
        let preferSmallest = (layer.role == .execution)
        let hinted = layer.modelHint.isEmpty
            ? []
            : candidates.filter { $0.name.lowercased().contains(layer.modelHint.lowercased()) }
        let pool = hinted.isEmpty ? candidates : hinted
        let sortedPool = preferSmallest
            ? pool.sorted { ($0.sizeGB ?? 0) < ($1.sizeGB ?? 0) }
            : pool.sorted { ($0.sizeGB ?? 0) > ($1.sizeGB ?? 0) }
        let fitting = sortedPool.filter { ($0.sizeGB ?? 0) <= machine.usableModelRAMGB }

        if let pick = fitting.first ?? sortedPool.first {
            let tooBig = (pick.sizeGB ?? 0) > machine.usableModelRAMGB
            let ramWarning = String(format:
                "%@ is ~%.1f GB; only ~%.1f GB of this Mac's RAM is comfortably usable for weights.",
                pick.name, pick.sizeGB ?? 0, machine.usableModelRAMGB)
            return LayerAssignment(
                role: layer.role, model: pick.name, backend: layer.backend,
                source: .local, sizeGB: pick.sizeGB,
                status: tooBig ? .warning(ramWarning) : .ok
            )
        }

        // Nothing local. Suggest, but never download.
        return unavailableAssignment(layer: layer, machine: machine)
    }

    private func unavailableAssignment(layer: LayerSpec, machine: MachineProfile) -> LayerAssignment {
        switch layer.backend {
        case .ollama:
            let suggestion = layer.modelHint.isEmpty ? "qwen2.5:7b" : "qwen2.5:\(layer.modelHint)"
            let sizeGB = ModelInventory.estimatedSizeGB(fromName: suggestion) ?? 5
            let needed = sizeGB * Self.diskMargin
            let fits = machine.freeDiskGB >= needed
            return LayerAssignment(
                role: layer.role, model: suggestion, backend: .ollama,
                source: .suggestedDownload, sizeGB: sizeGB,
                status: fits
                    ? .warning("Not installed yet — pull it before running this layer.")
                    : .blocked(String(format: "Needs ~%.1f GB free, only %.1f GB available.",
                                      needed, machine.freeDiskGB)),
                installHint: "ollama pull \(suggestion)"
            )
        case .jgen:
            return LayerAssignment(
                role: layer.role, model: "—", backend: .jgen,
                source: .unavailable, sizeGB: nil,
                status: .blocked("No runnable .jgen model converted yet."),
                installHint: "Settings → JGEN → convert a supported model."
            )
        case .bitnet:
            return LayerAssignment(
                role: layer.role, model: "—", backend: .bitnet,
                source: .unavailable, sizeGB: nil,
                status: .blocked("No BitNet model installed."),
                installHint: "Settings → BitNet → run setup."
            )
        case .mlx:
            return LayerAssignment(
                role: layer.role, model: "—", backend: .mlx,
                source: .unavailable, sizeGB: nil,
                status: .blocked("No MLX model downloaded."),
                installHint: "Settings → Model → Download MLX model."
            )
        case .anthropic, .none:
            return LayerAssignment(role: layer.role, model: "—", backend: layer.backend,
                                   source: .unavailable, sizeGB: nil,
                                   status: .blocked("Unavailable."))
        }
    }

    // MARK: - Web helpers

    private func webQuery(for template: ArchitectureTemplate, machine: MachineProfile) -> String {
        let ram = Int(machine.totalRAMGB.rounded())
        let chip = machine.isAppleSilicon ? "Apple Silicon" : "Intel Mac"
        return "best local LLM \(ram)GB \(chip) ollama tool use agent 2026 recommended"
    }

    /// Deliberately conservative: pull out short lines that mention a known
    /// model family and present them as *notes*. Free web text is never
    /// promoted into an actual model assignment -- that would let an
    /// arbitrary page choose what the user runs.
    static func advisoryLines(from snippet: String) -> [String] {
        let families = ["qwen", "llama", "mistral", "gemma", "phi", "deepseek",
                        "codestral", "granite", "smollm", "bitnet", "olmo"]
        var seen = Set<String>()
        var out: [String] = []
        for raw in snippet.components(separatedBy: .newlines) {
            let line = raw.trimmingCharacters(in: .whitespaces)
            guard line.count >= 20, line.count <= 200 else { continue }
            let lower = line.lowercased()
            guard families.contains(where: { lower.contains($0) }) else { continue }
            guard seen.insert(lower).inserted else { continue }
            out.append(line)
            if out.count == 5 { break }
        }
        return out
    }

    /// Races an async operation against a deadline. Returns nil on timeout so
    /// the caller can carry on with local-only results.
    private func withTimeout<T: Sendable>(seconds: UInt64,
                                          _ operation: @escaping @Sendable () async -> T) async -> T? {
        await withTaskGroup(of: T?.self) { group in
            group.addTask { await operation() }
            group.addTask {
                try? await Task.sleep(nanoseconds: seconds * 1_000_000_000)
                return nil
            }
            let first = await group.next() ?? nil
            group.cancelAll()
            return first
        }
    }
}
