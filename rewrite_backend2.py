import re

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    content = f.read()

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
            
            _ = accumulatedData.withUnsafeBytes { rawPtr in
                memcpy(zSpineBuffer.contents(), rawPtr.baseAddress!, spineLength)
            }
            
            runtime.mappedData.withUnsafeBytes { rawPtr in
                guard let baseAddress = rawPtr.baseAddress else { return }
                
                for z in zLayers {
                    guard let blocks = runtime.spatialGraph[z], !blocks.isEmpty else { continue }
                    
                    memset(layerOutBuffer.contents(), 0, spineLength)
                    
                    guard let commandBuffer = commandQueue.makeCommandBuffer(),
                          let encoder = commandBuffer.makeComputeCommandEncoder() else { return }
                    
                    var didDispatch = false
                    
                    if let pso = psoBlockMatMul {
                        encoder.setComputePipelineState(pso)
                        
                        // Create ONE buffer for the entire layer's mapped span to avoid 30k buffer bindings
                        let firstOffset = blocks.first!.fileOffset
                        let lastOffset = blocks.last!.fileOffset + blocks.last!.length
                        let spanLength = lastOffset - firstOffset
                        
                        // Only create if we can page align the start. To be safe, let's just pass the raw pointer via setBytes if possible? No, we can't.
                        // Actually, we can just use the memory map of the entire model if device supports it!
                        // Let's try to make one buffer for the whole mappedData:
                        if let wholeBuffer = device.makeBuffer(bytesNoCopy: UnsafeMutableRawPointer(mutating: baseAddress), length: runtime.mappedData.count, options: .storageModeShared, deallocator: nil) {
                            
                            encoder.setBuffer(wholeBuffer, offset: 0, index: 0)
                            encoder.setBuffer(zSpineBuffer, offset: 0, index: 1)
                            encoder.setBuffer(layerOutBuffer, offset: 0, index: 2)
                            
                            for block in blocks {
                                if block.matrixType == 0 || block.matrixType == 1 { continue }
                                
                                var rowIdx = uint(block.rowIdx)
                                encoder.setBytes(&rowIdx, length: MemoryLayout<uint>.size, index: 3)
                                
                                var colIdx = uint(block.colIdx)
                                encoder.setBytes(&colIdx, length: MemoryLayout<uint>.size, index: 4)
                                
                                var bSize = uint(64)
                                encoder.setBytes(&bSize, length: MemoryLayout<uint>.size, index: 5)
                                
                                var fileOffset = uint(block.fileOffset)
                                encoder.setBytes(&fileOffset, length: MemoryLayout<uint>.size, index: 6)
                                
                                let gridSize = MTLSizeMake(64, 1, 1)
                                let threadGroupSize = MTLSizeMake(min(pso.maxTotalThreadsPerThreadgroup, 64), 1, 1)
                                // Dispatch using the same buffer, just passing fileOffset!
                                encoder.dispatchThreads(gridSize, threadsPerThreadgroup: threadGroupSize)
                                didDispatch = true
                            }
                        }
                    }
                    
                    encoder.endEncoding()
                    if didDispatch { 
                        commandBuffer.commit()
                        commandBuffer.waitUntilCompleted() 
                        
                        let spinePtr = zSpineBuffer.contents().bindMemory(to: Float16.self, capacity: dim)
                        let outPtr = layerOutBuffer.contents().bindMemory(to: Float16.self, capacity: dim)
                        for i in 0..<dim {
                            spinePtr[i] += outPtr[i]
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
