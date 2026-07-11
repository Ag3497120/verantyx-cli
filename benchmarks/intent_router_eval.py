#!/usr/bin/env python3
"""
intent_router_eval.py — 入口ルーティング (intent_router.route) の分類精度評価
================================================================================
task/chat の2値分類として、正解率・precision/recall/F1・混同行列・
どの経路 (reflex/hard/anchor/router) が採用されたかの内訳を出す。

使い方:
  python benchmarks/intent_router_eval.py
  python benchmarks/intent_router_eval.py --dataset benchmarks/datasets/intent_routing.jsonl
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load_dataset(path):
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def main():
    ap = argparse.ArgumentParser(description="intent_router 分類精度評価")
    ap.add_argument("--dataset", default=os.path.join(
        ROOT, "benchmarks/datasets/intent_routing.jsonl"))
    ap.add_argument("--out", default=os.path.join(
        ROOT, "benchmarks/results/intent_router_eval.json"))
    ap.add_argument("--no-reflex", action="store_true",
                    help="反射弓を使わず素の0.5B分類だけを評価 (再現性重視)")
    a = ap.parse_args()

    items = load_dataset(a.dataset)
    print(f"[intent-eval] {len(items)} 件を評価します")

    from transformers import AutoTokenizer
    from verantyx_mind import DEFAULT_MODEL, TOKENIZER, RustBrain, JGenDict, can_learn_from
    from intent_router import route

    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(DEFAULT_MODEL)
    if not can_learn_from(brain):
        print("[intent-eval] 警告: ルーターがベクトル介入不可 (外部APIモデル?)。"
              "0.5B分類は動作しません")
    dictionary = JGenDict(DEFAULT_MODEL)
    reflex = None
    if not a.no_reflex:
        from router_reflex import RouterReflex
        reflex = RouterReflex()

    rows = []
    tp = fp = tn = fn = 0  # positive = 'task'
    source_counts = {}
    try:
        for it in items:
            d = route(it["text"], brain, tok, reflex=reflex, memory_enabled=reflex is not None,
                      dictionary=dictionary)
            got = d["intent"]
            expect = it["expect"]
            correct = got == expect
            source_counts[d["source"]] = source_counts.get(d["source"], 0) + 1
            if expect == "task" and got == "task":
                tp += 1
            elif expect == "chat" and got == "task":
                fp += 1
            elif expect == "chat" and got == "chat":
                tn += 1
            else:
                fn += 1
            rows.append({"id": it["id"], "text": it["text"], "expect": expect,
                         "got": got, "correct": correct, "source": d["source"],
                         "detail": d.get("detail", "")})
            mark = "OK" if correct else "NG"
            print(f"  {mark} expect={expect:4} got={got:4} ←{d['source']:7} | {it['text'][:40]}")
    finally:
        brain.close()

    n = len(rows)
    acc = sum(r["correct"] for r in rows) / max(n, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    summary = {
        "n": n, "accuracy": round(acc, 4),
        "task_precision": round(precision, 4), "task_recall": round(recall, 4),
        "task_f1": round(f1, 4),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "source_counts": source_counts,
    }
    print("\n[intent-eval] ── 集計 ──")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"\n[intent-eval] 結果を保存: {a.out}")


if __name__ == "__main__":
    main()
