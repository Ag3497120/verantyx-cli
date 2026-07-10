import { SWEBenchHarness } from './src/verantyx/agents/swe-bench-harness';

async function main() {
    console.log("Starting SWE-bench Verified Evaluation (500 instances)...");
    const harness = new SWEBenchHarness(
        "./qwen_9b_full.jgen",
        "./tokenizer.json",
        4096
    );
    
    await harness.initialize();
    
    // Evaluate the downloaded 500 instances
    await harness.evaluate(
        "./swe_bench_verified.jsonl",
        "./predictions_verified.jsonl"
    );
    
    harness.destroy();
    console.log("SWE-bench Verified Evaluation Completed successfully.");
}

main().catch(console.error);
