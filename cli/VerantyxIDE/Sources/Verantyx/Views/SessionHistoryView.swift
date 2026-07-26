import SwiftUI

// MARK: - SessionHistoryView
// Sidebar panel showing past chat sessions with JCross layer switcher.
// Appears as a sheet or as the "History" tab in AgentChatView.

struct SessionHistoryView: View {
    @EnvironmentObject var app: AppState
    @State private var editingId: UUID? = nil
    @State private var editTitle: String = ""
    @State private var confirmDeleteId: UUID? = nil
    @State private var showLayerPickerFor: UUID? = nil

    var body: some View {
        VStack(spacing: 0) {
            // ── Header ─────────────────────────────────────────────
            HStack {
                Image(systemName: "clock.arrow.circlepath")
                    .font(.system(size: 11))
                    .foregroundStyle(Color(red: 0.55, green: 0.55, blue: 0.75))
                Text(app.t("Session History", "セッション履歴"))
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color(red: 0.85, green: 0.85, blue: 0.95))
                Spacer()
                Button {
                    app.newChatSession()
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 1.0))
                }
                .contentShape(Rectangle())
                .buttonStyle(.plain)
                .help(app.t("New session", "新しいセッション"))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)

            Divider().opacity(0.3)

            // ── Session List ────────────────────────────────────────
            if app.sessions.sessions.isEmpty {
                emptyState
            } else {
                ScrollView {
                    LazyVStack(spacing: 2) {
                        ForEach(app.sessions.sessions) { session in
                            SessionRowView(
                                session: session,
                                isActive: session.id == app.sessions.activeSessionId,
                                editingId: $editingId,
                                editTitle: $editTitle,
                                showLayerPickerFor: $showLayerPickerFor,
                                confirmDeleteId: $confirmDeleteId
                            )
                            .environmentObject(app)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .background(Color(red: 0.11, green: 0.11, blue: 0.14))
        .confirmationDialog(
            app.t("Delete this session?", "セッションを削除しますか？"),
            isPresented: Binding(
                get: { confirmDeleteId != nil },
                set: { if !$0 { confirmDeleteId = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(app.t("Delete", "削除"), role: .destructive) {
                if let id = confirmDeleteId { app.sessions.delete(id) }
                confirmDeleteId = nil
            }
            Button(app.t("Cancel", "キャンセル"), role: .cancel) { confirmDeleteId = nil }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 32))
                .foregroundStyle(Color(red: 0.3, green: 0.3, blue: 0.4))
            Text(app.t("No sessions yet", "まだセッションがありません"))
                .font(.system(size: 12))
                .foregroundStyle(Color(red: 0.45, green: 0.45, blue: 0.55))
            Text(app.t("Sessions are saved automatically when you start a chat.",
                       "チャットを開始すると自動的に保存されます"))
                .font(.system(size: 11))
                .foregroundStyle(Color(red: 0.35, green: 0.35, blue: 0.45))
                .multilineTextAlignment(.center)
            Spacer()
        }
        .padding()
    }
}

// MARK: - Session Row

struct SessionRowView: View {
    let session: ChatSession
    let isActive: Bool
    @Binding var editingId: UUID?
    @Binding var editTitle: String
    @Binding var showLayerPickerFor: UUID?
    @Binding var confirmDeleteId: UUID?

    @EnvironmentObject var app: AppState

    private var isEditing: Bool { editingId == session.id }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                // Active indicator
                RoundedRectangle(cornerRadius: 2)
                    .fill(isActive
                          ? Color(red: 0.4, green: 0.7, blue: 1.0)
                          : Color.clear)
                    .frame(width: 3)
                    .padding(.vertical, 4)

                VStack(alignment: .leading, spacing: 2) {
                    // Title (editable)
                    if isEditing {
                        TextField(app.t("Session name", "セッション名"), text: $editTitle)
                            .textFieldStyle(.plain)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(Color.white)
                            .onSubmit {
                                app.sessions.rename(session.id, to: editTitle)
                                editingId = nil
                            }
                    } else {
                        Text(session.title)
                            .font(.system(size: 12, weight: isActive ? .semibold : .regular))
                            .foregroundStyle(isActive
                                             ? Color.white
                                             : Color(red: 0.75, green: 0.75, blue: 0.85))
                            .lineLimit(1)
                    }

                    HStack(spacing: 6) {
                        // Date
                        Text(session.updatedAt, style: .relative)
                            .font(.system(size: 10))
                            .foregroundStyle(Color(red: 0.45, green: 0.45, blue: 0.55))

                        // Workspace
                        if let wp = session.workspacePath {
                            Text("·")
                                .foregroundStyle(Color(red: 0.4, green: 0.4, blue: 0.5))
                            Text(URL(fileURLWithPath: wp).lastPathComponent)
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundStyle(Color(red: 0.4, green: 0.7, blue: 0.5))
                                .lineLimit(1)
                        }

                        // Memory nodes count
                        if !session.memoryNodeIds.isEmpty {
                            Text("·")
                                .foregroundStyle(Color(red: 0.4, green: 0.4, blue: 0.5))
                            Image(systemName: "brain")
                                .font(.system(size: 9))
                                .foregroundStyle(Color(red: 0.6, green: 0.5, blue: 0.9))
                            Text("\(session.memoryNodeIds.count)")
                                .font(.system(size: 10))
                                .foregroundStyle(Color(red: 0.6, green: 0.5, blue: 0.9))
                        }
                    }
                }

                Spacer()

                // Action buttons
                HStack(spacing: 4) {
                    // Layer badge
                    layerBadge

                    // Rename
                    Button {
                        editingId = session.id
                        editTitle = session.title
                    } label: {
                        Image(systemName: "pencil")
                            .font(.system(size: 10))
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .foregroundStyle(Color(red: 0.5, green: 0.5, blue: 0.65))
                    .help(app.t("Rename", "名前を変更"))

                    // Delete
                    Button {
                        confirmDeleteId = session.id
                    } label: {
                        Image(systemName: "trash")
                            .font(.system(size: 10))
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .foregroundStyle(Color(red: 0.7, green: 0.35, blue: 0.35))
                    .help(app.t("Delete", "削除"))
                }
                .opacity(isActive ? 1 : 0.5)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(isActive
                          ? Color.white.opacity(0.06)
                          : Color.clear)
            )
            .contentShape(Rectangle())
            .onTapGesture {
                guard !isEditing else { return }
                app.restoreSession(session.id)
            }

            // Layer picker (inline, shown on active row)
            if isActive && showLayerPickerFor == session.id {
                layerPicker
                    .padding(.horizontal, 8)
                    .padding(.bottom, 4)
            }
        }
        .padding(.horizontal, 4)
    }

    // MARK: - Layer Badge

    private var layerBadge: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.15)) {
                showLayerPickerFor = showLayerPickerFor == session.id ? nil : session.id
            }
        } label: {
            Text(session.activeLayer.rawValue)
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundStyle(layerColor(session.activeLayer))
                .padding(.horizontal, 5)
                .padding(.vertical, 2)
                .background(
                    RoundedRectangle(cornerRadius: 3)
                        .fill(layerColor(session.activeLayer).opacity(0.15))
                        .overlay(
                            RoundedRectangle(cornerRadius: 3)
                                .stroke(layerColor(session.activeLayer).opacity(0.4), lineWidth: 0.5)
                        )
                )
        }
        .contentShape(Rectangle())
        .buttonStyle(.plain)
        .help(app.t("Memory layer: \(session.activeLayer.description)",
                    "記憶レイヤー: \(session.activeLayer.description)"))
    }

    // MARK: - Inline Layer Picker

    private var layerPicker: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(app.t("Switch memory layer", "記憶レイヤーを切り替え"))
                .font(.system(size: 10))
                .foregroundStyle(Color(red: 0.5, green: 0.5, blue: 0.65))

            HStack(spacing: 6) {
                ForEach(JCrossLayer.allCases) { layer in
                    Button {
                        app.sessions.setLayer(layer, for: session.id)
                        // If this is the active session, re-inject memory
                        if session.id == app.sessions.activeSessionId {
                            Task {
                                let injection = await app.sessions.buildMemoryInjection(for: session.id)
                                if !injection.isEmpty {
                                    await MainActor.run {
                                        app.messages.removeAll { $0.role == .system && $0.content.contains("[JCROSS MEMORY") }
                                        app.messages.insert(ChatMessage(role: .system, content: injection), at: 0)
                                    }
                                }
                            }
                        }
                        withAnimation { showLayerPickerFor = nil }
                    } label: {
                        VStack(spacing: 2) {
                            Image(systemName: layer.icon)
                                .font(.system(size: 11))
                            Text(layer.rawValue)
                                .font(.system(size: 9, weight: .semibold))
                        }
                        .foregroundStyle(session.activeLayer == layer
                                         ? layerColor(layer)
                                         : Color(red: 0.5, green: 0.5, blue: 0.65))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 5)
                        .background(
                            RoundedRectangle(cornerRadius: 5)
                                .fill(session.activeLayer == layer
                                      ? layerColor(layer).opacity(0.12)
                                      : Color.white.opacity(0.04))
                        )
                    }
                    .contentShape(Rectangle())
                    .buttonStyle(.plain)
                    .help(layer.description)
                }
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color(red: 0.14, green: 0.14, blue: 0.18))
                .shadow(color: .black.opacity(0.4), radius: 6, y: 2)
        )
    }

    private func layerColor(_ layer: JCrossLayer) -> Color {
        switch layer {
        case .l1:   return Color(red: 0.9, green: 0.7, blue: 0.3)
        case .l1_5: return Color(red: 0.4, green: 0.8, blue: 0.5)
        case .l2:   return Color(red: 0.4, green: 0.7, blue: 1.0)
        case .l3:   return Color(red: 0.8, green: 0.5, blue: 1.0)
        }
    }
}

// MARK: - Preview

#Preview {
    SessionHistoryView()
        .environmentObject(AppState())
        .frame(width: 260, height: 500)
}
