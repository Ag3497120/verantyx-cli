/**
 * Verantyx Agent Configuration
 *
 * Defines model assignments for Commander/Worker/Scout roles.
 * Both Commander and Worker default to Opus for maximum reasoning quality.
 */

import { readFileSync, existsSync } from "fs";
import { join } from "path";

export interface VerantyxAgentConfig {
  agents: {
    commanderModel: string;
    workerModel: string;
    scoutModel: string;
  };
  providers: {
    anthropic: {
      apiKey?: string;
      oauthToken?: string;
    };
  };
}

const DEFAULT_CONFIG: VerantyxAgentConfig = {
  agents: {
    commanderModel: "claude-opus-4-6",
    workerModel: "claude-sonnet-4-6",
    scoutModel: "claude-sonnet-4-6",
  },
  providers: {
    anthropic: {},
  },
};

/**
 * Load Verantyx config from:
 * 1. VERANTYX_CONFIG env var (JSON file path)
 * 2. ~/.verantyx/config.json
 * 3. OpenClaw's ~/.openclaw/openclaw.json (extract API key)
 * 4. Fallback to defaults
 */
export function loadConfig(): VerantyxAgentConfig {
  const config = { ...DEFAULT_CONFIG };

  // Try VERANTYX_CONFIG env
  const envPath = process.env.VERANTYX_CONFIG;
  if (envPath && existsSync(envPath)) {
    try {
      const raw = JSON.parse(readFileSync(envPath, "utf-8"));
      if (raw.agents) {
        config.agents = { ...config.agents, ...raw.agents };
      }
      if (raw.providers) {
        config.providers = { ...config.providers, ...raw.providers };
      }
    } catch { /* ignore parse errors */ }
  }

  // Try ~/.verantyx/config.json
  const homeConfig = join(
    process.env.HOME || "",
    ".verantyx",
    "config.json"
  );
  if (existsSync(homeConfig)) {
    try {
      const raw = JSON.parse(readFileSync(homeConfig, "utf-8"));
      if (raw.agents) {
        config.agents = { ...config.agents, ...raw.agents };
      }
      if (raw.providers?.anthropic) {
        config.providers.anthropic = {
          ...config.providers.anthropic,
          ...raw.providers.anthropic,
        };
      }
    } catch { /* ignore */ }
  }

  // Try OpenClaw's config for API key
  const openclawConfig = join(
    process.env.HOME || "",
    ".openclaw",
    "openclaw.json"
  );
  if (existsSync(openclawConfig) && !config.providers.anthropic.apiKey) {
    try {
      const raw = JSON.parse(readFileSync(openclawConfig, "utf-8"));
      // OpenClaw stores API key in various locations
      if (raw.anthropic?.api_key) {
        config.providers.anthropic.apiKey = raw.anthropic.api_key;
      }
      if (raw.provider === "anthropic" && raw.apiKey) {
        config.providers.anthropic.apiKey = raw.apiKey;
      }
    } catch { /* ignore */ }
  }

  // Environment variable override
  if (process.env.ANTHROPIC_API_KEY) {
    config.providers.anthropic.apiKey = process.env.ANTHROPIC_API_KEY;
  }

  // Model overrides from env
  if (process.env.VERANTYX_COMMANDER_MODEL) {
    config.agents.commanderModel = process.env.VERANTYX_COMMANDER_MODEL;
  }
  if (process.env.VERANTYX_WORKER_MODEL) {
    config.agents.workerModel = process.env.VERANTYX_WORKER_MODEL;
  }
  if (process.env.VERANTYX_SCOUT_MODEL) {
    config.agents.scoutModel = process.env.VERANTYX_SCOUT_MODEL;
  }

  return config;
}

/**
 * Resolve the API key from provider config.
 * Supports both direct API key and OAuth token.
 */
export function resolveProviderApiKey(
  provider: VerantyxAgentConfig["providers"]["anthropic"]
): string {
  return provider.apiKey || provider.oauthToken || process.env.ANTHROPIC_API_KEY || "";
}
