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
  puzzle           6軸マトリョーシカ・パズル推論 (同一0.5B・depth2)
  council_div      乖離パケット + C/E/R/N (同一0.5B・escalate off 想定)
  puzzle_div       マトリョーシカ + 乖離接合連動 (同一0.5B)
  solo_4b          大型単体生成 (~4B)。評議会・escalate・plan_steal なし
  solo_9b          大型単体生成 (~9B)。評議会・escalate・plan_steal なし
  solo             任意モデル単体 (--solo-model 必須)

モデル解決 (solo_4b / solo_9b):
  1) --solo-model (solo モード、または両サイズの明示上書き)
  2) 環境変数 VERANTYX_SOLO_4B / VERANTYX_SOLO_9B
     (ローカルdir・HF hub id・ollama:<name> 可)
  3) 既知ローカルパス / HF キャッシュ探索
  既定候補: 4B=Qwen2.5-3B-Instruct (≈3B帯), 9B=Ornith-1.0-9B
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
    "council": "旧 ROLES ベクトル評議会 + 摂動テスト",
    "company": "会社型ベクトル合議 (worker=puzzle, AbstractCanvas)",
    "company_locked": "会社型+puzzle+speak_locked (実験・再推論禁止発話)",
    "council_no_perturb": "旧 ROLES ベクトル評議会 (摂動テスト off)",
    "nl_council": "自然言語評議会 (同一0.5B・媒体比較・対照用)",
    "puzzle": "6軸マトリョーシカ・パズル推論 (同一0.5B・depth2)",
    "council_div": "乖離パケット交換 + C/E/R/N (同一0.5B)",
    "puzzle_div": "マトリョーシカ + 乖離接合 (同一0.5B)",
    "solo_4b": "単体 ~4B 生成 (評議会なし・escalateなし)",
    "solo_9b": "単体 ~9B 生成 (評議会なし・escalateなし)",
    "solo": "単体任意モデル (--solo-model)",
}

# puzzle モード用: Council とルーター脳を共有する遅延シングルトン
_puzzle_council = None
_puzzle_div_council = None
# solo_4b / solo_9b / solo: 遅延ロードした発話器 {key: participant}
_solo_speakers = {}

LANG_MAP = {"ja": "Japanese", "en": "English", "zh": "Chinese", "ko": "Korean"}

# 既知のローカル / キャッシュ候補 (存在するパスだけ採用)
_SOLO_9B_CANDIDATES = [
    os.path.join(ROOT, "local_weights/models--deepreinforce-ai--Ornith-1.0-9B/"
                 "snapshots/83dc1f5e24ef8527af019a6b3bf66ac0f1c2c999"),
    os.path.expanduser(
        "~/.cache/huggingface/hub/models--deepreinforce-ai--Ornith-1.0-9B/"
        "snapshots/83dc1f5e24ef8527af019a6b3bf66ac0f1c2c999"),
]
_SOLO_4B_CANDIDATES = [
    # 厳密な 4B が無い環境向け: Qwen2.5-3B / Qwen3-4B 等を探す
    os.path.join(ROOT, "local_weights/models--Qwen--Qwen3-4B-Instruct"),
    os.path.join(ROOT, "local_weights/models--Qwen--Qwen2.5-3B-Instruct"),
    os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct"),
    os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen2.5-3B-Instruct"),
]
_SOLO_4B_HF_IDS = ("Qwen/Qwen3-4B-Instruct", "Qwen/Qwen2.5-3B-Instruct")
_SOLO_9B_HF_IDS = ("deepreinforce-ai/Ornith-1.0-9B",)
_SOLO_4B_OLLAMA = ("qwen3:4b", "qwen2.5:3b", "phi3:3.8b", "gemma2:2b")
_SOLO_9B_OLLAMA = ("ornith:9b", "qwen2.5:7b", "qwen2.5:9b", "llama3.1:8b")


def _hf_snapshot_dir(cache_or_local_root):
    """HF hub キャッシュ風ディレクトリから最新 snapshots/<hash> を返す。"""
    if not cache_or_local_root or not os.path.isdir(cache_or_local_root):
        return None
    # すでに snapshot 直下 (config.json あり)
    if os.path.isfile(os.path.join(cache_or_local_root, "config.json")):
        return cache_or_local_root
    snaps = os.path.join(cache_or_local_root, "snapshots")
    if not os.path.isdir(snaps):
        return None
    kids = [os.path.join(snaps, d) for d in os.listdir(snaps)
            if os.path.isdir(os.path.join(snaps, d))]
    for k in kids:
        if os.path.isfile(os.path.join(k, "config.json")):
            return k
    return kids[0] if kids else None


