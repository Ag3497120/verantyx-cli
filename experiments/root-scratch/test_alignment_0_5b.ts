import { JCrossEngineDriver05B, JCrossTokenizerDriver } from './src/verantyx/memory/ffi-driver-0-5b';
import * as path from 'path';

async function runAlignmentTest() {
    console.log("=== Testing Latent Alignment (Puzzle Inference) ===");
    const jgenPath = path.resolve(__dirname, 'qwen_0.5b_full.jgen');
    const engine = new JCrossEngineDriver05B(jgenPath);
    
    // We create a mock thought vector (random but fixed seed equivalent)
    const hiddenDim = 896; // For Qwen 0.5B
    const thoughtVector = new Float32Array(hiddenDim);
    for (let i = 0; i < hiddenDim; i++) {
        thoughtVector[i] = (Math.random() - 0.5) * 0.1; 
    }
    
    console.log("Initial thought vector created.");
    
    // 1. Check initial entropy before alignment
    const initialRes = engine.executePuzzleInference("lm_head", thoughtVector);
    console.log(`[Before Alignment] Max Token ID: ${initialRes.token}, Entropy: ${initialRes.entropy.toFixed(4)}`);
    
    // 2. Perform Latent Gradient Descent (Alignment)
    console.log("\nStarting spatial alignment (Gradient Descent)...");
    const finalEntropy = engine.optimizeThoughtInPlace("lm_head", thoughtVector, 50, 100.0, 1.0);
    console.log(`[After Alignment] Final Entropy from rust loop: ${finalEntropy.toFixed(4)}`);
    
    // 3. Check final entropy and locked token
    const finalRes = engine.executePuzzleInference("lm_head", thoughtVector);
    console.log(`[After Alignment] Max Token ID: ${finalRes.token}, Entropy: ${finalRes.entropy.toFixed(4)}`);
    
    engine.destroy();
}

runAlignmentTest().catch(console.error);
