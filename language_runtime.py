"""language_runtime.py — 三言語がそれぞれ「動作する」実行器
==============================================================================

立体十字グラフ (AbstractCanvas / MemoryGraph) は、自然言語とベクトルの
あいだに位置し、**双方へ忠実に変換できる**必要がある。

発想:
  受動的な符号化ではなく、各形式そのものに薄い実行器 (= 意思に近い操作系) を持たせる。
  「言語が意思を持つ」= 神秘ではなく、その言語の文法で推論・更新・発火できること。

  VectorLang  : encode / soft注入 / forward          (既存 RustBrain)
  GraphLang   : catchball / puzzle_join / search_graph (AbstractLink + MemoryGraph)
  NaturalLang : speak / brief 条件付け生成            (Speaker / bridges)

立体十字グラフはヒンジ。三言語はこのヒンジを通って往復し、
往復忠実度 (round-trip fidelity) で品質を測る。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

Dist = List[Tuple[str, float]]


@dataclass
class FidelityReport:
    """往復変換の忠実度。グラフが『間』として機能しているかの指標。"""

    direction: str  # e.g. "vector→graph→vector", "nl→graph→nl"
    score: float    # [0,1] 粗い総合
    parts: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def ok(self, threshold: float = 0.45) -> bool:
        return self.score >= threshold

    def as_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "score": round(float(self.score), 4),
            "parts": {k: round(float(v), 4) for k, v in self.parts.items()},
            "notes": list(self.notes),
            "ok": self.ok(),
        }


class VectorLang(Protocol):
    def encode(self, text: str):
        ...

    def inject_soft(self, dist, question: str):
        ...

    def reconstruct_from_dist(self, dist) -> Optional[np.ndarray]:
        """graph の dist レシピ → 自空間ベクトル近似。"""
        ...


class GraphLang(Protocol):
    def step(self, canvas):
        ...

    def remember(self, canvas, l3_text: str = ""):
        ...

    def recall(self, canvas, k: int = 5):
        ...


class NaturalLang(Protocol):
    def speak(self, brief) -> str:
        ...

    def parse_to_graph(self, text: str, question: str = ""):
        ...


# ── 忠実度 ───────────────────────────────────────────────────────────────────
def _dist_overlap(a: Optional[Dist], b: Optional[Dist]) -> float:
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


def _cos(a, b) -> float:
    aa = np.asarray(a, dtype=np.float32).ravel()
    bb = np.asarray(b, dtype=np.float32).ravel()
    n = min(aa.size, bb.size)
    if n == 0:
        return 0.0
    aa, bb = aa[:n], bb[:n]
    return float(np.dot(aa, bb) / (np.linalg.norm(aa) * np.linalg.norm(bb) + 1e-8))


def fidelity_vector_graph_vector(
    z_before,
    z_after,
    *,
    dist_before=None,
    dist_after=None,
) -> FidelityReport:
    """vector→graph→vector (または graph 経由の再合成) の忠実度。"""
    parts: Dict[str, float] = {}
    notes: List[str] = []
    if z_before is None or z_after is None:
        cos = 0.0
        notes.append("vector missing")
    else:
        cos = max(0.0, _cos(z_before, z_after))
    parts["cos"] = cos
    parts["dist_overlap"] = _dist_overlap(dist_before, dist_after)
    if not dist_before or not dist_after:
        notes.append("dist missing — cos weighted higher")
        score = cos
    else:
        score = 0.55 * cos + 0.45 * parts["dist_overlap"]
    return FidelityReport("vector→graph→vector", float(score), parts=parts, notes=notes)


def fidelity_nl_graph_nl(text_a: str, text_b: str) -> FidelityReport:
    """nl→graph→nl の粗い忠実度 (語彙 Jaccard)。"""
    def toks(s: str):
        return {w.strip(".,!?\"':;").lower() for w in (s or "").split() if len(w.strip()) >= 2}
    a, b = toks(text_a), toks(text_b)
    if not a and not b:
        return FidelityReport("nl→graph→nl", 0.0, notes=["empty"])
    j = len(a & b) / float(len(a | b) or 1)
    return FidelityReport("nl→graph→nl", float(j), parts={"jaccard": float(j)})


def fidelity_graph_preserve(seed, refined) -> FidelityReport:
    """graph step 前後で軸・概念・候補が壊れすぎていないか。"""
    parts: Dict[str, float] = {}
    notes: List[str] = []
    sa = getattr(seed, "axis_sig", None)
    ra = getattr(refined, "axis_sig", None)
    parts["axis_cos"] = max(0.0, _cos(sa, ra)) if sa is not None and ra is not None else 0.0
    if sa is None or ra is None:
        notes.append("axis_sig missing")
    sc = {c.strip().lower() for c in (getattr(seed, "concepts", None) or []) if c}
    rc = {c.strip().lower() for c in (getattr(refined, "concepts", None) or []) if c}
    parts["concept_jaccard"] = (
        len(sc & rc) / float(len(sc | rc) or 1) if (sc or rc) else 0.0)
    parts["dist_overlap"] = _dist_overlap(
        getattr(seed, "dist", None), getattr(refined, "dist", None))
    score = (0.35 * parts["axis_cos"] + 0.30 * parts["concept_jaccard"]
             + 0.35 * parts["dist_overlap"])
    return FidelityReport("graph→graph(step)", float(score), parts=parts, notes=notes)


# ── 具象アダプタ ─────────────────────────────────────────────────────────────
@dataclass
class RouterVectorLang:
    """VectorLang: ルーター脳上で動く。"""

    brain: Any
    dictionary: Any
    tok: Any

    def encode(self, text: str):
        from verantyx_mind import embed_text
        return embed_text(self.brain, self.tok, text)

    def inject_soft(self, dist, question: str):
        from verantyx_council import encode_with_dist_soft
        if not dist:
            return self.encode(question)
        # 長い role ChatML は soft を洗う → 短い answer probe + hidden ブレンド
        return encode_with_dist_soft(
            self.brain, self.tok, self.dictionary._embed_f16, dist,
            probe="answer", max_soft=16,
            dictionary=self.dictionary, hidden_blend=0.35)

    def reconstruct_from_dist(self, dist) -> Optional[np.ndarray]:
        """dist → 埋め込み期待値。forward なしの軽い graph→vector。"""
        if not dist:
            return None
        try:
            from verantyx_council import dist_to_soft_numpy
            return dist_to_soft_numpy(dist, self.tok, self.dictionary._embed_f16)
        except Exception:
            return None

    def embed_from_hidden(self, z) -> Optional[np.ndarray]:
        """隠れ z → 埋め込み空間 (辞書経路)。比較用。"""
        if z is None or self.dictionary is None:
            return None
        try:
            return self.dictionary.to_embedding(np.asarray(z, dtype=np.float32))
        except Exception:
            return None


@dataclass
class LinkGraphLang:
    """GraphLang: LinkChannel 上で立体十字グラフが動く。

    0.5B 単一期: step の末尾で PuzzleDecontaminator が汚染除去配管として動く。
    """

    link: Any
    peers: Sequence[Any] = field(default_factory=list)
    speaker_peer: Any = None
    speaker_participates: bool = False
    catchball_rounds: int = 1
    memory: Any = None
    decontaminate: bool = True
    last_decontam: Any = None

    def step(self, canvas):
        """1 ステップ = catchball → パズル汚染除去。
        peers 無しでも記憶共鳴 + 浄化器だけで画が更新される。"""
        out = self.link.catchball(
            canvas,
            peers=list(self.peers or []),
            rounds=max(1, int(self.catchball_rounds)),
            speaker_peer=self.speaker_peer,
            speaker_participates=bool(self.speaker_participates and self.speaker_peer),
        )
        if self.decontaminate:
            from puzzle_decontaminator import PuzzleDecontaminator
            out, report = PuzzleDecontaminator().purify_canvas(out)
            self.last_decontam = report
            out.meta = dict(out.meta or {})
            out.meta["decontam"] = report.as_dict()
        return out

    def remember(self, canvas, l3_text: str = ""):
        if self.memory is None or not getattr(self.memory, "enabled", False):
            return None
        from memory_graph import MemoryGraph
        mg = MemoryGraph.from_canvas(canvas, l3_text=l3_text or canvas.as_peer_summary(),
                                     kind="graph")
        if hasattr(self.memory, "add_graph"):
            return self.memory.add_graph(mg, vector=None, quiet=True)
        return None

    def recall(self, canvas, k: int = 5):
        if self.memory is None or not hasattr(self.memory, "search_graph"):
            return []
        from memory_graph import MemoryGraph
        return self.memory.search_graph(MemoryGraph.from_canvas(canvas), k=k)


@dataclass
class BriefNaturalLang:
    """NaturalLang: SpeakerBrief 条件で動く。speak_fn(brief)->str を注入。"""

    speak_fn: Any = None  # callable(brief) -> str

    def speak(self, brief) -> str:
        if self.speak_fn is None:
            if hasattr(brief, "evidence_block"):
                return brief.evidence_block() or ""
            return str(brief)
        return self.speak_fn(brief)

    def parse_to_graph(self, text: str, question: str = ""):
        """粗い NL→graph: 単語を概念・候補に載せる (専用パーサ前の足場)。"""
        from abstract_link import AbstractCanvas
        words = [w.strip(".,!?\"'") for w in (text or "").split() if len(w.strip()) >= 2]
        concepts = words[:6]
        dist = [(w, 1.0 / max(1, min(4, len(words)))) for w in words[:4]]
        if dist:
            s = sum(w for _, w in dist) or 1.0
            dist = [(t, w / s) for t, w in dist]
        props = []
        t = (text or "").strip().replace("\n", " ")
        if len(t) >= 12:
            props = [t[:240]]
        return AbstractCanvas(
            question=question or t[:120],
            concepts=concepts,
            dist=dist,
            propositions=props,
            source="nl_parse",
            confidence=0.35,
        )


@dataclass
class TriLanguageHinge:
    """立体十字グラフをヒンジに、三言語実行器を束ねる。"""

    vector: Any = None
    graph: Any = None
    natural: Any = None
    last_fidelity: List[FidelityReport] = field(default_factory=list)

    def think_on_graph(self, canvas, rounds: int = 1):
        if self.graph is None:
            return canvas
        # LinkGraphLang.step が内部で catchball_rounds を持つので、
        # 外側 rounds>1 のときは step を繰り返す
        out = canvas
        for _ in range(max(1, rounds)):
            out = self.graph.step(out)
        return out

    def speak_from_graph(self, canvas, **brief_kw) -> str:
        if self.natural is None:
            return canvas.as_peer_summary() if hasattr(canvas, "as_peer_summary") else str(canvas)
        brief = canvas.to_speaker_brief(**brief_kw) if hasattr(canvas, "to_speaker_brief") else canvas
        return self.natural.speak(brief)

    def record_fidelity(self, report: FidelityReport) -> FidelityReport:
        self.last_fidelity.append(report)
        return report

    def run_graph_step_with_fidelity(
        self,
        seed,
        *,
        consensus_z=None,
        consensus_dist: Optional[Dist] = None,
        graph_rounds: int = 1,
        max_resteps: int = 1,
    ):
        """GraphLang.step + 汚染除去 + 往復忠実度。

        忠実度が低く汚れが残る場合、max_resteps まで再 step (0.5B 配管の再循環)。
        計測:
          1) graph→graph(step)  — 軸/概念/候補の保存
          2) vector→graph→vector — dist 再合成埋め込み vs 元 z の埋め込み
        """
        from puzzle_decontaminator import PuzzleDecontaminator

        deco = PuzzleDecontaminator()
        refined = self.think_on_graph(seed, rounds=graph_rounds)
        reports: List[FidelityReport] = []
        resteps = 0

        def _measure(current):
            local: List[FidelityReport] = []
            r_preserve = fidelity_graph_preserve(seed, current)
            self.record_fidelity(r_preserve)
            local.append(r_preserve)
            dist_after = getattr(current, "dist", None)
            if self.vector is not None:
                z_after = self.vector.reconstruct_from_dist(dist_after)
                z_before_embed = None
                if consensus_z is not None and hasattr(self.vector, "embed_from_hidden"):
                    z_before_embed = self.vector.embed_from_hidden(consensus_z)
                r_vgv = fidelity_vector_graph_vector(
                    z_before_embed if z_before_embed is not None else consensus_z,
                    z_after if z_after is not None else consensus_z,
                    dist_before=consensus_dist or getattr(seed, "dist", None),
                    dist_after=dist_after,
                )
                if z_after is None:
                    r_vgv.notes.append("reconstruct_from_dist failed — dist-only score")
                self.record_fidelity(r_vgv)
                local.append(r_vgv)
            return local

        reports = _measure(refined)
        decontam = getattr(self.graph, "last_decontam", None)
        # step 内で浄化済みでも、強制もう一段かけられる
        if decontam is None:
            refined, decontam = deco.purify_canvas(refined, force=True)

        while (resteps < max_resteps
               and decontam is not None
               and deco.should_restep(reports, decontam)):
            resteps += 1
            # 再循環: 浄化した画を種にもう一度 step (peers 無しの自己浄化でも可)
            refined = self.think_on_graph(refined, rounds=1)
            reports = _measure(refined)
            decontam = getattr(self.graph, "last_decontam", None)
            if decontam is None:
                refined, decontam = deco.purify_canvas(refined, force=True)

        refined.meta = dict(getattr(refined, "meta", None) or {})
        refined.meta["fidelity"] = [r.as_dict() for r in reports]
        refined.meta["fidelity_ok"] = all(r.ok() for r in reports)
        refined.meta["resteps"] = resteps
        if decontam is not None:
            refined.meta["decontam"] = (
                decontam.as_dict() if hasattr(decontam, "as_dict") else decontam)
        return refined, reports

    def measure_nl_roundtrip(self, question: str, answer: str, canvas) -> FidelityReport:
        """発話後: 質問+グラフ要約 ↔ 回答 の NL 忠実度 (粗い)。"""
        graph_nl = ""
        if canvas is not None and hasattr(canvas, "as_peer_summary"):
            graph_nl = canvas.as_peer_summary()
        # 質問の内容語が回答に残っているか + グラフ候補が回答に触れているか
        seed_text = f"{question} {graph_nl}"
        report = fidelity_nl_graph_nl(seed_text, answer or "")
        # 候補トークンのヒットで加点
        hits = 0
        total = 0
        ans_l = (answer or "").lower()
        for s, w in (getattr(canvas, "dist", None) or [])[:6]:
            total += 1
            if (s or "").strip() and (s or "").strip().lower() in ans_l:
                hits += 1
        if total:
            bonus = hits / total
            report.parts["cand_in_answer"] = float(bonus)
            report.score = float(min(1.0, 0.6 * report.score + 0.4 * bonus))
            report.direction = "nl↔graph↔nl(speak)"
        self.record_fidelity(report)
        return report

    def fidelity_summary(self) -> Dict[str, Any]:
        return {
            "n": len(self.last_fidelity),
            "reports": [r.as_dict() for r in self.last_fidelity],
            "all_ok": all(r.ok() for r in self.last_fidelity) if self.last_fidelity else False,
            "mean_score": (
                float(np.mean([r.score for r in self.last_fidelity]))
                if self.last_fidelity else 0.0
            ),
        }


def build_hinge_for_council(council, *, peers=None, force_router_speaker=False) -> TriLanguageHinge:
    """Council インスタンスから三言語ヒンジを組み立てる。"""
    from abstract_link import LinkChannel

    peers = list(peers if peers is not None else [])
    link = LinkChannel(
        memory=council.memory, axes=council.axes,
        dictionary=council.dict, tok=council.tok, log=council.log,
    )
    speaker_peer = council._sage or (council._bridges[-1] if council._bridges else None)
    graph = LinkGraphLang(
        link=link,
        peers=peers,
        speaker_peer=speaker_peer,
        speaker_participates=bool(peers) and not force_router_speaker,
        catchball_rounds=1 if not peers else 2,
        memory=council.memory,
    )
    vector = RouterVectorLang(
        brain=council.brain, dictionary=council.dict, tok=council.tok,
    )
    # NaturalLang.speak は Council.speak 側で行う (二重発話を避ける)。
    # ここでは parse_to_graph / 計測用にプレースホルダを置く。
    natural = BriefNaturalLang(speak_fn=None)
    return TriLanguageHinge(vector=vector, graph=graph, natural=natural)
