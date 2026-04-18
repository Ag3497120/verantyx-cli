import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { compileTriLayerJCross } from "../memory/auto-selector.js";
import path from "path";
import fs from "fs";

// The MCP Server definition
const server = new Server(
    {
        name: "verantyx-trilayer-memory",
        version: "1.0.0",
    },
    {
        capabilities: {
            tools: {}
        }
    }
);

const ENGINE_ROOT = path.resolve(process.env.HOME || "~", ".openclaw/memory");

server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            {
                name: "compile_trilayer_memory",
                description: "Directly compile a 3-Layer JCross Memory node into the Front drive using Main LLM symbolic extraction (no local SLM).",
                inputSchema: {
                    type: "object",
                    properties: {
                        kanjiTags: {
                            type: "string",
                            description: "Layer 1 Topology: A string defining Spatial Kanji tags and weights. Example: '[標: 指示] [認: 1.0] [視: 0.8]'"
                        },
                        l1Summary: {
                            type: "string",
                            description: "Layer 1 Summary: A concise 1-2 sentence description of the critical decision or system state."
                        },
                        midResOperations: {
                            type: "array",
                            items: { type: "string" },
                            description: "Layer 2 Logic: A list of operation strings like 'OP.MAP_STATE(\"Agent Loop Phase\", \"[状態: 最終回答]\")' or 'OP.MAP(\"Concept\", \"[概念: X]\")'."
                        },
                        rawText: {
                            type: "string",
                            description: "Layer 3 Raw Text: A complete verbatim copy or deep description of the context/conversation to permanently store."
                        }
                    },
                    required: ["kanjiTags", "l1Summary", "midResOperations", "rawText"]
                }
            },
            {
                name: "scan_front_memory",
                description: "Quickly scan the metadata (Kanji Tags) of all JCross nodes in the front memory drive.",
                inputSchema: {
                    type: "object",
                    properties: {}
                }
            },
            {
                name: "migrate_memory_zone",
                description: "Safely and atomically move a memory node (e.g., tracking a completed task) from one spatial zone to another to establish active working memory Garbage Collection.",
                inputSchema: {
                    type: "object",
                    properties: {
                        fileName: {
                            type: "string",
                            description: "The name of the memory file to migrate (e.g., 'TURN_1234.jcross')."
                        },
                        targetZone: {
                            type: "string",
                            description: "The destination zone ('near', 'mid', or 'deep').",
                            enum: ["front", "near", "mid", "deep"]
                        }
                    },
                    required: ["fileName", "targetZone"]
                }
            },
            {
                name: "spatial_cross_search",
                description: "Utilizes the ARC-SGI Gravity Z-Depth algorithm to perform associative memory retrieval. Pulls dormant cross-spatial memory nodes representing similar architectural intent into the active context layer instantly.",
                inputSchema: {
                    type: "object",
                    properties: {
                        queryKanji: {
                            type: "object",
                            description: "A dictionary representing the search vector for Kanji Topology. Example: {'標': 1.0, '認': 0.8}",
                            additionalProperties: { type: "number" }
                        }
                    },
                    required: ["queryKanji"]
                }
            }
        ]
    };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (name === "compile_trilayer_memory") {
        const { kanjiTags, l1Summary, midResOperations, rawText } = args as any;
        
        try {
            await compileTriLayerJCross({ kanjiTags, l1Summary, midResOperations, rawText }, ENGINE_ROOT);
            return {
                content: [{ type: "text", text: "Successfully Compiled Pure CPU Symbolic Memory to JCross Drive." }]
            };
        } catch (e: any) {
            return {
                isError: true,
                content: [{ type: "text", text: `Failed to compile memory: ${e.message}` }]
            };
        }
    }
    
    if (name === "scan_front_memory") {
        try {
            const frontDir = path.join(ENGINE_ROOT, "front");
            if (!fs.existsSync(frontDir)) {
                return { content: [{ type: "text", text: "Front memory empty." }] };
            }
            
            const files = fs.readdirSync(frontDir).filter(f => f.endsWith(".jcross"));
            let summaries = [];
            for (const f of files) {
                const content = fs.readFileSync(path.join(frontDir, f), "utf-8");
                const phaseMatch = content.match(/【位相対応表】([\s\S]*?)【操作対応表】/);
                if (phaseMatch) {
                    summaries.push(`[File: ${f}]\n${phaseMatch[1].trim()}`);
                }
            }
            return {
                content: [{ type: "text", text: summaries.length > 0 ? summaries.join("\n\n") : "No Kanji topology found." }]
            };
        } catch (e: any) {
            return {
                 isError: true,
                 content: [{ type: "text", text: `Error reading memory: ${e.message}` }]
            };
        }
    }

    if (name === "migrate_memory_zone") {
        const { fileName, targetZone } = args as any;
        try {
            const { MemoryEngine } = await import("../memory/engine.js");
            const engine = new MemoryEngine(ENGINE_ROOT);
            const success = engine.move(fileName, targetZone);
            if (success) {
                return { content: [{ type: "text", text: `Successfully migrated ${fileName} to ${targetZone}/ zone.` }] };
            } else {
                return { isError: true, content: [{ type: "text", text: `Failed to find ${fileName} in any zone to migrate.` }] };
            }
        } catch (e: any) {
            return {
                isError: true,
                content: [{ type: "text", text: `Migration error: ${e.message}` }]
            };
        }
    }

    if (name === "spatial_cross_search") {
        const { queryKanji } = args as any;
        try {
            const { GravitySolver } = await import("../memory/spatial_search.js");
            const solver = new GravitySolver(ENGINE_ROOT);
            const surfaced = solver.triggerFlashback(queryKanji);
            const details = solver.getSurfacedNodeDetails(surfaced);
            
            return {
                content: [{ type: "text", text: details.trim() || "No correlating Kanji structures found in Deep Memory." }]
            };
        } catch (e: any) {
            return {
                isError: true,
                content: [{ type: "text", text: `Gravity Search error: ${e.message}` }]
            };
        }
    }

    throw new Error(`Unknown tool: ${name}`);
});

// Start the stdio transport
async function run() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("Verantyx Tri-Layer MCP Server running on stdio");
}

run().catch(console.error);
