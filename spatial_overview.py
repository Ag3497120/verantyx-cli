"""spatial_overview.py — 第二の脳: 十字/記憶空間の俯瞰とデータ流
==============================================================================

ファインチューニング無しで大規模コンテキスト窓の代わりに使う:

  永遠記憶 + CrossNode 群を「どこに何があるか」の空間地図に圧縮し、
  エージェントが少ないトークンで全体を俯瞰してから局所推論する。

位置関係 (軸・kind・scale・辺) は UI 用ではなく AI の索引である。
俯瞰そのものも MemoryGraph として刻み、会社型ベクトル合議の接地に使う。
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class SpatialRegion:
    """空間上の一塊 (軸支配 / kind / scale)。"""

    key: str
    label: str
    n: int = 0
    top_concepts: List[str] = field(default_factory=list)
    top_candidates: List[str] = field(default_factory=list)
    sample_ids: List[Any] = field(default_factory=list)
    grounds: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "n": self.n,
            "top_concepts": self.top_concepts[:6],
            "top_candidates": self.top_candidates[:6],
            "sample_ids": self.sample_ids[:5],
            "grounds": self.grounds[:4],
        }


@dataclass
class DataFlowEdge:
    """データの流れ (参照用)。"""

    src: str
    dst: str
    rel: str
    weight: float = 1.0
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "from": self.src, "to": self.dst, "rel": self.rel,
            "weight": round(self.weight, 3), "note": self.note[:80],
        }


@dataclass
class SpatialOverview:
    """第二の脳の一枚俯瞰。エージェント向け圧縮コンテキスト。"""

    question: str = ""
    regions: List[SpatialRegion] = field(default_factory=list)
    flows: List[DataFlowEdge] = field(default_factory=list)
    hotspots: List[str] = field(default_factory=list)
    cross_summary: Dict[str, Any] = field(default_factory=dict)
    n_memory: int = 0
    ts: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)

    def agent_brief(self, *, max_chars: int = 900) -> str:
        """大規模モデル向け: 大きな窓の代わりに届ける集約情報。"""
        lines = [
            "[SecondBrain Spatial Overview]",
            f"q: {(self.question or '')[:120]}",
            f"memory_nodes={self.n_memory} regions={len(self.regions)}",
        ]
        if self.cross_summary:
            lines.append(
                f"active_cross: id={self.cross_summary.get('id')} "
                f"scale={self.cross_summary.get('scale')} "
                f"children={self.cross_summary.get('n_children')} "
                f"top={self.cross_summary.get('top_dist')}"
            )
        lines.append("regions:")
        for r in self.regions[:8]:
            lines.append(
                f"  - {r.label} n={r.n} "
                f"concepts={','.join(r.top_concepts[:4]) or '-'} "
                f"cand={','.join(r.top_candidates[:3]) or '-'}"
            )
        if self.flows:
            lines.append("data_flow:")
            for e in self.flows[:10]:
                lines.append(f"  - {e.src} -{e.rel}-> {e.dst} {e.note}".rstrip())
        if self.hotspots:
            lines.append("hotspots: " + " | ".join(self.hotspots[:6]))
        text = "\n".join(lines)
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text

    def as_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question[:200],
            "n_memory": self.n_memory,
            "regions": [r.as_dict() for r in self.regions],
            "flows": [e.as_dict() for e in self.flows],
            "hotspots": self.hotspots[:8],
            "cross_summary": self.cross_summary,
            "agent_brief": self.agent_brief(),
            "ts": self.ts,
            "meta": self.meta,
        }

    def to_memory_graph(self):
        from memory_graph import MemoryGraph
        concepts = []
        cands = []
        props = [self.agent_brief(max_chars=240)]
        for r in self.regions[:6]:
            concepts.extend(r.top_concepts[:2])
            for c in r.top_candidates[:2]:
                cands.append((c, 1.0))
            props.append(f"Region {r.label}: n={r.n}")
        if cands:
            s = sum(w for _, w in cands) or 1.0
            cands = [(t, w / s) for t, w in cands[:12]]
        grounds = []
        for r in self.regions:
            grounds.extend(r.grounds[:2])
        return MemoryGraph(
            concepts=list(dict.fromkeys(concepts))[:10],
            propositions=props[:8],
            candidates=cands,
            grounds=list(dict.fromkeys(grounds))[:8],
            edges=[e.as_dict() for e in self.flows[:16]],
            l3_text=f"[SpatialOverview] {self.question[:100]}",
            kind="spatial_overview",
            confidence=0.55,
            meta={"n_regions": len(self.regions), "n_memory": self.n_memory},
        )


def _dom_axis(axes: Dict[str, float]) -> str:
    if not axes:
        return "untyped"
    k, _ = max(axes.items(), key=lambda kv: abs(float(kv[1])))
    return (k or "untyped").strip() or "untyped"


def _topk_count(counter: Dict[str, float], n: int = 6) -> List[str]:
    return [k for k, _ in sorted(counter.items(), key=lambda kv: -kv[1])[:n]]


def build_spatial_overview(
    memory=None,
    *,
    cross=None,
    question: str = "",
    max_records: int = 400,
) -> SpatialOverview:
    """永遠記憶 + 現十字から俯瞰を構築。"""
    ov = SpatialOverview(question=question or "")
    index = []
    if memory is not None and getattr(memory, "enabled", False):
        index = list(getattr(memory, "index", []) or [])[-max_records:]
    ov.n_memory = len(index)

    by_kind: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_axis: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    concept_mass: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    cand_mass: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    grounds_by: Dict[str, List[str]] = defaultdict(list)

    for rec in index:
        kind = (rec.get("kind") or "episode").strip()
        by_kind[kind].append(rec)
        g = rec.get("graph") or {}
        axes = g.get("axes") or {}
        if not axes and rec.get("l1_sig"):
            # 署名だけある旧レコード
            from memory_graph import AXIS_KEYS
            sig = rec.get("l1_sig") or []
            axes = {AXIS_KEYS[i]: float(sig[i]) for i in range(min(6, len(sig)))}
        dom = _dom_axis(axes)
        by_axis[dom].append(rec)
        key = f"axis:{dom}"
        for c in (g.get("concepts") or rec.get("l2_concepts") or [])[:6]:
            if c:
                concept_mass[key][str(c).strip()] += 1.0
        for item in (g.get("candidates") or [])[:6]:
            if isinstance(item, (list, tuple)) and item:
                concept_mass[key]  # touch
                cand_mass[key][str(item[0]).strip()] += float(item[1]) if len(item) > 1 else 1.0
        for gr in (g.get("grounds") or []):
            if gr:
                grounds_by[key].append(str(gr)[:80])
                grounds_by[f"kind:{kind}"].append(str(gr)[:80])

    # 領域: 軸支配 + kind
    for dom, recs in sorted(by_axis.items(), key=lambda kv: -len(kv[1]))[:6]:
        key = f"axis:{dom}"
        ov.regions.append(SpatialRegion(
            key=key,
            label=f"axis:{dom}",
            n=len(recs),
            top_concepts=_topk_count(concept_mass[key]),
            top_candidates=_topk_count(cand_mass[key]),
            sample_ids=[r.get("id") for r in recs[-3:]],
            grounds=list(dict.fromkeys(grounds_by[key]))[:4],
        ))
    for kind, recs in sorted(by_kind.items(), key=lambda kv: -len(kv[1]))[:6]:
        ov.regions.append(SpatialRegion(
            key=f"kind:{kind}",
            label=f"kind:{kind}",
            n=len(recs),
            top_concepts=[],
            top_candidates=[],
            sample_ids=[r.get("id") for r in recs[-3:]],
            grounds=list(dict.fromkeys(grounds_by[f"kind:{kind}"]))[:4],
        ))

    # データ流 (構造的な既定辺 + 観測)
    ov.flows = [
        DataFlowEdge("obsidian", "memory_graph", "ingest", 1.0, "vault→Cortex"),
        DataFlowEdge("memory_graph", "cross_node", "ground", 1.0, "search_graph"),
        DataFlowEdge("cross_node", "company_join", "arrange_wrap", 1.0, "vector council"),
        DataFlowEdge("company_join", "speaker", "brief", 1.0, "NaturalLang"),
        DataFlowEdge("cross_node", "obsidian", "export", 0.8, "Verantyx/Cross notes"),
        DataFlowEdge("speaker", "memory_graph", "etch", 0.9, "conclusion"),
        DataFlowEdge("spatial_overview", "company_join", "hotspot", 0.7, "second brain"),
        DataFlowEdge("agent_gaze", "telepathy_trace", "etch", 1.0, "kind=telepathy"),
        DataFlowEdge("telepathy_trace", "peer_models", "recall", 1.0, "cross-model read"),
        DataFlowEdge("obsidian", "agent_gaze", "focus", 0.9, "where looking"),
    ]
    if by_kind.get("obsidian"):
        ov.flows.append(DataFlowEdge(
            "obsidian", "axis_regions", "grounds",
            min(1.0, len(by_kind["obsidian"]) / 20.0),
            f"n={len(by_kind['obsidian'])}",
        ))
    if by_kind.get("cross_conclusion"):
        ov.flows.append(DataFlowEdge(
            "cross_conclusion", "memory_graph", "accumulate",
            min(1.0, len(by_kind["cross_conclusion"]) / 10.0),
            f"n={len(by_kind['cross_conclusion'])}",
        ))

    if cross is not None:
        dist = getattr(cross, "dist", None) or []
        ov.cross_summary = {
            "id": getattr(cross, "id", None),
            "scale": getattr(cross, "scale", 0),
            "n_children": len(getattr(cross, "children", None) or []),
            "source": getattr(cross, "source", ""),
            "top_dist": [(s, round(float(w), 3)) for s, w in dist[:4]],
            "grounds": list((getattr(cross, "meta", None) or {}).get("grounds") or [])[:4],
        }
        ov.hotspots.append(
            f"active_cross:{ov.cross_summary['id']}@"
            f"scale{ov.cross_summary['scale']}"
        )

    # ホットスポット: 大きい領域
    for r in ov.regions[:4]:
        if r.n >= 2:
            ov.hotspots.append(f"{r.label}×{r.n}")

    ov.meta["built_from"] = {
        "kinds": {k: len(v) for k, v in by_kind.items()},
    }
    return ov


def remember_overview(memory, overview: SpatialOverview, *, quiet: bool = True) -> bool:
    if memory is None or not getattr(memory, "enabled", False):
        return False
    try:
        mg = overview.to_memory_graph()
        memory.add_graph(mg, vector=None, quiet=quiet)
        return True
    except Exception:
        return False


def attach_overview_to_canvas(canvas, overview: SpatialOverview):
    """俯瞰を canvas.meta / pattern_hits に載せ、合議の第二の脳にする。"""
    if canvas is None or overview is None:
        return canvas
    canvas.meta = dict(getattr(canvas, "meta", None) or {})
    canvas.meta["spatial_overview"] = overview.as_dict()
    brief = overview.agent_brief(max_chars=320)
    hits = list(getattr(canvas, "pattern_hits", None) or [])
    if brief not in hits:
        hits.insert(0, brief)
    canvas.pattern_hits = hits[:6]
    # ホットスポット概念を薄く足す
    for h in overview.hotspots[:3]:
        tag = h.split(":")[0] if ":" in h else h
        if tag and tag not in (canvas.concepts or []):
            canvas.concepts = list(canvas.concepts or []) + [tag[:40]]
    canvas.concepts = (canvas.concepts or [])[:10]
    return canvas
