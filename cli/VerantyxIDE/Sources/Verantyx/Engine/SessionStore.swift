import Foundation
import SwiftUI

// MARK: - ChatSession
// A persisted chat session linking messages ↔ JCross memory nodes.

struct ChatSession: Identifiable, Codable {
    let id: UUID
    var title: String
    var createdAt: Date
    var updatedAt: Date
    var messages: [ChatMessage]
    var workspacePath: String?
    var memoryNodeIds: [String]    // filenames in JCross memory (e.g. "TURN_1234.jcross")
    var activeLayer: JCrossLayer

    init(
        id: UUID = UUID(),
        title: String = "New Session",
        messages: [ChatMessage] = [],
        workspacePath: String? = nil
    ) {
        self.id           = id
        self.title        = title
        self.createdAt    = Date()
        self.updatedAt    = Date()
        self.messages     = messages
        self.workspacePath = workspacePath
        self.memoryNodeIds = []
        self.activeLayer  = .l2
    }

    // Auto-title from first user message
    mutating func autoTitle() {
        if let first = messages.first(where: { $0.role == .user }) {
            title = String(first.content.prefix(40))
                        .trimmingCharacters(in: .whitespacesAndNewlines)
        }
    }
}

// MARK: - JCrossLayer

enum JCrossLayer: String, Codable, CaseIterable, Identifiable {
    case l1   = "L1"
    case l1_5 = "L1.5"
    case l2   = "L2"
    case l3   = "L3"

    var id: String { rawValue }

    var displayName: String { rawValue }

    var description: String {
        switch self {
        case .l1:   return "Kanji topology (ultrafast)"
        case .l1_5: return "Summary index (balanced)"
        case .l2:   return "Structured facts (accurate)"
        case .l3:   return "Verbatim text (max context)"
        }
    }

    var icon: String {
        switch self {
        case .l1:   return "character.ja"
        case .l1_5: return "tablecells"
        case .l2:   return "list.bullet.rectangle"
        case .l3:   return "doc.text.fill"
        }
    }

    // Maps to the layer argument in mcp_verantyx-compiler_read
    var mcpLayerArg: String {
        switch self {
        case .l1:   return "l1"
        case .l1_5: return "l2"   // L1.5 ≈ L2 summary in the MCP schema
        case .l2:   return "l2l3"
        case .l3:   return "l3"
        }
    }
}

// MARK: - SessionStore

@MainActor
final class SessionStore: ObservableObject {

    @Published var sessions: [ChatSession] = []
    @Published var activeSessionId: UUID? = nil

    var activeSession: ChatSession? {
        guard let id = activeSessionId else { return nil }
        return sessions.first(where: { $0.id == id })
    }

    // MARK: - Persistence

    private let storageDir: URL = {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory,
                                            in: .userDomainMask)[0]
            .appendingPathComponent("Verantyx/sessions")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    init() {
        // ⚠️ loadAll() は起動時にディスクI/Oを実行するためメインスレッドをブロックする。
        // Task.detached でバックグラウンドに逃がし、完了後に MainActor へ反映する。
        // ⚠️ [weak self] を Task.detached で直接キャプチャすると ObservableObject の
        // 型チェッククラッシュ(SIGTERM)を誘発するため、値返しの Task.detached を使用する。
        let dir = storageDir
        Task { [weak self] in
            let decoded = await Task.detached(priority: .utility) { () -> [ChatSession] in
                guard let files = try? FileManager.default.contentsOfDirectory(
                    at: dir, includingPropertiesForKeys: [.creationDateKey]
                ) else { return [] }
                
                return files
                    .filter { $0.pathExtension == "json" }
                    .compactMap { url -> ChatSession? in
                        guard let data = try? Data(contentsOf: url) else { return nil }
                        return try? JSONDecoder().decode(ChatSession.self, from: data)
                    }
                    .sorted { $0.updatedAt > $1.updatedAt }
            }.value
            
            self?.sessions = decoded
            self?.activeSessionId = decoded.first?.id
        }
    }

    // MARK: - CRUD

