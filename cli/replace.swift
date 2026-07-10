struct DoubleBufferHeader {
    var latestReadyIndex: UInt32
    var padding: (UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32, UInt32)
}

let mapSize = MemoryLayout<DoubleBufferHeader>.size + (Int(MemoryLayout<SharedFrame>.size) + 4096 * 4096 * 4) * 2 + 264 + 1024

let fd = open("/Users/motonishikoudai/Verantyx_VR_Drive/SteamVR_Prefix/drive_c/vr_shared_frame.dat", O_RDWR)
if fd < 0 {
    print("Failed to open C:\\vr_shared_frame.dat")
    exit(1)
}

let mapPtr = mmap(nil, mapSize, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0)
if mapPtr == MAP_FAILED {
    print("mmap failed")
    exit(1)
}

let basePtr = mapPtr! + MemoryLayout<DoubleBufferHeader>.size
let frameBlockSize = Int(MemoryLayout<SharedFrame>.size) + 4096 * 4096 * 4

let headers: [UnsafeMutablePointer<SharedFrame>] = [
    basePtr.bindMemory(to: SharedFrame.self, capacity: 1),
    (basePtr + frameBlockSize).bindMemory(to: SharedFrame.self, capacity: 1)
]

let pixelDatas: [UnsafeMutableRawPointer] = [
    basePtr + MemoryLayout<SharedFrame>.size,
    (basePtr + frameBlockSize) + MemoryLayout<SharedFrame>.size
]

let handsMapPtr = basePtr + (frameBlockSize * 2)
let dbHeaderPtr = mapPtr!.bindMemory(to: DoubleBufferHeader.self, capacity: 1)

var lastSeq: UInt32 = 0
var pixelBuffer: CVPixelBuffer?
var framesEncoded = 0
var currentFrameSequence: UInt32 = 0
var currentWidth = 0
var currentHeight = 0

// MARK: - Joy-Con UDP Server
DispatchQueue.global(qos: .userInteractive).async {
    let jcSock = socket(AF_INET, SOCK_DGRAM, 0)
    var opt: Int32 = 1
    setsockopt(jcSock, SOL_SOCKET, SO_REUSEADDR, &opt, socklen_t(MemoryLayout<Int32>.size))
    
    var bindAddr = sockaddr_in()
    bindAddr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    bindAddr.sin_family = sa_family_t(AF_INET)
    bindAddr.sin_port = in_port_t(11002).bigEndian
    bindAddr.sin_addr.s_addr = INADDR_ANY
    
    bind(jcSock, withUnsafePointer(to: &bindAddr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { $0 }
    }, socklen_t(MemoryLayout<sockaddr_in>.size))
    
    var buffer = [UInt8](repeating: 0, count: 2048)
    while true {
        var senderAddr = sockaddr()
        var senderLen = socklen_t(MemoryLayout<sockaddr>.size)
        let bytesRead = recvfrom(jcSock, &buffer, buffer.count, 0, &senderAddr, &senderLen)
        
        var ipStr = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
        let senderAddrIn = withUnsafePointer(to: &senderAddr) {
            $0.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { $0.pointee }
        }
        var sin_addr = senderAddrIn.sin_addr
        inet_ntop(AF_INET, &sin_addr, &ipStr, socklen_t(INET_ADDRSTRLEN))
        let senderIP = String(cString: ipStr)
        
        if senderIP == "127.0.0.1" && bytesRead == MemoryLayout<JoyconPacket>.size {
            buffer.withUnsafeBytes { rawBuffer in
                let jc = rawBuffer.load(as: JoyconPacket.self)
                if jc.magic == UInt32(0x4A4F5943) { // "JOYC"
                    handsMapPtr.advanced(by: 196).storeBytes(of: jc.rightButtons, as: UInt32.self)
                    handsMapPtr.advanced(by: 200).storeBytes(of: leftButtons, as: UInt32.self)
                    handsMapPtr.advanced(by: 204).storeBytes(of: jc.rightStickX, as: Float.self)
                    handsMapPtr.advanced(by: 208).storeBytes(of: jc.rightStickY, as: Float.self)
                    handsMapPtr.advanced(by: 212).storeBytes(of: jc.leftStickX, as: Float.self)
                    handsMapPtr.advanced(by: 216).storeBytes(of: jc.leftStickY, as: Float.self)
                    handsMapPtr.advanced(by: 220).storeBytes(of: jc.rightVelocityX, as: Float.self)
                    handsMapPtr.advanced(by: 224).storeBytes(of: jc.rightVelocityY, as: Float.self)
                    handsMapPtr.advanced(by: 228).storeBytes(of: jc.rightVelocityZ, as: Float.self)
                    handsMapPtr.advanced(by: 232).storeBytes(of: jc.leftVelocityX, as: Float.self)
                    handsMapPtr.advanced(by: 236).storeBytes(of: jc.leftVelocityY, as: Float.self)
                    handsMapPtr.advanced(by: 240).storeBytes(of: jc.leftVelocityZ, as: Float.self)
                }
            }
        }
    }
}

