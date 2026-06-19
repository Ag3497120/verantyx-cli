import Foundation

// MARK: - Stubs for CLI compilation
// These replace the UI/App dependencies from VerantyxIDE

@MainActor
class GatekeeperModeState {
    static let shared = GatekeeperModeState()
    
    var useOllamaNER: Bool = false
    var commanderModel: String = "qwen-coder-32b"
    var vault: JCrossVault!
}

enum GatekeeperPipelineStep: String, Codable {
    case modelValidation
    case irGeneration
    case vaultSeparation
    case intentTranslate
    case promptBuild
    case llmCall
    case patchParse
    case vaultRehydrate
}

// L25IndexEngine stub for JCrossIRPatcher
class L25IndexEngine {
    static let shared = L25IndexEngine()
    func resolveSymbolPath(_ symbol: String) -> String? { return nil }
}


extension L25IndexEngine {
    func updateEntryInstantly(for fileURL: URL, workspaceURL: URL, patchContext: String) async {
        // No-op for CLI
    }
}

public class AppLanguage {
    public static let shared = AppLanguage()
    public func t(_ en: String, _ ja: String) -> String {
        return en
    }
}

public class AppState {
    public static let shared: AppState? = AppState()
    
    public var ollamaEndpoint: String = "http://127.0.0.1:11434"
    public var exoEnabled: Bool = false
    public var exoEndpoint: String = ""
}

public class BitNetCommanderEngine {
    public static let shared = BitNetCommanderEngine()
    public func generate(prompt: String, systemPrompt: String) async -> String? { return nil }
}

extension AppState {
    public var activeOllamaModel: String {
        get { return "gemma4:26b" }
        set { }
    }
}

