# Gemini Private Audit System — Implementation Specification

## Overview

This spec defines the communication protocol between verantyx-cli and Gemini running in Safari Private Browsing mode. Gemini serves as an independent auditor that validates memory accuracy, approves agent operations, and manages TODO lists — all from a clean, non-personalized context.

## Existing Code to Reuse

The following files from the original verantyx-cli contain working implementations. Copy and adapt them into verantyx-cli-fork:

| Source File | Target Location | Status |
|---|---|---|
| `verantyx_cli/bridge/safari_controller.py` | `src/verantyx/audit/safari-controller.ts` | Rewrite in TypeScript |
| `verantyx_cli/bridge/gemini_bridge.py` | `src/verantyx/audit/gemini-bridge.ts` | Rewrite in TypeScript |
| `verantyx_cli/audit/private_auditor.py` | `src/verantyx/audit/private-auditor.ts` | Rewrite in TypeScript |
| `verantyx_cli/agent/gemini_agent_interface.py` | `src/verantyx/audit/agent-interface.ts` | Rewrite + implement _send_to_gemini |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  verantyx-cli-fork (TypeScript/Node.js)                  │
│                                                          │
│  GeminiAuditService                                      │
│  ├── SafariController  (AppleScript execution)           │
│  ├── GeminiBridge      (session management)              │
│  ├── MemoryAuditor     (hallucination detection)         │
│  ├── OperationAuditor  (agent action validation)         │
│  └── TodoManager       (task management via Gemini)      │
└──────────────────────┬───────────────────────────────────┘
                       │ AppleScript + JavaScript
                       ↓
┌──────────────────────────────────────────────────────────┐
│  Safari Private Browsing                                 │
│  URL: https://gemini.google.com                          │
│  - New private window per audit (Cmd+Shift+N)            │
│  - No login, no personalization                          │
│  - Tab closed after each audit                           │
│  - Subscription warning auto-recovery                    │
└──────────────────────────────────────────────────────────┘
```

## Component Specifications

### 1. SafariController (safari-controller.ts)

Lowest-level Safari automation. All AppleScript execution lives here.

```typescript
class SafariController {
  // Execute raw AppleScript
  runAppleScript(script: string): Promise<string>;

  // Execute JavaScript in Safari's front document
  runJavaScript(code: string): Promise<string>;

  // Open a genuine private browsing window (Cmd+Shift+N)
  openPrivateWindow(url?: string): Promise<void>;

  // Close the frontmost tab/window
  closeCurrentTab(): Promise<void>;

  // Open new private tab (close current + open new)
  switchToNewGeminiTab(): Promise<void>;

  // Type text into Gemini's input field
  // MUST use base64 encoding to avoid AppleScript escaping issues
  // MUST use Quill API or native setter to bypass React
  typeText(text: string): Promise<void>;

  // Click Gemini's send button
  sendMessage(): Promise<void>;

  // Wait for Gemini response with polling
  // Poll every 2s, consider stable after 2 identical checks
  // Split on "Gemini の回答" marker to detect new responses
  waitForResponse(timeoutMs: number, prevResponseCount: number): Promise<string>;

  // Count current responses on page
  getResponseCount(): Promise<number>;

  // Check for subscription/upgrade warning
  checkSubscriptionWarning(): Promise<boolean>;

  // High-level: type + send + wait
  askGemini(prompt: string, timeoutMs?: number): Promise<AskResult>;
}

interface AskResult {
  status: "success" | "subscription_warning" | "timeout" | "error";
  response: string;
  durationMs: number;
}
```

**Critical Implementation Details:**

1. **Private window opening** — MUST use System Events keystroke, not `make new document`:
```applescript
tell application "Safari"
    activate
end tell
tell application "System Events"
    keystroke "n" using {command down, shift down}
end tell
delay 1
tell application "Safari"
    set URL of front document to "https://gemini.google.com"