print("Published Bonjour _verantyxvr._udp on port 9999. Waiting for Vision Pro connection (AWDL enabled)...")

struct VRPosePacket {
    var magic: UInt32
    var padding: UInt32
    var timestamp: Double
    var headTransform: (Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float)
    var leftHandTransform: (Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float)
    var rightHandTransform: (Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float, Float)
    var leftPinch: UInt8
    var rightPinch: UInt8
}

// Receive loop using POSIX socket on port 9999
DispatchQueue.global(qos: .userInteractive).async {
    var buffer = [UInt8](repeating: 0, count: 2048)
    while true {
        var senderAddr = sockaddr_storage()
        var senderLen = socklen_t(MemoryLayout<sockaddr_storage>.size)
        
        let bytesRead = withUnsafeMutablePointer(to: &senderAddr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                recvfrom(sock, &buffer, buffer.count, 0, $0, &senderLen)
            }
        }
        
        if bytesRead >= 210 {
            buffer.withUnsafeBytes { rawBuffer in
                guard let baseAddr = rawBuffer.baseAddress else { return }
                var magic: UInt32 = 0
                memcpy(&magic, baseAddr, 4)

                if magic == 0x45534F50 || magic == 0x504F5345 { // "POSE"
                    if Int(Date().timeIntervalSince1970 * 10) % 50 == 0 {
                        print("Received POSE from Vision Pro! size: \(bytesRead)")
                    }
                    
                    let visionTs = baseAddr.load(fromByteOffset: 8, as: Double.self)
                    latestVisionTimestamp = visionTs
                    
                    // Vision Pro payload: magic(4) + pad(4) + ts(8) = 16 bytes offset
                    memcpy(handsMapPtr, baseAddr + 16, 64)       // Head (offset 0)
                    memcpy(handsMapPtr + 64, baseAddr + 80, 64)  // Left (offset 64)
                    memcpy(handsMapPtr + 128, baseAddr + 144, 64)// Right (offset 128)
                    
                    let visionLeftPinch = baseAddr.load(fromByteOffset: 208, as: UInt8.self)
                    let visionRightPinch = baseAddr.load(fromByteOffset: 209, as: UInt8.self)
                    let visionLeftTrigger = baseAddr.load(fromByteOffset: 210, as: UInt8.self)
                    let visionRightTrigger = baseAddr.load(fromByteOffset: 211, as: UInt8.self)
                    
                    handsMapPtr.advanced(by: 192).storeBytes(of: visionLeftPinch, as: UInt8.self)
                    handsMapPtr.advanced(by: 193).storeBytes(of: visionRightPinch, as: UInt8.self)
                    handsMapPtr.advanced(by: 194).storeBytes(of: visionLeftTrigger, as: UInt8.self)
                    handsMapPtr.advanced(by: 195).storeBytes(of: visionRightTrigger, as: UInt8.self)
                    
                    if bytesRead >= 236 {
                        let rightButtons = baseAddr.load(fromByteOffset: 212, as: UInt32.self)
                        let leftButtons = baseAddr.load(fromByteOffset: 216, as: UInt32.self)
                        let rightStickX = baseAddr.load(fromByteOffset: 220, as: Float.self)
                        let rightStickY = baseAddr.load(fromByteOffset: 224, as: Float.self)
                        let leftStickX = baseAddr.load(fromByteOffset: 228, as: Float.self)
                        let leftStickY = baseAddr.load(fromByteOffset: 232, as: Float.self)
                        
                        handsMapPtr.advanced(by: 196).storeBytes(of: rightButtons, as: UInt32.self)
                        handsMapPtr.advanced(by: 200).storeBytes(of: leftButtons, as: UInt32.self)
                        handsMapPtr.advanced(by: 204).storeBytes(of: rightStickX, as: Float.self)
                        handsMapPtr.advanced(by: 208).storeBytes(of: rightStickY, as: Float.self)
                        handsMapPtr.advanced(by: 212).storeBytes(of: leftStickX, as: Float.self)
                        handsMapPtr.advanced(by: 216).storeBytes(of: leftStickY, as: Float.self)
                    }
                    handsMapPtr.advanced(by: 252).storeBytes(of: visionTs, as: Double.self)
                    
                    var ipStr = [CChar](repeating: 0, count: Int(INET6_ADDRSTRLEN))
                    if senderAddr.ss_family == sa_family_t(AF_INET6) {
                        let senderAddrIn6 = withUnsafePointer(to: &senderAddr) {
                            $0.withMemoryRebound(to: sockaddr_in6.self, capacity: 1) { $0.pointee }
                        }
                        var sin6_addr = senderAddrIn6.sin6_addr
                        inet_ntop(AF_INET6, &sin6_addr, &ipStr, socklen_t(INET6_ADDRSTRLEN))
                    } else if senderAddr.ss_family == sa_family_t(AF_INET) {
                        let senderAddrIn = withUnsafePointer(to: &senderAddr) {
                            $0.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { $0.pointee }
                        }
                        var sin_addr = senderAddrIn.sin_addr
                        inet_ntop(AF_INET, &sin_addr, &ipStr, socklen_t(INET_ADDRSTRLEN))
                    }
                    
                    let currentSenderIP = String(cString: ipStr)
                    
                    if targetIP != currentSenderIP && currentSenderIP != "127.0.0.1" && currentSenderIP != "::1" && currentSenderIP != "" {
                        targetIP = currentSenderIP
                        print("Auto-discovered Vision Pro IP: \(targetIP)")
                    }
                    
                    // Store the entire sockaddr_storage to respond exactly to the same address/port
                    targetAddr = senderAddr
                    targetAddrLen = senderLen
                }
            }
        }
    }
}

