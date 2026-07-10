import Metal
guard let device = MTLCreateSystemDefaultDevice() else { print("No metal"); exit(1) }
print("Max buffer length: \(device.maxBufferLength / 1024 / 1024 / 1024) GB")
