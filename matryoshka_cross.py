"""matryoshka_cross.py — 立体十字のフラクタル接続 (並べる / 包む)
==============================================================================

同じスキーマのノードをスケール不変のタイルとして扱う:

  arrange  … 横: 同型ノードを辺で並べる (support / rival / peer)
  wrap     … 縦: 部分集合を親十字の 1 ノードに包む (マトリョーシカ)

頭打ち判定 (plateau) のあと wrap → また arrange、を繰り返せば
軸種を増やさずに接続を伸ばせる。

  vector → CrossNode (中解像・同型) → AbstractCanvas / MemoryGraph → language

生 z はノードに載せない。境界は dist / axis_sig / concepts / propositions。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import uuid

import numpy as np

from memory_graph import AXIS_KEYS

Dist = List[Tuple[str, float]]

# 親十字の 6 スロット名 (内側集合の役割タグと対応させられる)
PARENT_SLOTS = list(AXIS_KEYS)


def _new_id(prefix: str = "cx") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _blend_dists(dists: Sequence[Dist], weights: Optional[Sequence[float]] = None) -> Dist:
    if not dists:
        return []
    if weights is None:
        weights = [1.0] * len(dists)
    wsum = float(sum(weights)) or 1.0
    acc: Dict[str, float] = {}
    for dist, w in zip(dists, weights):
        ww = float(w) / wsum
        for s, p in dist or []:
            k = (s or "").strip()
            if k:
                acc[k] = acc.get(k, 0.0) + float(p) * ww
    if not acc:
        return []
    tot = sum(acc.values()) or 1.0
    return sorted(((k, v / tot) for k, v in acc.items()), key=lambda x: -x[1])[:48]


def _mean_sig(sigs: Sequence[Optional[Sequence[float]]]) -> Optional[List[float]]:
    arrs = []
    for s in sigs:
        if s is None:
            continue
        a = np.asarray(list(s) + [0.0] * 6, dtype=np.float32)[:6]
        n = float(np.linalg.norm(a) + 1e-8)
        arrs.append(a / n)
    if not arrs:
        return None
    m = np.mean(arrs, axis=0)
    n = float(np.linalg.norm(m) + 1e-8)
    return (m / n).tolist()


def _uniq(seq: Sequence[str], limit: int = 8) -> List[str]:
    out, seen = [], set()
    for x in seq or []:
        t = (x or "").strip()
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
        if len(out) >= limit:
            break
    return out


@dataclass
class CrossNode:
    """立体十字 1 ノード。どのスケールでも同スキーマ。

    scale=0 … 葉 (単一 puzzle / 役割 canvas)
    scale=k … 内側に children を持つ包みノード
    """

    id: str
    question: str
    scale: int = 0
    axis_sig: Optional[List[float]] = None
    dist: Dist = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    propositions: List[str] = field(default_factory=list)
    confidence: float = 0.5
    source: str = "cross"
    children: List["CrossNode"] = field(default_factory=list)
    # 横並びの辺: {from_id, to_id, rel, weight?}
    edges: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    # ── 構築 ──────────────────────────────────────────────────────────────
    @classmethod
    def leaf(
        cls,
        question: str,
        *,
        dist: Optional[Dist] = None,
        axis_sig: Optional[Sequence[float]] = None,
        concepts: Optional[Sequence[str]] = None,
        propositions: Optional[Sequence[str]] = None,
        confidence: float = 0.5,
        source: str = "leaf",
        node_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "CrossNode":
        return cls(
            id=node_id or _new_id("leaf"),
            question=question,
            scale=0,
            axis_sig=list(axis_sig) if axis_sig is not None else None,
            dist=list(dist or []),
            concepts=_uniq(concepts or []),
            propositions=_uniq(propositions or [], limit=8),
            confidence=float(confidence),
            source=source,
            meta=dict(meta or {}),
        )

    @classmethod
    def from_canvas(cls, canvas, *, source: Optional[str] = None) -> "CrossNode":
        """AbstractCanvas → 葉ノード。"""
        src = source or getattr(canvas, "source", None) or "canvas"
        return cls.leaf(
            getattr(canvas, "question", "") or "",
            dist=getattr(canvas, "dist", None),
            axis_sig=getattr(canvas, "axis_sig", None),
            concepts=getattr(canvas, "concepts", None),
            propositions=getattr(canvas, "propositions", None),
            confidence=float(getattr(canvas, "confidence", 0.5) or 0.5),
            source=str(src),
            meta=dict(getattr(canvas, "meta", None) or {}),
        )

    def to_canvas(self):
        from abstract_link import AbstractCanvas
        grounds = list((self.meta or {}).get("grounds") or [])
        return AbstractCanvas(
            question=self.question,
            axis_sig=list(self.axis_sig) if self.axis_sig is not None else None,
            dist=list(self.dist),
            concepts=list(self.concepts),
            propositions=list(self.propositions),
            pattern_hits=grounds[:6],
            confidence=self.confidence,
            source=self.source,
            meta={
                **dict(self.meta),
                "cross_id": self.id,
                "cross_scale": self.scale,
                "n_children": len(self.children),
            },
        )

    def to_memory_graph(self, *, l3_text: str = "", kind: str = "cross"):
        from memory_graph import MemoryGraph
        axes = {}
        if self.axis_sig is not None:
            for i, k in enumerate(AXIS_KEYS):
                if i < len(self.axis_sig):
                    axes[k] = float(self.axis_sig[i])
        grounds = []
        for g in (self.meta or {}).get("grounds") or []:
            # "obsidian:path" → path
            if isinstance(g, str) and g.startswith("obsidian:"):
                grounds.append(g.split(":", 1)[1])
            elif isinstance(g, str):
                grounds.append(g[:160])
        g = MemoryGraph(
            axes=axes,
            concepts=list(self.concepts),
            propositions=list(self.propositions),
            candidates=list(self.dist),
            grounds=grounds[:8],
            edges=list(self.edges),
            l3_text=l3_text or f"cross:{self.id} q={self.question[:80]}",
            kind=kind,
            confidence=self.confidence,
            meta={
                "cross_id": self.id,
                "scale": self.scale,
                "source": self.source,
                "n_children": len(self.children),
            },
        )
        return g

    def clone(self) -> "CrossNode":
        return CrossNode(
            id=self.id,
            question=self.question,
            scale=self.scale,
            axis_sig=list(self.axis_sig) if self.axis_sig is not None else None,
            dist=list(self.dist),
            concepts=list(self.concepts),
            propositions=list(self.propositions),
            confidence=self.confidence,
            source=self.source,
            children=[c.clone() for c in self.children],
            edges=[dict(e) for e in self.edges],
            meta=dict(self.meta),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question[:200],
            "scale": self.scale,
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "axis_sig": [round(float(x), 4) for x in self.axis_sig]
            if self.axis_sig is not None else None,
            "dist_top": [(s, round(w, 4)) for s, w in self.dist[:6]],
            "concepts": self.concepts[:6],
            "propositions": self.propositions[:4],
            "n_children": len(self.children),
            "children_ids": [c.id for c in self.children],
            "edges": self.edges[:24],
            "meta": self.meta,
        }


@dataclass
class CrossForest:
    """横並びノード集合 + 辺。arrange の戻り値。"""

    question: str
    nodes: List[CrossNode] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def node_map(self) -> Dict[str, CrossNode]:
        return {n.id: n for n in self.nodes}


def arrange(
    nodes: Sequence[CrossNode],
    *,
    question: Optional[str] = None,
    rel: str = "peer",
    rival_sources: Optional[Sequence[str]] = None,
) -> CrossForest:
    """横: 同型ノードを並べ、peer / rival 辺を張る。

    rival_sources: source にこの部分文字列を含むノードは cand:0 同士を rival に。
    """
    items = [n.clone() for n in nodes if n is not None]
    if not items:
        return CrossForest(question=question or "", nodes=[], edges=[])
    q = question or items[0].question
    rivals = tuple(rival_sources or ("critic", "rival"))
    edges: List[Dict[str, Any]] = []
    # 全対 peer (スパース: 連鎖 + ハブ)
    hub = items[0]
    for n in items[1:]:
        edges.append({
            "from": hub.id, "to": n.id, "rel": rel,
            "weight": float(min(hub.confidence, n.confidence)),
        })
    # critic 系は解候補ノードへ rival
    solvers = [n for n in items if not any(r in (n.source or "") for r in rivals)]
    critics = [n for n in items if any(r in (n.source or "") for r in rivals)]
    for c in critics:
        for s in solvers[:2]:
            edges.append({
                "from": c.id, "to": s.id, "rel": "rival",
                "weight": float(c.confidence),
            })
    # 各ノードにも辺を複写 (ローカル参照用)
    for n in items:
        n.edges = [e for e in edges if e["from"] == n.id or e["to"] == n.id]
    return CrossForest(
        question=q,
        nodes=items,
        edges=edges,
        meta={"op": "arrange", "n": len(items)},
    )


def wrap(
    forest_or_nodes,
    *,
    question: Optional[str] = None,
    source: str = "wrap",
    slot_map: Optional[Dict[str, str]] = None,
) -> CrossNode:
    """縦: ノード集合を親十字 1 ノードに包む。

    slot_map: child_id → PARENT_SLOTS 名 (省略時はエネルギー/登場順で割当)
    内側の dist/axis は質量保護ブレンドで親へ持ち上げる。
    """
    if isinstance(forest_or_nodes, CrossForest):
        children = [n.clone() for n in forest_or_nodes.nodes]
        edges = [dict(e) for e in forest_or_nodes.edges]
        q = question or forest_or_nodes.question
    else:
        children = [n.clone() for n in (forest_or_nodes or []) if n is not None]
        edges = []
        for n in children:
            edges.extend(n.edges)
        q = question or (children[0].question if children else "")

    if not children:
        return CrossNode.leaf(q or "", source=source)

    # 親の 6 スロットへ割当 (メタデータのみ。形式は同じ十字)
    assignment: Dict[str, str] = {}
    if slot_map:
        assignment = dict(slot_map)
    else:
        for i, ch in enumerate(children):
            assignment[ch.id] = PARENT_SLOTS[i % len(PARENT_SLOTS)]

    weights = [max(0.05, float(c.confidence)) for c in children]
    parent_dist = _blend_dists([c.dist for c in children], weights)
    parent_sig = _mean_sig([c.axis_sig for c in children])
    concepts = _uniq([c for ch in children for c in ch.concepts], limit=8)
    props = _uniq(
        [p for ch in children for p in ch.propositions]
        + [f"Wrapped {len(children)} crosses at scale+1."],
        limit=8,
    )
    conf = float(np.clip(np.average(
        [c.confidence for c in children], weights=weights), 0.0, 1.0))

    parent_scale = 1 + max(c.scale for c in children)
    parent = CrossNode(
        id=_new_id("wrap"),
        question=q,
        scale=parent_scale,
        axis_sig=parent_sig,
        dist=parent_dist,
        concepts=concepts,
        propositions=props,
        confidence=conf,
        source=source,
        children=children,
        edges=edges,
        meta={
            "op": "wrap",
            "slot_assignment": assignment,
            "n_children": len(children),
            "child_sources": [c.source for c in children],
        },
    )
    return parent


def plateau(
    scores: Sequence[float],
    *,
    window: int = 3,
    eps: float = 0.01,
) -> bool:
    """直近 window 個のスコアが eps 以内なら頭打ち → wrap 推奨。"""
    if not scores or len(scores) < window:
        return False
    recent = [float(x) for x in scores[-window:]]
    return (max(recent) - min(recent)) <= eps


def grow(
    nodes: Sequence[CrossNode],
    *,
    question: Optional[str] = None,
    scores: Optional[Sequence[float]] = None,
    force_wrap: bool = False,
    rival_sources: Optional[Sequence[str]] = None,
) -> CrossNode:
    """並べる → (頭打ち or force) なら包む、を一回分実行。

    戻り値は常に単一 CrossNode (包んだ親、または arrange ハブを擬似親化)。
    """
    forest = arrange(
        nodes, question=question, rival_sources=rival_sources)
    should = force_wrap or plateau(scores or [])
    if should and len(forest.nodes) >= 2:
        return wrap(forest, question=question, source="wrap:plateau" if not force_wrap else "wrap:force")
    # 包まないときも「横並び集合」を scale そのままのハブノードで返す
    if len(forest.nodes) == 1:
        return forest.nodes[0]
    hub = wrap(forest, question=question, source="arrange_hub")
    hub.meta["wrapped_as_hub_only"] = True
    hub.scale = max(c.scale for c in forest.nodes)  # 包み増しなし
    return hub


def company_roles_to_cross(
    canvases: Sequence[Any],
    *,
    question: str,
    wrap_roles: bool = True,
) -> CrossNode:
    """company 役割 canvas 列 → arrange → (任意で) wrap。"""
    leaves = [CrossNode.from_canvas(c) for c in canvases]
    forest = arrange(
        leaves, question=question, rival_sources=("critic", "rival"))
    if wrap_roles and len(forest.nodes) >= 2:
        return wrap(forest, question=question, source="company_wrap")
    if forest.nodes:
        return grow(forest.nodes, question=question, force_wrap=False)
    return CrossNode.leaf(question, source="company_empty")
