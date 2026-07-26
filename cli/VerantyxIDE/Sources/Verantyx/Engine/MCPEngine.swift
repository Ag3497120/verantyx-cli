import Foundation
import SwiftUI

// MARK: - MCPEngine
//
// Model Context Protocol client for Verantyx IDE.
//
// Persistent stdio design (fixes Puppeteer / slow-npx):
//   Each enabled server owns ONE long-running Process, started lazily on first
//   use and reused forever. The browser stays open between calls. No cold-start.
//
// HTTP design:
//   Uses a dedicated URLSession with no timeout so long-running HTTP tool calls
//   (e.g. Playwright, Puppeteer-HTTP) never time out at the network layer.
//
// Kill Switch:
//   killActiveCall() → Task.cancel(). Works for both transports.
//   subprocess is terminated only when disconnect() / removeServer() is called.

// MARK: - Data models

struct MCPServerConfig: Codable, Identifiable, Equatable {
    var id: UUID
    var name: String
    var transport: Transport
    var command: String          // stdio: e.g. "npx -y @modelcontextprotocol/server-puppeteer"
    var url: String              // http:  e.g. "http://localhost:3000"
    var envVars: [String: String]
    var isEnabled: Bool
    var mode: ExecutionMode

    enum Transport: String, Codable, CaseIterable {
        case stdio = "stdio"
        case http  = "http"
    }

    enum ExecutionMode: String, Codable, CaseIterable {
        case ai    = "AI Priority"   // no auto-timeout — runs until done or user kills
        case human = "Human Mode"    // 60 s outer deadline
    }

    init(id: UUID = UUID(), name: String, transport: Transport = .stdio,
         command: String = "", url: String = "", envVars: [String: String] = [:],
         isEnabled: Bool = true, mode: ExecutionMode = .ai) {
        self.id = id; self.name = name; self.transport = transport
        self.command = command; self.url = url; self.envVars = envVars
        self.isEnabled = isEnabled; self.mode = mode
    }

    static let examples: [MCPServerConfig] = [
        MCPServerConfig(name: "Filesystem", transport: .stdio,
                        command: "npx -y @modelcontextprotocol/server-filesystem /",
                        mode: .ai),
        MCPServerConfig(name: "GitHub", transport: .stdio,
                        command: "npx -y @modelcontextprotocol/server-github",
                        envVars: ["GITHUB_PERSONAL_ACCESS_TOKEN": ""],
                        mode: .ai),
        MCPServerConfig(name: "Puppeteer", transport: .stdio,
                        command: "npx -y @modelcontextprotocol/server-puppeteer",
                        mode: .ai),
        MCPServerConfig(name: "Brave Search", transport: .stdio,
                        command: "npx -y @modelcontextprotocol/server-brave-search",
                        envVars: ["BRAVE_API_KEY": ""],
                        mode: .human),
        MCPServerConfig(name: "Local HTTP", transport: .http,
                        url: "http://localhost:3000",
                        mode: .human),
    ]
}

struct MCPTool: Identifiable, Codable {
    let id: UUID
    let name: String
    let description: String
    let inputSchema: [String: AnyCodable]
    let serverName: String

    init(name: String, description: String, inputSchema: [String: AnyCodable] = [:], serverName: String) {
        self.id = UUID(); self.name = name; self.description = description
        self.inputSchema = inputSchema; self.serverName = serverName
    }
}

struct AnyCodable: Codable {
    let value: Any
    init(_ value: Any) { self.value = value }
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let v = try? c.decode(Bool.self)               { value = v; return }
        if let v = try? c.decode(Int.self)                { value = v; return }
        if let v = try? c.decode(Double.self)             { value = v; return }
        if let v = try? c.decode(String.self)             { value = v; return }
        if let v = try? c.decode([String: AnyCodable].self) { value = v; return }
        if let v = try? c.decode([AnyCodable].self)       { value = v; return }
        value = NSNull()
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch value {
        case let v as Bool:               try c.encode(v)
        case let v as Int:                try c.encode(v)
        case let v as Double:             try c.encode(v)
        case let v as String:             try c.encode(v)
        case let v as [String: AnyCodable]: try c.encode(v)
        case let v as [AnyCodable]:       try c.encode(v)
        default:                          try c.encodeNil()
        }
    }
}

