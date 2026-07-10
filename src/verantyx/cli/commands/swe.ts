import { SWEBenchHarness } from '../../agents/swe-bench-harness';
import * as path from 'path';
import * as fs from 'fs';

async function main() {
    const args = process.argv.slice(2);
    let inputJsonl = '';
    let outputJsonl = '';

    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--dataset') {
            inputJsonl = args[i + 1];
            i++;
        } else if (args[i] === '--output') {
            outputJsonl = args[i + 1];
            i++;
        }
    }

    if (!inputJsonl || !outputJsonl) {
        console.error("Usage: npx tsx swe.ts --dataset <input.jsonl> --output <output.jsonl>");
        process.exit(1);
    }

    // Default to the Qwen 9B model we have in workspace
    const rootDir = path.resolve(__dirname, '../../../..');
    const jgenPath = path.resolve(rootDir, 'qwen_9b_full.jgen');
    const tokenizerPath = path.resolve(rootDir, 'tokenizer.json');
    
    if (!fs.existsSync(jgenPath)) {
        console.error(`Error: Model not found at ${jgenPath}.`);
        process.exit(1);
    }

    console.log(`=== SWE-bench Evaluation Harness ===`);
    console.log(`Model: ${jgenPath}`);
    console.log(`Dataset: ${inputJsonl}`);
    console.log(`Output: ${outputJsonl}`);
    
    const harness = new SWEBenchHarness(jgenPath, tokenizerPath, 4096);
    
    try {
        await harness.initialize();
        await harness.evaluate(inputJsonl, outputJsonl);
    } catch (err) {
        console.error("Evaluation failed:", err);
    } finally {
        harness.destroy();
    }
}

main();
