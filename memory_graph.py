"""memory_graph.py — 異種モデル共通の記憶言語 (中間解像度グラフ)
==============================================================================

問題:
  永遠の記憶の L1.5 はルーター (0.5B) 埋め込み。異種モデルは同じ座標を読めない。
  生ベクトルのまま渡すと「一瞬で状況を掴む」能力がモデル境界で消える。

解:
  記憶の正本を **MemoryGraph** にする。
  パズル軸・概念・命題・候補分布・根拠辺で構造化した、
  「自然言語の上位互換 / 生ベクトルの下位互換」の共有言語。

  vector (高解像・非共有) → MemoryGraph (中解像・共有) → language (低解像・発話)

  読み込み側はグラフを見て状況をある程度フラッシュ理解し、
  必要なら自モデルの埋め込み空間へ再投影 (dist→soft) する。
  異種検索は query_vec を使わず、軸署名 + 概念 + 命題の重なりで行う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# verantyx_mind.AXIS_NAMES と一致させる (import 循環を避けるためここにも置く)
AXIS_NAMES = [
    "Logic/Structure",
    "Syntax/Code   ",
    "Factual Memory",
    "Temporal/Time ",
    "Creativity    ",
    "Swarm Consensus",
]


def _axis_key(name: str) -> str:
    return name.strip()


AXIS_KEYS = [_axis_key(n) for n in AXIS_NAMES]


@dataclass
class MemoryGraph:
    """異種モデルが読み書きする記憶の共有グラフ。

    スキーマ (言語の語彙):
      axes         : パズル6軸の向き {axis_name: weight in [-1,1] or [0,1]}
      concepts     : L2 概念トークン
      propositions : 命題サイズの主張
      candidates   : [(token, mass)] 答え候補分布
      grounds      : 根拠スニペット (Obsidian/過去ノート等)
      edges        : [{from, to, rel, weight?}] 任意の追加辺
      l3_text      : 人間可読アンカー (必須ではないが検索表示用)
    """

    axes: Dict[str, float] = field(default_factory=dict)
    concepts: List[str] = field(default_factory=list)
    propositions: List[str] = field(default_factory=list)
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    grounds: List[str] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    l3_text: str = ""
    kind: str = "episode"
    confidence: float = 0.5
    meta: Dict[str, Any] = field(default_factory=dict)

    # ── 構築 ──────────────────────────────────────────────────────────────
    @classmethod
    def from_axis_sig(
        cls,
        axis_sig: Optional[Sequence[float]],
        *,
        concepts: Optional[Sequence[str]] = None,
        propositions: Optional[Sequence[str]] = None,
        candidates: Optional[Sequence[Tuple[str, float]]] = None,
        grounds: Optional[Sequence[str]] = None,
        l3_text: str = "",
        kind: str = "episode",
        confidence: float = 0.5,
        edges: Optional[Sequence[Dict[str, Any]]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "MemoryGraph":
        axes: Dict[str, float] = {}
        if axis_sig is not None:
            sig = list(axis_sig)
            for i, key in enumerate(AXIS_KEYS):
                if i < len(sig):
                    axes[key] = round(float(sig[i]), 5)
        return cls(
            axes=axes,
            concepts=[c for c in (concepts or []) if c],
            propositions=[p for p in (propositions or []) if p],
            candidates=[(s, float(w)) for s, w in (candidates or []) if (s or "").strip()],
            grounds=[g for g in (grounds or []) if g],
            edges=list(edges or []),
            l3_text=l3_text or "",
            kind=kind,
            confidence=float(confidence),
            meta=dict(meta or {}),
        )

    @classmethod
    def from_canvas(cls, canvas, *, l3_text: str = "", kind: str = "episode") -> "MemoryGraph":
        from abstract_link import AbstractCanvas
        if not isinstance(canvas, AbstractCanvas):
            raise TypeError("from_canvas expects AbstractCanvas")
        g = cls.from_axis_sig(
            canvas.axis_sig,
            concepts=canvas.concepts,
            propositions=canvas.propositions,
            candidates=canvas.dist,
            grounds=canvas.pattern_hits,
            l3_text=l3_text or canvas.as_peer_summary(),
            kind=kind,
            confidence=canvas.confidence,
            meta={"source": canvas.source},
        )
        # AbstractCanvas.as_graph の辺を共有スキーマへ
        try:
            ag = canvas.as_graph()
            g.edges = list(ag.get("edges") or [])
            g.meta["canvas_resolution"] = ag.get("resolution")
        except Exception:
            pass
        return g

    @classmethod
    def from_record(cls, rec: Dict[str, Any]) -> "MemoryGraph":
        """Cortex ノード dict → MemoryGraph。graph フィールド優先、無ければ L1/L2/L3 から復元。"""
        if rec.get("graph"):
            return cls.from_dict(rec["graph"])
        return cls.from_axis_sig(
            rec.get("l1_sig"),
            concepts=rec.get("l2_concepts") or [],
            propositions=rec.get("propositions") or [],
            candidates=rec.get("candidates") or [],
            grounds=[],
            l3_text=rec.get("l3_text") or "",
            kind=rec.get("kind") or "episode",
            confidence=float(rec.get("confidence") or 0.5),
            edges=rec.get("edges") or [],
            meta={"id": rec.get("id"), "migrated": True},
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryGraph":
        cands = d.get("candidates") or []
        norm_cands = []
        for item in cands:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                norm_cands.append((str(item[0]), float(item[1])))
            elif isinstance(item, dict):
                norm_cands.append((str(item.get("label") or item.get("s") or ""),
                                   float(item.get("weight") or item.get("w") or 0)))
        return cls(
            axes={str(k): float(v) for k, v in (d.get("axes") or {}).items()},
            concepts=list(d.get("concepts") or []),
            propositions=list(d.get("propositions") or []),
            candidates=norm_cands,
            grounds=list(d.get("grounds") or []),
            edges=list(d.get("edges") or []),
            l3_text=d.get("l3_text") or "",
            kind=d.get("kind") or "episode",
            confidence=float(d.get("confidence") or 0.5),
            meta=dict(d.get("meta") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": "verantyx.memory_graph.v1",
            "axes": dict(self.axes),
            "concepts": list(self.concepts),
            "propositions": list(self.propositions),
            "candidates": [[s, float(w)] for s, w in self.candidates],
            "grounds": list(self.grounds),
            "edges": list(self.edges),
            "l3_text": self.l3_text,
            "kind": self.kind,
            "confidence": self.confidence,
            "meta": dict(self.meta),
        }

    def axis_sig_list(self) -> List[float]:
        return [float(self.axes.get(k, 0.0)) for k in AXIS_KEYS]

    def to_canvas(self, question: str = ""):
        from abstract_link import AbstractCanvas
        return AbstractCanvas(
            question=question or self.l3_text[:120],
            axis_sig=self.axis_sig_list(),
            dist=list(self.candidates),
            concepts=list(self.concepts),
            propositions=list(self.propositions),
            pattern_hits=list(self.grounds),
            confidence=self.confidence,
            source="memory_graph",
            meta={"kind": self.kind, **self.meta},
        )

    def flash_summary(self, max_chars: int = 280) -> str:
        """異種モデルが一瞬で状況を掴むための構造化サマリ (NL 上位互換の劣化写像)。"""
        dom = sorted(self.axes.items(), key=lambda x: -abs(x[1]))[:3]
        axis_s = ",".join(f"{k}:{v:+.2f}" for k, v in dom) if dom else "-"
        cand_s = ",".join(f"{s}({w*100:.0f}%)" for s, w in self.candidates[:4]) or "-"
        concept_s = ",".join(self.concepts[:6]) or "-"
        prop_s = " | ".join(self.propositions[:2]) or "-"
        text = (f"axes[{axis_s}] concepts[{concept_s}] "
                f"cand[{cand_s}] props[{prop_s}]")
        if self.l3_text:
            text += f" :: {self.l3_text[:80]}"
        return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


# ── 異種モデル共通スコア (query_vec 不要) ─────────────────────────────────────
def _cos_sig(a: Sequence[float], b: Sequence[float]) -> float:
    aa = np.asarray(list(a) + [0.0] * 6, dtype=np.float32)[:6]
    bb = np.asarray(list(b) + [0.0] * 6, dtype=np.float32)[:6]
    na, nb = float(np.linalg.norm(aa) + 1e-8), float(np.linalg.norm(bb) + 1e-8)
    return float(np.dot(aa, bb) / (na * nb))


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa = {x.strip().lower() for x in a if x and len(x.strip()) >= 2}
    sb = {x.strip().lower() for x in b if x and len(x.strip()) >= 2}
    if not sa and not sb:
        return 0.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def _cand_overlap(a: Sequence[Tuple[str, float]], b: Sequence[Tuple[str, float]]) -> float:
    ma, mb = {}, {}
    for s, w in a or []:
        k = (s or "").strip().lower()
        if k:
            ma[k] = ma.get(k, 0.0) + float(w)
    for s, w in b or []:
        k = (s or "").strip().lower()
        if k:
            mb[k] = mb.get(k, 0.0) + float(w)
    if not ma or not mb:
        return 0.0
    return float(sum(min(ma[k], mb[k]) for k in ma if k in mb))


def graph_similarity(query: MemoryGraph, doc: MemoryGraph) -> Dict[str, float]:
    """ベクトルを使わない異種共通類似度。"""
    axis = _cos_sig(query.axis_sig_list(), doc.axis_sig_list())
    concepts = _jaccard(query.concepts, doc.concepts)
    props = _jaccard(query.propositions, doc.propositions)
    cands = _cand_overlap(query.candidates, doc.candidates)
    # 粗い NL アンカー一致 (補助)
    lex = 0.0
    qt = (query.l3_text or "").lower()
    dt = (doc.l3_text or "").lower()
    if qt and dt:
        qwords = {w for w in qt.replace("/", " ").split() if len(w) >= 4}
        dwords = {w for w in dt.replace("/", " ").split() if len(w) >= 4}
        if qwords and dwords:
            lex = len(qwords & dwords) / float(len(qwords | dwords))
    # 重み: 軸と概念を主、候補・命題・字句を副
    score = (0.35 * max(0.0, axis) + 0.30 * concepts + 0.15 * props
             + 0.12 * cands + 0.08 * lex)
    return {
        "score": float(score),
        "axis": float(axis),
        "concepts": float(concepts),
        "props": float(props),
        "cands": float(cands),
        "lex": float(lex),
    }


def search_graphs(
    store_records: Sequence[Dict[str, Any]],
    query: MemoryGraph,
    *,
    k: int = 5,
    min_score: float = 0.08,
) -> List[Tuple[MemoryGraph, Dict[str, float], Dict[str, Any]]]:
    """レコード列をグラフ類似度で検索。戻り値: (graph, scores, rec)。"""
    scored = []
    for rec in store_records:
        g = MemoryGraph.from_record(rec)
        s = graph_similarity(query, g)
        if s["score"] >= min_score:
            scored.append((g, s, rec))
    scored.sort(key=lambda x: -x[1]["score"])
    return scored[:k]
