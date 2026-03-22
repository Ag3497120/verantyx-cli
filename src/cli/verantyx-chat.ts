import type { Command } from "commander";
import { createInterface } from "readline";
import { MemoryEngine, type MemoryZone } from "../verantyx/memory/engine.js";
import { Gatekeeper } from "../verantyx/vfs/gatekeeper.js";
import { onAgentEvent } from "../infra/agent-events.js";

// MARK: - Verantyx Chat Command

/**
 * Verantyx-enhanced chat command.
 * Displays thinking blocks, tool usage with agent labels,
 * and forced memory injection status.
 */

// ANSI colors
const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const MAGENTA = "\x1b[35m";
const GRAY = "\x1b[90m";
const DIM = "\x1b[2m";
const BOLD = "\x1b[1m";
const RESET = "\x1b[0m";

const AGENT_LABELS: Record<string, string> = {
  "claude-opus-4-6": `${MAGENTA}${BOLD}[Commander/Opus]${RESET}`,
  "claude-sonnet-4-6": `${CYAN}[Worker/Sonnet]${RESET}`,
  "claude-haiku-4-5-20251001": `${GRAY}[Scout/Haiku]${RESET}`,
};

function getAgentLabel(model?: string): string {
  if (!model) return `${GRAY}[Agent]${RESET}`;
  return AGENT_LABELS[model] || `${GRAY}[Agent/${model}]${RESET}`;
}

function formatThinking(thinking: string): string {
  const lines = thinking.split("\n");
  const maxLines = 15; // Show first 15 lines of thinking
  const display = lines.slice(0, maxLines);

  let output = `\n${DIM}${YELLOW}💭 Thinking...${RESET}\n`;
  for (const line of display) {
    output += `${DIM}${GRAY}  │ ${line}${RESET}\n`;
  }
  if (lines.length > maxLines) {
    output += `${DIM}${GRAY}  │ ... (${lines.length - maxLines} more lines)${RESET}\n`;
  }
  output += `${DIM}${GRAY}  └─────${RESET}\n`;
  return output;
}

function formatToolUse(toolName: string, model?: string): string {
  const label = getAgentLabel(model);
  const toolIcons: Record<string, string> = {
    read: "📖",
    write: "✍️",
    edit: "✏️",
    apply_patch: "🩹",
    exec: "⚡",
    grep: "🔍",
    find: "📂",
    ls: "📁",
    web_search: "🌐",
    web_fetch: "🌐",
    message: "💬",
  };
  const icon = toolIcons[toolName] || "🔧";
  return `${label} ${icon} ${toolName}`;
}

function formatToolResult(toolName: string, result: string, model?: string): string {
  const label = getAgentLabel(model);
  const lines = result.split("\n");
  const maxLines = 5;
  const display = lines.slice(0, maxLines);

  let output = `${GRAY}  ${label} ← ${toolName} result:${RESET}\n`;
  for (const line of display) {
    output += `${DIM}${GRAY}    ${line.slice(0, 120)}${RESET}\n`;
  }
  if (lines.length > maxLines) {
    output += `${DIM}${GRAY}    ... (${lines.length - maxLines} more lines)${RESET}\n`;
  }
  return output;
}

