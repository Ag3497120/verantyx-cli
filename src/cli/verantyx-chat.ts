import type { Command } from "commander";
import { createInterface } from "readline";
import { MemoryEngine } from "../verantyx/memory/engine.js";
import { HapticServer } from "../verantyx/notify/haptic-server.js";

// MARK: - Verantyx Chat Command

// ANSI
const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const MAGENTA = "\x1b[35m";
const GRAY = "\x1b[90m";
const DIM = "\x1b[2m";
const BOLD = "\x1b[1m";
const RESET = "\x1b[0m";
const WHITE = "\x1b[37m";
const BLUE = "\x1b[34m";

// Context tracking
interface ContextTracker {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  maxTokens: number;
  turnCount: number;
  toolCalls: number;
}

function createTracker(memoryTokens: number): ContextTracker {
  return {
    inputTokens: memoryTokens, // Memory injection tokens
    outputTokens: 0,
    totalTokens: memoryTokens,
    maxTokens: 1_000_000, // Opus 1M
    turnCount: 0,
    toolCalls: 0,
  };
}

function formatContextBar(ctx: ContextTracker): string {
  const pct = Math.min(100, Math.round((ctx.totalTokens / ctx.maxTokens) * 100));
  const barWidth = 30;
  const filled = Math.round((pct / 100) * barWidth);
  const empty = barWidth - filled;

  let barColor = GREEN;
  if (pct > 70) {barColor = YELLOW;}
  if (pct > 90) {barColor = "\x1b[31m";} // RED

  const bar = `${barColor}${"█".repeat(filled)}${GRAY}${"░".repeat(empty)}${RESET}`;
  const stats = `${GRAY}${ctx.totalTokens.toLocaleString()}/${(ctx.maxTokens / 1000).toFixed(0)}K${RESET}`;
  const turns = `${GRAY}T${ctx.turnCount}${RESET}`;
  const tools = ctx.toolCalls > 0 ? ` ${GRAY}🔧${ctx.toolCalls}${RESET}` : "";

  return `${bar} ${stats} ${turns}${tools} ${GRAY}${pct}%${RESET}`;
}

function formatStatusLine(ctx: ContextTracker): string {
  return `${GRAY}─── ctx: ${formatContextBar(ctx)} ───${RESET}`;
}

function getAgentLabel(model?: string): string {
  if (!model) {return `${GRAY}[agent]${RESET}`;}
  if (model.includes("opus")) {return `${MAGENTA}${BOLD}[commander/opus]${RESET}`;}
  if (model.includes("sonnet")) {return `${CYAN}[worker/sonnet]${RESET}`;}
  if (model.includes("haiku")) {return `${GRAY}[scout/haiku]${RESET}`;}
  return `${GRAY}[agent/${model}]${RESET}`;
}

