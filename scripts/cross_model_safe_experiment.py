#!/usr/bin/env python3
"""異種モデル連携の安全実験 (0.5B council ↔ Ollama gemma)

安全制約 (必須):
  - agent / shell / computer_control / ファイル書き込みツールは一切呼ばない
  - Ollama にはチャット完了のみ (tools なし)
  - system で破壊・ファイル操作・コマンド実行を明示禁止
  - 応答に危険パターンがあればログ上 redact
  - memorize=False (永遠の記憶へ書かない)
  - escalation は bridge のみ (HF sage は載せない)

使い方:
  python3 scripts/cross_model_safe_experiment.py \\
    --bridge ollama:huihui_ai/gemma-4-abliterated:e4b
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

# repo root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 破壊・実行を誘発しうる出力をログから隠す
_DANGER = re.compile(
    r"(?i)\b(rm\s+-rf|sudo\s+|mkfs|dd\s+if=|/dev/sd|"
    r"del\s+/[fq]|format\s+[a-z]:|Remove-Item|shutil\.rmtree|"
    r"os\.remove|unlink\(|rmdir\(|drop\s+table|curl\s+[^\n]*\|\s*sh)\b"
)

SAFE_SYS_EXTRA = (
    " SAFETY LOCK: You are a text-only answerer. "
    "Never suggest, output, or roleplay shell commands, file deletion, "
    "system modification, downloads, or code that changes the filesystem. "
    "If asked to destroy or modify files, refuse in one short sentence. "
    "Answer only the factual/reasoning question."
)

# 実験プロンプトは無害な推論のみ (ツール誘導なし)
PROMPTS = [
    "What is 17 + 28? Reply with the number only.",
    "In one word: capital of France?",
    "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost in cents? Number only.",
]


def _redact(text: str) -> str:
    if not text:
        return text
    if _DANGER.search(text):
        return "[REDACTED: dangerous pattern in model output]"
    return text


def _wrap_bridge_safe(participant):
    """OllamaParticipant の chat を安全 system で包む。tools は元々無し。"""
    orig_chat = participant._chat

    def safe_chat(messages, max_tokens):
        msgs = list(messages)
        if msgs and msgs[0].get("role") == "system":
            msgs[0] = {
                "role": "system",
                "content": (msgs[0].get("content") or "") + SAFE_SYS_EXTRA,
            }
        else:
            msgs = [{"role": "system", "content": SAFE_SYS_EXTRA.strip()}] + msgs
        # ユーザー文もツール誘導を拒否するメタを付与しない (質問は既に安全)
        out = orig_chat(msgs, max_tokens)
        return _redact(out)

    participant._chat = safe_chat
    participant.name = participant.name + "+safe"
    return participant


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--bridge",
        default="ollama:huihui_ai/gemma-4-abliterated:e4b",
        help="bridge spec",
    )
    ap.add_argument("--rounds", default="2", help="council rounds (int or auto)")
    ap.add_argument("--out", default="", help="jsonl result path")
    args = ap.parse_args()

    # 絶対に agent 系を import しない
    forbidden = ("verantyx_agent", "computer_control", "subprocess")
    print("[SAFE] no-agent experiment; bridge chat only")
    print(f"[SAFE] bridge={args.bridge}")

    from verantyx_council import Council
    from verantyx_bridges import make_participant

    # escalation off: sage/worker を呼ばせない。bridge は手動 add。
    council = Council(escalation=False, quiet=False)
    council.memory.enabled = False  # 記憶も書かない

    raw = make_participant(args.bridge)
    peer = _wrap_bridge_safe(raw)
    council._bridges.append(peer)
    council._rebuild_participants()
    print(f"[SAFE] participants: {[n for n, _ in council._participants]}")

    rounds = args.rounds
    if rounds not in ("auto",):
        try:
            rounds = int(rounds)
        except ValueError:
            rounds = 2

    out_path = args.out or os.path.join(
        ROOT, ".verantyx_chrono", "cross_model_safe_experiment.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    results = []
    for i, q in enumerate(PROMPTS):
        print(f"\n======== CASE {i+1}/{len(PROMPTS)} ========]")
        print(f"Q: {q}")
        t0 = time.time()
        # memorize=False, force_router_speaker=False → bridge が発話優先され得る
        # ただし agent は呼ばない
        rec = council.ask(
            q,
            rounds=rounds,
            escalation=False,
            memorize=False,
            perturb_test=False,
            force_router_speaker=False,
            speak_tokens=64,
        )
        elapsed = time.time() - t0
        answer = _redact(rec.get("answer") or "")
        row = {
            "case": i + 1,
            "question": q,
            "answer": answer,
            "speaker": rec.get("speaker"),
            "concepts": rec.get("concepts"),
            "escalation_level": rec.get("escalation_level"),
            "elapsed_s": round(elapsed, 2),
            "fidelity": rec.get("fidelity"),
            "decontam": rec.get("decontam"),
            "abstract_link": {
                k: (rec.get("abstract_link") or {}).get(k)
                for k in ("divergence", "fidelity_ok", "resteps", "decontam")
                if rec.get("abstract_link")
            },
            "bridge": args.bridge,
            "safe": True,
        }
        results.append(row)
        print(f"A [{row['speaker']}]: {answer}")
        print(f"elapsed={row['elapsed_s']}s fidelity={row.get('fidelity')}")
        with open(out_path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 単体: bridge が分布インターリンガを受け取れるか
    print("\n======== DIST TOSS (opine_dist only) ========]")
    dist = [("4", 0.55), ("four", 0.25), ("5", 0.1), ("banana", 0.1)]
    d_out, _inner = peer.opine_dist(
        "What is 2+2? One token only.", consensus_dist=dist)
    d_out = [(_redact(s), w) for s, w in (d_out or [])]
    print("peer opine_dist:", d_out)
    with open(out_path, "a") as f:
        f.write(json.dumps({
            "case": "dist_toss", "consensus_dist": dist,
            "peer_dist": d_out, "bridge": args.bridge, "safe": True,
        }, ensure_ascii=False) + "\n")

    print(f"\n[SAFE] done. results → {out_path}")
    print(json.dumps({"n": len(results),
                      "speakers": [r["speaker"] for r in results],
                      "answers": [r["answer"] for r in results]},
                     ensure_ascii=False, indent=2))
    try:
        council.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
