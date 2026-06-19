import Foundation

public struct SpatialQuantumBlock {
    public let zCoord: UInt8
    public let colIdx: UInt16
    public let rowIdx: UInt16
    public let matrixType: UInt8
    
    // Zero-Copy Mmap Info
    public let fileOffset: Int
    public let length: Int
}

public struct ScoutWeight {
    public let inDim: Int
    public let outDim: Int
    public let rank: Int
    public let w1: [Float]
    public let w2: [Float]
}

public class VeraRuntime {
    public let modelPath: String
    public let idxPath: String
    public let scoutPath: String
    
    // Spatial Hash Map: Z -> [SpatialQuantumBlock]
    public private(set) var spatialGraph: [UInt8: [SpatialQuantumBlock]] = [:]
    public private(set) var totalBlocks: UInt32 = 0
    public private(set) var mappedData: Data!
    public private(set) var scoutWeights: [UInt8: [UInt8: ScoutWeight]] = [:]
    private var isVerbose: Bool = true
    
    public init(modelPath: String, verbose: Bool = true) {
        self.modelPath = modelPath
        self.idxPath = modelPath.replacingOccurrences(of: ".jcross", with: ".jidx")
        self.scoutPath = modelPath.replacingOccurrences(of: ".jcross", with: ".jscout")
        self.isVerbose = verbose
    }
    
    public func load() throws {
        // 1. Map the 46GB matrix data into virtual memory (Zero-Copy)
        // CPU will NEVER touch this buffer. Only Metal will access it.
        let fileURL = URL(fileURLWithPath: modelPath)
        mappedData = try Data(contentsOf: fileURL, options: .alwaysMapped)
        
        if isVerbose { fputs("[*] .jcross mapped to virtual memory. Size: \(mappedData.count / 1024 / 1024) MB\n", stderr) }
        
        try loadScout()
        
        // 2. Load the lightweight spatial index into RAM
        let idxURL = URL(fileURLWithPath: idxPath)
        let idxData = try Data(contentsOf: idxURL)
        
        var offset = 0
        let magic = String(data: idxData.subdata(in: offset..<offset+4), encoding: .utf8)
        offset += 4
        guard magic == "JIDX" else {
            throw NSError(domain: "VeraRuntime", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid JIDX magic header"])
        }
        
        let version = idxData.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
        offset += 4
        
        totalBlocks = idxData.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
        offset += 4
        
        if isVerbose { fputs("[*] Loading Spatial Index (v\(version)) with \(totalBlocks) Spatial Nodes...\n", stderr) }
        
        let blockSizeBytes = 64 * 64 * 2 // 8192 bytes
        var tempGraph = Array(repeating: [SpatialQuantumBlock](), count: 256)
        
        idxData.withUnsafeBytes { rawPtr in
            guard let baseAddress = rawPtr.baseAddress else { return }
            
            var blockIndex = 0
            while offset < idxData.count {
                let zCoord = baseAddress.load(fromByteOffset: offset, as: UInt8.self)
                let colIdx = baseAddress.loadUnaligned(fromByteOffset: offset + 1, as: UInt16.self)
                let rowIdx = baseAddress.loadUnaligned(fromByteOffset: offset + 3, as: UInt16.self)
                let matrixType = baseAddress.load(fromByteOffset: offset + 5, as: UInt8.self)
                offset += 6
                
                // Pure .jcross has no headers, so fileOffset is just blockIndex * blockSizeBytes
                let fileOffset = blockIndex * blockSizeBytes
                let block = SpatialQuantumBlock(zCoord: zCoord, colIdx: colIdx, rowIdx: rowIdx, matrixType: matrixType, fileOffset: fileOffset, length: blockSizeBytes)
                
                tempGraph[Int(zCoord)].append(block)
                blockIndex += 1
            }
        }
        
        for i in 0..<256 {
            if !tempGraph[i].isEmpty {
                var uniqueBlocks = [String: SpatialQuantumBlock]()
                for block in tempGraph[i] {
                    let key = "\(block.matrixType)_\(block.rowIdx)_\(block.colIdx)"
                    if let existing = uniqueBlocks[key] {
                        if block.fileOffset < existing.fileOffset {
                            uniqueBlocks[key] = block
                        }
                    } else {
                        uniqueBlocks[key] = block
                    }
                }
                spatialGraph[UInt8(i)] = Array(uniqueBlocks.values).sorted { $0.fileOffset < $1.fileOffset }
            }
        }
        
        if isVerbose { fputs("[+] Spatial Graph loaded. Zero-Copy Architecture Ready (No CPU Page-Faults!).\n", stderr) }
    }
    
    private func loadScout() throws {
        guard FileManager.default.fileExists(atPath: scoutPath) else { return }
        let scoutData = try Data(contentsOf: URL(fileURLWithPath: scoutPath))
        var offset = 0
        let magic = String(data: scoutData.subdata(in: offset..<offset+4), encoding: .utf8)
        offset += 4
        guard magic == "JSCT" else { return }
        let version = scoutData.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
        offset += 4
        
        if isVerbose { fputs("[*] Loading Dynamic Scout Predictor weights (v\(version))...\n", stderr) }
        
        while offset < scoutData.count {
            let zCoord = scoutData[offset]
            let matrixType = scoutData[offset+1]
            let rank = Int(scoutData.subdata(in: offset+2..<offset+4).withUnsafeBytes { $0.load(as: UInt16.self) })
            let rows1 = Int(scoutData.subdata(in: offset+4..<offset+8).withUnsafeBytes { $0.load(as: UInt32.self) })
            let cols1 = Int(scoutData.subdata(in: offset+8..<offset+12).withUnsafeBytes { $0.load(as: UInt32.self) })
            let rows2 = Int(scoutData.subdata(in: offset+12..<offset+16).withUnsafeBytes { $0.load(as: UInt32.self) })
            let cols2 = Int(scoutData.subdata(in: offset+16..<offset+20).withUnsafeBytes { $0.load(as: UInt32.self) })
            offset += 20
            
            let len1 = rows1 * cols1 * 2
            let len2 = rows2 * cols2 * 2
            
            let w1F16 = scoutData.subdata(in: offset..<offset+len1).withUnsafeBytes { Array($0.bindMemory(to: Float16.self)) }
            offset += len1
            
            let w2F16 = scoutData.subdata(in: offset..<offset+len2).withUnsafeBytes { Array($0.bindMemory(to: Float16.self)) }
            offset += len2
            
            let w1 = w1F16.map { Float($0) }
            let w2 = w2F16.map { Float($0) }
            
            if scoutWeights[zCoord] == nil { scoutWeights[zCoord] = [:] }
            scoutWeights[zCoord]![matrixType] = ScoutWeight(inDim: cols1, outDim: rows2, rank: rank, w1: w1, w2: w2)
        }
        
        if isVerbose { fputs("[+] Scout Weights loaded into RAM.\n", stderr) }
    }
}