// MARK: - MCPCallRecord

struct MCPCallRecord: Identifiable {
    let id = UUID()
    let serverName: String
    let toolName: String
    let startTime: Date
    var status: Status
    var elapsedSeconds: Int { Int(Date().timeIntervalSince(startTime)) }
    var task: Task<String, Error>?

    enum Status { case running, completed, timedOut, cancelled, failed(String) }

    var statusLabel: String {
        switch status {
        case .running:        return "RUNNING  \(elapsedSeconds)s"
        case .completed:      return "DONE"
        case .timedOut:       return "TIMEOUT"
        case .cancelled:      return "KILLED"
        case .failed(let e):  return "ERR: \(e.prefix(30))"
        }
    }

    var statusColor: Color {
        switch status {
        case .running:   return Color(red: 0.9, green: 0.7, blue: 0.2)
        case .completed: return Color(red: 0.3, green: 0.9, blue: 0.5)
        case .timedOut:  return .orange
        case .cancelled: return .red
        case .failed:    return Color(red: 0.9, green: 0.4, blue: 0.4)
        }
    }
}

// MARK: - nonisolated helper (callable from any Task or actor)

/// Extracts text content from an MCP JSON-RPC response.
/// nonisolated free function so it compiles inside Task.detached / actor methods alike.
func mcpExtractText(from json: [String: Any]) -> String {
    if let result = json["result"] as? [String: Any] {
        if let content = result["content"] as? [[String: Any]] {
            let text = content.compactMap { block -> String? in
                guard block["type"] as? String == "text" else { return nil }
                return block["text"] as? String
            }.joined(separator: "\n")
            if !text.isEmpty { return text }
        }
        if let text = result["text"] as? String { return text }
    }
    if let err = json["error"] as? [String: Any] {
        return "[MCP Error] \(err["message"] as? String ?? "Unknown")"
    }
    return json.description
}

// MARK: - URLSession without timeout (shared across MCP HTTP calls)

private let mcpNoTimeoutSession: URLSession = {
    let cfg = URLSessionConfiguration.default
    cfg.timeoutIntervalForRequest  = .infinity
    cfg.timeoutIntervalForResource = .infinity
    return URLSession(configuration: cfg)
}()

// MARK: - StdioSession
//
// Persistent actor — owns one Process per MCP server.
// Serialises all tool calls via Swift's actor model (no mutex needed).

