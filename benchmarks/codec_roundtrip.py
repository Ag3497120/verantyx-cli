"""
codec_roundtrip.py — Phase 1 最終層 Read/Write round-trip ベンチ
================================================================

既存 API のみで半コーデックを数値化する:
  Read  : text → encode → dist_from_vector → top-k 重なり / キーワード
  Write : proposition → dist → soft inject (encode_soft) → re-encode → cosine
  Baseline: 生プロンプトのみ vs soft 注入

出力: benchmarks/results/codec_roundtrip/ に summary.json / detail.jsonl / report.md

例:
  python3 benchmarks/codec_roundtrip.py --max-items 20
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from transformers import AutoTokenizer

from verantyx_mind import RustBrain, JGenDict, DEFAULT_MODEL, TOKENIZER, HIDDEN
from verantyx_codec import (
    write_soft, read_dist, encode_proposition, proposition_tokens,
    roundtrip_metrics, keyword_hit, top_strings, _cosine, load_propositions,
)
from benchmarks.scoring import wilson_ci, percentile


CLAIM = (
    "Phase 1 measures final-layer half-codec only "
    "(dist_from_vector / encode_soft). Forward path only — "
    "not lexicon_only Write→Read; not BABEL; not intermediate layers; "
    "not lossless reconstruction. See codec_suite dual gates."
)


def run_item(brain, dictionary, tok, sem, text):
    z_src, z_out, dist_src = write_soft(
        brain, tok, dictionary, text, sem=sem, top_k=32)
    dist_out = read_dist(dictionary, tok, z_out, sem, top_k=32)
    metrics = roundtrip_metrics(z_src, z_out, dist_src, dist_out, text)

    # Baseline: carrier alone (no soft)
    carrier = proposition_tokens(tok, "Continue.")
    z_base = brain.encode(carrier)
    base_cos = _cosine(z_src, z_base)
    soft_improves = metrics["cosine"] > base_cos

    # Raw Read of source
    read_kw = keyword_hit(text, top_strings(dist_src, 16))

    return {
        "round_trip_cosine": metrics["cosine"],
        "baseline_cosine": base_cos,
        "soft_improves": soft_improves,
        "topk_jaccard": metrics["topk_jaccard"],
        "write_keyword_hit": metrics["keyword_repro"],
        "read_keyword_hit": read_kw,
        "read_top_tokens": metrics["top_src"],
        "write_top_tokens": metrics["top_out"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(
        ROOT, "benchmarks/datasets/codec_propositions.jsonl"))
    ap.add_argument("--max-items", type=int, default=20)
    ap.add_argument("--out", default=os.path.join(
        ROOT, "benchmarks/results/codec_roundtrip"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    props = load_propositions(args.dataset)
    if args.max_items and args.max_items > 0:
        props = props[: args.max_items]
    os.makedirs(args.out, exist_ok=True)

    print(f"[codec-p1] n={len(props)} model={args.model}")
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    dictionary = JGenDict(args.model)
    hidden = dictionary.hidden or HIDDEN
    brain = RustBrain(args.model, hidden=hidden)
    sem = dictionary.semantic_mask(tok)

    details = []
    try:
        for i, row in enumerate(props):
            text = row["text"]
            t0 = time.time()
            m = run_item(brain, dictionary, tok, sem, text)
            rec = {
                "id": row.get("id", f"p1_{i:03d}"),
                "domain": row.get("domain", ""),
                "text": text,
                "elapsed_s": time.time() - t0,
                **m,
            }
            details.append(rec)
            print(f"  [{i+1}/{len(props)}] cos={rec['round_trip_cosine']:.3f} "
                  f"base={rec['baseline_cosine']:.3f} "
                  f"Wkw={int(rec['write_keyword_hit'])}  {text[:48]}")
    finally:
        brain.close()

    n = len(details)
    soft_better = sum(1 for d in details if d["soft_improves"])
    kw_ok = sum(1 for d in details if d["write_keyword_hit"])
    read_ok = sum(1 for d in details if d["read_keyword_hit"])
    summary = {
        "phase": 1,
        "n": n,
        "model": args.model,
        "hidden": hidden,
        "claim_boundary": CLAIM,
        "mean_round_trip_cosine": float(np.mean(
            [d["round_trip_cosine"] for d in details])) if details else 0.0,
        "mean_baseline_cosine": float(np.mean(
            [d["baseline_cosine"] for d in details])) if details else 0.0,
        "soft_improves_rate": soft_better / max(1, n),
        "mean_topk_jaccard": float(np.mean(
            [d["topk_jaccard"] for d in details])) if details else 0.0,
        "write_retention_rate": kw_ok / max(1, n),
        "read_signal_rate": read_ok / max(1, n),
        "write_retention_ci": list(wilson_ci(kw_ok, n)),
        "p50_elapsed_s": percentile([d["elapsed_s"] for d in details], 50),
        "p95_elapsed_s": percentile([d["elapsed_s"] for d in details], 95),
    }

    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(args.out, "detail.jsonl"), "w", encoding="utf-8") as f:
        for rec in details:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    report = [
        "# Codec Round-Trip Report (Phase 1)",
        "",
        CLAIM,
        "",
        f"- n = {n}",
        f"- mean round-trip cosine: **{summary['mean_round_trip_cosine']:.3f}**",
        f"- mean baseline cosine: **{summary['mean_baseline_cosine']:.3f}**",
        f"- soft improves over baseline: **{summary['soft_improves_rate']*100:.1f}%**",
        f"- Write keyword retention: **{summary['write_retention_rate']*100:.1f}%** "
        f"(Wilson {summary['write_retention_ci'][0]*100:.1f}–"
        f"{summary['write_retention_ci'][1]*100:.1f})",
        "",
        "```bash",
        f"python3 benchmarks/codec_roundtrip.py --max-items {args.max_items} "
        f"--out {args.out}",
        "```",
        "",
    ]
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"[codec-p1] RT cos={summary['mean_round_trip_cosine']:.3f} "
          f"retention={summary['write_retention_rate']*100:.1f}% → {args.out}")


if __name__ == "__main__":
    main()
