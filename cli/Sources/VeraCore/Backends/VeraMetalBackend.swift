import Foundation
import Metal

struct BlockInfo {
    var rowIdx: UInt32
    var colIdx: UInt32
    var blockSize: UInt32
    var pad: UInt32 = 0
    var byteOffset: UInt64
}

public class VeraMetalBackend {
    private let device: MTLDevice
    private let commandQueue: MTLCommandQueue
    
    private var globalMmapPtr: UnsafeMutableRawPointer?
    private var globalMmapBuffer: MTLBuffer?
    private var globalMmapBuffer1: MTLBuffer?
    private var maxMmapBufferLength: UInt64 = 0
    private let runtime: VeraRuntime
    
    private var psoBlockMatMul: MTLComputePipelineState!
    private var psoClearBuffer: MTLComputePipelineState!
    private var psoRmsNorm: MTLComputePipelineState!
    private var psoSwiGLU: MTLComputePipelineState!
    private var psoZero: MTLComputePipelineState!
    private var psoAdd: MTLComputePipelineState!
    private var psoRope: MTLComputePipelineState!
    private var psoAttention: MTLComputePipelineState!
    private var psoWriteKVCache: MTLComputePipelineState!
    
    private var psoLinearConv1d: MTLComputePipelineState!
    private var psoLinearL2Norm: MTLComputePipelineState!
    private var psoLinearRecurrent: MTLComputePipelineState!
    private var psoLinearRMSNormGated: MTLComputePipelineState!
    private var psoLinearGatedOnly: MTLComputePipelineState!
    private var psoQkNorm: MTLComputePipelineState!
    private var psoLMHeadNorm: MTLComputePipelineState!
    private var psoLMHead: MTLComputePipelineState!
    private var psoArgmax: MTLComputePipelineState!
    private var psoEmbedLookup: MTLComputePipelineState!
    
    private var psoSplitQGate: MTLComputePipelineState!
    private var psoSiluMul: MTLComputePipelineState!
    
    // Phase 7: Predictive Routing & Amplification
    private var spatialMomentum: [Int: [Float]] = [:]
    private var staticRouteMap: [Int: [Float]] = [:]
    private var expectedVariance: [Int: Float] = [:]
    
    private var lmHeadBuffer: MTLBuffer?
    private var lmHeadAlignOffset: Int = 0
    private var embedBuffer: MTLBuffer?
    private var finalNormBuffer: MTLBuffer?
    private var ssmStateBuffer: MTLBuffer!
    
    var qOutBuffer: MTLBuffer!
    var qGateBuffer: MTLBuffer!
    var kOutBuffer: MTLBuffer!
    var vOutBuffer: MTLBuffer!
    var outQkvBuffer: MTLBuffer!
    
    private var varianceBuffer: MTLBuffer!
    private var logitsBuffer: MTLBuffer!
    private var outTokenBuffer: MTLBuffer!
    private var vocabSize: UInt32 = 248320
    private var embedMmapPtr: UnsafeMutableRawPointer? = nil
    private var lmHeadMmapPtr: UnsafeMutableRawPointer? = nil
    private var normMmapPtr: UnsafeMutableRawPointer? = nil
    
    private var embedAlignOffset: Int = 0
    private var jmetaTensors: [UInt8: [UInt8: Data]] = [:]
    private var isVerbose: Bool = true
    
