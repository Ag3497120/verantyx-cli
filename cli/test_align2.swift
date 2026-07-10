import Metal
import Foundation
let fd = open("test_align.bin", O_RDWR | O_CREAT, 0o666)
ftruncate(fd, 32768)
let ptr = mmap(nil, 32768, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0)
let bytePtr = ptr!.bindMemory(to: UInt8.self, capacity: 32768)
for i in 0..<32768 { bytePtr[i] = UInt8(i % 256) }
let unaligned = ptr!.advanced(by: 1234)
let device = MTLCreateSystemDefaultDevice()!
let buffer = device.makeBuffer(bytesNoCopy: unaligned, length: 1024, options: .storageModeShared, deallocator: nil)!
let bufPtr = buffer.contents().bindMemory(to: UInt8.self, capacity: 1024)
print("Expected:", 1234 % 256)
print("Actual:", bufPtr[0])