print("Starting native read loop via mmap...")

var lastReadIndex: UInt32 = 0xFFFFFFFF

while isEncoding {
    autoreleasepool {
        let readyIndex = dbHeaderPtr.pointee.latestReadyIndex
        if readyIndex != lastReadIndex && readyIndex < 2 {
            let headerPtr = headers[Int(readyIndex)]
            let currentSeq = headerPtr.pointee.sequenceNumber
            
            if currentSeq != lastSeq && currentSeq > 0 {
                let width = Int(headerPtr.pointee.width)
                let height = Int(headerPtr.pointee.height)
                
                if width != currentWidth || height != currentHeight {
                    if compressionSession != nil {
                        VTCompressionSessionInvalidate(compressionSession!)
                        compressionSession = nil
                    }
                    pixelBuffer = nil
                    currentWidth = width
                    currentHeight = height
                    print("Resolution changed to \(width)x\(height)")
                }
                
                if compressionSession == nil && width > 0 && height > 0 {
                    print("Initializing VideoToolbox encoder for \(width)x\(height)...")
                    fflush(stdout)
                    setupEncoder(width: Int32(width), height: Int32(height))
                }
                
                if width > 0 && height > 0 {
                    if pixelBuffer == nil {
                        CVPixelBufferCreate(kCFAllocatorDefault, width, height, kCVPixelFormatType_32BGRA, nil, &pixelBuffer)
                    }
                    
                    if let pb = pixelBuffer {
                        CVPixelBufferLockBaseAddress(pb, [])
                        let dst = CVPixelBufferGetBaseAddress(pb)!
                        let bytesPerRow = CVPixelBufferGetBytesPerRow(pb)
                        
                        let pixelPtr = pixelDatas[Int(readyIndex)]
                        var srcBuffer = vImage_Buffer(data: pixelPtr, height: vImagePixelCount(height), width: vImagePixelCount(width), rowBytes: Int(width * 4))
                        var dstBuffer = vImage_Buffer(data: dst, height: vImagePixelCount(height), width: vImagePixelCount(width), rowBytes: bytesPerRow)
                        let map: [UInt8] = [2, 1, 0, 3] // Swap R (0) and B (2) -> BGRA
                        vImagePermuteChannels_ARGB8888(&srcBuffer, &dstBuffer, map, vImage_Flags(kvImageNoFlags))
                        
                        CVPixelBufferUnlockBaseAddress(pb, [])
                        
                        let presentationTime = CMTime(value: CMTimeValue(framesEncoded), timescale: 90)
                        currentFrameSequence = currentSeq
                        let currentVisionTimestamp = headerPtr.pointee.visionTimestamp
                        
                        let refConPtr = UnsafeMutablePointer<FrameContext>.allocate(capacity: 1)
                        refConPtr.initialize(to: FrameContext(sequence: currentSeq, visionTimestamp: currentVisionTimestamp))
                        
                        let status = VTCompressionSessionEncodeFrame(compressionSession!,
                                                                     imageBuffer: pb,
                                                                     presentationTimeStamp: presentationTime,
                                                                     duration: CMTime.invalid,
                                                                     frameProperties: nil,
                                                                     sourceFrameRefcon: UnsafeMutableRawPointer(refConPtr),
                                                                     infoFlagsOut: nil)
                        
                        if status != noErr {
                            print("VTCompressionSessionEncodeFrame failed: \(status)")
                            refConPtr.deinitialize(count: 1)
                            refConPtr.deallocate()
                        }
                        
                        framesEncoded += 1
                    }
                }
                lastSeq = currentSeq
            }
            lastReadIndex = readyIndex
        } else {
            usleep(1000) // 1ms sleep to prevent 100% CPU usage
        }
    }
}
