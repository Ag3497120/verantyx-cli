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
  council          評議会 + 摂動テスト (既定) — ベクトル熟議
  council_no_perturb  評議会、摂動テスト off (アブレーション)
  nl_council       自然言語で役割が意見交換 (媒体比較用・同一0.5B)
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

from benchmarks.scoring import score_answer, wilson_ci, percentile

MODES = {
    "router": "ルーター単独 (0.5B 直接生成)",
    "council": "ベクトル評議会 + 摂動テスト",
    "council_no_perturb": "ベクトル評議会 (摂動テスト off)",
    "nl_council": "自然言語評議会 (同一0.5B・媒体比較)",
}

LANG_MAP = {"ja": "Japanese", "en": "English", "zh": "Chinese", "ko": "Korean"}


def category_of(item_id):
    """id の先頭セグメント ('fact_001' -> 'fact') をカテゴリとして使う。
    fact/numeric/logic/multihop/truthful/ja/zh/ko を横断比較する。"""
    return item_id.rsplit("_", 1)[0] if "_" in item_id else item_id


def process_rss_gb():
    """このプロセスの現在の実メモリ (RSS, GB)。psutil があれば使い、
    無ければ標準ライブラリの resource (macOS/Linux) にフォールバックする。"""
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e9
    except Exception:
        pass
    try:
        import platform
        import resource
        peak_kb_or_b = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS は bytes、Linux は KB を返す
        divisor = 1e9 if platform.system() == "Darwin" else 1e6
        return peak_kb_or_b / divisor
    except Exception:
        return 0.0


def load_dataset(path):
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def run_mode(council, item, mode, rounds, escalation, force_router_speaker=False):
    """1問×1モードを実行。戻り値は結果 dict。"""
    q = item["question"]
    lang = item.get("lang", "en")
    council.language = LANG_MAP.get(lang)

    t0 = time.time()
    meta = {"rounds_trace": [], "perturb": None, "consensus_top1": None}

    if mode == "router":
        answer = council.router_answer(q)
        speaker = "router"
    elif mode == "nl_council":
        # 媒体比較: ラウンド数は固定 (auto だと NL が過大コストになりやすい)
        nl_rounds = 2 if rounds == "auto" else int(rounds)
        rec = council.ask_nl(q, rounds=nl_rounds)
        answer = rec.get("answer", "")
        speaker = rec.get("speaker", "router")
        meta["rounds_trace"] = rec.get("rounds", [])
        meta["medium"] = "natural_language"
        meta["gen_calls"] = rec.get("gen_calls", 0)
        meta["char_budget"] = rec.get("char_budget", 0)
        meta["escalation_level"] = 0
    else:
        perturb = mode != "council_no_perturb"
        rec = council.ask(
            q, rounds=rounds, escalation=escalation,
            speak_tokens="auto", memorize=False, perturb_test=perturb,
            force_router_speaker=force_router_speaker)
        answer = rec.get("answer", "")
        speaker = rec.get("speaker", "?")
        meta["rounds_trace"] = rec.get("rounds", [])
        meta["concepts"] = rec.get("concepts", [])
        meta["escalation_level"] = rec.get("escalation_level", 0)
        meta["medium"] = "vector"
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
        "category": category_of(item["id"]),
        "mode": mode,
        "question": q,
        "answer": answer,
        "speaker": speaker,
        "correct": bool(ok),
        "score_method": method,
        "gold": detail,
        "elapsed_s": elapsed,
        "rss_gb": round(process_rss_gb(), 2),
        "escalation_level": meta.get("escalation_level"),
        "medium": meta.get("medium"),
        "gen_calls": meta.get("gen_calls"),
        "char_budget": meta.get("char_budget"),
        "n_rounds": len(meta.get("rounds_trace") or []),
        "meta": meta,
    }


