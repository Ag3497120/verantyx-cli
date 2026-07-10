"""
session_log.py — セッション履歴の最小永続ログ
================================================
「さっきの」「以前の」という参照を、再起動をまたいでも解決できるようにする。
各ターン (評議会/エージェント) のタスクと結果の要約を jsonl に追記し、
エージェント起動時に直近数ターンを文脈ブロックとして注入する。

シークレットモード中は呼び出し側が log_turn を呼ばないことで記録を止める。
"""
import json
import os
import time

CHRONO = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono")
LOG_PATH = os.path.join(CHRONO, "session_log.jsonl")
MAX_KEEP = 200  # ファイルが伸びすぎたら古い行を落とす


def log_turn(kind, task, result):
    """1ターンを記録する。kind: 'agent' | 'council'"""
    if not task:
        return
    os.makedirs(CHRONO, exist_ok=True)
    row = {"ts": time.time(), "kind": kind,
           "task": str(task)[:300], "result": str(result or "")[:400]}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    _trim()


def _trim():
    try:
        with open(LOG_PATH) as f:
            lines = f.readlines()
        if len(lines) > MAX_KEEP * 2:
            with open(LOG_PATH, "w") as f:
                f.writelines(lines[-MAX_KEEP:])
    except OSError:
        pass


def recent(n=6):
    """直近 n ターンを新しい順ではなく時系列順で返す。"""
    if not os.path.exists(LOG_PATH):
        return []
    rows = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows[-n:]


def context_block(n=6, max_chars=1800):
    """エージェントに渡す文脈ブロック。無ければ空文字。"""
    rows = recent(n)
    if not rows:
        return ""
    lines = []
    for r in rows:
        age_min = (time.time() - r["ts"]) / 60
        when = f"{age_min:.0f}分前" if age_min < 120 else f"{age_min/60:.0f}時間前"
        lines.append(f"- ({when}, {r['kind']}) 依頼: {r['task'][:160]}")
        if r.get("result"):
            lines.append(f"    結果: {r['result'][:200]}")
    block = "\n".join(lines)
    return block[:max_chars]
