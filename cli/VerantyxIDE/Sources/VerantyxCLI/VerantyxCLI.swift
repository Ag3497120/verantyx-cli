import Foundation
import ArgumentParser

@main
struct VerantyxCLI: AsyncParsableCommand {
    static var configuration = CommandConfiguration(
        commandName: "verantyx-cli",
        abstract: "Verantyx JCross Obfuscation CLI",
        subcommands: [ObfuscateCommand.self],
        defaultSubcommand: ObfuscateCommand.self
    )
}

struct ObfuscateCommand: AsyncParsableCommand {
    static var configuration = CommandConfiguration(
        commandName: "obfuscate",
        abstract: "Obfuscates a directory using JCross 6-axis engine"
    )
    
    @Argument(help: "Target directory to obfuscate (default: current directory)")
    var targetDir: String = "."
    
    @Option(name: .shortAndLong, help: "Comma-separated list of additional directories or files to exclude")
    var exclude: String = ""
    
    @Flag(help: "Enable Ollama NER support for secrets")
    var useOllamaNER: Bool = false
    
    @MainActor
    mutating func run() async throws {
        print("🚀 Verantyx JCross Obfuscator CLI")
        
        let fileManager = FileManager.default
        let currentPath = fileManager.currentDirectoryPath
        let targetURL = URL(fileURLWithPath: targetDir)
        let resolvedPath = targetURL.scheme == "file" && targetDir.hasPrefix("/") ? targetURL.standardizedFileURL : URL(fileURLWithPath: currentPath).appendingPathComponent(targetDir).standardizedFileURL
        
        print("📁 Target Directory: \(resolvedPath.path)")
        
        GatekeeperModeState.shared.useOllamaNER = useOllamaNER
        GatekeeperModeState.shared.commanderModel = "qwen-coder-32b"
        
        let vault = JCrossVault(workspaceURL: resolvedPath)
        GatekeeperModeState.shared.vault = vault
        
        // Add custom excludes logic here (to be implemented)
        
        print("🔄 Starting JCross conversion process...")
        await vault.initialize()
        
        while true {
            switch vault.vaultStatus {
            case .ready(let fileCount, _):
                print("\n✅ Conversion finished successfully. (\(fileCount) files)")
                print("📁 Artifacts stored in: \(resolvedPath.path)/.openclaw/jcross_vault")
                return
            case .error(let msg):
                print("\n❌ Conversion failed: \(msg)")
                return
            case .converting(let progress, let currentFile):
                let percent = String(format: "%.1f", progress * 100)
                print("\r⏳ Converting... \(percent)% (\(currentFile))", terminator: "")
                try await Task.sleep(nanoseconds: 100_000_000)
            case .notInitialized:
                try await Task.sleep(nanoseconds: 100_000_000)
            }
        }
    }
}
