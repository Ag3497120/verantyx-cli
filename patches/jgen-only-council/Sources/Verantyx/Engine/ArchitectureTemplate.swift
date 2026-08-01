import Foundation

/// Which backend a layer runs on.
enum ModelBackend: String, Codable, CaseIterable, Identifiable {
    case jgen, ollama, mlx, bitnet, anthropic, none
    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .jgen:      return "JGEN"
        case .ollama:    return "Ollama"
        case .mlx:       return "MLX"
        case .bitnet:    return "BitNet"
        case .anthropic: return "Anthropic API"
        case .none:      return "—"
        }
    }
}

/// One layer of the 4-layer architecture, with what it needs to run.
struct LayerSpec: Codable, Identifiable {
    enum Role: String, Codable, CaseIterable, Identifiable {
        case memory, councilCore, execution, escalation
        var id: String { rawValue }

        var title: String {
            switch self {
            case .memory:      return "Layer 0 — Memory"
            case .councilCore: return "Layer 1 — Council core"
            case .execution:   return "Layer 2 — Execution agent"
            case .escalation:  return "Layer 3 — Escalation"
            }
        }
        var titleJA: String {
            switch self {
            case .memory:      return "Layer 0 — 記憶"
            case .councilCore: return "Layer 1 — 合議核"
            case .execution:   return "Layer 2 — 実行エージェント"
            case .escalation:  return "Layer 3 — エスカレーション"
            }
        }
    }

    var role: Role
    var enabled: Bool
    var backend: ModelBackend
    /// Substring hint used to pick a model from the local inventory
    /// ("" = take whatever fits the machine).
    var modelHint: String = ""
    var minRAMGB: Double = 0
    var approxDiskGB: Double = 0
    var note: String = ""
    var noteJA: String = ""

    var id: String { role.rawValue }
}

struct ExecutionToolPolicy: Codable {
    var maxTurns: Int = 12
    var allowWeb: Bool = true
    var allowShell: Bool = true
    var allowDesktop: Bool = false
}

struct ResourceRequirement: Codable {
    var minRAMGB: Double = 8
    var minFreeDiskGB: Double = 2
    var needsNetwork: Bool = false
    var needsOllama: Bool = true
    var needsJGEN: Bool = true
    var needsBitNet: Bool = false
}

/// A complete 4-layer setup the user can pick and then approve.
///
/// This is the richer superset of `CouncilPreset`: that type only ever
/// described Layer 0 memory switches and Layer 1 knobs, with no way to say
/// which model each layer should run on or what hardware it needs -- which
/// is exactly what the setup planner has to reason about. `CouncilPreset`
/// remains as the shape `VectorLabView` consumes; see `asCouncilPreset`.
struct ArchitectureTemplate: Identifiable, Codable {
    let id: String
    let name: String
    let nameJA: String
    let description: String
    let descriptionJA: String
    var councilConfig: CouncilOrchestrator.Config
    var layers: [LayerSpec]
    var executionToolPolicy: ExecutionToolPolicy
    var requirements: ResourceRequirement
    var tags: [String] = []

    var asCouncilPreset: CouncilPreset {
        CouncilPreset(id: id, name: name, nameJA: nameJA,
                      description: description, descriptionJA: descriptionJA,
                      config: councilConfig)
    }

    func layer(_ role: LayerSpec.Role) -> LayerSpec? {
        layers.first { $0.role == role }
    }

    // MARK: - Builtins

