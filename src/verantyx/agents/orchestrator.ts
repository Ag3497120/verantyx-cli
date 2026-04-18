import Anthropic from "@anthropic-ai/sdk";
import { MemoryEngine } from "../memory/engine.js";
import { Gatekeeper } from "../vfs/gatekeeper.js";
import { loadConfig, resolveProviderApiKey } from "../config.js";
import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";
import { BrowserClient } from "../vfs/browser_client.js";
import { extractEternalContext } from "../memory/auto-selector.js";
import type { Tier } from "../locallm/calibrate.js";
import { analyzeTaskComplexity, parseTierToNumber } from "../locallm/task-analyzer.js";
import { getCalibrationProfile, generateCalibratedSystemDirectives } from "../locallm/calibrate.js";
import { HitlProxy } from "./hitl-proxy.js";
import { OllamaClient } from "../locallm/ollama-client.js";
import { SubAgentDispatcher } from "./subagent-dispatcher.js";
import { readFileSync } from "fs";

// MARK: - Ronin Neural Link (Orchestrator Pattern + Thinking Capture)

/**
 * The heart of Verantyx's commander pattern.
 */

export type AgentRole = "commander" | "worker" | "scout";

interface AgentMessage {
  role: "user" | "assistant";
  content: string | Anthropic.ContentBlock[];
}

interface ThinkingRecord {
  turn: number;
  timestamp: string;
  userMessage: string;
  thinking: string;
  response: string;
}

export class AgentOrchestrator {
  private client: Anthropic;
  private memory: MemoryEngine;
  private gatekeeper: Gatekeeper;
  private config: ReturnType<typeof loadConfig>;
  private browser: BrowserClient;
  private ollama: OllamaClient;
  private dispatcher: SubAgentDispatcher;

  // Commander state
  private commanderHistory: AgentMessage[] = [];
  private turnCount = 0;
  private hitlSessionTurn = 0;
  private currentTier: Tier = "Tier 1: Fully Autonomous";

  private mcpRuntime: any = null;
  public mcpTools: any[] = [];

  // Thinking capture
  private thinkingLog: ThinkingRecord[] = [];

  // Tri-Layer Cortex Constants
  private readonly L0_PRESSURE_THRESHOLD = 20; // Max turns before a full swap/reset
  private readonly EVICTION_BATCH = 4; // Legacy: used for incremental if preferred

  constructor(memory: MemoryEngine, gatekeeper: Gatekeeper) {
    this.config = loadConfig();
    const apiKey = resolveProviderApiKey(this.config.providers.anthropic);
    this.client = new Anthropic({
      apiKey: apiKey || "",
    });
    this.memory = memory;
    this.gatekeeper = gatekeeper;
    this.browser = new BrowserClient();
    this.ollama = new OllamaClient();
    this.dispatcher = new SubAgentDispatcher(this.ollama, this.browser, this.config.agents.commanderModel);

    // Ensure thinking directory exists
    const thinkingDir = join(this.memory.getRoot(), "front", "thinking");
    if (!existsSync(thinkingDir)) {
      mkdirSync(thinkingDir, { recursive: true });
    }
  }

  // MARK: - Commander Agent (Opus — The Experiencer)

  public setLocallmTier(tier: Tier) {
      this.currentTier = tier;
  }

  public async initMcp(workspaceDir: string) {
      try {
          const { createBundleMcpToolRuntime } = await import("../../agents/pi-bundle-mcp-tools.js");
          this.mcpRuntime = await createBundleMcpToolRuntime({
              workspaceDir: workspaceDir,
              cfg: this.config as any
          });
          this.mcpTools = this.mcpRuntime.tools || [];
          if (this.mcpTools.length > 0) {
              console.log(`[Orchestrator] MCP Runtime loaded ${this.mcpTools.length} external tools.`);
          }
      } catch (e: any) {
          console.warn(`[Orchestrator] Failed to load MCP Runtime: ${e.message}`);
      }
  }

