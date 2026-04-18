import { MemoryEngine } from "./engine.js";

const GEMINI_API_KEY = "AIzaSyATPOY0fmk94_bOWvkj13tvXGIegyjsZKE"; 

export async function extractEternalContext(sessionTurns: {role: string, content: string}[], engineRoot: string): Promise<void> {
    console.error("\n🧠 [Auto Selector] Scanning Session for Eternal Context Extraction via Gemini 3 Flash...");
    
    if (sessionTurns.length === 0) return;

    const engine = new MemoryEngine(engineRoot);
    const fullText = sessionTurns.map(t => `${t.role}: ${t.content}`).join("\n");
    const timestamp = Date.now();

    const prompt = `
You are the Eternal Context Memory Extractor for Verantyx.
Analyze the following session log and extract key architectural decisions, hard constraints, proven facts, or failed lessons.
You must output ONLY valid JSON in the following format:
{
  "extractions": [
    {
      "category": "front" | "near" | "mid" | "deep",
      "filename": "string_without_extension",
      "content_markdown": "Detailed markdown explanation"
    }
  ]
}

Categories meaning:
- front: Active/Current design constraints or operational parameters explicitly defined.
- near: Lessons learned, failed paths (e.g. system crashed when doing X).
- mid: Officially validated facts or completed large-scale design shifts.
- deep: Foundational knowledge or core truths established.

Log:
${fullText}
    `.trim();

    try {
        const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key=${GEMINI_API_KEY}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }],
                generationConfig: { response_mime_type: "application/json" }
            })
        });

        const data = await response.json();
        
        if (data.candidates && data.candidates[0].content) {
            const raw = data.candidates[0].content.parts[0].text;
            const parsed = JSON.parse(raw);
            
            let extractedCount = 0;
            if (parsed.extractions && Array.isArray(parsed.extractions)) {
                for (const item of parsed.extractions) {
                    engine.write(item.category, `${item.filename}_${timestamp}`, item.content_markdown);
                    console.error(`  -> Saved extraction: ${item.category}/${item.filename}_${timestamp}.md`);
                    extractedCount++;
                }
            }
            if (extractedCount === 0) {
                console.error("  -> No context thresholds reached. Dismissing ephemeral session.");
            }
        } else {
            console.error("  -> Gemini failed to classify session context.");
        }
    } catch (e: any) {
        console.error("  -> Network error during Eternal Context Extraction:", e.message);
    }
}

export async function compileTriLayerJCross(data: { kanjiTags: string, l1Summary: string, midResOperations: string[], rawText: string }, engineRoot: string): Promise<void> {
    console.error(`\n🌌 [Reflective Memory Agent] Compiling pure symbolic memory via MCP...`);

    try {
        const timestamp = Date.now();
        const nodeId = `TURN_${timestamp}.jcross`;
        
        const out = `■ JCROSS_NODE_MEMORY_${timestamp}
【空間座相】
${data.kanjiTags}

【位相対応表】
[標] := "${data.l1Summary}"

【操作対応表】
${data.midResOperations.join('\n')}

【原文】
${data.rawText}
`;

        const { MemoryEngine } = await import("./engine.js");
        const engine = new MemoryEngine(engineRoot);
        engine.write("front", nodeId, out.trim() + '\n');
        
        console.error(`  └─ [Saved] Main LLM successfully compiled symbolic memory: ${nodeId}`);
    } catch (e: any) {
        console.error("  └─ [Compiler Error] Memory Flow failed:", e.message);
        throw e;
    }
}


