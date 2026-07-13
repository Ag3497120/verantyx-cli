"""
codec_lexicon_gate.py — Phase 2 ゲートの薄いラッパ

本体は concept_lexicon.py。互換のためこのエントリを残す。

  python3 benchmarks/codec_lexicon_gate.py --train --gate 0.70
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from concept_lexicon import (  # noqa: E402
    DEFAULT_CORPUS, DEFAULT_GATE_THRESHOLD, ConceptLexicon,
    load_propositions, write_read_reproduce,
)
from verantyx_mind import RustBrain, DEFAULT_MODEL, TOKENIZER, HIDDEN  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Phase 2 concept lexicon gate (wrapper)")
    ap.add_argument("--dataset", default=DEFAULT_CORPUS)
    ap.add_argument("--max-items", type=int, default=0)
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--gate", type=float, default=DEFAULT_GATE_THRESHOLD)
    ap.add_argument("--require-gate", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from transformers import AutoTokenizer
    import json

    rows = load_propositions(args.dataset)
    if args.max_items and args.max_items > 0:
        rows = rows[: args.max_items]

    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(DEFAULT_MODEL, hidden=HIDDEN)
    try:
        lex = ConceptLexicon()
        if args.train or not lex.available:
            lex = ConceptLexicon.build(brain, tok, rows)
        gate = write_read_reproduce(lex, rows)
        gate["threshold"] = args.gate
        gate["pass"] = gate["rate"] >= args.gate
        print(
            f"[codec-p2] reproduce={gate['rate']*100:.1f}% "
            f"({gate['correct']}/{gate['n']}) "
            f"gate={'PASS' if gate['pass'] else 'FAIL'}"
        )
        out_dir = args.out or os.path.join(ROOT, "benchmarks/results/codec_p2_lexicon")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in gate.items() if k != "detail"}, f, indent=2)
            f.write("\n")
        if args.require_gate and not gate["pass"]:
            raise SystemExit(2)
    finally:
        brain.close()


if __name__ == "__main__":
    main()
