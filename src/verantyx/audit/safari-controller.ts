/**
 * SafariController — Lowest-level Safari automation via AppleScript
 * Ported from verantyx_cli/bridge/safari_controller.py
 */

import { execSync, execFileSync } from "child_process";
import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

export interface AskResult {
  status: "success" | "subscription_warning" | "timeout" | "error";
  response: string;
  durationMs: number;
}

export class SafariController {
  // ── AppleScript execution ──

  runAppleScript(script: string): string {
    try {
      return execFileSync("osascript", ["-e", script], {
        timeout: 30_000,
        encoding: "utf-8",
      }).trim();
    } catch (e: any) {
      throw new Error(`AppleScript error: ${e.stderr || e.message}`, { cause: e });
    }
  }

  runAppleScriptFile(script: string): string {
    const path = join(tmpdir(), `verantyx_${Date.now()}.scpt`);
    try {
      writeFileSync(path, script, "utf-8");
      const out = execFileSync("osascript", [path], {
        timeout: 60_000,
        encoding: "utf-8",
      }).trim();
      unlinkSync(path);
      return out;
    } catch (e: any) {
      try { unlinkSync(path); } catch {}
      throw new Error(`AppleScript file error: ${e.stderr || e.message}`, { cause: e });
    }
  }

  // ── JavaScript in Safari ──

