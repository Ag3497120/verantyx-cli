#!/usr/bin/env python3
"""
concept_lexicon_trainer.py — 命題コーデック辞書の学習
======================================================

benchmarks/datasets/codec_propositions.jsonl を PromptEOL 埋め込みし、
.verantyx_chrono/concept_lexicon.npz に保存する。

実行: python3 concept_lexicon_trainer.py [--max-items N]
"""

from __future__ import annotations

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from transformers import AutoTokenizer

from concept_lexicon import (
    build_lexicon_from_embeddings,
    encode_proposition,
    load_propositions,
    LEXICON_PATH,
)
from verantyx_mind import RustBrain, DEFAULT_MODEL, TOKENIZER


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus",
        default=os.path.join(ROOT, "benchmarks/datasets/codec_propositions.jsonl"),
    )
    ap.add_argument("--max-items", type=int, default=0)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--holdout-ratio", type=float, default=0.20)
    ap.add_argument("--holdout-seed", type=int, default=42)
    args = ap.parse_args()

    rows = load_propositions(args.corpus)
    if args.max_items and args.max_items > 0:
        rows = rows[: args.max_items]
    print(f"[Lexicon] {len(rows)} propositions from {args.corpus}")

    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(args.model)
    embs = []
    t0 = time.time()
    try:
        for i, row in enumerate(rows):
            e = encode_proposition(brain, tok, row["text"])
            embs.append(e)
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  [{i+1}/{len(rows)}] {row['text'][:60]}")
    finally:
        brain.close()

    import numpy as np

    lex, stats = build_lexicon_from_embeddings(
        rows,
        np.stack(embs),
        holdout_ratio=args.holdout_ratio,
        holdout_seed=args.holdout_seed,
    )
    print(f"\n[Lexicon] train_acc={stats['train_acc']*100:.1f}% "
          f"hold_acc={stats['hold_acc']*100:.1f}% "
          f"soft={stats.get('hold_acc_soft', 0)*100:.1f}% "
          f"domain={stats.get('hold_domain_acc', 0)*100:.1f}% "
          f"(n={stats['n']} train={stats['n_train']} hold={stats['n_hold']})")
    print(f"[Lexicon] saved {LEXICON_PATH} ({time.time()-t0:.1f}s)")
    print(f"[Lexicon] available={lex.available} size={lex.size}")


if __name__ == "__main__":
    main()