def summarize(rows):
    by_mode = {}
    by_mode_cat = {}
    for r in rows:
        m = r["mode"]
        by_mode.setdefault(m, {"n": 0, "correct": 0, "time": 0.0, "times": [],
                                 "perturb_recovered": 0, "perturb_total": 0,
                                 "esc_levels": [], "rss": [],
                                 "gen_calls": [], "char_budget": []})
        s = by_mode[m]
        s["n"] += 1
        s["correct"] += int(r["correct"])
        s["time"] += r["elapsed_s"]
        s["times"].append(r["elapsed_s"])
        if r.get("rss_gb"):
            s["rss"].append(r["rss_gb"])
        if r.get("gen_calls") is not None:
            s["gen_calls"].append(r["gen_calls"])
        if r.get("char_budget") is not None:
            s["char_budget"].append(r["char_budget"])
        esc = r.get("escalation_level")
        if esc is None:
            esc = r.get("meta", {}).get("escalation_level")
        if esc is not None:
            s["esc_levels"].append(esc)
        p = r.get("meta", {}).get("perturb")
        if p is not None:
            s["perturb_total"] += 1
            s["perturb_recovered"] += int(p.get("recovered", False))
        cat = r.get("category") or category_of(r["id"])
        by_mode_cat.setdefault(m, {}).setdefault(cat, {"n": 0, "correct": 0})
        by_mode_cat[m][cat]["n"] += 1
        by_mode_cat[m][cat]["correct"] += int(r["correct"])

    out = {}
    for m, s in by_mode.items():
        n = max(s["n"], 1)
        lo, hi = wilson_ci(s["correct"], s["n"])
        out[m] = {
            "description": MODES.get(m, m),
            "n": s["n"],
            "accuracy": round(s["correct"] / n, 4),
            "accuracy_ci95": [round(lo, 4), round(hi, 4)],
            "correct": s["correct"],
            "avg_time_s": round(s["time"] / n, 1),
            "p50_time_s": round(percentile(s["times"], 50), 1),
            "p95_time_s": round(percentile(s["times"], 95), 1),
            "peak_rss_gb": round(max(s["rss"]), 2) if s["rss"] else None,
            "avg_gen_calls": (
                round(sum(s["gen_calls"]) / len(s["gen_calls"]), 1)
                if s["gen_calls"] else None),
            "avg_char_budget": (
                round(sum(s["char_budget"]) / len(s["char_budget"]), 1)
                if s["char_budget"] else None),
            "avg_escalation_level": (
                round(sum(s["esc_levels"]) / len(s["esc_levels"]), 2)
                if s["esc_levels"] else None),
            "perturb_recovered_rate": (
                round(s["perturb_recovered"] / s["perturb_total"], 4)
                if s["perturb_total"] else None),
            "perturb_tests": s["perturb_total"],
            "by_category": {
                cat: {"n": v["n"], "correct": v["correct"],
                      "accuracy": round(v["correct"] / max(v["n"], 1), 4)}
                for cat, v in by_mode_cat.get(m, {}).items()
            },
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
        "## 集計 (95%信頼区間つき)",
        "",
        "| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |",
        "|--------|-----------------|-----------|-------------------|--------------|------------|---------|",
    ]
    for mode, s in summary.items():
        pr = (f"{s['perturb_recovered_rate']*100:.0f}% ({s['perturb_tests']}回)"
              if s["perturb_recovered_rate"] is not None else "—")
        lo, hi = s.get("accuracy_ci95", [0, 0])
        esc = f"{s['avg_escalation_level']:.2f}" if s.get("avg_escalation_level") is not None else "—"
        rss = f"{s['peak_rss_gb']:.1f}GB" if s.get("peak_rss_gb") is not None else "—"
        lines.append(
            f"| {mode} | **{s['accuracy']*100:.1f}%** [{lo*100:.1f}–{hi*100:.1f}] | {s['correct']}/{s['n']} "
            f"| {s['avg_time_s']}s / {s['p50_time_s']}s / {s['p95_time_s']}s | {esc} | {pr} | {rss} |")
    lines += ["", "## モード間の差分 (評議会の価値)", ""]
    if "router" in summary and "council" in summary:
        delta = summary["council"]["accuracy"] - summary["router"]["accuracy"]
        lines.append(f"- council − router: **{delta*100:+.1f} pt**"
                     " (信頼区間が重なる場合は有意差なしと解釈すること)")
    if "nl_council" in summary and "council" in summary:
        delta = summary["council"]["accuracy"] - summary["nl_council"]["accuracy"]
        lines.append(f"- vector council − NL council: **{delta*100:+.1f} pt**"
                     " (媒体の差。話者は同一0.5B)")
        if summary["nl_council"].get("avg_gen_calls") is not None:
            lines.append(
                f"- NL 平均生成回数: {summary['nl_council']['avg_gen_calls']} "
                f"/ 平均出力文字: {summary['nl_council'].get('avg_char_budget')}")
        lines.append(
            f"- 時間: NL {summary['nl_council']['avg_time_s']}s vs "
            f"vector {summary['council']['avg_time_s']}s")
    if "council_no_perturb" in summary and "council" in summary:
        delta = summary["council"]["accuracy"] - summary["council_no_perturb"]["accuracy"]
        lines.append(f"- 摂動テストの効果 (council − no_perturb): **{delta*100:+.1f} pt**")

    lines += ["", "## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)", ""]
    cats = sorted({c for s in summary.values() for c in s.get("by_category", {})})
    header = "| モード | " + " | ".join(cats) + " |"
    lines += [header, "|" + "---|" * (len(cats) + 1)]
    for mode, s in summary.items():
        cells = []
        for c in cats:
            bc = s.get("by_category", {}).get(c)
            cells.append(f"{bc['accuracy']*100:.0f}% ({bc['correct']}/{bc['n']})" if bc else "—")
        lines.append(f"| {mode} | " + " | ".join(cells) + " |")

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
    ap.add_argument("--no-escalate", action="store_true",
                    help="ワーカー/賢者を招集せず、発話も常駐ルーターに固定 "
                         "(評議会メカニズムの公平比較用)")
    ap.add_argument("--out", default="", help="出力ディレクトリ (既定: benchmarks/results/<ts>)")
    ap.add_argument("--secret", action="store_true", default=True,
                    help="記憶/反射を切る (ベンチマーク汚染防止、既定 on)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="各問題を何回繰り返すか (分散/再現性の確認用)")
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
    # --no-escalate 時は発話もルーター固定 (言語指定によるワーカー招集を防ぐ)
    force_router_speaker = a.no_escalate

    total_trials = len(items) * len(modes) * a.repeat
    print(f"[bench] データセット: {len(items)} 問 × {len(modes)} モード × repeat={a.repeat} = {total_trials} 試行")
    print(f"[bench] 出力: {out_dir}")
    print(f"[bench] rounds={rounds} escalation={escalation} "
          f"force_router_speaker={force_router_speaker}\n")

    from verantyx_council import Council
    from memory_guard import GUARD

    council = Council(quiet=True, secret=True)
    rows = []
    peak_rss = 0.0
    try:
        for rep in range(a.repeat):
            for i, item in enumerate(items):
                for mode in modes:
                    tag = f"rep{rep+1}/{a.repeat} " if a.repeat > 1 else ""
                    print(f"  {tag}[{i+1}/{len(items)}] {item['id']} / {mode} ...",
                          end="", flush=True)
                    try:
                        row = run_mode(council, item, mode, rounds, escalation,
                                       force_router_speaker=force_router_speaker)
                        if a.repeat > 1:
                            row["id"] = f"{row['id']}#{rep+1}"
                        rows.append(row)
                        peak_rss = max(peak_rss, row.get("rss_gb", 0) or 0)
                        mark = "✓" if row["correct"] else "✗"
                        print(f" {mark} ({row['elapsed_s']}s, rss={row.get('rss_gb', 0):.1f}GB)")
                    except Exception as e:
                        rows.append({"id": item["id"], "category": category_of(item["id"]),
                                     "mode": mode, "question": item["question"],
                                     "correct": False, "error": str(e), "elapsed_s": 0})
                        print(f" ERR: {e}")
                    GUARD.maybe_trim()
    finally:
        council.close()
    print(f"\n[bench] プロセス最大RSS: {peak_rss:.1f}GB")

    summary = summarize(rows)
    cfg = {
        "timestamp": ts,
        "dataset": a.dataset,
        "n_items": len(items),
        "modes": modes,
        "rounds": rounds,
        "escalation": escalation,
        "force_router_speaker": force_router_speaker,
        "repeat": a.repeat,
        "peak_rss_gb": round(peak_rss, 2),
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
