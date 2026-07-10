import Metal
let device = MTLCreateSystemDefaultDevice()!
print("Max buffer length: \(device.maxBufferLength)")
