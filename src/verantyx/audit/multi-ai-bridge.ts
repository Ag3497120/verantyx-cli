/**
 * MultiAIBridge — 複数AIをプライベートブラウザでサブエージェントとして管理
 *
 * Verantyxの管理下で、Gemini/ChatGPT/その他のAIを
 * プライベートブラウザ経由でサブエージェントとして呼び出す。
 *
 * 各AIは独立したプライベートウィンドウで動作し、
 * 相互のコンテキスト汚染がない。
 *
 * 使い分け:
 *   Gemini — 監査・検証（クリーンな判定）
 *   ChatGPT — コード生成・実装（実装力が高い）
 *   両方 — クロスバリデーション（2つの独立した意見を比較）
 */

import { SafariController, AskResult } from "./safari-controller.js";

// ── Types ──

type AIProvider = "gemini" | "chatgpt";

interface AISession {
  provider: AIProvider;
  url: string;
  isInitialized: boolean;
  turnCount: number;
  maxTurns: number;
}

interface SubAgentTask {
  provider: AIProvider;
  prompt: string;
  context?: string;
  timeout?: number;
}

interface SubAgentResult {
  provider: AIProvider;
  status: AskResult["status"];
  response: string;
  durationMs: number;
  turnCount: number;
}

// ── Provider Configs ──

const PROVIDER_CONFIG: Record<AIProvider, {
  url: string;
  initPrompt: string;
  inputSelector: string;
  sendSelector: string;
  responseMarker: string;
  footerStrip: string[];
}> = {
  gemini: {
    url: "https://gemini.google.com",
    initPrompt: "あなたはVerantyxサブエージェントです。簡潔にコードや分析を返してください。理解したら「OK」とだけ返答してください。",
    inputSelector: "div.ql-editor[contenteditable=true]",
    sendSelector: 'button[aria-label*="プロンプトを送信"], button[aria-label*="Send"]',
    responseMarker: "Gemini の回答",
    footerStrip: ["Gemini は AI であり", "ツール", "あなたのプロンプト", "回答案を表示"],
  },
  chatgpt: {
    url: "https://chatgpt.com",
    initPrompt: "You are a Verantyx sub-agent. Return concise code and analysis. Reply 'OK' to confirm.",
    inputSelector: "#prompt-textarea, textarea[data-id], div[contenteditable=true]",
    sendSelector: 'button[data-testid="send-button"], button[aria-label="Send prompt"]',
    responseMarker: "ChatGPT",
    footerStrip: ["ChatGPT can make mistakes", "ChatGPTは間違えることがあります"],
  },
};

// ── Multi AI Bridge ──

export class MultiAIBridge {
  private safari: SafariController;
  private sessions: Map<AIProvider, AISession> = new Map();

  constructor() {
    this.safari = new SafariController();
  }

  /**
   * AIプロバイダーを初期化（プライベートウィンドウで開く）
   */
  async initialize(provider: AIProvider): Promise<void> {
    const config = PROVIDER_CONFIG[provider];

    // プライベートウィンドウで開く
    await this.safari.openPrivateWindow(config.url);
    await sleep(5000); // ページロード待ち

    // 初期化プロンプト送信
    const result = await this.askProvider(provider, config.initPrompt);
    if (result.status !== "success") {
      throw new Error(`${provider} init failed: ${result.status}`);
    }

    this.sessions.set(provider, {
      provider,
      url: config.url,
      isInitialized: true,
      turnCount: 0,
      maxTurns: 5, // Pure-Through準拠
    });
  }

  /**
   * 特定のAIプロバイダーに質問
   */
  async ask(provider: AIProvider, prompt: string, timeout = 60_000): Promise<SubAgentResult> {
    const session = this.sessions.get(provider);
    if (!session?.isInitialized) {
      await this.initialize(provider);
    }

    const t0 = Date.now();
    const result = await this.askProvider(provider, prompt, timeout);

    const s = this.sessions.get(provider)!;
    s.turnCount++;

    // Pure-Throughリセットチェック
    if (s.turnCount >= s.maxTurns) {
      await this.resetProvider(provider);
    }

    return {
      provider,
      status: result.status,
      response: result.response,
      durationMs: Date.now() - t0,
      turnCount: s.turnCount,
    };
  }

  /**
   * サブエージェントタスクを実行（Verantyx管理下）
   */
  async executeSubAgent(task: SubAgentTask): Promise<SubAgentResult> {
    let prompt = task.prompt;
    if (task.context) {
      prompt = `コンテキスト:\n${task.context}\n\nタスク:\n${task.prompt}`;
    }
    return this.ask(task.provider, prompt, task.timeout);
  }

  /**
   * 複数AIでクロスバリデーション
   * 同じ質問を両方に投げて、結果を比較
   */
  async crossValidate(prompt: string): Promise<{
    gemini: SubAgentResult;
    chatgpt: SubAgentResult;
    agreement: boolean;
    summary: string;
  }> {
    // 順番に実行（並列はSafariの制約で不可）
    const geminiResult = await this.ask("gemini", prompt);
    const chatgptResult = await this.ask("chatgpt", prompt);

    // 簡易的な一致判定
    const g = geminiResult.response.toLowerCase();
    const c = chatgptResult.response.toLowerCase();

    // 両方にyes/noまたはtrue/falseが含まれる場合の一致チェック
    const gYes = g.includes("yes") || g.includes("true") || g.includes("正確") || g.includes("verified");
    const cYes = c.includes("yes") || c.includes("true") || c.includes("correct") || c.includes("verified");
    const gNo = g.includes("no") || g.includes("false") || g.includes("誤り") || g.includes("hallucination");
    const cNo = c.includes("no") || c.includes("false") || c.includes("incorrect") || c.includes("hallucination");

    const agreement = (gYes && cYes) || (gNo && cNo);
    const summary = agreement
      ? `Both agree: ${gYes ? "YES/VERIFIED" : "NO/REJECTED"}`
      : `Disagreement: Gemini=${gYes ? "YES" : gNo ? "NO" : "UNCLEAR"}, ChatGPT=${cYes ? "YES" : cNo ? "NO" : "UNCLEAR"}`;

    return { gemini: geminiResult, chatgpt: chatgptResult, agreement, summary };
  }

