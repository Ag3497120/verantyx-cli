import { JCrossEngineDriver } from './src/verantyx/memory/ffi-driver';
import * as fs from 'fs';
import * as path from 'path';

async function run() {
    console.log("=== Verantyx E2E Pipeline Vector Generation ===");
    const jgenPath = path.resolve(__dirname, 'qwen_9b_full.jgen');
    const driver = new JCrossEngineDriver(jgenPath);

    // Using 3584 dimensions as Qwen-9B uses a hidden_size of 3584
    const realInput = new Float32Array(3584);
    for (let i = 0; i < 3584; i++) {
        realInput[i] = Math.sin(i * 0.01) * 0.5;
    }

    // Since we don't have up_proj generating exactly 3584 for this E2E test, we pass the realInput directly,
    // which simulates a vector successfully projected down into the 3584 manifold space by the JCross rust engine.
    fs.writeFileSync("intent_real.json", JSON.stringify({ vector: Array.from(realInput) }));
    console.log("[E2E] Simulated JCross output vector saved to intent_real.json (3584 dims).");

    driver.destroy();
}
run();
