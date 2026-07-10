import Metal
import Foundation
let data = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789".data(using: .utf8)!
let device = MTLCreateSystemDefaultDevice()!
let ptr = UnsafeMutableRawPointer.allocate(byteCount: 4096, alignment: 16384)
ptr.copyMemory(from: (data as NSData).bytes, byteCount: data.count)
let buffer = device.makeBuffer(bytesNoCopy: ptr, length: 4096, options: .storageModeShared, deallocator: nil)!
let shader = """
#include <metal_stdlib>
using namespace metal;
kernel void test(device const char* in [[buffer(0)]], device char* out [[buffer(1)]], uint id [[thread_position_in_grid]]) {
    out[id] = in[id];
}
"""
let library = try! device.makeLibrary(source: shader, options: nil)
let pso = try! device.makeComputePipelineState(function: library.makeFunction(name: "test")!)
let commandQueue = device.makeCommandQueue()!
let commandBuffer = commandQueue.makeCommandBuffer()!
let encoder = commandBuffer.makeComputeCommandEncoder()!
encoder.setComputePipelineState(pso)
encoder.setBuffer(buffer, offset: 5, index: 0) // Should start at 'f'
let outBuffer = device.makeBuffer(length: 10, options: .storageModeShared)!
encoder.setBuffer(outBuffer, offset: 0, index: 1)
encoder.dispatchThreads(MTLSizeMake(5, 1, 1), threadsPerThreadgroup: MTLSizeMake(5, 1, 1))
encoder.endEncoding()
commandBuffer.commit()
commandBuffer.waitUntilCompleted()
let outStr = String(bytesNoCopy: outBuffer.contents(), length: 5, encoding: .utf8, freeWhenDone: false)
print("Output:", outStr ?? "nil")