  runJavaScript(code: string): string {
    const escaped = code
      .replace(/\\/g, "\\\\")
      .replace(/"/g, '\\"')
      .replace(/\n/g, "\\n")
      .replace(/\r/g, "");

    try {
      return execFileSync(
        "osascript",
        [
          "-e", 'tell application "Safari"',
          "-e", `return do JavaScript "${escaped}" in front document`,
          "-e", "end tell",
        ],
        { timeout: 30_000, encoding: "utf-8" }
      ).trim();
    } catch (e: any) {
      throw new Error(`Safari JS error: ${e.stderr || e.message}`, { cause: e });
    }
  }

  // ── Private window ──

  async openPrivateWindow(url = "https://gemini.google.com"): Promise<void> {
    // System Events keystroke — NOT make new document
    this.runAppleScript(
      `tell application "Safari" to activate`
    );
    await sleep(300);
    this.runAppleScript(
      `tell application "System Events" to keystroke "n" using {command down, shift down}`
    );
    await sleep(1200);
    this.runAppleScript(
      `tell application "Safari" to set URL of front document to "${url}"`
    );
    await sleep(3000);
  }

  async closeCurrentTab(): Promise<void> {
    this.runAppleScript(
      `tell application "Safari" to close front document`
    );
  }

  async switchToNewGeminiTab(): Promise<void> {
    await this.closeCurrentTab();
    await sleep(1000);
    await this.openPrivateWindow("https://gemini.google.com");
  }

  // ── Gemini text input (base64 encoded) ──

  async typeText(text: string): Promise<void> {
    const b64 = Buffer.from(text, "utf-8").toString("base64");

    const js = `(function(){
  var encoded='${b64}';
  var decoded=decodeURIComponent(escape(atob(encoded)));
  var el=document.querySelector('div.ql-editor[contenteditable=true]');
  if(!el) el=document.querySelector('[role=textbox]');
  if(!el) el=document.querySelector('div[contenteditable=true]');
  if(!el) el=document.querySelector('textarea');
  if(!el) return 'ERROR: textarea not found';
  el.focus(); el.click();
  if(el.classList.contains('ql-editor')){
    var c=el.closest('.ql-container');
    var q=c&&c.__quill;
    if(q){q.setText(decoded);q.setSelection(decoded.length,0);q.emitter.emit('text-change',{ops:[{insert:decoded}]},{ops:[]},'user');}
    else{el.innerText=decoded;el.dispatchEvent(new Event('input',{bubbles:true}));}
  }else if(el.tagName==='TEXTAREA'||el.tagName==='INPUT'){
    var ns=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
    ns.call(el,decoded);el.dispatchEvent(new Event('input',{bubbles:true}));
  }else{el.innerText=decoded;el.dispatchEvent(new Event('input',{bubbles:true}));}
  return 'OK:'+el.tagName;
})()`;

    const result = this.runJavaScript(js);
    if (result.startsWith("ERROR")) {throw new Error(result);}
  }

  // ── Send button ──

  async sendMessage(): Promise<void> {
    const js = `(function(){
  var btn=document.querySelector('button[aria-label*="プロンプトを送信"]');
  if(!btn) btn=document.querySelector('button[aria-label*="Send"]');
  if(!btn) return 'ERROR: send button not found';
  if(btn.getAttribute('aria-disabled')==='true') return 'ERROR: send button disabled';
  btn.click(); return 'OK';
})()`;
    const result = this.runJavaScript(js);
    if (result.startsWith("ERROR")) {throw new Error(result);}
  }

  // ── Response extraction ──

  getResponseCount(): number {
    try {
      const js = `(function(){
  var parts=document.body.innerText.split('Gemini の回答');
  return ''+(parts.length-1);
})()`;
      const r = this.runJavaScript(js);
      const n = parseInt(r, 10);
      return isNaN(n) ? 0 : n;
    } catch {
      return 0;
    }
  }

  async waitForResponse(timeoutMs: number, prevResponseCount: number): Promise<string> {
    const start = Date.now();
    await sleep(3000); // initial wait

    const js = `(function(){
  var prevCount=${prevResponseCount};
  var allText=document.body.innerText;
  var marker='Gemini の回答';
  var parts=allText.split(marker);
  if(parts.length>prevCount+1){
    var last=parts[parts.length-1];
    var idx;
    idx=last.indexOf('あなたのプロンプト'); if(idx>0) last=last.substring(0,idx);
    idx=last.indexOf('Gemini は AI であり'); if(idx>0) last=last.substring(0,idx);
    idx=last.lastIndexOf('ツール'); if(idx>0) last=last.substring(0,idx);
    idx=last.indexOf('回答案を表示'); if(idx>0) last=last.substring(0,idx);
    last=last.trim();
    if(last.length>0) return last;
  }
  return '';
})()`;

    let lastResponse = "";
    let stableCount = 0;

    while (Date.now() - start < timeoutMs) {
      try {
        const response = this.runJavaScript(js);
        if (response.length > 0) {
          if (response === lastResponse) {
            stableCount++;
            if (stableCount >= 2) {return response;}
          } else {
            stableCount = 0;
            lastResponse = response;
          }
        }
      } catch {}
      await sleep(2000);
    }

    if (lastResponse) {return lastResponse;}
    throw new Error("Gemini response timeout");
  }

  // ── Subscription warning ──

  checkSubscriptionWarning(): boolean {
    try {
      const text = this.runJavaScript("document.body.innerText").toLowerCase();

      const strict = [
        "upgrade to gemini advanced",
        "gemini advancedにアップグレード",
        "上限に達しました",
        "利用制限に達しました",
        "subscription required",
        "out of messages",
        "limit reached",
      ];
      for (const phrase of strict) {
        if (text.includes(phrase.toLowerCase())) {return true;}
      }

      const loose = ["subscription", "upgrade", "premium", "limit"];
      const count = loose.filter((kw) => text.includes(kw)).length;
      if (count >= 3 && (text.includes("gemini advanced") || text.includes("pricing"))) {
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  // ── High-level: ask Gemini ──

  async askGemini(prompt: string, timeoutMs = 60_000): Promise<AskResult> {
    const t0 = Date.now();

    if (this.checkSubscriptionWarning()) {
      return { status: "subscription_warning", response: "", durationMs: Date.now() - t0 };
    }

    const prevCount = this.getResponseCount();

    try {
      await this.typeText(prompt);
      await sleep(800);
      await this.sendMessage();
    } catch (e: any) {
      return { status: "error", response: e.message, durationMs: Date.now() - t0 };
    }

    try {
      const response = await this.waitForResponse(timeoutMs, prevCount);

      if (this.checkSubscriptionWarning()) {
        return { status: "subscription_warning", response, durationMs: Date.now() - t0 };
      }

      return { status: "success", response, durationMs: Date.now() - t0 };
    } catch (e: any) {
      return { status: "timeout", response: "", durationMs: Date.now() - t0 };
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
