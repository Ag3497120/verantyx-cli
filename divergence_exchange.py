"""
divergence_exchange.py — 乖離交換 + C/E/R/N スコア
==============================================================================
独立 R0 の DivergencePacket 同士を交換し、非多数決スコアで仮合意 or 再推論を決める。

S_i = a*C + b*E - c*R + d*N   (係数は下の定数テーブル; 学習接続は後続)

  C: 確信度 (packet.confidence / エントロピー逆数)
  E: 証拠整合 (記憶ヒット or factual 質量。無ければ 0)
  R: 他パケットとの矛盾・リスク (乖離大 + 相互否定)
  N: 他にない新規キー

乖離小 → 仮合意 (加重は S_i。単純多数決しない)
乖離大 → 割れた役割/軸だけ再推論 1 回 (命題サイズ hint)
それでも駄目 → 呼び出し側が _escalate / _plan_steal (本モジュールは escalate を呼ばない)

NL _nl_generate は本線に載せない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from divergence_packet import DivergencePacket, packets_to_serializable

# ── 係数テーブル (ヒューリスティック初期値; トレースで調整可能) ──────────────
COEFF_A_C = 1.0   # confidence
COEFF_B_E = 0.6   # evidence
COEFF_C_R = 0.8   # risk / contradiction
COEFF_D_N = 0.4   # novelty

# 乖離閾値: 平均 pairwise divergence がこれ以上なら high
DIVERGENCE_HIGH = 0.42
# join 用 PuzzleJoiner 閾値のベース; 乖離に連動して上げる
JOIN_THRESHOLD_BASE = 0.35
JOIN_THRESHOLD_MAX = 0.62


def score_coeffs() -> dict:
    return {
        "a_C": COEFF_A_C,
        "b_E": COEFF_B_E,
        "c_R": COEFF_C_R,
        "d_N": COEFF_D_N,
        "divergence_high": DIVERGENCE_HIGH,
        "formula": "S_i = a*C + b*E - c*R + d*N",
    }


def _cos(a, b) -> float:
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def _dist_overlap(dist_a, dist_b) -> float:
    """PuzzleJoiner と同型: 正規化文字列トークンの確率重み付き共通質量。"""
    ma, mb = {}, {}
    for s, w in (dist_a or []):
        k = (s or "").strip().lower()
        if k:
            ma[k] = ma.get(k, 0.0) + float(w)
    for s, w in (dist_b or []):
        k = (s or "").strip().lower()
        if k:
            mb[k] = mb.get(k, 0.0) + float(w)
    if not ma or not mb:
        return 0.0
    return float(sum(min(ma[k], mb[k]) for k in ma if k in mb))


def _key_jaccard_diff(keys_a, keys_b) -> float:
    """命題キー差分: 1 - Jaccard (大きいほど乖離)。"""
    a, b = set(keys_a or []), set(keys_b or [])
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b) or 1
    return 1.0 - (inter / union)


def pairwise_divergence(
    pkt_a: DivergencePacket,
    pkt_b: DivergencePacket,
    *,
    z_a=None,
    z_b=None,
    dist_a=None,
    dist_b=None,
) -> dict:
    """隠れ cos・分布重なり・命題キー差分から発散量 [0,1] を合成。"""
    cos = 0.0
    if z_a is not None and z_b is not None:
        cos = _cos(z_a, z_b)
    elif pkt_a.intent_vec is not None and pkt_b.intent_vec is not None:
        cos = _cos(pkt_a.intent_vec, pkt_b.intent_vec)

    overlap = 0.0
    if dist_a is not None and dist_b is not None:
        overlap = _dist_overlap(dist_a, dist_b)
    # meta に dist が無い場合はキー差分のみ

    key_diff = _key_jaccard_diff(pkt_a.proposition_keys(), pkt_b.proposition_keys())
    # dissent 相互否定
    da, db = set(pkt_a.dissent_keys or []), set(pkt_b.dissent_keys or [])
    dissent_clash = 0.0
    if da and db:
        dissent_clash = len(da & db) / max(1, len(da | db))
        # 同じ dissent キーを持つ = 対立点を共有 → やや合意寄りに扱う
        # キー集合が大きく異なり top1 も違う場合は clash を上げる
        if key_diff > 0.5:
            dissent_clash = 1.0 - dissent_clash

    # 合成: cos 高・overlap 高 → 低発散
    hidden_div = 0.5 * (1.0 - cos) + 0.5 * (1.0 - overlap) if (
        z_a is not None or dist_a is not None) else key_diff
    div = float(np.clip(0.45 * hidden_div + 0.35 * key_diff + 0.20 * dissent_clash, 0.0, 1.0))
    return {
        "cos": round(cos, 4),
        "overlap": round(overlap, 4),
        "key_diff": round(key_diff, 4),
        "dissent_clash": round(float(dissent_clash), 4),
        "divergence": round(div, 4),
    }


def _evidence_score(pkt: DivergencePacket, evidence_mass: float = 0.0) -> float:
    """E: 呼び出し側が渡す記憶ヒット等。無ければ meta.factual_mass or 0。"""
    if evidence_mass:
        return float(np.clip(evidence_mass, 0.0, 1.0))
    m = pkt.meta or {}
    if "factual_mass" in m:
        return float(np.clip(m["factual_mass"], 0.0, 1.0))
    if "evidence" in m:
        return float(np.clip(m["evidence"], 0.0, 1.0))
    return 0.0


def _novelty(pkt: DivergencePacket, all_packets: list[DivergencePacket]) -> float:
    """N: 他パケットにないキーの割合。"""
    mine = set(pkt.proposition_keys())
    if not mine:
        return 0.0
    others = set()
    for p in all_packets:
        if p is pkt or p.packet_id == pkt.packet_id:
            continue
        others |= set(p.proposition_keys())
    novel = mine - others
    return float(len(novel) / max(1, len(mine)))


def _risk(pkt: DivergencePacket, pair_divs: list[float], mean_div: float) -> float:
    """R: 平均より大きく乖離しているほどリスク。"""
    if not pair_divs:
        return mean_div
    return float(np.clip(0.5 * mean_div + 0.5 * float(np.mean(pair_divs)), 0.0, 1.0))


@dataclass
class ScoredCandidate:
    role: str
    axis: Optional[str]
    packet: DivergencePacket
    C: float
    E: float
    R: float
    N: float
    S: float
    z: Any = None
    dist: Any = None


@dataclass
class ExchangeResult:
    """乖離交換の決定結果。"""

    action: str = "joined"  # joined | reinfer | escalate
    divergence: float = 0.0
    agreement_mass: float = 0.0
    scores: list = field(default_factory=list)  # [{role, C,E,R,N,S}, ...]
    weights: dict = field(default_factory=dict)  # role -> normalized S weight
    split_roles: list = field(default_factory=list)  # reinfer 対象
    join_threshold: float = JOIN_THRESHOLD_BASE
    pairwise: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    packets: list = field(default_factory=list)
    reinfer_done: bool = False

    def trace_dict(self) -> dict:
        return {
            "action": self.action,
            "divergence": round(float(self.divergence), 4),
            "agreement_mass": round(float(self.agreement_mass), 4),
            "S_i": {s["role"]: s["S"] for s in self.scores},
            "scores": self.scores,
            "weights": {k: round(float(v), 4) for k, v in self.weights.items()},
            "split_roles": list(self.split_roles),
            "join_threshold": round(float(self.join_threshold), 4),
            "joined|reinfer|escalate": self.action,
            "coeffs": score_coeffs(),
            "notes": list(self.notes),
            "reinfer_done": self.reinfer_done,
            "n_packets": len(self.packets),
        }


def join_threshold_for_divergence(divergence: float) -> float:
    """乖離が大きいほど PuzzleJoiner 閾値を上げ、drop が出やすくする。

    乖離が DIVERGENCE_HIGH 未満のときは BASE のまま (旧 puzzle 互換)。
    低乖離で閾値を上げると接合が過剰に厳しくなり精度が落ちるため。
    """
    d = float(np.clip(divergence, 0.0, 1.0))
    if d <= DIVERGENCE_HIGH:
        return JOIN_THRESHOLD_BASE
    span = max(1e-8, 1.0 - DIVERGENCE_HIGH)
    t = JOIN_THRESHOLD_BASE + (JOIN_THRESHOLD_MAX - JOIN_THRESHOLD_BASE) * (
        (d - DIVERGENCE_HIGH) / span)
    return float(np.clip(t, JOIN_THRESHOLD_BASE, JOIN_THRESHOLD_MAX))


def exchange_packets(
    packets: list[DivergencePacket],
    *,
    zs: dict | None = None,
    dists: dict | None = None,
    evidence: dict | None = None,
    reinfer_done: bool = False,
    high_threshold: float = DIVERGENCE_HIGH,
) -> ExchangeResult:
    """パケット列を採点し、joined / reinfer / escalate を返す。

    zs / dists: role (or axis) → vector / dist
    evidence: role → E mass [0,1]
    reinfer_done: 既に1回再推論済みなら、なお high なら escalate 推奨
    """
    zs = zs or {}
    dists = dists or {}
    evidence = evidence or {}
    result = ExchangeResult(packets=list(packets), reinfer_done=reinfer_done)
    n = len(packets)
    if n == 0:
        result.action = "escalate"
        result.notes.append("no packets")
        return result
    if n == 1:
        p = packets[0]
        key = p.axis or p.role
        result.action = "joined"
        result.divergence = 0.0
        result.agreement_mass = 1.0
        C = float(p.confidence)
        E = _evidence_score(p, evidence.get(key, evidence.get(p.role, 0.0)))
        S = COEFF_A_C * C + COEFF_B_E * E
        result.scores = [{"role": p.role, "axis": p.axis, "C": C, "E": E,
                          "R": 0.0, "N": 0.0, "S": round(S, 4)}]
        result.weights = {p.role: 1.0}
        result.join_threshold = JOIN_THRESHOLD_BASE
        result.notes.append("single packet → join")
        return result

    # pairwise
    pair_rows = []
    per_role_divs = {p.role: [] for p in packets}
    for i in range(n):
        for j in range(i + 1, n):
            a, b = packets[i], packets[j]
            ka, kb = a.axis or a.role, b.axis or b.role
            row = pairwise_divergence(
                a, b,
                z_a=zs.get(ka, zs.get(a.role)),
                z_b=zs.get(kb, zs.get(b.role)),
                dist_a=dists.get(ka, dists.get(a.role)),
                dist_b=dists.get(kb, dists.get(b.role)),
            )
            row["a"] = a.role
            row["b"] = b.role
            pair_rows.append(row)
            per_role_divs[a.role].append(row["divergence"])
            per_role_divs[b.role].append(row["divergence"])

    mean_div = float(np.mean([r["divergence"] for r in pair_rows])) if pair_rows else 0.0
    agree = float(np.clip(1.0 - mean_div, 0.0, 1.0))
    result.divergence = mean_div
    result.agreement_mass = agree
    result.pairwise = pair_rows
    result.join_threshold = join_threshold_for_divergence(mean_div)

    scored: list[ScoredCandidate] = []
    for p in packets:
        key = p.axis or p.role
        C = float(np.clip(p.confidence, 0.0, 1.0))
        E = _evidence_score(p, evidence.get(key, evidence.get(p.role, 0.0)))
        R = _risk(p, per_role_divs.get(p.role, []), mean_div)
        N = _novelty(p, packets)
        S = (COEFF_A_C * C + COEFF_B_E * E - COEFF_C_R * R + COEFF_D_N * N)
        scored.append(ScoredCandidate(
            role=p.role, axis=p.axis, packet=p,
            C=C, E=E, R=R, N=N, S=float(S),
            z=zs.get(key, zs.get(p.role)),
            dist=dists.get(key, dists.get(p.role)),
        ))

    # S_i 加重 (負スコアは床上げしてから正規化 — 多数決しない)
    raw = np.array([max(s.S, 0.05) for s in scored], dtype=np.float64)
    raw = raw / (raw.sum() + 1e-12)
    result.weights = {s.role: float(w) for s, w in zip(scored, raw)}
    result.scores = [
        {"role": s.role, "axis": s.axis,
         "C": round(s.C, 4), "E": round(s.E, 4),
         "R": round(s.R, 4), "N": round(s.N, 4), "S": round(s.S, 4)}
        for s in scored
    ]

    high = mean_div >= high_threshold
    if not high:
        result.action = "joined"
        result.notes.append(f"low divergence {mean_div:.3f} → S_i-weighted consensus")
        return result

    # high: 平均より大きく乖離している役割を split
    split = [s.role for s in scored
             if float(np.mean(per_role_divs.get(s.role) or [mean_div])) >= mean_div]
    if not split:
        split = [s.role for s in scored]
    result.split_roles = split

    if not reinfer_done:
        result.action = "reinfer"
        result.notes.append(
            f"high divergence {mean_div:.3f} → reinfer split={split}")
    else:
        result.action = "escalate"
        result.notes.append(
            f"high divergence {mean_div:.3f} after reinfer → escalate/plan_steal fallback")
    return result


def weighted_consensus_vector(zs: dict, weights: dict, base_norm: float | None = None):
    """S_i 加重で隠れ合意ベクトルを作る (多数決しない)。"""
    acc = None
    wsum = 0.0
    for role, w in (weights or {}).items():
        z = zs.get(role)
        if z is None:
            continue
        z = np.asarray(z, dtype=np.float32).ravel()
        zn = z / (np.linalg.norm(z) + 1e-8)
        acc = w * zn if acc is None else acc + w * zn
        wsum += float(w)
    if acc is None:
        return None
    acc = acc / (np.linalg.norm(acc) + 1e-8)
    if base_norm is None:
        # 代表ノルム
        norms = [float(np.linalg.norm(zs[r])) for r in weights if r in zs]
        base_norm = float(np.mean(norms)) if norms else 1.0
    return (acc * base_norm).astype(np.float32)


def proposition_hint_text(packets: list[DivergencePacket], roles: list[str],
                          max_chars: int = 200) -> str:
    """再推論用の命題サイズ hint (全文ダンプ禁止)。"""
    bits = []
    role_set = set(roles)
    for p in packets:
        if p.role not in role_set and (p.axis or "") not in role_set:
            continue
        for prop in p.propositions[:2]:
            t = getattr(prop, "text", str(prop))
            bits.append(str(t).strip())
        if p.dissent_keys:
            bits.append("dissent:" + ",".join(p.dissent_keys[:3]))
    text = " | ".join(bits)
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    if len(text) < 12:
        text = "Reconsider the split claims; state one decisive answer."
    return text


def packets_summary(packets: list[DivergencePacket]) -> list[dict]:
    return packets_to_serializable(packets)