end tell
delay 3
```

2. **Text input** — MUST base64 encode, then decode in JavaScript:
```javascript
const text = atob("<base64_encoded_prompt>");
const editor = document.querySelector('div.ql-editor[contenteditable=true]');
if (editor) {
    const quill = editor.closest('.ql-container').__quill;
    quill.setText(text);
    quill.root.dispatchEvent(new Event('text-change'));
} else {
    const textarea = document.querySelector('textarea');
    const nativeSetter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype, 'value'
    ).set;
    nativeSetter.call(textarea, text);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
}
```

3. **Send button** — Try Japanese label first, then English:
```javascript
var btn = document.querySelector('button[aria-label*="プロンプトを送信"]');
if (!btn) btn = document.querySelector('button[aria-label*="Send"]');
btn.click();
```

4. **Response extraction** — Split on `"Gemini の回答"` marker, take last segment, strip footer strings:
```
Strip: "Gemini は AI であり", "ツール", "あなたのプロンプト", "回答案を表示"
```

5. **Subscription warning detection** — Check page text for:
```
Exact: "upgrade to gemini advanced", "gemini advancedにアップグレード",
       "上限に達しました", "利用制限に達しました"
Loose: 3+ of ["subscription","upgrade","premium","limit"] AND
       ("gemini advanced" OR "pricing")
```

6. **Recovery on warning** — Close tab, open new private window, restore context.

---

### 2. GeminiBridge (gemini-bridge.ts)

Session management layer over SafariController.

```typescript
class GeminiBridge {
  private safari: SafariController;
  private sessionHistory: Array<{ prompt: string; response: string; timestamp: number }>;
  private isInitialized: boolean;

  constructor();

  // Open private window + send init prompt
  initialize(): Promise<void>;

  // Ask with auto-retry on subscription warning
  ask(prompt: string, context?: string, timeoutMs?: number): Promise<AskResult>;

  // Handle subscription warning: close tab, open new, restore context
  handleSubscriptionWarning(context: string): Promise<AskResult>;

  // Save/restore session to JSON file
  saveSessionState(context: string): void;
  restoreSessionState(): SessionState | null;

  // Close everything
  cleanup(): void;
}

interface SessionState {
  timestamp: number;
  context: string;
  history: Array<{ prompt: string; response: string; timestamp: number }>;
}
```

**Init prompt** (sends to Gemini on first contact):
```
あなたはVerantyxエージェントです。簡潔に回答してください。理解したら「OK」とだけ返答してください。
```

**Session restore prompt** (sent after subscription warning recovery):
```
前回の会話が中断されました。以下のコンテキストで作業を続けてください：
{context}
最後の質問：{last_prompt}
```

---

### 3. MemoryAuditor (memory-auditor.ts)

Validates Cross spatial memory content for hallucinations.

```typescript
class MemoryAuditor {
  private bridge: GeminiBridge;
  private memory: MemoryEngine;

  constructor(memory: MemoryEngine);

  // Audit a single memory file
  auditMemory(zone: string, name: string): Promise<AuditResult>;

  // Audit all memories in a zone
  auditZone(zone: string): Promise<AuditResult[]>;

  // Move audited memory to verified/ zone
  verifyAndMove(zone: string, name: string): Promise<boolean>;

  // Periodic audit (called by freshness manager)
  runPeriodicAudit(): Promise<AuditSummary>;
}

interface AuditResult {
  memoryName: string;
  zone: string;
  verdict: "VERIFIED" | "HALLUCINATION" | "UNCERTAIN";
  confidence: number;     // 0.0 - 1.0
  contradictions: string[];
  supportingEvidence: string[];
  rawResponse: string;
  timestamp: string;
}

interface AuditSummary {
  total: number;
  verified: number;
  hallucinations: number;
  uncertain: number;
  details: AuditResult[];
}
```

**Audit prompt template:**
```
以下の技術文書の正確性を検証してください。

## 検証対象
{memory_content}

