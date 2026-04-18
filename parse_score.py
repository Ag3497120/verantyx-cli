import json

file_path = "benchmarks/LongMemEval/official_v7_1_accuracy_report.json.jsonl"
total = 0
hits = 0
deep_reads = 0

try:
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                total += 1
                if item["success"]:
                    hits += 1
                deep_reads += item.get("deep_reads", 0)

    score = (hits / total) * 100 if total > 0 else 0
    print(f"Current Checkpoint Score:")
    print(f"Processed: {total}")
    print(f"Hits: {hits}")
    print(f"Accuracy: {score:.2f}%")
    print(f"Total Deep Reads Fired: {deep_reads}")
except Exception as e:
    print(f"No checkpoint file found or error: {e}")
