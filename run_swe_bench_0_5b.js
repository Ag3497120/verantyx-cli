"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const swe_bench_harness_0_5b_1 = require("./src/verantyx/agents/swe-bench-harness-0-5b");
async function main() {
    console.log("Starting SWE-bench Verified Evaluation (500 instances)...");
    const harness = new swe_bench_harness_0_5b_1.SWEBenchHarness05B("./qwen_0.5b_full.jgen", "./tokenizer.json", 896);
    await harness.initialize();
    // Evaluate on the 500 verified instances
    await harness.evaluate("./swe_bench_verified.jsonl", "predictions_verified_0_5b.jsonl");
    harness.destroy();
    console.log("SWE-bench Verified Evaluation Completed successfully.");
}
main().catch(console.error);
//# sourceMappingURL=run_swe_bench_0_5b.js.map