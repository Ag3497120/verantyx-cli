import Foundation

struct L25ProjectMap {
    var entries: [String: String]
    var workspaceRoot: String
    var generatedAt: Date
    var globalTopology: String
    
    func toJCrossString() -> String {
        var lines: [String] = []
        lines.append(";;; L2.5 PROJECT MAP")
        lines.append(";;; GENERATED_AT: \(generatedAt.timeIntervalSince1970)")
        lines.append(";;; WORKSPACE: \(workspaceRoot)")
        lines.append(";;; GLOBAL: \(globalTopology)")
        lines.append("")
        
        for (path, _) in entries {
            lines.append("■ NODE L25 \(path)")
            lines.append("LANG: swift")
            lines.append("KANJI: [迅:1.0]")
            lines.append("TOKENS: A")
            lines.append("DEPS: ")
            lines.append("METRICS: L10 F1 C1")
            lines.append("DATE: \(generatedAt.timeIntervalSince1970)")
            lines.append("INDEX: A")
            lines.append("")
        }
        return lines.joined(separator: "\n")
    }
    
    static func fromJCrossString(_ text: String) -> L25ProjectMap? {
        let lines = text.components(separatedBy: "\n")
        var entries: [String: String] = [:]
        var workspaceRoot = ""
        var generatedAt = Date()
        var globalTopology = ""
        
        var currentPath = ""
        
        func finishEntry() {
            guard !currentPath.isEmpty else { return }
            entries[currentPath] = "OK"
            currentPath = ""
        }
        
        for line in lines {
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix(";;; GENERATED_AT: ") {
                let ts = Double(t.dropFirst(18)) ?? 0
                generatedAt = Date(timeIntervalSince1970: ts)
            } else if t.hasPrefix(";;; WORKSPACE: ") {
                workspaceRoot = String(t.dropFirst(15))
            } else if t.hasPrefix(";;; GLOBAL: ") {
                globalTopology = String(t.dropFirst(12))
            } else if t.hasPrefix("■ NODE L25 ") {
                finishEntry()
                currentPath = String(t.dropFirst(11))
            }
        }
        finishEntry()
        
        return L25ProjectMap(entries: entries, workspaceRoot: workspaceRoot, generatedAt: generatedAt, globalTopology: globalTopology)
    }
}

let map = L25ProjectMap(entries: ["a.swift": "OK"], workspaceRoot: "/tmp", generatedAt: Date(), globalTopology: "[X]")
let str = map.toJCrossString()
let parsed = L25ProjectMap.fromJCrossString(str)!
print("entries count:", parsed.entries.count)
print("generatedAt matches:", parsed.generatedAt == map.generatedAt)
