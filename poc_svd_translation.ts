import { JCrossEngineDriver05B } from './src/verantyx/memory/ffi-driver-0-5b';
import { JCrossTokenizerDriver } from './src/verantyx/memory/ffi-driver-0-5b';
import * as path from 'path';
import * as fs from 'fs';

async function runPoC() {
    console.log("=== Verantyx Latent Translation PoC ===");
    const jgenPath = path.resolve(__dirname, 'qwen_0.5b_full.jgen');
    if (!fs.existsSync(jgenPath)) {
        console.error("qwen_0.5b_full.jgen not found.");
        return;
    }

    console.log("[System] Booting Worker (Thinking Engine) - O(1) Memory Map...");
    const worker = new JCrossEngineDriver05B(jgenPath);

    console.log("[System] Booting Coder (Translation Engine) - O(1) Memory Map...");
    const coder = new JCrossEngineDriver05B(jgenPath);

    const tokenizer = new JCrossTokenizerDriver(path.resolve(__dirname, 'tokenizer.json'));

    const promptText = "Translate the following intent into a Python script: loop 5 times and print 'Verantyx is awesome'";
    console.log(`\n[User Prompt]: ${promptText}`);
    
    // 1. Thinking Phase (Worker)
    const promptTokens = tokenizer.encode(promptText);
    console.log(`\n[Worker] Thinking Phase... (Encoding ${promptTokens.length} tokens into pure latent vector)`);
    
    const hiddenDim = 896;
    // Worker processes the prompt and extracts the core intent vector
    const hWorker = worker.executeWorkerForward(new Uint32Array(promptTokens), hiddenDim);
    console.log(`[Worker] Intent Vector Extracted. Dim: ${hWorker.length}`);
    
    // 2. Spatial Translation Phase (The Synapse M)
    console.log(`\n[Translation] Applying Latent Translation Matrix M (Identity mapping for this PoC)...`);
    const hCoder = new Float32Array(hWorker); // h_coder = M * h_worker

    // 3. Translation Phase (Coder)
    console.log(`\n[Coder] Translation Phase...`);
    console.log(`[Coder] Optimizing thought vector (Latent Gradient Descent) to align with Coder syntax space...`);
    const finalEntropy = coder.optimizeThoughtInPlace("lm_head", hCoder, 50, 100.0, 1.0);
    console.log(`[Coder] Spatial alignment complete. Entropy locked to: ${finalEntropy.toFixed(4)}`);
    
    // Lock the first token
    const res = coder.executePuzzleInference("lm_head", hCoder);
    console.log(`[Coder] Resonance Lock achieved. First Token ID: ${res.token}`);
    
    // Translate the thought structure into Python code
    let patchOutput = tokenizer.decode(res.token);
    console.log(`\n[Coder] Translating Thought into Text (Code):`);
    process.stdout.write(patchOutput);

    const generatedIds = coder.executeGenerationLoop(res.token, 50); // generate 50 tokens
    for (let i = 0; i < generatedIds.length; i++) {
        if (generatedIds[i] !== 0) {
            const word = tokenizer.decode(generatedIds[i]);
            process.stdout.write(word);
        } else {
            break; // EOS
        }
    }
    console.log("\n\n=== PoC Complete ===");

    worker.destroy();
    coder.destroy();
}

runPoC();
