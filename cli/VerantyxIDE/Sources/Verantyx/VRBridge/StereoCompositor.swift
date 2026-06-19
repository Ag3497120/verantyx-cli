import Foundation
import Metal
import VideoToolbox
import CoreVideo
import Darwin

/// Apple Silicon UMA (Unified Memory Architecture) の極限を引き出すゼロコピーパイプライン。
/// GPU (Metal) が IOSurface に直接映像を合成し、そのままポインタ渡しで Media Engine (VideoToolbox) がエンコードを行う。
class StereoCompositor {
    private let device: MTLDevice
    private let commandQueue: MTLCommandQueue
    private var computePipelineState: MTLComputePipelineState!
    
    // ゼロコピーパイプラインの心臓部
    private var textureCache: CVMetalTextureCache?
    private var pixelBufferPool: CVPixelBufferPool?
    private var compressionSession: VTCompressionSession?
    
    // --- Phase 9: VirtioFS DAX mmap ---
    private var sharedMemoryPointer: UnsafeMutableRawPointer?
    private var sharedMemorySize: Int = 0
    private var sharedMemoryFD: Int32 = -1
    
    // --- Phase 13: Network Packetization ---
    public var networkCompositor: NetworkCompositor?
    
    private let outputWidth: Int = 3840  // SBS: 1920x1080 * 2
    private let outputHeight: Int = 1080
    
    init?() {
        guard let device = MTLCreateSystemDefaultDevice(),
              let commandQueue = device.makeCommandQueue() else {
            print("[StereoCompositor] Failed to initialize Metal device.")
            return nil
        }
        self.device = device
        self.commandQueue = commandQueue
        
        setupMetal()
        setupTextureCache()
        setupPixelBufferPool()
        setupVideoToolbox()
        setupVirtioFSSharedMemory()
    }
    
    deinit {
        if let ptr = sharedMemoryPointer {
            munmap(ptr, sharedMemorySize)
        }
        if sharedMemoryFD != -1 {
            close(sharedMemoryFD)
        }
    }
    
    private func setupMetal() {
        guard let library = device.makeDefaultLibrary(),
              let function = library.makeFunction(name: "stereo_compose_sbs") else {
            print("[StereoCompositor] Failed to load Metal function stereo_compose_sbs.")
            return
        }
        do {
            computePipelineState = try device.makeComputePipelineState(function: function)
        } catch {
            print("[StereoCompositor] Failed to create compute pipeline state: \(error)")
        }
    }
    
    private func setupTextureCache() {
        let status = CVMetalTextureCacheCreate(kCFAllocatorDefault, nil, device, nil, &textureCache)
        if status != kCVReturnSuccess {
            print("[StereoCompositor] Failed to create CVMetalTextureCache: \(status)")
        }
    }
    
    private func setupPixelBufferPool() {
        // IOSurfaceプロパティを必須とし、MetalとVideoToolboxの両方からゼロコピーアクセス可能にする
        let ioSurfaceProperties: [String: Any] = [:]
        let pixelBufferAttributes: [String: Any] = [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_64RGBAHalf, // Metalコンピュート結果に適合
            kCVPixelBufferWidthKey as String: outputWidth,
            kCVPixelBufferHeightKey as String: outputHeight,
            kCVPixelBufferIOSurfacePropertiesKey as String: ioSurfaceProperties
        ]
        
        let status = CVPixelBufferPoolCreate(
            kCFAllocatorDefault,
            nil,
            pixelBufferAttributes as CFDictionary,
            &pixelBufferPool
        )
        
        if status != kCVReturnSuccess {
            print("[StereoCompositor] Failed to create CVPixelBufferPool: \(status)")
        }
    }
    
