"""
divergence_packet.py — 発散交換用パケット (命題サイズ)
==============================================================================
長い NL 討論の代わりに、命題サイズの DivergencePacket を軸/役割間で交換する。

情報粒: 全文ダンプでも 1 トークン破片でもなく、命題サイズ (短文主張)。
R0 は他者 soft なし。Council / Matryoshka は packet_from_hidden_dist を共有。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import math
import time
import uuid

import numpy as np


# 命題サイズの目安 (文字)
PROP_MIN_CHARS = 12
PROP_MAX_CHARS = 240
# パケットあたり命題数の上限 (grain 正規化)
PROP_MAX_COUNT = 4


@dataclass
class Proposition:
    """命題サイズの主張 1 個。"""

    text: str
    confidence: float = 0.5
    polarity: str = "claim"  # claim | doubt | constraint | evidence

    def clipped(self) -> "Proposition":
        t = (self.text or "").strip()
        if len(t) > PROP_MAX_CHARS:
            t = t[: PROP_MAX_CHARS - 1] + "…"
        return Proposition(text=t, confidence=self.confidence, polarity=self.polarity)

    def is_grain_ok(self) -> bool:
        n = len((self.text or "").strip())
        return PROP_MIN_CHARS <= n <= PROP_MAX_CHARS


@dataclass
class DivergencePacket:
    """独立 round-0 の出力。他者を見ずに作る。

    Fields:
      role / axis   : 誰が / どの軸で出したか
      propositions  : 命題サイズの主張列 (順序付き)
      axis_sig      : AxisAnchors.signature (6,) があれば
      intent_vec    : 隠れ状態要約 (任意、numpy は list 化して保持可)
      dissent_keys  : 対立しうるキー (短い記号/語)
      confidence    : パケット全体の確信度
    """

    role: str
    axis: Optional[str] = None
    propositions: list = field(default_factory=list)
    axis_sig: Optional[list] = None
    intent_vec: Any = None
    dissent_keys: list = field(default_factory=list)
    confidence: float = 0.5
    packet_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created_at: float = field(default_factory=time.time)
    meta: dict = field(default_factory=dict)

    def add_proposition(self, text: str, confidence: float = 0.5,
                        polarity: str = "claim") -> Proposition:
        p = Proposition(text=text, confidence=confidence, polarity=polarity).clipped()
        self.propositions.append(p)
        return p

    def grain_ok(self) -> bool:
        if not self.propositions:
            return False
        return all(
            (p.is_grain_ok() if isinstance(p, Proposition)
             else PROP_MIN_CHARS <= len(str(p).strip()) <= PROP_MAX_CHARS)
            for p in self.propositions)

    def proposition_keys(self) -> list[str]:
        keys = []
        for p in self.propositions:
            t = p.text if isinstance(p, Proposition) else str(p)
            for tok in t.replace(",", " ").replace(";", " ").split():
                k = tok.strip().lower().lstrip("-_")
                if len(k) >= 2:
                    keys.append(k)
        return keys

    def to_dict(self) -> dict:
        d = asdict(self)
        # intent_vec は巨大になり得るので呼び出し側で落とす
        if d.get("intent_vec") is not None:
            d["intent_vec"] = None
            d["meta"] = dict(d.get("meta") or {})
            d["meta"]["intent_vec_omitted"] = True
        return d


@dataclass
class DivergenceExchange:
    """パケット間の発散交換結果 (軽量サマリ; 詳細は divergence_exchange.py)。"""

    packets: list = field(default_factory=list)
    agreement_mass: float = 0.0
    divergence_mass: float = 0.0
    join_ready: bool = False
    notes: list = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "n_packets": len(self.packets),
            "agreement_mass": self.agreement_mass,
            "divergence_mass": self.divergence_mass,
            "join_ready": self.join_ready,
            "notes": list(self.notes),
        }


def make_round0_packet(role: str, claims: list[str], *,
                       axis: str | None = None,
                       axis_sig=None,
                       confidence: float = 0.5,
                       dissent_keys: list | None = None,
                       intent_vec=None,
                       meta: dict | None = None) -> DivergencePacket:
    """独立 round-0 パケットを組み立てるヘルパ。"""
    pkt = DivergencePacket(
        role=role, axis=axis, confidence=confidence,
        axis_sig=list(axis_sig) if axis_sig is not None else None,
        dissent_keys=list(dissent_keys or []),
        intent_vec=intent_vec,
        meta=dict(meta or {}),
    )
    for c in claims:
        pkt.add_proposition(c)
    return normalize_grain(pkt)


def normalize_grain(pkt: DivergencePacket) -> DivergencePacket:
    """grain_ok を満たすようクリップ / 1命題へ正規化。"""
    props = []
    for p in pkt.propositions:
        if isinstance(p, Proposition):
            props.append(p.clipped())
        else:
            props.append(Proposition(text=str(p)).clipped())
    # 短すぎる命題はパディングして命題サイズ帯へ
    fixed = []
    for p in props:
        t = (p.text or "").strip()
        if len(t) < PROP_MIN_CHARS:
            t = (t + " [claim]").strip()
            if len(t) < PROP_MIN_CHARS:
                t = (t + " " + (pkt.role or "role")).strip()
            while len(t) < PROP_MIN_CHARS:
                t += "."
            p = Proposition(text=t[:PROP_MAX_CHARS], confidence=p.confidence,
                            polarity=p.polarity)
        fixed.append(p.clipped())
    if not fixed:
        stub = f"{pkt.role or 'role'} holds an open claim."
        fixed = [Proposition(text=stub[:PROP_MAX_CHARS], confidence=pkt.confidence)]
    if len(fixed) > PROP_MAX_COUNT:
        fixed = fixed[:PROP_MAX_COUNT]
    pkt.propositions = fixed
    # 全体 confidence を命題平均で軽く補正
    if fixed:
        pkt.confidence = float(np.clip(
            0.5 * pkt.confidence + 0.5 * np.mean([p.confidence for p in fixed]),
            0.0, 1.0))
    return pkt


def _claims_from_dist(dist, k: int = 3) -> list[str]:
    """語彙分布の上位トークンを命題サイズの短い主張へ。"""
    claims = []
    seen = set()
    for s, w in (dist or [])[:12]:
        body = (s or "").strip()
        key = body.lower().lstrip("-_")
        if len(body) < 2 or key in seen:
            continue
        if not any(c.isalnum() or ord(c) > 0x2E80 for c in body):
            continue
        seen.add(key)
        # 命題サイズ: 単独トークンは短いので枠を付ける
        claim = f"Candidate answer emphasizes '{body}' (p={float(w):.2f})."
        claims.append(claim)
        if len(claims) >= k:
            break
    if not claims:
        claims = ["No strong lexical candidate; keep the question open."]
    return claims


def _confidence_from_dist(dist) -> float:
    """分布エントロピーの逆数風確信度 [0,1]。"""
    if not dist:
        return 0.3
    ws = np.array([max(float(w), 1e-12) for _, w in dist[:32]], dtype=np.float64)
    ws = ws / (ws.sum() + 1e-12)
    ent = float(-(ws * np.log2(ws + 1e-12)).sum())
    # 典型 top-k エントロピー ~2–8 bits → 高エントロピーで低信頼
    return float(np.clip(1.0 / (1.0 + ent / 3.0), 0.05, 0.99))


def _dissent_keys_from_dist(dist, k: int = 6) -> list[str]:
    keys = []
    for s, _ in (dist or [])[:k]:
        tok = (s or "").strip().lower().lstrip("-_")
        if len(tok) >= 2:
            keys.append(tok)
    return keys


def packet_from_hidden_dist(
    role: str,
    z,
    dist,
    *,
    axis: str | None = None,
    axis_sig=None,
    dictionary=None,
    tok=None,
    top_k_claims: int = 3,
    store_intent_vec: bool = False,
    meta: dict | None = None,
) -> DivergencePacket:
    """独立 R0 の (z, dist) から DivergencePacket を構築する共有ヘルパ。

    Council.deliberate / Matryoshka AxisSlot.opine 後の両方から呼ぶ。
    dictionary+tok があれば共鳴クラウドで主張を補完できるが、必須ではない。
    """
    claims = _claims_from_dist(dist, k=top_k_claims)
    # 任意: 共鳴トップ概念で主張を補強
    if dictionary is not None and tok is not None and z is not None:
        try:
            from verantyx_mind import token_cloud
            _, _, p, top = dictionary.resonance(
                np.asarray(z, dtype=np.float32), temperature=1.0)
            cloud = token_cloud(tok, p, top, k=4)
            for s, pr in cloud:
                body = (s or "").strip()
                if len(body) < 2:
                    continue
                extra = f"Resonance peak '{body}' ({float(pr)*100:.0f}%)."
                if extra not in claims and len(claims) < PROP_MAX_COUNT:
                    claims.append(extra)
        except Exception:
            pass

    conf = _confidence_from_dist(dist)
    dissent = _dissent_keys_from_dist(dist)
    intent = None
    if store_intent_vec and z is not None:
        intent = np.asarray(z, dtype=np.float32).ravel().copy()

    m = dict(meta or {})
    if z is not None:
        try:
            m["z_norm"] = float(np.linalg.norm(z))
        except Exception:
            pass
    if dist:
        m["dist_top1"] = (dist[0][0] or "").strip()
        m["dist_entropy"] = float(
            -sum(w * math.log2(w + 1e-12) for _, w in dist[:48] if w > 0))

    return make_round0_packet(
        role, claims,
        axis=axis,
        axis_sig=axis_sig,
        confidence=conf,
        dissent_keys=dissent,
        intent_vec=intent,
        meta=m,
    )


def packets_to_serializable(packets: list) -> list[dict]:
    """ask() 戻り値用: intent_vec を落とした dict 列。"""
    out = []
    for p in packets or []:
        if isinstance(p, DivergencePacket):
            out.append(p.to_dict())
        elif isinstance(p, dict):
            out.append(p)
        else:
            out.append({"repr": repr(p)})
    return out