  async commanderChat(userMessage: string): Promise<string> {
    this.turnCount++;
    
    // Dynamic LLM Arbitrator (Task Analyzer Phase)
    console.log(`\n🔍 [TaskAnalyzer] Evaluating complexity of incoming task...`);
    const analysis = await analyzeTaskComplexity(userMessage);
    const requiredNum = analysis.requiredTier;
    const currentNum = parseTierToNumber(this.currentTier);
    
    console.log(`  └─ Domain: ${analysis.domain.toUpperCase()}`);
    console.log(`  └─ Complexity: ${analysis.complexity.toUpperCase()}`);
    console.log(`  └─ Capability Requirement: Tier ${requiredNum}`);

    let activeModel = this.config.agents.commanderModel;
    let isDelegated = false;

    if (currentNum > requiredNum) { // Remember, Tier 1 is better (lower number = tighter autonomy req)
        if (this.config.agents.cloudFallbackMode === "browser_hitl") {
             console.warn(`⚠️  [Orchestrator] HITL MODE: Delegating inference to human + local browser.`);
             
             this.hitlSessionTurn++;
             let isRebirth = false;
             
             const isViz = process.env.RONIN_VIZ_BROWSER === "1";
             if (this.hitlSessionTurn >= 5) {
                 this.hitlSessionTurn = 1;
                 isRebirth = true;
                 await this.browser.restart(isViz);
                 await this.browser.navigate("https://gemini.google.com/app");
             } else if (this.hitlSessionTurn === 1) {
                 await this.browser.restart(isViz);
                 await this.browser.navigate("https://gemini.google.com/app");
             }
             
             let systemPrompt = this.buildCommanderSystemPrompt(true);
             const isJa = this.config.agents.systemLanguage === "ja";
             
             if (isRebirth) {
                 const pastStateNode = this.memory.read("front", "hitl_state_backup");
                 const pastState = pastStateNode ? pastStateNode.content : "{}";
                 systemPrompt = (isJa 
                    ? `【以前のセッションからの引き継ぎ状態： ${pastState} 】\n\n` 
                    : `[State carried over from previous session: ${pastState}]\n\n`) 
                 + systemPrompt;
             }
             
             if (this.hitlSessionTurn === 4) {
                 systemPrompt += (isJa
                    ? `\n\n[SYSTEM DIRECTIVE] このセッションは次で終了します。必ず回答の最後に、現在のプロジェクトの進行状況と重要な変数を、500文字以内のJSON形式で [STATE] タグに囲んで出力してください。`
                    : `\n\n[SYSTEM DIRECTIVE] This session will end next turn. You MUST append an up-to-date summary of project progress and key variables in a JSON payload wrapped in [STATE] tags, max 500 characters, at the very end of your response.`);
             }

             this.commanderHistory.push({ role: "user", content: userMessage });

             const textContent = await HitlProxy.waitForHumanExecution(systemPrompt, userMessage, this.browser, this.config.agents.systemLanguage);
             
             // Extract STATE if it exists
             const stateMatch = textContent.match(/\[STATE\]([\s\S]*?)\[\/STATE\]/);
             if (stateMatch) {
                 await this.memory.write("front", "hitl_state_backup", stateMatch[1]);
             }
             
             const finalResponseContent = `[HITL Extracted Response]\n${textContent}`;
             
             this.commanderHistory.push({
               role: "assistant",
               content: finalResponseContent,
             });
         
             await this.autoUpdateMemory(userMessage, finalResponseContent);
             return finalResponseContent;
        } else {
             console.warn(`⚠️  [Orchestrator] Local capacity exceeded (Required Tier ${requiredNum} > Current Tier ${currentNum}). Delegating inference to Cloud Fallback API.`);
             activeModel = "claude-3-opus-20240229"; // Overriding local config standard fallback
             isDelegated = true;
        }
    } else {
        console.log(`✅ [Ronin Core] Task load approved for Local Inference. Executing loop.`);
    }

    const sysProfile = getCalibrationProfile(activeModel);
    console.log(`  └─ [Ronin Tuning] Auto-calibrated system for ${sysProfile.name} (Max Parallel Tools: ${sysProfile.maxParallelTools})`);

    let systemPrompt = this.buildCommanderSystemPrompt(isDelegated);
    systemPrompt += "\n\n" + generateCalibratedSystemDirectives(sysProfile);
    
    this.commanderHistory.push({ role: "user", content: userMessage });

    const MAX_STEPS = 10;
    let stepCount = 0;
    let finalOutput = "";

    while (stepCount < MAX_STEPS) {
        stepCount++;

        let thinkingContent = "";
        let textContent = "";
        let rawContent: any = null;

        if (!isDelegated) {
            // Native Local LLM Execution via Ollama HTTP
            console.log(`  └─ Calling Local Commander (${activeModel}) [Step ${stepCount}/${MAX_STEPS}]...`);
            const ollamaFormat = [
                { role: "system" as const, content: systemPrompt },
                ...this.commanderHistory.map(m => ({ 
                    role: m.role as "user" | "assistant", 
                    content: typeof m.content === "string" ? m.content : JSON.stringify(m.content) 
                }))
            ];
            
            textContent = await this.ollama.chat(activeModel, ollamaFormat);
            rawContent = textContent;

        } else {
            // Anthropic Cloud Fallback Execution
            const response = await this.client.messages.create({
              model: activeModel,
              max_tokens: 16000,
              thinking: { type: "enabled", budget_tokens: 10000 },
              messages: this.buildMessagesWithSystem(systemPrompt),
            });

            for (const block of response.content) {
              if (block.type === "thinking") {
                thinkingContent = block.thinking;
              } else if (block.type === "text") {
                textContent = block.text;
              }
            }
            rawContent = response.content;
        }

        if (thinkingContent) {
          await this.captureThinking(userMessage, thinkingContent, textContent);
        }

        this.commanderHistory.push({
          role: "assistant",
          content: rawContent,
        });

        // 1. XML parsing and loop breaker
        const actionMatch = textContent.match(/<action>([\s\S]*?)<\/action>/);
        const payloadMatch = textContent.match(/<payload>([\s\S]*?)<\/payload>/);
        const intentMatch = textContent.match(/<intent>([\s\S]*?)<\/intent>/);
        
        let action = actionMatch ? actionMatch[1].trim() : "";
        let payload = payloadMatch ? payloadMatch[1].trim() : "";
        let extractedIntent = intentMatch ? intentMatch[1].trim() : "No intent explicitly defined.";

        if (!actionMatch) {
            if (this.currentTier === "Tier 2: Hybrid Sensory Matrix") {
                // Tier 2 evaluates pure markdown without actions
                action = "finish";
            } else {
                console.warn(`  └─ [ACTION ERROR] Missing XML tags. Pushing correction to Commander.`);
                this.commanderHistory.push({ role: "user", content: "[SYSTEM ERROR] XML format missing. You must wrap your next action in <action> tags. If you are finished, output <action>finish</action>." });
                continue;
            }
        }

        if (action === "finish") {
            finalOutput = textContent;
            break; // Task Done
        }

        // 2. Execute Action & Return Observation
        try {
            console.log(`  └─ Commander issued action: <${action}>`);
            const observation = await this.executeAction(action, payload);
            this.commanderHistory.push({ role: "user", content: `[OBSERVATION]\n${observation}`});
        } catch (e: any) {
            console.warn(`  └─ [EXECUTION ERROR] ${e.message}`);
            this.commanderHistory.push({ role: "user", content: `[ACTION ERROR]\n${e.message}\nFix your action/payload and retry.`});
        }
    }

    if (stepCount >= MAX_STEPS) {
        this.commanderHistory.push({ role: "user", content: "[SYSTEM] ReAct loop limit reached. Yielding."});
        console.warn(`⚠️  [Orchestrator] Loop hit max steps (${MAX_STEPS}).`);
    }

    // Final state saving
    let finalIntent = "No intent extracted.";
    const lastMsgContent = typeof this.commanderHistory[this.commanderHistory.length-2]?.content === "string" 
      ? this.commanderHistory[this.commanderHistory.length-2].content as string 
      : "";
    const lastIntentMatch = lastMsgContent.match(/<intent>([\s\S]*?)<\/intent>/);
    if (lastIntentMatch) finalIntent = lastIntentMatch[1].trim();

    await this.autoUpdateMemory(userMessage, finalOutput || "[No final output extracted]", finalIntent);

    // Phase 4: Dynamic Paging Cortex (Context Swap Protocol)
    if (this.commanderHistory.length > this.L0_PRESSURE_THRESHOLD) {
        await this.performContextPaging();
    }

    return finalOutput || "[No final output extracted - ReAct loop terminated early]";
  }

