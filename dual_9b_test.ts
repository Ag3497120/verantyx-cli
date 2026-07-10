import { JCrossEngineDriver, JCrossTokenizerDriver } from './src/verantyx/memory/ffi-driver';
import * as path from 'path';
import * as fs from 'fs';

async function runDual9BJgen() {
    console.log("=== Verantyx Dual-JGEN Telepathy Protocol (Full) ===");
    
    const jgenPath = path.resolve(__dirname, 'qwen_9b_full.jgen');
    if (!fs.existsSync(jgenPath)) {
        console.error(`Error: Full 9B model not found at ${jgenPath}. Please ensure it exists.`);
        return;
    }
    const tokenizerPath = path.resolve(__dirname, 'tokenizer.json');
    
    console.log("\n[Cortex] Booting 9B Engines (Zero-Copy Mmap)...");
    
    // We can use two driver instances pointing to the same file.
    // OS will map the 23GB file into physical RAM only once!
    const worker = new JCrossEngineDriver(jgenPath);
    console.log("[Cortex] Worker Engine Loaded (O(1) Memory).");
    
    const coder = new JCrossEngineDriver(jgenPath);
    console.log("[Cortex] Coder Engine Loaded (O(1) Memory).");
    
    console.log("\n--- [Phase 1: Worker (Cognitive Search)] ---");
    // Dummy prompt token sequence (e.g., "Implement a quicksort function in Rust")
    // For this POC we just use some random valid token IDs as the prompt.
    const promptTokens = new Uint32Array([1056, 314, 256, 912, 1145, 12]); 
    console.log(`[Worker] Reading Prompt Tokens: [${promptTokens.join(', ')}]`);
    
    // Qwen 9B has 3584 hidden dimensions
    const hiddenDim = 4096; 
    let intentVector;
    try {
        intentVector = worker.executeWorkerForward(promptTokens, hiddenDim);
        console.log(`[Worker] Extracted ${hiddenDim}-dim conceptual blueprint (Intent Vector) from final token.`);
    } catch (e) {
        console.error("Worker forward pass failed:", e);
        return;
    }

    console.log("\n--- [Phase 2: Cortex Routing] ---");
    console.log("[Cortex] Routing 4096-dim vector directly to Coder (Zero-Copy FFI)...");

    console.log("\n--- [Phase 3: Coder (Latent Resonance Search)] ---");
    let startToken = 0;
    try {
        const resonance = coder.executePuzzleInference("lm_head.weight", intentVector);
        console.log(`[Coder] Resonance Lock achieved!`);
        console.log(`[Coder] Locked Token ID: ${resonance.token}`);
        console.log(`[Coder] Shannon Entropy (Resistance): ${resonance.entropy.toFixed(4)}`);
        startToken = resonance.token;
    } catch (e) {
        console.error("Coder inference failed:", e);
        return;
    }
    
    console.log("\n--- [Phase 4: Coder (Autoregressive Generation)] ---");
    console.log(`[Coder] Engaging generation loop for 10 tokens...`);
    const generatedIds = coder.executeGenerationLoop(startToken, 10);
    
    process.stdout.write("[Coder Output]: ");
    for (let i = 0; i < generatedIds.length; i++) {
        process.stdout.write(generatedIds[i] + " ");
    }
    console.log("\n\n[Cortex] Telepathic transmission complete.");

    worker.destroy();
    coder.destroy();
}

runDual9BJgen();
