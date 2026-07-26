import Foundation

// MARK: - VeraMemoryBridge
//
// Bridges the "Vera-α" `JCrossLayer` option to Vera's own deterministic,
// typed-verdict knowledge store, run as its own MCP server ("vera-memory",
// auto-registered in `MCPEngine.loadServers()` — `python3.11 -m
// verantyx.cli mcp` against the Verantyx-Vera-alpha checkout).
//
// Deliberately NOT wired through CortexEngine or SessionMemoryArchiver's
// existing l1/l1.5/l2/l3 machinery — those read/write .jcross node files;
// Vera reads/writes its own store instead. Selecting "Vera-α" as a
// session's `activeLayer` routes memory through here at the exact call
// sites in `AgentLoop.run()` that would otherwise call
// `SessionMemoryArchiver.semanticSearch(layer:)` — same position as
// l1/l1.5/l2/l3, mutually exclusive per session, never both at once. This
// is also why it's opt-in per session rather than always-on: an earlier
// pass wired Vera into CortexEngine's always-called `buildMemoryPrompt`/
// `extractAndStore`, which paid the MCP round-trip cost on every single
// turn in every mode — reverted in favor of this, which only runs for
// sessions that actually selected the Vera-α layer.
//
// Saving is unconditional application code that runs regardless of what
// the model does — not an LLM tool-call the model has to decide to make.
// A forced system-prompt instruction ("please remember this") is
// unreliable, especially for small local models, which is exactly why
// this exists instead of just exposing Vera's MCP tools to the model's
// own tool-calling loop and hoping it calls them.
@MainActor
enum VeraMemoryBridge {

    private static let serverName = "vera-memory"

    /// Called once per completed turn (after the AI's response is ready).
    /// Shows a preview popup — `VeraSaveApprovalView`, gated by
    /// `AppState.pendingVeraSave` — and only calls Vera at all if the
    /// human taps "Save". This is still application code, not an
    /// LLM-decided tool call (the popup ALWAYS appears every turn on a
    /// Vera-α session; what's optional is the human's decision, not
    /// whether the check happens). On "Save": the user's prompt goes
    /// straight into Vera's trusted store (`remember`); the AI's response
    /// goes through Vera's AI-output quarantine (`propose_ai_facts`) —
    /// never auto-promoted, still needs a later, separate human
    /// accept/reject via `vera review-ai-facts`. This popup is only the
    /// "queue it at all" gate, not that final review step.
    static func requestSaveApproval(userPrompt: String, aiResponse: String) async {
        let prompt = userPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        let response = aiResponse.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !prompt.isEmpty || !response.isEmpty else { return }

        let req = VeraSaveApprovalRequest(userPrompt: prompt, aiResponse: response)
        AppState.shared?.pendingVeraSave = req
        guard await req.waitForDecision() else { return }

        if !prompt.isEmpty {
            _ = await MCPEngine.shared.callTool(
                serverName: serverName, toolName: "remember",
                arguments: ["sentence": String(prompt.prefix(500))],
                mode: .human
            )
        }
        if !response.isEmpty {
            _ = await MCPEngine.shared.callTool(
                serverName: serverName, toolName: "propose_ai_facts",
                arguments: ["text": response, "source": "verantyx_ide_vera_layer"],
                mode: .human
            )
        }

        // Code changes go through `record_code_change`, NOT
        // `propose_ai_facts` — see extractCodeChanges' doc comment for why
        // (its sentence-splitter mangles diff/patch syntax).
        for change in extractCodeChanges(from: response) {
            _ = await MCPEngine.shared.callTool(
                serverName: serverName, toolName: "record_code_change",
                arguments: ["file_path": change.file, "description": change.description],
                mode: .human
            )
        }
    }

