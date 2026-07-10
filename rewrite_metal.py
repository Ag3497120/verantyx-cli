import re

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    content = f.read()

# Replace variables
content = content.replace("private var psoSpatialAttention: MTLComputePipelineState!", "private var psoBlockMatMul: MTLComputePipelineState!\n    private var psoSilu: MTLComputePipelineState!")
content = content.replace("private var psoSpatialFFN: MTLComputePipelineState!", "")

# Replace loadShaders
load_shaders_new = """    private func loadShaders() -> Bool {
        if isVerbose { print("[*] Compiling Metal Shaders...") }
        
        guard let library = try? device.makeLibrary(filepath: "default.metallib") else {
            if isVerbose { print("[-] Error: default.metallib not found in current directory.") }
            return false
        }
        
        do {
            if let fMatMul = library.makeFunction(name: "kernel_block_matmul") {
                psoBlockMatMul = try device.makeComputePipelineState(function: fMatMul)
            }
            if let fSilu = library.makeFunction(name: "kernel_silu") {
                psoSilu = try device.makeComputePipelineState(function: fSilu)
            }
            if isVerbose { print("[+] Metal Pipelines compiled successfully.") }
            return true
        } catch {
            if isVerbose { print("[-] Pipeline compilation failed: \\(error.localizedDescription)") }
            return false
        }
    }"""

content = re.sub(r'    private func loadShaders\(\) -> Bool \{.*?\n    \}', load_shaders_new, content, flags=re.DOTALL)

# Rewrite startDaemonLoop
daemon_loop_new = """    public func startDaemonLoop() {
        let dim = 5120
        let spineLength = dim * 2
        guard let zSpineBuffer = device.makeBuffer(length: spineLength, options: .storageModeShared) else { return }
        guard let layerOutBuffer = device.makeBuffer(length: spineLength, options: .storageModeShared) else { return }
        
        let zLayers = runtime.spatialGraph.keys.sorted()
        
        while true {
            var accumulatedData = Data()
            while accumulatedData.count < spineLength {
                let chunk = FileHandle.standardInput.readData(ofLength: spineLength - accumulatedData.count)
                if chunk.count == 0 { break }
                accumulatedData.append(chunk)
            }
            if accumulatedData.count < spineLength { break }
            if let string = String(data: accumulatedData, encoding: .utf8), string.hasPrefix("EXIT") { break }
            
            accumulatedData.withUnsafeBytes { rawPtr in
                memcpy(zSpineBuffer.contents(), rawPtr.baseAddress!, spineLength)
            }
            
            runtime.mappedData.withUnsafeBytes { rawPtr in
                guard let baseAddress = rawPtr.baseAddress else { return }
                
                for z in zLayers {
                    guard let blocks = runtime.spatialGraph[z], !blocks.isEmpty else { continue }
                    
                    // Clear intermediate layer output buffer
                    memset(layerOutBuffer.contents(), 0, spineLength)
                    
                    guard let commandBuffer = commandQueue.makeCommandBuffer(),
                          let encoder = commandBuffer.makeComputeCommandEncoder() else { return }
                    
                    var didDispatch = false
                    
                    if let pso = psoBlockMatMul {
                        encoder.setComputePipelineState(pso)
                        
                        for block in blocks {
                            // Only process actual weight matrices (ignore norm for now in this simple loop)
                            if block.matrixType == 0 || block.matrixType == 1 { continue }
                            
                            let blockPtr = baseAddress.advanced(by: block.fileOffset)
                            if let blockBuffer = device.makeBuffer(bytesNoCopy: UnsafeMutableRawPointer(mutating: blockPtr), length: block.length, options: .storageModeShared, deallocator: nil) {
                                
                                encoder.setBuffer(blockBuffer, offset: 0, index: 0)
                                encoder.setBuffer(zSpineBuffer, offset: 0, index: 1)
                                encoder.setBuffer(layerOutBuffer, offset: 0, index: 2)
                                
                                var rowIdx = uint(block.rowIdx)
                                encoder.setBytes(&rowIdx, length: MemoryLayout<uint>.size, index: 3)
                                
                                var colIdx = uint(block.colIdx)
                                encoder.setBytes(&colIdx, length: MemoryLayout<uint>.size, index: 4)
                                
                                var bSize = uint(64)
                                encoder.setBytes(&bSize, length: MemoryLayout<uint>.size, index: 5)
                                
                                let gridSize = MTLSizeMake(64, 1, 1)
                                let threadGroupSize = MTLSizeMake(min(pso.maxTotalThreadsPerThreadgroup, 64), 1, 1)
                                encoder.dispatchThreads(gridSize, threadsPerThreadgroup: threadGroupSize)
                                didDispatch = true
                            }
                        }
                    }
                    
                    encoder.endEncoding()
                    if didDispatch { 
                        commandBuffer.commit()
                        commandBuffer.waitUntilCompleted() 
                        
                        // Residual Add: zSpine += layerOut
                        let spinePtr = zSpineBuffer.contents().bindMemory(to: Float16.self, capacity: dim)
                        let outPtr = layerOutBuffer.contents().bindMemory(to: Float16.self, capacity: dim)
                        for i in 0..<dim {
                            spinePtr[i] += outPtr[i]
                        }
                        
                        // Simple non-linear activation to mix tokens and prevent explosion
                        if let cmdBuf2 = commandQueue.makeCommandBuffer(), let enc2 = cmdBuf2.makeComputeCommandEncoder(), let pso = psoSilu {
                            enc2.setComputePipelineState(pso)
                            enc2.setBuffer(zSpineBuffer, offset: 0, index: 0)
                            var sz = uint(dim)
                            enc2.setBytes(&sz, length: MemoryLayout<uint>.size, index: 1)
                            enc2.dispatchThreads(MTLSizeMake(dim, 1, 1), threadsPerThreadgroup: MTLSizeMake(min(pso.maxTotalThreadsPerThreadgroup, dim), 1, 1))
                            enc2.endEncoding()
                            cmdBuf2.commit()
                            cmdBuf2.waitUntilCompleted()
                        }
                    }
                }
            }
            
            let outputData = Data(bytes: zSpineBuffer.contents(), count: spineLength)
            FileHandle.standardOutput.write(outputData)
            fflush(stdout)
        }
    }"""

content = re.sub(r'    public func startDaemonLoop\(\) \{.*?\n    \}', daemon_loop_new, content, flags=re.DOTALL)

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.write(content)

