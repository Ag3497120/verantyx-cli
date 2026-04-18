import { MemoryEngine } from "../memory/engine.js";
import { join } from "path";
import { readFileSync, existsSync } from "fs";

export interface TopologyNode {
    id: string;
    zone: string;
    dimensions: Record<string, number>;
    zDepth: number; // 0.0 is active consciousness, negative is dormant
    rawText?: string;
}

export class GravitySolver {
    private registry: Map<string, TopologyNode> = new Map();
    private engine: MemoryEngine;

    constructor(engineRoot: string) {
        this.engine = new MemoryEngine(engineRoot);
        this.hydrateRegistry();
    }

    private hydrateRegistry() {
        const zones = ["front", "near", "mid"];
        // For performance, we only load the Ultra-Low Res Topology Phase 
        // to avoid reading MBs of text.
        for (const zone of zones) {
            const entries = this.engine.list(zone);
            for (const entry of entries) {
                if (!entry.path.endsWith(".jcross")) continue;
                
                try {
                    const content = readFileSync(entry.path, "utf-8");
                    const dims = this.extractKanjiDimensions(content);
                    
                    // Base starting depth: front is 0, near is -10, mid is -100
                    const baseZ = zone === "front" ? 0.0 : (zone === "near" ? -10.0 : -100.0);
                    
                    this.registry.set(entry.name, {
                        id: entry.name,
                        zone,
                        dimensions: dims,
                        zDepth: baseZ
                    });
                } catch (e) {
                    continue;
                }
            }
        }
    }

    private extractKanjiDimensions(content: string): Record<string, number> {
        const dims: Record<string, number> = {};
        const match = content.match(/【空間座相】([\s\S]*?)【/);
        if (match) {
            const tagStr = match[1].trim();
            // e.g. [標: 1.0] [認: 0.8]
            const regex = /\[(.*?):\s*([0-9.]+)\]/g;
            let m;
            while ((m = regex.exec(tagStr)) !== null) {
                dims[m[1]] = parseFloat(m[2]);
            }
        }
        return dims;
    }

    /**
     * Executes the ARC-SGI spreading activation to pull related nodes
     * out of deep Z-depth dormancy based on a query topology.
     */
    public triggerFlashback(queryKanjiTags: Record<string, number>): TopologyNode[] {
        // Step 1: Calculate "Gravity Pull" (Cosine Similarity with query vector)
        for (const [id, node] of this.registry.entries()) {
            let pullForce = 0;
            let queryMagnitude = 0;
            let nodeMagnitude = 0;
            
            for (const [kanji, weight] of Object.entries(queryKanjiTags)) {
                pullForce += weight * (node.dimensions[kanji] || 0.0);
                queryMagnitude += weight * weight;
            }
            
            for (const weight of Object.values(node.dimensions)) {
                nodeMagnitude += weight * weight;
            }
            
            queryMagnitude = Math.sqrt(queryMagnitude);
            nodeMagnitude = Math.sqrt(nodeMagnitude);
            
            if (queryMagnitude > 0 && nodeMagnitude > 0) {
                const similarity = pullForce / (queryMagnitude * nodeMagnitude);
                
                // If similarity > 0.8, it receives an intense Flashback pull (+100.0 Z-shift)
                if (similarity > 0.8) {
                    node.zDepth = Math.min(0.0, node.zDepth + 100.0); // Surface it to 0.0
                } else if (similarity > 0.5) {
                    node.zDepth = Math.min(0.0, node.zDepth + 50.0); // Pull halfway up
                }
            }
        }

        // Return the newly surfaced subconscious nodes (Z >= -5.0) that aren't already in front
        const surfaced = Array.from(this.registry.values())
            .filter(n => n.zDepth >= -5.0)
            .sort((a, b) => b.zDepth - a.zDepth); // closest to front first
            
        return surfaced;
    }

    public getSurfacedNodeDetails(nodes: TopologyNode[]): string {
        let output = "";
        for (const n of nodes) {
            output += `[Node IDs Surfaced from ${n.zone} (Z: ${n.zDepth.toFixed(2)})]\n`;
            output += `-> ID: ${n.id}\n`;
            
            // If it's a Resolution 2/3 node, fetch the High-Density Intent Header
            const entryPath = join(this.engine.getRoot(), n.zone, `${n.id}.jcross`);
            if (existsSync(entryPath)) {
                const content = readFileSync(entryPath, "utf-8");
                const intentMatch = content.match(/【位相対応表】([\s\S]*?)【/);
                if (intentMatch) {
                    output += `-> Nuance: ${intentMatch[1].trim()}\n`;
                }
            }
            output += "\n";
        }
        return output;
    }
}