  /**
   * Performs a full Context Page-Out / Reset.
   * Generates a high-density Anchor node and Flushes the active history.
   */
  private async performContextPaging(): Promise<void> {
      const history = [...this.commanderHistory];
      const stringHistory = history.map(h => ({
          role: h.role,
          content: typeof h.content === 'string' ? h.content : JSON.stringify(h.content)
      }));

      const chalk = require("chalk");
      console.log(chalk.red(`\n🚀 [OOM Event] Context Pressure Limit reached (${this.L0_PRESSURE_THRESHOLD} turns).`));
      console.log(chalk.red(`  └─ Paging-Out entire history to JCross V6...`));
      
      const { generateSnapshotAndAnchor } = require("../memory/auto-selector.js");
      
      try {
          // 1. Generate State Snapshot (L1) and Anchor Node (L1/L2)
          const snapshot = await generateSnapshotAndAnchor(stringHistory, this.memory.getRoot());
          
          // 2. FLUSH L0 Context
          this.commanderHistory = [];
          
          // 3. RELOAD L0 with Virtual State
          this.commanderHistory.push({
              role: "user",
              content: `[SYSTEM] Context Paged. Previous session has been archived in JCross V6.

## Current High-Density State Snapshot
${snapshot}

Continue with the project based on this state. Use 'query_jcross' or 'expand_memory' to retrieve specific raw details if needed.`
          });
          
          console.log(chalk.green(`  └─ [Swap Success] Context Refreshed. Project State preserved.`));
      } catch (e: any) {
          console.error(`  └─ [Paging Crash] Critical failure during context swap: ${e.message}`);
          // Emergency Fallback: Sliding window prune to avoid total crash
          this.commanderHistory.splice(0, 4);
      }
  }

