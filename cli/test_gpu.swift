import Metal
import Foundation
let fd = open("test_gpu.bin", O_RDWR | O_CREAT, 0o666)
ftruncate(fd, 32768)
let ptr = mmap(nil, 32768, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0)
let bytePtr = ptr!.bindMemory(to: UInt8.self, capacity: 32768)
for i in 0..<32768 { bytePtr[i] = UInt8(i % 256) }
let unaligned = ptr!.advanced(by: 1234)
let device = MTLCreateSystemDefaultDevice()!
let inBuffer = device.makeBuffer(bytesNoCopy: unaligned, length: 1024, options: .storageModeShared, deallocator: nil)!
let outBuffer = device.makeBuffer(length: 1024, options: .storageModeShared)!
let library = try! device.makeLibrary(filepath: "default.metallib")
let pso = try! device.makeComputePipelineState(function: library.makeFunction(name: "test_kernel")!)
let queue = device.makeCommandQueue()!
let cb = queue.makeCommandBuffer()!
let enc = cb.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
enc.setBuffer(inBuffer, offset: 0, index: 0)
enc.setBuffer(outBuffer, offset: 0, index: 1)
enc.dispatchThreadgroups(MTLSizeMake(1, 1, 1), threadsPerThreadgroup: MTLSizeMake(1, 1, 1))
enc.endEncoding()
cb.commit()
cb.waitUntilCompleted()
let outPtr = outBuffer.contents().bindMemory(to: UInt8.self, capacity: 1024)
print("Expected:", 1234 % 256)
print("GPU Actual:", outPtr[0])
