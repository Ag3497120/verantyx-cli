import json
import os
import glob

def calculate_score(path):
    if not os.path.exists(path): return "Not found"
    count = 0
    success = 0
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                try:
                    j = json.loads(line)
                    count += 1
                    if j.get("success"): success += 1
                except:
                    pass
    if count == 0: return "0 / 0 (0.00%)"
    return f"{success} / {count} ({(success/count)*100:.2f}%)"

files = [
    "pure_cpu_test_kanjishift.jsonl",
    "pure_cpu_test_w_0.8_0.2.jsonl",
    "pure_cpu_test_w_0.9_0.5.jsonl",
    "pure_cpu_test_w_1.0_0.7.jsonl",
]

print("--- Current Benchmark Progress ---")
for f in files:
    val = calculate_score(f"benchmarks/LongMemEval/{f}")
    print(f"- {f}: {val}")