def discover_solo_spec(size, explicit=None):
    """solo モデル仕様を解決する。戻り値: (spec_str, kind) or (None, reason)。
    kind: 'hf_dir' | 'hf_id' | 'ollama'
    size: '4b' | '9b' | 'any'
    """
    if explicit:
        exp = explicit.strip()
        if exp.startswith("ollama:"):
            return exp, "ollama"
        if os.path.isdir(os.path.expanduser(exp)):
            path = _hf_snapshot_dir(os.path.expanduser(exp)) or os.path.expanduser(exp)
            return path, "hf_dir"
        # HF repo id または未展開パス
        return exp, "hf_id" if "/" in exp else "hf_dir"

    env_key = {"4b": "VERANTYX_SOLO_4B", "9b": "VERANTYX_SOLO_9B"}.get(size)
    if env_key and os.environ.get(env_key):
        return discover_solo_spec("any", os.environ[env_key])

    cands = _SOLO_4B_CANDIDATES if size == "4b" else (
        _SOLO_9B_CANDIDATES if size == "9b" else [])
    for c in cands:
        path = _hf_snapshot_dir(c) or (c if os.path.isdir(c) else None)
        if path and os.path.isfile(os.path.join(path, "config.json")):
            return path, "hf_dir"

    # HF キャッシュを名前パターンで追加探索
    hub = os.path.expanduser("~/.cache/huggingface/hub")
    local = os.path.join(ROOT, "local_weights")
    patterns = (["*4[Bb]*", "*3[Bb]*", "*Qwen3-4B*", "*Qwen2.5-3B*"] if size == "4b"
                else ["*9[Bb]*", "*Ornith*9B*", "*7[Bb]*", "*8[Bb]*"])
    import glob as _glob
    for base in (local, hub):
        if not os.path.isdir(base):
            continue
        for pat in patterns:
            for hit in _glob.glob(os.path.join(base, f"models--{pat}")):
                path = _hf_snapshot_dir(hit)
                if path and os.path.isfile(os.path.join(path, "config.json")):
                    # 0.5B / 1.5B を 4B/9B と誤認しない
                    low = hit.lower()
                    if size == "4b" and any(x in low for x in ("0.5b", "0-5b", "1.5b", "1-5b")):
                        continue
                    if size == "9b" and any(x in low for x in ("0.5b", "0-5b", "1.5b", "35b", "26b")):
                        continue
                    return path, "hf_dir"

    # Ollama ローカルタグ
    try:
        from verantyx_bridges import detect_backends
        tags = detect_backends().get("ollama") or []
        prefer = _SOLO_4B_OLLAMA if size == "4b" else _SOLO_9B_OLLAMA
        for want in prefer:
            for t in tags:
                if t == want or t.startswith(want.split(":")[0] + ":"):
                    return f"ollama:{t}", "ollama"
    except Exception:
        pass

    hint_ids = _SOLO_4B_HF_IDS if size == "4b" else _SOLO_9B_HF_IDS
    reason = (
        f"no local {size} model found. Set {env_key or 'VERANTYX_SOLO_*'} or "
        f"--solo-model to a path / HF id ({', '.join(hint_ids)}) / ollama:<name>"
    )
    return None, reason


def load_solo_speaker(mode, solo_model=None):
    """遅延ロード。失敗時は RuntimeError (呼び出し側が error 行を記録)。"""
    if mode == "solo_4b":
        size, key = "4b", "solo_4b"
    elif mode == "solo_9b":
        size, key = "9b", "solo_9b"
    elif mode == "solo":
        size, key = "any", f"solo:{solo_model or 'default'}"
    else:
        raise ValueError(mode)

    if key in _solo_speakers:
        return _solo_speakers[key]

    explicit = solo_model if (mode == "solo" or solo_model) else None
    if mode == "solo" and not explicit:
        raise RuntimeError("solo モードには --solo-model が必要です")

    spec, kind = discover_solo_spec(size if mode != "solo" else "any", explicit)
    if spec is None:
        raise RuntimeError(kind)  # kind に reason 文字列

    if kind == "ollama" or (isinstance(spec, str) and spec.startswith("ollama:")):
        from verantyx_bridges import make_participant
        speaker = make_participant(spec if spec.startswith("ollama:") else f"ollama:{spec}")
        speaker._solo_spec = spec
        speaker._solo_kind = "ollama"
    else:
        from verantyx_council import HFSage
        name = f"solo-{mode}"
        if size == "9b" or "9b" in str(spec).lower() or "ornith" in str(spec).lower():
            name = "solo-9b"
        elif size == "4b" or any(x in str(spec).lower() for x in ("4b", "3b", "3.8")):
            name = "solo-4b"
        # hf_id の場合は from_pretrained に id を渡す (ネット要・オフラインなら失敗)
        model_dir = spec
        speaker = HFSage(model_dir=model_dir, name=name)
        speaker._solo_spec = spec
        speaker._solo_kind = kind

    _solo_speakers[key] = speaker
    return speaker