    static let builtins: [ArchitectureTemplate] = [

        ArchitectureTemplate(
            id: "jgen-vector-bus",
            name: "JGEN vector bus (no escalation)",
            nameJA: "JGENベクトルバス（エスカレなし）",
            description: "Same JGEN for council + execution. Eternal / zone memory as a hidden-state bus. Soft-token steer on L2. No Ollama, no AgentLoop, no Layer-3 escalation — the path for UI/vision vectors carved into JGEN space.",
            descriptionJA: "合議も実行も同一JGEN。永遠記憶・ゾーン記憶を隠れ状態バスとして使い、L2はソフトトークン誘導。Ollama・AgentLoop・L3エスカレーションなし — 画面/UIベクトルをJGEN空間に刻むための本線。",
            councilConfig: .init(roleCount: 5, roundsCap: 4, injectionPolicy: .none,
                                 useVeraMemory: true, zoneLayers: [.l1, .l1_5, .l2, .l3],
                                 useEternalMemory: true, escalateOnLowConfidence: false,
                                 escalationConfidenceThreshold: 0.6, escalationModel: "",
                                 executionMode: .external),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none,
                          note: "Vera + L1-L3 zones + eternal JGEN vectors",
                          noteJA: "Vera + L1-L3ゾーン + JGEN永遠ベクトル"),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 6,
                          note: "Same-arch JGEN roles", noteJA: "同型JGEN役割"),
                LayerSpec(role: .execution, enabled: true, backend: .jgen, minRAMGB: 6,
                          note: "JGenSpeakAgent (no AgentLoop)", noteJA: "JGenSpeakAgent（AgentLoopなし）"),
                LayerSpec(role: .escalation, enabled: false, backend: .none,
                          note: "Disabled", noteJA: "無効"),
            ],
            executionToolPolicy: .init(maxTurns: 4, allowWeb: false, allowShell: false, allowDesktop: false),
            requirements: .init(minRAMGB: 8, minFreeDiskGB: 1, needsNetwork: false, needsOllama: false, needsJGEN: true),
            tags: ["recommended", "jgen-only"]
        ),

        ArchitectureTemplate(
            id: "strongest",
            name: "Strongest (4-layer)",
            nameJA: "最強構成(4層)",
            description: "Full 5-role council on one JGEN model, every memory source, deep rounds with perturb-testing, a real tool-using execution agent, and escalation only when confidence is low.",
            descriptionJA: "1つのJGENモデルで5役割フル合議、全記憶ソース、摂動テスト付きの深いラウンド、ツールを使う実行エージェント、確信度が低いときだけエスカレーション。",
            councilConfig: .init(roleCount: 5, roundsCap: 5, injectionPolicy: .deepRounds,
                                 useVeraMemory: true, zoneLayers: [.l1, .l1_5, .l2, .l3],
                                 useEternalMemory: true, escalateOnLowConfidence: true,
                                 escalationConfidenceThreshold: 0.6),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none,
                          note: "Vera facts + L1-L3 zones + eternal vectors",
                          noteJA: "Vera確定事実 + L1-L3ゾーン + 永遠ベクトル"),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 24,
                          note: "Same-arch JGEN, 5 roles", noteJA: "同型JGEN・5役割"),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, minRAMGB: 16,
                          note: "Strongest local tool-user", noteJA: "ローカル最強のツール実行役"),
                LayerSpec(role: .escalation, enabled: true, backend: .ollama, minRAMGB: 24,
                          note: "Largest local model", noteJA: "ローカル最大のモデル"),
            ],
            executionToolPolicy: .init(maxTurns: 16),
            requirements: .init(minRAMGB: 32, minFreeDiskGB: 4),
            tags: ["recommended"]
        ),

        ArchitectureTemplate(
            id: "lean-local-8gb",
            name: "Lean (8GB machines)",
            nameJA: "軽量構成(8GB向け)",
            description: "2 council roles, single round, no eternal memory, a small execution model, no escalation. Fits machines where a large model would swap.",
            descriptionJA: "2役割・1ラウンド、永遠記憶なし、小さい実行モデル、エスカレーションなし。大きいモデルではスワップするマシン向け。",
            councilConfig: .init(roleCount: 2, roundsCap: 2, injectionPolicy: .none,
                                 useVeraMemory: true, zoneLayers: [.l2],
                                 useEternalMemory: false, escalateOnLowConfidence: false),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 6),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, modelHint: "3b", minRAMGB: 4),
                LayerSpec(role: .escalation, enabled: false, backend: .none),
            ],
            executionToolPolicy: .init(maxTurns: 8, allowShell: false),
            requirements: .init(minRAMGB: 8, minFreeDiskGB: 1)
        ),

        ArchitectureTemplate(
            id: "balanced-16gb",
            name: "Balanced (16GB)",
            nameJA: "バランス構成(16GB)",
            description: "3 roles with L1/L2 memory, a 7-8B execution agent, escalation to a larger local model.",
            descriptionJA: "3役割・L1/L2記憶、7〜8Bの実行エージェント、より大きいローカルモデルへエスカレーション。",
            councilConfig: .init(roleCount: 3, roundsCap: 4, injectionPolicy: .planSteal,
                                 useVeraMemory: true, zoneLayers: [.l1, .l2],
                                 useEternalMemory: true, escalateOnLowConfidence: true,
                                 escalationConfidenceThreshold: 0.6),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 10),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, modelHint: "8b", minRAMGB: 8),
                LayerSpec(role: .escalation, enabled: true, backend: .ollama, minRAMGB: 12),
            ],
            executionToolPolicy: .init(maxTurns: 12),
            requirements: .init(minRAMGB: 16, minFreeDiskGB: 2)
        ),

        ArchitectureTemplate(
            id: "offline-only",
            name: "Offline only",
            nameJA: "完全オフライン",
            description: "No network at any layer: web tools off for the execution agent, no cloud escalation. Everything runs from local weights.",
            descriptionJA: "どの層もネットワークを使いません。実行エージェントのWebツールはオフ、クラウドエスカレーションもなし。すべてローカルの重みで動作します。",
            councilConfig: .init(roleCount: 3, roundsCap: 4, injectionPolicy: .none,
                                 useVeraMemory: true, zoneLayers: [.l1, .l2, .l3],
                                 useEternalMemory: true, escalateOnLowConfidence: false),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 10),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, minRAMGB: 8),
                LayerSpec(role: .escalation, enabled: false, backend: .none),
            ],
            executionToolPolicy: .init(maxTurns: 12, allowWeb: false),
            requirements: .init(minRAMGB: 16, minFreeDiskGB: 2, needsNetwork: false)
        ),

        ArchitectureTemplate(
            id: "escalate-to-cloud",
            name: "Escalate to cloud",
            nameJA: "クラウドへエスカレート",
            description: "Local council and local execution, but hard cases go to the Anthropic API. Needs a configured API key and network.",
            descriptionJA: "合議と実行はローカル、難問だけAnthropic APIへ。APIキーの設定とネットワークが必要です。",
            councilConfig: .init(roleCount: 3, roundsCap: 4, injectionPolicy: .planSteal,
                                 useVeraMemory: true, zoneLayers: [.l1, .l2],
                                 useEternalMemory: true, escalateOnLowConfidence: true,
                                 escalationConfidenceThreshold: 0.7),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 10),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, minRAMGB: 8),
                LayerSpec(role: .escalation, enabled: true, backend: .anthropic,
                          note: "Requires an API key", noteJA: "APIキーが必要"),
            ],
            executionToolPolicy: .init(maxTurns: 12),
            requirements: .init(minRAMGB: 16, minFreeDiskGB: 2, needsNetwork: true)
        ),

        ArchitectureTemplate(
            id: "bitnet-frugal",
            name: "BitNet frugal",
            nameJA: "BitNet省メモリ",
            description: "Execution runs on a 1-bit BitNet model to keep memory and power low. Council still needs JGEN.",
            descriptionJA: "実行層を1-bitのBitNetモデルで動かし、メモリと消費電力を抑えます。合議にはJGENが必要です。",
            councilConfig: .init(roleCount: 2, roundsCap: 3, injectionPolicy: .none,
                                 useVeraMemory: true, zoneLayers: [.l2],
                                 useEternalMemory: false, escalateOnLowConfidence: false),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 6),
                LayerSpec(role: .execution, enabled: true, backend: .bitnet, minRAMGB: 3),
                LayerSpec(role: .escalation, enabled: false, backend: .none),
            ],
            executionToolPolicy: .init(maxTurns: 8, allowShell: false),
            requirements: .init(minRAMGB: 8, minFreeDiskGB: 1, needsBitNet: true)
        ),

        ArchitectureTemplate(
            id: "tool-heavy-exec",
            name: "Tool-heavy execution",
            nameJA: "ツール実行重視",
            description: "Minimal deliberation, maximal doing: a 2-role council just to frame the task, then a long-running execution agent with every tool enabled.",
            descriptionJA: "審議は最小限、実行を最大化。2役割の合議でタスクを枠付けし、あとは全ツール有効の実行エージェントに長く回させます。",
            councilConfig: .init(roleCount: 2, roundsCap: 1, injectionPolicy: .none,
                                 useVeraMemory: true, zoneLayers: [.l2],
                                 useEternalMemory: false, escalateOnLowConfidence: true,
                                 escalationConfidenceThreshold: 0.5),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 6),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, minRAMGB: 12),
                LayerSpec(role: .escalation, enabled: true, backend: .ollama, minRAMGB: 16),
            ],
            executionToolPolicy: .init(maxTurns: 30, allowWeb: true, allowShell: true, allowDesktop: true),
            requirements: .init(minRAMGB: 16, minFreeDiskGB: 2)
        ),

        ArchitectureTemplate(
            id: "skeptical",
            name: "Skeptical (perturb-focused)",
            nameJA: "懐疑的(摂動テスト重視)",
            description: "5 roles, deep rounds so the perturb-test always runs, and a high confidence bar before an answer is accepted — for questions where a confidently wrong answer is costly.",
            descriptionJA: "5役割、常に摂動テストが走る深いラウンド、回答を受け入れる確信度の基準を高く設定 — 自信を持って間違えるコストが高い質問向け。",
            councilConfig: .init(roleCount: 5, roundsCap: 6, injectionPolicy: .deepRounds,
                                 useVeraMemory: true, zoneLayers: [.l2],
                                 useEternalMemory: true, escalateOnLowConfidence: true,
                                 escalationConfidenceThreshold: 0.75),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 16),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, minRAMGB: 8),
                LayerSpec(role: .escalation, enabled: true, backend: .ollama, minRAMGB: 16),
            ],
            executionToolPolicy: .init(maxTurns: 12),
            requirements: .init(minRAMGB: 24, minFreeDiskGB: 3)
        ),

        ArchitectureTemplate(
            id: "research",
            name: "Research",
            nameJA: "リサーチ",
            description: "Deep deliberation with all memory on and web search enabled, for open-ended questions where gathering beats acting.",
            descriptionJA: "全記憶ON・Web検索ありで深く審議します。実行より調査が主になる、答えの決まっていない問い向け。",
            councilConfig: .init(roleCount: 4, roundsCap: 6, injectionPolicy: .earlySteal,
                                 useVeraMemory: true, zoneLayers: [.l1, .l1_5, .l2, .l3],
                                 useEternalMemory: true, escalateOnLowConfidence: true,
                                 escalationConfidenceThreshold: 0.65),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 12),
                LayerSpec(role: .execution, enabled: true, backend: .ollama, minRAMGB: 8),
                LayerSpec(role: .escalation, enabled: true, backend: .ollama, minRAMGB: 16),
            ],
            executionToolPolicy: .init(maxTurns: 20, allowWeb: true, allowShell: false),
            requirements: .init(minRAMGB: 16, minFreeDiskGB: 2, needsNetwork: true)
        ),

        ArchitectureTemplate(
            id: "fast",
            name: "Fast (single-pass)",
            nameJA: "高速(単一パス)",
            description: "2 roles, one round, no injection, no escalation — a quick sanity check with minimal overhead.",
            descriptionJA: "2役割・1ラウンド、注入なし、エスカレーションなし — 最小コストの簡易チェック。",
            councilConfig: .init(roleCount: 2, roundsCap: 1, injectionPolicy: .none,
                                 useVeraMemory: true, zoneLayers: [],
                                 useEternalMemory: false, escalateOnLowConfidence: false),
            layers: [
                LayerSpec(role: .memory, enabled: true, backend: .none),
                LayerSpec(role: .councilCore, enabled: true, backend: .jgen, minRAMGB: 6),
                LayerSpec(role: .execution, enabled: false, backend: .none),
                LayerSpec(role: .escalation, enabled: false, backend: .none),
            ],
            executionToolPolicy: .init(maxTurns: 4),
            requirements: .init(minRAMGB: 8, minFreeDiskGB: 1)
        ),
    ]
}
