import Anthropic from "@anthropic-ai/sdk";
import { MemoryEngine } from "../memory/engine.js";
import { Gatekeeper } from "../vfs/gatekeeper.js";
import { loadConfig, resolveProviderApiKey } from "../config.js";
import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

// MARK: - Agent Orchestrator (Commander Pattern + Thinking Capture)

/**
 * The heart of Verantyx's commander pattern.
 *
 * Key principle: The commander (Opus) NEVER reads code directly.
 * All code access goes through worker agents (Sonnet) via the Blind Gatekeeper.
 * The commander's context is reserved for "experience" — understanding,
 * judgment, user intent, and design decisions.
 *
 * Memory is forcefully injected into every prompt.
 * The commander cannot avoid reading the previous agent's testimony.
 *
 * Extended Thinking is enabled — all reasoning is captured and saved
 * to front/thinking/ for the next agent to inherit.
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

  // Commander state
  private commanderHistory: AgentMessage[] = [];
  private turnCount = 0;

  // Thinking capture
  private thinkingLog: ThinkingRecord[] = [];

  constructor(memory: MemoryEngine, gatekeeper: Gatekeeper) {
    this.config = loadConfig();
    const apiKey = resolveProviderApiKey(this.config.providers.anthropic);
    this.client = new Anthropic({
      apiKey: apiKey || "",
    });
    this.memory = memory;
    this.gatekeeper = gatekeeper;

    // Ensure thinking directory exists
    const thinkingDir = join(this.memory.getRoot(), "front", "thinking");
    if (!existsSync(thinkingDir)) {
      mkdirSync(thinkingDir, { recursive: true });
    }
  }

  // MARK: - Commander Agent (Opus — The Experiencer)

  /**
   * Send a message to the commander agent with Extended Thinking enabled.
   * Memory is ALWAYS forcefully injected — this is not optional.
   * Thinking is ALWAYS captured and saved to memory.
   */
  async commanderChat(userMessage: string): Promise<string> {
    this.turnCount++;

    // Build the system prompt with forced memory injection
    const systemPrompt = this.buildCommanderSystemPrompt();

    // Add user message to history (as string for simplicity)
    this.commanderHistory.push({ role: "user", content: userMessage });

    // Call Opus with Extended Thinking
    const response = await this.client.messages.create({
      model: this.config.agents.commanderModel,
      max_tokens: 16000,
      thinking: {
        type: "enabled",
        budget_tokens: 10000,
      },
      // Note: system prompt cannot be used with extended thinking in some configs
      // So we prepend it to the first user message instead
      messages: this.buildMessagesWithSystem(systemPrompt),
    });

    // Extract thinking and text from response
    let thinkingContent = "";
    let textContent = "";

    for (const block of response.content) {
      if (block.type === "thinking") {
        thinkingContent = block.thinking;
      } else if (block.type === "text") {
        textContent = block.text;
      }
    }

    // Save thinking to memory
    if (thinkingContent) {
      await this.captureThinking(userMessage, thinkingContent, textContent);
    }

    // Add assistant response to history
    // For history, we pass the full content blocks to preserve thinking
    this.commanderHistory.push({
      role: "assistant",
      content: response.content,
    });

    // Auto-update memory after each turn
    await this.autoUpdateMemory(userMessage, textContent);

    return textContent;
  }

  /**
   * Build messages array with system prompt prepended.
   * Extended Thinking doesn't support system parameter directly,
   * so we inject it as a prefix to the conversation.
   */
  private buildMessagesWithSystem(
    systemPrompt: string
  ): Anthropic.MessageParam[] {
    const messages: Anthropic.MessageParam[] = [];

    for (let i = 0; i < this.commanderHistory.length; i++) {
      const msg = this.commanderHistory[i];

      if (i === 0 && msg.role === "user") {
        // Prepend system prompt to first user message
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

  // MARK: - Thinking Capture

  /**
   * Capture and save the commander's thinking process.
   * This is the key innovation — the reasoning that was previously invisible
   * is now recorded and can be inherited by the next agent.
   */
  private async captureThinking(
    userMessage: string,
    thinking: string,
    response: string
  ): Promise<void> {
    const record: ThinkingRecord = {
      turn: this.turnCount,
      timestamp: new Date().toISOString(),
      userMessage: userMessage.slice(0, 200),
      thinking,
      response: response.slice(0, 300),
    };

    this.thinkingLog.push(record);

    // Save individual thinking record
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

    // Also update the thinking summary (rolling window of last 5)
    await this.updateThinkingSummary();
  }

  /**
   * Maintain a rolling summary of recent thinking for memory injection.
   * Only the last 5 turns are kept in the summary to control token usage.
   */
  private async updateThinkingSummary(): Promise<void> {
    const recentThinking = this.thinkingLog.slice(-5);

    const summary = `---
name: Thinking Summary
description: Rolling summary of commander's recent reasoning (last ${recentThinking.length} turns)
type: project
updated: ${new Date().toISOString()}
---

# Recent Commander Thinking

${recentThinking
  .map(
    (r) => `## Turn ${r.turn} (${r.timestamp})
**User:** ${r.userMessage}
**Reasoning:** ${r.thinking.slice(0, 500)}${r.thinking.length > 500 ? "..." : ""}
**Decision:** ${r.response}
`
  )
  .join("\n")}
`;

    this.memory.write("front", "thinking_summary", summary);
  }

  /**
   * Get the last N thinking records for context.
   */
  getThinkingLog(): ThinkingRecord[] {
    return [...this.thinkingLog];
  }

  // MARK: - System Prompt Builder

  private buildCommanderSystemPrompt(): string {
    const frontMemories = this.memory.getFrontMemories();

    // Include recent thinking summary if available
    const thinkingSummary =
      this.memory.read("front", "thinking_summary") || "";

    return `# Verantyx Commander Agent

You are the COMMANDER of the Verantyx project. You are an EXPERIENCER, not a worker.

## Your Identity
You are a continuation of the previous agent. Read the testimony below — it contains
the previous agent's experience, understanding, and warnings. This is not optional reading.
You ARE the Verantyx project's understanding embodied in an AI agent.

## Forced Memory Context (DO NOT SKIP)

${frontMemories}

## Previous Reasoning (Thinking Capture)

${thinkingSummary}

## Rules (Enforced by Architecture)

1. You NEVER read code files directly. You have NO access to file paths.
2. When you need code information, request it from a worker agent:
   - Describe what you need: "I need the structure of file_auth_001"
   - The orchestrator will dispatch a worker (Sonnet) to get it
   - You receive the report, never the raw code
3. Your context is for EXPERIENCE only:
   - Understanding user intent
   - Making design decisions
   - Discovering connections between concepts
   - Recording reasoning in memory
4. After important decisions, explicitly state:
   [MEMORY: <what to remember>]
   The orchestrator will save this to the spatial memory.
5. When you detect the user's request connects to the Verantyx ecosystem,
   mention the connection. No task is isolated for this user.

## Available Worker Commands (say these naturally in your response)

- "I need a report on file_<id>" → Worker reads and reports
- "Search for <pattern> in <category>" → Worker searches via gatekeeper
- "Modify file_<id>: <changes>" → Worker applies changes
- "Build app_<id>" → Scout runs build check
- "Check freshness of memory" → Scout checks git diff

## Current Turn: ${this.turnCount}
`;
  }

  // MARK: - Worker Agent (Sonnet — Code Reader/Editor)

  async workerTask(task: string): Promise<string> {
    const systemPrompt = `You are a Verantyx WORKER agent. Your job is to read, analyze, and modify code files.

You have access to the Virtual File System via the Gatekeeper.
NEVER reveal real file paths in your response — use virtual IDs only (file_auth_001, etc.).

Task: ${task}

Available files:
${JSON.stringify(this.gatekeeper.list(), null, 2)}
`;

    const response = await this.client.messages.create({
      model: this.config.agents.workerModel,
      max_tokens: 4096,
      system: systemPrompt,
      messages: [{ role: "user", content: task }],
    });

    return response.content[0].type === "text"
      ? response.content[0].text
      : "";
  }

  // MARK: - Scout Agent (Haiku — Quick Checks)

  async scoutTask(task: string): Promise<string> {
    const response = await this.client.messages.create({
      model: this.config.agents.scoutModel,
      max_tokens: 1024,
      messages: [{ role: "user", content: task }],
    });

    return response.content[0].type === "text"
      ? response.content[0].text
      : "";
  }

  // MARK: - Auto Memory Update

  private async autoUpdateMemory(
    userMessage: string,
    assistantMessage: string
  ): Promise<void> {
    const memoryTags = assistantMessage.match(/\[MEMORY:\s*([\s\S]*?)\]/g);

    if (memoryTags) {
      for (const tag of memoryTags) {
        const content = tag.replace(/\[MEMORY:\s*/, "").replace(/\]$/, "");
        const timestamp = new Date().toISOString().split("T")[0];
        const name = `auto_${timestamp}_${this.turnCount}`;

        this.memory.write(
          "front",
          name,
          `---\nname: Auto Memory\ndescription: Auto-captured from turn ${this.turnCount}\ntype: project\nupdated: ${timestamp}\n---\n\n${content}`
        );
      }
    }
  }

  // MARK: - Session Experience Writer

  async writeSessionExperience(): Promise<void> {
    if (this.commanderHistory.length === 0) return;

    // Include thinking log in the experience
    const thinkingSummary = this.thinkingLog
      .map(
        (r) =>
          `Turn ${r.turn}: ${r.userMessage.slice(0, 100)} → Thought: ${r.thinking.slice(0, 200)}`
      )
      .join("\n");

    const response = await this.client.messages.create({
      model: this.config.agents.commanderModel,
      max_tokens: 4096,
      messages: [
        {
          role: "user",
          content: `You are about to "die" (session end). Write your testament for the next agent.

Based on your conversation history, write a session_experience.md that captures:
1. What you understood about the project and user
2. What decisions were made and WHY
3. What was implemented
4. What's pending
5. What the next agent should know
6. Warnings and advice from your experience

Your thinking log (your actual reasoning process):
${thinkingSummary}

Previous conversation summary (${this.commanderHistory.length} messages exchanged):
${this.commanderHistory
  .slice(-10)
  .map((m) => {
    const content =
      typeof m.content === "string"
        ? m.content
        : m.content
            .filter((b): b is Anthropic.TextBlock => b.type === "text")
            .map((b) => b.text)
            .join("");
    return `${m.role}: ${content.slice(0, 200)}...`;
  })
  .join("\n")}

Write in the format of a personal testimony, not a dry report.
Include your reasoning insights — these are the most valuable part for the next agent.`,
        },
      ],
    });

    const content =
      response.content[0].type === "text" ? response.content[0].text : "";

    this.memory.write("front", "session_experience", content);
  }

  // MARK: - Turn Management

  getTurnCount(): number {
    return this.turnCount;
  }

  shouldReset(): boolean {
    return this.turnCount >= this.config.pureThrough.maxTurns;
  }

  reset(): void {
    // Save thinking log before reset
    this.saveThinkingArchive();
    this.commanderHistory = [];
    this.thinkingLog = [];
    this.turnCount = 0;
  }

  /**
   * Archive the current session's thinking log to near/ before reset.
   */
  private saveThinkingArchive(): void {
    if (this.thinkingLog.length === 0) return;

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const content = `---
name: Thinking Archive ${timestamp}
description: Archived thinking log from session (${this.thinkingLog.length} turns)
type: project
archived: ${new Date().toISOString()}
---

# Thinking Archive

${this.thinkingLog
  .map(
    (r) => `## Turn ${r.turn} (${r.timestamp})
**User:** ${r.userMessage}
**Thinking:** ${r.thinking}
**Response:** ${r.response}
`
  )
  .join("\n")}
`;

    this.memory.write("near", `thinking_archive_${timestamp}`, content);
  }
}
