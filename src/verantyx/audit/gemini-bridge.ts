/**
 * GeminiBridge — Session management over SafariController
 * Ported from verantyx_cli/bridge/gemini_bridge.py
 */

import { writeFileSync, readFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import { SafariController, AskResult } from "./safari-controller.js";

interface HistoryEntry {
  prompt: string;
  response: string;
  timestamp: number;
}

interface SessionState {
  timestamp: number;
  context: string;
  history: HistoryEntry[];
}

export class GeminiBridge {
  private safari: SafariController;
  private sessionHistory: HistoryEntry[] = [];
  private isInitialized = false;
  private sessionDir: string;
  private sessionFile: string;

  constructor() {
    this.safari = new SafariController();
    this.sessionDir = join(homedir(), ".verantyx", "gemini_sessions");
    this.sessionFile = join(this.sessionDir, "current_session.json");
    if (!existsSync(this.sessionDir)) {mkdirSync(this.sessionDir, { recursive: true });}
  }

  async initialize(): Promise<void> {
    await this.safari.openPrivateWindow("https://gemini.google.com");
    await sleep(5000); // page load

    const initPrompt =
      "あなたはVerantyxエージェントです。簡潔に回答してください。理解したら「OK」とだけ返答してください。";
    const result = await this.safari.askGemini(initPrompt, 30_000);

    if (result.status !== "success") {
      throw new Error(`Gemini init failed: ${result.status} — ${result.response}`);
    }
    this.isInitialized = true;
  }

  async ask(
    prompt: string,
    context?: string,
    timeoutMs = 60_000,
  ): Promise<AskResult> {
    if (!this.isInitialized) {await this.initialize();}

    let result = await this.safari.askGemini(prompt, timeoutMs);

    this.sessionHistory.push({
      prompt,
      response: result.response,
      timestamp: Date.now(),
    });

    // Auto-recover from subscription warning
    if (result.status === "subscription_warning") {
      const ctx = context ?? `質問中: ${prompt}`;
      result = await this.handleSubscriptionWarning(ctx, prompt, timeoutMs);
    }

    return result;
  }

  private async handleSubscriptionWarning(
    context: string,
    lastPrompt: string,
    timeoutMs: number,
  ): Promise<AskResult> {
    this.saveSessionState(context);

    await this.safari.switchToNewGeminiTab();
    await sleep(3000);

    // Restore context
    const restorePrompt = `前回の会話が中断されました。以下のコンテキストで作業を続けてください：\n${context}\n最後の質問：${lastPrompt}`;
    const restoreResult = await this.safari.askGemini(restorePrompt, 30_000);

    if (restoreResult.status !== "success") {
      return restoreResult;
    }

    // Retry original prompt
    await sleep(2000);
    return this.safari.askGemini(lastPrompt, timeoutMs);
  }

  saveSessionState(context: string): void {
    const state: SessionState = {
      timestamp: Date.now(),
      context,
      history: this.sessionHistory.slice(-10),
    };
    writeFileSync(this.sessionFile, JSON.stringify(state, null, 2), "utf-8");
  }

  restoreSessionState(): SessionState | null {
    if (!existsSync(this.sessionFile)) {return null;}
    try {
      const data = JSON.parse(readFileSync(this.sessionFile, "utf-8")) as SessionState;
      this.sessionHistory = data.history;
      return data;
    } catch {
      return null;
    }
  }

  cleanup(): void {
    try { this.safari.closeCurrentTab(); } catch {}
    this.isInitialized = false;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
