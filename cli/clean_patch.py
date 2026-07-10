import sys

with open("Sources/VeraCore/Backends/VeraMetalBackend.swift", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "private let commandQueue: MTLCommandQueue" in line:
        new_lines.append(line)
        new_lines.append("    private var globalMmapPtr: UnsafeMutableRawPointer?\n")
        new_lines.append("    private var globalMmapBuffer: MTLBuffer?\n")
        new_lines.append("    private var globalMmapBuffer1: MTLBuffer?\n")
        new_lines.append("    private var maxMmapBufferLength: UInt64 = 0\n")
    elif "if !AsynchronousPrefetcher.shared.openFile(path: runtime.modelPath) {" in line:
        new_lines.append("        let fd = open(runtime.modelPath, O_RDONLY)\n")
        new_lines.append("        if fd >= 0 {\n")
        new_lines.append("            let size = lseek(fd, 0, SEEK_END)\n")
        new_lines.append("            if size > 0 {\n")
        new_lines.append("                globalMmapPtr = mmap(nil, Int(size), PROT_READ, MAP_SHARED, fd, 0)\n")
        new_lines.append("                if globalMmapPtr != MAP_FAILED {\n")
        new_lines.append("                    maxMmapBufferLength = UInt64(device.maxBufferLength)\n")
        new_lines.append("                    if size <= device.maxBufferLength {\n")
        new_lines.append("                        globalMmapBuffer = device.makeBuffer(bytesNoCopy: globalMmapPtr!, length: Int(size), options: .storageModeShared, deallocator: nil)\n")
        new_lines.append("                        if verbose { fputs(\"[*] Successfully memory-mapped \\(size) bytes directly to Metal (1 buffer).\\n\", stderr); fflush(stderr) }\n")
        new_lines.append("                    } else {\n")
        new_lines.append("                        globalMmapBuffer = device.makeBuffer(bytesNoCopy: globalMmapPtr!, length: device.maxBufferLength, options: .storageModeShared, deallocator: nil)\n")
        new_lines.append("                        let remaining = Int(size) - device.maxBufferLength\n")
        new_lines.append("                        let ptr1 = globalMmapPtr!.advanced(by: device.maxBufferLength)\n")
        new_lines.append("                        globalMmapBuffer1 = device.makeBuffer(bytesNoCopy: ptr1, length: remaining, options: .storageModeShared, deallocator: nil)\n")
        new_lines.append("                        if verbose { fputs(\"[*] Successfully memory-mapped \\(size) bytes directly to Metal (2 buffers).\\n\", stderr); fflush(stderr) }\n")
        new_lines.append("                    }\n")
        new_lines.append("                }\n")
        new_lines.append("            }\n")
        new_lines.append("            close(fd)\n")
        new_lines.append("        }\n")
        new_lines.append(line)
    elif "private func dispatchBlocks(_ targetBlocks: [SpatialBlock], inBuffer: MTLBuffer, outBuffer: MTLBuffer, encoder: MTLComputeCommandEncoder) {" in line:
        new_lines.append(line)
        new_lines.append("        if targetBlocks.isEmpty { return }\n")
        new_lines.append("        let blockCount = targetBlocks.count\n")
        new_lines.append("        if let mmapBuffer = globalMmapBuffer {\n")
        new_lines.append("            let infoBufferSize = blockCount * MemoryLayout<BlockInfo>.stride\n")
        new_lines.append("            guard let globalInfoBuffer = device.makeBuffer(length: infoBufferSize, options: .storageModeShared) else { return }\n")
        new_lines.append("            var infos = [BlockInfo]()\n")
        new_lines.append("            infos.reserveCapacity(blockCount)\n")
        new_lines.append("            for i in 0..<blockCount {\n")
        new_lines.append("                let b = targetBlocks[i]\n")
        new_lines.append("                if b.fileOffset < maxMmapBufferLength {\n")
        new_lines.append("                    infos.append(BlockInfo(rowIdx: UInt32(b.rowIdx), colIdx: UInt32(b.colIdx), blockSize: 64, pad: 0, byteOffset: UInt64(b.fileOffset)))\n")
        new_lines.append("                } else {\n")
        new_lines.append("                    infos.append(BlockInfo(rowIdx: UInt32(b.rowIdx), colIdx: UInt32(b.colIdx), blockSize: 64, pad: 1, byteOffset: UInt64(b.fileOffset) - maxMmapBufferLength))\n")
        new_lines.append("                }\n")
        new_lines.append("            }\n")
        new_lines.append("            globalInfoBuffer.contents().copyMemory(from: infos, byteCount: infoBufferSize)\n")
        new_lines.append("            encoder.setBuffer(mmapBuffer, offset: 0, index: 0)\n")
        new_lines.append("            if let buf1 = globalMmapBuffer1 { encoder.setBuffer(buf1, offset: 0, index: 1) }\n")
        new_lines.append("            encoder.setBuffer(inBuffer, offset: 0, index: 2)\n")
        new_lines.append("            encoder.setBuffer(outBuffer, offset: 0, index: 3)\n")
        new_lines.append("            encoder.setBuffer(globalInfoBuffer, offset: 0, index: 4)\n")
        new_lines.append("            encoder.dispatchThreadgroups(MTLSizeMake(blockCount, 1, 1), threadsPerThreadgroup: MTLSizeMake(64, 1, 1))\n")
        new_lines.append("            return\n")
        new_lines.append("        }\n")
    elif "if targetBlocks.isEmpty { return }" in line and "dispatchBlocks" in lines[i-1]:
        pass
    elif "let blockCount = targetBlocks.count" in line and "let firstFileOffset =" in lines[i+1]:
        pass
    else:
        new_lines.append(line)

with open("Sources/VeraCore/Backends/VeraMetalBackend.swift", "w") as f:
    f.writelines(new_lines)