    func newSession(messages: [ChatMessage] = [], workspacePath: String? = nil) -> ChatSession {
        var session = ChatSession(messages: messages, workspacePath: workspacePath)
        if !messages.isEmpty { session.autoTitle() }
        sessions.insert(session, at: 0)
        activeSessionId = session.id
        save(session)
        return session
    }

    func updateActiveSession(messages: [ChatMessage], workspacePath: String? = nil) {
        guard let id = activeSessionId,
              let idx = sessions.firstIndex(where: { $0.id == id }) else { return }
        // Strip any empty-content assistant bubbles that were created mid-stream
        // (e.g. the placeholder appended before the first token arrives).
        // These appear as blank bubbles when a session is restored.
        let clean = messages.filter { msg in
            !(msg.role == .assistant && msg.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        sessions[idx].messages     = clean
        sessions[idx].updatedAt    = Date()
        if let wp = workspacePath { sessions[idx].workspacePath = wp }
        sessions[idx].autoTitle()
        save(sessions[idx])
    }

    /// 終了時専用の同期セーブ。
    /// `save()` は毎 5 メッセージごとに `Task.detached { archiveProgressively() }` を起動するが、
    /// `applicationShouldTerminate` の同期コンテキストでこれを呼ぶとメインスレッドがブロックされる。
    /// このメソッドは JSON ディスク書き込みのみを行い、非同期タスクを一切起動しない。
    func saveForQuit(messages: [ChatMessage], workspacePath: String? = nil) {
        guard let id = activeSessionId,
              let idx = sessions.firstIndex(where: { $0.id == id }) else { return }
        let clean = messages.filter { msg in
            !(msg.role == .assistant && msg.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        sessions[idx].messages  = clean
        sessions[idx].updatedAt = Date()
        if let wp = workspacePath { sessions[idx].workspacePath = wp }
        sessions[idx].autoTitle()
        // JSON のみ書き込む — archiveProgressively は起動しない
        guard let data = try? JSONEncoder().encode(sessions[idx]) else { return }
        try? data.write(to: sessionURL(sessions[idx].id))
    }

    func setLayer(_ layer: JCrossLayer, for sessionId: UUID) {
        guard let idx = sessions.firstIndex(where: { $0.id == sessionId }) else { return }
        sessions[idx].activeLayer = layer
        save(sessions[idx])
    }

    func linkMemoryNode(_ fileName: String, to sessionId: UUID) {
        guard let idx = sessions.firstIndex(where: { $0.id == sessionId }) else { return }
        if !sessions[idx].memoryNodeIds.contains(fileName) {
            sessions[idx].memoryNodeIds.append(fileName)
            save(sessions[idx])
        }
    }

    func rename(_ sessionId: UUID, to newTitle: String) {
        guard let idx = sessions.firstIndex(where: { $0.id == sessionId }) else { return }
        sessions[idx].title = newTitle
        save(sessions[idx])
    }

    /// Delete a session. The **conversation messages** are removed, but the
    /// session's key facts are immortalized as a JCross node BEFORE deletion.
    func delete(_ sessionId: UUID) {
        // ── Step 1: Archive to JCross (永続化) ─────────────────────────
        if let session = sessions.first(where: { $0.id == sessionId }) {
            SessionMemoryArchiver.shared.archiveBeforeDelete(session: session)
        }

        // ── Step 2: Remove the session JSON (会話は消す) ────────────────
        sessions.removeAll { $0.id == sessionId }
        let url = sessionURL(sessionId)
        try? FileManager.default.removeItem(at: url)
        if activeSessionId == sessionId { activeSessionId = sessions.first?.id }
    }

    func selectSession(_ sessionId: UUID) {
        activeSessionId = sessionId
    }

    // MARK: - JCross Memory retrieval
    // Returns a context injection string built from the session's linked nodes
    // at the current active layer. This is called before inference to inject
    // session-specific long-term memory into the prompt.

    func buildMemoryInjection(for sessionId: UUID) async -> String {
        guard let session = sessions.first(where: { $0.id == sessionId }),
              !session.memoryNodeIds.isEmpty else { return "" }

        var parts: [String] = []
        let layer = session.activeLayer

        for fileName in session.memoryNodeIds.prefix(8) {
            if let content = await fetchJCrossNode(fileName: fileName, layer: layer) {
                parts.append(content)
            }
        }

        guard !parts.isEmpty else { return "" }

        return """

        [JCROSS MEMORY — Layer: \(layer.rawValue) — \(layer.description)]
        \(parts.joined(separator: "\n---\n"))
        [/JCROSS MEMORY]
        """
    }

    // Fetch a single JCross node via the MCP server file system
    // (reads from ~/.openclaw/memory/ where JCross nodes live)
    private func fetchJCrossNode(fileName: String, layer: JCrossLayer) async -> String? {
        let wsPath = await MainActor.run { AppState.shared?.cortexWorkspacePath ?? AppState.shared?.workspaceURL?.path }
        guard let basePath = wsPath else { return nil }
        
        let searchPaths: [String] = [
            basePath + "/.openclaw/memory/front/" + fileName,
            basePath + "/.openclaw/memory/near/" + fileName,
            basePath + "/.openclaw/memory/mid/" + fileName,
            basePath + "/.openclaw/memory/deep/" + fileName,
        ]

        for path in searchPaths {
            guard FileManager.default.fileExists(atPath: path),
                  let raw = try? String(contentsOfFile: path, encoding: .utf8)
            else { continue }

            return extractLayer(from: raw, layer: layer)
        }
        return nil
    }

    // Extract the requested layer from a .jcross file's raw content
    private func extractLayer(from raw: String, layer: JCrossLayer) -> String {
        switch layer {
        case .l1:
            // L1: first non-empty line (kanji tags / summary)
            return raw.components(separatedBy: "\n")
                .first(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty })
                ?? String(raw.prefix(100))

        case .l1_5:
            // L1.5: first 3 lines (index + brief summary)
            let lines = raw.components(separatedBy: "\n")
                .filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
            return lines.prefix(3).joined(separator: "\n")

        case .l2:
            // L2: Extract OP.FACT / OP.ENTITY / OP.STATE lines
            let opLines = raw.components(separatedBy: "\n")
                .filter { $0.contains("OP.FACT") || $0.contains("OP.ENTITY") || $0.contains("OP.STATE") }
            return opLines.isEmpty
                ? String(raw.prefix(400))
                : opLines.joined(separator: "\n")

        case .l3:
            // L3: full raw text (capped at 2000 chars)
            return String(raw.prefix(2000))
        }
    }

    // MARK: - Disk I/O

    private func sessionURL(_ id: UUID) -> URL {
        storageDir.appendingPathComponent("\(id.uuidString).json")
    }

    private func save(_ session: ChatSession) {
        guard let data = try? JSONEncoder().encode(session) else { return }
        try? data.write(to: sessionURL(session.id))

        // ── Progressive JCross archiving ──────────────────────────────
        // Every 10 messages, distill the session into a .jcross node.
        // The node is overwritten each time (fixed filename PROG_<id>.jcross),
        // so the count stays bounded regardless of session length.
        let userMessageCount = session.messages.filter { $0.role == .user }.count
        if userMessageCount > 0 && userMessageCount % 5 == 0 {
            Task.detached(priority: .background) {
                SessionMemoryArchiver.shared.archiveProgressively(session: session)
            }
        }
    }

    private func loadAll() {
        guard let files = try? FileManager.default.contentsOfDirectory(at: storageDir,
                                                       includingPropertiesForKeys: [.creationDateKey]) else { return }
        let decoded: [ChatSession] = files
            .filter { $0.pathExtension == "json" }
            .compactMap { url -> ChatSession? in
                guard let data = try? Data(contentsOf: url) else { return nil }
                return try? JSONDecoder().decode(ChatSession.self, from: data)
            }
            .sorted { $0.updatedAt > $1.updatedAt }

        sessions = decoded
        activeSessionId = sessions.first?.id
    }
}
