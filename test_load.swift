import Foundation
import simd

struct VRPosePacket {
    var magic: UInt32
    var padding: UInt32
    var timestamp: Double
    var headTransform: simd_float4x4
    var leftHandTransform: simd_float4x4
    var rightHandTransform: simd_float4x4
    var leftPinch: UInt8
    var rightPinch: UInt8
}

var data = Data(count: 210)
data.withUnsafeBytes { rawBuffer in
    do {
        let _ = rawBuffer.load(as: VRPosePacket.self)
        print("Load succeeded!")
    } catch {
        print("Load failed!")
    }
}