    public init?(runtime: VeraRuntime, verbose: Bool = false) {
        self.isVerbose = true
        guard let defaultDevice = MTLCreateSystemDefaultDevice() else {
            if verbose { fputs("[-] Metal is not supported on this device.\n", stderr); fflush(stderr) }
            return nil
        }
        self.device = defaultDevice
        
        guard let queue = device.makeCommandQueue() else {
            if verbose { fputs("[-] Failed to create Metal command queue.\n", stderr); fflush(stderr) }
            return nil
        }
        self.commandQueue = queue
        self.runtime = runtime
        
        if !AsynchronousPrefetcher.shared.openFile(path: runtime.modelPath) {
            fputs("[-] Failed to open .jcross file for AsynchronousPrefetcher!\n", stderr)
            return nil
        }
        if verbose { fputs("[*] Successfully initialized AsynchronousPrefetcher for \(runtime.modelPath)\n", stderr); fflush(stderr) }
        
        if verbose { fputs("[*] VeraMetalBackend initialized on GPU: \(device.name)\n", stderr); fflush(stderr) }
        
        if !loadShaders() { return nil }
        loadJMeta()
        
        let mapPath = "route_map.json"
        if let data = try? Data(contentsOf: URL(fileURLWithPath: mapPath)),
           let json = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any],
           let layers = json["layers"] as? [String: Any] {
            for (key, val) in layers {
                if let z = Int(key), let layerDict = val as? [String: Any] {
                    if let ffn = layerDict["ffn_dim_scores"] as? [Float] {
                        staticRouteMap[z] = ffn
                    }
                    if let evar = layerDict["expected_variance"] as? Float {
                        expectedVariance[z] = evar
                    }
                }
            }
            if verbose { fputs("[*] Loaded Activation Atlas from route_map.json\n", stderr); fflush(stderr) }
        }
    }
    
    private func loadShaders() -> Bool {
        if isVerbose { fputs("[*] Compiling Metal Shaders...\n", stderr); fflush(stderr) }
        
        guard let library = try? device.makeLibrary(filepath: "default.metallib") else {
            if isVerbose { fputs("[-] Error: default.metallib not found in current directory.\n", stderr); fflush(stderr) }
            return false
        }
        
        do {
            psoBlockMatMul = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_block_matmul")!)
            psoClearBuffer = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_clear_buffer")!)
            psoRmsNorm = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_rmsnorm")!)
            psoSwiGLU = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_swiglu")!)
            psoZero = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_zero")!)
            psoAdd = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_add")!)
            psoRope = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_rope")!)
            psoRope = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_rope")!)
            psoAttention = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_attention")!)
            psoWriteKVCache = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_write_kv_cache")!)
            
            psoLinearConv1d = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_linear_conv1d")!)
            psoLinearL2Norm = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_linear_l2norm")!)
            psoLinearRecurrent = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_linear_recurrent_step")!)
            psoLinearRMSNormGated = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_linear_rmsnorm_gated")!)
            psoLinearGatedOnly = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_linear_gated_only")!)
            
            psoQkNorm = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_qk_norm")!)
            psoLMHeadNorm = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_lm_head_norm")!)
            psoLMHead = try device.makeComputePipelineState(function: library.makeFunction(name: "kernel_lm_head")!)
            psoArgmax = try! device.makeComputePipelineState(function: library.makeFunction(name: "kernel_argmax")!)
            psoEmbedLookup = try! device.makeComputePipelineState(function: library.makeFunction(name: "kernel_embed_lookup")!)
            psoSplitQGate = try! device.makeComputePipelineState(function: library.makeFunction(name: "kernel_split_q_gate")!)
            psoSiluMul = try! device.makeComputePipelineState(function: library.makeFunction(name: "kernel_silu_mul")!)
            
            if isVerbose { fputs("[+] Metal Pipelines compiled successfully.\n", stderr); fflush(stderr) }
            return true
        } catch {
            if isVerbose { fputs("[-] Pipeline compilation failed: \(error.localizedDescription)\n", stderr); fflush(stderr) }
            return false
        }
    }
    
    private func loadJMeta() {
        let metaPath = URL(fileURLWithPath: "qwen_27b.jmeta")
        guard let data = try? Data(contentsOf: metaPath) else {
            fputs("[-] Could not find qwen_27b.jmeta\n", stderr); fflush(stderr)
            return
        }
        
        var offset = 8 // Skip magic and version
        while offset + 6 <= data.count {
            let header = data.subdata(in: offset..<offset+6)
            let z = header[0]
            let mtype = header[1]
            let length = header.withUnsafeBytes { $0.loadUnaligned(fromByteOffset: 2, as: UInt32.self) }
            
            offset += 6
            if offset + Int(length) > data.count { break }
            let tensorData = data.subdata(in: offset..<offset+Int(length))
            
            if jmetaTensors[z] == nil { jmetaTensors[z] = [:] }
            jmetaTensors[z]![mtype] = tensorData
            
            offset += Int(length)
        }
        
        if jmetaTensors.isEmpty {
            if isVerbose { fputs("[-] Could not find qwen_27b.jmeta\n", stderr); fflush(stderr) }
        } else {
            if isVerbose { fputs("[+] Loaded .jmeta with \(jmetaTensors.keys.count) layers.\n", stderr); fflush(stderr) }
            if isVerbose {
                if let t0 = jmetaTensors[0] {
                    fputs("[+] Z=0 jmeta matrix types: \(t0.keys)\n", stderr); fflush(stderr)
                } else {
                    fputs("[-] Z=0 NOT IN jmetaTensors\n", stderr); fflush(stderr)
                }
            }
        }
    }
    
    public func mapPyTorchTensors(embedPath: String, embedOffset: Int, embedSize: Int,
                                  lmHeadPath: String, lmHeadOffset: Int, lmHeadSize: Int,
                                  normPath: String, normOffset: Int, normSize: Int) {
        
        func mapFile(path: String, offset: Int, size: Int) -> (ptr: UnsafeMutableRawPointer, alignOffset: Int)? {
            let fd = open(path, O_RDONLY)
            if fd < 0 { return nil }
            // Alignment to page size
            let pageSize = Int(getpagesize())
            let alignOffset = offset % pageSize
            let mmapOffset = offset - alignOffset
            let mmapSize = size + alignOffset
            
            let ptr = mmap(nil, mmapSize, PROT_READ, MAP_SHARED, fd, off_t(mmapOffset))
            close(fd)
            if ptr == MAP_FAILED { return nil }
            return (ptr!, alignOffset)
        }
        
        if let embedMap = mapFile(path: embedPath, offset: embedOffset, size: embedSize) {
            self.embedMmapPtr = embedMap.ptr.advanced(by: embedMap.alignOffset)
            self.embedBuffer = device.makeBuffer(length: 10240, options: .storageModeShared)
        }
        
        if let lmHeadMap = mapFile(path: lmHeadPath, offset: lmHeadOffset, size: lmHeadSize) {
            let alignedPtr = lmHeadMap.ptr
            let alignOffset = lmHeadMap.alignOffset
            self.lmHeadMmapPtr = alignedPtr.advanced(by: alignOffset)
            
            let mmapSize = lmHeadSize + alignOffset
            self.lmHeadBuffer = device.makeBuffer(bytesNoCopy: alignedPtr, length: mmapSize, options: .storageModeShared, deallocator: { (ptr, size) in
                munmap(ptr, size)
            })
            self.lmHeadAlignOffset = alignOffset
            // Use exact vocab size for Qwen, ignoring padded garbage
            self.vocabSize = 151936
        }
        
        if let normMap = mapFile(path: normPath, offset: normOffset, size: normSize) {
            self.normMmapPtr = normMap.ptr.advanced(by: normMap.alignOffset)
            self.finalNormBuffer = device.makeBuffer(length: normSize, options: .storageModeShared)
            if let dest = self.finalNormBuffer?.contents() {
                memcpy(dest, self.normMmapPtr, normSize)
            }
        }
        
        fputs("[+] Initialized memory mapped PyTorch tensors for token generation.\n", stderr)
        if isVerbose {
            fputs("[*] Successfully memory-mapped PyTorch Tensors.\n", stderr)
            fflush(stderr)
        }
    }
    
    public func prepareMemoryZones() {
        if isVerbose { fputs("[*] JIT VRAM Allocation Mode: Weights will stream directly from SSD.\n", stderr); fflush(stderr) }
    }
    
    public func startDaemonLoop() {
        let dim = 5120
        let intDim = 17408
        let spineLength = dim * 4 // float32 size
        
        if self.lmHeadBuffer != nil {
            self.varianceBuffer = device.makeBuffer(length: 4, options: .storageModeShared)
            self.logitsBuffer = device.makeBuffer(length: Int(self.vocabSize) * 4, options: .storageModeShared)
            self.outTokenBuffer = device.makeBuffer(length: 4, options: .storageModeShared)
        }

        guard let zSpineBuffer = device.makeBuffer(length: spineLength, options: .storageModeShared) else { return }
        guard let normedSpineBuffer = device.makeBuffer(length: dim * 4, options: .storageModeShared) else { return }
        guard let gateOutBuffer = device.makeBuffer(length: intDim * 4, options: .storageModeShared) else { return }
        guard let upOutBuffer = device.makeBuffer(length: intDim * 4, options: .storageModeShared) else { return }
        guard let downOutBuffer = device.makeBuffer(length: dim * 4, options: .storageModeShared) else { return }
        guard let globalSumBuffer = device.makeBuffer(length: 4, options: .storageModeShared) else { return }
        
        guard let tempQBuffer = device.makeBuffer(length: 12288 * 4, options: .storageModeShared) else { return }
        
        guard let qOutBuffer = device.makeBuffer(length: 12288 * 4, options: .storageModeShared) else { return }
        guard let qGateBuffer = device.makeBuffer(length: 12288 * 4, options: .storageModeShared) else { return }
        guard let kOutBuffer = device.makeBuffer(length: 1024 * 4, options: .storageModeShared) else { return }
        guard let vOutBuffer = device.makeBuffer(length: 1024 * 4, options: .storageModeShared) else { return }
        
        guard let outQkvBuffer = device.makeBuffer(length: 10240 * 4, options: .storageModeShared) else { return }
        guard let outBBuffer = device.makeBuffer(length: 64 * 4, options: .storageModeShared) else { return }
        guard let outABuffer = device.makeBuffer(length: 64 * 4, options: .storageModeShared) else { return }
        
        // 64 layers * 4096 max seq len * 2 (K, V) * 1024 (heads * head_dim) * 2 bytes (half precision)
        guard let kvCacheBuffer = device.makeBuffer(length: 64 * 4096 * 2 * 1024 * 2, options: .storageModeShared) else { return }
        
        // SSM DeltaNet Buffers
        guard let ssmConvBuffer = device.makeBuffer(length: 64 * 10240 * 4 * 4, options: .storageModeShared) else { return }
        memset(ssmConvBuffer.contents(), 0, ssmConvBuffer.length)
        guard let ssmRecurrentBuffer = device.makeBuffer(length: 64 * 48 * 128 * 128 * 4, options: .storageModeShared) else { return }
        memset(ssmRecurrentBuffer.contents(), 0, ssmRecurrentBuffer.length)
        guard let linearQkvOutBuffer = device.makeBuffer(length: 10240 * 4, options: .storageModeShared) else { return }
        guard let linearCoreAttnOutBuffer = device.makeBuffer(length: 6144 * 4, options: .storageModeShared) else { return }
        
        memset(linearQkvOutBuffer.contents(), 0, linearQkvOutBuffer.length)
        memset(linearCoreAttnOutBuffer.contents(), 0, linearCoreAttnOutBuffer.length)
        
        // Static ring buffers for zero-copy streaming without MTLBuffer fragmentation
        let maxWeightBufferSize = 1500 * 1024 * 1024 // 1.5 GB per layer
        
        // Setup LM Head buffers
        let jheadPath = ProcessInfo.processInfo.environment["VERA_JHEAD_PATH"] ?? (URL(fileURLWithPath: runtime.modelPath).deletingPathExtension().path + ".jhead").replacingOccurrences(of: "file://", with: "")
            if FileManager.default.fileExists(atPath: jheadPath) {
                do {
                    let jheadData = try Data(contentsOf: URL(fileURLWithPath: jheadPath), options: .alwaysMapped)
                    if jheadData.count > 12 {
                        let header = jheadData.subdata(in: 0..<4)
                        if header == "JHED".data(using: .utf8) {
                            var offset = 8
                            
                            // Norm
                            let normLen = jheadData.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
                            offset += 4
                            finalNormBuffer = device.makeBuffer(bytes: [UInt8](jheadData.subdata(in: offset..<offset+Int(normLen))), length: Int(normLen), options: .storageModeShared)
                            offset += Int(normLen)
                            
                            // Align offset + 8 to 16384
                            let targetWeightPos = ((offset + 8 + 16383) / 16384) * 16384
                            offset = targetWeightPos - 8
                            
                            // LM Head
                            let vSize = jheadData.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
                            offset += 4
                            let dimSize = jheadData.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
                            offset += 4
                            
                            vocabSize = vSize
                            let headLen = Int(vSize * dimSize * 2)
                            
                            jheadData.withUnsafeBytes { rawPtr in
                                let headPtr = rawPtr.baseAddress!.advanced(by: offset)
                                lmHeadBuffer = device.makeBuffer(bytesNoCopy: UnsafeMutableRawPointer(mutating: headPtr), length: headLen, options: .storageModeShared, deallocator: nil)
                            }
                            
                            varianceBuffer = device.makeBuffer(length: 4, options: .storageModeShared)
                            logitsBuffer = device.makeBuffer(length: Int(vocabSize) * 4, options: .storageModeShared)
                            outTokenBuffer = device.makeBuffer(length: 4, options: .storageModeShared)
                        }
                    }
                } catch {
                    fputs("[-] Failed to load jhead file: \(error)\n", stderr)
                }
            }
        
        // VRAM Ring Buffer for Weights Streaming (to bypass OS Cache & GPU Page Faults)
        var weightBufferPtr: UnsafeMutableRawPointer?
        posix_memalign(&weightBufferPtr, 16384, maxWeightBufferSize)
        guard let validWeightPtr = weightBufferPtr else {
            fputs("[-] FATAL: Failed to posix_memalign weight buffer.\n", stderr)
            return
        }
        guard let globalWeightBuffer = device.makeBuffer(bytesNoCopy: validWeightPtr, length: maxWeightBufferSize, options: .storageModeShared, deallocator: { ptr, size in
            free(ptr)
        }) else { return }
        
        let maxInfoBufferSize = 20 * 1024 * 1024 // 20 MB per layer
        guard let globalInfoBuffer = device.makeBuffer(length: maxInfoBufferSize, options: .storageModeShared) else { 
            fputs("[-] Failed to allocate globalInfoBuffer (20MB)\n", stderr)
            return 
        }
        
        let zLayers = runtime.spatialGraph.keys.sorted()
        
        var currentPos: UInt32 = 0
        
        while true {
            autoreleasepool {
                let expectedBytes = (self.embedMmapPtr != nil) ? 4 : spineLength
                var accumulatedData = Data()
                while accumulatedData.count < expectedBytes {
                    let chunk = FileHandle.standardInput.readData(ofLength: expectedBytes - accumulatedData.count)
                    if chunk.count == 0 {
                        fputs("  > chunk.count == 0, breaking\n", stderr)
                        fflush(stderr)
                        break
                    }
                    accumulatedData.append(chunk)
                }
                if accumulatedData.count < expectedBytes {
                    fputs("  > accumulatedData.count < expectedBytes (\(accumulatedData.count)), breaking\n", stderr)
                    fflush(stderr)
                    exit(0) // Use exit(0) to safely terminate instead of infinite loop
                }
                
                if let embedPtr = self.embedMmapPtr, let embed = self.embedBuffer {
                    // Token ID mode
                    var tokenId = accumulatedData.withUnsafeBytes { $0.load(as: UInt32.self) }
                    var dim32 = UInt32(dim)
                    
                    // Copy 10KB row into tiny reusable buffer
                    let offset = Int(tokenId) * dim * 2
                    memcpy(embed.contents(), embedPtr.advanced(by: offset), dim * 2)
                    
                    if let cmdBuffer = self.commandQueue.makeCommandBuffer(),
                       let currentEncoder = cmdBuffer.makeComputeCommandEncoder() {
                        
                        currentEncoder.setComputePipelineState(self.psoEmbedLookup)
                        
                        // We use the tiny embedBuffer and treat it as if it's the embed_tokens matrix but with only 1 row!
                        // In the shader, token_id * dim + tid is used. To avoid out-of-bounds, we pass token_id = 0 to the shader!
                        currentEncoder.setBuffer(embed, offset: 0, index: 0)
                        currentEncoder.setBuffer(zSpineBuffer, offset: 0, index: 1)
                        var zeroToken: UInt32 = 0
                        currentEncoder.setBytes(&zeroToken, length: 4, index: 2)
                        currentEncoder.setBytes(&dim32, length: 4, index: 3)
                        
                        currentEncoder.dispatchThreadgroups(MTLSizeMake((dim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        currentEncoder.endEncoding()
                        cmdBuffer.commit()
                        cmdBuffer.waitUntilCompleted()
                        
                        if isVerbose {
                            let zSpineData = zSpineBuffer.contents().assumingMemoryBound(to: Float.self)
                            fputs("  > zSpine AFTER embed [0..<5]: \(zSpineData[0]), \(zSpineData[1]), \(zSpineData[2]), \(zSpineData[3]), \(zSpineData[4])\n", stderr)
                            fflush(stderr)
                        }
                        if isVerbose {
                            let zSpineData = zSpineBuffer.contents().assumingMemoryBound(to: UInt16.self) // BFloat16 but just checking if zero or weird
                            fputs("    [Debug] zSpine after embed: \(String(format: "%04x", zSpineData[0])), \(String(format: "%04x", zSpineData[1]))\n", stderr)
                        }
                    }
                    if isVerbose {
                        fputs("  > Received Token ID \(tokenId)! Embed lookup complete.\n", stderr)
                        fflush(stderr)
                    }
                } else {
                    // Raw vector mode
                    fputs("  > Received \(accumulatedData.count) bytes! Starting execution...\n", stderr)
                    fflush(stderr)
                    
                    accumulatedData.withUnsafeBytes { rawPtr in
                        memcpy(zSpineBuffer.contents(), rawPtr.baseAddress!, spineLength)
                    }
                }
                
                if isVerbose {
                    let zSpinePtr = zSpineBuffer.contents().bindMemory(to: Float.self, capacity: Int(dim))
                    fputs("  > zSpineBuffer[0..<10]: \(zSpinePtr[0]), \(zSpinePtr[1]), \(zSpinePtr[2]), \(zSpinePtr[3]), \(zSpinePtr[4]), \(zSpinePtr[5]), \(zSpinePtr[6]), \(zSpinePtr[7]), \(zSpinePtr[8]), \(zSpinePtr[9])\n", stderr)
                }
                
                for z in zLayers {
                    autoreleasepool {
                        let t1 = CFAbsoluteTimeGetCurrent()
                        if isVerbose { fputs("  > Executing Z=\(z)\n", stderr) }
                        fflush(stderr)
                        
                        let t0 = CFAbsoluteTimeGetCurrent()
                        var layerWeightOffset = 0
                        var layerInfoOffset = 0
                        
                        guard var commandBuffer = commandQueue.makeCommandBuffer() else { return }
                        guard var encoder = commandBuffer.makeComputeCommandEncoder() else { return }
                    

                    func clearBuffer(_ buffer: MTLBuffer, size: Int, encoder currentEncoder: MTLComputeCommandEncoder) {
                        currentEncoder.setComputePipelineState(psoClearBuffer)
                        currentEncoder.setBuffer(buffer, offset: 0, index: 0)
                        let gridSize = MTLSizeMake((size + 63) / 64, 1, 1)
                        let groupSize = MTLSizeMake(64, 1, 1)
                        currentEncoder.dispatchThreadgroups(gridSize, threadsPerThreadgroup: groupSize)
                    }

                    func dispatchBlocks(_ unsortedBlocks: [SpatialQuantumBlock], inBuffer: MTLBuffer, outBuffer: MTLBuffer, encoder currentEncoder: MTLComputeCommandEncoder) {
                        if unsortedBlocks.isEmpty { return }
                        let targetBlocks = unsortedBlocks.sorted { $0.fileOffset < $1.fileOffset }
                        let blockCount = targetBlocks.count
                        let msg = String(format: "    [Profiler] dispatchBlocks: %d blocks\n", blockCount)
                        if isVerbose { fputs(msg, stderr) }
                        fflush(stderr)
                        
                        let weightBufferSize = blockCount * 64 * 64 * 2
                        let infoBufferSize = blockCount * MemoryLayout<BlockInfo>.stride
                        
                        let destWeightPtr = globalWeightBuffer.contents().advanced(by: layerWeightOffset)
                        let destInfoPtr = globalInfoBuffer.contents().advanced(by: layerInfoOffset)
                        
                        // Address check
                        let dstAddr = UInt(bitPattern: destWeightPtr)
                        let baseAddr = UInt(bitPattern: globalWeightBuffer.contents())
                        
                        let rawFirstFileOffset = targetBlocks.first?.fileOffset ?? 0
                        // Apple Silicon requires 16KB alignment for F_NOCACHE Direct I/O
                        let firstFileOffset = (rawFirstFileOffset / 16384) * 16384
                        
                        let rawLastOffset = targetBlocks.last?.fileOffset ?? 0
                        let rawLength = targetBlocks.isEmpty ? 0 : (rawLastOffset + 8192 - firstFileOffset)
                        // The actual required buffer size is now the bounding box of the blocks, aligned to 16KB
                        let actualWeightBufferSize = (rawLength + 16383) & ~16383
                        
                        if dstAddr + UInt(actualWeightBufferSize) > baseAddr + UInt(maxWeightBufferSize) {
                            fputs("[-] FATAL: Ring Buffer Overflow! offset=\(layerWeightOffset), required=\(actualWeightBufferSize), max=\(maxWeightBufferSize)\n", stderr)
                            fflush(stderr)
                            exit(1)
                        }
                        
                        // 6-Axis Asynchronous Prefetcher: bypass OS cache, read directly into Ring Buffer
                        let startPread = CFAbsoluteTimeGetCurrent()
                        if globalMmapBuffer == nil {
                            AsynchronousPrefetcher.shared.prefetchToRingBuffer(blocks: targetBlocks, ringBufferBase: globalWeightBuffer.contents(), ringBufferOffset: layerWeightOffset, alignedFileOffset: firstFileOffset, alignedLength: actualWeightBufferSize)
                        }
                        let endPread = CFAbsoluteTimeGetCurrent()
                        if endPread - startPread > 0.005 {
                            let msg = String(format: "    [Profiler] Z=\(z) matrix pread took %.3fs for \(actualWeightBufferSize / 1024 / 1024) MB\n", endPread - startPread)
                            if isVerbose { fputs(msg, stderr) }
                            fflush(stderr)
                        }
                        
                        var currentByteOffset: UInt64 = 0
                        var infos = [BlockInfo]()
                        
                        for b in targetBlocks {
                            // Calculate the relative offset based on the file offset to perfectly mirror the SSD layout in VRAM
                            if globalMmapBuffer != nil {
                                if b.fileOffset < maxMmapBufferLength {
                                    infos.append(BlockInfo(rowIdx: UInt32(b.rowIdx), colIdx: UInt32(b.colIdx), blockSize: 64, pad: 0, byteOffset: UInt64(b.fileOffset)))
                                } else {
                                    infos.append(BlockInfo(rowIdx: UInt32(b.rowIdx), colIdx: UInt32(b.colIdx), blockSize: 64, pad: 1, byteOffset: UInt64(b.fileOffset) - maxMmapBufferLength))
                                }
                            } else {
                                currentByteOffset = UInt64(b.fileOffset - firstFileOffset)
                                infos.append(BlockInfo(rowIdx: UInt32(b.rowIdx), colIdx: UInt32(b.colIdx), blockSize: 64, pad: 0, byteOffset: UInt64(layerWeightOffset) + currentByteOffset))
                            }
                        }
                        
                        infos.withUnsafeBytes { rawPtr in
                            if let baseAddress = rawPtr.baseAddress {
                                memcpy(destInfoPtr, baseAddress, infoBufferSize)
                            }
                        }
                        
                        if let mmapBuf = globalMmapBuffer {
                            currentEncoder.setBuffer(mmapBuf, offset: 0, index: 0)
                            if let mmapBuf1 = globalMmapBuffer1 {
                                currentEncoder.setBuffer(mmapBuf1, offset: 0, index: 1)
                            } else {
                                currentEncoder.setBuffer(mmapBuf, offset: 0, index: 1)
                            }
                        } else {
                            currentEncoder.setBuffer(globalWeightBuffer, offset: layerWeightOffset, index: 0)
                            currentEncoder.setBuffer(globalWeightBuffer, offset: layerWeightOffset, index: 1)
                        }
                        currentEncoder.setBuffer(inBuffer, offset: 0, index: 2)
                        currentEncoder.setBuffer(outBuffer, offset: 0, index: 3)
                        currentEncoder.setBuffer(globalInfoBuffer, offset: layerInfoOffset, index: 4)
                        
                        let startGPU = CFAbsoluteTimeGetCurrent()
                        currentEncoder.dispatchThreadgroups(MTLSizeMake(blockCount, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        // We can't measure GPU time here directly without waiting, but we can measure command encoding time
                        
                        let startDispatch = CFAbsoluteTimeGetCurrent()
                        // Align Ring Buffer to 16KB for F_NOCACHE
                        if globalMmapBuffer == nil {
                            layerWeightOffset = (layerWeightOffset + actualWeightBufferSize + 16383) & ~16383
                        }
                        let endDispatch = CFAbsoluteTimeGetCurrent()
                        if endDispatch - startDispatch > 0.05 {
                            fputs("    [Profiler] Z=\(z) dispatchBlocks total time: \(String(format: "%.3f", endDispatch - startDispatch))s\n", stderr); fflush(stderr)
                        }
                        layerInfoOffset = (layerInfoOffset + infoBufferSize + 16383) & ~16383
                        if isVerbose && z == 3 { fputs("    [Profiler] dispatchBlocks finished\n", stderr); fflush(stderr) }
                    }
                    
                    let blocks = runtime.spatialGraph[z] ?? []
                    
                    // 1. Norm 1
                    if let normWeight = jmetaTensors[z]?[0] {
                        let normBuffer = device.makeBuffer(bytes: [UInt8](normWeight), length: normWeight.count, options: .storageModeShared)
                        
                        encoder.setComputePipelineState(psoRmsNorm)
                        encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)
                        encoder.setBuffer(normBuffer, offset: 0, index: 1)
                        encoder.setBuffer(normedSpineBuffer, offset: 0, index: 2)
                        var size: UInt32 = UInt32(dim)
                        encoder.setBytes(&size, length: 4, index: 3)
                        encoder.setThreadgroupMemoryLength(1024 * MemoryLayout<Float>.stride, index: 0)
                        encoder.dispatchThreadgroups(MTLSizeMake(1, 1, 1), threadsPerThreadgroup: MTLSizeMake(1024, 1, 1))
                        
                        encoder.endEncoding()
                        commandBuffer.commit()
                        let startWait = CFAbsoluteTimeGetCurrent()
                        commandBuffer.waitUntilCompleted()
                        let endWait = CFAbsoluteTimeGetCurrent()
                        if endWait - startWait > 0.05 {
                            fputs("    [Profiler] Z=\(z) GPU wait took \(String(format: "%.3f", endWait - startWait))s\n", stderr); fflush(stderr)
                        }
                        
                        if isVerbose && z == 0 {
                            let w1Ptr = normBuffer!.contents().bindMemory(to: Float16.self, capacity: dim)
                            fputs("  > Z=0 normWeight1[0..<5]: \(w1Ptr[0]), \(w1Ptr[1]), \(w1Ptr[2]), \(w1Ptr[3]), \(w1Ptr[4])\n", stderr); fflush(stderr)
                            let n1Ptr = normedSpineBuffer.contents().bindMemory(to: Float.self, capacity: dim)
                            fputs("  > Z=0 normedSpineBuffer AFTER Norm 1 [0..<10]: \(n1Ptr[0]), \(n1Ptr[1]), \(n1Ptr[2]), \(n1Ptr[3]), \(n1Ptr[4])\n", stderr); fflush(stderr)
                        }
                        
                        guard let newCommandBuffer = commandQueue.makeCommandBuffer(),
                              let newEncoder = newCommandBuffer.makeComputeCommandEncoder() else { return }
                        commandBuffer = newCommandBuffer
                        encoder = newEncoder
                    } else {
                        encoder.setComputePipelineState(psoAdd)
                        encoder.setBuffer(normedSpineBuffer, offset: 0, index: 0)
                        encoder.setBuffer(zSpineBuffer, offset: 0, index: 1)
                        var dim32 = UInt32(dim)
                        encoder.setBytes(&dim32, length: 4, index: 2)
                        var amp: Float = 1.0 // Short circuit, no amplification
                        encoder.setBytes(&amp, length: 4, index: 3)
                        encoder.dispatchThreadgroups(MTLSizeMake((dim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        encoder.endEncoding()
                        commandBuffer.commit()
                        commandBuffer.waitUntilCompleted()
                        
                        guard let newCommandBuffer = commandQueue.makeCommandBuffer(),
                              let newEncoder = newCommandBuffer.makeComputeCommandEncoder() else { return }
                        commandBuffer = newCommandBuffer
                        encoder = newEncoder
                    }
                    
                    var activeRows = Set<UInt16>()
                    var amplificationFactor: Float = 1.0
                    
                    if let scout = runtime.scoutWeights[z]?[10] {
                        let zSpinePtr = normedSpineBuffer.contents().bindMemory(to: Float.self, capacity: Int(dim))
                        var zSpineArray = [Float](repeating: 0.0, count: Int(dim))
                        for i in 0..<Int(dim) { zSpineArray[i] = zSpinePtr[i] }
                        
                        if spatialMomentum[Int(z)] == nil {
                            spatialMomentum[Int(z)] = [Float](repeating: 0.0, count: scout.outDim)
                        }
                        let staticMap = staticRouteMap[Int(z)] ?? []
                        
                        let pred = LayerScout.predictWithMomentum(
                            input: zSpineArray, w1: scout.w1, w2: scout.w2, 
                            inDim: scout.inDim, rank: scout.rank, outDim: scout.outDim, 
                            momentum: &spatialMomentum[Int(z)]!, staticMap: staticMap
                        )
                        
                        let numBlockRows = (scout.outDim + 63) / 64
                        var blockRowScores = [Float](repeating: -Float.greatestFiniteMagnitude, count: numBlockRows)
                        var staticRowScores = [Float](repeating: 0.0, count: numBlockRows)
                        
                        for i in 0..<scout.outDim {
                            let blockRow = i / 64
                            if pred[i] > blockRowScores[blockRow] {
                                blockRowScores[blockRow] = pred[i]
                            }
                            if i < staticMap.count && staticMap[i] > staticRowScores[blockRow] {
                                staticRowScores[blockRow] = staticMap[i]
                            }
                        }
                        
                        let sortedDynamicRows = blockRowScores.enumerated().sorted(by: { $0.element > $1.element })
                        let sortedStaticRows = staticRowScores.enumerated().sorted(by: { $0.element > $1.element })
                        
                        // Use ALL blocks (0% sparsity) to ensure model generation is accurate.
                        // We proved that dropping any blocks causes noise cascade in the residual stream.
                        let targetActiveCount = numBlockRows
                        
                        activeRows.removeAll()
                        
                        // Select all blocks
                        for i in 0..<numBlockRows {
                            activeRows.insert(UInt16(i))
                        }
                        
                        // CRITICAL FIX: If we drop neurons that are ALREADY zero due to SiLU sparsity,
                        // the sum of the remaining active neurons is ALREADY mathematically correct!
                        // Amplifying it by 10x or 2x destroys the residual stream.
                        amplificationFactor = 1.0 
                        
                        let msg = "    [Scout] Z=\(z) activeBlockRows: \(activeRows.count) / \(numBlockRows)\n"
                        if isVerbose { fputs(msg, stderr) }
                        fflush(stderr)
                    }
                    let t2 = CFAbsoluteTimeGetCurrent()
                    
                    // 3. Attention
                    let rawMlpGateBlocks = blocks.filter { $0.matrixType == 10 }
                    let rawMlpUpBlocks = blocks.filter { $0.matrixType == 11 }
                    let rawMlpDownBlocks = blocks.filter { $0.matrixType == 12 }
                    
                    let mlpGateBlocks = activeRows.isEmpty ? rawMlpGateBlocks : rawMlpGateBlocks.filter { activeRows.contains($0.rowIdx) }
                    let mlpUpBlocks = activeRows.isEmpty ? rawMlpUpBlocks : rawMlpUpBlocks.filter { activeRows.contains($0.rowIdx) }
                    let mlpDownBlocks = activeRows.isEmpty ? rawMlpDownBlocks : rawMlpDownBlocks.filter { activeRows.contains($0.colIdx) }
                    let qBlocks = blocks.filter { $0.matrixType == 20 }
                    let kBlocks = blocks.filter { $0.matrixType == 21 }
                    let vBlocks = blocks.filter { $0.matrixType == 22 }
                    let oBlocks = blocks.filter { $0.matrixType == 23 }
                    
                    let linearQkvBlocks = blocks.filter { $0.matrixType == 7 }
                    let linearZBlocks = blocks.filter { $0.matrixType == 8 }
                    let linearABlocks = blocks.filter { $0.matrixType == 5 }
                    let linearBBlocks = blocks.filter { $0.matrixType == 6 }
                    let linearOutBlocks = blocks.filter { $0.matrixType == 9 }
                    if isVerbose && z < 4 {
                        let types = Set(blocks.map { $0.matrixType })
                        fputs("  > Z=\(z) ALL MATRIX TYPES: \(Array(types).sorted())\n", stderr)
                        fputs("  > Z=\(z) BLOCK COUNTS: q=\(qBlocks.count), k=\(kBlocks.count), v=\(vBlocks.count), linearQkv=\(linearQkvBlocks.count), linearA=\(linearABlocks.count), linearB=\(linearBBlocks.count), linearOut=\(linearOutBlocks.count)\n", stderr)
                        
                        var btypeCounts: [UInt8: Int] = [:]
                        for b in blocks {
                            let btype = b.matrixType
                            btypeCounts[btype, default: 0] += 1
                        }
                        fputs("  > Z=\(z) MATRIX TYPE COUNTS: \(btypeCounts)\n", stderr)
                        fflush(stderr)
                    }
                    
                    if !qBlocks.isEmpty && !kBlocks.isEmpty && !vBlocks.isEmpty && linearQkvBlocks.isEmpty {
                        encoder.setComputePipelineState(psoZero)
                        var qSize1: UInt32 = 6144
                        encoder.setBuffer(qOutBuffer, offset: 0, index: 0)
                        encoder.setBytes(&qSize1, length: 4, index: 1)
                        encoder.dispatchThreadgroups(MTLSizeMake((6144 + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        encoder.setBuffer(kOutBuffer, offset: 0, index: 0)
                        encoder.dispatchThreadgroups(MTLSizeMake((1024 + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        encoder.setBuffer(vOutBuffer, offset: 0, index: 0)
                        encoder.dispatchThreadgroups(MTLSizeMake((1024 + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        var oSize: UInt32 = UInt32(dim)
                        encoder.setBuffer(downOutBuffer, offset: 0, index: 0)
                        encoder.setBytes(&oSize, length: 4, index: 1)
                        encoder.dispatchThreadgroups(MTLSizeMake((dim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        var qSizeFloat = qBlocks.count * 64 / (dim / 64)
                        var fullQHeads: UInt32 = UInt32(qSizeFloat / 256)
                        if fullQHeads == 0 { fullQHeads = 24 } // fallback
                        var fullKvHeads: UInt32 = 4
                        var fullHeadDim: UInt32 = 256
                        var actualQHeads = fullQHeads
                        
                        if fullQHeads == 48 {
                            actualQHeads = 24
                            clearBuffer(tempQBuffer, size: 12288, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(qBlocks, inBuffer: normedSpineBuffer, outBuffer: tempQBuffer, encoder: encoder)
                            
                            encoder.setComputePipelineState(psoSplitQGate)
                            encoder.setBuffer(tempQBuffer, offset: 0, index: 0)
                            encoder.setBuffer(qOutBuffer, offset: 0, index: 1)
                            encoder.setBuffer(qGateBuffer, offset: 0, index: 2)
                            encoder.setBytes(&actualQHeads, length: 4, index: 3)
                            encoder.setBytes(&fullHeadDim, length: 4, index: 4)
                            encoder.dispatchThreadgroups(MTLSizeMake((Int(actualQHeads) * Int(fullHeadDim) + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        } else {
                            clearBuffer(qOutBuffer, size: 12288, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(qBlocks, inBuffer: normedSpineBuffer, outBuffer: qOutBuffer, encoder: encoder)
                        }
                        
                        clearBuffer(kOutBuffer, size: 1024, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(kBlocks, inBuffer: normedSpineBuffer, outBuffer: kOutBuffer, encoder: encoder)
                        clearBuffer(vOutBuffer, size: 1024, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(vBlocks, inBuffer: normedSpineBuffer, outBuffer: vOutBuffer, encoder: encoder)
                        
                        if let qNormWeight = jmetaTensors[z]?[24] {
                            let qnBuffer = device.makeBuffer(bytes: [UInt8](qNormWeight), length: qNormWeight.count, options: .storageModeShared)
                            encoder.setComputePipelineState(psoQkNorm)
                            encoder.setBuffer(qOutBuffer, offset: 0, index: 0)
                            encoder.setBuffer(qnBuffer, offset: 0, index: 1)
                            encoder.setBytes(&fullHeadDim, length: 4, index: 2)
                            encoder.setThreadgroupMemoryLength(Int(fullHeadDim) * MemoryLayout<Float>.stride, index: 0)
                            encoder.dispatchThreadgroups(MTLSizeMake(Int(actualQHeads), 1, 1), threadsPerThreadgroup: MTLSizeMake(Int(fullHeadDim), 1, 1))
                        }
                        if let kNormWeight = jmetaTensors[z]?[25] {
                            let knBuffer = device.makeBuffer(bytes: [UInt8](kNormWeight), length: kNormWeight.count, options: .storageModeShared)
                            encoder.setComputePipelineState(psoQkNorm)
                            encoder.setBuffer(kOutBuffer, offset: 0, index: 0)
                            encoder.setBuffer(knBuffer, offset: 0, index: 1)
                            encoder.setBytes(&fullHeadDim, length: 4, index: 2)
                            encoder.setThreadgroupMemoryLength(Int(fullHeadDim) * MemoryLayout<Float>.stride, index: 0)
                            encoder.dispatchThreadgroups(MTLSizeMake(Int(fullKvHeads), 1, 1), threadsPerThreadgroup: MTLSizeMake(Int(fullHeadDim), 1, 1))
                        }
                        
                        if isVerbose && z == 3 { fputs("  > About to encode psoRope\n", stderr); fflush(stderr) }

                        
                        encoder.setComputePipelineState(psoRope)
                        encoder.setBuffer(qOutBuffer, offset: 0, index: 0)
                        encoder.setBuffer(kOutBuffer, offset: 0, index: 1)
                        var qSizeRope: UInt32 = actualQHeads
                        var kSizeRope: UInt32 = fullKvHeads
                        var headDimRope: UInt32 = fullHeadDim
                        var posRope: UInt32 = currentPos
                        encoder.setBytes(&qSizeRope, length: 4, index: 2)
                        encoder.setBytes(&kSizeRope, length: 4, index: 3)
                        encoder.setBytes(&headDimRope, length: 4, index: 4)
                        encoder.setBytes(&posRope, length: 4, index: 5)
                        encoder.dispatchThreadgroups(MTLSizeMake(Int(actualQHeads), 1, 1), threadsPerThreadgroup: MTLSizeMake(Int(fullHeadDim)/2, 1, 1))
                        
                        if isVerbose && z == 3 { fputs("  > About to encode psoWriteKVCache\n", stderr); fflush(stderr) }

                        
                        encoder.setComputePipelineState(psoWriteKVCache)
                        encoder.setBuffer(kOutBuffer, offset: 0, index: 0)
                        encoder.setBuffer(vOutBuffer, offset: 0, index: 1)
                        encoder.setBuffer(kvCacheBuffer, offset: 0, index: 2)
                        var layerIdx: UInt32 = UInt32(z)
                        encoder.setBytes(&layerIdx, length: 4, index: 3)
                        var pos: UInt32 = currentPos
                        encoder.setBytes(&pos, length: 4, index: 4)
                        encoder.dispatchThreadgroups(MTLSizeMake((1024 + 63)/64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        if isVerbose && z == 3 { fputs("  > About to encode psoAttention\n", stderr); fflush(stderr) }

                        
                        encoder.setComputePipelineState(psoAttention)
                        encoder.setBuffer(qOutBuffer, offset: 0, index: 0)
                        encoder.setBuffer(kvCacheBuffer, offset: 0, index: 1)
                        encoder.setBuffer(qOutBuffer, offset: 0, index: 2)
                        var seqLen: UInt32 = currentPos + 1
                        var numQHeadsAttn: UInt32 = actualQHeads
                        var numKvHeadsAttn: UInt32 = fullKvHeads
                        encoder.setBytes(&seqLen, length: 4, index: 3)
                        encoder.setBytes(&layerIdx, length: 4, index: 4)
                        encoder.setBytes(&numQHeadsAttn, length: 4, index: 5)
                        encoder.setBytes(&numKvHeadsAttn, length: 4, index: 6)
                        var headDimAttn: UInt32 = fullHeadDim
                        encoder.setBytes(&headDimAttn, length: 4, index: 7)
                        encoder.setThreadgroupMemoryLength(4096 * MemoryLayout<Float>.stride, index: 0)
                        encoder.dispatchThreadgroups(MTLSizeMake(Int(actualQHeads), 1, 1), threadsPerThreadgroup: MTLSizeMake(256, 1, 1))
                        
                        // REMOVED psoSiluMul for Attention
                        
                        if isVerbose && z == 3 { fputs("  > About to encode psoBlockMatMul oBlocks\n", stderr); fflush(stderr) }
                        if isVerbose && z == 3 { fputs("  > About to encode psoBlockMatMul oBlocks\n", stderr); fflush(stderr) }

                        encoder.setComputePipelineState(psoBlockMatMul)
                        dispatchBlocks(oBlocks, inBuffer: qOutBuffer, outBuffer: downOutBuffer, encoder: encoder)
                        
                        encoder.setComputePipelineState(psoAdd)
                        encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)
                        encoder.setBuffer(downOutBuffer, offset: 0, index: 1)
                        var downSize: UInt32 = UInt32(dim)
                        encoder.setBytes(&downSize, length: 4, index: 2)
                        var attAmp: Float = 1.0
                        encoder.setBytes(&attAmp, length: 4, index: 3)
                        encoder.dispatchThreadgroups(MTLSizeMake((dim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                    } else if !linearQkvBlocks.isEmpty {
                        // ----------------------------------------------------
                        // LINEAR ATTENTION (MAMBA/SSM) ROUTE
                        // ----------------------------------------------------
                        
                        // Buffer offsets in linearQkvOutBuffer (total capacity 10240 floats)
                        // qkv: 10240, z: 6144, b: 48, a: 48
                        // Wait, qOutBuffer is 12288 floats, we can just use qOutBuffer, kOutBuffer, vOutBuffer and others!
                        let outQkvBuffer = linearQkvOutBuffer // 10240
                        let outZBuffer = linearCoreAttnOutBuffer // 6144
                        // For a and b, let's just reuse kOutBuffer and vOutBuffer since they are 1024 long each.
                        let outBBuffer = kOutBuffer
                        let outABuffer = vOutBuffer
                        
                        // 1. Zero out buffers
                        encoder.setComputePipelineState(psoZero)
                        var qkvSize: UInt32 = 10240
                        encoder.setBuffer(outQkvBuffer, offset: 0, index: 0)
                        encoder.setBytes(&qkvSize, length: 4, index: 1)
                        encoder.dispatchThreadgroups(MTLSizeMake((10240 + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        var zSize: UInt32 = 6144
                        encoder.setBuffer(outZBuffer, offset: 0, index: 0)
                        encoder.setBytes(&zSize, length: 4, index: 1)
                        encoder.dispatchThreadgroups(MTLSizeMake((6144 + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        var abSize: UInt32 = 48
                        encoder.setBuffer(outBBuffer, offset: 0, index: 0)
                        encoder.setBytes(&abSize, length: 4, index: 1)
                        encoder.dispatchThreadgroups(MTLSizeMake(1, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        encoder.setBuffer(outABuffer, offset: 0, index: 0)
                        encoder.dispatchThreadgroups(MTLSizeMake(1, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        var oSize: UInt32 = UInt32(dim)
                        encoder.setBuffer(downOutBuffer, offset: 0, index: 0)
                        encoder.setBytes(&oSize, length: 4, index: 1)
                        encoder.dispatchThreadgroups(MTLSizeMake((dim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        
                        // 2. Perform MatMuls for projections
                        clearBuffer(outQkvBuffer, size: 10240, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(linearQkvBlocks, inBuffer: normedSpineBuffer, outBuffer: outQkvBuffer, encoder: encoder)
                            
                            if isVerbose && z == 0 {
                                encoder.endEncoding()
                                commandBuffer.commit()
                                commandBuffer.waitUntilCompleted()
                                let qkvPtr = outQkvBuffer.contents().bindMemory(to: Float.self, capacity: 10240)
                                let qArr = (0..<5).map { qkvPtr[$0] }
                                fputs("  > Z=0 mixed_qkv AFTER linearQkv SYNC [0..<5]: \(qArr)\n", stderr); fflush(stderr)
                                
                                let firstBlockOffset = Int(linearQkvBlocks.first?.fileOffset ?? 0)
                                let firstAlignedOffset = (firstBlockOffset / 16384) * 16384
                                let relativeOffset = firstBlockOffset - firstAlignedOffset
                                let weightPtr = globalWeightBuffer.contents().advanced(by: layerWeightOffset + relativeOffset).bindMemory(to: UInt16.self, capacity: 5)
                                let wArr = (0..<5).map { weightPtr[$0] }
                                let wArrStr = wArr.map { String(format: "%04x", $0) }.joined(separator: ", ")
                                fputs("  > Z=0 first weights [0..<5] in globalWeightBuffer: [\(wArrStr)]\n", stderr); fflush(stderr)
                                
                                guard let newCommandBuffer = commandQueue.makeCommandBuffer(),
                                      let newEncoder = newCommandBuffer.makeComputeCommandEncoder() else { return }
                                commandBuffer = newCommandBuffer
                                encoder = newEncoder
                            }
                        clearBuffer(outZBuffer, size: 6144, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(linearZBlocks, inBuffer: normedSpineBuffer, outBuffer: outZBuffer, encoder: encoder)
                        clearBuffer(outBBuffer, size: 64, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(linearBBlocks, inBuffer: normedSpineBuffer, outBuffer: outBBuffer, encoder: encoder)
                        clearBuffer(outABuffer, size: 64, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(linearABlocks, inBuffer: normedSpineBuffer, outBuffer: outABuffer, encoder: encoder)
                        
                        // DEBUG QKV BEFORE CONV1D
                        encoder.endEncoding()
                        commandBuffer.commit()
                        commandBuffer.waitUntilCompleted()
                        if isVerbose && z == 0 {
                            let qkvPtr = outQkvBuffer.contents().bindMemory(to: Float.self, capacity: 10240)
                            let qArr = (0..<5).map { qkvPtr[$0] }
                            fputs("  > Z=0 mixed_qkv AFTER SYNC [0..<5]: \(qArr)\n", stderr); fflush(stderr)
                        }
                        guard let newCommandBuffer = commandQueue.makeCommandBuffer(),
                              let newEncoder = newCommandBuffer.makeComputeCommandEncoder() else { return }
                        commandBuffer = newCommandBuffer
                        encoder = newEncoder
                        
                        // 3. Conv1D
                        if let convWeight = jmetaTensors[z]?[2] {
                            let convWBuffer = device.makeBuffer(bytes: [UInt8](convWeight), length: convWeight.count, options: .storageModeShared)
                            encoder.setComputePipelineState(psoLinearConv1d)
                            encoder.setBuffer(outQkvBuffer, offset: 0, index: 0)
                            encoder.setBuffer(ssmConvBuffer, offset: 0, index: 1)
                            encoder.setBuffer(convWBuffer, offset: 0, index: 2)
                            encoder.setBuffer(convWBuffer, offset: 0, index: 3) // Bias not used, sending same buffer
                            var layerIdx: UInt32 = UInt32(z)
                            encoder.setBytes(&layerIdx, length: 4, index: 4)
                            encoder.setBytes(&qkvSize, length: 4, index: 5)
                            var useBias: UInt32 = 0
                            encoder.setBytes(&useBias, length: 4, index: 6)
                            encoder.dispatchThreadgroups(MTLSizeMake((Int(qkvSize) + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                        }
                        
                        // DEBUG QKV AFTER CONV1D
                        encoder.endEncoding()
                        commandBuffer.commit()
                        commandBuffer.waitUntilCompleted()
                        if isVerbose && z == 0 {
                            let qkvPtr = outQkvBuffer.contents().bindMemory(to: Float.self, capacity: 10240)
                            let qArr = (0..<5).map { qkvPtr[$0] }
                            fputs("  > Z=0 mixed_qkv AFTER conv1d [0..<5]: \(qArr)\n", stderr); fflush(stderr)
                        }
                        guard let newCommandBuffer2 = commandQueue.makeCommandBuffer(),
                              let newEncoder2 = newCommandBuffer2.makeComputeCommandEncoder() else { return }
                        commandBuffer = newCommandBuffer2
                        encoder = newEncoder2
                        
                        // 4. L2Norm on Q and K
                        // DEBUG CHECK
                        encoder.endEncoding()
                        commandBuffer.commit()
                        commandBuffer.waitUntilCompleted()
                        let qkvPtr = outQkvBuffer.contents().assumingMemoryBound(to: Float.self)
                        var hasNan = false
                        for i in 0..<Int(qkvSize) { if qkvPtr[i].isNaN { hasNan = true; break } }
                        if hasNan { fputs("    [Debug] outQkvBuffer became NaN at layer \(z)!\n", stderr); fflush(stderr) }
                        guard let newCommandBuffer = commandQueue.makeCommandBuffer(),
                              let newEncoder = newCommandBuffer.makeComputeCommandEncoder() else { return }
                        commandBuffer = newCommandBuffer
                        encoder = newEncoder
                        
                        encoder.setComputePipelineState(psoLinearL2Norm)
                        encoder.setBuffer(outQkvBuffer, offset: 0, index: 0)
                        let numQHeadsLinear: UInt32 = 16
                        let headKDim: UInt32 = 128
                        var totalKDim: UInt32 = numQHeadsLinear * headKDim
                        encoder.setBytes(&totalKDim, length: 4, index: 1)
                        encoder.dispatchThreadgroups(MTLSizeMake(Int(numQHeadsLinear), 1, 1), threadsPerThreadgroup: MTLSizeMake(1, 1, 1))
                        
                        // 5. Recurrent Step
                        if let aLogWeight = jmetaTensors[z]?[3], let dtBiasWeight = jmetaTensors[z]?[4] {
                            if isVerbose && z == 0 {
                                let dtPtr = dtBiasWeight.withUnsafeBytes { $0.bindMemory(to: Float16.self).baseAddress! }
                                let alogPtr = aLogWeight.withUnsafeBytes { $0.bindMemory(to: Float16.self).baseAddress! }
                                let dtArr = (0..<5).map { Float(dtPtr[$0]) }
                                let alogArr = (0..<5).map { Float(alogPtr[$0]) }
                                fputs("  > Z=0 dt_bias [0..<5]: \(dtArr[0]), \(dtArr[1]), \(dtArr[2]), \(dtArr[3]), \(dtArr[4])\n", stderr)
                                fputs("  > Z=0 A_log [0..<5]: \(alogArr[0]), \(alogArr[1]), \(alogArr[2]), \(alogArr[3]), \(alogArr[4])\n", stderr)
                                fflush(stderr)
                            }
                            let aLogBuffer = device.makeBuffer(bytes: [UInt8](aLogWeight), length: aLogWeight.count, options: .storageModeShared)
                            let dtBiasBuffer = device.makeBuffer(bytes: [UInt8](dtBiasWeight), length: dtBiasWeight.count, options: .storageModeShared)
                            
                            encoder.setComputePipelineState(psoLinearRecurrent)
                            encoder.setBuffer(outQkvBuffer, offset: 0, index: 0)
                            encoder.setBuffer(outBBuffer, offset: 0, index: 1)
                            encoder.setBuffer(outABuffer, offset: 0, index: 2)
                            encoder.setBuffer(dtBiasBuffer, offset: 0, index: 3)
                            encoder.setBuffer(aLogBuffer, offset: 0, index: 4)
                            encoder.setBuffer(ssmRecurrentBuffer, offset: 0, index: 5)
                            
                            // Using gateOutBuffer for core_attn_out to avoid race conditions
                            encoder.setBuffer(gateOutBuffer, offset: 0, index: 6)
                            var layerIdx: UInt32 = UInt32(z)
                            encoder.setBytes(&layerIdx, length: 4, index: 7)
                            var numVHeads: UInt32 = 48
                            var realNumKHeads: UInt32 = 16
                            var headKDim2: UInt32 = 128
                            var headVDim2: UInt32 = 128
                            encoder.setBytes(&numVHeads, length: 4, index: 8)
                            encoder.setBytes(&realNumKHeads, length: 4, index: 9)
                            encoder.setBytes(&headKDim2, length: 4, index: 10)
                            encoder.setBytes(&headVDim2, length: 4, index: 11)
                            encoder.dispatchThreadgroups(MTLSizeMake(48, 1, 1), threadsPerThreadgroup: MTLSizeMake(128, 1, 1))
                            
                            encoder.endEncoding()
                            commandBuffer.commit()
                            commandBuffer.waitUntilCompleted()
                            
                            if isVerbose && z == 0 {
                                let coreAttnPtr = gateOutBuffer.contents().bindMemory(to: Float.self, capacity: 6144)
                                let coreAttnArr = (0..<10).map { coreAttnPtr[$0] }
                                fputs("  > Z=0 core_attn_out [0..<10]: \(coreAttnArr[0]), \(coreAttnArr[1]), \(coreAttnArr[2]), \(coreAttnArr[3]), \(coreAttnArr[4])\n", stderr); fflush(stderr)
                            }
                            
                            guard let newCommandBuffer = commandQueue.makeCommandBuffer(),
                                  let newEncoder = newCommandBuffer.makeComputeCommandEncoder() else { return }
                            commandBuffer = newCommandBuffer
                            encoder = newEncoder
                        }
                        
                        // 6. RMSNorm Gated
                        if let normWeight2 = jmetaTensors[z]?[15] {
                            let nW2Buffer = device.makeBuffer(bytes: [UInt8](normWeight2), length: normWeight2.count, options: .storageModeShared)
                            encoder.setComputePipelineState(psoLinearRMSNormGated)
                            encoder.setBuffer(gateOutBuffer, offset: 0, index: 0) // core_attn_out
                            encoder.setBuffer(outZBuffer, offset: 0, index: 1) // z
                            
                            var headVDim: UInt32 = 128
                            encoder.setBytes(&headVDim, length: 4, index: 2)
                            encoder.setBuffer(nW2Buffer, offset: 0, index: 3)
                            
                            encoder.setThreadgroupMemoryLength(128 * MemoryLayout<Float>.stride, index: 0)
                            encoder.dispatchThreadgroups(MTLSizeMake(48, 1, 1), threadsPerThreadgroup: MTLSizeMake(128, 1, 1))
                        } else {
                            encoder.setComputePipelineState(psoLinearGatedOnly)
                            encoder.setBuffer(gateOutBuffer, offset: 0, index: 0) // core_attn_out
                            encoder.setBuffer(outZBuffer, offset: 0, index: 1) // z
                            
                            var headVDim: UInt32 = 128
                            encoder.setBytes(&headVDim, length: 4, index: 2)
                            
                            encoder.dispatchThreadgroups(MTLSizeMake(48, 1, 1), threadsPerThreadgroup: MTLSizeMake(128, 1, 1))
                        }
                        
                        encoder.endEncoding()
                        commandBuffer.commit()
                        commandBuffer.waitUntilCompleted()
                        
                        if isVerbose && z == 0 {
                            let gatePtr = gateOutBuffer.contents().bindMemory(to: Float.self, capacity: 6144)
                            let gateArr = (0..<5).map { gatePtr[$0] }
                            fputs("  > Z=0 gateOutBuffer AFTER RMSNorm Gated [0..<10]: \(gateArr[0]), \(gateArr[1]), \(gateArr[2]), \(gateArr[3]), \(gateArr[4])\n", stderr); fflush(stderr)
                            
                            let aPtr = outABuffer.contents().bindMemory(to: Float.self, capacity: 64)
                            let aArr = (0..<5).map { aPtr[$0] }
                            fputs("  > Z=0 outABuffer [0..<5]: \(aArr[0]), \(aArr[1]), \(aArr[2]), \(aArr[3]), \(aArr[4])\n", stderr); fflush(stderr)
                            
                            let qkvPtr = outQkvBuffer.contents().bindMemory(to: Float.self, capacity: 10240)
                            let qArr = (0..<64).map { qkvPtr[6144 + 2048 + $0] }
                            let kArr = (0..<64).map { qkvPtr[6144 + $0] }
                            fputs("  > Z=0 Q [0..<64]: \(qArr)\n", stderr); fflush(stderr)
                            fputs("  > Z=0 K [0..<64]: \(kArr)\n", stderr); fflush(stderr)
                            
                            let qkvArr = (0..<5).map { qkvPtr[$0] }
                            fputs("  > Z=0 outQkvBuffer [0..<5]: \(qkvArr[0]), \(qkvArr[1]), \(qkvArr[2]), \(qkvArr[3]), \(qkvArr[4])\n", stderr); fflush(stderr)
                            
                            let bPtr = outBBuffer.contents().bindMemory(to: Float.self, capacity: 64)
                            let bArr = (0..<5).map { bPtr[$0] }
                            fputs("  > Z=0 outBBuffer [0..<5]: \(bArr[0]), \(bArr[1]), \(bArr[2]), \(bArr[3]), \(bArr[4])\n", stderr); fflush(stderr)
                        }
                        
                        guard let newCommandBuffer2 = commandQueue.makeCommandBuffer(),
                              let newEncoder2 = newCommandBuffer2.makeComputeCommandEncoder() else { return }
                        commandBuffer = newCommandBuffer2
                        encoder = newEncoder2
                        
                        // 7. Out Proj
                        clearBuffer(downOutBuffer, size: dim, encoder: encoder)
                            encoder.setComputePipelineState(psoBlockMatMul)
                            dispatchBlocks(linearOutBlocks, inBuffer: gateOutBuffer, outBuffer: downOutBuffer, encoder: encoder)
                        
                        // 8. Add to Spine
                        encoder.setComputePipelineState(psoAdd)
                        encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)
                        encoder.setBuffer(downOutBuffer, offset: 0, index: 1)
                        var downSize: UInt32 = UInt32(dim)
                        encoder.setBytes(&downSize, length: 4, index: 2)
                        var mlpAmp = amplificationFactor
                        encoder.setBytes(&mlpAmp, length: 4, index: 3)
                        encoder.dispatchThreadgroups(MTLSizeMake((dim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                    }
                    

                    if let normWeight2 = jmetaTensors[z]?[1] {
                        let normBuffer2 = device.makeBuffer(bytes: [UInt8](normWeight2), length: normWeight2.count, options: .storageModeShared)
                        
                        encoder.setComputePipelineState(psoRmsNorm)
                        encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)
                        encoder.setBuffer(normBuffer2, offset: 0, index: 1)
                        encoder.setBuffer(normedSpineBuffer, offset: 0, index: 2)
                        var size: UInt32 = UInt32(dim)
                        encoder.setBytes(&size, length: 4, index: 3)
                        encoder.setThreadgroupMemoryLength(1024 * MemoryLayout<Float>.stride, index: 0)
                        encoder.dispatchThreadgroups(MTLSizeMake(1, 1, 1), threadsPerThreadgroup: MTLSizeMake(1024, 1, 1))
                        
                        if isVerbose && z == 0 {
                            let wPtr = normBuffer2!.contents().bindMemory(to: Float16.self, capacity: dim)
                            fputs("  > Z=0 normWeight2[0..<5]: \(wPtr[0]), \(wPtr[1]), \(wPtr[2]), \(wPtr[3]), \(wPtr[4])\n", stderr); fflush(stderr)
                        }
                    } else {
                        if isVerbose {
                            fputs("  > Z=\(z) WARNING: normWeight2 (jmetaTensors[z]?[1]) is MISSING!\n", stderr); fflush(stderr)
                        }
                    }
                    
                    encoder.endEncoding()
                    commandBuffer.commit()
                    commandBuffer.waitUntilCompleted()
                    
                    // --- DYNAMIC ACTIVATION MASKING (PUZZLE PIECE FILTERING) ---
                    // We now use the ultra-fast CPU Scout Predictor which has already filtered the blocks!
                    // mlpGateBlocks, mlpUpBlocks, mlpDownBlocks contain only the active puzzle pieces!
                    
                    guard let commandBuffer3 = commandQueue.makeCommandBuffer(),
                          let encoder3 = commandBuffer3.makeComputeCommandEncoder() else { return }
                    
                    var intDimSize = UInt32(intDim)
                    encoder3.setComputePipelineState(psoZero)
                    encoder3.setBuffer(gateOutBuffer, offset: 0, index: 0)
                    encoder3.setBytes(&intDimSize, length: 4, index: 1)
                    encoder3.dispatchThreadgroups(MTLSizeMake((intDim + 1023) / 1024, 1, 1), threadsPerThreadgroup: MTLSizeMake(1024, 1, 1))

                    encoder3.setComputePipelineState(psoBlockMatMul)
                    dispatchBlocks(mlpGateBlocks, inBuffer: normedSpineBuffer, outBuffer: gateOutBuffer, encoder: encoder3)
                    
                    encoder3.endEncoding()
                    commandBuffer3.commit()
                    commandBuffer3.waitUntilCompleted()
                    
                    guard let commandBuffer2 = commandQueue.makeCommandBuffer(),
                          let encoder2 = commandBuffer2.makeComputeCommandEncoder() else { return }
                    
                    var intDimSize2 = UInt32(intDim)
                    encoder2.setComputePipelineState(psoZero)
                    encoder2.setBuffer(upOutBuffer, offset: 0, index: 0)
                    encoder2.setBytes(&intDimSize2, length: 4, index: 1)
                    encoder2.dispatchThreadgroups(MTLSizeMake((intDim + 1023) / 1024, 1, 1), threadsPerThreadgroup: MTLSizeMake(1024, 1, 1))

                    clearBuffer(upOutBuffer, size: 17408, encoder: encoder2)
                        encoder2.setComputePipelineState(psoBlockMatMul)
                        dispatchBlocks(mlpUpBlocks, inBuffer: normedSpineBuffer, outBuffer: upOutBuffer, encoder: encoder2)
                    
                    encoder2.setComputePipelineState(psoSwiGLU)
                    encoder2.setBuffer(gateOutBuffer, offset: 0, index: 0)
                    encoder2.setBuffer(upOutBuffer, offset: 0, index: 1)
                    var gateSize: UInt32 = UInt32(intDim)
                    encoder2.setBytes(&gateSize, length: 4, index: 2)
                    encoder2.dispatchThreadgroups(MTLSizeMake((intDim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                    
                    var dimSize2 = UInt32(dim)
                    encoder2.setComputePipelineState(psoZero)
                    encoder2.setBuffer(downOutBuffer, offset: 0, index: 0)
                    encoder2.setBytes(&dimSize2, length: 4, index: 1)
                    encoder2.dispatchThreadgroups(MTLSizeMake((dim + 1023) / 1024, 1, 1), threadsPerThreadgroup: MTLSizeMake(1024, 1, 1))

                    clearBuffer(downOutBuffer, size: dim, encoder: encoder2)
                        encoder2.setComputePipelineState(psoBlockMatMul)
                        dispatchBlocks(mlpDownBlocks, inBuffer: gateOutBuffer, outBuffer: downOutBuffer, encoder: encoder2)
                    
                    encoder2.setComputePipelineState(psoAdd)
                    encoder2.setBuffer(zSpineBuffer, offset: 0, index: 0)
                    encoder2.setBuffer(downOutBuffer, offset: 0, index: 1)
                    var downSize: UInt32 = UInt32(dim)
                    encoder2.setBytes(&downSize, length: 4, index: 2)
                    var mlpAmp2 = amplificationFactor
                    encoder2.setBytes(&mlpAmp2, length: 4, index: 3)
                    encoder2.dispatchThreadgroups(MTLSizeMake((dim + 63) / 64, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))
                    
                    encoder2.endEncoding()
                    commandBuffer2.commit()
                    commandBuffer2.waitUntilCompleted()
                    let tEnd = CFAbsoluteTimeGetCurrent()
                    if z < 3 {
                        let tStr = String(format: "    [Profiler] Z=\(z) Total Layer Time: %.3fs\n", tEnd - t0)
                        fputs(tStr, stderr)
                        let tStr1 = String(format: "               - Setup & Encoder: %.3fs\n", t1 - t0)
                        fputs(tStr1, stderr)
                        let tStr2 = String(format: "               - Predict & Filters: %.3fs\n", t2 - t1)
                        fputs(tStr2, stderr)
                        let tStr3 = String(format: "               - Dispatch Time: %.3fs\n", tEnd - t2)
                        fputs(tStr3, stderr)
                        fflush(stderr)
                    }
                    if isVerbose {
                        let zSpineData = zSpineBuffer.contents().assumingMemoryBound(to: Float.self)
                        if zSpineData[1].isNaN || zSpineData[0].isNaN {
                            fputs("    [Debug] zSpine became NaN at layer \(z)!\n", stderr)
                        }
                    }
                } // End of autoreleasepool
                    } // End of autoreleasepool
                } // End of for z in zLayers
                
                // Final Norm if available
                if let finalNormWeight = jmetaTensors[254]?[0] {
                    guard let commandBuffer = commandQueue.makeCommandBuffer(),
                          let encoder = commandBuffer.makeComputeCommandEncoder() else { return }
                    let normBuffer = device.makeBuffer(bytes: [UInt8](finalNormWeight), length: finalNormWeight.count, options: .storageModeShared)
                    
                    encoder.setComputePipelineState(psoRmsNorm)
                    encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)
                    encoder.setBuffer(normBuffer, offset: 0, index: 1)
                    encoder.setBuffer(normedSpineBuffer, offset: 0, index: 2)
                    var normSize: UInt32 = UInt32(dim)
                    encoder.setBytes(&normSize, length: 4, index: 3)
                    encoder.setThreadgroupMemoryLength(1024 * MemoryLayout<Float>.stride, index: 0)
                    encoder.dispatchThreadgroups(MTLSizeMake(1, 1, 1), threadsPerThreadgroup: MTLSizeMake(1024, 1, 1))
                    encoder.endEncoding()
                    commandBuffer.commit()
                    commandBuffer.waitUntilCompleted()
                }
            
                // Zero-Copy Pipeline: Run LM Head in Metal
                if let lmHead = lmHeadBuffer, let finalNorm = finalNormBuffer {
                    if isVerbose {
                        let zData = zSpineBuffer.contents().assumingMemoryBound(to: UInt32.self)
                        fputs("    [Debug] zSpine before lm_head: \(String(format: "%08x", zData[0])), \(String(format: "%08x", zData[1]))\n", stderr)
                        
                        let normData = finalNorm.contents().assumingMemoryBound(to: UInt16.self)
                        fputs("    [Debug] norm[0..4]: \(String(format: "%04x", normData[0])), \(String(format: "%04x", normData[1])), \(String(format: "%04x", normData[2]))\n", stderr)
                        
                        let lmData = lmHead.contents().advanced(by: self.lmHeadAlignOffset).assumingMemoryBound(to: UInt16.self)
                        fputs("    [Debug] REAL lm_head[0..4]: \(String(format: "%04x", lmData[0])), \(String(format: "%04x", lmData[1])), \(String(format: "%04x", lmData[2])), \(String(format: "%04x", lmData[3]))\n", stderr)
                    }
                    guard let commandBuffer = commandQueue.makeCommandBuffer(),
                          let encoder = commandBuffer.makeComputeCommandEncoder() else { return }
                    
                    // 1. LM Head Norm (variance)
                    encoder.setComputePipelineState(psoLMHeadNorm)
                    encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)
                    encoder.setBuffer(varianceBuffer, offset: 0, index: 1)
                    var dimSize = UInt32(dim)
                    encoder.setBytes(&dimSize, length: 4, index: 2)
                    
                    let threadsPerThreadgroup = MTLSizeMake(1024, 1, 1)
                    encoder.setThreadgroupMemoryLength(1024 * MemoryLayout<Float>.stride, index: 0)
                    encoder.dispatchThreadgroups(MTLSizeMake(1, 1, 1), threadsPerThreadgroup: threadsPerThreadgroup)
                    
                    // 2. LM Head (matmul)
                    encoder.setComputePipelineState(psoLMHead)
                    encoder.setBuffer(zSpineBuffer, offset: 0, index: 0)
                    encoder.setBuffer(lmHead, offset: self.lmHeadAlignOffset, index: 1)
                    encoder.setBuffer(logitsBuffer, offset: 0, index: 2)
                    encoder.setBuffer(finalNorm, offset: 0, index: 3)
                    encoder.setBytes(&vocabSize, length: 4, index: 4)
                    encoder.setBytes(&dimSize, length: 4, index: 5)
                    encoder.setBuffer(varianceBuffer, offset: 0, index: 6)
                    
                    // Dispatch one thread per vocab word
                    let maxThreads = psoLMHead.maxTotalThreadsPerThreadgroup
                    let groupSize = MTLSizeMake(maxThreads, 1, 1)
                    let gridWidth = (Int(vocabSize) + maxThreads - 1) / maxThreads
                    let gridSize = MTLSizeMake(gridWidth, 1, 1)
                    encoder.dispatchThreadgroups(gridSize, threadsPerThreadgroup: groupSize)
                    
                    encoder.memoryBarrier(scope: .buffers)
                    
                    encoder.endEncoding()
                    commandBuffer.commit()
                    commandBuffer.waitUntilCompleted()
                    
                    // -- LOGITS DEBUG START --
                    let zSpineData = zSpineBuffer.contents().assumingMemoryBound(to: UInt16.self) // half
                    if isVerbose {
                        fputs("    [Debug] zSpine before lm_head: \(String(format: "%04x", zSpineData[0])), \(String(format: "%04x", zSpineData[1]))\n", stderr)
                    }
                    let logitsPtr = self.logitsBuffer.contents().assumingMemoryBound(to: Float.self)
                    struct TokenLogit: Comparable {
                        let id: Int
                        let val: Float
                        static func < (lhs: TokenLogit, rhs: TokenLogit) -> Bool {
                            return lhs.val > rhs.val // Descending
                        }
                    }
                    var topTokens = [TokenLogit]()
                    var hasNan = false
                    for i in 0..<vocabSize {
                        let val = logitsPtr[Int(i)]
                        if val.isNaN && !hasNan {
                            fputs("    [Debug] NaN found at \(i)!\n", stderr)
                            hasNan = true
                        }
                        topTokens.append(TokenLogit(id: Int(i), val: val))
                    }
                    topTokens.sort()
                    fputs("    [Debug] Top 5 logits:\n", stderr)
                    for i in 0..<5 {
                        fputs("      - Token \(topTokens[i].id): \(topTokens[i].val)\n", stderr)
                    }
                    fflush(stderr)
                    // -- LOGITS DEBUG END --
                    
                    if isVerbose {
                        let varData = varianceBuffer.contents().assumingMemoryBound(to: Float.self)
                        let logData = logitsBuffer.contents().assumingMemoryBound(to: Float.self)
                        fputs("    [Debug] variance: \(varData[0]), logits: \(logData[0]), \(logData[1]), \(logData[2]), \(logData[3]), \(logData[4])\n", stderr)
                    }
                    
                    // Output single token ID (4 bytes) from CPU Argmax
                    var bestToken = UInt32(topTokens[0].id)
                    let outputData = Data(bytes: &bestToken, count: 4)
                    FileHandle.standardOutput.write(outputData)
                    fflush(stdout)
                } else {
                    if lmHeadBuffer == nil {
                        fputs("[-] FATAL: lmHeadBuffer is nil! Skipping argmax.\n", stderr)
                    }
                    if finalNormBuffer == nil {
                        fputs("[-] FATAL: finalNormBuffer is nil! Skipping argmax.\n", stderr)
                    }
                    fflush(stderr)
                    // Fallback to sending spine to Python
                    let hasFinalNorm = jmetaTensors[254]?[0] != nil
                    let outPtr = hasFinalNorm ? normedSpineBuffer.contents() : zSpineBuffer.contents()
                    let outputData = Data(bytes: outPtr, count: spineLength)
                    FileHandle.standardOutput.write(outputData)
                    fflush(stdout)
                }
                
                currentPos += 1
            }
}
}
