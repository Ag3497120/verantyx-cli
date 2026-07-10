import Foundation
import Metal

let device = MTLCreateSystemDefaultDevice()!
let path = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9/model-00008-of-00015.safetensors"
let offset = 60000
let size = 1000

let fd = open(path, O_RDONLY)
let ptr = mmap(nil, size + offset, PROT_READ, MAP_SHARED, fd, 0)
print("mmap ptr: \(ptr!)")
let advPtr = ptr!.advanced(by: offset)
print("advPtr: \(advPtr)")

let buffer = device.makeBuffer(bytesNoCopy: advPtr, length: size, options: .storageModeShared, deallocator: nil)
if buffer != nil {
    print("Buffer created successfully! Buffer address: \(buffer!.contents())")
} else {
    print("Buffer creation FAILED!")
}
