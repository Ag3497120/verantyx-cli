#!/usr/bin/env python3
"""
codec_suite.py — 層×領域コーデック・スイート (Sprint 1–5)
==============================================================================

デュアルゲートを明示分離する:
  lexicon_only      — Write→Read NN（フォワード不要）
  forward_roundtrip — encode / soft / inject / Write→forward→Read

例:
  python3 benchmarks/codec_suite.py --max-items 30 \\
      --out benchmarks/results/codec_suite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "benchmarks"))

from transformers import AutoTokenizer

from concept_lexicon import (
    ConceptLexicon, DEFAULT_GATE_THRESHOLD, load_propositions,
    write_read_reproduce, proposition_match,
)
from scoring import wilson_ci, percentile
from verantyx_council import (
    dist_from_vector, dist_to_soft_numpy, dist_to_soft_sequence,
    encode_with_dist_soft, sharpen_dist, soft_probe_tokens,
)
from verantyx_mind import DEFAULT_MODEL, TOKENIZER, HIDDEN, JGenDict, RustBrain
from verantyx_codec import (
    layer_probe_points, layer_quartile_points, hybrid_read, write_router,
    write_forward_read, soft_keyword_hit, encode_proposition,
    best_layer_by_domain, save_layer_routing, load_layer_routing,
    DEFAULT_READ_THRESHOLD,
)

DEFAULT_CORPUS = os.path.join(ROOT, "benchmarks/datasets/codec_propositions.jsonl")

CLAIM_BOUNDARY = [
    "Measures hidden-state Read/Write reconstruction only — not LongMemEval QA.",
    "Keyword / label overlap is a coarse heuristic, not BABEL-style 100% reconstruction.",
    "Soft inject is a semi-codec (vocab-distribution interlingua), not a lossless inverse.",
    "Mid-layer scores require encode_layers / inject_at_layer FFI (rebuild jcross_engine_glm).",
    "C_valve Identity is unrelated to codec completion.",
    "Codec APIs are for control research; safety-bypass / jailbreak use is out of scope.",
    "lexicon_only and forward_roundtrip are separate gates — do not conflate them.",
    "NOT an accuracy booster for council/router QA; NOT BABEL parity.",
]


def _unit(v):
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    return v / (np.linalg.norm(v) + 1e-8)


def _cosine(a, b):
    return float(_unit(a) @ _unit(b))


def _keyword_hit(dist_tokens, keywords):
    blob = " ".join(dist_tokens).lower()
    hits = sum(1 for kw in keywords if kw.lower() in blob)
    return hits >= max(1, (len(keywords) + 1) // 2)


def stratified_sample(items: list, max_items: int, seed: int = 0) -> list:
    """Domain-balanced subsample for suite smokes (keeps coverage for L2/L3)."""
    if max_items <= 0 or max_items >= len(items):
        return list(items)
    rng = np.random.default_rng(seed)
    by_dom: dict = defaultdict(list)
    for it in items:
        by_dom[it.get("domain") or "_"].append(it)
    domains = sorted(by_dom.keys())
    if not domains:
        return items[:max_items]
    per = max(1, max_items // len(domains))
    picked = []
    for d in domains:
        pool = list(by_dom[d])
        rng.shuffle(pool)
        picked.extend(pool[:per])
    if len(picked) < max_items:
        rest = [it for it in items if it not in picked]
        rng.shuffle(rest)
        picked.extend(rest[: max_items - len(picked)])
    rng.shuffle(picked)
    return picked[:max_items]


def probe_layers(brain, mode: str = "early_mid_late") -> list[int]:
    n = brain.num_layers
    if not n:
        return []
    if mode == "quartile":
        return layer_quartile_points(int(n))
    return layer_probe_points(int(n))


def run_final_read_write(brain, dic, tok, sem, item, lex=None) -> dict:
    text = item["text"]
    keywords = item.get("keywords") or text.split()[:3]
    # 命題スロット encode → sharpen dist → soft トークン列 (キャリア無し)
    z0 = encode_proposition(brain, tok, text)
    # R1 hybrid read on encode
    hr = hybrid_read(z0, lexicon=lex, dictionary=dic, tok=tok, sem=sem)
    dist0 = sharpen_dist(dist_from_vector(dic, tok, z0, sem, top_k=48))
    toks0 = [t for t, _ in dist0[:16]]
    z1 = encode_with_dist_soft(
        brain, tok, dic._embed_f16, dist0, probe="none", max_soft=16,
        dictionary=dic, hidden_blend=0.35)
    dist1 = dist_from_vector(dic, tok, z1, sem, top_k=32)
    toks1 = [t for t, _ in dist1[:16]]
    # baseline: answer probe のみ (soft 無し)
    z_base = brain.encode(soft_probe_tokens(tok, "answer"))
    dist_base = dist_from_vector(dic, tok, z_base, sem, top_k=32)
    toks_base = [t for t, _ in dist_base[:16]]
    return {
        "phase": "final",
        "gate": "forward_roundtrip",
        "id": item["id"],
        "domain": item.get("domain", ""),
        "text": text,
        "read_keyword_hit": _keyword_hit(toks0, keywords),
        "soft_keyword_hit": _keyword_hit(toks1, keywords),
        "baseline_keyword_hit": _keyword_hit(toks_base, keywords),
        "hybrid_read_path": hr.get("path"),
        "hybrid_label": hr.get("label", ""),
        "hybrid_ok": proposition_match(hr.get("label", ""), text, keywords),
        "roundtrip_cos": _cosine(z0, z1),
        "top_read": toks0[:6],
        "top_soft": toks1[:6],
        "soft_path": "sharpen+sequence+soft_only",
    }


def run_forward_read_gate(brain, tok, lex, item) -> dict:
    """R2: encode(text) → hybrid/lexicon Read → proposition_match."""
    text = item["text"]
    keywords = item.get("keywords") or text.split()[:3]
    z = encode_proposition(brain, tok, text)
    pred, score = ("", 0.0)
    if lex is not None and lex.available:
        pred, score = lex.top1(z)
    ok = proposition_match(pred, text, keywords)
    return {
        "phase": "forward_read",
        "gate": "forward_roundtrip",
        "id": item["id"],
        "domain": item.get("domain", ""),
        "text": text,
        "pred": pred,
        "score": float(score),
        "ok": ok,
    }


def run_write_forward_read(brain, dic, tok, sem, lex, item, inject_layer=None,
                           layer_routing=None) -> dict:
    """W4: Write → forward → Read (primary forward metric)."""
    text = item["text"]
    keywords = item.get("keywords") or text.split()[:3]
    domain = item.get("domain", "")
    rec = write_forward_read(
        text, brain, tok, dic, lexicon=lex, sem=sem, keywords=keywords,
        inject_layer=inject_layer, domain=domain, layer_routing=layer_routing,
    )
    return {
        "phase": "write_forward_read",
        "gate": "forward_roundtrip",
        "id": item["id"],
        "domain": domain,
        "text": text,
        **rec,
    }


def run_inject_ab(brain, dic, tok, sem, item, layers: list[int], lex=None) -> list[dict]:
    """W2: A/B inject_at_layer mid/late vs final encode baseline."""
    text = item["text"]
    keywords = item.get("keywords") or text.split()[:3]
    chatml = (
        f"<|im_start|>user\nState this fact: {text}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    ids = tok.encode(chatml, add_special_tokens=False)
    out = []
    z_ref = brain.encode(ids)
    # final baseline (no mid inject)
    dist_final = dist_from_vector(dic, tok, z_ref, sem, top_k=32)
    toks_final = [t for t, _ in dist_final[:16]]
    hr_final = hybrid_read(z_ref, lexicon=lex, dictionary=dic, tok=tok, sem=sem)
    out.append({
        "phase": "inject_ab",
        "gate": "forward_roundtrip",
        "id": item["id"],
        "domain": item.get("domain", ""),
        "text": text,
        "variant": "final",
        "layer": None,
        "keyword_hit": _keyword_hit(toks_final, keywords),
        "hybrid_ok": proposition_match(hr_final.get("label", ""), text, keywords),
        "inject_vs_encode_cos": 1.0,
    })
    n_layers = int(brain.num_layers or 0)
    try:
        dumps = brain.encode_layers(ids, layers)
    except (RuntimeError, AttributeError) as e:
        out.append({"phase": "inject_ab", "id": item["id"], "error": str(e)})
        return out
    for layer, z_mid in dumps.items():
        inject_at = min(int(layer) + 1, n_layers) if n_layers else int(layer)
        try:
            z_final = brain.inject_at_layer(ids, inject_at, z_mid, alpha=1.0)
        except (RuntimeError, AttributeError) as e:
            out.append({
                "phase": "inject_ab", "id": item["id"], "layer": int(layer),
                "error": str(e),
            })
            continue
        dist = dist_from_vector(dic, tok, z_final, sem, top_k=32)
        toks = [t for t, _ in dist[:16]]
        hr = hybrid_read(z_final, lexicon=lex, dictionary=dic, tok=tok, sem=sem)
        mid = max(0, (n_layers - 1) // 2) if n_layers else 0
        late = (n_layers - 1) if n_layers else 0
        if int(layer) == mid:
            variant = "mid"
        elif int(layer) == late:
            variant = "late"
        else:
            variant = f"L{int(layer)}"
        out.append({
            "phase": "inject_ab",
            "gate": "forward_roundtrip",
            "id": item["id"],
            "domain": item.get("domain", ""),
            "text": text,
            "variant": variant,
            "layer": int(layer),
            "inject_at": inject_at,
            "keyword_hit": _keyword_hit(toks, keywords),
            "hybrid_ok": proposition_match(hr.get("label", ""), text, keywords),
            "inject_vs_encode_cos": _cosine(z_final, z_ref),
            "top_tokens": toks[:6],
        })
    return out


def run_layer_item(brain, dic, tok, sem, item, layers: list[int], lex=None) -> list[dict]:
    text = item["text"]
    keywords = item.get("keywords") or text.split()[:3]
    chatml = (
        f"<|im_start|>user\nState this fact: {text}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    ids = tok.encode(chatml, add_special_tokens=False)
    out = []
    try:
        dumps = brain.encode_layers(ids, layers)
    except (RuntimeError, AttributeError) as e:
        return [{"phase": "layer", "id": item["id"], "error": str(e)}]

    z_ref = brain.encode(ids)
    n_layers = int(brain.num_layers or 0)
    for layer, z_mid in dumps.items():
        inject_at = min(int(layer) + 1, n_layers) if n_layers else int(layer)
        try:
            z_final = brain.inject_at_layer(ids, inject_at, z_mid, alpha=1.0)
        except (RuntimeError, AttributeError) as e:
            out.append({
                "phase": "layer", "id": item["id"], "layer": int(layer),
                "inject_at": inject_at, "error": str(e),
            })
            continue
        dist = dist_from_vector(dic, tok, z_final, sem, top_k=32)
        toks = [t for t, _ in dist[:16]]
        hr = hybrid_read(z_final, lexicon=lex, dictionary=dic, tok=tok, sem=sem)
        out.append({
            "phase": "layer",
            "gate": "forward_roundtrip",
            "id": item["id"],
            "domain": item.get("domain", ""),
            "text": text,
            "layer": int(layer),
            "inject_at": inject_at,
            "keyword_hit": _keyword_hit(toks, keywords),
            "hybrid_ok": proposition_match(hr.get("label", ""), text, keywords),
            "inject_vs_encode_cos": _cosine(z_final, z_ref),
            "mid_norm": float(np.linalg.norm(z_mid)),
            "top_tokens": toks[:6],
        })
    return out


def run_lexicon_item(lex: ConceptLexicon, item) -> dict:
    text = item["text"]
    base = np.random.randn(HIDDEN).astype(np.float32)
    base = _unit(base) * 10.0
    try:
        z = lex.write(base, [text], alpha=1.0, mode="replace")
    except Exception as e:
        return {
            "phase": "lexicon", "gate": "lexicon_only",
            "id": item["id"], "domain": item.get("domain", ""),
            "text": text, "ok": False, "error": str(e),
        }
    # R1 hybrid prefer lexicon
    hr = hybrid_read(z, lexicon=lex, dictionary=None, tok=None,
                     threshold=DEFAULT_READ_THRESHOLD)
    pred = hr.get("label") or lex.top1(z)[0]
    score = hr.get("score", 0.0)
    ok = proposition_match(pred, text, item.get("keywords"))
    return {
        "phase": "lexicon",
        "gate": "lexicon_only",
        "id": item["id"],
        "domain": item.get("domain", ""),
        "text": text,
        "pred": pred,
        "score": score,
        "ok": ok,
        "read_path": hr.get("path"),
    }


def _rate_ci(flags: list[int]) -> dict:
    c, n = sum(flags), len(flags)
    lo, hi = wilson_ci(c, n)
    return {
        "n": n,
        "rate": c / max(n, 1),
        "ci95": [lo, hi],
        "correct": c,
    }


def summarize(rows: list[dict], gate: dict, layers: list[int],
              lex_hold: dict | None = None) -> dict:
    by_phase = defaultdict(list)
    for r in rows:
        by_phase[r.get("phase", "?")].append(r)

    # Dual gates
    lex_only_rows = [r for r in rows if r.get("gate") == "lexicon_only" or r.get("phase") == "lexicon"]
    forward_rows = [r for r in rows if r.get("gate") == "forward_roundtrip"]

    lexicon_only = {
        "description": "Write→Read NN on concept lexicon (no forward pass)",
        "gate_threshold": gate.get("threshold", DEFAULT_GATE_THRESHOLD),
        "write_read_reproduce": {
            "n": gate.get("n", 0),
            "rate": gate.get("rate", 0.0),
            "correct": gate.get("correct", 0),
            "pass": gate.get("pass", False),
        },
    }
    if lex_hold:
        lexicon_only["holdout"] = lex_hold
    if lex_only_rows:
        oks = [int(r.get("ok")) for r in lex_only_rows if "ok" in r]
        block = _rate_ci(oks)
        by_dom = defaultdict(lambda: {"n": 0, "ok": 0})
        for r in lex_only_rows:
            d = r.get("domain") or "?"
            by_dom[d]["n"] += 1
            by_dom[d]["ok"] += int(bool(r.get("ok")))
        lexicon_only["suite_reproduce"] = {
            **block,
            "gate_pass": block["rate"] >= gate.get("threshold", DEFAULT_GATE_THRESHOLD),
            "by_domain": {
                d: {"n": v["n"], "rate": v["ok"] / v["n"] if v["n"] else 0.0}
                for d, v in sorted(by_dom.items())
            },
        }

    forward_roundtrip: dict = {
        "description": "encode / soft / inject / Write→forward→Read metrics",
    }

    finals = by_phase.get("final", [])
    if finals:
        soft = [int(r["soft_keyword_hit"]) for r in finals]
        read = [int(r["read_keyword_hit"]) for r in finals]
        hybrid = [int(r.get("hybrid_ok")) for r in finals if "hybrid_ok" in r]
        cos = [r["roundtrip_cos"] for r in finals]
        soft_b = _rate_ci(soft)
        forward_roundtrip["final_soft"] = {
            **soft_b,
            "soft_keyword_hit_rate": soft_b["rate"],
            "soft_keyword_hit_ci95": soft_b["ci95"],
            "read_keyword_hit_rate": sum(read) / max(len(read), 1),
            "hybrid_ok_rate": sum(hybrid) / max(len(hybrid), 1) if hybrid else 0.0,
            "mean_roundtrip_cos": float(np.mean(cos)) if cos else 0.0,
            "p50_roundtrip_cos": percentile(cos, 50) if cos else 0.0,
        }

    fr = by_phase.get("forward_read", [])
    if fr:
        oks = [int(r.get("ok")) for r in fr]
        forward_roundtrip["forward_read"] = _rate_ci(oks)

    wfr = by_phase.get("write_forward_read", [])
    if wfr:
        oks = [int(r.get("ok")) for r in wfr]
        ok_kw = [int(r.get("ok_keyword")) for r in wfr if "ok_keyword" in r]
        by_path = defaultdict(lambda: {"n": 0, "ok": 0})
        for r in wfr:
            p = r.get("write_path") or "?"
            by_path[p]["n"] += 1
            by_path[p]["ok"] += int(bool(r.get("ok")))
        block = _rate_ci(oks)
        forward_roundtrip["write_forward_read"] = {
            **block,
            "keyword_rate": sum(ok_kw) / max(len(ok_kw), 1) if ok_kw else 0.0,
            "by_write_path": {
                p: {"n": v["n"], "rate": v["ok"] / v["n"] if v["n"] else 0.0}
                for p, v in sorted(by_path.items())
            },
        }

    ab = by_phase.get("inject_ab", [])
    if ab:
        by_var = defaultdict(list)
        for r in ab:
            if "keyword_hit" in r:
                by_var[r.get("variant") or "?"].append(int(r["keyword_hit"]))
        forward_roundtrip["inject_ab"] = {
            v: _rate_ci(flags) for v, flags in sorted(by_var.items())
        }

    layer_rows = [r for r in by_phase.get("layer", []) if "keyword_hit" in r]
    layer_matrix = {}
    if layer_rows:
        by_layer = defaultdict(list)
        by_dom_layer = defaultdict(lambda: defaultdict(list))
        for r in layer_rows:
            by_layer[r["layer"]].append(r)
            by_dom_layer[r.get("domain") or "?"][r["layer"]].append(int(r["keyword_hit"]))
        layer_stats = {}
        for L, lr in sorted(by_layer.items()):
            hits = [int(x["keyword_hit"]) for x in lr]
            cos = [x["inject_vs_encode_cos"] for x in lr]
            c, n = sum(hits), len(hits)
            lo, hi = wilson_ci(c, n)
            layer_stats[str(L)] = {
                "n": n,
                "keyword_hit_rate": c / max(n, 1),
                "keyword_hit_ci95": [lo, hi],
                "mean_inject_vs_encode_cos": float(np.mean(cos)) if cos else 0.0,
            }
        layer_matrix = {
            dom: {str(L): sum(v) / max(len(v), 1) for L, v in sorted(layers_d.items())}
            for dom, layers_d in sorted(by_dom_layer.items())
        }
        forward_roundtrip["layer"] = {
            "by_layer": layer_stats,
            "by_domain_layer": layer_matrix,
        }
    elif by_phase.get("layer"):
        forward_roundtrip["layer"] = {
            "error": by_phase["layer"][0].get("error", "unavailable"),
            "note": "Rebuild jcross_engine_glm so encode_layers/inject_at_layer are exported.",
        }

    # Backward-compatible phases block + dual gates
    summary = {
        "layers_probed": layers,
        "lexicon_gate": gate,
        "claim_boundary": CLAIM_BOUNDARY,
        "gates": {
            "lexicon_only": lexicon_only,
            "forward_roundtrip": forward_roundtrip,
        },
        "phases": {},
    }
    # Keep legacy phase keys for older report consumers
    if "final_soft" in forward_roundtrip:
        summary["phases"]["final"] = forward_roundtrip["final_soft"]
    if "suite_reproduce" in lexicon_only:
        summary["phases"]["lexicon"] = lexicon_only["suite_reproduce"]
    if "layer" in forward_roundtrip:
        summary["phases"]["layer"] = forward_roundtrip["layer"]
    if "forward_read" in forward_roundtrip:
        summary["phases"]["forward_read"] = forward_roundtrip["forward_read"]
    if "write_forward_read" in forward_roundtrip:
        summary["phases"]["write_forward_read"] = forward_roundtrip["write_forward_read"]
    if "inject_ab" in forward_roundtrip:
        summary["phases"]["inject_ab"] = forward_roundtrip["inject_ab"]

    if layer_matrix:
        summary["layer_routing_suggested"] = best_layer_by_domain(layer_matrix)

    return summary


def write_report(path, summary, args, elapsed):
    lines = [
        "# Codec Reconstruction Suite",
        "",
        f"- elapsed_s: {elapsed:.1f}",
        f"- model: `{DEFAULT_MODEL}`",
        f"- corpus: `{args.corpus}`",
        f"- max_items: {args.max_items or 'all'}",
        f"- layers: {summary.get('layers_probed')}",
        "",
        "## Claim boundary",
        "",
    ]
    for c in CLAIM_BOUNDARY:
        lines.append(f"- {c}")
    lines.append("")

    gates = summary.get("gates") or {}
    lo = gates.get("lexicon_only") or {}
    fr = gates.get("forward_roundtrip") or {}

    lines += ["## Gate: lexicon_only", ""]
    wr = lo.get("write_read_reproduce") or {}
    if wr:
        lines.append(
            f"- Write→Read reproduce: {wr.get('rate', 0)*100:.1f}% "
            f"({wr.get('correct', 0)}/{wr.get('n', 0)}) "
            f"pass={wr.get('pass')}"
        )
    hold = lo.get("holdout") or {}
    if hold:
        lines.append(
            f"- hold_acc: {hold.get('hold_acc', 0)*100:.1f}% "
            f"(soft={hold.get('hold_acc_soft', 0)*100:.1f}%, "
            f"domain={hold.get('hold_domain_acc', 0)*100:.1f}%, "
            f"n_hold={hold.get('n_hold', '?')})"
        )
    if lo.get("suite_reproduce"):
        lines.append("```json")
        lines.append(json.dumps(lo["suite_reproduce"], indent=2, ensure_ascii=False))
        lines.append("```")
    lines.append("")

    lines += ["## Gate: forward_roundtrip", ""]
    for key in ("final_soft", "forward_read", "write_forward_read", "inject_ab", "layer"):
        if key in fr:
            lines.append(f"### {key}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(fr[key], indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")

    if summary.get("layer_routing_suggested"):
        lines += [
            "## L3 suggested domain→layer routing",
            "",
            "```json",
            json.dumps(summary["layer_routing_suggested"], indent=2),
            "```",
            "",
        ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Codec layer×domain suite (dual gates)")
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--max-items", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--skip-layers", action="store_true")
    ap.add_argument("--build-lexicon", action="store_true")
    ap.add_argument("--gate-threshold", type=float, default=DEFAULT_GATE_THRESHOLD)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--layer-mode", choices=("early_mid_late", "quartile"),
                    default="early_mid_late")
    ap.add_argument("--inject-ab", action="store_true",
                    help="W2: A/B mid/late inject vs final")
    ap.add_argument("--forward-read", action="store_true", default=True,
                    help="R2: encode→Read proposition_match (default on)")
    ap.add_argument("--no-forward-read", action="store_true")
    ap.add_argument("--write-forward-read", action="store_true", default=True,
                    help="W4: Write→forward→Read (default on)")
    ap.add_argument("--no-write-forward-read", action="store_true")
    ap.add_argument("--save-layer-routing", action="store_true",
                    help="L3: persist domain→best layer from L2 matrix")
    ap.add_argument("--use-layer-routing", action="store_true",
                    help="Apply saved domain→layer routing on Write path")
    args = ap.parse_args()

    do_forward_read = args.forward_read and not args.no_forward_read
    do_wfr = args.write_forward_read and not args.no_write_forward_read

    np.random.seed(args.seed)
    items = load_propositions(args.corpus)
    if args.max_items and args.max_items > 0:
        items = stratified_sample(items, args.max_items, seed=args.seed)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out or os.path.join(ROOT, "benchmarks/results", f"codec_suite_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    print(f"[codec-suite] n={len(items)} out={out_dir}")
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(DEFAULT_MODEL, hidden=HIDDEN)
    dic = JGenDict(DEFAULT_MODEL)
    sem = dic.semantic_mask(tok)

    lex = ConceptLexicon()
    if args.build_lexicon or not lex.available:
        print("[codec-suite] building concept lexicon...")
        lex = ConceptLexicon.build(brain, tok, load_propositions(args.corpus))

    gate = write_read_reproduce(lex, items)
    gate["threshold"] = args.gate_threshold
    gate["pass"] = gate["rate"] >= args.gate_threshold
    print(f"[codec-suite] lexicon_only gate: {gate['rate']*100:.1f}% "
          f"{'PASS' if gate['pass'] else 'FAIL'} "
          f"(hold_acc={lex.hold_acc*100:.1f}%)")

    lex_hold = {
        "hold_acc": float(lex.hold_acc),
        "n": lex.size,
    }
    meta_path = os.path.join(
        os.path.dirname(lex.path), "concept_lexicon.meta.json"
    )
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            lex_hold.update({
                "hold_acc_soft": meta.get("hold_acc_soft", lex.hold_acc),
                "hold_domain_acc": meta.get("hold_domain_acc", 0.0),
                "n_hold": meta.get("n_hold"),
                "n_train": meta.get("n_train"),
            })
        except Exception:
            pass

    layers = [] if args.skip_layers else probe_layers(brain, args.layer_mode)
    if layers:
        print(f"[codec-suite] layer probes: {layers} (of {brain.num_layers})")
    else:
        print("[codec-suite] layer probes unavailable "
              "(FFI missing — rebuild jcross_engine_glm, or --skip-layers)")

    layer_routing = load_layer_routing() if args.use_layer_routing else None
    if layer_routing:
        print(f"[codec-suite] using layer routing: {layer_routing.get('by_domain', layer_routing)}")

    rows = []
    t0 = time.time()
    try:
        for i, item in enumerate(items):
            print(f"  [{i+1}/{len(items)}] {item['id']} ...", flush=True)
            rows.append(run_final_read_write(brain, dic, tok, sem, item, lex=lex))
            rows.append(run_lexicon_item(lex, item))
            if do_forward_read:
                rows.append(run_forward_read_gate(brain, tok, lex, item))
            if do_wfr:
                rows.append(run_write_forward_read(
                    brain, dic, tok, sem, lex, item,
                    layer_routing=layer_routing,
                ))
            if layers:
                rows.extend(run_layer_item(brain, dic, tok, sem, item, layers, lex=lex))
            if args.inject_ab and layers:
                # mid/late only for A/B
                nL = int(brain.num_layers or 0)
                ab_layers = sorted({max(0, (nL - 1) // 2), nL - 1}) if nL else layers[:2]
                rows.extend(run_inject_ab(brain, dic, tok, sem, item, ab_layers, lex=lex))
    finally:
        brain.close()

    elapsed = time.time() - t0
    summary = summarize(rows, gate, layers, lex_hold=lex_hold)
    summary["elapsed_s"] = elapsed
    summary["n_items"] = len(items)
    summary["model"] = DEFAULT_MODEL

    if args.save_layer_routing and summary.get("layer_routing_suggested"):
        payload = {
            "by_domain": summary["layer_routing_suggested"],
            "source": "codec_suite L2 matrix",
            "layers_probed": layers,
            "n_items": len(items),
        }
        path = save_layer_routing(payload)
        summary["layer_routing_saved"] = path
        print(f"[codec-suite] L3 routing saved → {path}")

    with open(os.path.join(out_dir, "detail.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    write_report(os.path.join(out_dir, "report.md"), summary, args, elapsed)

    print(f"[codec-suite] done in {elapsed:.1f}s → {out_dir}")
    lo = (summary.get("gates") or {}).get("lexicon_only") or {}
    fr = (summary.get("gates") or {}).get("forward_roundtrip") or {}
    if fr.get("write_forward_read"):
        print(f"[codec-suite] forward W→R: "
              f"{fr['write_forward_read']['rate']*100:.1f}%")
    if not gate["pass"]:
        print("[codec-suite] WARNING: lexicon_only gate failed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
