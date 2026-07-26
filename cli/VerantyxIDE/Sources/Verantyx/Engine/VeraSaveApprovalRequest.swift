import Foundation

// MARK: - VeraSaveApprovalRequest
// Vera-α layer gate — suspends AgentLoop via CheckedContinuation until the
// user taps "保存" or "破棄" in the save-preview sheet. Same pattern as
// FileApprovalRequest (see that file); this one gates a Vera memory write
// instead of a file write.
//
// Usage (AgentLoop / VeraMemoryBridge):
//   let req = VeraSaveApprovalRequest(userPrompt: p, aiResponse: r)
//   await MainActor.run { AppState.shared?.pendingVeraSave = req }
//   let approved = await req.waitForDecision()   // suspends here
//   if approved { /* remember(p) + propose_ai_facts(r) */ }

final class VeraSaveApprovalRequest: Identifiable, @unchecked Sendable {

    let id = UUID()
    let userPrompt: String
    let aiResponse: String

    private var continuation: CheckedContinuation<Bool, Never>?

    init(userPrompt: String, aiResponse: String) {
        self.userPrompt = userPrompt
        self.aiResponse = aiResponse
    }

    /// User tapped "保存".
    func approve() {
        continuation?.resume(returning: true)
        continuation = nil
    }

    /// User tapped "破棄".
    func reject() {
        continuation?.resume(returning: false)
        continuation = nil
    }

    /// Suspends AgentLoop until the user makes a decision.
    func waitForDecision() async -> Bool {
        await withCheckedContinuation { cont in
            self.continuation = cont
        }
    }
}