    private func setupVideoToolbox() {
        var session: VTCompressionSession?
        
        let status = VTCompressionSessionCreate(
            allocator: kCFAllocatorDefault,
            width: Int32(outputWidth),
            height: Int32(outputHeight),
            codecType: kCMVideoCodecType_HEVC,
            encoderSpecification: nil,
            imageBufferAttributes: nil,
            compressedDataAllocator: nil,
            outputCallback: { outputCallbackRefCon, sourceFrameRefCon, status, infoFlags, sampleBuffer in
                // ゼロコピーエンコードの非同期完了コールバック
                guard status == noErr, let sampleBuffer = sampleBuffer, let refCon = outputCallbackRefCon else {
                    print("[StereoCompositor] VT Encoding Error: \(status)")
                    return
                }
                
                let compositor = Unmanaged<StereoCompositor>.fromOpaque(refCon).takeUnretainedValue()
                compositor.extractAndSendNALUnits(from: sampleBuffer)
            },
            refcon: Unmanaged.passUnretained(self).toOpaque(),
            compressionSessionOut: &session
        )
        
        guard status == noErr, let session = session else {
            print("[StereoCompositor] Failed to create VTCompressionSession: \(status)")
            return
        }
        
        // VRストリーミング向けのリアルタイム・超低遅延設定
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_RealTime, value: kCFBooleanTrue)
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_ProfileLevel, value: kVTProfileLevel_HEVC_Main_AutoLevel)
        // 1フレームごとに即時出力 (遅延最小化)
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_MaxKeyFrameInterval, value: 1 as CFNumber)
        
        VTCompressionSessionPrepareToEncodeFrames(session)
        self.compressionSession = session
    }
    
    // --- Phase 9: VirtioFS DAX mmap ---
    private func setupVirtioFSSharedMemory() {
        let filePath = "/Users/motonishikoudai/verantyx-cli/cli/VerantyxIDE/Sources/Verantyx/VRBridge/GuestOS/vr_framebuffer.bin"
        
        // ファイルが存在しない場合は作成してサイズを確保
        let bytesPerPixel = 4
        self.sharedMemorySize = outputWidth * outputHeight * bytesPerPixel + 1024 // 1024 for header struct (frameId, etc.)
        
        let fm = FileManager.default
        if !fm.fileExists(atPath: filePath) {
            fm.createFile(atPath: filePath, contents: nil, attributes: nil)
            let fd = open(filePath, O_RDWR)
            if fd != -1 {
                ftruncate(fd, off_t(sharedMemorySize))
                close(fd)
            }
        }
        
        self.sharedMemoryFD = open(filePath, O_RDWR)
        guard self.sharedMemoryFD != -1 else {
            print("[StereoCompositor] Failed to open VirtioFS dummy file.")
            return
        }
        
        self.sharedMemoryPointer = mmap(nil, sharedMemorySize, PROT_READ | PROT_WRITE, MAP_SHARED, self.sharedMemoryFD, 0)
        
        if self.sharedMemoryPointer == MAP_FAILED {
            print("[StereoCompositor] mmap failed for VirtioFS Dummy file.")
            self.sharedMemoryPointer = nil
        } else {
            print("[StereoCompositor] Successfully mmap-ed VirtioFS Framebuffer for DAX Zero-Copy!")
        }
    }
    
    // --- Phase 13: H.264/HEVC NAL Unit Packetization ---
    private func extractAndSendNALUnits(from sampleBuffer: CMSampleBuffer) {
        guard let dataBuffer = CMSampleBufferGetDataBuffer(sampleBuffer) else { return }
        
        var lengthAtOffset: Int = 0
        var totalLength: Int = 0
        var dataPointer: UnsafeMutablePointer<Int8>?
        
        if CMBlockBufferGetDataPointer(dataBuffer, atOffset: 0, lengthAtOffsetOut: &lengthAtOffset, totalLengthOut: &totalLength, dataPointerOut: &dataPointer) == noErr {
            if let ptr = dataPointer, totalLength > 0 {
                // CMBlockBuffer には AVCC/HVCC フォーマット（先頭4バイトがサイズ）でNALユニットが格納されている
                // これをそのまま NetworkCompositor に渡し、向こうでUDPのMTUサイズに断片化して送信する
                let nalData = Data(bytes: ptr, count: totalLength)
                
                // P2P通信へ流し込む
                // (frameId 等のタイムスタンプは実際のストリームに合わせて管理)
                networkCompositor?.sendEncodedVideoFrame(nalUnitData: nalData, frameId: 0)
            }
        }
        
        // （初回フレーム等でパラメータセット SPS/PPS/VPS が必要な場合は CMVideoFormatDescription から抽出して送信するロジックが追加されます）
    }
    
    /// VirtioFS (Windows) 側から書き込まれたメモリを直接 CVPixelBuffer としてラップし、即座にエンコードする
    func processVirtioFSFrame(presentationTimestamp: CMTime) {
        guard let sharedPtr = self.sharedMemoryPointer,
              let vtSession = self.compressionSession else { return }
        
        // 最初の1024バイトはヘッダー（frameId, isReady等）と仮定し、ピクセルデータはその次から
        let pixelDataPtr = sharedPtr.advanced(by: 1024)
        
        var pixelBufferOut: CVPixelBuffer?
        let status = CVPixelBufferCreateWithBytes(
            kCFAllocatorDefault,
            outputWidth,
            outputHeight,
            kCVPixelFormatType_32BGRA, // Windowsからのピクセルフォーマットに合わせて調整
            pixelDataPtr,
            outputWidth * 4,
            { releaseContext, baseAddress in
                // メモリ管理は mmap に任せるため何もしない
            },
            nil,
            nil,
            &pixelBufferOut
        )
        
        guard status == kCVReturnSuccess, let pixelBuffer = pixelBufferOut else {
            print("[StereoCompositor] Failed to wrap DAX memory into CVPixelBuffer")
            return
        }
        
        // そのまま VideoToolbox へ（一切のコピーなし）
        var flags: VTEncodeInfoFlags = []
        let encodeStatus = VTCompressionSessionEncodeFrame(
            vtSession,
            imageBuffer: pixelBuffer,
            presentationTimeStamp: presentationTimestamp,
            duration: .invalid,
            frameProperties: nil,
            sourceFrameRefcon: nil,
            infoFlagsOut: &flags
        )
        
        if encodeStatus != noErr {
            print("[StereoCompositor] DAX Encode failed: \(encodeStatus)")
        }
    }
    
    /// 左目と右目のバッファを受け取り、UMAゼロコピーで合成からエンコードまで一気通貫で行う
    func processZeroCopyFrame(leftEye: MTLTexture, rightEye: MTLTexture, presentationTimestamp: CMTime) {
        let commandQueue = self.commandQueue
        guard let commandBuffer = commandQueue.makeCommandBuffer(),
              let encoder = commandBuffer.makeComputeCommandEncoder(),
              let textureCache = self.textureCache,
              let pool = self.pixelBufferPool,
              let vtSession = self.compressionSession else {
            return
        }
        
        // 1. IOSurface バックの共有ピクセルバッファを取得
        var pixelBufferOut: CVPixelBuffer?
        let poolStatus = CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, pool, &pixelBufferOut)
        guard poolStatus == kCVReturnSuccess, let pixelBuffer = pixelBufferOut else {
            print("[StereoCompositor] Failed to get pixel buffer from pool.")
            return
        }
        
        // 2. ピクセルバッファを MTLTexture としてマッピング (ゼロコピー)
        var cvTextureOut: CVMetalTexture?
        let cacheStatus = CVMetalTextureCacheCreateTextureFromImage(
            kCFAllocatorDefault,
            textureCache,
            pixelBuffer,
            nil,
            .rgba16Float, // kCVPixelFormatType_64RGBAHalf に対応
            outputWidth,
            outputHeight,
            0,
            &cvTextureOut
        )
        guard cacheStatus == kCVReturnSuccess,
              let cvTexture = cvTextureOut,
              let outputTexture = CVMetalTextureGetTexture(cvTexture) else {
            print("[StereoCompositor] Failed to create CVMetalTexture.")
            return
        }
        
        // 3. GPU (Metal) で合成処理を実行。結果は outputTexture (実態は IOSurface) に書き込まれる
        encoder.setComputePipelineState(computePipelineState)
        encoder.setTexture(leftEye, index: 0)
        encoder.setTexture(rightEye, index: 1)
        encoder.setTexture(outputTexture, index: 2)
        
        let width = computePipelineState.threadExecutionWidth
        let height = computePipelineState.maxTotalThreadsPerThreadgroup / width
        let threadsPerThreadgroup = MTLSizeMake(width, height, 1)
        let threadsPerGrid = MTLSizeMake(outputTexture.width, outputTexture.height, 1)
        
        encoder.dispatchThreads(threadsPerGrid, threadsPerThreadgroup: threadsPerThreadgroup)
        encoder.endEncoding()
        
        // 4. GPU の書き込み完了を検知して Media Engine に投げる
        commandBuffer.addCompletedHandler { _ in
            // Metalの処理が完了したので、これ以降は IOSurface の内容が確定している。
            // ピクセルバッファのポインタだけを Media Engine に渡してゼロコピーエンコード開始！
            
            var flags: VTEncodeInfoFlags = []
            let encodeStatus = VTCompressionSessionEncodeFrame(
                vtSession,
                imageBuffer: pixelBuffer,
                presentationTimeStamp: presentationTimestamp,
                duration: .invalid,
                frameProperties: nil,
                sourceFrameRefcon: nil,
                infoFlagsOut: &flags
            )
            
            if encodeStatus != noErr {
                print("[StereoCompositor] Failed to encode frame: \(encodeStatus)")
            }
        }
        
        commandBuffer.commit()
    }
}
