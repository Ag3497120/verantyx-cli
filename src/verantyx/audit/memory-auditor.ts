/**
 * MemoryAuditor — Validates Cross spatial memory for hallucinations
 * Uses Gemini in private browsing as independent auditor
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, copyFileSync } from "fs";
import { join, basename } from "path";
import { GeminiBridge } from "./gemini-bridge.js";

export interface AuditResult {
  memoryName: string;
  zone: string;
  verdict: "VERIFIED" | "HALLUCINATION" | "UNCERTAIN";
  confidence: number;
  contradictions: string[];
  supportingEvidence: string[];
  rawResponse: string;
  timestamp: string;
}

export interface AuditSummary {
  total: number;
  verified: number;
  hallucinations: number;
  uncertain: number;
  details: AuditResult[];
}

export class MemoryAuditor {
  private bridge: GeminiBridge;
  private memoryRoot: string;

  constructor(bridge: GeminiBridge, memoryRoot: string) {
    this.bridge = bridge;
    this.memoryRoot = memoryRoot;
    // Ensure new zones exist
    for (const zone of ["verified", "audit", "todo"]) {
      const dir = join(memoryRoot, zone);
      if (!existsSync(dir)) {mkdirSync(dir, { recursive: true });}
    }
  }

  async auditMemory(zone: string, name: string): Promise<AuditResult> {
    const filePath = join(this.memoryRoot, zone, name.endsWith(".md") ? name : `${name}.md`);
    if (!existsSync(filePath)) {
      throw new Error(`Memory not found: ${filePath}`);
    }

    const content = readFileSync(filePath, "utf-8");

    const prompt = `以下の技術文書の正確性を検証してください。

## 検証対象
${content}

## 回答フォーマット
1. 判定: VERIFIED / HALLUCINATION / UNCERTAIN
2. 矛盾点: (ある場合リストアップ)
3. 根拠: (判定の理由)
4. 信頼度: 0.0〜1.0

事実に基づいて客観的に回答してください。`;

    const result = await this.bridge.ask(prompt, `メモリ監査: ${zone}/${name}`, 90_000);
    const parsed = this.parseAuditResponse(result.response);

    const auditResult: AuditResult = {
      memoryName: name,
      zone,
      verdict: parsed.verdict,
      confidence: parsed.confidence,
      contradictions: parsed.contradictions,
      supportingEvidence: parsed.supportingEvidence,
      rawResponse: result.response,
      timestamp: new Date().toISOString(),
    };

    // Write audit log
    this.writeAuditLog(auditResult);

    // Move to verified/ if VERIFIED
    if (auditResult.verdict === "VERIFIED") {
      this.moveToVerified(zone, name, auditResult);
    } else if (auditResult.verdict === "HALLUCINATION") {
      this.markStale(zone, name);
    }

    return auditResult;
  }

  async auditZone(zone: string): Promise<AuditResult[]> {
    const dir = join(this.memoryRoot, zone);
    if (!existsSync(dir)) {return [];}

    const { readdirSync } = await import("fs");
    const files = readdirSync(dir).filter((f) => f.endsWith(".md"));
    const results: AuditResult[] = [];

    for (const file of files) {
      try {
        const r = await this.auditMemory(zone, file);
        results.push(r);
      } catch (e: any) {
        console.error(`Audit failed for ${zone}/${file}: ${e.message}`);
      }
    }
    return results;
  }

  async runPeriodicAudit(): Promise<AuditSummary> {
    const allResults: AuditResult[] = [];
    for (const zone of ["front", "near", "mid", "deep"]) {
      const results = await this.auditZone(zone);
      allResults.push(...results);
    }
    return {
      total: allResults.length,
      verified: allResults.filter((r) => r.verdict === "VERIFIED").length,
      hallucinations: allResults.filter((r) => r.verdict === "HALLUCINATION").length,
      uncertain: allResults.filter((r) => r.verdict === "UNCERTAIN").length,
      details: allResults,
    };
  }

  // ── Private helpers ──

  private parseAuditResponse(response: string): {
    verdict: "VERIFIED" | "HALLUCINATION" | "UNCERTAIN";
    confidence: number;
    contradictions: string[];
    supportingEvidence: string[];
  } {
    const lower = response.toLowerCase();

    // Verdict
    let verdict: "VERIFIED" | "HALLUCINATION" | "UNCERTAIN" = "UNCERTAIN";
    if (/verified|正確|問題なし/.test(lower)) {verdict = "VERIFIED";}
    else if (/hallucination|誤り|不正確|ハルシネーション/.test(lower)) {verdict = "HALLUCINATION";}

    // Confidence
    let confidence = 0.5;
    const confMatch = response.match(/(?:信頼度|confidence)[:\s]*([0-9]+\.?[0-9]*)/i);
    if (confMatch) {
      const val = parseFloat(confMatch[1]);
      if (val >= 0 && val <= 1) {confidence = val;}
      else if (val > 1 && val <= 100) {confidence = val / 100;}
    }

    // Contradictions
    const contradictions: string[] = [];
    const contraSection = response.match(/(?:矛盾点|contradictions?)[:\s]*([\s\S]*?)(?:\n(?:根拠|supporting|信頼度|confidence)|$)/i);
    if (contraSection) {
      const lines = contraSection[1].split("\n").map((l) => l.replace(/^[-*•]\s*/, "").trim()).filter(Boolean);
      contradictions.push(...lines.filter((l) => l.length > 2 && !/^なし$|^none$/i.test(l)));
    }

    // Supporting evidence
    const supportingEvidence: string[] = [];
    const evidSection = response.match(/(?:根拠|supporting evidence?)[:\s]*([\s\S]*?)(?:\n(?:信頼度|confidence)|$)/i);
    if (evidSection) {
      const lines = evidSection[1].split("\n").map((l) => l.replace(/^[-*•]\s*/, "").trim()).filter(Boolean);
      supportingEvidence.push(...lines.filter((l) => l.length > 2));
    }

    return { verdict, confidence, contradictions, supportingEvidence };
  }

  private writeAuditLog(result: AuditResult): void {
    const auditDir = join(this.memoryRoot, "audit");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const logPath = join(auditDir, `audit_${stamp}_${result.memoryName.replace(/\.md$/, "")}.md`);

    const content = `---
name: Audit Log ${result.timestamp}
type: audit
timestamp: ${result.timestamp}
target: ${result.zone}/${result.memoryName}
verdict: ${result.verdict}
confidence: ${result.confidence}
---

## Audit Details
- Target: ${result.zone}/${result.memoryName}
- Verdict: ${result.verdict}
- Confidence: ${result.confidence}
- Contradictions: ${result.contradictions.length > 0 ? result.contradictions.join("; ") : "none"}
- Supporting evidence: ${result.supportingEvidence.length > 0 ? result.supportingEvidence.join("; ") : "none"}

## Raw Response
${result.rawResponse.slice(0, 2000)}
`;
    writeFileSync(logPath, content, "utf-8");
  }

  private moveToVerified(zone: string, name: string, audit: AuditResult): void {
    const src = join(this.memoryRoot, zone, name.endsWith(".md") ? name : `${name}.md`);
    const dest = join(this.memoryRoot, "verified", basename(src));
    if (!existsSync(src)) {return;}

    let content = readFileSync(src, "utf-8");

    // Inject audit metadata into frontmatter
    const fmEnd = content.indexOf("---", 4);
    if (fmEnd > 0) {
      const insertPos = fmEnd;
      const auditMeta = `verified: true
audit_date: ${audit.timestamp}
audit_verdict: ${audit.verdict}
audit_confidence: ${audit.confidence}
audit_source: gemini-private
original_zone: ${zone}
`;
      content = content.slice(0, insertPos) + auditMeta + content.slice(insertPos);
    }

    writeFileSync(dest, content, "utf-8");
  }

  private markStale(zone: string, name: string): void {
    const filePath = join(this.memoryRoot, zone, name.endsWith(".md") ? name : `${name}.md`);
    if (!existsSync(filePath)) {return;}

    let content = readFileSync(filePath, "utf-8");
    if (!content.includes("[STALE]")) {
      content = content.replace(/^(---\n)/, `$1# [STALE] — Flagged by Gemini audit\n`);
      writeFileSync(filePath, content, "utf-8");
    }
  }
}