  /**
   * Deprecated in favor of Dynamic Paging Cortex.
   */
  private initiateL0Eviction(): void {
      // No longer used, handled by performContextPaging
  }

  // MARK: - Action Executor
  private async executeAction(action: string, payload: string): Promise<string> {
      if (action.startsWith("mcp_")) {
          const mcpActionName = action.replace("mcp_", "");
          const tool = this.mcpTools.find(t => t.name === mcpActionName);
          if (!tool) {
              throw new Error(`MCP Tool ${mcpActionName} not found in available tools.`);
          }
          const argsMatch = payload.match(/<args>([\s\S]*?)<\/args>/);
          const argsJsonString = argsMatch ? argsMatch[1].trim() : "{}";
          let parsedArgs = {};
          try {
              parsedArgs = JSON.parse(argsJsonString);
          } catch (e: any) {
              throw new Error(`Failed to parse MCP Payload JSON inside <args>: ${e.message}`);
          }
          
          try {
              const chalk = (await import("chalk")).default;
              console.log(chalk.cyan(`\n  🔌 [MCP Call] Executing external plugin tool: ${mcpActionName}`));
              const result = await tool.execute("mcp_cmd_" + Date.now(), parsedArgs);
              return `MCP Tool [${mcpActionName}] Executed successfully.\nResult Observation:\n${JSON.stringify(result, null, 2)}`;
          } catch (mcpErr: any) {
              return `MCP Tool [${mcpActionName}] Failed during execution. Error:\n${mcpErr.message}`;
          }
      }

      switch (action) {
          case "map_reduce": {
              const taskMatch = payload.match(/<task>([\s\S]*?)<\/task>/);
              if (!taskMatch) throw new Error("Missing <task> tag in payload.");
              const chunks = await this.dispatcher.mapTask(taskMatch[1].trim());
              const results = await this.dispatcher.executeSubTasks(chunks, this.config.agents.systemLanguage);
              return `MapReduce Completion Report:\n${results.join("\n\n")}`;
          }
          case "deep_memory": {
              const domainMatch = payload.match(/<domain>([\s\S]*?)<\/domain>/);
              if (!domainMatch) throw new Error("Missing <domain> tag in payload.");
              return await this.queryDeepMemory(domainMatch[1].trim());
          }
          case "edit_file": {
              const fileMatch = payload.match(/<file>([\s\S]*?)<\/file>/);
              const patchMatch = payload.match(/<patch>([\s\S]*?)<\/patch>/);
              if (!fileMatch) throw new Error("Missing <file> tag in payload.");
              if (!patchMatch) throw new Error("Missing <patch> tag in payload. You must provide the proposed code in <patch> tags.");
              
              const file = fileMatch[1].trim();
              const patch = patchMatch[1].trim();

              const chalk = (await import("chalk")).default;
              
              // Phase 2: Ronin CLI TUI Diff Engine Delegation
              const { writeFileSync, unlinkSync } = await import("fs");
              const patchFile = ".ronin_patch.tmp";
              writeFileSync(patchFile, patch);

              console.log(chalk.yellow(`\n  📝 [DiffEngine] Delegating file rewrite to Ronin UX Engine for: ${file}`));

              const { spawn } = await import("child_process");
              
              // We must use spawn with stdio: 'inherit' so the user can interact with the Rust TUI
              return new Promise<string>((resolve, reject) => {
                  const child = spawn("ronin", ["tool", "patch", file, "--patch-file", patchFile], {
                      stdio: ['inherit', 'inherit', 'inherit']
                  });

                  child.on('close', (code) => {
                      try { if (existsSync(patchFile)) unlinkSync(patchFile); } catch(e) {}
                      if (code === 0) {
                          resolve(`Patch approved by human and successfully applied to ${file}.`);
                      } else {
                          resolve(`User REJECTED the patch or diff engine failed. Do not re-issue this exact patch without changes.`);
                      }
                  });
              });
          }
          case "execute_command": {
              // Phase 3: Ronin Sandbox PTY Execution Loop
              const cmdMatch = payload.match(/<cmd>([\s\S]*?)<\/cmd>/);
              if (!cmdMatch) throw new Error("Missing <cmd> tag in payload.");
              
              const cmd = cmdMatch[1].trim();
              const { exec } = await import("child_process");
              const util = await import("util");
              const execAsync = util.promisify(exec);
              const chalk = (await import("chalk")).default;
              
              console.log(chalk.magenta(`\n  ⚡ [Rust Sandbox] Invoking ronin tool shell for: ${cmd}`));
              
              try {
                  // Delegate to Rust Engine (ronin tool shell)
                  // It handles timeout, PTY, and strict policy within Rust, yielding a controlled JSON output.
                  const { stdout, stderr } = await execAsync(`ronin tool shell --cmd "${cmd.replace(/"/g, '\\"')}"`);
                  const result = JSON.parse(stdout);

                  if (result.exit_code === 0) {
                      return `Command executed successfully.\n[STDOUT]\n${(result.stdout || "").slice(0, 2000)}\n[STDERR]\n${(result.stderr || "").slice(0, 1000)}`;
                  } else {
                      return `Command failed.\n[STDOUT]\n${(result.stdout || "").slice(0, 2000)}\n[STDERR]\n${(result.stderr || "").slice(0, 1000)}`;
                  }
              } catch (error: any) {
                  // Fallback if the Rust PTY Bridge completely crashes
                  console.log(chalk.red(`  └─ [Rust PTY Crash] ${error.message}`));
                  return `Command execution bridge failed.\n[ERROR]\n${error.message.slice(0, 1000)}`;
              }
          }
          case "browse":
          case "browse_visible":
          case "interact": {
              return await this.browserTask(action, payload);
          }
          case "expand_memory": {
              const nodeMatch = payload.match(/<node>([\s\S]*?)<\/node>/);
              if (!nodeMatch) throw new Error("Missing <node> tag in payload.");
              const nodeId = nodeMatch[1].trim();
              
              const chalk = (await import("chalk")).default;
              console.log(chalk.cyan(`\n  📂 [L2 Expansion] Restoring raw archive for node: ${nodeId}`));
              
              try {
                  const path = (await import("path"));
                  const fs = (await import("fs"));
                  const v6Path = path.join(this.memory.getRoot(), "jcross_v6", `${nodeId}.jcross`);
                  const v4Path = path.join(this.memory.getRoot(), "jcross_v4", `${nodeId}.jcross`);
                  const targetPath = fs.existsSync(v6Path) ? v6Path : v4Path;
                  
                  if (!fs.existsSync(targetPath)) return `[Expansion Error] Node ${nodeId} not found in V6 or V4 space.`;
                  
                  const raw = fs.readFileSync(targetPath, "utf-8");
                  const l2Match = raw.match(/\[L2_Archive\]\s*([\s\S]*?)\s*===/);
                  if (l2Match) return `[L2_ARCHIVE RESTORED for ${nodeId}]\n${l2Match[1]}`;
                  
                  // Fallback to [本質記憶] if v4
                  const v4Match = raw.match(/\[本質記憶\]\s*([\s\S]*?)\s*===/);
                  if (v4Match) return `[EPISODIC RESTORED for ${nodeId}]\n${v4Match[1]}`;
                  
                  return `[Expansion Error] Node ${nodeId} exists but contains no L2 or episodic archive.`;
              } catch (e: any) {
                  return `[Expansion Error] ${e.message}`;
              }
          }
          default:
              throw new Error(`Unknown action: ${action}`);
      }
  }

