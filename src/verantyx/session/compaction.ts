/**
 * Session Compaction — claw-code pattern for token budget management
 *
 * When context exceeds threshold, old messages are compacted
 * into a summary and stored in spatial memory.
 */

export interface CompactionConfig {
  autoCompactThreshold: number;  // Token count to trigger compaction
  keepRecentTurns: number;       // Number of recent turns to preserve
  summaryMaxTokens: number;      // Max tokens for the summary
}

export const DEFAULT_COMPACTION_CONFIG: CompactionConfig = {
  autoCompactThreshold: 100_000,
  keepRecentTurns: 5,
  summaryMaxTokens: 2000,
};

export interface CompactionResult {
  removedMessageCount: number;
  summary: string;
  savedToMemory: string;  // Path in spatial memory
  tokensBefore: number;
  tokensAfter: number;
}

export interface SessionMessage {
  role: "user" | "assistant" | "tool";
  content: string;
  timestamp: number;
  toolName?: string;
}

/**
 * Estimate token count (rough: 1 token ≈ 4 chars)
 */
export function estimateTokens(messages: SessionMessage[]): number {
  return messages.reduce((sum, m) => sum + Math.ceil(m.content.length / 4), 0);
}

/**
 * Check if compaction is needed
 */
export function shouldCompact(
  messages: SessionMessage[],
  config: CompactionConfig = DEFAULT_COMPACTION_CONFIG
): boolean {
  return estimateTokens(messages) > config.autoCompactThreshold;
}

/**
 * Generate compaction summary from messages being removed
 */
export function generateCompactionSummary(
  messages: SessionMessage[],
  maxTokens: number = 2000
): string {
  const lines: string[] = [];
  lines.push("# Session Compaction Summary");
  lines.push(`Compacted ${messages.length} messages at ${new Date().toISOString()}`);
  lines.push("");

  // Extract key decisions and findings
  for (const msg of messages) {
    if (msg.role === "assistant") {
      // Extract [MEMORY:] tags
      const memoryTags = msg.content.match(/\[MEMORY:\s*([\s\S]*?)\]/g);
      if (memoryTags) {
        for (const tag of memoryTags) {
          lines.push(`- ${tag.replace(/\[MEMORY:\s*/, "").replace(/\]$/, "")}`);
        }
      }

      // Extract key decisions (lines starting with "→" or "Decision:")
      const decisions = msg.content
        .split("\n")
        .filter(l => /^[→•\-]\s|Decision:|Conclusion:|Result:/.test(l.trim()))
        .slice(0, 10);
      if (decisions.length > 0) {
        lines.push("## Key Decisions");
        lines.push(...decisions.map(d => d.trim()));
      }
    }
  }

  // Truncate to max tokens
  const maxChars = maxTokens * 4;
  const result = lines.join("\n");
  return result.length > maxChars ? result.slice(0, maxChars) + "\n...(truncated)" : result;
}

/**
 * Perform compaction
 */
export function compactSession(
  messages: SessionMessage[],
  config: CompactionConfig = DEFAULT_COMPACTION_CONFIG
): { remaining: SessionMessage[]; result: CompactionResult } {
  const tokensBefore = estimateTokens(messages);

  // Keep recent turns
  const keepCount = Math.min(config.keepRecentTurns * 2, messages.length);
  const toRemove = messages.slice(0, messages.length - keepCount);
  const remaining = messages.slice(messages.length - keepCount);

  // Generate summary
  const summary = generateCompactionSummary(toRemove, config.summaryMaxTokens);

  // Inject summary as first message
  const summaryMessage: SessionMessage = {
    role: "user",
    content: `[COMPACTION SUMMARY]\n${summary}\n[/COMPACTION SUMMARY]`,
    timestamp: Date.now(),
  };
  remaining.unshift(summaryMessage);

  return {
    remaining,
    result: {
      removedMessageCount: toRemove.length,
      summary,
      savedToMemory: `near/compaction_${Date.now()}.md`,
      tokensBefore,
      tokensAfter: estimateTokens(remaining),
    },
  };
}