actor StdioSession {

    private let server: MCPServerConfig

    private var process: Process?
    private var stdinHandle: FileHandle?
    private var stdoutHandle: FileHandle?
    private var nextId: Int = 10        // RPC IDs; 1-2 reserved for handshake
    private var isReady = false

    // AsyncStream continuation — readabilityHandler pushes chunks here.
    // NOT weak (Continuation is a struct, not a class).
    private var continuation: AsyncStream<Data>.Continuation?

    init(server: MCPServerConfig) {
        self.server = server
    }

    // ── Public API ──────────────────────────────────────────────────────────

    func ensureRunning() async throws {
        if isReady, let p = process, p.isRunning { return }
        try await startProcess()
    }

    /// Send one JSON-RPC request and return the matching response.
    /// If the process has crashed it is restarted transparently (once).
    func callTool(method: String, params: [String: Any], deadline: Date) async throws -> [String: Any] {
        try await ensureRunning()

        let rpcId = nextId
        nextId += 1

        let req: [String: Any] = [
            "jsonrpc": "2.0", "id": rpcId,
            "method": method, "params": params
        ]

        if !safeWrite(req) {
            // Likely crashed — restart once and retry
            try await startProcess()
            guard safeWrite(req) else {
                throw MCPError.processLaunchFailed("Write failed after auto-restart")
            }
        }

        return try await readResponse(rpcId: rpcId, deadline: deadline)
    }

    func terminate() {
        stdoutHandle?.readabilityHandler = nil
        continuation?.finish()
        continuation = nil
        process?.terminate()
        process = nil
        isReady = false
    }

    // ── Private: process lifecycle ──────────────────────────────────────────

    private func startProcess() async throws {
        // Tear down stale state
        process?.terminate()
        process = nil
        stdinHandle = nil
        stdoutHandle = nil
        isReady = false
        continuation?.finish()
        continuation = nil

        _ = StdioSession.sigpipeInstalled

        let p = Process()
        let stdinPipe  = Pipe()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments     = tokenise(server.command)

        // ENV 構築: プロセス ENV + PATH 拡張 + Keychain 解決済み API キー
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:" + (env["PATH"] ?? "")
        // Keychain から解決した値を注入（空の env vars を上書き）
        let resolvedEnv = MCPKeychainStore.resolvedEnv(for: server)
        resolvedEnv.forEach { env[$0.key] = $0.value }
        p.environment = env

        p.standardInput  = stdinPipe
        p.standardOutput = stdoutPipe
        p.standardError  = stderrPipe
        p.terminationHandler = { [weak self] _ in
            Task { await self?.handleTermination() }
        }

        do { try p.run() } catch {
            throw MCPError.processLaunchFailed(error.localizedDescription)
        }

        process      = p
        stdinHandle  = stdinPipe.fileHandleForWriting
        stdoutHandle = stdoutPipe.fileHandleForReading

        // Wire readabilityHandler → AsyncStream
        // Note: cont is a VALUE (struct) so we capture it directly, not with [weak].
        let (stream, cont) = AsyncStream<Data>.makeStream()
        self.continuation = cont

        stdoutPipe.fileHandleForReading.readabilityHandler = { fh in
            let chunk = fh.availableData
            if chunk.isEmpty {
                cont.finish()
                fh.readabilityHandler = nil
            } else {
                cont.yield(chunk)
            }
        }

        // Perform MCP initialize handshake (up to 20 s for npx cold-start / Puppeteer)
        try await performHandshake(stream: stream, maxWait: 20.0)
        isReady = true
    }

    private func performHandshake(stream: AsyncStream<Data>, maxWait: Double) async throws {
        let initReq: [String: Any] = [
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": [
                "protocolVersion": "2024-11-05",
                "capabilities":    ["tools": [:], "resources": [:]],
                "clientInfo":      ["name": "Verantyx", "version": "0.1"]
            ]
        ]
        guard safeWrite(initReq) else {
            throw MCPError.processLaunchFailed("Process exited before initialize")
        }

        var buf = Data()
        let deadline = Date().addingTimeInterval(maxWait)

        outer: for await chunk in stream {
            buf.append(chunk)
            let (lines, remainder) = splitLines(buf)
            buf = remainder
            for line in lines {
                if let json = parseJSON(line), let id = json["id"] as? Int, id == 1 {
                    break outer
                }
            }
            if Date() > deadline {
                throw MCPError.processLaunchFailed(
                    "Initialize timed out (>\(Int(maxWait))s). Server may not be installed.")
            }
            try Task.checkCancellation()
        }

        let notif: [String: Any] = ["jsonrpc": "2.0", "method": "notifications/initialized"]
        safeWrite(notif)
    }

    // ── Private: response reading ───────────────────────────────────────────

    /// Drain the stream after each call by reassigning the readabilityHandler to a
    /// fresh AsyncStream so each callTool() gets its own isolated iterator.
    private func readResponse(rpcId: Int, deadline: Date) async throws -> [String: Any] {
        guard let fh = stdoutHandle else { throw MCPError.noResponse }

        // Create a fresh stream for this specific call's response
        let (stream, freshCont) = AsyncStream<Data>.makeStream()
        self.continuation = freshCont

        fh.readabilityHandler = { handle in
            let chunk = handle.availableData
            if chunk.isEmpty {
                freshCont.finish()
                handle.readabilityHandler = nil
            } else {
                freshCont.yield(chunk)
            }
        }

        var buf = Data()
        for await chunk in stream {
            buf.append(chunk)
            let (lines, remainder) = splitLines(buf)
            buf = remainder
            for line in lines {
                if let json = parseJSON(line),
                   let idValue = json["id"] {
                    // Compare both Int and String forms of the id
                    if "\(idValue)" == "\(rpcId)" {
                        return json
                    }
                }
            }
            if Date() > deadline { throw MCPError.timeout }
            try Task.checkCancellation()
        }

        throw MCPError.noResponse
    }

    // ── Private: termination handler ────────────────────────────────────────

    private func handleTermination() {
        isReady = false
        continuation?.finish()
        continuation = nil
        stdoutHandle?.readabilityHandler = nil
    }

    // ── Private: helpers ────────────────────────────────────────────────────

    @discardableResult
    private func safeWrite(_ obj: [String: Any]) -> Bool {
        guard let p = process, p.isRunning, let fh = stdinHandle else { return false }
        guard let data = try? JSONSerialization.data(withJSONObject: obj),
              let line = String(data: data, encoding: .utf8),
              let bytes = (line + "\n").data(using: .utf8) else { return false }
        do {
            try fh.write(contentsOf: bytes)
            return true
        } catch { return false }
    }

    private func parseJSON(_ s: String) -> [String: Any]? {
        guard let d = s.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: d) as? [String: Any]
    }

    private func splitLines(_ data: Data) -> ([String], Data) {
        guard let str = String(data: data, encoding: .utf8) else { return ([], data) }
        var parts = str.components(separatedBy: "\n")
        let remainder = parts.removeLast()         // last element may be partial
        let complete = parts.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        return (complete, remainder.data(using: .utf8) ?? Data())
    }

    private func tokenise(_ command: String) -> [String] {
        var tokens: [String] = []
        var current = ""
        var inQ: Character? = nil
        for ch in command {
            if let q = inQ {
                if ch == q { inQ = nil } else { current.append(ch) }
            } else if ch == "\"" || ch == "'" {
                inQ = ch
            } else if ch == " " {
                if !current.isEmpty { tokens.append(current); current = "" }
            } else {
                current.append(ch)
            }
        }
        if !current.isEmpty { tokens.append(current) }
        return tokens
    }

    private static let sigpipeInstalled: Bool = {
        signal(SIGPIPE, SIG_IGN)
        return true
    }()
}

