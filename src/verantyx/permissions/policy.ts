/**
 * Permission Policy — claw-code pattern ported to Verantyx
 *
 * Mode-based tool permission enforcement.
 * Commander mode blocks read/write/edit by default.
 * Custom policies can be defined per-session.
 */

export type PermissionMode = "commander" | "worker" | "readonly" | "full";

export type PermissionOutcome = "approved" | "denied" | "needs_prompt";

export interface PermissionPolicy {
  mode: PermissionMode;
  blockedTools: Set<string>;
  allowedTools: Set<string>;
  execWhitelist: string[];
}

export const COMMANDER_POLICY: PermissionPolicy = {
  mode: "commander",
  blockedTools: new Set(["read", "write", "edit", "apply_patch"]),
  allowedTools: new Set([
    "exec", "web_search", "web_fetch", "sessions_spawn",
    "sessions_yield", "sessions_send", "sessions_list",
    "sessions_history", "subagents", "session_status",
    "image", "image_generate", "cron", "process",
  ]),
  execWhitelist: ["node", "openclaw", "python3", "git", "pnpm", "npm"],
};

export const WORKER_POLICY: PermissionPolicy = {
  mode: "worker",
  blockedTools: new Set([]),
  allowedTools: new Set(["read", "write", "edit", "exec", "apply_patch"]),
  execWhitelist: [],
};

export const READONLY_POLICY: PermissionPolicy = {
  mode: "readonly",
  blockedTools: new Set(["write", "edit", "exec", "apply_patch"]),
  allowedTools: new Set(["read", "web_search", "web_fetch"]),
  execWhitelist: [],
};

export function checkPermission(
  policy: PermissionPolicy,
  toolName: string,
  execCommand?: string
): PermissionOutcome {
  if (policy.blockedTools.has(toolName)) {
    return "denied";
  }

  if (toolName === "exec" && execCommand && policy.execWhitelist.length > 0) {
    const cmd = execCommand.trim().split(/\s+/)[0];
    if (!policy.execWhitelist.includes(cmd)) {
      return "denied";
    }
  }

  if (policy.allowedTools.size > 0 && !policy.allowedTools.has(toolName)) {
    return "needs_prompt";
  }

  return "approved";
}