export async function sublimateToJCross(sessionTurns: {role: string, content: string}[], engineRoot: string): Promise<void> {
    console.error(`  └─ [Sublimation] Distilling ${sessionTurns.length} turns into Semantic Cortex (V6)...`);

    const fullText = sessionTurns.map(t => `${t.role.toUpperCase()}: ${t.content}`).join("\n");
    
    const prompt = `
You are the JCross V6 Sublimator. Distill these evicted chat turns into a permanent memory node.
- L1 Cache: Extract high-density entities (brands, names, tech concepts), core facts, and a one-sentence summary.
- Domain: Decide if this is 'system_core' (code/tech) or 'personal_memory' (opinions/user life).
- Spatial Tags: Assign 2-3 Kanji tags with weights (0.0 to 1.0). 
  Available: 渇 (thirst/need), 探 (search/discovery), 視 (observation), 核 (core/system), 認 (cognition).

Output ONLY VALID JSON:
{
  "l1_summary": "string",
  "domain": "personal_memory" | "system_core",
  "tags": { "Kanji": weight },
  "key_entities": ["str"]
}

Current Log:
${fullText}
`.trim();

    try {
        const fetch = (await import("node-fetch")).default;
        const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key=${GEMINI_API_KEY}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }],
                generationConfig: { response_mime_type: "application/json" }
            })
        });

        const data = await response.json() as any;
        if (data.candidates && data.candidates[0].content) {
            const raw = data.candidates[0].content.parts[0].text;
            const parsed = JSON.parse(raw);
            
            const timestamp = new Date().toISOString();
            const nodeId = `evicted_${Date.now()}`;
            
            // Construct Kanji tags string
            const tagsStr = Object.entries(parsed.tags || {})
                .map(([k, v]) => `[${k}:${v}]`)
                .join(" ");

            const jcrossV6 = `■ JCROSS_NODE_${nodeId}

【空間座相】
${tagsStr || "[視:0.5]"}

【次元概念】
Sublimated History: ${parsed.l1_summary?.slice(0, 100) || "Recent conversation"}

【領域】
${parsed.domain || "personal_memory"}

【時間刻印】
${timestamp}

---
[L1_Cache]
Keywords: ${parsed.key_entities?.join(", ") || "none"}
Summary: ${parsed.l1_summary}

[L2_Archive]
${fullText}
===
`;
            const { join } = await import("path");
            const jcrossPath = join(engineRoot, "jcross_v6", `${nodeId}.jcross`);
            const v6Dir = join(engineRoot, "jcross_v6");
            const { mkdirSync, writeFileSync, existsSync } = await import("fs");
            if (!existsSync(v6Dir)) mkdirSync(v6Dir, { recursive: true });
            
            writeFileSync(jcrossPath, jcrossV6);
            console.error(`  └─ [V6 Cortex] Sublimated to ${jcrossPath}`);
        }
    } catch (e: any) {
        console.error("  └─ [Sublimation Meta-Error] Failed to distill context:", e.message);
    }
}

export async function generateSnapshotAndAnchor(sessionTurns: {role: string, content: string}[], engineRoot: string): Promise<string> {
    console.error(`  └─ [Sublimation] Creating ARCHIVE ANCHOR and State Snapshot...`);

    const fullText = sessionTurns.map(t => `${t.role.toUpperCase()}: ${t.content}`).join("\n");
    
    const prompt = `
You are the JCross V6 Paging Engine. A context window limit has been reached. 
You must distill the entire previous session into a High-Density State Snapshot to be used as the new starting point.

RULES:
1. Snapshot MUST include: 
   - Summary of completed sub-tasks.
   - Current project status and active bottlenecks.
   - Crucial variables, paths, or logic branch decisions.
   - Next 3 immediate steps.
2. Metadata for Anchor Node:
   - Specific keywords for L1.
   - Domain classification ('system_core' or 'personal_memory').

Output ONLY VALID JSON:
{
  "state_snapshot_markdown": "string",
  "l1_summary": "string",
  "domain": "system_core" | "personal_memory",
  "key_entities": ["str"]
}

Current Full Log:
${fullText}
`.trim();

    try {
        const fetch = (await import("node-fetch")).default;
        const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key=${GEMINI_API_KEY}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }],
                generationConfig: { response_mime_type: "application/json" }
            })
        });

        const data = await response.json() as any;
        if (data.candidates && data.candidates[0].content) {
            const raw = data.candidates[0].content.parts[0].text;
            const parsed = JSON.parse(raw);
            
            const timestamp = new Date().toISOString();
            const nodeId = `anchor_${Date.now()}`;
            
            // Construct V6 Anchor JCross Node
            const jcrossV6 = `■ JCROSS_NODE_${nodeId}

【空間座相】
[核:1.0] [認:1.0] [時:1.0]

【次元概念】
SYSTEM ANCHOR: ${parsed.l1_summary?.slice(0, 100)}

【領域】
${parsed.domain || "system_core"}

【時間刻印】
${timestamp}

---
[L1_Cache]
Keywords: ${parsed.key_entities?.join(", ") || "none"}
Snapshot: ${parsed.state_snapshot_markdown}

[L2_Archive]
${fullText}
===
`;
            const { join } = await import("path");
            const jcrossPath = join(engineRoot, "jcross_v6", `${nodeId}.jcross`);
            const v6Dir = join(engineRoot, "jcross_v6");
            const { mkdirSync, writeFileSync, existsSync } = await import("fs");
            if (!existsSync(v6Dir)) mkdirSync(v6Dir, { recursive: true });
            
            writeFileSync(jcrossPath, jcrossV6);
            console.error(`  └─ [V6 Anchor] Created checkpoint at ${jcrossPath}`);
            
            return parsed.state_snapshot_markdown as string;
        }
    } catch (e: any) {
        console.error("  └─ [Paging Meta-Error] Failed to generate snapshot:", e.message);
        return "Context paging failed. Raw history was archived but no state snapshot was generated. Please use 'query_jcross' to find your last anchor.";
    }
    return "Snapshot generation failed.";
}

