import Foundation

let data = try! Data(contentsOf: URL(fileURLWithPath: "qwen_27b.jcross"))
let magic = data.subdata(in: 0..<4).withUnsafeBytes { $0.load(as: UInt32.self) }

let jsonLen = data.subdata(in: 8..<16).withUnsafeBytes { $0.load(as: UInt64.self) }

let json = try! JSONSerialization.jsonObject(with: data.subdata(in: 16..<16+Int(jsonLen)), options: []) as! [String: Any]
let jmeta = json["jmeta"] as! [String: [String: [String: UInt64]]]
let lmHeadMeta = jmeta["64"]!["0"]!

let offset = Int(lmHeadMeta["offset"]!)
let jheadData = data.subdata(in: offset..<offset+Int(lmHeadMeta["length"]!))

let normLen = jheadData.subdata(in: 8..<12).withUnsafeBytes { $0.load(as: UInt32.self) }
print("NormLen: \(normLen)")
