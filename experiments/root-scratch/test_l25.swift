import Foundation

let text = """
;;; L2.5 PROJECT MAP
;;; GENERATED_AT: 1716680000.0
;;; WORKSPACE: /tmp
;;; GLOBAL: [碼:1]
"""
var lines = text.components(separatedBy: "\n")
var generatedAt = Date()
for line in lines {
    let t = line.trimmingCharacters(in: .whitespaces)
    if t.hasPrefix(";;; GENERATED_AT: ") {
        let valStr = String(t.dropFirst(18))
        print("Parsing: '\(valStr)'")
        let ts = Double(valStr) ?? 0
        generatedAt = Date(timeIntervalSince1970: ts)
    }
}
print(generatedAt.timeIntervalSince1970)
