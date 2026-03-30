/**
 * GeminiAgentLoop — Gemini に手足を外付けするエージェントループ
 *
 * ブラウザ上の手足のないGeminiに対して、Verantyxが仲介役となり
 * ファイル操作・コマンド実行・記憶アクセスを提供する。
 *
 * フロー:
 *   1. ユーザーがタスクをGeminiに渡す
 *   2. Geminiが指定書式でツール実行を要求
 *   3. Verantyxが要求をパースして実行
 *   4. 結果をGeminiに返す
 *   5. Geminiが次のアクションを決定
 *   6. 繰り返し（完了まで）
 *
 * ツール要求書式:
 *   [VERANTYX_CMD]
 *   action: read | write | exec | search | memory_read | memory_write | list
 *   target: file_auth_001 | front/active_context | "grep pattern"
 *   params: { max_lines: 100 }
 *   [/VERANTYX_CMD]
 *
 * Pure-Through統合:
 *   - 5ターンでGeminiをリセット（コンテキスト汚染防止）
 *   - リセット時に遺言(CodedWill)を空間記憶に保存
 *   - 新Geminiに遺言を注入して復元
 */

import { GeminiBridge } from "./gemini-bridge.js";
import { execSync } from "child_process";
import { readFileSync, writeFileSync, existsSync, readdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";

// ── Types ──

interface ToolRequest {
  action: "read" | "write" | "exec" | "search" | "memory_read" | "memory_write" | "list" | "gatekeeper";
  target: string;
  params?: Record<string, any>;
}

interface ToolResult {
  success: boolean;
  output: string;
  truncated: boolean;
}

interface AgentLoopOptions {
  memoryRoot: string;
  vfsMappingPath?: string;
  maxTurns: number;           // Pure-Throughリセット閾値
  maxOutputLines: number;     // ツール出力の最大行数
  onToolExec?: (req: ToolRequest, result: ToolResult) => void;
  onTurnComplete?: (turn: number, geminiResponse: string) => void;
  onReset?: (turn: number, will: string) => void;
}

// ── Agent Loop ──

export class GeminiAgentLoop {
  private bridge: GeminiBridge;
  private opts: AgentLoopOptions;
  private turnCount = 0;
  private totalTurns = 0;
  private resetCount = 0;
  private isRunning = false;

  constructor(opts: AgentLoopOptions) {
    this.bridge = new GeminiBridge();
    this.opts = {
      maxTurns: 5,
      maxOutputLines: 100,
      ...opts,
    };
  }

  /**
   * タスクをGeminiに渡してエージェントループを開始
   * Geminiが[DONE]を返すか、maxTurnsに達するまで繰り返す
   */
  async run(task: string): Promise<string> {
    this.isRunning = true;
    this.turnCount = 0;

    // 初期プロンプト: Geminiにツール使用方法を教える
    const systemPrompt = this.buildSystemPrompt(task);

    let lastResponse = "";

    try {
      // 最初の質問を送る
      const initResult = await this.bridge.ask(systemPrompt);
      if (initResult.status !== "success") {
        return `Gemini init error: ${initResult.status}`;
      }

      lastResponse = initResult.response;
      this.turnCount++;
      this.totalTurns++;
      this.opts.onTurnComplete?.(this.totalTurns, lastResponse);

      // メインループ
      while (this.isRunning) {
        // [DONE] チェック
        if (lastResponse.includes("[DONE]") || lastResponse.includes("[完了]")) {
          break;
        }

        // ツール要求をパース
        const toolRequests = this.parseToolRequests(lastResponse);

        if (toolRequests.length === 0) {
          // ツール要求なし → タスク完了とみなす
          break;
        }

        // ツール実行 + 結果収集
        let resultText = "";
        for (const req of toolRequests) {
          const result = this.executeTool(req);
          this.opts.onToolExec?.(req, result);
          resultText += `[VERANTYX_RESULT]\naction: ${req.action}\ntarget: ${req.target}\nstatus: ${result.success ? "success" : "error"}\n${result.truncated ? "(truncated)\n" : ""}output:\n${result.output}\n[/VERANTYX_RESULT]\n\n`;
        }

        // Pure-Throughリセットチェック
        if (this.turnCount >= this.opts.maxTurns) {
          const will = await this.extractWill(lastResponse);
          this.opts.onReset?.(this.totalTurns, will);

          // 遺言を空間記憶に保存
          this.saveWill(will);

          // Geminiをリセット
          await this.bridge.cleanup();
          this.bridge = new GeminiBridge();

          // 新しいGeminiに遺言を注入
          const restorePrompt = this.buildRestorePrompt(task, will);
          const restoreResult = await this.bridge.ask(restorePrompt);
          if (restoreResult.status !== "success") {
            return `Gemini restore error after reset: ${restoreResult.status}`;
          }
          lastResponse = restoreResult.response;
          this.turnCount = 0;
          this.resetCount++;
          this.totalTurns++;
          this.opts.onTurnComplete?.(this.totalTurns, lastResponse);
          continue;
        }

        // 結果をGeminiに返す
        const nextResult = await this.bridge.ask(resultText);
        if (nextResult.status !== "success") {
          if (nextResult.status === "subscription_warning") {
            // 自動リカバリ済みのはず
            lastResponse = nextResult.response;
          } else {
            return `Gemini error: ${nextResult.status}`;
          }
        } else {
          lastResponse = nextResult.response;
        }

        this.turnCount++;
        this.totalTurns++;
        this.opts.onTurnComplete?.(this.totalTurns, lastResponse);
      }
    } finally {
      this.isRunning = false;
    }

    return lastResponse;
  }

  stop(): void {
    this.isRunning = false;
  }

  cleanup(): void {
    this.bridge.cleanup();
  }

  // ── System Prompt ──

  private buildSystemPrompt(task: string): string {
    // 空間記憶からfrontの概要を読む
    const frontSummary = this.getFrontMemorySummary();

    return `あなたはVerantyxエージェントです。以下のタスクを実行してください。

## ツール使用方法
ファイル操作やコマンド実行が必要な場合は、以下の書式で指示してください。
Verantyxシステムが実行して結果を返します。

\`\`\`
[VERANTYX_CMD]
action: read
target: path/to/file
params: { "max_lines": 100 }
[/VERANTYX_CMD]
\`\`\`

### 利用可能なアクション
- **read**: ファイルを読む。target=ファイルパスまたは仮想ID
- **write**: ファイルに書き込む。target=パス, params.content=内容
- **exec**: シェルコマンドを実行。target=コマンド文字列
- **search**: ファイル検索。target=検索パターン, params.path=検索ディレクトリ
- **memory_read**: 空間記憶を読む。target=ゾーン/名前 (例: front/active_context)
- **memory_write**: 空間記憶に書く。target=ゾーン/名前, params.content=内容
- **list**: ディレクトリ内容を一覧。target=ディレクトリパス
- **gatekeeper**: 仮想ファイルシステム操作。target=list|search|report, params.query=検索語

### ルール
1. 一度に複数のツール要求を出せます（順番に実行されます）
2. 結果は [VERANTYX_RESULT] ブロックで返されます
3. タスク完了時は [DONE] と書いてください
4. 各ツール出力は最大${this.opts.maxOutputLines}行に制限されます

## 現在のプロジェクト記憶
${frontSummary}

## タスク
${task}

まず何が必要か分析して、必要なファイルを読むところから始めてください。`;
  }

  private buildRestorePrompt(task: string, will: string): string {
    return `あなたはVerantyxエージェントです。前任のエージェントがタスク途中でリセットされました。

## 前任の遺言
${will}

## 元のタスク
${task}

## ツール使用方法
ファイル操作やコマンド実行が必要な場合は [VERANTYX_CMD] ブロックで指示してください。
タスク完了時は [DONE] と書いてください。

前任の遺言を引き継いで、タスクを続行してください。`;
  }

  // ── Tool Request Parser ──

  private parseToolRequests(text: string): ToolRequest[] {
    const requests: ToolRequest[] = [];
    const regex = /\[VERANTYX_CMD\]([\s\S]*?)\[\/VERANTYX_CMD\]/g;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const block = match[1];
      const actionMatch = block.match(/action:\s*(\w+)/);
      const targetMatch = block.match(/target:\s*(.+?)(?:\n|$)/);
      const paramsMatch = block.match(/params:\s*(\{[\s\S]*?\})/);

      if (actionMatch && targetMatch) {
        let params: Record<string, any> = {};
        if (paramsMatch) {
          try { params = JSON.parse(paramsMatch[1]); } catch {}
        }
        requests.push({
          action: actionMatch[1] as ToolRequest["action"],
          target: targetMatch[1].trim(),
          params,
        });
      }
    }

    // 自然言語からfile_XXXパターンも検出
    const fileIdRegex = /\bfile_\w+_\d+\b/g;
    const fileIds = text.match(fileIdRegex);
    if (fileIds && requests.length === 0) {
      for (const fid of [...new Set(fileIds)]) {
        requests.push({ action: "gatekeeper", target: "report", params: { file_id: fid } });
      }
    }

    return requests;
  }

  // ── Tool Executor ──

  private executeTool(req: ToolRequest): ToolResult {
    try {
      switch (req.action) {
        case "read":
          return this.toolRead(req.target, req.params?.max_lines ?? this.opts.maxOutputLines);

        case "write":
          return this.toolWrite(req.target, req.params?.content ?? "");

        case "exec":
          return this.toolExec(req.target);

        case "search":
          return this.toolSearch(req.target, req.params?.path);

        case "memory_read":
          return this.toolMemoryRead(req.target);

        case "memory_write":
          return this.toolMemoryWrite(req.target, req.params?.content ?? "");

        case "list":
          return this.toolList(req.target);

        case "gatekeeper":
          return this.toolGatekeeper(req.target, req.params);

        default:
          return { success: false, output: `Unknown action: ${req.action}`, truncated: false };
      }
    } catch (e: any) {
      return { success: false, output: `Error: ${e.message}`, truncated: false };
    }
  }

  private toolRead(path: string, maxLines: number): ToolResult {
    if (!existsSync(path)) {
      return { success: false, output: `File not found: ${path}`, truncated: false };
    }
    const content = readFileSync(path, "utf-8");
    const lines = content.split("\n");
    const truncated = lines.length > maxLines;
    const output = lines.slice(0, maxLines).join("\n");
    return { success: true, output, truncated };
  }

  private toolWrite(path: string, content: string): ToolResult {
    writeFileSync(path, content, "utf-8");
    return { success: true, output: `Written ${content.length} chars to ${path}`, truncated: false };
  }

  private toolExec(command: string): ToolResult {
    // セキュリティ: 危険なコマンドをブロック
    const blocked = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:"];
    for (const b of blocked) {
      if (command.includes(b)) {
        return { success: false, output: `Blocked dangerous command: ${command}`, truncated: false };
      }
    }

    try {
      const output = execSync(command, {
        timeout: 30_000,
        encoding: "utf-8",
        maxBuffer: 1024 * 1024,
      });
      const lines = output.split("\n");
      const truncated = lines.length > this.opts.maxOutputLines;
      return {
        success: true,
        output: lines.slice(0, this.opts.maxOutputLines).join("\n"),
        truncated,
      };
    } catch (e: any) {
      return { success: false, output: e.stderr || e.message, truncated: false };
    }
  }

  private toolSearch(pattern: string, searchPath?: string): ToolResult {
    const path = searchPath || ".";
    try {
      const output = execSync(`grep -rn "${pattern}" ${path} 2>/dev/null | head -${this.opts.maxOutputLines}`, {
        timeout: 15_000,
        encoding: "utf-8",
        maxBuffer: 512 * 1024,
      });
      return { success: true, output, truncated: output.split("\n").length >= this.opts.maxOutputLines };
    } catch {
      return { success: true, output: "No matches found", truncated: false };
    }
  }

  private toolMemoryRead(target: string): ToolResult {
    // target = "front/active_context" or "near/auth_details"
    const parts = target.split("/");
    const zone = parts[0];
    const name = parts.slice(1).join("/");
    const filePath = join(this.opts.memoryRoot, zone, `${name}.md`);

    if (!existsSync(filePath)) {
      return { success: false, output: `Memory not found: ${target}`, truncated: false };
    }
    const content = readFileSync(filePath, "utf-8");
    return { success: true, output: content, truncated: false };
  }

  private toolMemoryWrite(target: string, content: string): ToolResult {
    const parts = target.split("/");
    const zone = parts[0];
    const name = parts.slice(1).join("/");
    const filePath = join(this.opts.memoryRoot, zone, `${name}.md`);

    writeFileSync(filePath, content, "utf-8");
    return { success: true, output: `Memory written: ${target}`, truncated: false };
  }

  private toolList(dirPath: string): ToolResult {
    if (!existsSync(dirPath)) {
      return { success: false, output: `Directory not found: ${dirPath}`, truncated: false };
    }
    try {
      const entries = readdirSync(dirPath);
      return { success: true, output: entries.join("\n"), truncated: entries.length > this.opts.maxOutputLines };
    } catch (e: any) {
      return { success: false, output: e.message, truncated: false };
    }
  }

  private toolGatekeeper(subAction: string, params?: Record<string, any>): ToolResult {
    const mappingPath = this.opts.vfsMappingPath;
    if (!mappingPath || !existsSync(mappingPath)) {
      return { success: false, output: "VFS mapping not configured", truncated: false };
    }
    try {
      const mapping = JSON.parse(readFileSync(mappingPath, "utf-8"));

      switch (subAction) {
        case "list":
          const entries = Object.entries(mapping)
            .map(([id, info]: [string, any]) => `${id}: ${info.name || info.path}`)
            .join("\n");
          return { success: true, output: entries, truncated: false };

        case "search":
          const query = (params?.query || "").toLowerCase();
          const matches = Object.entries(mapping)
            .filter(([id, info]: [string, any]) =>
              id.includes(query) ||
              (info.name || "").toLowerCase().includes(query) ||
              (info.category || "").toLowerCase().includes(query)
            )
            .map(([id, info]: [string, any]) => `${id}: ${info.name || info.path}`)
            .join("\n");
          return { success: true, output: matches || "No matches", truncated: false };

        case "report":
          const fileId = params?.file_id;
          if (!fileId || !mapping[fileId]) {
            return { success: false, output: `File not found: ${fileId}`, truncated: false };
          }
          const fileInfo = mapping[fileId];
          const realPath = fileInfo.path;
          if (existsSync(realPath)) {
            const content = readFileSync(realPath, "utf-8");
            const lines = content.split("\n");
            return {
              success: true,
              output: `File: ${fileId}\nName: ${fileInfo.name}\nLines: ${lines.length}\nCategory: ${fileInfo.category || "unknown"}\n\n${lines.slice(0, this.opts.maxOutputLines).join("\n")}`,
              truncated: lines.length > this.opts.maxOutputLines,
            };
          }
          return { success: false, output: `Real file not found for ${fileId}`, truncated: false };

        default:
          return { success: false, output: `Unknown gatekeeper action: ${subAction}`, truncated: false };
      }
    } catch (e: any) {
      return { success: false, output: `Gatekeeper error: ${e.message}`, truncated: false };
    }
  }

  // ── Pure-Through ──

  private async extractWill(lastResponse: string): Promise<string> {
    // Geminiに遺言を書かせる
    const willPrompt = `タスクの途中ですが、あなたはリセットされます。
次のエージェントのために遺言を書いてください：
1. 現在の状況（何を達成し、何が残っているか）
2. 重要な発見や判断
3. 次のステップの提案
簡潔に200文字以内で。`;

    const result = await this.bridge.ask(willPrompt, undefined, 30_000);
    return result.status === "success" ? result.response : `(遺言取得失敗) 最終応答: ${lastResponse.slice(0, 200)}`;
  }

  private saveWill(will: string): void {
    const willPath = join(this.opts.memoryRoot, "front", `will_${this.resetCount}.md`);
    const content = `---
name: Agent Will #${this.resetCount}
type: will
timestamp: ${new Date().toISOString()}
turn: ${this.totalTurns}
---

${will}
`;
    writeFileSync(willPath, content, "utf-8");
  }

  // ── Memory Access ──

  private getFrontMemorySummary(): string {
    const frontDir = join(this.opts.memoryRoot, "front");
    if (!existsSync(frontDir)) {return "(空間記憶なし)";}

    try {
      const files = readdirSync(frontDir).filter(f => f.endsWith(".md"));
      const summaries: string[] = [];

      for (const file of files.slice(0, 5)) {
        const content = readFileSync(join(frontDir, file), "utf-8");
        const firstLines = content.split("\n").slice(0, 3).join(" ").trim();
        summaries.push(`- ${file}: ${firstLines.slice(0, 80)}`);
      }

      return summaries.join("\n") || "(記憶ファイルなし)";
    } catch {
      return "(記憶読み込みエラー)";
    }
  }

  // ── Stats ──

  getStats(): { totalTurns: number; resets: number; currentTurn: number } {
    return {
      totalTurns: this.totalTurns,
      resets: this.resetCount,
      currentTurn: this.turnCount,
    };
  }
}