  private buildMessagesWithSystem(systemPrompt: string): Anthropic.MessageParam[] {
    const messages: Anthropic.MessageParam[] = [];
    for (let i = 0; i < this.commanderHistory.length; i++) {
      const msg = this.commanderHistory[i];
      if (i === 0 && msg.role === "user") {
        messages.push({
          role: "user",
          content: `${systemPrompt}\n\n---\n\n${typeof msg.content === "string" ? msg.content : ""}`,
        });
      } else {
        messages.push({
          role: msg.role,
          content: msg.content as any,
        });
      }
    }
    return messages;
  }

  private async captureThinking(userMessage: string, thinking: string, response: string): Promise<void> {
    const record: ThinkingRecord = {
      turn: this.turnCount,
      timestamp: new Date().toISOString(),
      userMessage: userMessage.slice(0, 200),
      thinking,
      response: response.slice(0, 300),
    };

    this.thinkingLog.push(record);
    const thinkingDir = join(this.memory.getRoot(), "front", "thinking");
    const filename = `turn_${String(this.turnCount).padStart(3, "0")}.md`;

    const content = `---
name: Thinking Turn ${this.turnCount}
description: Commander's reasoning process for turn ${this.turnCount}
type: project
timestamp: ${record.timestamp}
---

# Turn ${this.turnCount} — Commander Thinking

## User Input
${record.userMessage}

## Reasoning Process
${thinking}

## Decision/Response (summary)
${record.response}
`;

    writeFileSync(join(thinkingDir, filename), content);
    await this.updateThinkingSummary();
  }

