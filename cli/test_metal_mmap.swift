import Metal
import Foundation
let fd = open("/Users/motonishikoudai/verantyx-cli/cli/qwen_27b.jcross", O_RDONLY)
let ptr = mmap(nil, 16384, PROT_READ, MAP_SHARED, fd, 0)!
let device = MTLCreateSystemDefaultDevice()!
let buffer = device.makeBuffer(bytesNoCopy: ptr, length: 16384, options: .storageModeShared, deallocator: nil)
print("Buffer: \(String(describing: buffer))")
