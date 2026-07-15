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

var pkt = VRPosePacket(magic: 0, padding: 0, timestamp: 0, headTransform: matrix_identity_float4x4, leftHandTransform: matrix_identity_float4x4, rightHandTransform: matrix_identity_float4x4, leftPinch: 0, rightPinch: 0)

withUnsafePointer(to: &pkt) { ptr in
    let base = UnsafeRawPointer(ptr)
    print("magic:", UnsafeRawPointer(withUnsafePointer(to: &pkt.magic) { $0 }) - base)
    print("padding:", UnsafeRawPointer(withUnsafePointer(to: &pkt.padding) { $0 }) - base)
    print("timestamp:", UnsafeRawPointer(withUnsafePointer(to: &pkt.timestamp) { $0 }) - base)
    print("head:", UnsafeRawPointer(withUnsafePointer(to: &pkt.headTransform) { $0 }) - base)
    print("left:", UnsafeRawPointer(withUnsafePointer(to: &pkt.leftHandTransform) { $0 }) - base)
    print("right:", UnsafeRawPointer(withUnsafePointer(to: &pkt.rightHandTransform) { $0 }) - base)
    print("leftPinch:", UnsafeRawPointer(withUnsafePointer(to: &pkt.leftPinch) { $0 }) - base)
    print("rightPinch:", UnsafeRawPointer(withUnsafePointer(to: &pkt.rightPinch) { $0 }) - base)
}