  private async updateThinkingSummary(): Promise<void> {
    const recentThinking = this.thinkingLog.slice(-5);
    const summary = `---
name: Thinking Summary
description: Rolling summary of commander's recent reasoning
type: project
updated: ${new Date().toISOString()}
---

# Recent Commander Thinking

${recentThinking
  .map(
    (r) => `## Turn ${r.turn} (${r.timestamp})
**User:** ${r.userMessage}
**Reasoning:** ${r.thinking.slice(0, 500)}...
**Decision:** ${r.response}
`
  )
  .join("\n")}
`;
    try {
        const existingNode = this.memory.read("front", "thinking_summary");
        this.memory.write("front", "thinking_summary", summary, existingNode?.version);
    } catch (e: any) {
        if (e.message.includes("STALE_MEMORY")) {
            console.warn("\n⚠️  [Orchestrator] Data Conflict Detected: thinking_summary was modified by another parallel agent. Forcing overwrite resolve.");
            // Advanced MVCC logic would trigger a graph merge, for now we overwrite based on master orchestrator priority
            this.memory.write("front", "thinking_summary", summary);
        } else {
            throw e;
        }
    }
  }

  // Exposed explicitly for Commander Map-Reduce processing
  public async queryDeepMemory(domain: string): Promise<string> {
      try {
          console.log(`\n🧠 [DeepMemory] Injecting JCross topology for domain: ${domain}...`);
          const deepPath = join(this.memory.getRoot(), "deep", `${domain}.jcross`);
          if (existsSync(deepPath)) {
              const raw = readFileSync(deepPath, "utf-8");
              // A real implementation would parse and compress the topology here.
              // For now, we simulate a compressed return.
              return `[JCROSS EXTRACTED]\n${raw.slice(0, 500)}...\n[END EXTRACT]`;
          }
          return `[DeepMemory: No JCross snapshot found for ${domain}]`;
      } catch (e) {
          return `[DeepMemory Error]`;
      }
  }

