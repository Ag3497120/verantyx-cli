"""abstract_link.py — 異種モデル間の「NVLink」的抽象チャネル
==============================================================================

AbstractCanvas は解像度の変換器でもある:

  生ベクトル z  ──(高解像度・モデル固有)──┐
                                            ├─► 中間解像度グラフ (抽象画)
  自然言語     ──(低解像度・伝言ゲーム)──┘

  - ベクトルより解像度は低いが、共有でき調整できる
  - 自然言語より解像度が高く、不確実性・対立・根拠を壊しにくい
  - お互いがグラフを投げ合い、リンク推論で寄せて総意を形成する

ユーザー比喩の実装骨格:
  - リンク自体が推論する (パズル接合 + パターンマッチ)
  - パイプを流れるのは文章ではなく AbstractCanvas
  - キャッチボールで総意へ → 発話役が言語化 (参加描画も可)

生の隠れ状態はモデル内に閉じ、境界では常にキャンバスだけが渡る。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

Dist = List[Tuple[str, float]]


@dataclass
class AbstractCanvas:
    """中間解像度の共有グラフ (= 抽象画)。人間向けの長文ではない。

    変換器としての位置:
      vector (高解像・非共有) → canvas graph (中解像・共有可) → language (低解像・発話)

    layers (= グラフのノード種):
      axis_sig     : L1 共有軸 (6,) — モデル非依存の粗い向き
      dist         : 語彙分布レシピ — 相手側で soft 再合成可能
      concepts     : L2 概念トークン
      propositions : 命題サイズの主張 (DivergencePacket 由来)
      pattern_hits : 記憶/語彙とのパターンマッチ結果
      meta         : ラウンド履歴など
    """

    question: str
    axis_sig: Optional[List[float]] = None
    dist: Dist = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    propositions: List[str] = field(default_factory=list)
    pattern_hits: List[str] = field(default_factory=list)
    confidence: float = 0.5
    source: str = "council"
    meta: Dict[str, Any] = field(default_factory=dict)

    def as_graph(self) -> Dict[str, Any]:
        """投げ合い用の明示グラフ。ノードと粗い辺だけを持つ。

        辺の意味:
          supports  — 概念/分布が命題を支える
          rivals    — 分布候補同士の競合
          grounds   — パターンヒットが命題/概念の根拠
          orients   — 軸署名が全体の向きを与える
        """
        nodes: List[Dict[str, Any]] = [
            {"id": "q", "kind": "question", "label": self.question[:160]},
            {"id": "src", "kind": "source", "label": self.source,
             "confidence": self.confidence},
        ]
        edges: List[Dict[str, Any]] = []
        if self.axis_sig is not None:
            nodes.append({
                "id": "axis", "kind": "l1_axis",
                "value": [round(float(x), 4) for x in self.axis_sig],
            })
            edges.append({"from": "axis", "to": "q", "rel": "orients"})
        for i, (s, w) in enumerate(self.dist[:12]):
            nid = f"cand:{i}"
            nodes.append({"id": nid, "kind": "candidate",
                          "label": (s or "").strip(), "weight": float(w)})
            edges.append({"from": nid, "to": "q", "rel": "answers",
                          "weight": float(w)})
            if i > 0:
                edges.append({"from": "cand:0", "to": nid, "rel": "rivals"})
        for i, c in enumerate(self.concepts[:8]):
            nid = f"concept:{i}"
            nodes.append({"id": nid, "kind": "concept", "label": c})
            edges.append({"from": nid, "to": "q", "rel": "about"})
            if self.dist:
                edges.append({"from": nid, "to": "cand:0", "rel": "supports"})
        for i, p in enumerate(self.propositions[:6]):
            nid = f"prop:{i}"
            nodes.append({"id": nid, "kind": "proposition", "label": p[:240]})
            edges.append({"from": nid, "to": "q", "rel": "claims"})
            if self.concepts:
                edges.append({"from": "concept:0", "to": nid, "rel": "supports"})
        for i, h in enumerate(self.pattern_hits[:4]):
            nid = f"pat:{i}"
            nodes.append({"id": nid, "kind": "pattern", "label": h[:160]})
            target = "prop:0" if self.propositions else (
                "concept:0" if self.concepts else "q")
            edges.append({"from": nid, "to": target, "rel": "grounds"})
        return {
            "resolution": "mid",  # vector > canvas > language
            "converter": "AbstractCanvas",
            "nodes": nodes,
            "edges": edges,
            "summary": self.as_peer_summary(),
        }

    def clone(self) -> "AbstractCanvas":
        return AbstractCanvas(
            question=self.question,
            axis_sig=list(self.axis_sig) if self.axis_sig is not None else None,
            dist=list(self.dist),
            concepts=list(self.concepts),
            propositions=list(self.propositions),
            pattern_hits=list(self.pattern_hits),
            confidence=self.confidence,
            source=self.source,
            meta=dict(self.meta),
        )

    def as_peer_summary(self, top: int = 6) -> str:
        """キャッチボール用の短い要約 (peer スロット / API 向け劣化表現)。"""
        bits = []
        if self.concepts:
            bits.append("concepts=" + ",".join(self.concepts[:top]))
        if self.dist:
            items = ", ".join(f"{s.strip()}({w*100:.0f}%)"
                              for s, w in self.dist[:top] if (s or "").strip())
            if items:
                bits.append("dist=" + items)
        if self.propositions:
            bits.append("props=" + " | ".join(self.propositions[:3]))
        if self.pattern_hits:
            bits.append("patterns=" + ",".join(self.pattern_hits[:4]))
        return f"[{self.source} conf={self.confidence:.2f}] " + "; ".join(bits)

    def to_speaker_brief(
        self,
        *,
        memory_texts: Optional[Sequence[str]] = None,
        web_texts: Optional[Sequence[str]] = None,
        peer_texts: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
        intent: Optional[str] = None,
        purpose: str = "speak",
        locked_answer: Optional[str] = None,
    ):
        from speaker_bridge import SpeakerBrief
        peers = list(peer_texts or [])
        if self.as_peer_summary() and not peers:
            peers = [self.as_peer_summary()]
        return SpeakerBrief.build(
            self.question,
            concepts=self.concepts,
            consensus_dist=self.dist,
            memory_hits=memory_texts,
            web_snippets=web_texts,
            peer_summaries=peers,
            intent=intent,
            language=language,
            purpose=purpose,
            locked_answer=locked_answer,
        )


def canvas_from_role(
    question: str,
    role: str,
    *,
    dist: Optional[Dist] = None,
    concepts: Optional[Sequence[str]] = None,
    propositions: Optional[Sequence[str]] = None,
    axis_sig: Optional[List[float]] = None,
    confidence: float = 0.5,
) -> AbstractCanvas:
    """会社型ロール1体分の AbstractCanvas (`source=role:<name>`)。"""
    return AbstractCanvas(
        question=question,
        axis_sig=list(axis_sig) if axis_sig is not None else None,
        dist=list(dist or []),
        concepts=[c for c in (concepts or []) if c],
        propositions=[p for p in (propositions or []) if p][:8],
        confidence=float(confidence),
        source=f"role:{role}",
        meta={"role": role},
    )


def canvas_from_council(
    question: str,
    *,
    consensus_z=None,
    consensus_dist: Optional[Dist] = None,
    concepts: Optional[Sequence[str]] = None,
    axes=None,
    packets: Optional[Sequence[Any]] = None,
    source: str = "council",
) -> AbstractCanvas:
    """評議会合意から抽象画を起こす。"""
    sig = None
    if consensus_z is not None and axes is not None and getattr(axes, "available", False):
        try:
            sig = axes.signature(np.asarray(consensus_z, dtype=np.float32)).tolist()
        except Exception:
            sig = None
    props: List[str] = []
    if packets:
        for p in packets:
            raw_props = (
                getattr(p, "propositions", None)
                if not isinstance(p, dict)
                else p.get("propositions")
            ) or []
            for prop in raw_props:
                if hasattr(prop, "text"):
                    t = prop.text
                elif isinstance(prop, dict):
                    t = prop.get("text") or ""
                else:
                    t = str(prop)
                if t and t.strip():
                    props.append(t.strip())
    conf = 0.5
    if consensus_dist:
        conf = float(max(w for _, w in consensus_dist[:3])) if consensus_dist else 0.5
    return AbstractCanvas(
        question=question,
        axis_sig=sig,
        dist=list(consensus_dist or []),
        concepts=[c for c in (concepts or []) if c],
        propositions=props[:8],
        confidence=conf,
        source=source,
    )


def _blend_dists(a: Dist, b: Dist, wa: float = 0.6, wb: float = 0.4) -> Dist:
    acc: Dict[str, float] = {}
    for s, w in a or []:
        k = (s or "").strip()
        if k:
            acc[k] = acc.get(k, 0.0) + float(w) * wa
    for s, w in b or []:
        k = (s or "").strip()
        if k:
            acc[k] = acc.get(k, 0.0) + float(w) * wb
    if not acc:
        return list(a or b or [])
    total = sum(acc.values()) or 1.0
    items = sorted(((k, v / total) for k, v in acc.items()), key=lambda x: -x[1])
    return items[:48]


def _sig_blend(a, b, wa=0.6, wb=0.4):
    if a is None:
        return list(b) if b is not None else None
    if b is None:
        return list(a)
    aa = np.asarray(a, dtype=np.float32)
    bb = np.asarray(b, dtype=np.float32)
    if aa.shape != bb.shape:
        return list(a)
    out = wa * aa + wb * bb
    n = float(np.linalg.norm(out) + 1e-8)
    return (out / n).tolist()


class LinkChannel:
    """リンク自体が推論するチャネル (NVLink 比喩の本体)。

    infer_step:
      1) パターンマッチ — 記憶 L2/L3 と概念の共鳴
      2) パズル接合 — DivergencePacket 交換スコアで寄せる
      3) 分布ブレンド — 異端点の dist をレシピ合成 (生 z は触らない)
    """

    def __init__(self, memory=None, axes=None, dictionary=None, tok=None, log=None):
        self.memory = memory
        self.axes = axes
        self.dict = dictionary
        self.tok = tok
        self.log = log or (lambda *_a, **_k: None)

    def pattern_match(self, canvas: AbstractCanvas, k: int = 4) -> AbstractCanvas:
        """記憶側のパターンマッチ。リンク推論の片翼。

        異種対応: MemoryGraph 検索 (軸+概念+命題)。ルーターベクトルは使わない。
        フラッシュ理解用に hit.flash_summary() を pattern_hits へ載せる。
        """
        out = canvas.clone()
        hits: List[str] = []
        if self.memory is None or not getattr(self.memory, "enabled", False):
            out.pattern_hits = hits
            return out
        try:
            from memory_graph import MemoryGraph
            q = MemoryGraph.from_canvas(canvas)
            graph_hits = []
            if hasattr(self.memory, "search_graph"):
                graph_hits = self.memory.search_graph(q, k=k, min_score=0.06)
            for g, scores, rec in graph_hits:
                hits.append(g.flash_summary())
                for c in g.concepts:
                    if c not in out.concepts:
                        out.concepts.append(c)
                for p in g.propositions:
                    if p not in out.propositions:
                        out.propositions.append(p)
                out.concepts = out.concepts[:8]
                out.propositions = out.propositions[:8]
                out.meta.setdefault("memory_graph_hits", []).append({
                    "id": rec.get("id"), "score": round(scores["score"], 3),
                    "axis": round(scores["axis"], 3),
                    "concepts": round(scores["concepts"], 3),
                })
        except Exception as e:
            out.meta["memory_graph_error"] = str(e)[:120]
        # フォールバック: 旧字句共鳴 (graph 未整備ノード向け)
        if len(hits) < k:
            keys = set(c.strip().lower() for c in out.concepts if c and len(c.strip()) >= 2)
            for rec in getattr(self.memory, "index", [])[-400:]:
                l2 = [str(x).lower() for x in (rec.get("l2_concepts") or [])]
                text = (rec.get("l3_text") or "")[:160]
                if keys and any(any(k in c or c in k for c in l2) for k in keys):
                    hits.append(text)
                elif keys and any(k in text.lower() for k in keys):
                    hits.append(text)
                if len(hits) >= k:
                    break
        out.pattern_hits = hits[:k]
        if hits:
            out.confidence = float(min(1.0, out.confidence + 0.05 * len(hits)))
        return out

    def puzzle_join(self, canvases: Sequence[AbstractCanvas]) -> AbstractCanvas:
        """複数キャンバスをパズル接合。リンク推論のもう片翼。"""
        if not canvases:
            raise ValueError("puzzle_join: empty")
        if len(canvases) == 1:
            return canvases[0].clone()

        from divergence_packet import DivergencePacket
        from divergence_exchange import exchange_packets

        packets = []
        dists = {}
        for i, c in enumerate(canvases):
            role = c.source or f"peer{i}"
            pkt = DivergencePacket(role=role, axis=None, confidence=c.confidence)
            for prop in (c.propositions or c.concepts)[:4]:
                pkt.add_proposition(prop if len(prop) >= 12 else (prop + " as working claim."),
                                    confidence=c.confidence)
            if c.axis_sig is not None:
                pkt.axis_sig = list(c.axis_sig)
            packets.append(pkt)
            dists[role] = c.dist

        result = exchange_packets(packets, dists=dists)
        # 加重で dist / sig / concepts を合成
        weights = result.weights or {c.source: 1.0 / len(canvases) for c in canvases}
        wsum = sum(weights.values()) or 1.0
        blended = canvases[0].clone()
        blended.source = "link"
        blended.meta = {
            "link_action": result.action,
            "divergence": result.divergence,
            "weights": {k: round(float(v), 4) for k, v in weights.items()},
        }
        dist_acc: Dict[str, float] = {}
        for c in canvases:
            w = float(weights.get(c.source, 1.0 / len(canvases))) / wsum
            for s, p in c.dist or []:
                k = (s or "").strip()
                if k:
                    dist_acc[k] = dist_acc.get(k, 0.0) + float(p) * w
        if dist_acc:
            tot = sum(dist_acc.values()) or 1.0
            blended.dist = sorted(
                ((k, v / tot) for k, v in dist_acc.items()), key=lambda x: -x[1])[:48]
        # concepts / props
        seen = set()
        concepts = []
        for c in sorted(canvases, key=lambda x: -weights.get(x.source, 0)):
            for t in c.concepts:
                key = t.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    concepts.append(t.strip())
        blended.concepts = concepts[:8]
        props = []
        for c in canvases:
            props.extend(c.propositions)
        blended.propositions = props[:8]
        # axis
        sig = None
        for c in canvases:
            w = float(weights.get(c.source, 0)) / wsum
            sig = _sig_blend(sig, c.axis_sig, wa=1.0, wb=w) if sig is not None else (
                list(c.axis_sig) if c.axis_sig is not None else None)
        blended.axis_sig = sig
        blended.confidence = float(np.clip(
            sum(c.confidence * weights.get(c.source, 0) / wsum for c in canvases),
            0.0, 1.0))
        # pattern hits union
        hits = []
        for c in canvases:
            for h in c.pattern_hits:
                if h not in hits:
                    hits.append(h)
        blended.pattern_hits = hits[:6]
        blended.meta["agreement_mass"] = getattr(result, "agreement_mass", None)
        return blended

    def peer_toss(
        self,
        canvas: AbstractCanvas,
        peer,
        *,
        name: Optional[str] = None,
    ) -> AbstractCanvas:
        """相手モデルへキャンバスを投げ、返ってきた分布で新しい画を受ける。
        生 z は渡さない。consensus_dist / concepts のみ。"""
        name = name or getattr(peer, "name", "peer")
        out = canvas.clone()
        out.source = name
        try:
            dist, inner = peer.opine_dist(canvas.question, canvas.dist or None)
        except TypeError:
            dist, inner = peer.opine_dist(canvas.question)
        except Exception as e:
            out.meta["peer_error"] = str(e)[:120]
            return out
        if dist:
            # 相手の答えを分布に混ぜ、リンク側で再接合しやすい形へ
            out.dist = _blend_dists(canvas.dist, dist, wa=0.45, wb=0.55)
            top = [s for s, _ in dist[:4] if (s or "").strip()]
            for t in top:
                if t not in out.concepts:
                    out.concepts.append(t)
            out.concepts = out.concepts[:8]
            if isinstance(inner, str) and inner.strip():
                # 長い NL は命題サイズに切る
                prop = inner.strip().replace("\n", " ")
                if len(prop) > 240:
                    prop = prop[:239] + "…"
                if len(prop) >= 12:
                    out.propositions = ([prop] + out.propositions)[:8]
            out.confidence = float(max(w for _, w in dist[:1])) if dist else out.confidence
        return out

    def catchball(
        self,
        seed: AbstractCanvas,
        peers: Optional[Sequence[Any]] = None,
        *,
        rounds: int = 2,
        speaker_peer=None,
        speaker_participates: bool = True,
    ) -> AbstractCanvas:
        """キャッチボール: パターンマッチ → peer toss → パズル接合 を繰り返す。

        speaker_participates: 最終ラウンドで発話役も抽象画の作成に参加。
        """
        current = self.pattern_match(seed)
        history = [{"round": 0, "source": current.source,
                    "summary": current.as_peer_summary()}]
        peers = list(peers or [])

        for r in range(max(1, rounds)):
            tossed = [current]
            for peer in peers:
                try:
                    tossed.append(self.peer_toss(current, peer))
                except Exception as e:
                    self.log(f"[AbstractLink] peer toss failed: {e}")
            # 最終ラウンドで発話役も描画に参加
            if speaker_participates and speaker_peer is not None and r == rounds - 1:
                try:
                    tossed.append(self.peer_toss(current, speaker_peer,
                                                 name=getattr(speaker_peer, "name", "speaker")))
                except Exception as e:
                    self.log(f"[AbstractLink] speaker join failed: {e}")

            # 各画にパターンを足してから接合
            tossed = [self.pattern_match(c) for c in tossed]
            current = self.puzzle_join(tossed)
            history.append({
                "round": r + 1,
                "source": current.source,
                "divergence": current.meta.get("divergence"),
                "summary": current.as_peer_summary(),
            })
            # 十分寄ったら早期終了
            div = current.meta.get("divergence")
            if div is not None and float(div) < 0.25 and r + 1 >= 1:
                break

        current.meta["catchball"] = history
        current.source = "link"
        return current


def gather_web_snippets(question: str, k: int = 3) -> List[str]:
    """factual 向け web スロット。失敗時は空 (オフライン耐性)。"""
    try:
        from verantyx_browser import search
        hits = search(question, k=k)
        if isinstance(hits, str) and hits.strip():
            # search は複数行テキストを返す → 箇条書き単位に分割
            lines = [ln.strip(" -") for ln in hits.splitlines() if ln.strip()]
            # タイトル行だけ拾う
            out = [ln[:400] for ln in lines if ln and not ln.startswith("http")][:k]
            return out or [hits[:400]]
    except Exception:
        return []
    return []
