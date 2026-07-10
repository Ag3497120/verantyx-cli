"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const swe_bench_harness_1 = require("../../agents/swe-bench-harness");
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
async function main() {
    const args = process.argv.slice(2);
    let inputJsonl = '';
    let outputJsonl = '';
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--dataset') {
            inputJsonl = args[i + 1];
            i++;
        }
        else if (args[i] === '--output') {
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
    const harness = new swe_bench_harness_1.SWEBenchHarness(jgenPath, tokenizerPath, 4096);
    try {
        await harness.initialize();
        await harness.evaluate(inputJsonl, outputJsonl);
    }
    catch (err) {
        console.error("Evaluation failed:", err);
    }
    finally {
        harness.destroy();
    }
}
main();
//# sourceMappingURL=swe.js.map