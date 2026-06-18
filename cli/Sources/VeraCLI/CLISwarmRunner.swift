import Foundation

class CLISwarmRunner {
    private var process: Process?
    private var standardInputPipe = Pipe()
    private var standardOutputPipe = Pipe()
    private var standardErrorPipe = Pipe()

    // ANSI Colors for output formatting
    private let colorReset = "\u{001B}[0m"
    private let colorCyan = "\u{001B}[36m"
    private let colorYellow = "\u{001B}[33m"
    private let colorGreen = "\u{001B}[32m"
    private let colorRed = "\u{001B}[31m"
    private let colorMagenta = "\u{001B}[35m"
    private let colorBlue = "\u{001B}[34m"

    func run(prompt: String, memoryPreset: String = "64gb") {
        print("\(colorCyan)[VeraCLI] Starting Swarm Pipeline for prompt: \"\(prompt)\" with memory preset: \(memoryPreset)\(colorReset)")
        
        var numNodes = 10
        var numSub = 3
        
        switch memoryPreset {
        case "16gb":
            numNodes = 3
            numSub = 0
        case "24gb":
            numNodes = 5
            numSub = 0
        case "32gb":
            numNodes = 7
            numSub = 1
        case "64gb":
            numNodes = 10
            numSub = 3
        default:
            print("\(colorYellow)[VeraCLI] Warning: Unknown memory preset '\(memoryPreset)'. Defaulting to 64gb.\(colorReset)")
        }
        
        process = Process()
        guard let process = process else { return }

        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        
        let currentDir = FileManager.default.currentDirectoryPath
        let projectRoot = currentDir.hasSuffix("/cli") ? (currentDir as NSString).deletingLastPathComponent : currentDir
        process.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
        
        process.arguments = ["python3", "cli/scripts/start_swarm_pipeline_socket.py", 
                             "--prompt", prompt,
                             "--nodes", String(numNodes),
                             "--sub_commanders", String(numSub)]

        process.standardInput = standardInputPipe
        process.standardOutput = standardOutputPipe
        process.standardError = standardErrorPipe

        // Handle Stdout (JSON-RPC tools & final output)
        standardOutputPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let str = String(data: data, encoding: .utf8) else { return }
            self?.handleStdout(str)
        }

        // Handle Stderr (Streaming Logs)
        standardErrorPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let str = String(data: data, encoding: .utf8) else { return }
            self?.handleStderr(str)
        }

        do {
            try process.run()
            process.waitUntilExit()
            
            // Clean up handlers
            standardOutputPipe.fileHandleForReading.readabilityHandler = nil
            standardErrorPipe.fileHandleForReading.readabilityHandler = nil
            
            print("\(colorGreen)[VeraCLI] Swarm Pipeline finished.\(colorReset)")
        } catch {
            print("\(colorRed)[VeraCLI] Failed to run Swarm process: \(error)\(colorReset)")
        }
    }

    private func handleStderr(_ output: String) {
        let lines = output.split(separator: "\n")
        for line in lines {
            let strLine = String(line)
            
            // Colorize based on keywords
            if strLine.contains("Discussion Turn") {
                print("\(colorMagenta)\(strLine)\(colorReset)")
            } else if strLine.contains("Commander") {
                print("\(colorBlue)\(strLine)\(colorReset)")
            } else if strLine.contains("SubCommander") {
                print("\(colorYellow)\(strLine)\(colorReset)")
            } else if strLine.contains("Worker") {
                print("\(colorGreen)\(strLine)\(colorReset)")
            } else if strLine.contains("Error") || strLine.contains("Failed") {
                print("\(colorRed)\(strLine)\(colorReset)")
            } else {
                print(strLine) // default
            }
        }
        fflush(stdout)
    }

    private func handleStdout(_ output: String) {
        let lines = output.split(separator: "\n")
        for line in lines {
            let strLine = String(line)
            
            if let data = strLine.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any] {
                
                // If it's a JSON-RPC request from a worker
                if let method = json["method"] as? String,
                   let id = json["id"] as? Int,
                   let params = json["params"] as? [String: Any] {
                    
                    print("\(colorCyan)[VeraCLI - Tool Execution] Node \(id) requested: \(method)\(colorReset)")
                    executeTool(method: method, params: params, nodeId: id)
                } 
                // If it's the final result from orchestrator
                else if let status = json["status"] as? String, status == "success",
                        let resultText = json["result"] as? String {
                    print("\n\(colorGreen)================ FINAL RESULT ================\(colorReset)")
                    print("\(resultText)")
                    print("\(colorGreen)==============================================\(colorReset)\n")
                }
            } else {
                // Not JSON, just print it out
                print(strLine)
            }
        }
        fflush(stdout)
    }

    private func executeTool(method: String, params: [String: Any], nodeId: Int) {
        var resultText = ""
        
        switch method {
        case "read_file":
            if let path = params["path"] as? String {
                do {
                    resultText = try String(contentsOfFile: path, encoding: .utf8)
                } catch {
                    resultText = "Error reading file: \(error.localizedDescription)"
                }
            } else {
                resultText = "Error: Invalid path parameter"
            }
            
        case "write_file":
            if let path = params["path"] as? String, let content = params["content"] as? String {
                do {
                    try content.write(toFile: path, atomically: true, encoding: .utf8)
                    resultText = "Successfully wrote to \(path)"
                } catch {
                    resultText = "Error writing file: \(error.localizedDescription)"
                }
            } else {
                resultText = "Error: Invalid parameters for write_file"
            }
            
        case "list_directory":
            if let path = params["path"] as? String {
                do {
                    let items = try FileManager.default.contentsOfDirectory(atPath: path)
                    resultText = items.joined(separator: "\n")
                } catch {
                    resultText = "Error listing directory: \(error.localizedDescription)"
                }
            } else {
                resultText = "Error: Invalid parameters for list_directory"
            }
            
        default:
            resultText = "Unknown tool: \(method)"
        }
        
        // Return JSON-RPC response to stdout so Python pipeline can read it from stdin
        let response: [String: Any] = [
            "jsonrpc": "2.0",
            "result": resultText,
            "id": nodeId
        ]
        
        if let responseData = try? JSONSerialization.data(withJSONObject: response, options: []),
           var responseString = String(data: responseData, encoding: .utf8) {
            responseString += "\n"
            if let writeData = responseString.data(using: .utf8) {
                standardInputPipe.fileHandleForWriting.write(writeData)
            }
        }
    }
}
