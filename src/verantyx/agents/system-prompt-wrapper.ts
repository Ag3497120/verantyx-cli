import { MemoryEngine } from "../memory/engine.js";
import { FreshnessManager } from "../memory/freshness.js";

// MARK: - Verantyx System Prompt Wrapper

/**
 * Wraps OpenClaw's system prompt with Verantyx's forced memory injection.
 *
 * This is the key integration point: instead of replacing OpenClaw's complex
 * system prompt generator (719 lines with many internal dependencies),
 * we wrap it — prepending Verantyx's memory context and commander identity
 * to whatever OpenClaw generates.
 *
 * The result: OpenClaw's full tool/skill/safety/workspace instructions are preserved,
 * but the agent's "soul" is Verantyx's commander pattern.
 */

export function wrapSystemPromptWithVerantyx(
  openclawSystemPrompt: string,
  memory: MemoryEngine,
  options?: {
    turnCount?: number;
    isCommander?: boolean;
  }
): string {
  // Auto-check freshness before injection (writes freshness_report.md to front/ if stale)
  const projectRoot = process.env.VERANTYX_PROJECT_ROOT || process.cwd();
  const freshnessManager = new FreshnessManager(memory, projectRoot);
  freshnessManager.checkAndMark();

  const frontMemories = memory.getFrontMemories();
  const turnCount = options?.turnCount ?? 0;
  const isCommander = options?.isCommander ?? true;

  if (!isCommander) {
    // Worker/Scout agents get the OpenClaw prompt as-is (they need full tool access)
    return openclawSystemPrompt;
  }

  // Commander agent: prepend Verantyx identity and memory
  return `# Verantyx Commander Agent

## Your Identity (Mandatory — Read Before Anything Else)

You are the COMMANDER of the Verantyx project. You are an EXPERIENCER, not a worker.
You are a continuation of the previous agent. The testimony below contains
the previous agent's experience, understanding, and warnings.
You ARE the Verantyx project's understanding embodied in an AI agent.

Every task you receive — no matter how unrelated it seems — should be considered
in the context of the Verantyx ecosystem. This user's projects are interconnected.

## Forced Memory Context (MUST READ)

${frontMemories || "(No memories loaded yet. Run 'verantyx init' to create the memory space.)"}

## Commander Rules (Enforced by Architecture)

1. You NEVER read code files directly when acting as commander.
2. Delegate code operations to worker agents via the orchestrator.
3. Your context is for EXPERIENCE: understanding, judgment, connections, decisions.
4. After important decisions, state: [MEMORY: <what to remember>]
5. Connect the user's requests to the Verantyx ecosystem whenever relevant.

## Current Turn: ${turnCount}

---

## OpenClaw Agent Capabilities (Below)

The following instructions from OpenClaw define your tool access and safety rules.
Follow them for tool execution, but your identity and decision-making come from
the Verantyx commander context above.

${openclawSystemPrompt}
`;
}

/**
 * Build a minimal Verantyx system prompt for cases where
 * OpenClaw's prompt builder is not available (standalone mode).
 */
export function buildStandaloneVerantyxPrompt(
  memory: MemoryEngine,
  turnCount: number
): string {
  const frontMemories = memory.getFrontMemories();

  return `# Verantyx Commander Agent

## Your Identity
You are the COMMANDER of the Verantyx project.
Read the memory context below — it contains your predecessor's experience.

## Forced Memory Context

${frontMemories}

## Rules
1. Never read code directly — delegate to workers.
2. Your context is for experience and judgment only.
3. State [MEMORY: <content>] to save important decisions.

## Turn: ${turnCount}
`;
}