## 回答フォーマット
1. 判定: VERIFIED / HALLUCINATION / UNCERTAIN
2. 矛盾点: (ある場合リストアップ)
3. 根拠: (判定の理由)
4. 信頼度: 0.0〜1.0

事実に基づいて客観的に回答してください。
```

**Response parsing:**
- `"VERIFIED"` or `"正確"` or `"問題なし"` → VERIFIED
- `"HALLUCINATION"` or `"誤り"` or `"不正確"` → HALLUCINATION
- Otherwise → UNCERTAIN
- Confidence: extract number after `"信頼度"` or `"confidence"`, default 0.5

**After audit:**
- VERIFIED → copy to `verified/` zone with audit metadata in frontmatter
- HALLUCINATION → keep in original zone, add `[STALE]` marker, write audit log to `audit/`
- UNCERTAIN → keep as-is, write audit log

---

### 4. OperationAuditor (operation-auditor.ts)

Validates agent operation requests before execution.

```typescript
class OperationAuditor {
  private bridge: GeminiBridge;

  constructor();

  // Ask Gemini if an operation is appropriate
  validateOperation(request: OperationRequest): Promise<OperationDecision>;
}

interface OperationRequest {
  action: string;           // "read file_auth_001" or "edit file_game_eat_001"
  agent: string;            // "worker/sonnet" or "scout/haiku"
  context: string;          // Why this operation is needed
  availableAgents: string[]; // List of available agent types
  manual: string;           // Agent operation manual excerpt
}

interface OperationDecision {
  approved: boolean;
  selectedAgent: string;    // Which agent to use
  parameters: Record<string, any>;
  reasoning: string;
  confidence: number;
  rawResponse: string;
}
```

**Validation prompt template:**
```
エージェント操作の適切性を判断してください。

## リクエスト
操作: {action}
エージェント: {agent}
理由: {context}

## 利用可能なエージェント
{availableAgents}

## 操作マニュアル
{manual}

## 回答フォーマット (JSON)
```json
{
  "approved": true/false,
  "selected_agent": "worker/sonnet",
  "parameters": {},
  "reasoning": "理由",
  "confidence": 0.0-1.0
}
```
```

**Response parsing:**
- Extract JSON from ```json ... ``` block
- Fallback: regex for "approved"/"rejected" keywords
- Default confidence: 0.5

---

### 5. TodoManager (todo-manager.ts)

Manages TODO lists via Gemini auditing.

```typescript
class TodoManager {
  private bridge: GeminiBridge;
  private memory: MemoryEngine;

  constructor(memory: MemoryEngine);

  // Ask Gemini to audit current TODO list
  auditTodos(): Promise<TodoAuditResult>;

  // Ask Gemini to prioritize tasks
  prioritizeTodos(tasks: string[]): Promise<string[]>;

  // Save TODO state to memory todo/ zone
  saveTodos(todos: TodoItem[]): void;

  // Load TODOs from memory
  loadTodos(): TodoItem[];
}

interface TodoItem {
  id: string;
  content: string;
  priority: "high" | "medium" | "low";
  status: "pending" | "in_progress" | "completed";
  dependencies: string[];
  assignedAgent: string;
}

interface TodoAuditResult {
  gaps: string[];           // Missing tasks
  granularityIssues: string[]; // Tasks too big/small
  dependencyIssues: string[];  // Wrong ordering
  priorityIssues: string[];    // Wrong priorities
  suggestions: string[];
}
```

**Audit prompt:**
```
以下のTODOリストを監査してください。

{todo_list}

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
- 提案: [リスト]
```

---

### 6. GeminiAuditService (audit-service.ts)

Top-level service that combines all audit components.

```typescript
class GeminiAuditService {
  private memoryAuditor: MemoryAuditor;
  private operationAuditor: OperationAuditor;
  private todoManager: TodoManager;
  private bridge: GeminiBridge;

  constructor(memory: MemoryEngine);

  // Initialize Gemini connection
  initialize(): Promise<void>;