// MARK: - MCPEngine

@MainActor
final class MCPEngine: ObservableObject {

    static let shared = MCPEngine()

    // MARK: - Published state

    @Published var servers: [MCPServerConfig] = [] {
        didSet { saveServers() }
    }
    @Published var connectedTools: [MCPTool] = []
    @Published var activeCall: MCPCallRecord?
    @Published var callHistory: [MCPCallRecord] = []
    @Published var connectionStatus: [UUID: ConnectionStatus] = [:]

    enum ConnectionStatus { case disconnected, connecting, connected, error(String) }

    @Published var currentExecutionMode: MCPServerConfig.ExecutionMode = .human

    // One persistent session per server UUID
    private var stdioSessions: [UUID: StdioSession] = [:]

    private static let storageKey = "mcp_servers_v1"

    func setMode(_ mode: MCPServerConfig.ExecutionMode) {
        currentExecutionMode = mode
    }

    init() { loadServers() }

    // MARK: - Server CRUD

    func addServer(_ config: MCPServerConfig) { servers.append(config) }

    func removeServer(id: UUID) {
        if let session = stdioSessions.removeValue(forKey: id) {
            Task { await session.terminate() }
        }
        // Remove tools before removing the server entry
        if let name = servers.first(where: { $0.id == id })?.name {
            connectedTools.removeAll { $0.serverName == name }
        }
        servers.removeAll { $0.id == id }
        connectionStatus.removeValue(forKey: id)
    }

    func updateServer(_ config: MCPServerConfig) {
        if let idx = servers.firstIndex(where: { $0.id == config.id }) {
            servers[idx] = config
        }
    }

    /// サーバーのプロセスを強制終了して再接続する（再起動ボタン）
    func restartServer(id: UUID) async {
        // 既存セッションをクリーンに終了
        if let session = stdioSessions.removeValue(forKey: id) {
            await session.terminate()
        }
        connectionStatus[id] = .disconnected
        // ツールリストをクリアして再取得
        if let server = servers.first(where: { $0.id == id }) {
            connectedTools.removeAll { $0.serverName == server.name }
            await connect(server: server)
        }
    }

    /// 全サーバーをリロード（新たに接続されたものを含めて再スキャン）
    func reloadAll() async {
        // 全セッション終了
        for (_, session) in stdioSessions {
            await session.terminate()
        }
        stdioSessions.removeAll()
        connectedTools.removeAll()
        connectionStatus.removeAll()
        await connectAll()
    }

    // MARK: - Connect / discover tools

