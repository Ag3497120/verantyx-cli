import Foundation
struct SpatialQuantumBlock { let zCoord: UInt8; let xCoord: Int8; let yCoord: Int8; let axisVector: UInt8; let fileOffset: Int; let length: Int }
print("Starting...")
let fileURL = URL(fileURLWithPath: "../qwen_27b.jcross")
let mappedData = try! Data(contentsOf: fileURL, options: .alwaysMapped)
var spatialGraph: [UInt8: [SpatialQuantumBlock]] = [:]
var offset = 12
let blockSizeBytes = 64 * 64 * 2
var tempGraph = Array(repeating: [SpatialQuantumBlock](), count: 256)
mappedData.withUnsafeBytes { rawPtr in
    let ptr = rawPtr.baseAddress!.assumingMemoryBound(to: UInt8.self)
    while offset < mappedData.count {
        let zCoord = ptr[offset]
        let xCoord = Int8(bitPattern: ptr[offset + 1])
        let yCoord = Int8(bitPattern: ptr[offset + 2])
        let axisVector = ptr[offset + 3]
        offset += 4
        let block = SpatialQuantumBlock(zCoord: zCoord, xCoord: xCoord, yCoord: yCoord, axisVector: axisVector, fileOffset: offset, length: blockSizeBytes)
        tempGraph[Int(zCoord)].append(block)
        offset += blockSizeBytes
    }
}
print("Done parsing.")
