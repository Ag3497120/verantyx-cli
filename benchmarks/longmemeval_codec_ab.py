"""
longmemeval_codec_ab.py — Phase 5: 証拠のテキスト注入 vs Write コーデック A/B
=============================================================================

LongMemEval の oracle 証拠を二経路で最終状態へ載せる:

  A) prompt   : 既存どおり Evidence テキストをプロンプトに載せて generate
  B) codec    : 証拠を dist→soft で Write (encode_soft) し、短い digest+質問で generate

指標はコーデック計画用に分離:
  - QA containment (ヒューリスティック、公式 GPT-4o ではない)
  - Soft 介入後の隠れ状態と証拠 encode のコサイン (codec path のみ)

グローバル永遠記憶は汚さない。任意で一時 CortexMemory ノードに
codec_label / codec_dir を載せるデモも可能 (--stamp-memory)。

例:
  python3 benchmarks/longmemeval_codec_ab.py --max-items 10
  python3 benchmarks/longmemeval_codec_ab.py --split oracle --max-items 30
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

from verantyx_mind import (
    RustBrain, JGenDict, DEFAULT_MODEL, TOKENIZER, HIDDEN,
    embed_text, CortexMemory, AxisAnchors, translate_vector,
)
from verantyx_council import (
    dist_from_vector, dist_to_soft_numpy, polish_answer, resolve_tokens,
)
from benchmarks.longmemeval_verantyx import (
    DATA, _build_index, _containment_correct,
)
from benchmarks.scoring import wilson_ci, percentile


def _ask_prompt(brain, tok, question, evidence, max_new=128):
    sys_p = (
        "Answer using ONLY the evidence below. "
        "If the evidence is insufficient, say you don't know. Be concise."
    )
    prompt = (
        f"<|im_start|>system\n{sys_p}<|im_end|>\n"
        f"<|im_start|>user\nEvidence:\n{evidence}\n\nQuestion: {question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    ids = tok.encode(prompt, add_special_tokens=False)
    if len(ids) > 2800:
        ids = ids[:800] + ids[-2000:]
    out = brain.generate(ids, resolve_tokens(max_new, small=True))
    return polish_answer(tok.decode(out, skip_special_tokens=True).strip())


def _ask_codec(brain, dictionary, tok, sem, embed_rows, question, evidence, max_new=128):
    """Write evidence into soft tokens; generate with digest scaffold (generate FFI
    cannot carry soft tokens, so B = soft prefill measurement + compact digest QA)."""
    clip = evidence if len(evidence) <= 1200 else evidence[:1200]
    e_prompt = (
        f"<|im_start|>user\nRemember this evidence:\n{clip}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    e_ids = tok.encode(e_prompt, add_special_tokens=False)
    if len(e_ids) > 2000:
        e_ids = e_ids[:2000]
    z_e = brain.encode(e_ids)
    dist = dist_from_vector(dictionary, tok, z_e, sem, top_k=48)
    soft = dist_to_soft_numpy(dist, tok, embed_rows)
    soft2 = dictionary.to_embedding(z_e, mask=sem)
    softs = np.stack([soft, soft2.astype(np.float32)], axis=0)

    hybrid = (
        f"<|im_start|>system\nUse latent evidence.<|im_end|>\n"
        f"<|im_start|>user\nQuestion: {question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    h_ids = tok.encode(hybrid, add_special_tokens=False)
    z_after = brain.encode_soft(softs, h_ids)
    cos = float(np.dot(z_e, z_after) /
                (np.linalg.norm(z_e) * np.linalg.norm(z_after) + 1e-8))
    z_emb = embed_text(brain, tok, clip)

    digest = " ".join(t for t, _ in dist[:12])
    gen_prompt = (
        f"<|im_start|>system\nAnswer from latent evidence digest. Be concise.<|im_end|>\n"
        f"<|im_start|>user\nDigest: {digest}\nQuestion: {question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    g_ids = tok.encode(gen_prompt, add_special_tokens=False)
    out = brain.generate(g_ids, resolve_tokens(max_new, small=True))
    answer = polish_answer(tok.decode(out, skip_special_tokens=True).strip())
    return answer, cos, z_after, z_emb


def run(args):
    path = DATA[args.split]
    if not os.path.isfile(path):
        raise SystemExit(f"dataset missing: {path}")
    data = json.load(open(path, encoding="utf-8"))
    if args.max_items and args.max_items > 0:
        data = data[: args.max_items]

    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    dictionary = JGenDict(DEFAULT_MODEL)
    hidden = dictionary.hidden or HIDDEN
    brain = RustBrain(DEFAULT_MODEL, hidden=hidden)
    sem = dictionary.semantic_mask(tok)
    embed_rows = np.asarray(dictionary._embed_f16, dtype=np.float32)

    memory = None
    if args.stamp_memory:
        memory = CortexMemory(axes=AxisAnchors())

    out_dir = args.out or os.path.join(
        ROOT, "benchmarks/results", f"codec_ab_{args.split}_{len(data)}")
    os.makedirs(out_dir, exist_ok=True)

    details = []
    stats = {
        "prompt": {"correct": 0, "n": 0, "times": []},
        "codec": {"correct": 0, "n": 0, "times": [], "cosines": []},
    }

    try:
        for i, item in enumerate(data):
            qid = item["question_id"]
            q = item["question"]
            gold = item.get("answer", "")
            qtype = item.get("question_type") or "?"

            mode = "oracle" if args.split == "oracle" else "retrieval"
            idx = _build_index(item, brain, tok, mode)
            if args.split == "oracle":
                evidence = "\n\n".join(r["text"][:800] for r in idx.rows[:3])
            else:
                hits = idx.search(q, topk=args.topk)
                evidence = "\n\n".join(r["text"][:800] for _, r in hits)

            t0 = time.time()
            ans_a = _ask_prompt(brain, tok, q, evidence)
            ta = time.time() - t0
            ok_a = _containment_correct(ans_a, gold, qtype, qid)
            stats["prompt"]["n"] += 1
            stats["prompt"]["correct"] += int(ok_a)
            stats["prompt"]["times"].append(ta)

            t0 = time.time()
            ans_b, cos, z_after, z_emb = _ask_codec(
                brain, dictionary, tok, sem, embed_rows, q, evidence)
            tb = time.time() - t0
            ok_b = _containment_correct(ans_b, gold, qtype, qid)
            stats["codec"]["n"] += 1
            stats["codec"]["correct"] += int(ok_b)
            stats["codec"]["times"].append(tb)
            stats["codec"]["cosines"].append(cos)

            if memory is not None:
                memory.add(
                    z_emb, evidence[:200],
                    concepts=translate_vector(dictionary, tok, z_emb)[:6],
                    kind="fact", quiet=True,
                    codec_label=f"evidence:{qid}", codec_dir=z_after)

            details.append({
                "question_id": qid,
                "question_type": qtype,
                "question": q,
                "gold": gold,
                "prompt_answer": ans_a,
                "prompt_correct": ok_a,
                "prompt_s": ta,
                "codec_answer": ans_b,
                "codec_correct": ok_b,
                "codec_s": tb,
                "codec_write_cosine": cos,
            })
            print(f"  [{i+1}/{len(data)}] {qid} "
                  f"A={'Y' if ok_a else 'n'} B={'Y' if ok_b else 'n'} "
                  f"cos={cos:.3f}")
    finally:
        brain.close()

    def pack(side):
        s = stats[side]
        n, c = s["n"], s["correct"]
        out = {
            "n": n,
            "correct": c,
            "accuracy": c / max(1, n),
            "wilson95": wilson_ci(c, n),
            "p50_s": percentile(s["times"], 50),
            "p95_s": percentile(s["times"], 95),
        }
        if side == "codec" and s["cosines"]:
            out["mean_write_cosine"] = float(np.mean(s["cosines"]))
        return out

    summary = {
        "phase": 5,
        "split": args.split,
        "claim_boundary": (
            "A/B compares evidence delivery (full prompt text vs Write-codec soft+digest). "
            "Not a LongMemEval leaderboard claim; grading is containment heuristic. "
            "Separate from Phase 1–4 reconstruction metrics."
        ),
        "prompt": pack("prompt"),
        "codec": pack("codec"),
        "delta_accuracy_codec_minus_prompt": (
            pack("codec")["accuracy"] - pack("prompt")["accuracy"]
        ),
    }

    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(out_dir, "detail.jsonl"), "w", encoding="utf-8") as f:
        for rec in details:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    report = [
        "# LongMemEval Codec A/B (Phase 5)",
        "",
        summary["claim_boundary"],
        "",
        "| path | accuracy | Wilson 95% | p50 s |",
        "|---|---:|---|---:|",
        f"| prompt (A) | {summary['prompt']['accuracy']*100:.1f}% | "
        f"{summary['prompt']['wilson95']} | {summary['prompt']['p50_s']:.2f} |",
        f"| codec Write (B) | {summary['codec']['accuracy']*100:.1f}% | "
        f"{summary['codec']['wilson95']} | {summary['codec']['p50_s']:.2f} |",
        "",
        f"- Δ (codec − prompt): **{summary['delta_accuracy_codec_minus_prompt']*100:+.1f}pt**",
        f"- mean Write cosine (B): {summary['codec'].get('mean_write_cosine')}",
        "",
        "```bash",
        f"python3 benchmarks/longmemeval_codec_ab.py --split {args.split} "
        f"--max-items {args.max_items} --out {out_dir}",
        "```",
        "",
    ]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"[ab] prompt={summary['prompt']['accuracy']*100:.1f}% "
          f"codec={summary['codec']['accuracy']*100:.1f}% "
          f"Δ={summary['delta_accuracy_codec_minus_prompt']*100:+.1f}pt")
    print(f"[ab] wrote {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["oracle", "s", "m"], default="oracle")
    ap.add_argument("--max-items", type=int, default=10)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--stamp-memory", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