    func connectAll() async {
        for server in servers where server.isEnabled {
            await connect(server: server)
        }
    }

    func connect(server: MCPServerConfig) async {
        connectionStatus[server.id] = .connecting
        do {
            let tools = try await discoverTools(server: server)
            connectedTools.removeAll { $0.serverName == server.name }
            connectedTools.append(contentsOf: tools)
            connectionStatus[server.id] = .connected
        } catch {
            connectionStatus[server.id] = .error(error.localizedDescription)
        }
    }

    func disconnect(serverId: UUID) {
        if let session = stdioSessions.removeValue(forKey: serverId) {
            Task { await session.terminate() }
        }
        if let server = servers.first(where: { $0.id == serverId }) {
            connectedTools.removeAll { $0.serverName == server.name }
        }
        connectionStatus[serverId] = .disconnected
    }

    // MARK: - Tool execution

    func callTool(serverName: String, toolName: String,
                  arguments: [String: Any],
                  mode: MCPServerConfig.ExecutionMode? = nil) async -> String {
        let resolvedMode = mode ?? currentExecutionMode
        guard let server = servers.first(where: { $0.name == serverName && $0.isEnabled }) else {
            return "[MCP] Server '\(serverName)' not found or disabled"
        }

        var record = MCPCallRecord(serverName: serverName, toolName: toolName,
                                   startTime: Date(), status: .running)
        activeCall = record

        NotificationCenter.default.post(
            name: .mcpToolCalled, object: nil,
            userInfo: ["server": serverName, "tool": toolName]
        )

        // Obtain (or create) the persistent session before entering the detached task
        let session: StdioSession? = server.transport == .stdio
            ? getOrCreateSession(for: server)
            : nil

        let execTask = Task<String, Error>.detached(priority: .userInitiated) {
            let deadline: Date = resolvedMode == .human
                ? Date().addingTimeInterval(60)
                : Date.distantFuture

            var finalArgs = arguments
            if serverName == "tool-search-oss" {
                let allTools = await MainActor.run {
                    self.connectedTools.filter { $0.serverName != "tool-search-oss" }
                }
                let toolsList = allTools.map { t -> [String: Any] in
                    var dict: [String: Any] = [
                        "name": "\(t.serverName).\(t.name)",
                        "description": t.description
                    ]
                    // inputSchema is [String: AnyCodable]. Convert to [String: Any] via JSONSerialization
                    if let data = try? JSONEncoder().encode(t.inputSchema),
                       let schema = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        dict["inputSchema"] = schema
                    }
                    return dict
                }
                finalArgs["tools"] = toolsList
            }

            let params: [String: Any] = ["name": toolName, "arguments": finalArgs]

            switch server.transport {
            case .stdio:
                guard let s = session else {
                    throw MCPError.processLaunchFailed("No session")
                }
                let resp = try await s.callTool(
                    method: "tools/call", params: params, deadline: deadline)
                return mcpExtractText(from: resp)

            case .http:
                guard let url = URL(string: server.url + "/tools/call") else {
                    throw MCPError.invalidURL
                }
                var req = URLRequest(url: url)
                req.httpMethod = "POST"
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                req.httpBody = try? JSONSerialization.data(withJSONObject: [
                    "jsonrpc": "2.0", "id": UUID().uuidString,
                    "method": "tools/call", "params": params
                ])
                // mcpNoTimeoutSession: no URLSession-level timeout.
                // Human-mode deadline is enforced by Task.cancel() below.
                let (data, _) = try await mcpNoTimeoutSession.data(for: req)
                let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
                return mcpExtractText(from: json)
            }
        }

        record.task = execTask

        // Human mode: fire a cancellation timer
        if resolvedMode == .human {
            Task {
                try? await Task.sleep(nanoseconds: 60_000_000_000)
                execTask.cancel()
            }
        }

