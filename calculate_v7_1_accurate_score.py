import json
import re

file_path = "benchmarks/LongMemEval/official_v7_1_accuracy_report.json.jsonl"
total = 0
naive_hits = 0
accurate_hits = 0
deep_reads = 0

def exact_f1_score(prediction, ground_truth):
    prediction_tokens = re.findall(r'\w+', str(prediction).lower())
    ground_truth_tokens = re.findall(r'\w+', str(ground_truth).lower())
    
    if len(prediction_tokens) == 0 or len(ground_truth_tokens) == 0:
        return 0.0

    common_tokens = set(prediction_tokens).intersection(set(ground_truth_tokens))
    
    if len(common_tokens) == 0:
        return 0.0

    prec = len(common_tokens) / len(prediction_tokens)
    rec = len(common_tokens) / len(ground_truth_tokens)
    return 2 * (prec * rec) / (prec + rec)

try:
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                total += 1
                
                prediction = str(item.get("answer", "")).lower().strip()
                truth = str(item.get("ground_truth", "")).lower().strip()
                
                # 1. Naive Check (V7 legacy boolean check)
                is_naive_hit = truth in prediction
                if is_naive_hit:
                    naive_hits += 1
                
                # 2. Accurate Check (Handles concise answers correctly)
                is_accurate_hit = False
                
                # Condition A: Original naive logic
                if is_naive_hit:
                    is_accurate_hit = True
                # Condition B: The model answered concisely and its exact phrase is in the ground truth
                elif prediction != "" and prediction != "error" and "don't know" not in prediction and prediction in truth and len(prediction) >= 3:
                    is_accurate_hit = True
                # Condition C: F1 Score is above an acceptable threshold (e.g. 0.4 for QA overlap)
                else:
                    f1 = exact_f1_score(prediction, truth)
                    if f1 > 0.4 and "don't know" not in prediction:
                        is_accurate_hit = True
                
                if is_accurate_hit:
                    accurate_hits += 1
                    
                deep_reads += item.get("deep_reads", 0)

    naive_score = (naive_hits / total) * 100 if total > 0 else 0
    accurate_score = (accurate_hits / total) * 100 if total > 0 else 0
    
    print("=" * 50)
    print("V7.1 PUZZLE CORTEX (26B) - CURRENT STATE EVALUATION")
    print("=" * 50)
    print(f"Total Processed Examples : {total}")
    print(f"Total Deep Reads Triggered: {deep_reads}")
    print(f"Naive Substring Score    : {naive_score:.2f}% ({naive_hits}/{total})")
    print(f"Accurate Keyword/F1 Score: {accurate_score:.2f}% ({accurate_hits}/{total})")
    print("=" * 50)
    
except Exception as e:
    print(f"Error reading file: {e}")
