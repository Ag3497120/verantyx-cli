"""
verantyx_codec.py — 最終層隠れ状態 ⇔ 短い英語命題のコーデック補助
==============================================================================

命題辞書の本体は concept_lexicon.py。ここは Read/Write ルータと層プローブ点。

ゲートは二系統を分離する:
  lexicon_only      — Write→Read NN（フォワード不要）
  forward_roundtrip — encode / soft / inject → Read
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable, Optional, Sequence

import numpy as np

from concept_lexicon import (  # noqa: F401
    ConceptLexicon,
    DEFAULT_GATE,
    DEFAULT_GATE_THRESHOLD,
    LEXICON_PATH,
    build_lexicon,
    codec_enabled,
    encode_proposition as encode_proposition_eol,
    load_propositions,
    proposition_match,
    write_read_reproduce,
)
from verantyx_council import (
    dist_from_vector,
    dist_to_hidden,
    dist_to_soft_numpy,
    role_tokens,
)

CODEC_DIRECTIVE = (
    "You encode short English propositions into your hidden state. "
    "Respond with the proposition itself, nothing else."
)

# Hybrid Read: lexicon NN score above this → prefer lexicon label
DEFAULT_READ_THRESHOLD = 0.35

# Domain → preferred inject layer (filled by L2/L3; optional override)
LAYER_ROUTING_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".verantyx_chrono",
    "codec_layer_routing.json",
)


def _l2(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    return v / (np.linalg.norm(v) + 1e-8)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(_l2(a) @ _l2(b))


def proposition_tokens(tok, proposition: str):
    return role_tokens(tok, CODEC_DIRECTIVE, proposition)


def encode_proposition(brain, tok, proposition: str) -> np.ndarray:
    """命題 → 最終層隠れ (答えスロット ChatML)。"""
    return brain.encode(proposition_tokens(tok, proposition))


def read_dist(dictionary, tok, z, sem, top_k=48, temperature=1.0):
    return dist_from_vector(dictionary, tok, z, sem, top_k=top_k, temperature=temperature)


def top_strings(dist, k=8) -> list[str]:
    return [t for t, _ in dist[:k]]


def vocab_overlap(a: Iterable[str], b: Iterable[str]) -> float:
    A, B = set(a), set(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def write_soft(brain, tok, dictionary, proposition: str, carrier_ids=None,
               sem=None, top_k=48):
    """Write (分布経路): encode → dist → soft → encode_soft。Returns (z_src, z_out, dist)."""
    if sem is None:
        sem = dictionary.semantic_mask(tok)
    z_src = encode_proposition(brain, tok, proposition)
    dist = read_dist(dictionary, tok, z_src, sem, top_k=top_k)
    soft = dist_to_soft_numpy(dist, tok, dictionary._embed_f16)
    if carrier_ids is None:
        carrier_ids = proposition_tokens(tok, "Continue.")
    z_out = brain.encode_soft(soft[None, :], carrier_ids)
    return z_src, z_out, dist


def keyword_hit(proposition: str, tokens: list[str]) -> bool:
    import re
    words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", proposition)]
    if not words:
        return False
    blob = " ".join(tokens).lower()
    words.sort(key=len, reverse=True)
    return any(w in blob for w in words[:4])


def soft_keyword_hit(proposition: str, tokens: list[str],
                     keywords: Optional[Sequence[str]] = None) -> bool:
    """キーワード列があれば過半数ヒット、なければ proposition の語幹ヒット。"""
    if keywords:
        blob = " ".join(tokens).lower()
        hits = sum(1 for kw in keywords if kw.lower() in blob)
        return hits >= max(1, (len(keywords) + 1) // 2)
    return keyword_hit(proposition, tokens)


def roundtrip_metrics(z_src, z_out, dist_src, dist_out, proposition: str) -> dict:
    return {
        "cosine": _cosine(z_src, z_out),
        "topk_jaccard": vocab_overlap(top_strings(dist_src, 8), top_strings(dist_out, 8)),
        "keyword_repro": bool(keyword_hit(proposition, top_strings(dist_out, 16))),
        "top_src": top_strings(dist_src, 5),
        "top_out": top_strings(dist_out, 5),
    }


def layer_probe_points(num_layers: int) -> list[int]:
    """early / mid / late (0-indexed residual dumps)."""
    if num_layers <= 0:
        return [0]
    early = 0
    mid = max(0, (num_layers - 1) // 2)
    late = num_layers - 1
    pts = []
    for p in (early, mid, late):
        if p not in pts:
            pts.append(p)
    return pts


def layer_quartile_points(num_layers: int) -> list[int]:
    """Quartile dump points for L2 sweep (plus final-norm index = num_layers)."""
    if num_layers <= 0:
        return [0]
    qs = [0, num_layers // 4, num_layers // 2, (3 * num_layers) // 4, num_layers - 1]
    pts = []
    for p in qs:
        p = int(max(0, min(num_layers - 1, p)))
        if p not in pts:
            pts.append(p)
    return pts


# ── R1: Hybrid Read router ───────────────────────────────────────────────────

def hybrid_read(
    z: np.ndarray,
    lexicon: Optional[ConceptLexicon] = None,
    dictionary=None,
    tok=None,
    sem=None,
    threshold: float = DEFAULT_READ_THRESHOLD,
    top_k: int = 48,
) -> dict[str, Any]:
    """Prefer lexicon.read(z) above threshold; else dist_from_vector + semantic mask.

    Returns dict with keys: path ('lexicon'|'dist'), label/score or tokens/dist.
    """
    z = np.asarray(z, dtype=np.float32).reshape(-1)
    hits: list = []
    if lexicon is not None and getattr(lexicon, "available", False) and lexicon.size > 0:
        hits = lexicon.read(z, top_k=5)
        if hits and hits[0][1] >= threshold:
            return {
                "path": "lexicon",
                "label": hits[0][0],
                "score": float(hits[0][1]),
                "hits": hits,
                "tokens": [lab for lab, _ in hits],
            }
    if dictionary is None or tok is None:
        return {
            "path": "lexicon_below_threshold" if hits else "none",
            "label": hits[0][0] if hits else "",
            "score": float(hits[0][1]) if hits else 0.0,
            "hits": hits,
            "tokens": [lab for lab, _ in hits] if hits else [],
        }
    dist = read_dist(dictionary, tok, z, sem, top_k=top_k)
    return {
        "path": "dist",
        "dist": dist,
        "tokens": top_strings(dist, 16),
        "label": top_strings(dist, 1)[0] if dist else "",
        "score": float(dist[0][1]) if dist else 0.0,
    }


# ── W1: Write router ─────────────────────────────────────────────────────────

def write_router(
    proposition: str,
    brain=None,
    tok=None,
    dictionary=None,
    lexicon: Optional[ConceptLexicon] = None,
    sem=None,
    base: Optional[np.ndarray] = None,
    alpha: float = 1.0,
    mode: str = "replace",
    inject_layer: Optional[int] = None,
    carrier_ids=None,
    top_k: int = 48,
    domain: str = "",
    layer_routing: Optional[dict] = None,
) -> dict[str, Any]:
    """Known label → lexicon.write (+ optional inject); unknown → soft / dist_to_hidden.

    inject_layer: if set (and brain supports inject_at_layer), inject written z at layer.
    layer_routing: optional {domain: layer_int} from L3; used when inject_layer is None
                   and domain is provided.
    """
    prop = (proposition or "").strip()
    # Layer routing is opt-in via layer_routing arg (suite --use-layer-routing).
    # Do not silently load disk routing — that injects mid-layer and breaks lexicon Read.
    routing = layer_routing or {}
    if inject_layer is None and domain and routing:
        inj = routing.get("by_domain", routing).get(domain)
        if inj is not None:
            inject_layer = int(inj)

    known = bool(
        lexicon is not None
        and getattr(lexicon, "available", False)
        and prop in lexicon.labels
    )

    if known:
        if base is None:
            bn = 10.0
            base = (_l2(np.random.randn(lexicon.vectors.shape[1]).astype(np.float32)) * bn)
        z = lexicon.write(base, [prop], alpha=alpha, mode=mode)
        path = "lexicon"
        dist = None
        z_src = z
    else:
        if brain is None or tok is None or dictionary is None:
            raise ValueError("unknown proposition requires brain/tok/dictionary for soft path")
        if sem is None:
            sem = dictionary.semantic_mask(tok)
        z_src, z_soft, dist = write_soft(
            brain, tok, dictionary, prop, carrier_ids=carrier_ids, sem=sem, top_k=top_k
        )
        # Also offer dist_to_hidden as an alternate Write (Council pattern)
        base_norm = float(np.linalg.norm(z_src)) + 1e-8
        z_hidden = dist_to_hidden(dictionary, tok, dist, base_norm)
        z = z_hidden if z_hidden is not None else z_soft
        path = "soft"
        z = z.astype(np.float32)

    injected = False
    z_final = z
    if (
        inject_layer is not None
        and brain is not None
        and tok is not None
        and hasattr(brain, "inject_at_layer")
    ):
        try:
            ids = carrier_ids or proposition_tokens(tok, "Continue.")
            z_final = brain.inject_at_layer(ids, int(inject_layer), z, alpha=1.0)
            injected = True
        except (RuntimeError, AttributeError):
            z_final = z
            injected = False

    return {
        "path": path,
        "z": np.asarray(z_final, dtype=np.float32),
        "z_pre_inject": np.asarray(z, dtype=np.float32),
        "z_src": np.asarray(z_src, dtype=np.float32),
        "dist": dist,
        "injected": injected,
        "inject_layer": inject_layer,
        "known": known,
        "proposition": prop,
    }


# ── W4: end-to-end Write → forward → Read ────────────────────────────────────

def write_forward_read(
    proposition: str,
    brain,
    tok,
    dictionary,
    lexicon: Optional[ConceptLexicon] = None,
    sem=None,
    keywords: Optional[Sequence[str]] = None,
    read_threshold: float = DEFAULT_READ_THRESHOLD,
    inject_layer: Optional[int] = None,
    domain: str = "",
    layer_routing: Optional[dict] = None,
) -> dict[str, Any]:
    """Primary forward metric: Write router → hybrid Read → proposition_match / keyword."""
    if sem is None and dictionary is not None:
        sem = dictionary.semantic_mask(tok)
    wr = write_router(
        proposition,
        brain=brain,
        tok=tok,
        dictionary=dictionary,
        lexicon=lexicon,
        sem=sem,
        inject_layer=inject_layer,
        domain=domain,
        layer_routing=layer_routing,
    )
    # Lexicon Write stays on lexicon Read (do not fall through to dist after a clean write).
    if wr["path"] == "lexicon" and lexicon is not None and lexicon.available:
        pred, score = lexicon.top1(wr["z"])
        tokens = [lab for lab, _ in lexicon.read(wr["z"], top_k=5)]
        rd = {
            "path": "lexicon",
            "label": pred,
            "score": float(score),
            "tokens": tokens,
        }
    else:
        rd = hybrid_read(
            wr["z"],
            lexicon=lexicon,
            dictionary=dictionary,
            tok=tok,
            sem=sem,
            threshold=read_threshold,
        )
    pred = rd.get("label") or ""
    tokens = rd.get("tokens") or []
    ok_label = proposition_match(pred, proposition, keywords)
    ok_kw = soft_keyword_hit(proposition, tokens, keywords)
    return {
        "write_path": wr["path"],
        "read_path": rd.get("path"),
        "pred": pred,
        "tokens": tokens[:8],
        "ok_label": ok_label,
        "ok_keyword": ok_kw,
        "ok": bool(ok_label or ok_kw),
        "inject_layer": wr.get("inject_layer"),
        "injected": wr.get("injected"),
        "score": rd.get("score", 0.0),
    }


# ── L3: domain → layer routing ───────────────────────────────────────────────

def load_layer_routing(path: str = LAYER_ROUTING_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_layer_routing(payload: dict, path: str = LAYER_ROUTING_PATH) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def best_layer_by_domain(matrix: dict) -> dict[str, int]:
    """From L2 by_domain_layer {domain: {layer: rate}} pick argmax layer per domain."""
    out: dict[str, int] = {}
    for dom, layers in (matrix or {}).items():
        if not layers:
            continue
        best_L, best_r = None, -1.0
        for L, rate in layers.items():
            r = float(rate) if not isinstance(rate, dict) else float(rate.get("rate", 0))
            Li = int(L)
            if r > best_r or (r == best_r and (best_L is None or Li < best_L)):
                best_L, best_r = Li, r
        if best_L is not None:
            out[dom] = best_L
    return out
