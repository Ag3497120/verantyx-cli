"""static_jgen_dict.py — 大型 jgen を発火なし静的辞書として開く
==============================================================================

generate() は呼ばない。使えるもの:

  JGenDict (mmap)
    - embed_tokens / lm_head 行へのアクセス
    - logits(z) → 語彙分布 (z の hidden が一致する場合のみ)
    - resonance / to_embedding

使えない / 弱いもの:
  - 多トークンの事実回答 (KB ではない)
  - 計算の確定 (電卓レーンへ)
  - ルーターの z を大型 lm_head に直接掛ける (次元不一致)

環境変数:
  VERANTYX_STATIC_DICT_JGEN=/path/to/large.jgen
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

Dist = List[Tuple[str, float]]

_CACHE: Dict[str, Any] = {}


def configured_path() -> Optional[str]:
    p = (os.environ.get("VERANTYX_STATIC_DICT_JGEN") or "").strip()
    if p and os.path.isfile(p):
        return p
    return None


def open_static_dict(path: Optional[str] = None, *, quiet: bool = True):
    """JGenDict のみ開く (RustBrain / generate なし)。"""
    path = path or configured_path()
    if not path:
        return None
    if path in _CACHE:
        return _CACHE[path]
    try:
        from verantyx_mind import JGenDict
        d = JGenDict(path)
        _CACHE[path] = d
        if not quiet:
            print(f"[StaticDict] opened {path} vocab={d.vocab_size} hidden={d.hidden}")
        return d
    except Exception as e:
        if not quiet:
            print(f"[StaticDict] open failed: {e}")
        return None


def project_z_to_dist(dictionary, tok, z, *, top_k: int = 24) -> Dist:
    """同一 hidden の z を語彙分布へ (発火なし)。"""
    if dictionary is None or tok is None or z is None:
        return []
    try:
        from verantyx_council import dist_from_vector, sharpen_dist
        sem = dictionary.semantic_mask(tok) if hasattr(dictionary, "semantic_mask") else None
        return sharpen_dist(dist_from_vector(dictionary, tok, z, sem, top_k=top_k))
    except Exception:
        return []


def feasibility_note() -> Dict[str, Any]:
    return {
        "vocab_grounding": 8,
        "factual_recall": 3,
        "numeric": 2,
        "means": "JGenDict mmap + logits(z); no generate()",
        "requires": "z.hidden == dict.hidden (encode in that model, or same-family)",
        "env": "VERANTYX_STATIC_DICT_JGEN",
        "lane_advice": (
            "Use on relational/factual for soft vocab bias only; "
            "never as determinate ground — use task_lanes lock instead. "
            "Council blends: relational≈0.35, factual≈0.22, default≈0.18."
        ),
    }


def relational_vocab_bias(
    dist: Dist,
    question: str,
    *,
    router_z=None,
    router_hidden: Optional[int] = None,
    tok=None,
    path: Optional[str] = None,
) -> Tuple[Dist, Dict[str, Any]]:
    """relational レーン専用の厚め語彙バイアス。"""
    return enrich_dist_with_static(
        dist, question,
        router_z=router_z, router_hidden=router_hidden,
        tok=tok, path=path, blend=0.35,
    )


def enrich_dist_with_static(
    dist: Dist,
    question: str,
    *,
    router_z=None,
    router_hidden: Optional[int] = None,
    tok=None,
    path: Optional[str] = None,
    blend: float = 0.25,
) -> Tuple[Dist, Dict[str, Any]]:
    """任意: 静的大型辞書で語彙接地を薄く混ぜる (確定レーンでは呼ばないこと)。"""
    meta = {"used": False}
    d = open_static_dict(path, quiet=True)
    if d is None or tok is None or router_z is None:
        return list(dist or []), meta
    if router_hidden is not None and int(d.hidden) != int(router_hidden):
        meta["skipped"] = f"hidden mismatch dict={d.hidden} router={router_hidden}"
        return list(dist or []), meta
    try:
        import numpy as np
        z = np.asarray(router_z, dtype=np.float32).ravel()
        if z.shape[0] != int(d.hidden):
            meta["skipped"] = "z dim mismatch"
            return list(dist or []), meta
        other = project_z_to_dist(d, tok, z)
        if not other:
            return list(dist or []), meta
        # 薄いブレンド (確定ロックは壊さない前提で呼ぶ側が保証)
        from abstract_link import _blend_dists
        blended = _blend_dists(dist or [], other, wa=1.0 - blend, wb=blend)
        meta.update({"used": True, "path": configured_path() or path, "top": other[:4]})
        return blended, meta
    except Exception as e:
        meta["error"] = str(e)[:120]
        return list(dist or []), meta
