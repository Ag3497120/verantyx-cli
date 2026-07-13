#!/usr/bin/env python3
"""
smoke_router_classify.py — Phase 1 分類専用ルーターのスモーク
==============================================================================
数件のプロンプトを classify し、label / confidence / ambiguous / source を表示する。
回答生成は行わない (ClassifyOnlyBrain で generate 禁止を確認)。

使い方:
  python scripts/smoke_router_classify.py
  python scripts/smoke_router_classify.py --no-model   # キーワード安全網のみ
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SAMPLES = [
    "appleのメモにアクセスして中身を見て",
    "火星の直径は？",
    "今日の東京の天気は？",
    "README.md を編集して",
    "ベクトル通信の利点を議論して",
    "最新のニュースを検索して",
    "1+1は何ですか",
]


def smoke_no_model():
    from intent_router import hard_task_hint
    print("=== hard hints only (no model) ===")
    for s in SAMPLES:
        print(f"  {'task' if hard_task_hint(s) else 'chat?':5} | {s}")


def smoke_generate_guard(clf_brain):
    print("\n=== generate() guard ===")
    try:
        clf_brain.generate([1, 2, 3], 8)
        print("  FAIL: generate() should have raised")
        return False
    except RuntimeError as e:
        print(f"  OK: blocked — {e}")
        return True


def smoke_classify():
    from transformers import AutoTokenizer
    from verantyx_mind import DEFAULT_MODEL, TOKENIZER, RustBrain, JGenDict, AxisAnchors
    from router_classifier import classify, wrap_for_classify

    print("=== loading 0.5B classify brain ===")
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(DEFAULT_MODEL)
    dictionary = JGenDict(DEFAULT_MODEL)
    axes = AxisAnchors()
    clf = wrap_for_classify(brain)

    ok_guard = smoke_generate_guard(clf)
    print("\n=== classify samples ===")
    print(f"{'label':7} {'conf':>5} {'amb':>3} {'source':12} | text")
    try:
        for s in SAMPLES:
            r = classify(s, clf, tok, dictionary, axes=axes if axes.available else None,
                         memory_enabled=False)
            amb = "Y" if r.ambiguous else "n"
            print(f"  {r.label:7} {r.confidence:5.2f} {amb:>3} {r.source:12} | {s[:48]}")
            if r.detail:
                print(f"           detail: {r.detail[:90]}")
    finally:
        brain.close()
    return ok_guard


def main():
    ap = argparse.ArgumentParser(description="Phase 1 router classifier smoke")
    ap.add_argument("--no-model", action="store_true",
                    help="キーワード安全網のみ (モデル不要)")
    a = ap.parse_args()
    if a.no_model:
        smoke_no_model()
        return 0
    ok = smoke_classify()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
