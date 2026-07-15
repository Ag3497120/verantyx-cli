import re

with open("cli/Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    content = f.read()

struct_def = """struct BlockInfo {
    var rowIdx: UInt32
    var colIdx: UInt32
    var blockSize: UInt32
    var pad: UInt32 = 0 // for alignment if needed
    var byteOffset: UInt64
}

public class VeraMetalBackend {"""

content = content.replace("public class VeraMetalBackend {", struct_def)

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
                    
                    if let pso = psoBlockMatMul {
                        encoder.setComputePipelineState(pso)
                        
                        let firstOffset = blocks.first!.fileOffset
                        let lastOffset = blocks.last!.fileOffset + blocks.last!.length
                        
                        let alignedOffset = (firstOffset / 4096) * 4096
                        let alignedLength = ((lastOffset - alignedOffset + 4095) / 4096) * 4096
                        
                        if let layerBuffer = device.makeBuffer(bytesNoCopy: UnsafeMutableRawPointer(mutating: baseAddress.advanced(by: alignedOffset)), length: alignedLength, options: .storageModeShared, deallocator: nil) {
                            
                            encoder.setBuffer(layerBuffer, offset: 0, index: 0)
                            encoder.setBuffer(zSpineBuffer, offset: 0, index: 1)
                            encoder.setBuffer(layerOutBuffer, offset: 0, index: 2)
                            
                            var blockInfos: [BlockInfo] = []
                            for block in blocks {
                                if block.matrixType == 0 || block.matrixType == 1 { continue }
                                let info = BlockInfo(rowIdx: UInt32(block.rowIdx), colIdx: UInt32(block.colIdx), blockSize: UInt32(64), pad: 0, byteOffset: UInt64(block.fileOffset - alignedOffset))
                                blockInfos.append(info)
                            }
                            
                            if !blockInfos.isEmpty {
                                let infoBuffer = device.makeBuffer(bytes: blockInfos, length: blockInfos.count * MemoryLayout<BlockInfo>.stride, options: .storageModeShared)
                                encoder.setBuffer(infoBuffer, offset: 0, index: 3)
                                
                                let gridSize = MTLSizeMake(blockInfos.count, 1, 1)
                                let threadGroupSize = MTLSizeMake(1, 1, 1)
                                encoder.dispatchThreadgroups(gridSize, threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                            }
                        }
                    }
                    
                    encoder.endEncoding()
                    commandBuffer.commit()
                    commandBuffer.waitUntilCompleted() 
                    
                    let spinePtr = zSpineBuffer.contents().bindMemory(to: Float16.self, capacity: dim)
                    let outPtr = layerOutBuffer.contents().bindMemory(to: Float16.self, capacity: dim)
                    for i in 0..<dim {
                        spinePtr[i] += outPtr[i]
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