  /**
   * コード生成タスクをChatGPTに委譲
   */
  async generateCode(task: string, language: string, context?: string): Promise<SubAgentResult> {
    const prompt = `Generate ${language} code for the following task. Return ONLY the code, no explanation.

Task: ${task}
${context ? `\nContext:\n${context}` : ""}`;

    return this.executeSubAgent({
      provider: "chatgpt",
      prompt,
      timeout: 90_000,
    });
  }

  /**
   * Geminiで監査（コードレビュー等）
   */
  async auditCode(code: string, criteria: string): Promise<SubAgentResult> {
    const prompt = `Review the following code for: ${criteria}

\`\`\`
${code}
\`\`\`

Reply with:
1. Verdict: PASS or FAIL
2. Issues (if any)
3. Suggestions`;

    return this.executeSubAgent({
      provider: "gemini",
      prompt,
      timeout: 60_000,
    });
  }

  // ── Internal ──

  private async askProvider(provider: AIProvider, prompt: string, timeout = 60_000): Promise<AskResult> {
    const config = PROVIDER_CONFIG[provider];

    // テキスト入力（base64エンコード）
    const b64 = Buffer.from(prompt, "utf-8").toString("base64");
    const inputJs = `(function(){
  var encoded='${b64}';
  var decoded=decodeURIComponent(escape(atob(encoded)));
  var selectors='${config.inputSelector}'.split(', ');
  var el=null;
  for(var s of selectors){el=document.querySelector(s);if(el)break;}
  if(!el) return 'ERROR: input not found';
  el.focus(); el.click();
  if(el.tagName==='TEXTAREA'||el.tagName==='INPUT'){
    var ns=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
    if(ns){ns.call(el,decoded);}else{el.value=decoded;}
    el.dispatchEvent(new Event('input',{bubbles:true}));
  }else if(el.classList&&el.classList.contains('ql-editor')){
    var c=el.closest('.ql-container');
    var q=c&&c.__quill;
    if(q){q.setText(decoded);}else{el.innerText=decoded;el.dispatchEvent(new Event('input',{bubbles:true}));}
  }else{
    el.innerText=decoded;
    el.dispatchEvent(new Event('input',{bubbles:true}));
  }
  return 'OK:'+el.tagName;
})()`;

    const t0 = Date.now();
    try {
      const inputResult = this.safari.runJavaScript(inputJs);
      if (inputResult.startsWith("ERROR")) {
        return { status: "error", response: inputResult, durationMs: Date.now() - t0 };
      }
    } catch (e: any) {
      return { status: "error", response: e.message, durationMs: Date.now() - t0 };
    }

    await sleep(800);

    // 送信ボタンクリック
    const sendJs = `(function(){
  var selectors='${config.sendSelector}'.split(', ');
  var btn=null;
  for(var s of selectors){btn=document.querySelector(s);if(btn)break;}
  if(!btn) return 'ERROR: send not found';
  btn.click(); return 'OK';
})()`;

    try {
      const sendResult = this.safari.runJavaScript(sendJs);
      if (sendResult.startsWith("ERROR")) {
        return { status: "error", response: sendResult, durationMs: Date.now() - t0 };
      }
    } catch (e: any) {
      return { status: "error", response: e.message, durationMs: Date.now() - t0 };
    }

    // 応答を待つ
    await sleep(3000);
    const pollJs = `(function(){
  var text=document.body.innerText;
  var marker='${config.responseMarker}';
  var parts=text.split(marker);
  if(parts.length>1){
    var last=parts[parts.length-1];
    ${config.footerStrip.map(s => `var idx=last.indexOf('${s}'); if(idx>0) last=last.substring(0,idx);`).join("\n    ")}
    return last.trim();
  }
  return '';
})()`;

    let lastResponse = "";
    let stableCount = 0;
    const deadline = Date.now() + timeout;

    while (Date.now() < deadline) {
      try {
        const resp = this.safari.runJavaScript(pollJs);
        if (resp.length > 0) {
          if (resp === lastResponse) {
            stableCount++;
            if (stableCount >= 2) {
              return { status: "success", response: resp, durationMs: Date.now() - t0 };
            }
          } else {
            stableCount = 0;
            lastResponse = resp;
          }
        }
      } catch {}
      await sleep(2000);
    }

    if (lastResponse) {
      return { status: "success", response: lastResponse, durationMs: Date.now() - t0 };
    }
    return { status: "timeout", response: "", durationMs: Date.now() - t0 };
  }

  private async resetProvider(provider: AIProvider): Promise<void> {
    // タブを閉じて新しいプライベートウィンドウで再開
    await this.safari.closeCurrentTab();
    await sleep(1000);

    const session = this.sessions.get(provider)!;
    session.turnCount = 0;
    session.isInitialized = false;

    // 再初期化は次の ask() で自動的に行われる
  }

  cleanup(): void {
    try { this.safari.closeCurrentTab(); } catch {}
    this.sessions.clear();
  }

  getSessionInfo(): Array<{ provider: AIProvider; turnCount: number; initialized: boolean }> {
    return Array.from(this.sessions.values()).map(s => ({
      provider: s.provider,
      turnCount: s.turnCount,
      initialized: s.isInitialized,
    }));
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}
