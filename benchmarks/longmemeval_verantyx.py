"""
longmemeval_verantyx.py — LongMemEval × Verantyx 永遠の記憶 (主張可能な公式プロトコル寄り)
==============================================================================

公式 LongMemEval の流れに合わせる:
  1) oracle     : 証拠セッションのみ索引 → QA（検索上限）
  2) retrieval  : 全 haystack を session 粒度で索引 → top-k 検索 → QA
     指標: session Recall@k（answer_session_ids との一致）+ QA

埋め込みはルーター PromptEOL (embed_text)。検索は字句 bigram + コサインのハイブリッド。
グローバルな永遠の記憶ファイルは汚さない（質問ごとにメモリ上の索引）。

採点:
  - 既定は containment ヒューリスティック（公式 GPT-4o judge ではない）
  - --hyp-out に公式形式 (question_id, hypothesis) を書き、evaluate_qa.py に渡せる

例:
  python3 benchmarks/longmemeval_verantyx.py --split oracle --max-items 50
  python3 benchmarks/longmemeval_verantyx.py --split s --max-items 50 --topk 5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from verantyx_mind import (
    RustBrain, DEFAULT_MODEL, TOKENIZER, HIDDEN,
    embed_text,
)
from transformers import AutoTokenizer

from verantyx_council import polish_answer, resolve_tokens

DATA = {
    "oracle": os.path.join(
        ROOT, "cortex/benchmarks/LongMemEval/data/longmemeval_oracle.json"),
    "s": os.path.join(
        ROOT, "cortex/benchmarks/LongMemEval/data/longmemeval_s_cleaned.json"),
    "m": os.path.join(
        ROOT, "cortex/benchmarks/LongMemEval/data/longmemeval_m_cleaned.json"),
}


def _session_text(session) -> str:
    parts = []
    for turn in session:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role", "?")
        content = (turn.get("content") or "").strip()
        if content:
            parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _bigrams(s: str) -> set:
    s = re.sub(r"\s+", "", s.lower())
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _lex_overlap(a: str, b: str) -> float:
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / (len(A | B) + 1e-8)


class SessionIndex:
    """質問単位の一時索引（disk の CortexMemory は使わない）。"""

    def __init__(self, brain, tok):
        self.brain = brain
        self.tok = tok
        self.rows = []  # {session_id, date, text, vec}

    def add(self, session_id, date, session):
        text = _session_text(session)
        if not text.strip():
            return
        # 埋め込みは長すぎると切る
        clip = text if len(text) <= 1500 else text[:1500]
        vec = embed_text(self.brain, self.tok, clip).astype(np.float32)
        self.rows.append({
            "session_id": session_id,
            "date": date,
            "text": text,
            "vec": vec,
        })

    def search(self, query: str, topk: int = 5):
        if not self.rows:
            return []
        qv = embed_text(self.brain, self.tok, query).astype(np.float32)
        qn = qv / (np.linalg.norm(qv) + 1e-8)
        scored = []
        for r in self.rows:
            vn = r["vec"] / (np.linalg.norm(r["vec"]) + 1e-8)
            cos = float(vn @ qn)
            lex = _lex_overlap(query, r["text"][:2000])
            score = 0.7 * cos + 0.3 * lex
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return scored[:topk]


def _containment_correct(answer: str, gold: str, question_type: str, qid: str) -> bool:
    """ヒューリスティック。公式 GPT-4o judge ではないことをレポートに明記する。"""
    if gold is None:
        gold = ""
    a = (answer or "").strip().lower()
    g = str(gold).strip().lower()
    abstention = str(qid).endswith("_abs")
    if abstention:
        cues = ("don't know", "do not know", "unknown", "not sure",
                "no information", "cannot answer", "can't answer",
                "足りない", "わからない", "不明")
        return any(c in a for c in cues)
    if not g:
        return False
    if g in a:
        return True
    # 短い gold のトークン包含（3文字以上）
    toks = re.findall(r"[a-z0-9']+", g)
    long = [t for t in toks if len(t) >= 4]
    if long and all(t in a for t in long[:3]):
        return True
    return False


def _build_index(item, brain, tok, mode: str) -> SessionIndex:
    idx = SessionIndex(brain, tok)
    sessions = item.get("haystack_sessions") or []
    ids = item.get("haystack_session_ids") or [f"s{i}" for i in range(len(sessions))]
    dates = item.get("haystack_dates") or [None] * len(sessions)
    answer_ids = set(item.get("answer_session_ids") or [])

    for sid, date, sess in zip(ids, dates, sessions):
        if mode == "oracle" and answer_ids and sid not in answer_ids:
            continue
        idx.add(sid, date, sess)
    return idx


def _ask(brain, tok, question: str, evidence: str, max_new: int = 128) -> str:
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
    # コンテキスト過長ガード
    if len(ids) > 2800:
        ids = ids[:800] + ids[-2000:]
    out = brain.generate(ids, resolve_tokens(max_new, small=True))
    return polish_answer(tok.decode(out, skip_special_tokens=True).strip())


def _ask_codec_write(brain, tok, dictionary, sem, question: str, evidence: str,
                     max_new: int = 128) -> str:
    """A/B: 証拠をプロンプトに載せるだけでなく、soft Write で最終状態へ注入してから生成。

    コーデック計画 Phase 5 の接続実験。LongMemEval 公式スコアとは分離して報告する。
    """
    from verantyx_council import dist_from_vector, dist_to_soft_numpy

    clip = evidence if len(evidence) <= 1200 else evidence[:1200]
    # 証拠 → 隠れ → 語彙分布 → soft 仮想トークン
    z_ev = embed_text(brain, tok, clip)
    dist = dist_from_vector(dictionary, tok, z_ev, sem, top_k=48)
    soft = dist_to_soft_numpy(dist, tok, dictionary._embed_f16)

    sys_p = (
        "Answer using ONLY the injected evidence vector and the short evidence text. "
        "If insufficient, say you don't know. Be concise."
    )
    # プロンプトは短めにし、本体は soft 注入で運ぶ
    short_ev = evidence if len(evidence) <= 600 else evidence[:600]
    prompt = (
        f"<|im_start|>system\n{sys_p}<|im_end|>\n"
        f"<|im_start|>user\nEvidence (also injected as soft tokens):\n{short_ev}\n\n"
        f"Question: {question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    ids = tok.encode(prompt, add_special_tokens=False)
    if len(ids) > 2000:
        ids = ids[:500] + ids[-1500:]
    # soft 注入で最終隠れを証拠方向へ寄せてから生成
    _ = brain.encode_soft(soft[None, :], ids)
    out = brain.generate(ids, resolve_tokens(max_new, small=True))
    return polish_answer(tok.decode(out, skip_special_tokens=True).strip())


def run(args):
    path = DATA[args.split]
    data = json.load(open(path, encoding="utf-8"))
    if args.max_items and args.max_items > 0:
        data = data[: args.max_items]

    qa_modes = [m.strip() for m in (getattr(args, "qa_modes", None) or "prompt").split(",") if m.strip()]
    for m in qa_modes:
        if m not in ("prompt", "codec_write"):
            raise SystemExit(f"unknown qa mode: {m} (use prompt,codec_write)")

    print(f"[longmem] split={args.split} n={len(data)} topk={args.topk} "
          f"mode_index={'oracle' if args.split == 'oracle' else 'retrieval'} "
          f"qa_modes={qa_modes}")
    print(f"[longmem] loading router {DEFAULT_MODEL} ...")
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(DEFAULT_MODEL, hidden=HIDDEN)
    dictionary = None
    sem = None
    if "codec_write" in qa_modes:
        from verantyx_mind import JGenDict
        dictionary = JGenDict(DEFAULT_MODEL)
        sem = dictionary.semantic_mask(tok)

    out_dir = args.out or os.path.join(
        ROOT, "benchmarks/results", f"longmemeval_{args.split}_{len(data)}")
    os.makedirs(out_dir, exist_ok=True)
    detail_path = os.path.join(out_dir, "detail.jsonl")
    hyp_path = os.path.join(out_dir, "hypothesis.jsonl")

    # 既存チェックポイント (qid+qa_mode)
    done = set()
    if os.path.isfile(detail_path) and not args.fresh:
        for line in open(detail_path, encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                done.add((row["question_id"], row.get("qa_mode", "prompt")))
        print(f"[longmem] resume {len(done)} (qid,mode) done")

    recalls = []
    corrects_by_mode = {m: [] for m in qa_modes}
    by_type = defaultdict(lambda: {
        "n": 0, "correct": 0, "recall": [],
        "by_mode": defaultdict(lambda: {"n": 0, "correct": 0}),
    })

    t0 = time.time()
    with open(detail_path, "a", encoding="utf-8") as df, \
            open(hyp_path, "a", encoding="utf-8") as hf:
        for i, item in enumerate(data):
            qid = item["question_id"]
            q = item["question"]
            gold = item.get("answer", "")
            qtype = item.get("question_type") or "?"
            answer_ids = set(item.get("answer_session_ids") or [])
            abstention = qid.endswith("_abs")

            # skip only if ALL modes done
            if all((qid, m) in done for m in qa_modes):
                for m in qa_modes:
                    # cannot recover counts easily without re-read; skip fresh metrics
                    pass
                continue

            index_mode = "oracle" if args.split == "oracle" else "retrieval"
            idx = _build_index(item, brain, tok, index_mode)
            hits = idx.search(q, topk=args.topk)
            hit_ids = [h[1]["session_id"] for h in hits]

            recall = None
            if answer_ids and not abstention:
                recall = len(answer_ids & set(hit_ids)) / len(answer_ids)
                recalls.append(recall)

            evidence = "\n\n---\n\n".join(
                f"[{h[1]['session_id']} | {h[1].get('date')}]\n{h[1]['text'][:2000]}"
                for h in hits
            ) or "(no evidence)"

            bt = by_type[qtype]
            bt["n"] += 1
            if recall is not None:
                bt["recall"].append(recall)

            for mode in qa_modes:
                if (qid, mode) in done:
                    continue
                if mode == "codec_write":
                    ans = _ask_codec_write(
                        brain, tok, dictionary, sem, q, evidence, max_new=args.max_new)
                else:
                    ans = _ask(brain, tok, q, evidence, max_new=args.max_new)
                ok = _containment_correct(ans, gold, qtype, qid)
                corrects_by_mode[mode].append(int(ok))
                if mode == qa_modes[0]:
                    bt["correct"] += int(ok)
                bt["by_mode"][mode]["n"] += 1
                bt["by_mode"][mode]["correct"] += int(ok)

                row = {
                    "question_id": qid,
                    "question_type": qtype,
                    "question": q,
                    "gold": gold,
                    "hypothesis": ans,
                    "correct": ok,
                    "recall_at_k": recall,
                    "retrieved_session_ids": hit_ids,
                    "answer_session_ids": list(answer_ids),
                    "n_indexed": len(idx.rows),
                    "split": args.split,
                    "topk": args.topk,
                    "qa_mode": mode,
                    "grader": "containment_heuristic",
                }
                df.write(json.dumps(row, ensure_ascii=False) + "\n")
                df.flush()
                if mode == qa_modes[0]:
                    hf.write(json.dumps({
                        "question_id": qid,
                        "hypothesis": ans,
                    }, ensure_ascii=False) + "\n")
                    hf.flush()

            if (i + 1) % 5 == 0 or i == 0:
                parts = []
                for m, xs in corrects_by_mode.items():
                    if xs:
                        parts.append(f"{m}={sum(xs)/len(xs)*100:.1f}%")
                rmean = (sum(recalls) / len(recalls)) if recalls else None
                print(f"  [{i+1}/{len(data)}] {' '.join(parts) or 'n/a'} "
                      f"recall@k={None if rmean is None else round(rmean*100,1)}% "
                      f"qid={qid}")

    brain.close()
    elapsed = time.time() - t0
    primary = qa_modes[0]
    corrects = corrects_by_mode[primary]
    n = len(corrects)
    by_mode_summary = {}
    for m, xs in corrects_by_mode.items():
        nn = len(xs)
        by_mode_summary[m] = {
            "n": nn,
            "accuracy_containment": sum(xs) / nn if nn else 0.0,
            "correct": sum(xs),
        }
    summary = {
        "split": args.split,
        "n": n,
        "qa_modes": qa_modes,
        "accuracy_containment": sum(corrects) / n if n else 0.0,
        "correct": sum(corrects),
        "by_qa_mode": by_mode_summary,
        "recall_at_k_mean": (sum(recalls) / len(recalls)) if recalls else None,
        "recall_n": len(recalls),
        "topk": args.topk,
        "speaker": "qwen2.5-0.5B-router",
        "retriever": "promptEOL_cosine+bigram",
        "granularity": "session",
        "grader": "containment_heuristic (NOT official GPT-4o judge)",
        "elapsed_s": round(elapsed, 1),
        "by_type": {
            t: {
                "n": v["n"],
                "accuracy": v["correct"] / v["n"] if v["n"] else 0.0,
                "recall_at_k_mean": (sum(v["recall"]) / len(v["recall"]))
                if v["recall"] else None,
                "by_mode": {
                    m: {
                        "n": mv["n"],
                        "accuracy": mv["correct"] / mv["n"] if mv["n"] else 0.0,
                    }
                    for m, mv in v["by_mode"].items()
                },
            }
            for t, v in by_type.items()
        },
        "claim_notes": [
            "Retrieval metric (session Recall@k) is comparable to LongMemEval retrieval eval.",
            "QA accuracy here uses string containment, not the official GPT-4o evaluator.",
            "To claim official QA numbers, run src/evaluation/evaluate_qa.py gpt-4o hypothesis.jsonl <ref.json>",
            "Global CortexMemory store was not modified; per-question in-memory index only.",
            "codec_write is a Phase-5 A/B (soft Write inject); not an official LongMemEval protocol.",
            "Do not mix codec reconstruction rates with LongMemEval QA scores.",
        ],
        "data_file": path,
        "out_dir": out_dir,
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    rmean = summary["recall_at_k_mean"]
    rmean_s = "n/a" if rmean is None else f"{rmean * 100:.1f}%"
    lines = [
        f"# LongMemEval × Verantyx ({args.split})",
        "",
        f"- n={n}  topk={args.topk}  speaker=0.5B router  qa_modes={qa_modes}",
        f"- session Recall@{args.topk}: {rmean_s}",
        f"- QA primary ({primary}, containment): **{summary['accuracy_containment']*100:.1f}%** "
        f"({summary['correct']}/{n})",
    ]
    if len(qa_modes) > 1:
        lines.append("- A/B by qa_mode:")
        for m, v in by_mode_summary.items():
            lines.append(
                f"  - {m}: {v['accuracy_containment']*100:.1f}% ({v['correct']}/{v['n']})"
            )
    lines += [
        f"- grader: **not** official GPT-4o (see claim_notes)",
        "",
        "## by question_type",
        "",
        "| type | n | QA | Recall@k |",
        "|------|---|----|----------|",
    ]
    for t, v in sorted(summary["by_type"].items()):
        r = v["recall_at_k_mean"]
        lines.append(
            f"| {t} | {v['n']} | {v['accuracy']*100:.1f}% | "
            f"{'—' if r is None else f'{r*100:.1f}%'} |"
        )
    lines.extend([
        "",
        "## Claim boundary",
        "",
        "- OK to claim: session retrieval Recall@k under PromptEOL+bigram hybrid.",
        "- Not OK to claim as official LongMemEval QA score without GPT-4o judge.",
        "- codec_write A/B is codec integration research, not LongMemEval official.",
        "",
        f"hypothesis: `{hyp_path}`",
    ])
    report = "\n".join(lines) + "\n"
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["oracle", "s", "m"], default="oracle")
    ap.add_argument("--max-items", type=int, default=50,
                    help="0=全件。主張用はまず 50→拡大")
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--max-new", type=int, default=96)
    ap.add_argument("--out", default="")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument(
        "--qa-modes", default="prompt",
        help="comma list: prompt (baseline) and/or codec_write (Phase5 soft Write A/B)",
    )
    ap.add_argument(
        "--codec", action="store_true",
        help="shorthand for --qa-modes prompt,codec_write (Phase 5 A/B)",
    )
    args = ap.parse_args()
    if args.codec:
        modes = {m.strip() for m in (args.qa_modes or "prompt").split(",") if m.strip()}
        modes.update({"prompt", "codec_write"})
        args.qa_modes = ",".join(sorted(modes))
    if args.max_items is not None and args.max_items <= 0:
        args.max_items = None
    run(args)


if __name__ == "__main__":
    main()