    /// Same bracket-tag markers CortexEngine.extractAndStore already
    /// scans for (`[WRITE: ...]`, `[PATCH_FILE: ...]`, `[APPLY_PATCH: ...]`)
    /// — reused here rather than re-deriving them, and routed to
    /// `record_code_change` instead of the sentence-splitting
    /// `propose_ai_facts`: a unified diff or a bracket tag like
    /// `[WRITE: billing.py]` contains no real sentence terminators except
    /// stray periods in file extensions/decimals, so Vera's `.`/`!`/`?`
    /// sentence splitter chops it at nonsensical points instead of
    /// dropping or preserving it cleanly.
    private static func extractCodeChanges(from response: String) -> [(file: String, description: String)] {
        let patterns = [
            (#"\[WRITE:\s*([^\]]+)\]"#, "written"),
            (#"\[PATCH_FILE:\s*([^\]]+)\]"#, "patched"),
            (#"\[APPLY_PATCH:\s*([^\]]+)\]"#, "patch applied"),
        ]
        var results: [(file: String, description: String)] = []
        for (pattern, verb) in patterns {
            guard let regex = try? NSRegularExpression(pattern: pattern) else { continue }
            let matches = regex.matches(in: response, range: NSRange(response.startIndex..., in: response))
            for m in matches {
                guard let r = Range(m.range(at: 1), in: response) else { continue }
                let file = String(response[r]).trimmingCharacters(in: .whitespaces)
                guard !file.isEmpty else { continue }
                results.append((file: file, description: verb))
            }
        }
        return results
    }

    // MARK: - ask() — single source of truth for every Vera query

    struct AskResult {
        let verdict: String
        let core: String?
        let text: String?
        let agreeFrac: Double?
    }

    /// Every other function in this bridge that reads from Vera goes
    /// through this one call site. Shape from
    /// `verantyx.consensus.Verdict.as_dict()` via the `ask` MCP tool:
    /// {"verdict": "ANSWER"|"UNKNOWN_*", "core": str, "text": str,
    /// "agree_frac": float, ...} — verified against a live
    /// `python3.11 -m verantyx.cli mcp` process, not guessed.
    private static func askRaw(_ query: String) async -> AskResult {
        let raw = await MCPEngine.shared.callTool(
            serverName: serverName, toolName: "ask",
            arguments: ["query": query], mode: .human
        )
        guard
            let data = raw.data(using: .utf8),
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let verdict = obj["verdict"] as? String
        else { return AskResult(verdict: "UNKNOWN_CALL_FAILED", core: nil, text: nil, agreeFrac: nil) }

        let result = AskResult(
            verdict: verdict,
            core: obj["core"] as? String,
            text: obj["text"] as? String,
            agreeFrac: obj["agree_frac"] as? Double
        )
        if verdict == "ANSWER", let core = result.core {
            await VeraSkillForge.recordAnswerAndMaybeForge(core: core)
        }
        return result
    }

    /// Same position as `SessionMemoryArchiver.semanticSearch(layer:)` for
    /// l1/l1.5/l2/l3 — call this instead when a session's `activeLayer` is
    /// `.vera`. Only injects a section when Vera itself returns a typed
    /// ANSWER verdict; UNKNOWN_* or any call failure (server not yet
    /// connected) contributes nothing, same fail-open behavior every other
    /// layer already has on an empty match — never a hard error in the
    /// agent loop.
    static func recall(for query: String) async -> String {
        let r = await askRaw(query)
        guard r.verdict == "ANSWER", let core = r.core else { return "" }
        let text = r.text ?? ""
        let agreeFrac = r.agreeFrac.map { String(format: "%.2f", $0) } ?? "?"

        return """

        [VERA MEMORY — deterministic, typed-verdict store (ANSWER, not a guess)]
          🧩 \(core): \(text)  (agreement: \(agreeFrac))
        [/VERA MEMORY]
        """
    }

    /// Minimum `agree_frac` required to skip the LLM entirely. Deliberately
    /// high — this trades a rarer fast-path for never confidently
    /// short-circuiting on a shaky verdict. Below this, the normal path
    /// (LLM call, with Vera's answer injected as context via `recall`)
    /// still runs — this is a strict ADDITION to the existing path, never
    /// a replacement for it.
    static let directAnswerThreshold = 0.9

    /// Skips the local LLM call entirely for a high-confidence, already-
    /// grounded ANSWER. Returns nil (meaning: fall through to the normal
    /// LLM turn) on anything less than a clean, confident ANSWER —
    /// UNKNOWN_*, a call failure, or an ANSWER below `directAnswerThreshold`
    /// all fall through rather than risk answering wrong with false
    /// confidence.
    static func tryDirectAnswer(for query: String) async -> String? {
        let r = await askRaw(query)
        guard
            r.verdict == "ANSWER",
            let core = r.core, let text = r.text,
            let agree = r.agreeFrac, agree >= directAnswerThreshold
        else { return nil }

        return """
        🧩 \(text)

        (Vera direct answer — core: \(core), agreement: \(String(format: "%.2f", agree)) — no LLM call was made)
        """
    }
}
