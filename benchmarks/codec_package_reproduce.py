#!/usr/bin/env python3
"""
codec_package_reproduce.py — P3 one-command codec package reproduce
===================================================================

Runs: corpus load → (optional) train lexicon → lexicon_only gate → suite smoke.
Prints hold_acc from meta and dual-gate summary paths.

  python3 benchmarks/codec_package_reproduce.py --max-items 20
  python3 benchmarks/codec_package_reproduce.py --train --max-items 30
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "benchmarks/datasets/codec_propositions.jsonl")
META = os.path.join(ROOT, ".verantyx_chrono", "concept_lexicon.meta.json")
OUT = os.path.join(ROOT, "benchmarks/results/codec_package")


def main():
    ap = argparse.ArgumentParser(description="One-command codec package reproduce")
    ap.add_argument("--train", action="store_true", help="Retrain lexicon before suite")
    ap.add_argument("--max-items", type=int, default=20)
    ap.add_argument("--gate", type=float, default=0.70)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--skip-layers", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("JCROSS_GPU", env.get("JCROSS_GPU", "0"))

    if args.train:
        print("[package] training concept lexicon...")
        r = subprocess.run(
            [
                sys.executable, os.path.join(ROOT, "concept_lexicon_trainer.py"),
                "--corpus", CORPUS,
                "--holdout-ratio", "0.20",
                "--holdout-seed", "42",
            ],
            cwd=ROOT, env=env,
        )
        if r.returncode != 0:
            raise SystemExit(r.returncode)

    if os.path.exists(META):
        with open(META, encoding="utf-8") as f:
            meta = json.load(f)
        print(
            f"[package] lexicon meta: n={meta.get('n')} "
            f"hold_acc={meta.get('hold_acc', 0)*100:.1f}% "
            f"soft={meta.get('hold_acc_soft', 0)*100:.1f}% "
            f"domain={meta.get('hold_domain_acc', 0)*100:.1f}%"
        )
        with open(os.path.join(args.out, "lexicon_meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
            f.write("\n")
    else:
        print("[package] WARNING: no concept_lexicon.meta.json — run with --train")

    cmd = [
        sys.executable, os.path.join(ROOT, "benchmarks/codec_suite.py"),
        "--corpus", CORPUS,
        "--max-items", str(args.max_items),
        "--gate-threshold", str(args.gate),
        "--inject-ab",
        "--save-layer-routing",
        "--out", args.out,
    ]
    if args.skip_layers:
        cmd.append("--skip-layers")
    if args.train:
        cmd.append("--build-lexicon")

    print("[package] running codec_suite...")
    r = subprocess.run(cmd, cwd=ROOT, env=env)
    summary_path = os.path.join(args.out, "summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)
        gates = summary.get("gates") or {}
        lo = gates.get("lexicon_only") or {}
        fr = gates.get("forward_roundtrip") or {}
        print("[package] lexicon_only:", json.dumps(lo.get("write_read_reproduce"), ensure_ascii=False))
        if fr.get("write_forward_read"):
            print("[package] forward write→read:",
                  f"{fr['write_forward_read'].get('rate', 0)*100:.1f}%")
        print(f"[package] report: {os.path.join(args.out, 'report.md')}")
    raise SystemExit(r.returncode)


if __name__ == "__main__":
    main()
