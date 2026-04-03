/**
 * Triple-Check Memory Verification
 *
 * 3つの独立したAIが同意した情報だけが信頼される。
 * 1. Commander (Opus) が記憶を書く
 * 2. Gemini (プライベート) が検証
 * 3. ChatGPT (プライベート) が独立検証
 * → 2/3以上がVERIFIED → verified/に移動
 * → 1/3以下 → UNCERTAIN、手動確認待ち
 */

import { GeminiBridge } from "./gemini-bridge.js";
import { MultiAIBridge } from "./multi-ai-bridge.js";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";

export interface TripleCheckResult {
  memoryName: string;
  zone: string;
  geminiVerdict: string;
  chatgptVerdict: string;
  commanderVerdict: string;
  consensus: "VERIFIED" | "UNCERTAIN" | "REJECTED";
  agreementRatio: string;  // "3/3", "2/3", "1/3", "0/3"
  details: {
    gemini: string;
    chatgpt: string;
    commander: string;
  };
  timestamp: string;
}

export class TripleCheckAuditor {
  private memoryRoot: string;

  constructor(memoryRoot: string) {
    this.memoryRoot = memoryRoot;
    const tripleDir = join(memoryRoot, "audit", "triple");
    if (!existsSync(tripleDir)) mkdirSync(tripleDir, { recursive: true });
  }

  async verify(zone: string, name: string): Promise<TripleCheckResult> {
    const filePath = join(this.memoryRoot, zone, name.endsWith(".md") ? name : `${name}.md`);
    if (!existsSync(filePath)) {
      throw new Error(`Memory not found: ${filePath}`);
    }

    const content = readFileSync(filePath, "utf-8");
    const auditPrompt = this.buildAuditPrompt(content);

    // 1. Gemini (private browser)
    let geminiVerdict = "UNCERTAIN";
    let geminiDetail = "";
    try {
      const bridge = new GeminiBridge();
      const result = await bridge.ask(auditPrompt, undefined, 90_000);
      geminiVerdict = this.parseVerdict(result.response);
      geminiDetail = result.response.slice(0, 200);
      bridge.cleanup();
    } catch (e: unknown) {
      geminiDetail = `Error: ${e instanceof Error ? e.message : String(e)}`;
    }

    // 2. ChatGPT (private browser)
    let chatgptVerdict = "UNCERTAIN";
    let chatgptDetail = "";
    try {
      const multi = new MultiAIBridge();
      const result = await multi.auditCode(content, "factual accuracy and consistency");
      chatgptVerdict = this.parseVerdict(result.response);
      chatgptDetail = result.response.slice(0, 200);
      multi.cleanup();
    } catch (e: unknown) {
      chatgptDetail = `Error: ${e instanceof Error ? e.message : String(e)}`;
    }

    // 3. Commander self-assessment (from memory metadata)
    const commanderVerdict = content.includes("verified: true") ? "VERIFIED" : "UNCERTAIN";
    const commanderDetail = "Self-reported verification status from frontmatter";

    // Consensus
    const verdicts = [geminiVerdict, chatgptVerdict, commanderVerdict];
    const verifiedCount = verdicts.filter(v => v === "VERIFIED").length;
    const rejectedCount = verdicts.filter(v => v === "HALLUCINATION" || v === "REJECTED").length;

    let consensus: "VERIFIED" | "UNCERTAIN" | "REJECTED";
    if (verifiedCount >= 2) {
      consensus = "VERIFIED";
    } else if (rejectedCount >= 2) {
      consensus = "REJECTED";
    } else {
      consensus = "UNCERTAIN";
    }

    const result: TripleCheckResult = {
      memoryName: name,
      zone,
      geminiVerdict,
      chatgptVerdict,
      commanderVerdict,
      consensus,
      agreementRatio: `${verifiedCount}/3`,
      details: {
        gemini: geminiDetail,
        chatgpt: chatgptDetail,
        commander: commanderDetail,
      },
      timestamp: new Date().toISOString(),
    };

    // Save log
    this.saveLog(result);

    // Move to verified if consensus
    if (consensus === "VERIFIED") {
      this.moveToVerified(zone, name, result);
    }

    return result;
  }

  private buildAuditPrompt(content: string): string {
    return `以下の技術文書の事実の正確性を検証してください。

## 検証対象
${content.slice(0, 3000)}

## 回答
1行目に判定を書いてください: VERIFIED / HALLUCINATION / UNCERTAIN
2行目以降に理由を書いてください。`;
  }

  private parseVerdict(response: string): string {
    const lower = response.toLowerCase();
    if (/verified|正確|問題なし|pass/.test(lower)) return "VERIFIED";
    if (/hallucination|誤り|不正確|fail|reject/.test(lower)) return "HALLUCINATION";
    return "UNCERTAIN";
  }

  private saveLog(result: TripleCheckResult): void {
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const logPath = join(
      this.memoryRoot, "audit", "triple",
      `triple_${stamp}_${result.memoryName.replace(/\.md$/, "")}.md`
    );

    const content = `---
name: Triple-Check ${result.timestamp}
type: audit
consensus: ${result.consensus}
agreement: ${result.agreementRatio}
---

# Triple-Check Audit: ${result.zone}/${result.memoryName}

| Source | Verdict |
|--------|---------|
| Gemini | ${result.geminiVerdict} |
| ChatGPT | ${result.chatgptVerdict} |
| Commander | ${result.commanderVerdict} |

**Consensus: ${result.consensus} (${result.agreementRatio})**

## Details
- Gemini: ${result.details.gemini}
- ChatGPT: ${result.details.chatgpt}
- Commander: ${result.details.commander}
`;
    writeFileSync(logPath, content, "utf-8");
  }

  private moveToVerified(zone: string, name: string, result: TripleCheckResult): void {
    const src = join(this.memoryRoot, zone, name.endsWith(".md") ? name : `${name}.md`);
    const verifiedDir = join(this.memoryRoot, "verified");
    if (!existsSync(verifiedDir)) mkdirSync(verifiedDir, { recursive: true });

    const dest = join(verifiedDir, name.endsWith(".md") ? name : `${name}.md`);
    let content = readFileSync(src, "utf-8");

    // Inject triple-check metadata
    const fmEnd = content.indexOf("---", 4);
    if (fmEnd > 0) {
      const meta = `triple_checked: true
triple_check_date: ${result.timestamp}
triple_check_consensus: ${result.consensus}
triple_check_agreement: ${result.agreementRatio}
`;
      content = content.slice(0, fmEnd) + meta + content.slice(fmEnd);
    }

    writeFileSync(dest, content, "utf-8");
  }
}
