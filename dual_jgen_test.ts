import { JCrossEngineDriver } from './src/verantyx/memory/ffi-driver';
import * as path from 'path';

async function runDualJgen() {
    console.log("=== Verantyx Dual-JGEN Telepathy Protocol ===");
    const jgenPath = path.resolve(__dirname, 'qwen_9b_full.jgen');
    const coder = new JCrossEngineDriver(jgenPath);

    const intentVector = new Float32Array(4096);
    for (let i = 0; i < 4096; i++) intentVector[i] = Math.sin(i * 0.05) * 0.2;

    try {
        const resonance = coder.executePuzzleInference("lm_head.weight", intentVector);
        console.log(`[Coder] Resonance Lock achieved!`);
        console.log(`[Coder] Locked Token ID: ${resonance.token}`);
        console.log(`[Coder] Shannon Entropy (Resistance): ${resonance.entropy.toFixed(4)}`);
    } catch (e) {
        console.error("Coder inference failed:", e);
    }
    coder.destroy();
}
runDualJgen();
