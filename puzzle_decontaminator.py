"""puzzle_decontaminator.py — 0.5B 単一構成での汚染除去配管
==============================================================================

方針:
  全構成要素は 0.5B。異種・役割・記憶から混入する「汚染」は
  別モデルではなく、すでに配管になっているパズル接合で落とす。

汚染の例:
  - 対立候補 (rivals) の尾が長い
  - 合意と無関係な概念・命題
  - 外れ軸エネルギー
  - 記憶パターンの字句ノイズ

このモジュールは AbstractCanvas を入力に、除去レポート付きで浄化する。
Matryoshka の PuzzleJoiner と同じ適合性発想を、グラフ言語側に適用する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

Dist = List[Tuple[str, float]]

# 除去の既定パラメータ (0.5B 期のヒューリスティック)
TOP_MASS_KEEP = 0.88          # 上位候補で蓄える確率質量
RIVAL_RATIO_DROP = 0.18       # top1 比がこれ未満の候補は rival 汚染として落とす
MIN_CANDIDATES = 1
MAX_CANDIDATES = 6
CONCEPT_KEEP = 6
PROP_KEEP = 4
AXIS_OUTLIER_Z = 1.35         # |axis - median| / mad がこれを超えたら減衰


@dataclass
class DecontamReport:
    """汚染除去の計測。軌跡・ログに載せる。"""

    dropped_candidates: List[str] = field(default_factory=list)
    kept_candidates: List[str] = field(default_factory=list)
    dropped_concepts: List[str] = field(default_factory=list)
    dropped_propositions: int = 0
    axis_damped: List[str] = field(default_factory=list)
    mass_before: float = 0.0
    mass_after_top: float = 0.0
    entropy_before: float = 0.0
    entropy_after: float = 0.0
    contamination_score: float = 0.0   # 除去前の汚れ [0,1]
    purity_gain: float = 0.0           # エントロピー低下など
    actions: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "dropped_candidates": list(self.dropped_candidates),
            "kept_candidates": list(self.kept_candidates),
            "dropped_concepts": list(self.dropped_concepts),
            "dropped_propositions": int(self.dropped_propositions),
            "axis_damped": list(self.axis_damped),
            "mass_before": round(self.mass_before, 4),
            "mass_after_top": round(self.mass_after_top, 4),
            "entropy_before": round(self.entropy_before, 4),
            "entropy_after": round(self.entropy_after, 4),
            "contamination_score": round(self.contamination_score, 4),
            "purity_gain": round(self.purity_gain, 4),
            "actions": list(self.actions),
        }


def _entropy(dist: Dist) -> float:
    if not dist:
        return 0.0
    ps = np.array([max(1e-12, float(w)) for _, w in dist], dtype=np.float64)
    ps = ps / ps.sum()
    return float(-(ps * np.log(ps + 1e-12)).sum())


def _norm_dist(dist: Dist) -> Dist:
    items = [((s or "").strip(), float(w)) for s, w in (dist or []) if (s or "").strip()]
    if not items:
        return []
    # 同一キー統合
    acc: Dict[str, float] = {}
    label: Dict[str, str] = {}
    for s, w in items:
        k = s.lower()
        acc[k] = acc.get(k, 0.0) + w
        label.setdefault(k, s)
    tot = sum(acc.values()) or 1.0
    return sorted(((label[k], v / tot) for k, v in acc.items()), key=lambda x: -x[1])


def contamination_score(dist: Dist, concepts: Sequence[str] = ()) -> float:
    """汚れの粗指標: 高エントロピー + 長い尾 + 概念過多。"""
    d = _norm_dist(dist)
    if not d:
        return 0.0
    ent = _entropy(d)
    # 一様分布エントロピー log(n) で正規化
    ent_n = ent / max(1e-6, np.log(max(2, len(d))))
    top1 = d[0][1]
    tail = 1.0 - top1
    concept_bloat = min(1.0, max(0, len(concepts) - 4) / 8.0)
    return float(np.clip(0.45 * ent_n + 0.40 * tail + 0.15 * concept_bloat, 0.0, 1.0))


def purify_dist(
    dist: Dist,
    *,
    top_mass: float = TOP_MASS_KEEP,
    rival_ratio: float = RIVAL_RATIO_DROP,
    max_keep: int = MAX_CANDIDATES,
) -> Tuple[Dist, List[str], List[str]]:
    """候補分布から rival 尾を落とす。戻り値: (clean, kept_labels, dropped_labels)。

    規則:
      1) top1 は必ず残す
      2) top1 比が rival_ratio 未満は rival 汚染として落とす
      3) 累積質量が top_mass に達したら以降は落とす
      4) 最大 max_keep 件
    """
    d = _norm_dist(dist)
    if not d:
        return [], [], []
    top1_w = d[0][1]
    floor = top1_w * float(rival_ratio)
    kept, dropped = [], []
    acc = []
    mass = 0.0
    for i, (s, w) in enumerate(d):
        if i == 0:
            acc.append((s, w))
            kept.append(s)
            mass += w
            continue
        if len(acc) >= max_keep:
            dropped.append(s)
            continue
        if w < floor:
            dropped.append(s)
            continue
        if mass >= top_mass:
            dropped.append(s)
            continue
        acc.append((s, w))
        kept.append(s)
        mass += w
    clean = _norm_dist(acc)
    return clean, kept, dropped


def purify_concepts(concepts: Sequence[str], dist: Dist, keep: int = CONCEPT_KEEP) -> Tuple[List[str], List[str]]:
    """候補トークンと字句的に共鳴しない概念を落とす。"""
    keys = {(s or "").strip().lower() for s, _ in dist if (s or "").strip()}
    kept, dropped = [], []
    for c in concepts or []:
        cl = (c or "").strip()
        if not cl:
            continue
        low = cl.lower()
        if not keys or any(k in low or low in k for k in keys) or len(kept) < 2:
            kept.append(cl)
        else:
            dropped.append(cl)
    # 上限
    if len(kept) > keep:
        dropped.extend(kept[keep:])
        kept = kept[:keep]
    return kept, dropped


def damp_axis_outliers(axis_sig: Optional[Sequence[float]]) -> Tuple[Optional[List[float]], List[str]]:
    """外れ軸を中央値方向へ減衰 (立体十字の汚染除去)。"""
    if axis_sig is None:
        return None, []
    from memory_graph import AXIS_KEYS
    a = np.asarray(list(axis_sig) + [0.0] * 6, dtype=np.float32)[:6]
    med = float(np.median(a))
    mad = float(np.median(np.abs(a - med))) + 1e-6
    damped = a.copy()
    names = []
    for i in range(6):
        z = abs(float(a[i]) - med) / mad
        if z > AXIS_OUTLIER_Z:
            damped[i] = med + 0.35 * (a[i] - med)
            names.append(AXIS_KEYS[i] if i < len(AXIS_KEYS) else f"axis{i}")
    n = float(np.linalg.norm(damped) + 1e-8)
    return (damped / n).tolist(), names


def purify_propositions(props: Sequence[str], dist: Dist, concepts: Sequence[str],
                        keep: int = PROP_KEEP) -> Tuple[List[str], int]:
    keys = {(s or "").strip().lower() for s, _ in (dist or []) if (s or "").strip()}
    keys |= {c.strip().lower() for c in (concepts or []) if c and len(c.strip()) >= 2}
    kept = []
    dropped = 0
    for p in props or []:
        t = (p or "").strip()
        if not t:
            continue
        low = t.lower()
        if not keys or any(k in low for k in keys):
            kept.append(t[:240])
        else:
            dropped += 1
    if len(kept) > keep:
        dropped += len(kept) - keep
        kept = kept[:keep]
    return kept, dropped


@dataclass
class PuzzleDecontaminator:
    """パズル配管としての汚染除去器 (0.5B 期の浄水器)。"""

    top_mass: float = TOP_MASS_KEEP
    rival_ratio: float = RIVAL_RATIO_DROP
    # 汚れが高いときだけ強くかける
    aggressive_threshold: float = 0.42

    def purify_canvas(self, canvas, *, force: bool = False):
        """AbstractCanvas を浄化して (clean_canvas, report) を返す。"""
        from abstract_link import AbstractCanvas

        report = DecontamReport()
        dist_in = list(getattr(canvas, "dist", None) or [])
        concepts_in = list(getattr(canvas, "concepts", None) or [])
        report.entropy_before = _entropy(dist_in)
        report.mass_before = float(sum(w for _, w in dist_in) or 0.0)
        report.contamination_score = contamination_score(dist_in, concepts_in)

        aggressive = force or report.contamination_score >= self.aggressive_threshold
        # aggressive: 相対閾値を上げて尾を短く、件数も絞る
        rival = self.rival_ratio if not aggressive else max(0.40, self.rival_ratio)
        top_mass = self.top_mass if not aggressive else min(0.80, self.top_mass)
        max_keep = MAX_CANDIDATES if not aggressive else 3

        clean_dist, kept, dropped = purify_dist(
            dist_in, top_mass=top_mass, rival_ratio=rival, max_keep=max_keep)
        report.kept_candidates = kept
        report.dropped_candidates = dropped
        if dropped:
            report.actions.append("drop_rival_tail")

        clean_concepts, drop_c = purify_concepts(concepts_in, clean_dist or dist_in)
        report.dropped_concepts = drop_c
        if drop_c:
            report.actions.append("drop_unrelated_concepts")

        clean_props, n_drop_p = purify_propositions(
            getattr(canvas, "propositions", None) or [],
            clean_dist or dist_in, clean_concepts)
        report.dropped_propositions = n_drop_p
        if n_drop_p:
            report.actions.append("drop_unrelated_props")

        axis_out, damped_names = damp_axis_outliers(getattr(canvas, "axis_sig", None))
        report.axis_damped = damped_names
        if damped_names:
            report.actions.append("damp_axis_outliers")

        # パターンヒットは多すぎると汚染 → 上位のみ
        patterns = list(getattr(canvas, "pattern_hits", None) or [])[:3]

        report.entropy_after = _entropy(clean_dist)
        report.mass_after_top = float(sum(w for _, w in clean_dist[:3]) if clean_dist else 0.0)
        report.purity_gain = float(max(0.0, report.entropy_before - report.entropy_after))
        if aggressive:
            report.actions.append("aggressive_mode")

        out = canvas.clone() if hasattr(canvas, "clone") else AbstractCanvas(
            question=getattr(canvas, "question", ""))
        out.dist = clean_dist or dist_in[:1]
        out.concepts = clean_concepts
        out.propositions = clean_props
        out.pattern_hits = patterns
        if axis_out is not None:
            out.axis_sig = axis_out
        # 浄化した分、確信度をわずかに引き上げ (汚れが減ったため)
        out.confidence = float(min(1.0, float(getattr(canvas, "confidence", 0.5))
                                   + 0.04 * len(report.actions)))
        out.source = getattr(canvas, "source", "council")
        out.meta = dict(getattr(canvas, "meta", None) or {})
        out.meta["decontam"] = report.as_dict()
        return out, report

    def should_restep(self, fidelity_reports: Sequence[Any], decontam: DecontamReport) -> bool:
        """忠実度が低く、まだ汚れが残る／落としすぎのとき再 step を推奨。"""
        if not fidelity_reports:
            return decontam.contamination_score >= 0.55
        # vector→graph が弱い & まだ候補尾が長い
        vgv = next((r for r in fidelity_reports
                    if getattr(r, "direction", "").startswith("vector→graph")), None)
        preserve = next((r for r in fidelity_reports
                         if getattr(r, "direction", "").startswith("graph→graph")), None)
        if vgv is not None and vgv.score < 0.40 and decontam.entropy_after > 1.2:
            return True
        if preserve is not None and preserve.score < 0.35:
            return True
        if decontam.contamination_score >= 0.60 and decontam.purity_gain < 0.05:
            return True
        return False
