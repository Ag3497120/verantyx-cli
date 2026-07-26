import SwiftUI

// MARK: - VeraSaveApprovalView
// Vera-α layer: preview of what's about to be saved, before it's saved.
// Same pattern as FileApprovalView (MainSplitView.swift) — suspends
// AgentLoop via CheckedContinuation until the user decides.
//
// Two different trust levels shown side by side, matching how the two
// pieces are actually handled once approved: the user's own prompt goes
// straight into Vera's trusted store (`remember`); the AI's response goes
// into Vera's AI-output quarantine (`propose_ai_facts` — queued, still
// needs a SEPARATE human accept/reject later via `vera review-ai-facts`,
// this popup is not that review step, just the "should this even be
// queued" gate).

struct VeraSaveApprovalView: View {
    @EnvironmentObject var app: AppState
    let req: VeraSaveApprovalRequest

    var body: some View {
        VStack(spacing: 0) {

            // ─ Header ───────────────────────────────────────────────────
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color(red: 0.3, green: 0.9, blue: 0.7).opacity(0.18))
                        .frame(width: 40, height: 40)
                    Image(systemName: "checkmark.seal")
                        .font(.system(size: 18))
                        .foregroundStyle(Color(red: 0.3, green: 0.9, blue: 0.7))
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text(app.t("Save this turn to Vera?", "この内容を Vera に保存しますか？"))
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Color(red: 0.92, green: 0.92, blue: 0.98))
                    Text(app.t("Vera-α memory layer", "Vera-α 記憶レイヤー"))
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(Color(red: 0.55, green: 0.65, blue: 0.85))
                }

                Spacer()
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 14)

            Divider().opacity(0.25)

            // ─ Content preview ────────────────────────────────────────────
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    previewSection(
                        badge: app.t("USER — remember()", "USER — remember()"),
                        badgeColor: Color(red: 0.4, green: 0.7, blue: 1.0),
                        note: app.t("Goes straight into Vera's trusted store.",
                                    "そのまま Vera の信頼済みストアに入ります。"),
                        text: req.userPrompt
                    )
                    previewSection(
                        badge: app.t("AI — propose_ai_facts() (quarantined)", "AI — propose_ai_facts()（検疫）"),
                        badgeColor: Color(red: 1.0, green: 0.65, blue: 0.2),
                        note: app.t("Only queued for later human review — never auto-trusted.",
                                    "レビュー待ちで検疫キューに入るだけです。自動的には信頼されません。"),
                        text: req.aiResponse
                    )
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Color(red: 0.06, green: 0.06, blue: 0.09))
            .frame(maxHeight: .infinity)

            Divider().opacity(0.25)

            // ─ Action buttons ───────────────────────────────────────────
            HStack(spacing: 12) {
                Spacer()

                Button {
                    app.rejectVeraSave()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "xmark")
                            .font(.system(size: 11, weight: .semibold))
                        Text(app.t("Discard", "破棄"))
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .foregroundStyle(Color(red: 0.9, green: 0.4, blue: 0.4))
                    .padding(.horizontal, 20).padding(.vertical, 9)
                    .contentShape(Rectangle())
                    .background(Color(red: 0.32, green: 0.10, blue: 0.10).opacity(0.7),
                                in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .stroke(Color(red: 0.9, green: 0.4, blue: 0.4).opacity(0.5), lineWidth: 1))
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .keyboardShortcut(.escape)

                Button {
                    app.approveVeraSave()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark")
                            .font(.system(size: 11, weight: .semibold))
                        Text(app.t("Save", "保存"))
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .foregroundStyle(Color(red: 0.3, green: 0.92, blue: 0.5))
                    .padding(.horizontal, 20).padding(.vertical, 9)
                    .contentShape(Rectangle())
                    .background(Color(red: 0.10, green: 0.28, blue: 0.15).opacity(0.8),
                                in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .stroke(Color(red: 0.3, green: 0.92, blue: 0.5).opacity(0.5), lineWidth: 1))
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .keyboardShortcut(.return, modifiers: .command)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
            .background(Color(red: 0.11, green: 0.11, blue: 0.15))
        }
        .background(Color(red: 0.09, green: 0.09, blue: 0.12))
        .frame(minWidth: 640, idealWidth: 760, maxWidth: 960,
               minHeight: 420, idealHeight: 560, maxHeight: 720)
    }

    @ViewBuilder
    private func previewSection(badge: String, badgeColor: Color, note: String, text: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text(badge)
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundStyle(badgeColor)
                    .padding(.horizontal, 7).padding(.vertical, 3)
                    .background(Capsule().fill(badgeColor.opacity(0.15)))
            }
            Text(note)
                .font(.system(size: 10))
                .foregroundStyle(Color(red: 0.5, green: 0.5, blue: 0.65))
            Text(text.isEmpty ? "(empty)" : text)
                .font(.system(size: 12, design: .monospaced))
                .foregroundStyle(Color(red: 0.85, green: 0.85, blue: 0.9))
                .textSelection(.enabled)
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(red: 0.12, green: 0.12, blue: 0.16),
                            in: RoundedRectangle(cornerRadius: 6))
        }
    }
}
