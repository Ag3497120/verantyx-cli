import Foundation

public class AsynchronousPrefetcher {
    public static let shared = AsynchronousPrefetcher()
    private let queue = DispatchQueue(label: "com.verantyx.prefetchQueue", attributes: .concurrent)
    private let numAxes = 16
    
    private var fd: Int32 = -1
    
    public func openFile(path: String) -> Bool {
        self.fd = open(path, O_RDONLY)
        if self.fd == -1 {
            fputs("[-] Failed to open .jcross file for asynchronous prefetch.\n", stderr)
        } else {
            fcntl(self.fd, F_NOCACHE, 1)
        }
        return self.fd != -1
    }
    
    public func closeFile() {
        if self.fd != -1 {
            close(self.fd)
            self.fd = -1
        }
    }
    
    public func prefetchToRingBuffer(blocks: [SpatialQuantumBlock], ringBufferBase: UnsafeMutableRawPointer, ringBufferOffset: Int, alignedFileOffset: Int, alignedLength: Int) {
        if blocks.isEmpty || self.fd == -1 { return }
        
        let startTotal = CFAbsoluteTimeGetCurrent()
        let group = DispatchGroup()
        
        // Intelligent Sparse I/O Grouping
        // We only merge blocks if the gap is small (< 64KB). Otherwise, we issue separate reads.
        // This preserves the 95% sparsity (only reading ~500MB per token) while minimizing syscalls.
        
        struct SparseChunk {
            var startOffset: Int
            var endOffset: Int
        }
        
        var chunks = [SparseChunk]()
        var currentChunk: SparseChunk?
        
        let maxGap = 8192 // 8 KB: Only merge strictly adjacent blocks to ensure sparse I/O
        let sortedBlocks = blocks.sorted { $0.fileOffset < $1.fileOffset }
        for b in sortedBlocks {
            let offset = b.fileOffset
            if var chunk = currentChunk {
                if offset - chunk.endOffset <= maxGap {
                    chunk.endOffset = offset + 8192
                    currentChunk = chunk
                } else {
                    chunks.append(chunk)
                    currentChunk = SparseChunk(startOffset: offset, endOffset: offset + 8192)
                }
            } else {
                currentChunk = SparseChunk(startOffset: offset, endOffset: offset + 8192)
            }
        }
        if let chunk = currentChunk { chunks.append(chunk) }
        
        var finalChunks = [SparseChunk]()
        for chunk in chunks {
            let totalLength = chunk.endOffset - chunk.startOffset
            if totalLength > 1024 * 1024 { // If > 1MB, split into 6 parallel sub-chunks
                let subChunkSize = ((totalLength / 6) / 16384) * 16384 // 16KB aligned
                var currentStart = chunk.startOffset
                for i in 0..<5 {
                    finalChunks.append(SparseChunk(startOffset: currentStart, endOffset: currentStart + subChunkSize))
                    currentStart += subChunkSize
                }
                finalChunks.append(SparseChunk(startOffset: currentStart, endOffset: chunk.endOffset))
            } else {
                finalChunks.append(chunk)
            }
        }
        
        var totalBytesRead = 0
        
        // "6軸並列処理" (6-axis parallel processing)
        // Divide chunks into 6 batches to avoid thread explosion
        let numAxes = 128
        var batches = Array(repeating: [SparseChunk](), count: numAxes)
        for (i, chunk) in finalChunks.enumerated() {
            batches[i % numAxes].append(chunk)
            totalBytesRead += (chunk.endOffset - chunk.startOffset)
        }
        
        for batch in batches {
            if batch.isEmpty { continue }
            group.enter()
            queue.async {
                for chunk in batch {
                    let chunkAlignedOffset = (chunk.startOffset / 16384) * 16384
                    let rawLength = chunk.endOffset - chunkAlignedOffset
                    let chunkAlignedLength = (rawLength + 16383) & ~16383
                    let destOffset = chunkAlignedOffset - alignedFileOffset
                    let destPtr = ringBufferBase.advanced(by: ringBufferOffset + destOffset)
                    let bytesRead = pread(self.fd, destPtr, chunkAlignedLength, off_t(chunkAlignedOffset))
                    if bytesRead == -1 {
                        fputs("pread Error: \(String(cString: strerror(errno)))\n", stderr); fflush(stderr)
                    } else if bytesRead != chunkAlignedLength {
                        fputs("pread Partial/Zero Read: requested \(chunkAlignedLength), got \(bytesRead)\n", stderr); fflush(stderr)
                    }
                }
                group.leave()
            }
        }
        
        group.wait()
        
        let endTotal = CFAbsoluteTimeGetCurrent()
        if endTotal - startTotal > 0.0 {
            let msg = String(format: "    [Prefetcher] read %d bytes in %.3fs\n", totalBytesRead, endTotal - startTotal)
            fputs(msg, stderr)
            fflush(stderr)
        }
    }
    
    public func prefetchScattered(blocks: [SpatialQuantumBlock], bufferBase: UnsafeMutableRawPointer, currentOffset: inout Int, cacheMap: inout [Int: Int]) {
        if blocks.isEmpty || self.fd == -1 { return }
        let group = DispatchGroup()
        
        let numAxes = 128
        var batches = Array(repeating: [SpatialQuantumBlock](), count: numAxes)
        for (i, block) in blocks.enumerated() {
            batches[i % numAxes].append(block)
        }
        
        var allocatedOffsets = [Int: Int]()
        for block in blocks {
            allocatedOffsets[block.fileOffset] = currentOffset
            cacheMap[block.fileOffset] = currentOffset
            currentOffset += 8192
        }
        
        for batch in batches {
            if batch.isEmpty { continue }
            group.enter()
            queue.async {
                for block in batch {
                    let destOffset = allocatedOffsets[block.fileOffset]!
                    let destPtr = bufferBase.advanced(by: destOffset)
                    let bytesRead = pread(self.fd, destPtr, 8192, off_t(block.fileOffset))
                    if bytesRead == -1 {
                        fputs("pread Error: \(String(cString: strerror(errno)))\n", stderr); fflush(stderr)
                    }
                }
                group.leave()
            }
        }
        
        group.wait()
    }
}
