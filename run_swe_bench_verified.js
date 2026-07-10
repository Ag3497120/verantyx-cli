"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const swe_bench_harness_1 = require("./src/verantyx/agents/swe-bench-harness");
async function main() {
    console.log("Starting SWE-bench Verified Evaluation (500 instances)...");
    const harness = new swe_bench_harness_1.SWEBenchHarness("./qwen_9b_full.jgen", "./tokenizer.json", 4096);
    await harness.initialize();
    // Evaluate the downloaded 500 instances
    await harness.evaluate("./swe_bench_verified.jsonl", "./predictions_verified.jsonl");
    harness.destroy();
    console.log("SWE-bench Verified Evaluation Completed successfully.");
}
main().catch(console.error);
//# sourceMappingURL=run_swe_bench_verified.js.map