  private buildCommanderSystemPrompt(isDelegated: boolean = false): string {
    const frontMemories = this.memory.getFrontMemories();
    const thinkingNode = this.memory.read("front", "thinking_summary");
    const thinkingSummary = thinkingNode ? thinkingNode.content : "";

    return `# Verantyx Commander Agent

You are the COMMANDER of the Verantyx project. You are an EXPERIENCER, not a worker.

## Forced Memory Context (JCross V6 Index)
> You are using the Tri-Layer Cortex. Oldest messages are automatically moved to JCross V6.
> To retrieve evicted context, use `mcp_query_jcross` for searching L1 and `mcp_expand_memory` for L2 expansion.

${frontMemories}

## Previous Reasoning

${thinkingSummary}

## Rules

1. You NEVER read code files directly.
2. DO NOT rewrite entire files. You must only use Diff Patches using XML <search> and <replace> blocks.
3. When delegating code generation, break tasks into Micro-Tasks.

## Available Actions

You must ALWAYS output your response in the following XML format. Do not use JSON.
<thought>
Reasoning about what to do next. Step-by-step thinking.
</thought>
<intent>
Explain the hidden truth, deep nuance, or unstated purpose behind your response. 
This is critical for the Subconscious Memory Manager to accurately compile this turn into JCross.
</intent>
<action>ACTION_NAME</action>
<payload>
Action specific arguments inside XML tags depending on the action.
</payload>

Allowed ACTION_NAMEs:
- edit_file: Modify an existing file using Diff Approval. Payload requires <file> and <patch> tags.
- execute_command: Run a bash command. Payload requires <cmd> tag.
- map_reduce: Dispatch task to sub-agents. Payload requires <task> tag.
- query_jcross: Search the Semantic Index (L1 Cache). Recommended when history is evicted. Payload requires <query> and <domain> tags.
- expand_memory: Restore raw Episodic Archive (L2). Recommended after identifying a node via query_jcross. Payload requires <node> tag.
- browse: Navigate the web. Payload requires <url> tag.
- browse_visible: Force UI browser. Payload requires <url> tag.
- interact: Interact with DOM. Payload requires <type> (click/type) and <id> tags.

Required External Plugins:
${this.mcpTools.map((t: any) => `- mcp_${t.name}: ${t.description}. Payload requires <args> tag containing JSON matching schema: ${JSON.stringify(t.parameters)}`).join("\n") || "No external MCP tools loaded."}

## Current Tier Execution: ${this.currentTier}
Current Tier Rules: ${this.currentTier === "Tier 2: Hybrid Sensory Matrix" ? "You MUST NOT emit <action> tags. You act ONLY as a vision/sensory observer outputting pure markdown constraints. A cloud Planner agent will act on your markdown." : "You are fully autonomous and MUST output XML <action> tags."}

## Current Turn: ${this.turnCount}
`;
  }

