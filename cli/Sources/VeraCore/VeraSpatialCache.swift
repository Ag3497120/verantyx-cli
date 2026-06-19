import Foundation
import Metal

public class VeraSpatialCache {
    private let device: MTLDevice
    
    // Z-Depth -> Array of X-Axis buffers (KV Cache)
    public private(set) var xCacheKeys: [UInt8: MTLBuffer] = [:]
    public private(set) var xCacheValues: [UInt8: MTLBuffer] = [:]
    public private(set) var sequenceLengths: [UInt8: Int] = [:]
    
    public let maxContextLength: Int = 4096 // Maximum supported tokens
    
    public init(device: MTLDevice) {
        self.device = device
    }
    
    public func ensureAllocated(zDepth: UInt8, dim: Int) {
        // Allocate only if not already present
        // Size: maxContextLength * dim * 4 bytes (Float32) 
        // Wait, the attention shader currently uses Float32 for KV Cache! Let's ensure it's Float32 for precision.
        let length = maxContextLength * dim * MemoryLayout<Float>.size
        
        if xCacheKeys[zDepth] == nil {
            xCacheKeys[zDepth] = device.makeBuffer(length: length, options: .storageModeShared)
            xCacheValues[zDepth] = device.makeBuffer(length: length, options: .storageModeShared)
            sequenceLengths[zDepth] = 0
            
            fputs("      [KV-Cache] Allocated X-Axis context memory at Z=\(zDepth) (\(length*2) bytes for max \(maxContextLength) tokens)\n", stderr); fflush(stderr)
        }
    }
    
    public func incrementSequenceLength(zDepth: UInt8) {
        if let current = sequenceLengths[zDepth] {
            if current < maxContextLength {
                sequenceLengths[zDepth] = current + 1
            }
        }
    }
}
