import Foundation
import VeraCore

struct VeraCLI {
    static func main() {
        let args = CommandLine.arguments
        
        guard args.count > 1 else {
            printUsage()
            return
        }
        
        let command = args[1]
        
        switch command {
        case "fetch":
            guard args.count == 3 else { print("Usage: verantyx fetch <repo_id>"); return }
            fetchModel(repoId: args[2])
            
        case "compile":
            guard args.count >= 4 else { print("Usage: verantyx compile <input.safetensors> --output <output.jcross>"); return }
            let input = args[2]
            var output = "model.jcross"
            if args.count == 5 && args[3] == "--output" { output = args[4] }
            compileModel(input: input, output: output)
            
        case "run":
            guard args.count >= 4, args[2] == "-p" else { print("Usage: verantyx run -p \"prompt\" <model.jcross>"); return }
            let prompt = args[3]
            let modelPath = args.count == 5 ? args[4] : "model.jcross"
            runInference(prompt: prompt, modelPath: modelPath)
            
        case "daemon":
            guard args.count >= 3 else { print("Usage: verantyx daemon <model.jcross>"); return }
            let modelPath = args[2]
            
            var embedPath = "", lmHeadPath = "", normPath = ""
            var embedOffset = 0, lmHeadOffset = 0, normOffset = 0
            var embedSize = 0, lmHeadSize = 0, normSize = 0
            
            for i in 3..<args.count {
                if args[i] == "--embed-path" { embedPath = args[i+1] }
                if args[i] == "--embed-offset" { embedOffset = Int(args[i+1]) ?? 0 }
                if args[i] == "--embed-size" { embedSize = Int(args[i+1]) ?? 0 }
                if args[i] == "--lm-head-path" { lmHeadPath = args[i+1] }
                if args[i] == "--lm-head-offset" { lmHeadOffset = Int(args[i+1]) ?? 0 }
                if args[i] == "--lm-head-size" { lmHeadSize = Int(args[i+1]) ?? 0 }
                if args[i] == "--norm-path" { normPath = args[i+1] }
                if args[i] == "--norm-offset" { normOffset = Int(args[i+1]) ?? 0 }
                if args[i] == "--norm-size" { normSize = Int(args[i+1]) ?? 0 }
            }
            
            runDaemon(modelPath: modelPath,
                      embedPath: embedPath, embedOffset: embedOffset, embedSize: embedSize,
                      lmHeadPath: lmHeadPath, lmHeadOffset: lmHeadOffset, lmHeadSize: lmHeadSize,
                      normPath: normPath, normOffset: normOffset, normSize: normSize)
            
        case "swarm":
            guard args.count >= 3 else { print("Usage: verantyx swarm \"<prompt>\" [--memory <16gb|24gb|32gb|64gb>]"); return }
            
            var promptArgs: [String] = []
            var memoryPreset = "64gb"
            
            var i = 2
            while i < args.count {
                if args[i] == "--memory" && i + 1 < args.count {
                    memoryPreset = args[i+1].lowercased()
                    i += 2
                } else {
                    promptArgs.append(args[i])
                    i += 1
                }
            }
            
            let prompt = promptArgs.joined(separator: " ")
            let runner = CLISwarmRunner()
            runner.run(prompt: prompt, memoryPreset: memoryPreset)
            
        default:
            print("Unknown command: \(command)")
            printUsage()
        }
    }
    
    static func printUsage() {
        print("""
        ========================================
          Verantyx Vera Inference CLI v1.0   
        ========================================
        Commands:
          fetch <repo>                            : Download model from HuggingFace
          compile <input> --output <out.jcross>   : Compile flat tensors to JCross Spatial Blocks
          run -p "prompt" <model.jcross>          : Execute Z-Wavefront Generation natively
          daemon <model.jcross> [options]         : Run as interactive daemon via stdin/stdout
          swarm "<prompt>"                        : Start 10-node Swarm Pipeline with Discussion Layer
        """)
    }
    
    static func fetchModel(repoId: String) {
        print("[*] Fetching \(repoId) via Python Bridge...")
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        task.arguments = ["python3", "scripts/vera_bridge.py", "fetch", repoId]
        try? task.run()
        task.waitUntilExit()
    }
    
    static func compileModel(input: String, output: String) {
        print("[*] Compiling \(input) to \(output) via Python Bridge...")
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        task.arguments = ["python3", "scripts/vera_compiler.py", "--model", input, "--output", output]
        try? task.run()
        task.waitUntilExit()
    }
    
    static func runInference(prompt: String, modelPath: String) {
        print("\n[-] The standalone 'run' command is deprecated for Phase 9.")
        print("    Please use the Python bridge daemon: python3 scripts/vera_bridge_daemon.py \"prompt\"")
    }
    
    static func runDaemon(modelPath: String,
                          embedPath: String, embedOffset: Int, embedSize: Int,
                          lmHeadPath: String, lmHeadOffset: Int, lmHeadSize: Int,
                          normPath: String, normOffset: Int, normSize: Int) {
        do {
            let runtime = VeraRuntime(modelPath: modelPath, verbose: true)
            try runtime.load()
            if let backend = VeraMetalBackend(runtime: runtime, verbose: true) {
                backend.prepareMemoryZones()
                
                if !embedPath.isEmpty {
                    backend.mapPyTorchTensors(embedPath: embedPath, embedOffset: embedOffset, embedSize: embedSize,
                                              lmHeadPath: lmHeadPath, lmHeadOffset: lmHeadOffset, lmHeadSize: lmHeadSize,
                                              normPath: normPath, normOffset: normOffset, normSize: normSize)
                }
                
                FileHandle.standardOutput.write("READY\n".data(using: .utf8)!)
                fflush(stdout)
                backend.startDaemonLoop()
            }
        } catch {
            print("[-] Daemon Error: \(error.localizedDescription)")
        }
    }
}

VeraCLI.main()