def solo_answer(speaker, question, language=None):
    """単発生成。council / escalate / plan_steal を一切通さない。
    Ornith 等の thinking モデルは enable_thinking=False で思考枠を閉じ、
    1パス短生成する (本番 HFSage.speak の2パスより軽い)。"""
    from verantyx_council import polish_answer
    q = question
    if language:
        q = f"{question}\n(Respond in {language}.)"

    # HF / transformers 系: 短い1パス生成
    if hasattr(speaker, "model") and hasattr(speaker, "tok"):
        torch = speaker.torch
        sys_p = "Answer concisely with only the final answer. No chain-of-thought."
        msgs = [{"role": "system", "content": sys_p},
                {"role": "user", "content": q}]
        text = None
        for kwargs in ({"enable_thinking": False}, {}):
            try:
                text = speaker.tok.apply_chat_template(
                    msgs, add_generation_prompt=True, tokenize=False, **kwargs)
                break
            except TypeError:
                continue
        if text is None:
            text = f"System: {sys_p}\nUser: {q}\nAssistant:"
        enc = speaker.tok(text, return_tensors="pt")
        device = next(speaker.model.parameters()).device
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            out = speaker.model.generate(
                **enc, max_new_tokens=128, do_sample=False,
                pad_token_id=speaker.tok.pad_token_id or speaker.tok.eos_token_id)
        gen = out[0][enc["input_ids"].shape[1]:]
        ans = speaker.tok.decode(gen, skip_special_tokens=True).strip()
        # thinking 漏れへの保険
        for marker in ("</think>", "Final answer:", "The answer is"):
            if marker.lower() in ans.lower():
                # case-insensitive split on first marker
                idx = ans.lower().rfind(marker.lower())
                ans = ans[idx + len(marker):].strip()
                break
        if ans.lower().startswith("thinking process"):
            # 思考だけ出て止まった場合は空扱いにせず原文を残す
            pass
        ans = ans.split("\n\n")[0].strip()
        return polish_answer(ans)

    # Ollama 等: 既存 speak
    text = speaker.speak(q, concepts=[], max_new=96)
    return polish_answer(text or "")


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


