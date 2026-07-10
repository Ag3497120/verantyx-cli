#!/usr/bin/env python3
"""
verantyx_bench.py — Verantyx 評議会の定量ベンチマーク
========================================================
評議会 vs ルーター単独、摂動テスト on/off を同一問題集合で比較する。

使い方:
  python benchmarks/verantyx_bench.py                          # 全モード・全20問
  python benchmarks/verantyx_bench.py --max-items 5          # 先頭5問だけ
  python benchmarks/verantyx_bench.py --modes router,council   # モード限定
  python benchmarks/verantyx_bench.py --rounds 2 --no-escalate # 0.5Bのみ・2ラウンド固定
  python benchmarks/verantyx_bench.py --dataset benchmarks/datasets/factual_qa.jsonl

モード:
  router           評議会なし (0.5B 直接生成)
  council          評議会 + 摂動テスト (既定)
  council_no_perturb  評議会、摂動テスト off (アブレーション)

出力:
  benchmarks/results/<timestamp>/
    summary.json   集計
    detail.jsonl   1行1試行 (再分析用)
    report.md      人間可読サマリ
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

# リポジトリルートを import path に
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmarks.scoring import score_answer

MODES = {
    "router": "ルーター単独 (0.5B 直接生成)",
    "council": "評議会 + 摂動テスト",
    "council_no_perturb": "評議会 (摂動テスト off)",
}

LANG_MAP = {"ja": "Japanese", "en": "English", "zh": "Chinese", "ko": "Korean"}


def load_dataset(path):
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def run_mode(council, item, mode, rounds, escalation):
    """1問×1モードを実行。戻り値は結果 dict。"""
    q = item["question"]
    lang = item.get("lang", "en")
    council.language = LANG_MAP.get(lang)

    t0 = time.time()
    meta = {"rounds_trace": [], "perturb": None, "consensus_top1": None}

    if mode == "router":
        answer = council.router_answer(q)
        speaker = "router"
    else:
        perturb = mode != "council_no_perturb"
        rec = council.ask(
            q, rounds=rounds, escalation=escalation,
            speak_tokens="auto", memorize=False, perturb_test=perturb)
        answer = rec.get("answer", "")
        speaker = rec.get("speaker", "?")
        meta["rounds_trace"] = rec.get("rounds", [])
        meta["concepts"] = rec.get("concepts", [])
        meta["escalation_level"] = rec.get("escalation_level", 0)
        # 最終ラウンドの摂動結果
        for rnd in reversed(meta["rounds_trace"]):
            if "perturb" in rnd:
                meta["perturb"] = rnd["perturb"]
            if rnd.get("top1"):
                meta["consensus_top1"] = rnd["top1"]
        if meta["consensus_top1"] is None and meta["rounds_trace"]:
            meta["consensus_top1"] = meta["rounds_trace"][-1].get("top1")

    elapsed = round(time.time() - t0, 1)
    ok, method, detail = score_answer(answer, item.get("answers", []),
                                      qtype=item.get("type", "fact"))
    return {
        "id": item["id"],
        "mode": mode,
        "question": q,
        "answer": answer,
        "speaker": speaker,
        "correct": ok,
        "score_method": method,
        "gold": detail,
        "elapsed_s": elapsed,
        "meta": meta,
    }


def summarize(rows):
    by_mode = {}
    for r in rows:
        m = r["mode"]
        by_mode.setdefault(m, {"n": 0, "correct": 0, "time": 0.0,
                                 "perturb_recovered": 0, "perturb_total": 0})
        s = by_mode[m]
        s["n"] += 1
        s["correct"] += int(r["correct"])
        s["time"] += r["elapsed_s"]
        p = r.get("meta", {}).get("perturb")
        if p is not None:
            s["perturb_total"] += 1
            s["perturb_recovered"] += int(p.get("recovered", False))

    out = {}
    for m, s in by_mode.items():
        n = max(s["n"], 1)
        out[m] = {
            "description": MODES.get(m, m),
            "n": s["n"],
            "accuracy": round(s["correct"] / n, 4),
            "correct": s["correct"],
            "avg_time_s": round(s["time"] / n, 1),
            "perturb_recovered_rate": (
                round(s["perturb_recovered"] / s["perturb_total"], 4)
                if s["perturb_total"] else None),
            "perturb_tests": s["perturb_total"],
        }
    return out


def write_report(path, summary, rows, cfg):
    lines = [
        "# Verantyx Benchmark Report",
        "",
        f"- 実行: {cfg['timestamp']}",
        f"- データセット: `{cfg['dataset']}` ({cfg['n_items']} 問)",
        f"- ラウンド: {cfg['rounds']} | エスカレーション: {cfg['escalation']}",
        "",
        "## 集計",
        "",
        "| モード | 正解率 | 正解/総数 | 平均時間 | 摂動復帰率 |",
        "|--------|--------|-----------|----------|------------|",
    ]
    for mode, s in summary.items():
        pr = (f"{s['perturb_recovered_rate']*100:.0f}% ({s['perturb_tests']}回)"
              if s["perturb_recovered_rate"] is not None else "—")
        lines.append(
            f"| {mode} | **{s['accuracy']*100:.1f}%** | {s['correct']}/{s['n']} "
            f"| {s['avg_time_s']}s | {pr} |")
    lines += ["", "## モード間の差分 (評議会の価値)", ""]
    if "router" in summary and "council" in summary:
        delta = summary["council"]["accuracy"] - summary["router"]["accuracy"]
        lines.append(f"- council − router: **{delta*100:+.1f} pt**")
    if "council_no_perturb" in summary and "council" in summary:
        delta = summary["council"]["accuracy"] - summary["council_no_perturb"]["accuracy"]
        lines.append(f"- 摂動テストの効果 (council − no_perturb): **{delta*100:+.1f} pt**")
    lines += ["", "## 誤答一覧", ""]
    for r in rows:
        if not r["correct"]:
            lines.append(f"- `{r['id']}` [{r['mode']}] 期待=`{r['gold']}` → `{r['answer'][:120]}`")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Verantyx council benchmark")
    ap.add_argument("--dataset", default=os.path.join(ROOT, "benchmarks/datasets/factual_qa.jsonl"))
    ap.add_argument("--modes", default="router,council,council_no_perturb",
                    help="カンマ区切り: router,council,council_no_perturb")
    ap.add_argument("--max-items", type=int, default=0, help="0=全件")
    ap.add_argument("--rounds", default="auto", help="auto または整数 (auto 推奨: 摂動テストが有効)")
    ap.add_argument("--no-escalate", action="store_true", help="0.5B のみ (ワーカー/賢者を招集しない)")
    ap.add_argument("--out", default="", help="出力ディレクトリ (既定: benchmarks/results/<ts>)")
    ap.add_argument("--secret", action="store_true", default=True,
                    help="記憶/反射を切る (ベンチマーク汚染防止、既定 on)")
    a = ap.parse_args()

    modes = [m.strip() for m in a.modes.split(",") if m.strip()]
    for m in modes:
        if m not in MODES:
            ap.error(f"未知のモード: {m} (有効: {', '.join(MODES)})")

    items = load_dataset(a.dataset)
    if a.max_items > 0:
        items = items[:a.max_items]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = a.out or os.path.join(ROOT, "benchmarks", "results", ts)
    os.makedirs(out_dir, exist_ok=True)

    rounds = a.rounds if a.rounds == "auto" else int(a.rounds)
    escalation = not a.no_escalate

    print(f"[bench] データセット: {len(items)} 問 × {len(modes)} モード = {len(items)*len(modes)} 試行")
    print(f"[bench] 出力: {out_dir}")
    print(f"[bench] rounds={rounds} escalation={escalation}\n")

    from verantyx_council import Council
    from memory_guard import GUARD

    council = Council(quiet=True, secret=True)
    rows = []
    try:
        for i, item in enumerate(items):
            for mode in modes:
                print(f"  [{i+1}/{len(items)}] {item['id']} / {mode} ...", end="", flush=True)
                try:
                    row = run_mode(council, item, mode, rounds, escalation)
                    rows.append(row)
                    mark = "✓" if row["correct"] else "✗"
                    print(f" {mark} ({row['elapsed_s']}s)")
                except Exception as e:
                    rows.append({"id": item["id"], "mode": mode, "question": item["question"],
                                 "correct": False, "error": str(e), "elapsed_s": 0})
                    print(f" ERR: {e}")
                GUARD.maybe_trim()
    finally:
        council.close()

    summary = summarize(rows)
    cfg = {
        "timestamp": ts,
        "dataset": a.dataset,
        "n_items": len(items),
        "modes": modes,
        "rounds": rounds,
        "escalation": escalation,
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "summary": summary}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "detail.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_report(os.path.join(out_dir, "report.md"), summary, rows, cfg)

    print(f"\n[bench] 完了 → {out_dir}/")
    for mode, s in summary.items():
        print(f"  {mode:22s} {s['correct']}/{s['n']} = {s['accuracy']*100:.1f}%  "
              f"(avg {s['avg_time_s']}s)")


if __name__ == "__main__":
    main()
