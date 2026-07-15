import Foundation

struct L25ProjectMap {
    var entries: [String: String]
}
let workspaceURL = URL(fileURLWithPath: "/Users/motonishikoudai/verantyx-cli")
let fileURL = URL(fileURLWithPath: "/Users/motonishikoudai/verantyx-cli/cli/VerantyxIDE/Sources/Verantyx/Engine/L25IndexEngine.swift")

let relativePath = String(fileURL.path.dropFirst(workspaceURL.path.count + 1))
print("relativePath: '\(relativePath)'")
