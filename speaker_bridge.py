"""speaker_bridge.py — 発話役ブリーフと異モデル合意の橋渡し
==============================================================================

問題:
  - 隠れ次元が違う (0.5B≈896/1024 vs 9B≈4096…) と生ベクトルは渡せない
  - 同じ次元でも学習空間が違い、「同じ座標 ≠ 同じ意味」
  - だから 9B に 0.5B の合意 z をそのまま注入しても翻訳できない

解 (既存の JCross 方針を製品化する):
  生の隠れ状態はモデル内だけに閉じる。
  モデル境界では必ず **語彙分布インターリンガ** [(文字列, 確率), ...] に落とす。
  - 埋め込みを持てる相手: dist → 相手の embed 行で soft 仮想トークン再合成
  - API 相手 (Ollama/LM Studio): 分布 + 概念 + 予算付き根拠をテキストブリーフ化
  - 発話役: 思考をやり直させず、ブリーフを口にするだけに条件付け

加えてタスク種別に応じて memory / web / peer のブレンド比を動的に変える。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

Dist = List[Tuple[str, float]]

# タスク種別ごとのソース配分 (合計≈1.0)。発話プロンプトの根拠スロット予算に使う。
BLEND_TABLE: Dict[str, Dict[str, float]] = {
    "memory": {"memory": 0.55, "consensus": 0.30, "web": 0.05, "peer": 0.10},
    "factual": {"memory": 0.10, "consensus": 0.25, "web": 0.45, "peer": 0.20},
    "ambiguous": {"memory": 0.20, "consensus": 0.35, "web": 0.15, "peer": 0.30},
    "tool": {"memory": 0.15, "consensus": 0.20, "web": 0.25, "peer": 0.40},
    "default": {"memory": 0.25, "consensus": 0.45, "web": 0.15, "peer": 0.15},
}

# 発話プロンプトに載せる根拠の最大文字数 (分離で空いた窓の一部をここに使う)
BUDGET_CHARS = {
    "memory": 900,
    "web": 700,
    "peer": 700,
    "consensus": 400,
}


def classify_task_kind(question: str, intent: Optional[str] = None) -> str:
    """粗いタスク種別。intent_router の結果があれば優先。"""
    if intent == "task":
        return "tool"
    q = (question or "").lower()
    mem_hints = ("remember", "前回", "以前", "昨日", "my name", "私が", "覚えて",
                 "先週", "last time", "you said")
    web_hints = ("今日", "最新", "today", "latest", "news", "現在の", "天気",
                 "price", "誰が大統領", "who is the")
    if any(h in q for h in mem_hints):
        return "memory"
    if any(h in q for h in web_hints):
        return "factual"
    if any(h in q for h in ("なぜ", "どう思う", "maybe", "perhaps", "曖昧", "どっち")):
        return "ambiguous"
    return "default"


def blend_for(kind: str) -> Dict[str, float]:
    return dict(BLEND_TABLE.get(kind) or BLEND_TABLE["default"])


def _clip(text: str, budget: int) -> str:
    t = (text or "").strip()
    if len(t) <= budget:
        return t
    return t[: max(0, budget - 1)].rstrip() + "…"


def dist_to_text(dist: Optional[Dist], top: int = 6) -> str:
    if not dist:
        return ""
    items = []
    for s, w in dist[:top]:
        s = (s or "").strip()
        if not s:
            continue
        items.append(f"{s} ({w * 100:.0f}%)")
    return ", ".join(items)


@dataclass
class SpeakerBrief:
    """異モデル境界を越える発話用パケット。生 z は含めない。"""

    question: str
    task_kind: str = "default"
    concepts: List[str] = field(default_factory=list)
    consensus_dist: Dist = field(default_factory=list)
    memory_texts: List[str] = field(default_factory=list)
    web_texts: List[str] = field(default_factory=list)
    peer_texts: List[str] = field(default_factory=list)
    blend: Dict[str, float] = field(default_factory=dict)
    language: Optional[str] = None
    # 実験: 発話目的を「読み上げ」に縛る。locked_answer があると再推論を禁止。
    purpose: str = "speak"  # speak | speak_locked
    locked_answer: Optional[str] = None

    def __post_init__(self):
        if not self.blend:
            self.blend = blend_for(self.task_kind)

    # ── 構築 ──────────────────────────────────────────────────────────────
    @classmethod
    def build(
        cls,
        question: str,
        *,
        concepts: Optional[Sequence[str]] = None,
        consensus_dist: Optional[Dist] = None,
        memory_hits: Optional[Sequence[Any]] = None,
        web_snippets: Optional[Sequence[str]] = None,
        peer_summaries: Optional[Sequence[str]] = None,
        intent: Optional[str] = None,
        task_kind: Optional[str] = None,
        language: Optional[str] = None,
        purpose: str = "speak",
        locked_answer: Optional[str] = None,
    ) -> "SpeakerBrief":
        kind = task_kind or classify_task_kind(question, intent=intent)
        blend = blend_for(kind)
        mem_texts: List[str] = []
        if memory_hits:
            for hit in memory_hits:
                if isinstance(hit, str):
                    mem_texts.append(hit)
                elif isinstance(hit, (tuple, list)) and hit:
                    mem_texts.append(str(hit[0]))
                elif isinstance(hit, dict):
                    mem_texts.append(str(hit.get("l3_text") or hit.get("text") or ""))
        # locked 未指定なら上位候補から短いロック文を作る (実験)
        locked = locked_answer
        if purpose == "speak_locked" and not locked and consensus_dist:
            tops = [((s or "").strip()) for s, _ in consensus_dist[:4] if (s or "").strip()]
            if tops:
                locked = " / ".join(tops[:3])
        return cls(
            question=question,
            task_kind=kind,
            concepts=[c for c in (concepts or []) if c],
            consensus_dist=list(consensus_dist or []),
            memory_texts=[t for t in mem_texts if t.strip()],
            web_texts=[t for t in (web_snippets or []) if t and str(t).strip()],
            peer_texts=[t for t in (peer_summaries or []) if t and str(t).strip()],
            blend=blend,
            language=language,
            purpose=purpose or "speak",
            locked_answer=locked,
        )

    # ── 異モデル: soft 再合成 (埋め込み共有できる相手向け) ─────────────────
    def to_soft_token(self, tok, embed_rows):
        """合意分布を相手モデルの埋め込み空間で仮想トークン列化する。
        生 z は使わない。失敗時は None。戻り値 shape=(n_soft, hidden)。"""
        if not self.consensus_dist:
            return None
        from verantyx_council import dist_to_soft_sequence
        try:
            return dist_to_soft_sequence(
                self.consensus_dist, tok, embed_rows, max_soft=12, sharpen=True)
        except Exception:
            return None

    # ── 発話役向けテキストブリーフ ─────────────────────────────────────────
    def evidence_block(self) -> str:
        """ブレンド比に応じて根拠スロットを埋める。合計文字予算を守る。"""
        parts = []
        # consensus は常に短く先頭へ (思考役の結論の核)
        if self.blend.get("consensus", 0) > 0.05:
            dist_s = dist_to_text(self.consensus_dist)
            cons = []
            if self.concepts:
                cons.append("concepts: " + ", ".join(self.concepts[:8]))
            if dist_s:
                cons.append("candidates: " + dist_s)
            if cons:
                budget = int(BUDGET_CHARS["consensus"] * self.blend["consensus"] / 0.45)
                parts.append(_clip(" | ".join(cons), max(120, budget)))

        def take(texts: Sequence[str], key: str, label: str):
            w = float(self.blend.get(key, 0))
            if w < 0.05 or not texts:
                return
            budget = int(BUDGET_CHARS[key] * (w / 0.25))
            budget = max(80, min(budget, BUDGET_CHARS[key]))
            blob = " // ".join(t.strip().replace("\n", " ") for t in texts if t.strip())
            parts.append(f"{label}: {_clip(blob, budget)}")

        take(self.memory_texts, "memory", "memory")
        take(self.web_texts, "web", "web")
        take(self.peer_texts, "peer", "peer")
        return "\n".join(parts)

    def system_prompt(self, *, for_api: bool = False) -> str:
        """発話役専用。長い思考を禁止し、ブリーフの結論化に寄せる。

        purpose=speak_locked のとき出力目的を「ロック答案の言語化」に固定する。
        再推論・別解の提案を明示禁止 (分離のデメリット潰し用の実験)。
        """
        if self.purpose == "speak_locked" and self.locked_answer:
            sys_p = (
                "You are a RENDERER, not a reasoner. "
                "Your ONLY job is to turn the LOCKED ANSWER into a short fluent reply. "
                "Do NOT recalculate, do NOT propose alternatives, do NOT contradict the lock. "
                "If unsure, still state the locked answer. "
                "End with a line starting exactly with 'Final answer:' "
                "followed by the locked conclusion."
            )
            sys_p += f"\nLOCKED ANSWER: {self.locked_answer}"
        else:
            sys_p = (
                "You are the SPEAKER, not the thinker. "
                "Do not re-solve the problem from scratch. "
                "Use the provided council brief and evidence. "
                "Answer concisely. End with a line starting exactly with "
                "'Final answer:' followed by the conclusion in plain language."
            )
        if self.language:
            native = {
                "Japanese": "常に日本語で答えてください。",
                "Chinese": "请始终用中文回答。",
                "Korean": "항상 한국어로 대답하세요。",
            }
            sys_p += f" Respond only in {self.language}. " + native.get(self.language, "")
        if self.concepts:
            sys_p += " Council consensus concepts: " + ", ".join(self.concepts[:8]) + "."
        if (for_api or self.purpose == "speak_locked") and self.consensus_dist:
            sys_p += (
                " Council candidate distribution: "
                + dist_to_text(self.consensus_dist)
                + "."
            )
        ev = self.evidence_block()
        if ev:
            sys_p += "\n\n[Brief — task=" + self.task_kind + " blend=" + \
                ",".join(f"{k}:{v:.2f}" for k, v in self.blend.items()) + \
                " purpose=" + self.purpose + "]\n" + ev
        return sys_p

    def user_prompt(self) -> str:
        return self.question

    def as_dict(self) -> Dict[str, Any]:
        return {
            "task_kind": self.task_kind,
            "blend": self.blend,
            "concepts": self.concepts,
            "consensus_dist_top": self.consensus_dist[:8],
            "memory_n": len(self.memory_texts),
            "web_n": len(self.web_texts),
            "peer_n": len(self.peer_texts),
            "purpose": self.purpose,
            "locked_answer": self.locked_answer,
        }


def remember_hits_for_question(memory, brain, tok, question: str, k: int = 3):
    """CortexMemory から発話ブリーフ用の L3 候補を取る。無効時は空。"""
    if memory is None or not getattr(memory, "enabled", False):
        return []
    try:
        from verantyx_mind import embed_text
        qv = embed_text(brain, tok, question)
        hits = memory.search(qv, k=k, query_text=question)
        # search -> (text, score, vec, concepts, id)
        return [h[0] for h in hits if h and h[0]]
    except Exception:
        return []
