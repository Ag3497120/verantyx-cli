import Metal
import Foundation
let fd = open("metadata.json", O_RDWR | O_CREAT, 0o666)
ftruncate(fd, 32768)
let ptr = mmap(nil, 32768, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0)
let unaligned = ptr!.advanced(by: 1234)
let device = MTLCreateSystemDefaultDevice()!
let buffer = device.makeBuffer(bytesNoCopy: unaligned, length: 1024, options: .storageModeShared, deallocator: nil)
print("Buffer is", buffer != nil ? "Created" : "nil")