export function registerVerantyxChatCli(program: Command) {
  program
    .command("vchat")
    .description("Verantyx commander chat with thinking display and tool tracking")
    .option("--no-thinking", "Hide thinking blocks")
    .option("--no-tools", "Hide tool usage details")
    .option("-m, --model <model>", "Override commander model")
    .action(async (opts: { thinking?: boolean; tools?: boolean; model?: string }) => {
      const showThinking = opts.thinking !== false;
      const showTools = opts.tools !== false;

      // Resolve memory
      const memoryRoot = process.env.VERANTYX_MEMORY_ROOT;
      let memoryStatus = "OFF";
      if (memoryRoot) {
        try {
          const memory = new MemoryEngine(memoryRoot);
          const front = memory.getFrontMemories();
          const tokenEstimate = Math.ceil(front.length / 4);
          memoryStatus = `ON (${tokenEstimate} tokens injected)`;
        } catch {
          memoryStatus = "ERROR";
        }
      }

      console.log(`\n${CYAN}${BOLD}🧬 Verantyx Commander Chat${RESET}`);
      console.log(`${GRAY}   Memory injection: ${memoryStatus}${RESET}`);
      console.log(`${GRAY}   Thinking display: ${showThinking ? "ON" : "OFF"}${RESET}`);
      console.log(`${GRAY}   Tool tracking:    ${showTools ? "ON" : "OFF"}${RESET}`);
      console.log(`${GRAY}   Commander mode:   ${process.env.VERANTYX_COMMANDER_MODE === "true" ? "ON (read/write/edit blocked)" : "OFF"}${RESET}`);
      console.log(`${GRAY}   Type "exit" to end, "memory" to list, "inject" to preview${RESET}`);
      console.log();

      // Listen to agent events for real-time tool/thinking display
      let currentModel: string | undefined;

      onAgentEvent((evt) => {
        const { stream, data } = evt;

        // Extract tool name from various possible fields
        const toolName = (data.name || data.toolName || data.tool) as string | undefined;

        // Extract model from various possible fields
        const model = (data.model || data.provider) as string | undefined;
        if (model) currentModel = model;

        if (stream === "tool" && showTools && toolName) {
          const phase = data.phase || data.status || data.event;
          if (phase === "start" || phase === "invoke" || phase === "call" || !phase) {
            const toolLine = formatToolUse(toolName, currentModel);
            process.stdout.write(`${toolLine}\n`);
          }
          if (phase === "end" || phase === "result" || phase === "complete") {
            if (data.result || data.output) {
              const resultStr = typeof (data.result || data.output) === "string"
                ? (data.result || data.output) as string
                : JSON.stringify(data.result || data.output).slice(0, 500);
              process.stdout.write(formatToolResult(toolName, resultStr, currentModel));
            }
          }
        }

        if (stream === "assistant" && showThinking) {
          // Check various thinking field names
          const thinking = (data.thinking || data.thought || data.reasoning) as string | undefined;
          if (thinking) {
            process.stdout.write(formatThinking(thinking));
          }
        }

        if (stream === "lifecycle") {
          if (data.model) {
            currentModel = data.model as string;
          }
          if (data.event === "model_selected" || data.event === "run_start") {
            const m = (data.model || data.modelId) as string | undefined;
            if (m) {
              currentModel = m;
              process.stdout.write(`${getAgentLabel(m)} ${GRAY}selected${RESET}\n`);
            }
          }
        }
      });

      // Interactive loop
      const rl = createInterface({
        input: process.stdin,
        output: process.stdout,
      });

      const prompt = () => {
        rl.question(`${GREEN}💬 You: ${RESET}`, async (input) => {
          const trimmed = input.trim();

          if (!trimmed) { prompt(); return; }
          if (trimmed === "exit" || trimmed === "quit") {
            console.log(`${GRAY}\nSession ended.${RESET}`);
            rl.close();
            return;
          }

          // Built-in commands
          if (trimmed === "memory" && memoryRoot) {
            const memory = new MemoryEngine(memoryRoot);
            const entries = memory.list();
            for (const e of entries) {
              console.log(`  ${GRAY}${e.zone}/${e.name}${RESET}`);
            }
            console.log();
            prompt();
            return;
          }
          if (trimmed === "inject" && memoryRoot) {
            const memory = new MemoryEngine(memoryRoot);
            const front = memory.getFrontMemories();
            console.log(`\n${YELLOW}💉 Injection Preview (${Math.ceil(front.length / 4)} tokens):${RESET}`);
            console.log(front.slice(0, 500) + (front.length > 500 ? "\n..." : ""));
            console.log();
            prompt();
            return;
          }

          console.log();

          // Send to agent directly (--local, no gateway needed)
          try {
            const { spawn } = await import("child_process");
            const { dirname, resolve } = await import("path");
            const { fileURLToPath } = await import("url");
            const cliRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
            const thinkingFlag = showThinking ? "high" : "off";

            console.log(`${GRAY}⏳ Thinking...${RESET}`);

            await new Promise<void>((resolvePromise) => {
              const child = spawn(
                "node",
                [
                  "openclaw.mjs", "agent",
                  "--agent", "main",
                  "--local",
                  "--message", trimmed,
                  "--thinking", thinkingFlag,
                ],
                {
                  cwd: cliRoot,
                  env: { ...process.env, VERANTYX_COMMANDER_MODE: "true" },
                  stdio: ["pipe", "pipe", "pipe"],
                }
              );

              // stdout: agent response (stream directly)
              child.stdout?.on("data", (chunk: Buffer) => {
                process.stdout.write(chunk);
              });

              // stderr: tool usage, errors, logs — format with agent labels
              child.stderr?.on("data", (chunk: Buffer) => {
                const text = chunk.toString();
                for (const line of text.split("\n")) {
                  const trimLine = line.trim();
                  if (!trimLine) continue;

                  // Skip noise
                  if (trimLine.includes("Config was last written")) continue;
                  if (trimLine.includes("🦞")) continue;
                  if (trimLine.includes("[agents/auth-profiles]")) continue;

                  // Tool usage — format with agent labels
                  if (trimLine.includes("[tools]") && trimLine.includes("exec")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}⚡ exec${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("read")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}📖 read${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("write")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}✍️ write${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("edit")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}✏️ edit${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("grep")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}🔍 grep${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("find")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}📂 find${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("ls")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}📁 ls${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("web_search")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}🌐 web_search${RESET}\n`);
                  } else if (trimLine.includes("[tools]") && trimLine.includes("image")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}🖼️ image${RESET}\n`);
                  } else if (trimLine.includes("[exec]") || trimLine.includes("exec ")) {
                    process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}⚡ exec${RESET}\n`);
                  // Model selection
                  } else if (trimLine.includes("model-fallback") && trimLine.includes("candidate=")) {
                    const modelMatch = trimLine.match(/candidate=(\S+)/);
                    if (modelMatch) {
                      currentModel = modelMatch[1];
                      process.stderr.write(`${getAgentLabel(currentModel)} ${GRAY}selected${RESET}\n`);
                    }
                  // Errors worth showing
                  } else if (trimLine.includes("Error:") && !trimLine.includes("plugin tool failed") && !trimLine.includes("allowlist")) {
                    process.stderr.write(`${YELLOW}  ${trimLine}${RESET}\n`);
                  }
                }
              });

              child.on("close", () => {
                console.log();
                resolvePromise();
              });
              child.on("error", (err) => {
                console.error(`${YELLOW}Error: ${err.message}${RESET}`);
                resolvePromise();
              });
            });
          } catch (err: any) {
            console.error(`${YELLOW}Error: ${err.message}${RESET}`);
          }

          console.log();
          prompt();
        });
      };

      prompt();
    });
}
