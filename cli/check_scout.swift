import Foundation

struct ScoutWeight {
    var zCoord: UInt8
    var matrixType: UInt8
    var rank: UInt16
    var inDim: UInt32
    var outDim: UInt32
    var w1: [Float]
    var w2: [Float]
}

var scoutWeights = [UInt8: [UInt8: ScoutWeight]]()

func loadJScout(path: String) {
    guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return }
    var offset = 0
    let magic = data.subdata(in: offset..<offset+4)
    offset += 4
    let version = data.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
    offset += 4
    while offset < data.count {
        let z = data[offset]
        let m = data[offset+1]
        offset += 2
        let rank = data.subdata(in: offset..<offset+2).withUnsafeBytes { $0.load(as: UInt16.self) }
        offset += 2
        let inDim = data.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
        offset += 4
        let outDim = data.subdata(in: offset..<offset+4).withUnsafeBytes { $0.load(as: UInt32.self) }
        offset += 4
        if scoutWeights[z] == nil { scoutWeights[z] = [:] }
        scoutWeights[z]![m] = ScoutWeight(zCoord: z, matrixType: m, rank: rank, inDim: inDim, outDim: outDim, w1: [], w2: [])
        let sizeW1 = Int(inDim) * Int(rank) * 2
        let sizeW2 = Int(outDim) * Int(rank) * 2
        offset += sizeW1 + sizeW2
    }
}

loadJScout(path: "qwen_27b.jscout")
if let w = scoutWeights[0] {
    print("Z=0 scout types: \(w.keys)")
} else {
    print("No scout weights for Z=0")
}
