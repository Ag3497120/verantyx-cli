import { SWEBenchHarness } from './src/verantyx/agents/swe-bench-harness';

async function main() {
    console.log("Starting SWE-bench Verified Evaluation (500 instances) with 0.5B model...");
    const harness = new SWEBenchHarness(
        "./qwen_0.5b_full.jgen",
        "./tokenizer.json",
        1024
    );
    
    await harness.initialize();
    
    // Evaluate the downloaded 500 instances
    await harness.evaluate(
        "./swe_bench_verified.jsonl",
        "./predictions_verified_05b.jsonl"
    );
    
    harness.destroy();
    console.log("SWE-bench 0.5B Evaluation Completed successfully.");
}

main().catch(console.error);
