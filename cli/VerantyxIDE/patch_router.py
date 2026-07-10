import re

with open('Sources/Verantyx/AppState.swift', 'r') as f:
    content = f.read()

target = """            // Route: Smart Router
            let isGatekeeperEnabled = forceBypassGatekeeper ? false : await MainActor.run(body: { GatekeeperModeState.shared.isEnabled })
            let isPipeline = await self.isPipelineIntent(text: text)

            if isGatekeeperEnabled && isPipeline {
                // Gatekeeper Mode → 新フロー (6軸IR → GraphPatch JSON → Vault復元)
                await GatekeeperChatBridge.shared.run(instruction: text, images: snapshotImages as! [String], appState: self)
            } else if isGatekeeperEnabled && !isPipeline {
                // Non-Coding Task during Gatekeeper Mode
                await MainActor.run {
                    let msg = self.t("🧭 Smart Router: Routing non-coding task to \(self.nonCodingTaskEngine.rawValue)",
                                     "🧭 Smart Router: 非コーディングタスクと判定されたため \(self.nonCodingTaskEngine.rawValue) にルーティングします")
                    self.addSystemMessage(msg)
                }
                
                let engine = await MainActor.run { self.nonCodingTaskEngine }
                if engine == .cloudDirect {
                    // Bypass Gatekeeper, send to Cloud Model
                    await runHybrid(instruction: text)
                } else {
                    // Local Agent
                    let history = Array(self.messages.dropLast())
                    await runAgentLoop(instruction: text,
                                       images: snapshotImages,
                                       files: snapshotFiles,
                                       previousMessages: history)
                }"""

replacement = """            // Route: UI-based Router
            let isGatekeeperEnabled = forceBypassGatekeeper ? false : await MainActor.run(body: { GatekeeperModeState.shared.isEnabled })
            // UI determines task type: IDE input -> Programming, Spotlight -> General
            let isProgrammingTask = !isSpotlight

            if isGatekeeperEnabled && isProgrammingTask {
                // Gatekeeper Mode → 新フロー (6軸IR → GraphPatch JSON → Vault復元)
                await GatekeeperChatBridge.shared.run(instruction: text, images: snapshotImages as! [String], appState: self)
            } else if isGatekeeperEnabled && !isProgrammingTask {
                // General Task during Gatekeeper Mode (Spotlight)
                await MainActor.run {
                    let msg = self.t("🧭 Spotlight Agent: Routing general task to \\(self.nonCodingTaskEngine.rawValue)",
                                     "🧭 Spotlight Agent: 汎用タスクとして \\(self.nonCodingTaskEngine.rawValue) にルーティングします")
                    self.addSystemMessage(msg)
                }
                
                let engine = await MainActor.run { self.nonCodingTaskEngine }
                if engine == .cloudDirect {
                    // Bypass Gatekeeper, send to Cloud Model
                    await runHybrid(instruction: text)
                } else {
                    // Local Agent
                    let history = Array(self.messages.dropLast())
                    await runAgentLoop(instruction: text,
                                       images: snapshotImages,
                                       files: snapshotFiles,
                                       previousMessages: history)
                }"""

if target in content:
    content = content.replace(target, replacement)
    print("Replaced Smart Router block")
else:
    print("Failed to find target block")

with open('Sources/Verantyx/AppState.swift', 'w') as f:
    f.write(content)