def run_mode(council, item, mode, rounds, escalation, force_router_speaker=False,
             solo_model=None):
    """1問×1モードを実行。戻り値は結果 dict。"""
    q = item["question"]
    lang = item.get("lang", "en")
    if council is not None:
        council.language = LANG_MAP.get(lang)

    t0 = time.time()
    meta = {"rounds_trace": [], "perturb": None, "consensus_top1": None}

    if mode in ("solo_4b", "solo_9b", "solo"):
        sp = load_solo_speaker(mode, solo_model=solo_model)
        answer = solo_answer(sp, q, language=LANG_MAP.get(lang))
        speaker = getattr(sp, "name", mode)
        meta["medium"] = "solo_generate"
        meta["solo_spec"] = getattr(sp, "_solo_spec", solo_model)
        meta["solo_kind"] = getattr(sp, "_solo_kind", None)
        meta["escalation_level"] = 0
    elif mode == "router":
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
    elif mode in ("puzzle", "puzzle_div"):
        global _puzzle_council, _puzzle_div_council
        use_div = mode == "puzzle_div"
        holder = _puzzle_div_council if use_div else _puzzle_council
        if holder is None:
            from verantyx_matryoshka import MatryoshkaCouncil
            # Council と同一ルーター脳を共有 (再ロード防止)
            holder = MatryoshkaCouncil(
                quiet=True,
                brain=council.brain,
                dictionary=council.dict,
                tok=council.tok,
                axes=getattr(council, "axes", None),
                carrier_alpha=0.08 if use_div else 0.0,
                enable_lexicon=use_div,
            )
            if use_div:
                _puzzle_div_council = holder
            else:
                _puzzle_council = holder
        rec = holder.ask(q, depth=2, use_divergence=use_div)
        answer = rec.get("answer", "")
        speaker = rec.get("speaker", "router(matryoshka)")
        meta["rounds_trace"] = [{"depth": rec.get("rounds", 2),
                                 "joined": rec.get("joined_axes", []),
                                 "dropped": rec.get("dropped_axes", []),
                                 "divergence": rec.get("divergence"),
                                 "pass_order": rec.get("pass_order")}]
        meta["concepts"] = rec.get("concepts", [])
        meta["axis_energies"] = rec.get("axis_energies", {})
        meta["joined_axes"] = rec.get("joined_axes", [])
        meta["dropped_axes"] = rec.get("dropped_axes", [])
        meta["divergence_packets"] = rec.get("divergence_packets", [])
        meta["divergence"] = rec.get("divergence")
        meta["medium"] = "matryoshka_puzzle_div" if use_div else "matryoshka_puzzle"
        meta["escalation_level"] = 0
    elif mode == "council_div":
        # 乖離パイプラインは Council.ask 本線。fair: escalate off + router speaker
        rec = council.ask(
            q, rounds=rounds, escalation=False,
            speak_tokens="auto", memorize=False, perturb_test=True,
            force_router_speaker=True, medium="council")
        answer = rec.get("answer", "")
        speaker = rec.get("speaker", "?")
        meta["rounds_trace"] = rec.get("rounds", [])
        meta["concepts"] = rec.get("concepts", [])
        meta["escalation_level"] = rec.get("escalation_level", 0)
        meta["divergence_packets"] = rec.get("divergence_packets", [])
        meta["divergence"] = rec.get("divergence")
        meta["medium"] = "vector_divergence"
        for rnd in reversed(meta["rounds_trace"]):
            if "perturb" in rnd:
                meta["perturb"] = rnd["perturb"]
            if rnd.get("top1"):
                meta["consensus_top1"] = rnd["top1"]
        if meta["consensus_top1"] is None and meta["rounds_trace"]:
            meta["consensus_top1"] = meta["rounds_trace"][-1].get("top1")
    else:
        perturb = mode != "council_no_perturb"
        if mode in ("company", "company_locked"):
            ask_medium = "company"
            use_puzzle = True
            sep_speak = mode == "company_locked"
        else:
            ask_medium = "council"
            use_puzzle = False
            sep_speak = False
        rec = council.ask(
            q, rounds=rounds, escalation=escalation,
            speak_tokens="auto", memorize=False, perturb_test=perturb,
            force_router_speaker=force_router_speaker, medium=ask_medium,
            use_puzzle_worker=use_puzzle, separate_speaker=sep_speak)
        answer = rec.get("answer", "")
        speaker = rec.get("speaker", "?")
        meta["rounds_trace"] = rec.get("rounds", [])
        meta["concepts"] = rec.get("concepts", [])
        meta["escalation_level"] = rec.get("escalation_level", 0)
        meta["divergence_packets"] = rec.get("divergence_packets", [])
        meta["divergence"] = rec.get("divergence")
        meta["medium"] = rec.get("medium") or (
            "vector_company_puzzle" if ask_medium == "company" else "vector")
        meta["separate_speaker"] = sep_speak
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
                    help="カンマ区切り: router,council,...,council_div,puzzle_div,"
                         "solo_4b,solo_9b,solo")
    ap.add_argument("--max-items", type=int, default=0, help="0=全件")
    ap.add_argument("--rounds", default="auto", help="auto または整数 (auto 推奨: 摂動テストが有効)")
    ap.add_argument("--no-escalate", action="store_true",
                    help="ワーカー/賢者を招集せず、発話も常駐ルーターに固定 "
                         "(評議会メカニズムの公平比較用)")
    ap.add_argument("--solo-model", default="",
                    help="solo / solo_4b / solo_9b のモデル指定 "
                         "(ローカルdir・HF id・ollama:name)。未指定時は自動探索")
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
    if "solo" in modes and not a.solo_model:
        ap.error("solo モードには --solo-model が必要です")

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
    solo_model = a.solo_model.strip() or None

    # 事前に solo モデル解決を表示 (未発見なら正直に報告。偽スコアは作らない)
    solo_modes = [m for m in modes if m in ("solo_4b", "solo_9b", "solo")]
    for sm in solo_modes:
        size = "4b" if sm == "solo_4b" else ("9b" if sm == "solo_9b" else "any")
        spec, kind = discover_solo_spec(size, solo_model if sm == "solo" or solo_model else None)
        if spec is None:
            print(f"[bench] WARN: {sm} モデル未検出 — {kind}")
            print(f"[bench]        実行時に error 行を記録します (スコアは捏造しません)")
        else:
            print(f"[bench] {sm} → {kind}: {spec}")

    total_trials = len(items) * len(modes) * a.repeat
    print(f"[bench] データセット: {len(items)} 問 × {len(modes)} モード × repeat={a.repeat} = {total_trials} 試行")
    print(f"[bench] 出力: {out_dir}")
    print(f"[bench] rounds={rounds} escalation={escalation} "
          f"force_router_speaker={force_router_speaker}\n")

    from memory_guard import GUARD

    # 0.5B 構造モードが無い純 solo ランでは Council を起動しない (9B RAM 節約)
    need_council = any(m not in ("solo_4b", "solo_9b", "solo") for m in modes)
    council = None
    if need_council:
        from verantyx_council import Council
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
                                       force_router_speaker=force_router_speaker,
                                       solo_model=solo_model)
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
        if council is not None:
            council.close()
        for sp in list(_solo_speakers.values()):
            try:
                sp.close()
            except Exception:
                pass
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
        "solo_model": solo_model,
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