  async workerTask(task: string): Promise<string> {
    const systemPrompt = `You are a Verantyx WORKER agent. Your job is to read code and browse the web.
You have access to the Virtual File System via the Gatekeeper.

Task: ${task}

Available files:
${JSON.stringify(this.gatekeeper.list(), null, 2)}

You must respond utilizing XML action formatting.
<action>ACTION_NAME</action>
<payload>
<url>https://...</url>
</payload>

Allowed browser actions: browse, browse_visible, click, type
For click/type, payload requires <id>, and for type requires <text>.
`;

    const response = await this.client.messages.create({
      model: this.config.agents.workerModel,
      max_tokens: 4096,
      system: systemPrompt,
      messages: [{ role: "user", content: task }],
    });

    const result = response.content[0].type === "text" ? response.content[0].text : "";

    const actionMatch = result.match(/<action>(.*?)<\/action>/);
    const payloadMatch = result.match(/<payload>([\s\S]*?)<\/payload>/);
    if (actionMatch) {
      const action = actionMatch[1].trim();
      const payload = payloadMatch ? payloadMatch[1] : "";
      
      if (['browse', 'browse_visible', 'click', 'type', 'interact'].includes(action)) {
          return await this.browserTask(action, payload);
      }
    }

    return result;
  }

  async browserTask(action: string, payload: string): Promise<string> {
    try {
      if (action === "browse_visible") {
        const urlMatch = payload.match(/<url>(.*?)<\/url>/);
        if (!urlMatch) return `[XML ERROR] Missing <url> tag inside <payload>`;
        const url = urlMatch[1].trim();
        await this.browser.restart(true); // Restart process in visible mode
        const resp = await this.browser.navigate(url);
        return `[BROWSER VISIBLE] Navigated to ${url}\n\n${resp.markdown || "No content"}`;
      }
      if (action === "browse") {
        const urlMatch = payload.match(/<url>(.*?)<\/url>/);
        if (!urlMatch) return `[XML ERROR] Missing <url> tag inside <payload>`;
        const url = urlMatch[1].trim();
        const resp = await this.browser.navigate(url);
        return `[BROWSER] Navigated to ${url}\n\n${resp.markdown || "No content"}`;
      }
      if (action === "click" || action === "interact") {
        const idMatch = payload.match(/<id>(\d+)<\/id>/);
        if (!idMatch) return `[XML ERROR] Missing <id> tag inside <payload>`;
        const id = parseInt(idMatch[1].trim());
        const resp = await this.browser.click(id);
        return `[BROWSER] Clicked element ${id}\n\n${resp.markdown || "Updated view Above"}`;
      }
      if (action === "type") {
        const idMatch = payload.match(/<id>(\d+)<\/id>/);
        const textMatch = payload.match(/<text>([\s\S]*?)<\/text>/);
        if (!idMatch || !textMatch) return `[XML ERROR] Missing <id> or <text> tag inside <payload>`;
        const id = parseInt(idMatch[1].trim());
        await this.browser.type(id, textMatch[1].trim());
        return `[BROWSER] Typed text into element ${id}`;
      }
      return `[BROWSER] Unknown command action: ${action}`;
    } catch (e) {
      return `[BROWSER ERROR] ${e}`;
    }
  }

  async scoutTask(task: string): Promise<string> {
    const response = await this.client.messages.create({
      model: this.config.agents.scoutModel,
      max_tokens: 1024,
      messages: [{ role: "user", content: task }],
    });
    return response.content[0].type === "text" ? response.content[0].text : "";
  }

  private async autoUpdateMemory(userMessage: string, assistantMessage: string, intent: string): Promise<void> {
    const { compileTriLayerJCross } = await import("../memory/auto-selector.js");
    await compileTriLayerJCross(userMessage, assistantMessage, intent, this.memory.getRoot());
  }

  async writeSessionExperience(): Promise<void> {
    const stringTurns = this.commanderHistory.map(h => ({
        role: h.role, 
        content: typeof h.content === 'string' ? h.content : JSON.stringify(h.content)
    }));
    
    // Automatically extract context and dump the active raw turn sequence!
    await extractEternalContext(stringTurns, this.memory.getRoot());
    
    // Clear ephemeral context arrays preventing memory overflow
    this.commanderHistory = [];
    this.thinkingLog = [];
  }
}
