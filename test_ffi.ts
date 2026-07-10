import { JCrossEngineDriver } from './src/verantyx/memory/ffi-driver';
import * as fs from 'fs';
import * as path from 'path';

async function run() {
    console.log("=== Verantyx Native Engine Boot Test ===");
    
    // Check if qwen_0.5b_full.jgen exists
    const jgenPath = '/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen';
    if (!fs.existsSync(jgenPath)) {
        console.error(`[Test] Error: ${jgenPath} not found.`);
        return;
    }

    try {
        const { initKoffi } = require('./src/verantyx/memory/ffi-driver');
        initKoffi(jgenPath);
        const driver = new JCrossEngineDriver(jgenPath);

        // Dummy vector simulating a Qwen 0.5B embedding (1024 hidden size)
        const dummyInput = new Float32Array(1024);
        dummyInput.fill(0.1);

        console.log("[Test] Executing SVD projection on layer: model.layers.0.mlp.gate_proj.weight");
        
        // Output len is typically intermediate_size (2816) for gate_proj
        const outputBuffer = driver.projectSubspace("model.layers.0.mlp.gate_proj.weight", dummyInput, 2816);
        
        console.log(`[Test] Projection successful! First 5 values: ${outputBuffer.slice(0, 5)}`);

        driver.destroy();
        console.log("=== Test Complete ===");
    } catch (e) {
        console.error("Test failed:", e);
    }
}

run();
