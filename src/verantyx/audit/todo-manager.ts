/**
 * TodoManager — Manages TODO lists via Gemini auditing
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from "fs";
import { join } from "path";
import { GeminiBridge } from "./gemini-bridge.js";

export interface TodoItem {
  id: string;
  content: string;
  priority: "high" | "medium" | "low";
  status: "pending" | "in_progress" | "completed";
  dependencies: string[];
  assignedAgent: string;
}

export interface TodoAuditResult {
  gaps: string[];
  granularityIssues: string[];
  dependencyIssues: string[];
  priorityIssues: string[];
  suggestions: string[];
}

export class TodoManager {
  private bridge: GeminiBridge;
  private todoDir: string;

  constructor(bridge: GeminiBridge, memoryRoot: string) {
    this.bridge = bridge;
    this.todoDir = join(memoryRoot, "todo");
    if (!existsSync(this.todoDir)) {mkdirSync(this.todoDir, { recursive: true });}
  }

  async auditTodos(): Promise<TodoAuditResult> {
    const todos = this.loadTodos();
    if (todos.length === 0) {
      return { gaps: [], granularityIssues: [], dependencyIssues: [], priorityIssues: [], suggestions: ["TODOリストが空です"] };
    }

    const todoText = todos
      .map(
        (t, i) =>
          `${i + 1}. [${t.priority}][${t.status}] ${t.content}${t.dependencies.length ? ` (depends: ${t.dependencies.join(",")})` : ""}${t.assignedAgent ? ` → ${t.assignedAgent}` : ""}`,
      )
      .join("\n");

    const prompt = `以下のTODOリストを監査してください。

${todoText}

チェック項目:
1. 抜け漏れ: 必要なタスクが欠けていないか
2. 粒度: タスクが大きすぎ/小さすぎないか
3. 依存関係: 実行順序は正しいか
4. 優先順位: 優先度は適切か
5. 実現可能性: 各タスクは実現可能か

回答フォーマット:
- 抜け漏れ: [リスト]
- 粒度問題: [リスト]
- 依存関係問題: [リスト]
- 優先度問題: [リスト]
- 提案: [リスト]`;

    const result = await this.bridge.ask(prompt, `TODO監査: ${todos.length}件`, 90_000);
    return this.parseAuditResponse(result.response);
  }

  async prioritizeTodos(tasks: string[]): Promise<string[]> {
    const taskText = tasks.map((t, i) => `${i + 1}. ${t}`).join("\n");

    const prompt = `以下のタスクを優先度順に並び替えてください。最も重要なものを最初に。

${taskText}

番号だけを優先度順にカンマ区切りで返してください（例: 3,1,2,4）`;

    const result = await this.bridge.ask(prompt, "TODO優先度付け", 30_000);

    // Parse order
    const nums = result.response.match(/\d+/g);
    if (!nums) {return tasks;}

    const order = nums.map((n) => parseInt(n, 10) - 1);
    const reordered: string[] = [];
    for (const idx of order) {
      if (idx >= 0 && idx < tasks.length) {reordered.push(tasks[idx]);}
    }
    // Append any tasks not referenced
    for (const t of tasks) {
      if (!reordered.includes(t)) {reordered.push(t);}
    }
    return reordered;
  }

  saveTodos(todos: TodoItem[]): void {
    const filePath = join(this.todoDir, "current.md");
    const lines = [
      "---",
      `name: Current Sprint TODOs`,
      `type: todo`,
      `updated: ${new Date().toISOString()}`,
      `count: ${todos.length}`,
      "---",
      "",
    ];

    for (const t of todos) {
      const check = t.status === "completed" ? "x" : t.status === "in_progress" ? "~" : " ";
      lines.push(
        `- [${check}] **[${t.priority}]** ${t.content}${t.dependencies.length ? ` (deps: ${t.dependencies.join(", ")})` : ""}${t.assignedAgent ? ` → ${t.assignedAgent}` : ""}  <!-- id:${t.id} -->`,
      );
    }

    writeFileSync(filePath, lines.join("\n"), "utf-8");
  }

  loadTodos(): TodoItem[] {
    const filePath = join(this.todoDir, "current.md");
    if (!existsSync(filePath)) {return [];}

    const content = readFileSync(filePath, "utf-8");
    const items: TodoItem[] = [];

    const lineRe =
      /^- \[([x~ ])\] \*\*\[(\w+)\]\*\* (.+?)(?:\s*\(deps:\s*(.+?)\))?(?:\s*→\s*(\S+))?(?:\s*<!--\s*id:(\S+)\s*-->)?$/;

    for (const line of content.split("\n")) {
      const m = line.match(lineRe);
      if (!m) {continue;}
      const [, check, priority, contentText, deps, agent, id] = m;
      items.push({
        id: id ?? `todo_${items.length}`,
        content: contentText.trim(),
        priority: (priority as "high" | "medium" | "low") || "medium",
        status: check === "x" ? "completed" : check === "~" ? "in_progress" : "pending",
        dependencies: deps ? deps.split(",").map((d) => d.trim()) : [],
        assignedAgent: agent ?? "",
      });
    }
    return items;
  }

  // ── Private ──

  private parseAuditResponse(response: string): TodoAuditResult {
    const extract = (label: string): string[] => {
      const re = new RegExp(`(?:${label})[:\\s]*([\\s\\S]*?)(?:\\n(?:粒度|依存|優先|提案|granularity|dependency|priority|suggestion)|$)`, "i");
      const m = response.match(re);
      if (!m) {return [];}
      return m[1]
        .split("\n")
        .map((l) => l.replace(/^[-*•\d.]\s*/, "").trim())
        .filter((l) => l.length > 2 && !/^なし$|^none$/i.test(l));
    };

    return {
      gaps: extract("抜け漏れ|gaps"),
      granularityIssues: extract("粒度問題|粒度|granularity"),
      dependencyIssues: extract("依存関係問題|依存関係|dependency"),
      priorityIssues: extract("優先度問題|優先度|priority"),
      suggestions: extract("提案|suggestion"),
    };
  }
}
