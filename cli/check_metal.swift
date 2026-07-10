import Metal
guard let device = MTLCreateSystemDefaultDevice() else { print("No Metal"); exit(1) }
print("Max buffer length: \(device.maxBufferLength) bytes")
