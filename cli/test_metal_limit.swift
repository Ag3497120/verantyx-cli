import Metal
let device = MTLCreateSystemDefaultDevice()!
print("Max Buffer Length: \(device.maxBufferLength / 1024 / 1024) MB")
