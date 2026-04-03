/**
 * Tool Hooks — Pre/post tool execution hooks (claw-code pattern)
 *
 * Hooks fire before and after every tool use, enabling:
 * - Auto-audit of responses
 * - Haptic notifications
 * - Memory auto-update
 * - Stale memory detection
 * - Anomaly flagging
 */

export type HookEvent =
  | "pre_tool_use"
  | "post_tool_use"
  | "pre_turn"
  | "post_turn"
  | "session_start"
  | "session_end"
  | "memory_write"
  | "compaction";

export interface HookContext {
  event: HookEvent;
  toolName?: string;
  input?: string;
  output?: string;
  isError?: boolean;
  turnCount?: number;
  sessionId?: string;
}

export type HookHandler = (ctx: HookContext) => Promise<HookResult>;

export interface HookResult {
  abort?: boolean;
  message?: string;
  modifiedOutput?: string;
}

export class HookRunner {
  private hooks: Map<HookEvent, HookHandler[]> = new Map();

  register(event: HookEvent, handler: HookHandler): void {
    const existing = this.hooks.get(event) || [];
    existing.push(handler);
    this.hooks.set(event, existing);
  }

  async run(ctx: HookContext): Promise<HookResult> {
    const handlers = this.hooks.get(ctx.event) || [];
    for (const handler of handlers) {
      const result = await handler(ctx);
      if (result.abort) {
        return result;
      }
    }
    return {};
  }
}

// ── Built-in Hooks ──

/** Auto-audit: Check responses for hallucination markers */
export function createAutoAuditHook(
  auditFn: (content: string) => Promise<{ verdict: string; confidence: number }>
): HookHandler {
  return async (ctx) => {
    if (ctx.event !== "post_turn" || !ctx.output) return {};

    // Only audit substantial responses
    if (ctx.output.length < 200) return {};

    // Check for hallucination indicators
    const indicators = [
      /I (?:believe|think|assume) (?:the|this|that)/i,
      /(?:probably|likely|might be|could be)/i,
    ];

    const hasUncertainty = indicators.some(r => r.test(ctx.output || ""));
    if (!hasUncertainty) return {};

    try {
      const result = await auditFn(ctx.output);
      if (result.verdict === "HALLUCINATION") {
        return {
          message: `⚠️ Possible hallucination detected (confidence: ${result.confidence})`,
        };
      }
    } catch {
      // Audit failure is non-fatal
    }
    return {};
  };
}

/** Haptic: Send vibration on events */
export function createHapticHook(
  notifyFn: (pattern: string) => Promise<void>
): HookHandler {
  return async (ctx) => {
    switch (ctx.event) {
      case "post_turn":
        if (ctx.isError) {
          await notifyFn("error"); // 5 vibrations
        } else {
          await notifyFn("message"); // 3 vibrations
        }
        break;
      case "session_end":
        await notifyFn("complete"); // 1 long vibration
        break;
      case "compaction":
        await notifyFn("warning"); // 2 vibrations
        break;
    }
    return {};
  };
}

/** Memory lifecycle: Auto-move wills from front to near/mid/deep */
export function createMemoryLifecycleHook(
  memoryRoot: string
): HookHandler {
  return async (ctx) => {
    if (ctx.event !== "session_start") return {};

    const { readdirSync, renameSync, existsSync, mkdirSync } = await import("fs");
    const { join, basename } = await import("path");

    // Move old wills: front/will_* → near/ after 1 session
    const frontDir = join(memoryRoot, "front");
    const nearDir = join(memoryRoot, "near");
    const midDir = join(memoryRoot, "mid");

    if (!existsSync(nearDir)) mkdirSync(nearDir, { recursive: true });
    if (!existsSync(midDir)) mkdirSync(midDir, { recursive: true });

    if (existsSync(frontDir)) {
      const wills = readdirSync(frontDir).filter(f => f.startsWith("will_"));
      for (const will of wills) {
        const src = join(frontDir, will);
        const dest = join(nearDir, will);
        try {
          renameSync(src, dest);
        } catch { /* ignore */ }
      }
    }

    // Move old near/ wills to mid/
    if (existsSync(nearDir)) {
      const { statSync } = await import("fs");
      const oldWills = readdirSync(nearDir).filter(f => f.startsWith("will_"));
      const now = Date.now();
      for (const will of oldWills) {
        try {
          const stat = statSync(join(nearDir, will));
          const ageHours = (now - stat.mtimeMs) / (1000 * 60 * 60);
          if (ageHours > 48) {
            renameSync(join(nearDir, will), join(midDir, will));
          }
        } catch { /* ignore */ }
      }
    }

    return {};
  };
}
