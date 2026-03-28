/**
 * OperationAuditor — Validates agent operations before execution
 * Asks Gemini in private browsing for approval
 */

import { GeminiBridge } from "./gemini-bridge.js";

export interface OperationRequest {
  action: string;
  agent: string;
  context: string;
  availableAgents: string[];
  manual: string;
}

export interface OperationDecision {
  approved: boolean;
  selectedAgent: string;
  parameters: Record<string, any>;
  reasoning: string;
  confidence: number;
  rawResponse: string;
}

export class OperationAuditor {
  private bridge: GeminiBridge;

  constructor(bridge: GeminiBridge) {
    this.bridge = bridge;
  }

  async validateOperation(request: OperationRequest): Promise<OperationDecision> {
    const agentsList = request.availableAgents.map((a) => `- ${a}`).join("\n");

    const prompt = `エージェント操作の適切性を判断してください。

## リクエスト
操作: ${request.action}
エージェント: ${request.agent}
理由: ${request.context}

## 利用可能なエージェント
${agentsList}

## 操作マニュアル
${request.manual.slice(0, 1500)}

## 回答フォーマット (JSON)
\`\`\`json
{
  "approved": true,
  "selected_agent": "worker/sonnet",
  "parameters": {},
  "reasoning": "理由",
  "confidence": 0.85
}
\`\`\``;

    const result = await this.bridge.ask(
      prompt,
      `操作検証: ${request.action}`,
      60_000,
    );

    return this.parseDecision(result.response);
  }

  private parseDecision(response: string): OperationDecision {
    // Try JSON block
    const jsonMatch = response.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[1]);
        return {
          approved: Boolean(parsed.approved),
          selectedAgent: parsed.selected_agent ?? parsed.selectedAgent ?? "unknown",
          parameters: parsed.parameters ?? {},
          reasoning: parsed.reasoning ?? "",
          confidence: clampConfidence(parsed.confidence),
          rawResponse: response,
        };
      } catch {}
    }

    // Fallback: keyword extraction
    const lower = response.toLowerCase();
    const approved = /approve|承認|適切|問題なし/.test(lower) && !/reject|却下|不適切/.test(lower);

    return {
      approved,
      selectedAgent: "unknown",
      parameters: {},
      reasoning: response.slice(0, 200),
      confidence: 0.5,
      rawResponse: response,
    };
  }
}

function clampConfidence(val: any): number {
  const n = parseFloat(val);
  if (isNaN(n)) {return 0.5;}
  if (n > 1 && n <= 100) {return n / 100;}
  return Math.max(0, Math.min(1, n));
}