export function registerVerantyxChatCli(program: Command) {
  program
    .command("vchat")
    .description("Verantyx commander chat with context tracking")
    .option("--no-thinking", "Hide thinking blocks")
    .option("-m, --model <model>", "Override commander model")
    .action(async (opts: { thinking?: boolean; model?: string }) => {
      const showThinking = opts.thinking !== false;

      // Resolve memory and estimate tokens
      const memoryRoot = process.env.VERANTYX_MEMORY_ROOT;
      let memoryTokens = 0;
      if (memoryRoot) {
        try {
          const memory = new MemoryEngine(memoryRoot);
          const front = memory.getFrontMemories();
          memoryTokens = Math.ceil(front.length / 4);
        } catch { /* ignore */ }
      }

      const ctx = createTracker(memoryTokens);

      // Haptic notification server
      const haptic = new HapticServer(19800);
      let hapticActive = false;
      try {
        await haptic.start();
        hapticActive = true;
      } catch { /* haptic server optional */ }

      haptic.on("reply", (event: any) => {
        console.log(`\n  ${MAGENTA}📱 Remote reply: ${event.reply}${RESET}`);
      });

      // Header
      console.log();
      console.log(`${CYAN}${BOLD}  verantyx${RESET} ${GRAY}v0.1.0${RESET}`);
      console.log(`${GRAY}  memory: ${memoryTokens > 0 ? `${GREEN}injected${RESET} ${GRAY}(${memoryTokens} tokens)` : `${YELLOW}none`}${RESET}`);
      console.log(`${GRAY}  commander: ${process.env.VERANTYX_COMMANDER_MODE === "true" ? `${GREEN}enforced${RESET}` : `${YELLOW}off${RESET}`}${RESET}`);
      console.log(`${GRAY}  haptic: ${hapticActive ? `${GREEN}listening${RESET} ${GRAY}(port ${haptic["port"]}, ${haptic.connectedDevices} devices)` : `${YELLOW}off${RESET}`}${RESET}`);
      console.log();
      console.log(formatStatusLine(ctx));
      console.log();

      let currentModel: string | undefined;

      const rl = createInterface({
        input: process.stdin,
        output: process.stdout,
      });

      const showPrompt = () => {
        rl.question(`${DIM}${GRAY}> ${RESET}`, async (input) => {
          const trimmed = input.trim();

          if (!trimmed) { showPrompt(); return; }
          if (trimmed === "exit" || trimmed === "quit" || trimmed === "q") {
            if (hapticActive) {
              haptic.notifyComplete("Session ended");
              setTimeout(() => haptic.stop(), 500);
            }
            console.log();
            console.log(formatStatusLine(ctx));
            console.log(`${GRAY}  session ended. ${ctx.turnCount} turns, ${ctx.toolCalls} tool calls${RESET}`);
            console.log();
            rl.close();
            return;
          }

          // Built-in commands
          if (trimmed === "/memory" && memoryRoot) {
            const memory = new MemoryEngine(memoryRoot);
            const entries = memory.list();
            console.log();
            for (const e of entries) {
              console.log(`  ${GRAY}${e.zone}/${RESET}${WHITE}${e.name}${RESET}`);
            }
            console.log();
            showPrompt();
            return;
          }
          if (trimmed === "/ctx") {
            console.log();
            console.log(formatStatusLine(ctx));
            console.log(`  ${GRAY}input:  ${ctx.inputTokens.toLocaleString()} tokens${RESET}`);
            console.log(`  ${GRAY}output: ${ctx.outputTokens.toLocaleString()} tokens${RESET}`);
            console.log(`  ${GRAY}turns:  ${ctx.turnCount}${RESET}`);
            console.log(`  ${GRAY}tools:  ${ctx.toolCalls}${RESET}`);
            console.log();
            showPrompt();
            return;
          }
          if (trimmed === "/help") {
            console.log();
            console.log(`  ${WHITE}Search${RESET}`);
            console.log(`  ${GRAY}.search <words>      — Spotlight search (each word independently)${RESET}`);
            console.log(`  ${GRAY}.search-all <words>  — search + auto-load top matches + summarize${RESET}`);
            console.log(`  ${GRAY}.search/notes <words>— Spotlight + Notes 二重検索 + 自動読み込み${RESET}`);
            console.log(`  ${GRAY}.haptic test      — Send test haptic to connected devices${RESET}`);
            console.log(`  ${GRAY}.haptic morse <txt>— Send morse code vibration${RESET}`);
            console.log(`  ${GRAY}.haptic status    — Show connected devices${RESET}`);
            console.log();
            console.log(`  ${WHITE}Load${RESET}`);
            console.log(`  ${GRAY}.read <path>         — read file into buffer${RESET}`);
            console.log(`  ${GRAY}.notes [query]       — list/search Apple Notes${RESET}`);
            console.log(`  ${GRAY}.note <name>         — read a Note into buffer${RESET}`);
            console.log();
            console.log(`  ${WHITE}Sub-Agents (Private Browser)${RESET}`);
            console.log(`  ${GRAY}.gemini <task>        — run task via Gemini with tool access${RESET}`);
            console.log(`  ${GRAY}.chatgpt <task>       — generate code via ChatGPT (private)${RESET}`);
            console.log(`  ${GRAY}.crossval <question>  — cross-validate with Gemini + ChatGPT${RESET}`);
            console.log(`  ${GRAY}.gemini.stop          — stop running agent loop${RESET}`);
            console.log();
            console.log(`  ${WHITE}Audit${RESET}`);
            console.log(`  ${GRAY}.audit <zone/name>   — check memory via private Gemini${RESET}`);
            console.log(`  ${GRAY}.audit all|status|auto|triple <zone/name>${RESET}`);
            console.log();
            console.log(`  ${WHITE}System${RESET}`);
            console.log(`  ${GRAY}/memory              — list spatial memories${RESET}`);
            console.log(`  ${GRAY}/ctx                 — show context usage${RESET}`);
            console.log(`  ${GRAY}/help                — show this help${RESET}`);
            console.log(`  ${GRAY}exit                 — end session${RESET}`);
            console.log();
            showPrompt();
            return;
          }

          // .gemini — Run task via Gemini agent loop with tool access
          if (trimmed.startsWith(".gemini ") && trimmed !== ".gemini.stop") {
            const task = trimmed.slice(8).trim();
            if (!task) {
              console.log(`  ${YELLOW}Usage: .gemini <task description>${RESET}`);
              showPrompt();
              return;
            }

            console.log();
            console.log(`  ${WHITE}🧬 Gemini Agent Loop${RESET}`);
            console.log(`  ${GRAY}Task: ${task.slice(0, 60)}${task.length > 60 ? "..." : ""}${RESET}`);
            console.log(`  ${GRAY}Pure-Through: reset every 5 turns${RESET}`);
            console.log(`  ${GRAY}Tools: read, write, exec, search, memory, gatekeeper${RESET}`);
            console.log();

            try {
              const { GeminiAgentLoop } = await import("../verantyx/audit/gemini-agent-loop.js");

              const agentLoop = new GeminiAgentLoop({
                memoryRoot: memoryRoot || "",
                vfsMappingPath: process.env.VERANTYX_VFS_MAPPING,
                maxTurns: 5,
                maxOutputLines: 100,
                onToolExec: (req, result) => {
                  const icon = result.success ? "✅" : "❌";
                  const preview = result.output.split("\n")[0]?.slice(0, 60) || "";
                  console.log(`  ${GRAY}  [tool] ${icon} ${req.action} ${req.target} → ${preview}${result.truncated ? " (truncated)" : ""}${RESET}`);
                },
                onTurnComplete: (turn, response) => {
                  console.log();
                  console.log(`  ${WHITE}[Gemini T${turn}]${RESET}`);
                  // Show first 5 lines of response
                  const lines = response.split("\n").slice(0, 5);
                  for (const line of lines) {
                    console.log(`  ${GRAY}${line.slice(0, 80)}${RESET}`);
                  }
                  if (response.split("\n").length > 5) {
                    console.log(`  ${GRAY}... (${response.split("\n").length - 5} more lines)${RESET}`);
                  }
                },
                onReset: (turn, will) => {
                  console.log();
                  console.log(`  ${YELLOW}⚡ Pure-Through Reset at turn ${turn}${RESET}`);
                  console.log(`  ${GRAY}Will: ${will.slice(0, 80)}...${RESET}`);
                },
              });

              // Store for .gemini.stop
              (globalThis as any).__geminiLoop = agentLoop;

              const result = await agentLoop.run(task);

              console.log();
              console.log(`  ${GREEN}━━━ Gemini Agent Complete ━━━${RESET}`);
              const stats = agentLoop.getStats();
              console.log(`  ${GRAY}Turns: ${stats.totalTurns}, Resets: ${stats.resets}${RESET}`);
              console.log();

              // Show final result
              const resultLines = result.split("\n");
              for (const line of resultLines.slice(0, 20)) {
                console.log(`  ${WHITE}${line}${RESET}`);
              }
              if (resultLines.length > 20) {
                console.log(`  ${GRAY}... (${resultLines.length - 20} more lines)${RESET}`);
              }

              agentLoop.cleanup();
              (globalThis as any).__geminiLoop = null;
            } catch (err: any) {
              console.log(`  ${YELLOW}Gemini error: ${err.message}${RESET}`);
            }

            console.log();
            showPrompt();
            return;
          }

          // .chatgpt — Generate code via ChatGPT in private browser
          if (trimmed.startsWith(".chatgpt ")) {
            const task = trimmed.slice(9).trim();
            if (!task) {
              console.log(`  ${YELLOW}Usage: .chatgpt <code generation task>${RESET}`);
              showPrompt();
              return;
            }

            console.log();
            console.log(`  ${WHITE}🤖 ChatGPT Sub-Agent (Private Browser)${RESET}`);
            console.log(`  ${GRAY}Task: ${task.slice(0, 60)}${task.length > 60 ? "..." : ""}${RESET}`);
            console.log(`  ${GRAY}Opening Safari Private Window...${RESET}`);

            try {
              const { MultiAIBridge } = await import("../verantyx/audit/multi-ai-bridge.js");
              const bridge = new MultiAIBridge();
              const result = await bridge.generateCode(task, "Swift");

              console.log();
              if (result.status === "success") {
                console.log(`  ${GREEN}✅ ChatGPT response (${result.durationMs}ms)${RESET}`);
                console.log();
                const lines = result.response.split("\n");
                for (const line of lines.slice(0, 30)) {
                  console.log(`  ${WHITE}${line}${RESET}`);
                }
                if (lines.length > 30) {
                  console.log(`  ${GRAY}... (${lines.length - 30} more lines)${RESET}`);
                }
              } else {
                console.log(`  ${YELLOW}ChatGPT error: ${result.status}${RESET}`);
              }

              bridge.cleanup();
            } catch (err: any) {
              console.log(`  ${YELLOW}Error: ${err.message}${RESET}`);
            }

            console.log();
            showPrompt();
            return;
          }

          // .crossval — Cross-validate with both Gemini and ChatGPT
          if (trimmed.startsWith(".crossval ")) {
            const question = trimmed.slice(10).trim();
            if (!question) {
              console.log(`  ${YELLOW}Usage: .crossval <question to validate>${RESET}`);
              showPrompt();
              return;
            }

            console.log();
            console.log(`  ${WHITE}🔍 Cross-Validation (Gemini × ChatGPT)${RESET}`);
            console.log(`  ${GRAY}Question: ${question.slice(0, 60)}${question.length > 60 ? "..." : ""}${RESET}`);
            console.log();

            try {
              const { MultiAIBridge } = await import("../verantyx/audit/multi-ai-bridge.js");
              const bridge = new MultiAIBridge();

              console.log(`  ${GRAY}  Asking Gemini (private)...${RESET}`);
              const result = await bridge.crossValidate(question);

              console.log(`  ${GRAY}  Asking ChatGPT (private)...${RESET}`);
              console.log();
              console.log(`  ${WHITE}━━━ Results ━━━${RESET}`);
              console.log();
              console.log(`  ${GRAY}Gemini:${RESET}  ${result.gemini.response.split("\n")[0]?.slice(0, 60)}`);
              console.log(`  ${GRAY}ChatGPT:${RESET} ${result.chatgpt.response.split("\n")[0]?.slice(0, 60)}`);
              console.log();
              console.log(`  ${result.agreement ? GREEN + "✅ Agreement" : YELLOW + "⚠️ Disagreement"}: ${result.summary}${RESET}`);

              bridge.cleanup();
            } catch (err: any) {
              console.log(`  ${YELLOW}Error: ${err.message}${RESET}`);
            }

            console.log();
            showPrompt();
            return;
          }

          // .gemini.stop — Stop running Gemini agent loop
          if (trimmed === ".gemini.stop") {
            const loop = (globalThis as any).__geminiLoop;
            if (loop) {
              loop.stop();
              console.log(`  ${GREEN}Gemini agent loop stopped${RESET}`);
            } else {
              console.log(`  ${GRAY}No Gemini agent loop running${RESET}`);
            }
            showPrompt();
            return;
          }

          // .audit — Hallucination detection via private Gemini
          if (trimmed.startsWith(".audit") && memoryRoot) {
            const subCmd = trimmed.slice(6).trim();

            try {
              const { existsSync } = await import("fs");
              const { GeminiBridge } = await import("../verantyx/audit/gemini-bridge.js");
              const { MemoryAuditor } = await import("../verantyx/audit/memory-auditor.js");

              // .audit status — Show audit history
              if (subCmd === "status") {
                const { readdirSync, readFileSync: readF } = await import("fs");
                const { join: joinP } = await import("path");
                const auditDir = joinP(memoryRoot, "audit");
                const verifiedDir = joinP(memoryRoot, "verified");

                const auditFiles = existsSync(auditDir)
                  ? readdirSync(auditDir).filter(f => f.endsWith(".md")).sort().reverse().slice(0, 10)
                  : [];
                const verifiedFiles = existsSync(verifiedDir)
                  ? readdirSync(verifiedDir).filter(f => f.endsWith(".md"))
                  : [];

                console.log();
                console.log(`  ${WHITE}Audit Status${RESET}`);
                console.log(`  ${GREEN}Verified: ${verifiedFiles.length} memories${RESET}`);
                console.log();

                if (auditFiles.length > 0) {
                  console.log(`  ${WHITE}Recent Audits (latest 10):${RESET}`);
                  for (const f of auditFiles) {
                    const content = readF(joinP(auditDir, f), "utf-8");
                    const verdictMatch = content.match(/verdict:\s*(\w+)/);
                    const confMatch = content.match(/confidence:\s*([\d.]+)/);
                    const targetMatch = content.match(/target:\s*(.+)/);
                    const verdict = verdictMatch?.[1] || "?";
                    const conf = confMatch?.[1] || "?";
                    const target = targetMatch?.[1] || f;
                    const icon = verdict === "VERIFIED" ? "✅" : verdict === "HALLUCINATION" ? "❌" : "❓";
                    console.log(`  ${GRAY}  ${icon} ${target} — ${verdict} (${conf})${RESET}`);
                  }
                } else {
                  console.log(`  ${GRAY}No audits yet. Run .audit <zone/name> to start.${RESET}`);
                }
                console.log();
                showPrompt();
                return;
              }

              // .audit auto — Toggle auto-audit
              if (subCmd === "auto") {
                const current = (globalThis as any).__auditAutoEnabled ?? false;
                (globalThis as any).__auditAutoEnabled = !current;
                console.log();
                console.log(`  ${WHITE}Auto-audit: ${!current ? "ON" : "OFF"}${RESET}`);
                if (!current) {
                  console.log(`  ${GRAY}Commander responses will be checked for hallucinations via private Gemini${RESET}`);
                }
                console.log();
                showPrompt();
                return;
              }

              // .audit all — Audit all unverified memories
              if (subCmd === "all") {
                console.log();
                console.log(`  ${WHITE}🔍 Full Audit — Opening Safari Private Window...${RESET}`);
                console.log(`  ${GRAY}This will check all memories in front/near/mid/deep${RESET}`);
                console.log();

                const bridge = new GeminiBridge();
                const auditor = new MemoryAuditor(bridge, memoryRoot);

                const summary = await auditor.runPeriodicAudit();

                console.log(`  ${WHITE}━━━ Audit Complete ━━━${RESET}`);
                console.log(`  ${GRAY}Total:         ${summary.total}${RESET}`);
                console.log(`  ${GREEN}Verified:      ${summary.verified}${RESET}`);
                console.log(`  ${YELLOW}Hallucination: ${summary.hallucinations}${RESET}`);
                console.log(`  ${GRAY}Uncertain:     ${summary.uncertain}${RESET}`);

                for (const d of summary.details) {
                  const icon = d.verdict === "VERIFIED" ? "✅" : d.verdict === "HALLUCINATION" ? "❌" : "❓";
                  console.log(`  ${GRAY}  ${icon} ${d.zone}/${d.memoryName} — ${d.verdict} (${d.confidence})${RESET}`);
                  if (d.contradictions.length > 0) {
                    for (const c of d.contradictions) {
                      console.log(`  ${YELLOW}     ⚠ ${c}${RESET}`);
                    }
                  }
                }

                bridge.cleanup();
                console.log();
                showPrompt();
                return;
              }

              // .audit <zone/name> — Audit specific memory
              if (subCmd && subCmd.includes("/")) {
                const parts = subCmd.split("/");
                const zone = parts[0];
                const name = parts.slice(1).join("/");

                console.log();
                console.log(`  ${WHITE}🔍 Auditing ${zone}/${name} via private Gemini...${RESET}`);

                const bridge = new GeminiBridge();
                const auditor = new MemoryAuditor(bridge, memoryRoot);

                const result = await auditor.auditMemory(zone, name);

                const icon = result.verdict === "VERIFIED" ? "✅" : result.verdict === "HALLUCINATION" ? "❌" : "❓";
                console.log();
                console.log(`  ${WHITE}━━━ Audit Result ━━━${RESET}`);
                console.log(`  ${icon} Verdict: ${result.verdict}`);
                console.log(`  ${GRAY}Confidence: ${result.confidence}${RESET}`);

                if (result.contradictions.length > 0) {
                  console.log(`  ${YELLOW}Contradictions:${RESET}`);
                  for (const c of result.contradictions) {
                    console.log(`  ${YELLOW}  - ${c}${RESET}`);
                  }
                }
                if (result.supportingEvidence.length > 0) {
                  console.log(`  ${GREEN}Evidence:${RESET}`);
                  for (const e of result.supportingEvidence) {
                    console.log(`  ${GREEN}  - ${e}${RESET}`);
                  }
                }

                if (result.verdict === "VERIFIED") {
                  console.log(`  ${GREEN}→ Moved to verified/ zone${RESET}`);
                } else if (result.verdict === "HALLUCINATION") {
                  console.log(`  ${YELLOW}→ Marked as [STALE]${RESET}`);
                }

                bridge.cleanup();
                console.log();
                showPrompt();
                return;
              }

              // .audit triple <zone/name> — Triple-check (Gemini + ChatGPT + Commander)
              if (subCmd.startsWith("triple ")) {
                const target = subCmd.slice(7).trim();
                if (!target.includes("/")) {
                  console.log(`  ${YELLOW}Usage: .audit triple <zone/name>${RESET}`);
                  console.log();
                  showPrompt();
                  return;
                }

                const parts = target.split("/");
                const zone = parts[0];
                const name = parts.slice(1).join("/");

                console.log();
                console.log(`  ${WHITE}🔍🔍🔍 Triple-Check: ${zone}/${name}${RESET}`);
                console.log(`  ${GRAY}Gemini (private) + ChatGPT (private) + Commander${RESET}`);
                console.log();

                const { TripleCheckAuditor } = await import("../verantyx/audit/triple-check.js");
                const auditor = new TripleCheckAuditor(memoryRoot);
                const result = await auditor.verify(zone, name);

                const cIcon = result.consensus === "VERIFIED" ? "✅" : result.consensus === "REJECTED" ? "❌" : "❓";
                console.log(`  ${WHITE}━━━ Triple-Check Result ━━━${RESET}`);
                console.log(`  ${cIcon} Consensus: ${result.consensus} (${result.agreementRatio})`);
                console.log(`  ${GRAY}  Gemini:    ${result.geminiVerdict}${RESET}`);
                console.log(`  ${GRAY}  ChatGPT:   ${result.chatgptVerdict}${RESET}`);
                console.log(`  ${GRAY}  Commander: ${result.commanderVerdict}${RESET}`);

                if (result.consensus === "VERIFIED") {
                  console.log(`  ${GREEN}→ Moved to verified/ with triple-check metadata${RESET}`);
                }
                console.log();
                showPrompt();
                return;
              }

              // No valid subcommand
              console.log(`  ${YELLOW}Usage: .audit <zone/name> | .audit all | .audit status | .audit auto | .audit triple <zone/name>${RESET}`);
              console.log();
              showPrompt();
              return;

            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : String(err);
              console.log(`  ${YELLOW}Audit error: ${msg}${RESET}`);
              console.log();
              showPrompt();
              return;
            }
          }

          // .search — Spotlight search, each word independently
          if (trimmed.startsWith(".search ")) {
            const queryStr = trimmed.slice(8).trim();
            if (!queryStr) {
              console.log(`  ${YELLOW}Usage: .search <word1> <word2> ...${RESET}`);
              showPrompt();
              return;
            }

            // Split into individual keywords
            const keywords = queryStr.split(/\s+/).filter(Boolean);

            console.log();
            process.stderr.write(`  ${CYAN}[search]${RESET} ${GRAY}🔍 ${keywords.length} keyword(s): ${keywords.join(", ")}${RESET}\n`);
            console.log();

            try {
              const { execSync } = await import("child_process");

              // Collect all unique results across all keywords
              const allResults = new Map<string, string[]>(); // path → which keywords matched

              for (const kw of keywords) {
                process.stderr.write(`  ${GRAY}  searching "${kw}"...${RESET}\n`);

                try {
                  const raw = execSync(
                    `mdfind "${kw.replace(/"/g, '\\"')}" 2>/dev/null | head -30`,
                    { timeout: 10_000, maxBuffer: 1024 * 1024 }
                  ).toString().trim();

                  const files = raw.split("\n").filter(Boolean);
                  for (const f of files) {
                    if (!allResults.has(f)) {
                      allResults.set(f, []);
                    }
                    allResults.get(f)!.push(kw);
                  }
                } catch {
                  // Individual keyword search failure — continue
                }
              }

              if (allResults.size === 0) {
                console.log(`  ${GRAY}No results found${RESET}`);
                console.log();
                showPrompt();
                return;
              }

              // Sort by relevance: files matching more keywords first
              const sorted = [...allResults.entries()]
                .toSorted((a, b) => b[1].length - a[1].length);

              // Categorize
              const categories: Record<string, Array<{ path: string; keywords: string[] }>> = {
                "📝 Documents": [],
                "💻 Code": [],
                "📁 Other": [],
              };

              for (const [f, kws] of sorted) {
                const lower = f.toLowerCase();
                const entry = { path: f, keywords: kws };
                if (lower.endsWith(".md") || lower.endsWith(".txt") || lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".jcross")) {
                  categories["📝 Documents"].push(entry);
                } else if (lower.endsWith(".swift") || lower.endsWith(".ts") || lower.endsWith(".js") || lower.endsWith(".py") || lower.endsWith(".json")) {
                  categories["💻 Code"].push(entry);
                } else {
                  categories["📁 Other"].push(entry);
                }
              }

              console.log();
              console.log(`  ${GREEN}${allResults.size} unique files found${RESET}`);

              // Show files matching multiple keywords first
              const multiMatch = sorted.filter(([, kws]) => kws.length > 1);
              if (multiMatch.length > 0) {
                console.log();
                console.log(`  ${WHITE}⭐ Multi-keyword matches (${multiMatch.length})${RESET}`);
                for (const [f, kws] of multiMatch.slice(0, 15)) {
                  const display = f.replace(/^\/Users\/[^/]+/, "~");
                  const kwBadges = kws.map(k => `${CYAN}${k}${RESET}`).join(" ");
                  console.log(`    ${GRAY}${display}${RESET} ${kwBadges}`);
                }
              }

              console.log();
              for (const [cat, items] of Object.entries(categories)) {
                if (items.length === 0) {continue;}
                console.log(`  ${WHITE}${cat} (${items.length})${RESET}`);
                for (const item of items.slice(0, 8)) {
                  const display = item.path.replace(/^\/Users\/[^/]+/, "~");
                  const matchCount = item.keywords.length;
                  const badge = matchCount > 1 ? ` ${GREEN}[${matchCount}/${keywords.length}]${RESET}` : "";
                  console.log(`    ${GRAY}${display}${RESET}${badge}`);
                }
                if (items.length > 8) {
                  console.log(`    ${DIM}... and ${items.length - 8} more${RESET}`);
                }
                console.log();
              }

              process.stderr.write(`  ${GRAY}Tip: .read <path> to load a file${RESET}\n`);
              console.log();
            } catch (err: any) {
              console.log(`  ${YELLOW}Search error: ${err.message}${RESET}`);
              console.log();
            }
            showPrompt();
            return;
          }

          // .search-all — Spotlight search + auto-load top multi-keyword matches + summarize
          if (trimmed.startsWith(".search-all ")) {
            const queryStr = trimmed.slice(12).trim();
            if (!queryStr) {
              console.log(`  ${YELLOW}Usage: .search-all <word1> <word2> ...${RESET}`);
              showPrompt();
              return;
            }

            const keywords = queryStr.split(/\s+/).filter(Boolean);
            console.log();
            process.stderr.write(`  ${CYAN}[search-all]${RESET} ${GRAY}🔍 ${keywords.length} keyword(s): ${keywords.join(", ")}${RESET}\n`);

            try {
              const { execSync, spawnSync } = await import("child_process");
              const { readFileSync, statSync } = await import("fs");
              const { dirname, resolve } = await import("path");
              const { fileURLToPath } = await import("url");

              // Collect results per keyword
              const allResults = new Map<string, string[]>();
              for (const kw of keywords) {
                process.stderr.write(`  ${GRAY}  searching "${kw}"...${RESET}\n`);
                try {
                  const raw = execSync(
                    `mdfind "${kw.replace(/"/g, '\\"')}" 2>/dev/null | head -30`,
                    { timeout: 10_000, maxBuffer: 1024 * 1024 }
                  ).toString().trim();
                  for (const f of raw.split("\n").filter(Boolean)) {
                    if (!allResults.has(f)) {allResults.set(f, []);}
                    allResults.get(f)!.push(kw);
                  }
                } catch { /* continue */ }
              }

              // Sort by keyword match count, filter readable text files
              const sorted = [...allResults.entries()]
                .toSorted((a, b) => b[1].length - a[1].length);

              const readableExts = [".md", ".txt", ".swift", ".ts", ".js", ".py", ".json", ".jcross", ".yaml", ".yml", ".csv", ".html", ".css"];
              const candidates = sorted.filter(([f, kws]) => {
                const lower = f.toLowerCase();
                return kws.length >= 1 && readableExts.some(ext => lower.endsWith(ext));
              });

              // Prefer multi-keyword matches, then take top by relevance
              const multiMatch = candidates.filter(([, kws]) => kws.length > 1);
              const singleMatch = candidates.filter(([, kws]) => kws.length === 1);
              const toLoad = [...multiMatch.slice(0, 7), ...singleMatch.slice(0, Math.max(0, 5 - multiMatch.length))];

              if (toLoad.length === 0) {
                console.log(`  ${GRAY}No readable files found${RESET}`);
                console.log();
                showPrompt();
                return;
              }

              process.stderr.write(`  ${GREEN}📂 auto-loading ${toLoad.length} files...${RESET}\n`);

              // Load files into buffer
              (globalThis as any).__spotlightBuffer = (globalThis as any).__spotlightBuffer || [];
              let totalLoaded = 0;
              let totalChars = 0;

              for (const [filePath, kws] of toLoad) {
                try {
                  const stats = statSync(filePath);
                  if (stats.size > 2 * 1024 * 1024) {continue;} // Skip >2MB

                  const content = readFileSync(filePath, "utf-8");
                  const lines = content.split("\n").length;
                  const basename = filePath.split("/").pop() || filePath;
                  const kwBadges = kws.join(",");

                  (globalThis as any).__spotlightBuffer.push({
                    path: filePath,
                    name: basename,
                    content: content,
                    lines: lines,
                  });

                  totalLoaded++;
                  totalChars += content.length;
                  process.stderr.write(`  ${GRAY}  ✅ ${basename} (${lines}L) [${kwBadges}]${RESET}\n`);
                } catch {
                  // Skip unreadable files
                }
              }

              const totalLines = ((globalThis as any).__spotlightBuffer as any[])
                .reduce((sum: number, f: any) => sum + f.lines, 0);

              console.log();
              console.log(`  ${GREEN}${totalLoaded} files loaded (${totalLines} lines, ${(totalChars / 1024).toFixed(1)}KB)${RESET}`);
              console.log(`  ${GRAY}Type your question — files will be auto-attached and summarized${RESET}`);
              console.log();
            } catch (err: any) {
              console.log(`  ${YELLOW}Search error: ${err.message}${RESET}`);
              console.log();
            }
            showPrompt();
            return;
          }

          // .haptic — Haptic notification commands
          if (trimmed.startsWith(".haptic")) {
            const args = trimmed.slice(7).trim();
            if (!hapticActive) {
              console.log(`  ${YELLOW}Haptic server not active${RESET}`);
            } else if (args === "status") {
              console.log(`  ${GREEN}📱 Haptic server: port ${haptic["port"]}, ${haptic.connectedDevices} device(s) connected${RESET}`);
            } else if (args === "test") {
              console.log(`  ${GRAY}Sending test vibration (3x short)...${RESET}`);
              haptic.notifyMessage("Test notification");
            } else if (args.startsWith("morse ")) {
              const text = args.slice(6).trim();
              console.log(`  ${GRAY}Sending morse: "${text}"${RESET}`);
              haptic.notifyMorse(text);
            } else if (args === "error") {
              haptic.notifyError("Test error");
              console.log(`  ${GRAY}Sent error pattern (5x short)${RESET}`);
            } else if (args === "complete") {
              haptic.notifyComplete("Test complete");
              console.log(`  ${GRAY}Sent complete pattern (1x long)${RESET}`);
            } else {
              console.log(`  ${GRAY}Usage: .haptic test|status|morse <text>|error|complete${RESET}`);
            }
            console.log();
            showPrompt();
            return;
          }

          // .search/notes — Spotlight + Apple Notes 二重検索（各キーワード独立）
          if (trimmed.startsWith(".search/notes ")) {
            const queryStr = trimmed.slice(14).trim();
            if (!queryStr) {
              console.log(`  ${YELLOW}Usage: .search/notes <word1> <word2> ...${RESET}`);
              showPrompt();
              return;
            }

            const keywords = queryStr.split(/\s+/).filter(Boolean);
            console.log();
            process.stderr.write(`  ${CYAN}[search/notes]${RESET} ${GRAY}🔍📓 ${keywords.length} keyword(s): ${keywords.join(", ")}${RESET}\n`);
            console.log();

            try {
              const { execSync } = await import("child_process");

              // === Phase 1: Spotlight search ===
              process.stderr.write(`  ${WHITE}Phase 1: Spotlight${RESET}\n`);
              const fileResults = new Map<string, string[]>();

              for (const kw of keywords) {
                process.stderr.write(`  ${GRAY}  🔍 "${kw}"...${RESET}\n`);
                try {
                  const raw = execSync(
                    `mdfind "${kw.replace(/"/g, '\\"')}" 2>/dev/null | head -30`,
                    { timeout: 10_000, maxBuffer: 1024 * 1024 }
                  ).toString().trim();
                  for (const f of raw.split("\n").filter(Boolean)) {
                    if (!fileResults.has(f)) {fileResults.set(f, []);}
                    fileResults.get(f)!.push(kw);
                  }
                } catch { /* continue */ }
              }

              // === Phase 2: Apple Notes search ===
              process.stderr.write(`  ${WHITE}Phase 2: Apple Notes${RESET}\n`);
              const noteResults = new Map<string, string[]>();

              for (const kw of keywords) {
                process.stderr.write(`  ${GRAY}  📓 "${kw}"...${RESET}\n`);
                try {
                  const script = `osascript -e '
                    tell application "Notes"
                      set matchingNames to {}
                      repeat with aNote in every note
                        try
                          if (name of aNote contains "${kw.replace(/"/g, '\\"')}") or (plaintext of aNote contains "${kw.replace(/"/g, '\\"')}") then
                            set end of matchingNames to name of aNote
                          end if
                        end try
                      end repeat
                      return matchingNames
                    end tell
                  ' 2>/dev/null`;

                  const result = execSync(script, { timeout: 30_000, maxBuffer: 1024 * 1024 }).toString().trim();
                  if (result && result !== "{}") {
                    const names = result.split(",").map((s: string) => s.trim()).filter(Boolean);
                    for (const name of names) {
                      if (!noteResults.has(name)) {noteResults.set(name, []);}
                      noteResults.get(name)!.push(kw);
                    }
                  }
                } catch { /* continue */ }
              }

              // === Display combined results ===
              console.log();

              // Files — sort by keyword count
              const sortedFiles = [...fileResults.entries()].toSorted((a, b) => b[1].length - a[1].length);
              const multiFiles = sortedFiles.filter(([, kws]) => kws.length > 1);

              // Notes — sort by keyword count
              const sortedNotes = [...noteResults.entries()].toSorted((a, b) => b[1].length - a[1].length);
              const multiNotes = sortedNotes.filter(([, kws]) => kws.length > 1);

              const totalResults = fileResults.size + noteResults.size;
              console.log(`  ${GREEN}${totalResults} total results${RESET} ${GRAY}(${fileResults.size} files + ${noteResults.size} notes)${RESET}`);

              // Multi-keyword matches (combined)
              if (multiFiles.length > 0 || multiNotes.length > 0) {
                console.log();
                console.log(`  ${WHITE}⭐ Multi-keyword matches${RESET}`);

                for (const [f, kws] of multiFiles.slice(0, 10)) {
                  const display = f.replace(/^\/Users\/[^/]+/, "~");
                  const kwBadges = kws.map(k => `${CYAN}${k}${RESET}`).join(" ");
                  console.log(`    ${GRAY}📄 ${display}${RESET} ${kwBadges}`);
                }
                for (const [name, kws] of multiNotes.slice(0, 10)) {
                  const kwBadges = kws.map(k => `${CYAN}${k}${RESET}`).join(" ");
                  console.log(`    ${MAGENTA}📓 ${name}${RESET} ${kwBadges}`);
                }
              }

              // Files by category
              if (fileResults.size > 0) {
                const categories: Record<string, Array<{ path: string; keywords: string[] }>> = {
                  "📝 Documents": [],
                  "💻 Code": [],
                  "📁 Other": [],
                };

                for (const [f, kws] of sortedFiles) {
                  const lower = f.toLowerCase();
                  const entry = { path: f, keywords: kws };
                  if (lower.endsWith(".md") || lower.endsWith(".txt") || lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".jcross")) {
                    categories["📝 Documents"].push(entry);
                  } else if (lower.endsWith(".swift") || lower.endsWith(".ts") || lower.endsWith(".js") || lower.endsWith(".py") || lower.endsWith(".json")) {
                    categories["💻 Code"].push(entry);
                  } else {
                    categories["📁 Other"].push(entry);
                  }
                }

                console.log();
                for (const [cat, items] of Object.entries(categories)) {
                  if (items.length === 0) {continue;}
                  console.log(`  ${WHITE}${cat} (${items.length})${RESET}`);
                  for (const item of items.slice(0, 8)) {
                    const display = item.path.replace(/^\/Users\/[^/]+/, "~");
                    const badge = item.keywords.length > 1 ? ` ${GREEN}[${item.keywords.length}/${keywords.length}]${RESET}` : "";
                    console.log(`    ${GRAY}${display}${RESET}${badge}`);
                  }
                  if (items.length > 8) {
                    console.log(`    ${DIM}... and ${items.length - 8} more${RESET}`);
                  }
                  console.log();
                }
              }

              // Notes
              if (noteResults.size > 0) {
                console.log(`  ${WHITE}📓 Apple Notes (${noteResults.size})${RESET}`);
                for (const [name, kws] of sortedNotes.slice(0, 15)) {
                  const badge = kws.length > 1 ? ` ${GREEN}[${kws.length}/${keywords.length}]${RESET}` : "";
                  console.log(`    ${MAGENTA}📓 ${name}${RESET}${badge}`);
                }
                if (sortedNotes.length > 15) {
                  console.log(`    ${DIM}... and ${sortedNotes.length - 15} more${RESET}`);
                }
                console.log();
              }

              // === Phase 3: Auto-load top matches ===
              process.stderr.write(`  ${WHITE}Phase 3: Auto-loading top matches${RESET}\n`);

              const { readFileSync, statSync } = await import("fs");
              (globalThis as any).__spotlightBuffer = (globalThis as any).__spotlightBuffer || [];
              let autoLoadCount = 0;
              let autoLoadChars = 0;

              // Auto-load files (prefer multi-keyword, readable text files)
              const readableExts = [".md", ".txt", ".swift", ".ts", ".js", ".py", ".json", ".jcross", ".yaml", ".yml", ".csv", ".html", ".css"];
              const fileMulti = sortedFiles.filter(([f, kws]) =>
                kws.length > 1 && readableExts.some(ext => f.toLowerCase().endsWith(ext))
              );
              const fileSingle = sortedFiles.filter(([f, kws]) =>
                kws.length === 1 && readableExts.some(ext => f.toLowerCase().endsWith(ext))
              );
              const filesToLoad = [...fileMulti.slice(0, 5), ...fileSingle.slice(0, Math.max(0, 3 - fileMulti.length))];

              for (const [filePath, kws] of filesToLoad) {
                try {
                  const stats = statSync(filePath);
                  if (stats.size > 2 * 1024 * 1024) {continue;}
                  const content = readFileSync(filePath, "utf-8");
                  const lines = content.split("\n").length;
                  const basename = filePath.split("/").pop() || filePath;

                  (globalThis as any).__spotlightBuffer.push({
                    path: filePath, name: basename, content, lines,
                  });
                  autoLoadCount++;
                  autoLoadChars += content.length;
                  process.stderr.write(`  ${GRAY}  ✅ 📄 ${basename} (${lines}L) [${kws.join(",")}]${RESET}\n`);
                } catch { /* skip */ }
              }

              // Auto-load Notes (prefer multi-keyword)
              const noteMulti = sortedNotes.filter(([, kws]) => kws.length > 1);
              const noteSingle = sortedNotes.filter(([, kws]) => kws.length === 1);
              const notesToLoad = [...noteMulti.slice(0, 3), ...noteSingle.slice(0, Math.max(0, 2 - noteMulti.length))];

              for (const [noteName, kws] of notesToLoad) {
                try {
                  const noteScript = `osascript -e '
                    tell application "Notes"
                      repeat with aNote in every note
                        if name of aNote contains "${noteName.replace(/"/g, '\\"')}" then
                          return body of aNote
                        end if
                      end repeat
                      return ""
                    end tell
                  ' 2>/dev/null`;

                  const noteContent = execSync(noteScript, { timeout: 15_000, maxBuffer: 2 * 1024 * 1024 }).toString().trim();
                  if (noteContent) {
                    const plainText = noteContent.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
                    const lines = plainText.split("\n").length;

                    (globalThis as any).__spotlightBuffer.push({
                      path: `notes://${noteName}`, name: `📓 ${noteName}`, content: plainText, lines,
                    });
                    autoLoadCount++;
                    autoLoadChars += plainText.length;
                    process.stderr.write(`  ${GRAY}  ✅ 📓 ${noteName} (${lines}L) [${kws.join(",")}]${RESET}\n`);
                  }
                } catch { /* skip */ }
              }

              console.log();
              if (autoLoadCount > 0) {
                const totalLines = ((globalThis as any).__spotlightBuffer as any[])
                  .reduce((sum: number, f: any) => sum + f.lines, 0);
                console.log(`  ${GREEN}${autoLoadCount} items loaded (${totalLines} lines, ${(autoLoadChars / 1024).toFixed(1)}KB)${RESET}`);
                console.log(`  ${GRAY}Type your question — auto-attached and summarized${RESET}`);
              } else {
                console.log(`  ${GRAY}No readable files to auto-load. Use .read or .note manually${RESET}`);
              }
              console.log();
            } catch (err: any) {
              if (err.message?.includes("not allowed")) {
                console.log(`  ${YELLOW}⚠ Grant Notes access: System Settings → Privacy → Automation → Terminal → Notes${RESET}`);
              } else {
                console.log(`  ${YELLOW}Search error: ${err.message}${RESET}`);
              }
              console.log();
            }
            showPrompt();
            return;
          }

          // .read — Read a file into buffer for next message
          if (trimmed.startsWith(".read ")) {
            const filePath = trimmed.slice(6).trim();
            if (!filePath) {
              console.log(`  ${YELLOW}Usage: .read <file path>${RESET}`);
              showPrompt();
              return;
            }

            console.log();
            try {
              const { readFileSync, statSync } = await import("fs");
              const stats = statSync(filePath);
              const sizeMB = stats.size / (1024 * 1024);

              if (sizeMB > 2) {
                console.log(`  ${YELLOW}File too large (${sizeMB.toFixed(1)}MB). Max 2MB.${RESET}`);
                showPrompt();
                return;
              }

              const content = readFileSync(filePath, "utf-8");
              const lines = content.split("\n").length;
              const basename = filePath.split("/").pop() || filePath;

              process.stderr.write(`  ${CYAN}[read]${RESET} ${GRAY}📄 ${basename} (${lines} lines, ${(stats.size / 1024).toFixed(1)}KB)${RESET}\n`);

              (globalThis as any).__spotlightBuffer = (globalThis as any).__spotlightBuffer || [];
              (globalThis as any).__spotlightBuffer.push({
                path: filePath,
                name: basename,
                content: content,
                lines: lines,
              });

              console.log(`  ${GREEN}✅ Loaded "${basename}" — will attach to your next message${RESET}`);
              console.log();
            } catch (err: any) {
              console.log(`  ${YELLOW}Read error: ${err.message}${RESET}`);
              console.log();
            }
            showPrompt();
            return;
          }

          // .notes — Search or list Apple Notes
          if (trimmed.startsWith(".notes")) {
            const query = trimmed.slice(6).trim();
            console.log();

            try {
              const { execSync } = await import("child_process");

              let script: string;
              if (query) {
                script = `osascript -e '
                  tell application "Notes"
                    set matchingNotes to {}
                    repeat with aNote in every note
                      try
                        if (name of aNote contains "${query.replace(/"/g, '\\"')}") or (body of aNote contains "${query.replace(/"/g, '\\"')}") then
                          set end of matchingNotes to name of aNote
                        end if
                      end try
                    end repeat
                    return matchingNotes
                  end tell
                ' 2>/dev/null`;
                process.stderr.write(`  ${CYAN}[notes]${RESET} ${GRAY}🔍 searching: "${query}"${RESET}\n`);
              } else {
                script = `osascript -e '
                  tell application "Notes"
                    set recentNotes to {}
                    repeat with i from 1 to (min(20, count of every note))
                      set aNote to note i
                      set end of recentNotes to name of aNote
                    end repeat
                    return recentNotes
                  end tell
                ' 2>/dev/null`;
                process.stderr.write(`  ${CYAN}[notes]${RESET} ${GRAY}📓 listing recent notes${RESET}\n`);
              }

              const result = execSync(script, { timeout: 30_000, maxBuffer: 1024 * 1024 }).toString().trim();

              if (!result || result === "{}") {
                console.log(`  ${GRAY}No notes found${query ? ` for "${query}"` : ""}${RESET}`);
              } else {
                const items = result.split(",").map((s: string) => s.trim()).filter(Boolean);
                console.log(`  ${GREEN}${items.length} note(s)${RESET}`);
                console.log();
                for (const item of items.slice(0, 20)) {
                  console.log(`  ${GRAY}📓 ${item}${RESET}`);
                }
              }
              console.log();
            } catch (err: any) {
              if (err.message.includes("not allowed")) {
                console.log(`  ${YELLOW}⚠ Grant access: System Settings → Privacy → Automation → Terminal → Notes${RESET}`);
              } else {
                console.log(`  ${YELLOW}Notes error: ${err.message}${RESET}`);
              }
              console.log();
            }
            showPrompt();
            return;
          }

          // .note — Read a specific Apple Note by name
          if (trimmed.startsWith(".note ")) {
            const noteName = trimmed.slice(6).trim();
            if (!noteName) {
              console.log(`  ${YELLOW}Usage: .note <note name>${RESET}`);
              showPrompt();
              return;
            }

            console.log();
            try {
              const { execSync } = await import("child_process");
              const script = `osascript -e '
                tell application "Notes"
                  repeat with aNote in every note
                    if name of aNote contains "${noteName.replace(/"/g, '\\"')}" then
                      return body of aNote
                    end if
                  end repeat
                  return ""
                end tell
              ' 2>/dev/null`;

              const content = execSync(script, { timeout: 15_000, maxBuffer: 2 * 1024 * 1024 }).toString().trim();

              if (!content) {
                console.log(`  ${YELLOW}Note "${noteName}" not found${RESET}`);
              } else {
                const plainText = content.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
                const lines = plainText.split("\n").length;

                process.stderr.write(`  ${CYAN}[note]${RESET} ${GRAY}📓 "${noteName}" (${lines} lines)${RESET}\n`);

                (globalThis as any).__spotlightBuffer = (globalThis as any).__spotlightBuffer || [];
                (globalThis as any).__spotlightBuffer.push({
                  path: `notes://${noteName}`,
                  name: noteName,
                  content: plainText,
                  lines: lines,
                });

                console.log(`  ${GREEN}✅ Loaded note "${noteName}" — will attach to your next message${RESET}`);
              }
              console.log();
            } catch (err: any) {
              console.log(`  ${YELLOW}Notes read error: ${err.message}${RESET}`);
              console.log();
            }
            showPrompt();
            return;
          }

          // Check for spotlight buffer — attach loaded files to message
          const spotlightBuffer = (globalThis as any).__spotlightBuffer as Array<{ path: string; name: string; content: string; lines: number }> | undefined;
          let messageWithAttachments = trimmed;
          let totalAttachedChars = 0;
          let totalAttachedLines = 0;
          let attachedFileCount = 0;

          if (spotlightBuffer && spotlightBuffer.length > 0) {
            // Calculate total size of all buffered documents
            attachedFileCount = spotlightBuffer.length;
            totalAttachedChars = spotlightBuffer.reduce((sum, f) => sum + f.content.length, 0);
            totalAttachedLines = spotlightBuffer.reduce((sum, f) => sum + f.lines, 0);

            const attachments = spotlightBuffer.map((f) =>
              `\n## Attached: ${f.name}\nSource: ${f.path}\n\`\`\`\n${f.content}\n\`\`\``
            ).join("\n");
            messageWithAttachments = `${trimmed}\n${attachments}`;

            process.stderr.write(
              `  ${GRAY}📎 ${attachedFileCount} file(s) attached` +
              ` (${totalAttachedLines} lines, ${(totalAttachedChars / 1024).toFixed(1)}KB total)${RESET}\n`
            );
            (globalThis as any).__spotlightBuffer = []; // Clear after use
          }

          // Estimate input tokens — count TOTAL including attachments
          const totalInputChars = messageWithAttachments.length;
          const inputEstimate = Math.ceil(totalInputChars / 4);
          ctx.inputTokens += inputEstimate;
          ctx.turnCount++;

          console.log();

          // Long document detection: use TOTAL size (user message + all attachments combined)
          // Threshold: 2000 chars (~500 tokens)
          const LONG_INPUT_THRESHOLD = 2000;
          let messageForCommander = messageWithAttachments;

          if (totalInputChars > LONG_INPUT_THRESHOLD) {
            const sourceInfo = attachedFileCount > 0
              ? `${attachedFileCount} docs, ${totalAttachedLines} lines, ${(totalInputChars / 1024).toFixed(1)}KB`
              : `${(totalInputChars / 1024).toFixed(1)}KB`;
            process.stderr.write(`  ${CYAN}[worker/sonnet]${RESET} ${GRAY}📋 long input detected (${sourceInfo}) — summarizing...${RESET}\n`);

            try {
              const { spawnSync } = await import("child_process");
              const { dirname, resolve } = await import("path");
              const { fileURLToPath } = await import("url");
              const cliRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

              // Extract user intent (first line or sentence before the long content)
              const lines = messageWithAttachments.split("\n");
              const firstLine = lines[0] || "";
              const hasUserIntent = firstLine.length < 200 && lines.length > 3;
              const userIntent = hasUserIntent ? firstLine : "";
              const documentBody = hasUserIntent ? lines.slice(1).join("\n") : messageWithAttachments;

              const summaryPrompt = [
                "以下のドキュメントを技術的に正確に要約してください。",
                "重要な構造、クラス名、関数名、設定値、依存関係は必ず保持してください。",
                "要約は日本語で、200行以内に収めてください。",
                "",
                "## ドキュメント",
                documentBody,
              ].join("\n");

              const result = spawnSync(
                "node",
                [
                  "openclaw.mjs", "agent",
                  "--agent", "main",
                  "--local",
                  "--message", summaryPrompt,
                  "--thinking", "off",
                ],
                {
                  cwd: cliRoot,
                  env: {
                    ...process.env,
                    VERANTYX_COMMANDER_MODE: "false", // Worker doesn't need commander restrictions
                  },
                  timeout: 120_000,
                  maxBuffer: 10 * 1024 * 1024,
                }
              );

              const summary = result.stdout?.toString().trim();
              if (summary && summary.length > 50) {
                const reduction = Math.round((1 - summary.length / messageWithAttachments.length) * 100);
                process.stderr.write(`  ${CYAN}[worker/sonnet]${RESET} ${GRAY}✅ summarized (${reduction}% reduction: ${messageWithAttachments.length} → ${summary.length} chars)${RESET}\n`);

                // Compose commander message: user intent + summary
                messageForCommander = [
                  userIntent ? `ユーザーの要求: ${userIntent}` : "",
                  "",
                  "## Worker/Sonnetによるドキュメント要約",
                  summary,
                  "",
                  `(元のドキュメント: ${messageWithAttachments.length}文字 → 要約: ${summary.length}文字)`,
                ].filter(Boolean).join("\n");

                // Update token estimate with reduced size
                const savedTokens = inputEstimate - Math.ceil(messageForCommander.length / 4);
                if (savedTokens > 0) {
                  ctx.inputTokens -= savedTokens;
                  process.stderr.write(`  ${GREEN}  └ saved ~${savedTokens} commander tokens${RESET}\n`);
                }
              } else {
                process.stderr.write(`  ${YELLOW}[worker/sonnet]${RESET} ${GRAY}⚠ summary too short, passing original${RESET}\n`);
              }
            } catch (err: any) {
              process.stderr.write(`  ${YELLOW}[worker/sonnet]${RESET} ${GRAY}⚠ summarization failed: ${err.message}, passing original${RESET}\n`);
            }

            console.log();
          }

          // Send to commander agent
          try {
            const { spawn } = await import("child_process");
            const { dirname, resolve } = await import("path");
            const { fileURLToPath } = await import("url");
            const cliRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
            const thinkingFlag = showThinking ? "high" : "off";

            await new Promise<void>((resolvePromise) => {
              const child = spawn(
                "node",
                [
                  "openclaw.mjs", "agent",
                  "--agent", "main",
                  "--local",
                  "--message", messageForCommander,
                  "--thinking", thinkingFlag,
                ],
                {
                  cwd: cliRoot,
                  env: { ...process.env, VERANTYX_COMMANDER_MODE: "true" },
                  stdio: ["pipe", "pipe", "pipe"],
                }
              );

              let outputChars = 0;

              // stdout: agent response
              child.stdout?.on("data", (chunk: Buffer) => {
                const text = chunk.toString();
                outputChars += text.length;
                process.stdout.write(text);
              });

              // stderr: tool usage + model info
              child.stderr?.on("data", (chunk: Buffer) => {
                const text = chunk.toString();
                for (const line of text.split("\n")) {
                  const t = line.trim();
                  if (!t) {continue;}

                  // Skip noise
                  if (t.includes("Config was last written")) {continue;}
                  if (t.includes("🦞")) {continue;}
                  if (t.includes("[agents/auth-profiles]")) {continue;}
                  if (t.includes("plugin tool failed")) {continue;}
                  if (t.includes("allowlist contains unknown")) {continue;}

                  // Model selection
                  if (t.includes("candidate=")) {
                    const m = t.match(/candidate=(\S+)/);
                    if (m) {
                      currentModel = m[1];
                      process.stderr.write(`  ${getAgentLabel(currentModel)} ${GRAY}selected${RESET}\n`);
                    }
                    continue;
                  }

                  // Tool usage
                  const toolMatch = t.match(/\[tools?\]\s+(\w+)\s+(failed|succeeded|timed)/i) ||
                                    t.match(/\[exec\]/);
                  if (t.includes("[tools]") || t.includes("[exec]")) {
                    ctx.toolCalls++;
                    let toolName = "exec";
                    if (t.includes("read")) {toolName = "📖 read";}
                    else if (t.includes("write")) {toolName = "✍️  write";}
                    else if (t.includes("edit")) {toolName = "✏️  edit";}
                    else if (t.includes("grep")) {toolName = "🔍 grep";}
                    else if (t.includes("find")) {toolName = "📂 find";}
                    else if (t.includes("exec")) {toolName = "⚡ exec";}
                    else if (t.includes("ls")) {toolName = "📁 ls";}
                    else if (t.includes("web")) {toolName = "🌐 web";}
                    else if (t.includes("image")) {toolName = "🖼  image";}
                    else {toolName = `🔧 ${t.slice(0, 30)}`;}

                    process.stderr.write(`  ${getAgentLabel(currentModel)} ${GRAY}${toolName}${RESET}\n`);

                    // Failed tool
                    if (t.includes("failed")) {
                      const reason = t.match(/failed:\s*(.+)/)?.[1] || "";
                      if (reason && !reason.includes("plugin")) {
                        process.stderr.write(`  ${YELLOW}  └ ${reason.slice(0, 80)}${RESET}\n`);
                      }
                    }
                    continue;
                  }

                  // Real errors
                  if (t.includes("Error:") && !t.includes("plugin") && !t.includes("allowlist")) {
                    process.stderr.write(`  ${YELLOW}${t}${RESET}\n`);
                  }
                }
              });

              child.on("close", () => {
                // Update context estimate
                ctx.outputTokens += Math.ceil(outputChars / 4);
                ctx.totalTokens = ctx.inputTokens + ctx.outputTokens;

                // Haptic notification: message received
                if (hapticActive && outputChars > 0) {
                  haptic.notifyMessage("Agent response ready");
                } else if (hapticActive && outputChars === 0) {
                  haptic.notifyError("No reply from agent");
                }

                console.log();
                console.log(formatStatusLine(ctx));
                console.log();
                resolvePromise();
              });

              child.on("error", (err) => {
                // Haptic notification: error
                if (hapticActive) {
                  haptic.notifyError(err.message);
                }
                console.error(`${YELLOW}Error: ${err.message}${RESET}`);
                resolvePromise();
              });
            });
          } catch (err: any) {
            console.error(`${YELLOW}Error: ${err.message}${RESET}`);
          }

          showPrompt();
        });
      };

      showPrompt();
    });
}
