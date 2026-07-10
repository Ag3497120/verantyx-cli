import { JCrossEngineDriver05B, JCrossTokenizerDriver } from './src/verantyx/memory/ffi-driver-0-5b';
import * as path from 'path';
import * as readline from 'readline';

async function startSwarm() {
    console.log("=== Verantyx Swarm CLI (vtx-swarm) ===");
    console.log("[System] Booting JCross Engine - O(1) Memory Map...");

    const modelPath = path.resolve(__dirname, 'qwen_0.5b_full.jgen');
    const engine = new JCrossEngineDriver05B(modelPath);
    const tokenizerPath = path.resolve(__dirname, 'tokenizer.json');
    const tokenizer = new JCrossTokenizerDriver(tokenizerPath);
    
    console.log("[System] Engine booted successfully. Ready for input.\n");

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    const hiddenDim = 896; // Qwen 0.5B hidden size

    const promptUser = () => {
        rl.question("\n[User Intent] > ", (input) => {
            if (input.toLowerCase() === 'exit' || input.toLowerCase() === 'quit') {
                console.log("[System] Shutting down...");
                engine.destroy();
                tokenizer.destroy();
                rl.close();
                return;
            }
            if (input.trim() === '') {
                promptUser();
                return;
            }

            // ChatML format for Qwen
            const promptText = `<|im_start|>system\nYou are a helpful translation and coding assistant.<|im_end|>\n<|im_start|>user\n${input}<|im_end|>\n<|im_start|>assistant\n`;
            const promptTokens = tokenizer.encode(promptText);

            // ==========================================
            // Phase 1: WORKER PHASE
            // ==========================================
            console.log(`\n[Worker] Encoding intent into latent vector (Tokens: ${promptTokens.length})...`);
            
            // This builds the KV cache in the engine and returns the final hidden state
            const hWorker = engine.executeWorkerForward(new Uint32Array(promptTokens), hiddenDim);
            console.log(`[Worker] Extraction complete. Vector Dimension: ${hWorker.length}`);
            
            // ==========================================
            // Phase 2: TRANSLATION (SYNAPSE)
            // ==========================================
            // In a real SVD scenario, this is where M is applied.
            // For now, we pass the vector cleanly as a new Float32Array.
            const hCoder = new Float32Array(hWorker);
            
            // ==========================================
            // Phase 3: CODER PHASE
            // ==========================================
            // The Coder NEVER sees the `promptText` or `promptTokens`.
            // It only receives `hCoder` and the spatial context (KV cache) left by the Worker.
            console.log(`[Coder] Translating intent vector into code space (Latent Gradient Descent)...`);
            
            // Force the vector to align with the language model's output space
            const finalEntropy = engine.optimizeThoughtInPlace("lm_head", hCoder, 30, 100.0, 1.0);
            
            // Lock the first token based on the optimized vector
            const res = engine.executePuzzleInference("lm_head", hCoder);
            
            console.log(`[Coder] Resonance Lock achieved. Entropy: ${finalEntropy.toFixed(4)}. Generation started:`);
            console.log("--------------------------------------------------");
            
            let outputText = tokenizer.decode(res.token);
            process.stdout.write(outputText);

            // Generate subsequent tokens
            const maxTokens = 200;
            const generatedIds = engine.executeGenerationLoop(res.token, maxTokens);
            
            for (let i = 0; i < generatedIds.length; i++) {
                if (generatedIds[i] !== 0) { // Assuming 0 is pad/invalid, handle EOS logic
                    const word = tokenizer.decode(generatedIds[i]);
                    process.stdout.write(word);
                } else {
                    break;
                }
            }
            console.log("\n--------------------------------------------------");

            // Loop back for next input
            promptUser();
        });
    };

    promptUser();
}

startSwarm().catch(err => {
    console.error("[Fatal Error]", err);
    process.exit(1);
});