  // Audit a memory before it enters verified/ zone
  auditMemory(zone: string, name: string): Promise<AuditResult>;

  // Validate an operation before execution
  validateOperation(request: OperationRequest): Promise<OperationDecision>;

  // Audit TODO list
  auditTodos(): Promise<TodoAuditResult>;

  // Full audit cycle (all memories + TODO)
  runFullAudit(): Promise<FullAuditReport>;

  // Cleanup
  shutdown(): void;
}
```

---

## Cross Spatial Memory Extension

### New Zones

```
memory/
├── front/      (existing)
├── near/       (existing)
├── mid/        (existing)
├── deep/       (existing)
├── verified/   (NEW — Gemini-audited memories only)
│   └── *.md    — frontmatter includes audit metadata
├── audit/      (NEW — audit logs)
│   └── *.md    — one per audit run
└── todo/       (NEW — Gemini-managed TODO)
    └── *.md    — current sprint + backlog
```

### Verified Memory Frontmatter

```yaml
---
name: Auth System Structure
description: VerantyxAuth unified authentication architecture
type: reference
verified: true
audit_date: 2026-03-22T20:00:00Z
audit_verdict: VERIFIED
audit_confidence: 0.85
audit_source: gemini-private
original_zone: mid
---
```

### Audit Log Format

```yaml
---
name: Audit Log 2026-03-22 001
type: audit
timestamp: 2026-03-22T20:00:00Z
target: mid/moutheat_structure
verdict: VERIFIED
confidence: 0.85
---

## Audit Details
- Target: mid/moutheat_structure.md
- Verdict: VERIFIED
- Contradictions: none
- Supporting evidence: File structure matches typical iOS project patterns
- Raw response: (truncated Gemini response)
```

---

## CLI Commands to Add

```bash
# Memory audit
verantyx audit memory [zone] [name]   # Audit specific memory
verantyx audit all                     # Audit all unverified memories
verantyx audit status                  # Show audit status

# Operation validation
verantyx audit operation <action>      # Validate an operation

# TODO management
verantyx todo list                     # Show TODOs
verantyx todo audit                    # Ask Gemini to audit TODOs
verantyx todo prioritize               # Ask Gemini to reprioritize
```

---

## Error Handling

| Error | Recovery |
|---|---|
| Safari not running | Auto-launch Safari |
| Subscription warning | Close tab → new private window → restore context |
| Response timeout | Retry once with longer timeout (90s → 180s) |
| Empty response | Retry once, then return UNCERTAIN |
| AppleScript failure | Fall back to `make new document` (non-private) |
| Gemini UI change | Log error, return raw page text for manual review |

---

## Integration with Orchestrator

In `orchestrator.ts`, before executing any worker task:

```typescript
// Before tool execution
const decision = await auditService.validateOperation({
  action: "read file_auth_001",
  agent: "worker/sonnet",
  context: "User requested auth system analysis",
  availableAgents: ["worker/sonnet", "scout/haiku"],
  manual: AGENT_OPERATION_MANUAL,
});

if (!decision.approved) {
  // Log rejection, notify commander
  return `Operation rejected: ${decision.reasoning}`;
}

// Execute with approved agent
const result = await this.workerTask(task);

// After execution, audit the result before writing to memory
const memoryContent = extractMemoryFromResult(result);
const audit = await auditService.auditMemory("front", memoryName);
if (audit.verdict === "VERIFIED") {
  memory.move(memoryName, "verified");
}
```

---

## Implementation Order

1. `safari-controller.ts` — Port from Python, test AppleScript commands
2. `gemini-bridge.ts` — Port session management, test ask/recovery flow
3. `memory-auditor.ts` — Implement audit prompt + parsing
4. `operation-auditor.ts` — Implement validation prompt + parsing
5. `todo-manager.ts` — Implement TODO audit + prioritization
6. `audit-service.ts` — Combine all components
7. CLI commands — Register in command-registry.ts
8. Orchestrator integration — Wire audit into tool execution flow
