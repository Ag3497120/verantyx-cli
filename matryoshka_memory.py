"""matryoshka_memory.py — L1–L3 をマトリョーシカ立体十字として再定義
==============================================================================

方針:
  - 記憶の正本は入れ子 CrossNode (外側=粗いアンカー、内側=細かい葉)
  - 深さは thinking 的予算 (段数ハードキャップ + トークン軟制限)
  - 検索は外側優先。長い／争点／予算ありのときだけ内側を expand
  - 窓に収まらなければ内側を再 wrap して圧縮

env:
  VERANTYX_MATRYOSHKA_MEMORY=1     刻印・想起で入れ子を使う
  VERANTYX_MEMORY_THINK=0|1|2      既定の想起深度モード
  VERANTYX_MEMORY_TOKEN_BUDGET=512 想起に使ってよいおおよそ文字/トークン予算
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ── 予算 (thinking 的バルブ) ──────────────────────────────────────────────

@dataclass
class MemoryDepthBudget:
    """想起・展開の予算。

    think_level:
      0 … 外側のみ (L3 アンカー相当)
      1 … 一段内側まで (L2 相当)
      2 … 葉まで予算の許す限り (L1 相当)
    """
    think_level: int = 0
    max_scale_open: int = 1          # ハードキャップ (開いてよい親子段数)
    token_budget: int = 512          # 軟制限 (おおよそ文字数≈token 粗い近似)
    expand_if_long: int = 180        # 外側テキストがこれ超で一段開く候補
    expand_if_contested: bool = True
    prefer_audited: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "think_level": self.think_level,
            "max_scale_open": self.max_scale_open,
            "token_budget": self.token_budget,
            "expand_if_long": self.expand_if_long,
            "expand_if_contested": self.expand_if_contested,
            "prefer_audited": self.prefer_audited,
        }


def matryoshka_memory_enabled() -> bool:
    v = (os.environ.get("VERANTYX_MATRYOSHKA_MEMORY") or "").strip().lower()
    return v in ("1", "on", "true", "yes")


def budget_from_env(*, think_override: Optional[int] = None) -> MemoryDepthBudget:
    lvl = 0
    try:
        if think_override is not None:
            lvl = int(think_override)
        else:
            lvl = int(os.environ.get("VERANTYX_MEMORY_THINK") or "0")
    except Exception:
        lvl = 0
    lvl = max(0, min(2, lvl))
    tok = 512
    try:
        tok = max(64, int(os.environ.get("VERANTYX_MEMORY_TOKEN_BUDGET") or "512"))
    except Exception:
        pass
    # think_level → 開いてよい段数
    max_open = {0: 0, 1: 1, 2: 3}.get(lvl, 0)
    return MemoryDepthBudget(
        think_level=lvl,
        max_scale_open=max_open,
        token_budget=tok,
    )


def budget_for_council(council, *, question: str = "") -> MemoryDepthBudget:
    """council の /think やレーンから想起予算を推定。"""
    b = budget_from_env()
    # bridge / sage の allow_thinking が onboard なら一段深く
    try:
        deep = False
        for br in list(getattr(council, "_bridges", None) or []):
            if getattr(br, "allow_thinking", False):
                deep = True
        if deep:
            b.think_level = max(b.think_level, 1)
            b.max_scale_open = max(b.max_scale_open, 1)
    except Exception:
        pass
    # contested / multihop っぽい問い
    q = (question or "").lower()
    if any(h in q for h in ("why", "how did", "after that", "then ", "therefore")):
        b.think_level = max(b.think_level, 1)
        b.max_scale_open = max(b.max_scale_open, 1)
    return b


# ── Cross 木のシリアライズ ────────────────────────────────────────────────

def cross_to_tree(node) -> Dict[str, Any]:
    """CrossNode → 入れ子 dict (永続用)。"""
    if node is None:
        return {}
    return {
        "id": getattr(node, "id", ""),
        "question": (getattr(node, "question", None) or "")[:240],
        "scale": int(getattr(node, "scale", 0) or 0),
        "source": getattr(node, "source", "") or "",
        "confidence": float(getattr(node, "confidence", 0.5) or 0.5),
        "axis_sig": list(node.axis_sig) if getattr(node, "axis_sig", None) is not None else None,
        "dist": [[s, float(w)] for s, w in (getattr(node, "dist", None) or [])[:16]],
        "concepts": list(getattr(node, "concepts", None) or [])[:10],
        "propositions": list(getattr(node, "propositions", None) or [])[:8],
        "edges": list(getattr(node, "edges", None) or [])[:24],
        "meta": dict(getattr(node, "meta", None) or {}),
        "children": [cross_to_tree(c) for c in (getattr(node, "children", None) or [])],
    }


def tree_to_cross(d: Dict[str, Any]):
    """入れ子 dict → CrossNode。"""
    from matryoshka_cross import CrossNode
    if not d:
        return None
    children = [tree_to_cross(c) for c in (d.get("children") or []) if c]
    children = [c for c in children if c is not None]
    dist = []
    for item in d.get("dist") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            dist.append((str(item[0]), float(item[1])))
    return CrossNode(
        id=d.get("id") or "cx_anon",
        question=d.get("question") or "",
        scale=int(d.get("scale") or 0),
        axis_sig=list(d["axis_sig"]) if d.get("axis_sig") is not None else None,
        dist=dist,
        concepts=list(d.get("concepts") or []),
        propositions=list(d.get("propositions") or []),
        confidence=float(d.get("confidence") or 0.5),
        source=d.get("source") or "matryoshka",
        children=children,
        edges=list(d.get("edges") or []),
        meta=dict(d.get("meta") or {}),
    )


def estimate_tokens(text: str) -> int:
    """粗いトークン近似 (空白分割 + CJK 文字)。"""
    if not text:
        return 0
    # 英単語 + 各CJKを1
    latin = len(re.findall(r"[A-Za-z0-9_]+", text))
    cjk = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text))
    other = max(0, len(text) // 4)
    return max(latin + cjk, other)


def node_surface_text(node) -> str:
    parts = [
        getattr(node, "question", "") or "",
        " ".join(getattr(node, "concepts", None) or []),
        " ".join(getattr(node, "propositions", None) or []),
        " ".join(s for s, _ in (getattr(node, "dist", None) or [])[:6]),
    ]
    return " | ".join(p for p in parts if p)


def truth_status_of(node) -> str:
    meta = getattr(node, "meta", None) or {}
    return str(meta.get("truth_status") or meta.get("auditor", {}).get("verdict")
               or "unreviewed")


# ── 刻印: Cross → MemoryGraph (入れ子を meta に格納) ──────────────────────

def pack_cross_to_graph(cross, *, l3_text: str = "", kind: str = "matryoshka_cross",
                        truth_status: str = "unreviewed"):
    """外側アンカー + 木全体を MemoryGraph にパック。"""
    from memory_graph import MemoryGraph, AXIS_KEYS
    if cross is None:
        return None
    # 外側は cross.to_memory_graph 相当 + tree
    axes = {}
    if getattr(cross, "axis_sig", None) is not None:
        for i, k in enumerate(AXIS_KEYS):
            if i < len(cross.axis_sig):
                axes[k] = float(cross.axis_sig[i])
    grounds = []
    for g in (cross.meta or {}).get("grounds") or []:
        if isinstance(g, str):
            grounds.append(g[:160])
    tree = cross_to_tree(cross)
    mg = MemoryGraph(
        axes=axes,
        concepts=list(cross.concepts or [])[:10],
        propositions=list(cross.propositions or [])[:8],
        candidates=list(cross.dist or [])[:12],
        grounds=grounds[:8],
        edges=list(cross.edges or [])[:24],
        l3_text=(l3_text or f"[nest s={cross.scale}] {(cross.question or '')[:160]}")[:400],
        kind=kind,
        confidence=float(cross.confidence or 0.5),
        meta={
            "matryoshka": True,
            "cross_id": cross.id,
            "scale": int(cross.scale or 0),
            "n_children": len(cross.children or []),
            "truth_status": truth_status,
            "cross_tree": tree,
            "schema": "verantyx.matryoshka_cross.v1",
        },
    )
    return mg


def unpack_graph_to_cross(graph):
    """MemoryGraph / dict → CrossNode 木。"""
    if graph is None:
        return None
    if hasattr(graph, "meta"):
        meta = graph.meta or {}
        tree = meta.get("cross_tree")
        if tree:
            return tree_to_cross(tree)
        # flat graph → 葉
        from matryoshka_cross import CrossNode
        sig = graph.axis_sig_list() if hasattr(graph, "axis_sig_list") else None
        return CrossNode.leaf(
            graph.l3_text or "",
            dist=list(graph.candidates or []),
            axis_sig=sig,
            concepts=list(graph.concepts or []),
            propositions=list(graph.propositions or []),
            confidence=float(graph.confidence or 0.5),
            source="flat_graph",
            meta=dict(meta),
        )
    if isinstance(graph, dict):
        meta = graph.get("meta") or {}
        if meta.get("cross_tree"):
            return tree_to_cross(meta["cross_tree"])
    return None


def remember_matryoshka(memory, cross, *, question: str = "", answer: str = "",
                        vector=None, truth_status: str = "unreviewed",
                        quiet: bool = True) -> Optional[Dict[str, Any]]:
    """入れ子十字を永遠記憶へ。"""
    if memory is None or not getattr(memory, "enabled", False) or cross is None:
        return None
    label = f"Q: {question}  →  A: {answer}" if (question or answer) else ""
    mg = pack_cross_to_graph(
        cross, l3_text=label or None, truth_status=truth_status)
    if mg is None:
        return None
    try:
        rec = memory.add_graph(mg, vector=vector, quiet=quiet)
        return {"ok": True, "id": (rec or {}).get("id"),
                "scale": cross.scale, "n_children": len(cross.children or [])}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


# ── 想起: 外側優先 + 予算で expand ────────────────────────────────────────

@dataclass
class ExpandedView:
    """発話・検索に渡す展開結果。"""
    texts: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    propositions: List[str] = field(default_factory=list)
    grounds: List[str] = field(default_factory=list)
    scale_opened: int = 0
    tokens_used: int = 0
    truncated: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    def as_memory_texts(self) -> List[str]:
        return list(self.texts)[:6]


def _should_expand(node, budget: MemoryDepthBudget, depth_opened: int) -> bool:
    if depth_opened >= budget.max_scale_open:
        return False
    if not getattr(node, "children", None):
        return False
    surface = node_surface_text(node)
    long = estimate_tokens(surface) >= budget.expand_if_long // 2 or len(surface) >= budget.expand_if_long
    status = truth_status_of(node)
    contested = status in ("contested", "uncertain", "unreviewed", "incorrect")
    if budget.think_level >= 2:
        return True
    if budget.think_level >= 1 and (long or (budget.expand_if_contested and contested)):
        return True
    if long and budget.think_level >= 0 and depth_opened == 0 and budget.max_scale_open >= 1:
        # 外側が長いときだけ一段 (think0 でも max_open が許せば)
        return budget.max_scale_open >= 1 and long
    return False


def tree_token_estimate(node, *, max_depth: int = 8) -> int:
    """木全体のおおよそトークン量 (深さ上限付き)。"""
    if node is None or max_depth < 0:
        return 0
    total = estimate_tokens(node_surface_text(node))
    for ch in (getattr(node, "children", None) or []):
        total += tree_token_estimate(ch, max_depth=max_depth - 1)
    return total


def rewrap_for_budget(root, budget: Optional[MemoryDepthBudget] = None):
    """窓に収まらない深い木を、外側アンカー + 要約葉に畳む。

    expand 側の省略と対になる「刻印前圧縮」。葉が多すぎるとき wrap し直す。
    """
    from matryoshka_cross import CrossNode, wrap
    budget = budget or budget_from_env()
    if root is None:
        return None
    est = tree_token_estimate(root)
    if est <= budget.token_budget and len(getattr(root, "children", None) or []) <= 6:
        return root
    # 子を信頼度順に残し、余りは 1 葉に畳む
    kids = sorted(
        list(root.children or []),
        key=lambda c: float(getattr(c, "confidence", 0) or 0),
        reverse=True,
    )
    keep_n = max(1, min(4, budget.max_scale_open + 2))
    kept = kids[:keep_n]
    rest = kids[keep_n:]
    if rest:
        summary = CrossNode.leaf(
            f"collapsed {len(rest)} inner crosses",
            concepts=_uniq_concepts([c for ch in rest for c in (ch.concepts or [])]),
            propositions=[
                f"Collapsed {len(rest)} nodes under budget={budget.token_budget}"
            ],
            confidence=min(float(c.confidence or 0.5) for c in rest),
            source="matryoshka_rewrap",
            meta={"truth_status": "unreviewed", "collapsed": len(rest)},
        )
        kept.append(summary)
    if not kept:
        return root
    parent = wrap(
        kept,
        question=getattr(root, "question", "") or "",
        source="matryoshka_rewrap",
    )
    parent.meta = dict(getattr(root, "meta", None) or {})
    parent.meta["rewrapped"] = True
    parent.meta["prev_estimate"] = est
    parent.meta["truth_status"] = truth_status_of(root)
    # 外側アンカー情報を温存
    if getattr(root, "dist", None):
        parent.dist = list(root.dist)[:12]
    if getattr(root, "axis_sig", None) is not None:
        parent.axis_sig = list(root.axis_sig)
    parent.concepts = _uniq_concepts(
        list(root.concepts or []) + list(parent.concepts or []))
    return parent


def _uniq_concepts(items: Sequence[str], limit: int = 8) -> List[str]:
    out: List[str] = []
    for x in items:
        s = (x or "").strip()
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def expand_for_budget(
    root,
    budget: Optional[MemoryDepthBudget] = None,
    *,
    question: str = "",
) -> ExpandedView:
    """外側から読み、予算内で内側を開く。超過したら開かない (再wrap相当=省略)。"""
    budget = budget or budget_from_env()
    view = ExpandedView(meta={"budget": budget.as_dict(), "question": question[:120]})
    if root is None:
        return view

    def walk(node, depth_opened: int):
        if node is None:
            return
        status = truth_status_of(node)
        if budget.prefer_audited and status in ("incorrect",):
            # 誤判定ノードはスキップ気味
            pass
        surf = node_surface_text(node)
        # 外側アンカーを先に計上
        chunk = f"[s={getattr(node, 'scale', 0)}|{status}] {surf}"[:400]
        cost = estimate_tokens(chunk)
        if view.tokens_used + cost > budget.token_budget and view.texts:
            view.truncated = True
            return
        view.texts.append(chunk)
        view.tokens_used += cost
        view.scale_opened = max(view.scale_opened, depth_opened)
        for c in (getattr(node, "concepts", None) or [])[:4]:
            if c not in view.concepts:
                view.concepts.append(c)
        for p in (getattr(node, "propositions", None) or [])[:3]:
            if p not in view.propositions:
                view.propositions.append(p)
        for g in ((getattr(node, "meta", None) or {}).get("grounds") or [])[:2]:
            if str(g) not in view.grounds:
                view.grounds.append(str(g)[:120])

        if _should_expand(node, budget, depth_opened):
            # 子を信頼度順に、予算が続く限り
            kids = sorted(
                list(node.children or []),
                key=lambda c: float(getattr(c, "confidence", 0) or 0),
                reverse=True,
            )
            for ch in kids:
                if view.tokens_used >= budget.token_budget:
                    view.truncated = True
                    break
                walk(ch, depth_opened + 1)

    walk(root, 0)
    view.concepts = view.concepts[:10]
    view.propositions = view.propositions[:8]
    view.grounds = view.grounds[:8]
    view.texts = view.texts[:8]
    return view


def nest_status(council=None) -> Dict[str, Any]:
    """CLI /mem nest 用の状態。"""
    b = budget_from_env()
    if council is not None:
        b = budget_for_council(council)
    last = getattr(council, "_last_matryoshka", None) if council is not None else None
    return {
        "enabled": matryoshka_memory_enabled(),
        "budget": b.as_dict(),
        "env": {
            "VERANTYX_MATRYOSHKA_MEMORY": os.environ.get("VERANTYX_MATRYOSHKA_MEMORY", ""),
            "VERANTYX_MEMORY_THINK": os.environ.get("VERANTYX_MEMORY_THINK", "0"),
            "VERANTYX_MEMORY_TOKEN_BUDGET": os.environ.get(
                "VERANTYX_MEMORY_TOKEN_BUDGET", "512"),
        },
        "last_etch": last,
        "thesis": (
            "eternal memory = nested CrossNode (outer anchor → inner leaves); "
            "depth budget like thinking; expand uncontested outer-first"
        ),
    }


def recall_matryoshka(
    memory,
    question: str,
    *,
    budget: Optional[MemoryDepthBudget] = None,
    k: int = 3,
    council=None,
) -> ExpandedView:
    """search_graph → 外側 hit → 予算展開。"""
    budget = budget or (
        budget_for_council(council, question=question) if council is not None
        else budget_from_env())
    view = ExpandedView(meta={"budget": budget.as_dict()})
    if memory is None or not getattr(memory, "enabled", False):
        view.meta["skipped"] = "memory_off"
        return view
    try:
        from memory_graph import MemoryGraph
        qg = MemoryGraph(
            l3_text=question[:160],
            concepts=(question or "").split()[:6],
            kind="matryoshka_query",
        )
        hits = memory.search_graph(qg, k=k, min_score=0.05) if hasattr(memory, "search_graph") else []
    except Exception as e:
        view.meta["error"] = str(e)[:120]
        return view
    if not hits:
        view.meta["n_hits"] = 0
        return view
    view.meta["n_hits"] = len(hits)
    for g, scores, rec in hits:
        root = unpack_graph_to_cross(g)
        if root is None:
            # flat fallback
            t = (getattr(g, "l3_text", None) or rec.get("l3_text") or "")[:240]
            if t and view.tokens_used < budget.token_budget:
                view.texts.append(t)
                view.tokens_used += estimate_tokens(t)
            continue
        part = expand_for_budget(root, budget, question=question)
        for t in part.texts:
            if view.tokens_used >= budget.token_budget:
                view.truncated = True
                break
            view.texts.append(t)
            view.tokens_used += estimate_tokens(t)
        for c in part.concepts:
            if c not in view.concepts:
                view.concepts.append(c)
        view.scale_opened = max(view.scale_opened, part.scale_opened)
        if view.truncated:
            break
    return view


def build_nested_from_company(cross_root, *, answer: str = "", question: str = "",
                              budget: Optional[MemoryDepthBudget] = None):
    """company の cross をそのまま入れ子正本に。無ければ answer 葉を wrap。

    予算超過時は rewrap_for_budget で内側を畳む。
    """
    from matryoshka_cross import CrossNode, wrap
    budget = budget or budget_from_env()
    if cross_root is not None:
        # 監査メタの芽
        cross_root.meta = dict(cross_root.meta or {})
        if answer:
            cross_root.meta.setdefault("answer_anchor", answer[:200])
        return rewrap_for_budget(cross_root, budget)
    leaf = CrossNode.leaf(
        question or "",
        dist=[(answer, 1.0)] if answer else [],
        concepts=[answer] if answer else [],
        propositions=[f"A: {answer}"] if answer else [],
        source="answer_leaf",
        meta={"truth_status": "unreviewed"},
    )
    if answer:
        nested = wrap([leaf], question=question or answer, source="matryoshka_wrap")
        return rewrap_for_budget(nested, budget)
    return leaf