        do {
            let result = try await execTask.value
            finishRecord(record, status: .completed)
            return result
        } catch is CancellationError {
            finishRecord(record, status: .cancelled)
            return "[MCP] Tool call cancelled"
        } catch MCPError.timeout {
            execTask.cancel()
            finishRecord(record, status: .timedOut)
            return "[MCP] Tool '\(toolName)' timed out"
        } catch {
            finishRecord(record, status: .failed(error.localizedDescription))
            return "[MCP] Error: \(error.localizedDescription)"
        }
    }

    /// Kill Switch — immediately cancels the in-flight tool call
    func killActiveCall() {
        activeCall?.task?.cancel()
        if var a = activeCall {
            a.status = .cancelled
            callHistory.insert(a, at: 0)
        }
        activeCall = nil
    }

    // MARK: - Private helpers

    private func getOrCreateSession(for server: MCPServerConfig) -> StdioSession {
        if let s = stdioSessions[server.id] { return s }
        let s = StdioSession(server: server)
        stdioSessions[server.id] = s
        return s
    }

    private func finishRecord(_ record: MCPCallRecord, status: MCPCallRecord.Status) {
        var r = record
        r.status = status
        callHistory.insert(r, at: 0)
        if callHistory.count > 100 { callHistory.removeLast(50) }
        activeCall = nil
    }

    private func discoverTools(server: MCPServerConfig) async throws -> [MCPTool] {
        switch server.transport {
        case .stdio:
            let session = getOrCreateSession(for: server)
            // 30 s for first cold-start (npx may need to download the package)
            let deadline = Date().addingTimeInterval(30)
            let resp = try await session.callTool(
                method: "tools/list", params: [:], deadline: deadline)
            return parseTools(from: resp, serverName: server.name)

        case .http:
            guard let url = URL(string: server.url + "/tools/list") else {
                throw MCPError.invalidURL
            }
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try? JSONSerialization.data(withJSONObject: [
                "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": [:]
            ])
            req.timeoutInterval = 15
            let (data, _) = try await URLSession.shared.data(for: req)
            let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
            return parseTools(from: json, serverName: server.name)
        }
    }

    private func parseTools(from json: [String: Any], serverName: String) -> [MCPTool] {
        guard let result = json["result"] as? [String: Any],
              let toolsList = result["tools"] as? [[String: Any]] else { return [] }
        return toolsList.compactMap { t in
            guard let name = t["name"] as? String else { return nil }
            let desc = t["description"] as? String ?? ""
            return MCPTool(name: name, description: desc, serverName: serverName)
        }
    }

    // MARK: - Persistence

    private func saveServers() {
        if let data = try? JSONEncoder().encode(servers) {
            UserDefaults.standard.set(data, forKey: Self.storageKey)
        }
    }

    private func loadServers() {
        if let data = UserDefaults.standard.data(forKey: Self.storageKey),
           let decoded = try? JSONDecoder().decode([MCPServerConfig].self, from: data) {
            servers = decoded
        }
        
        // ── Auto-inject verantyx-compiler if missing ──
        if !servers.contains(where: { $0.name == "verantyx-compiler" }) {
            let config = MCPServerConfig(
                name: "verantyx-compiler",
                transport: .stdio,
                command: "sh -c \"cd /Users/motonishikoudai/verantyx-cli && /usr/local/bin/node --import tsx cortex/src/mcp/server.ts\"",
                mode: .ai
            )
            servers.append(config)
            Task { await self.connect(server: config) }
        }

        // ── Auto-inject tool-search-oss if missing ──
        if !servers.contains(where: { $0.name == "tool-search-oss" }) {
            let config = MCPServerConfig(
                name: "tool-search-oss",
                transport: .stdio,
                command: "sh -c \"cd /Users/motonishikoudai/verantyx-cli/tools && /usr/local/bin/node --import tsx/esm src/server.ts\"",
                mode: .ai
            )
            servers.append(config)
            Task { await self.connect(server: config) }
        }

        saveServers()
    }
}

// MARK: - Errors

enum MCPError: LocalizedError {
    case timeout
    case invalidURL
    case noResponse
    case decodingFailed
    case processLaunchFailed(String)

    var errorDescription: String? {
        switch self {
        case .timeout:                    return "MCP tool call timed out"
        case .invalidURL:                 return "Invalid MCP server URL"
        case .noResponse:                 return "No response from MCP server"
        case .decodingFailed:             return "Failed to decode MCP response"
        case .processLaunchFailed(let r): return "MCP process failed to launch: \(r)"
        }
    }
}

// MARK: - Notification

extension Notification.Name {
    static let mcpToolCalled = Notification.Name("mcpToolCalled")
}
