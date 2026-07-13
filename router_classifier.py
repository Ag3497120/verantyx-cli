"""
router_classifier.py — 分類専用ルーター (neuro classifier at symbolic boundary)
==============================================================================
公理:
  - 回答・熟考・計画をしない。generate() 禁止。
  - 埋め込み (PromptEOL) / AxisAnchors.signature / 次トークン離散採点で柔軟に分類。
  - キーワードは安全網のみ。曖昧なら ambiguous=True + 保守デフォルト (生成で解消しない)。
  - Council / Matryoshka は別エントリポイント。同一 RustBrain を共有していても
    分類経路はこのモジュールの ClassifyOnlyBrain 経由に限る。

出力ラベル (離散):
  chat | task | search
Omni 互換では search → task に正規化できる (normalize_for_omni)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import numpy as np

# 低信頼: 生成せず ambiguous を立て、保守デフォルトへ
CONFIDENCE_FLOOR = 0.45
# Omni 向け保守デフォルト (議論側。誤って手足を動かすより安全)
CONSERVATIVE_DEFAULT = "chat"

LABELS = ("TASK", "SEARCH", "CHAT")
LABEL_TO_OMNI = {"TASK": "task", "SEARCH": "search", "CHAT": "chat"}


@dataclass
class ClassificationResult:
    """分類専用の戻り値。回答テキストは持たない。"""

    label: str                          # 'chat' | 'task' | 'search'
    confidence: float                   # [0, 1]
    scores: dict = field(default_factory=dict)  # label -> prob
    ambiguous: bool = False
    source: str = "fallback"            # reflex|hard|anchor|neuro|axis|fallback
    detail: str = ""
    qvec: Any = None
    axis_sig: Any = None                # (6,) or None
    raw: Any = None

    def as_route_dict(self) -> dict:
        """intent_router.route 互換 (search は task に正規化)。"""
        intent = "task" if self.label in ("task", "search") else "chat"
        return {
            "intent": intent,
            "source": self.source,
            "detail": self.detail,
            "qvec": self.qvec,
            "raw": self.raw,
            "label": self.label,
            "confidence": self.confidence,
            "scores": dict(self.scores),
            "ambiguous": self.ambiguous,
            "axis_sig": self.axis_sig,
        }


class ClassifyOnlyBrain:
    """RustBrain の classify 用ビュー。encode のみ。generate() は常に拒否。

    Phase 1: プロセス分離はしないが、API 境界で「分類専用」を強制する。
    Council / speak は元の brain ハンドルを別エントリから使うこと。
    """

    def __init__(self, brain):
        if isinstance(brain, ClassifyOnlyBrain):
            self._brain = brain._brain
        else:
            self._brain = brain
        self.vector_intervention = bool(
            getattr(self._brain, "vector_intervention", False))

    @property
    def underlying(self):
        return self._brain

    def encode(self, *args, **kwargs):
        return self._brain.encode(*args, **kwargs)

    def encode_soft(self, *args, **kwargs):
        return self._brain.encode_soft(*args, **kwargs)

    def generate(self, *args, **kwargs):
        raise RuntimeError(
            "ClassifyOnlyBrain: router path must not generate(). "
            "Use Council.ask / speaker entrypoints on a separate handle.")

    def trim(self):
        return self._brain.trim()

    def close(self):
        # 共有脳を分類側から閉じない
        return None


def wrap_for_classify(brain) -> ClassifyOnlyBrain:
    """分類経路に載せる脳ハンドル。既にラップ済みならそのまま。"""
    if isinstance(brain, ClassifyOnlyBrain):
        return brain
    return ClassifyOnlyBrain(brain)


# ── Axis prior (立体十字の粗い偏り。推論ではない) ─────────────────────────────
# Syntax/Code が高い → 作業寄り / Factual が高く Syntax が低い → 議論寄り
_AXIS_TASK_IDX = 1   # Syntax/Code
_AXIS_CHAT_IDX = 2   # Factual Memory


def axis_prior_bias(axis_sig) -> Optional[dict]:
    """AxisAnchors.signature → 弱いラベル偏り。無ければ None。"""
    if axis_sig is None:
        return None
    sig = np.asarray(axis_sig, dtype=np.float64).reshape(-1)
    if sig.size < 6:
        return None
    syntax = float(sig[_AXIS_TASK_IDX])
    factual = float(sig[_AXIS_CHAT_IDX])
    # 相対差が小さいときは使わない
    if abs(syntax - factual) < 0.08:
        return None
    if syntax > factual:
        return {"task": 0.08, "search": 0.02, "chat": -0.05,
                "note": f"axis Syntax>{factual:.2f}→task lean"}
    return {"task": -0.05, "search": -0.02, "chat": 0.08,
            "note": f"axis Factual>{syntax:.2f}→chat lean"}


def _softmax_temps(logits: Mapping[str, float], temp: float = 0.7) -> dict:
    keys = list(logits.keys())
    vals = np.array([float(logits[k]) for k in keys], dtype=np.float64)
    vals -= vals.max()
    probs = np.exp(vals / max(temp, 1e-6))
    probs /= probs.sum() + 1e-12
    return {k: float(p) for k, p in zip(keys, probs)}


def neuro_next_token_scores(brain, tok, text: str, dictionary) -> tuple[dict, str]:
    """0.5B 次トークン分布で TASK/SEARCH/CHAT を採点 (自由生成しない)。

    戻り値: (scores_upper, detail_str)  scores キーは TASK/SEARCH/CHAT
    """
    from intent_router import _CLASSIFY_PROMPT, _label_token_ids

    if not getattr(brain, "vector_intervention", False):
        raise RuntimeError("neuro classify requires vector-intervention brain")
    prompt = _CLASSIFY_PROMPT.format(text=text[:800])
    ids = tok.encode(prompt, add_special_tokens=False)
    z = brain.encode(ids)
    logits = dictionary.logits(np.asarray(z, dtype=np.float32))
    label_ids = _label_token_ids(tok)
    raw_logits = {}
    for label in LABELS:
        tids = label_ids.get(label) or []
        raw_logits[label] = float(max(logits[t] for t in tids)) if tids else -1e9
    probs = _softmax_temps(raw_logits, temp=0.7)
    ranking = sorted(probs.items(), key=lambda x: -x[1])
    detail = " ".join(f"{lab}={pr * 100:.0f}%" for lab, pr in ranking)
    return probs, detail


def _apply_soft_chat_correction(best: str, text: str, detail: str) -> tuple[str, str]:
    from intent_router import soft_chat_hint
    if best in ("TASK", "SEARCH") and soft_chat_hint(text):
        return "CHAT", detail + " (factoid→chat)"
    return best, detail


def classify(
    text: str,
    brain,
    tok,
    dictionary=None,
    *,
    reflex=None,
    memory_enabled: bool = True,
    qvec=None,
    axes=None,
    confidence_floor: float = CONFIDENCE_FLOOR,
) -> ClassificationResult:
    """ユーザー文 → 離散ラベル。generate() は一切呼ばない。

    優先順位:
      1. 反射弓 (類似経験)
      2. 明確動詞 (hard)
      3. 時間アンカー → search
      4. neuro (次トークン離散採点) ± AxisAnchors prior
      5. 保守フォールバック + ambiguous
    """
    from verantyx_mind import embed_text
    import cognitive_anchors
    from intent_router import hard_task_hint

    clf_brain = wrap_for_classify(brain)
    result = ClassificationResult(
        label=CONSERVATIVE_DEFAULT,
        confidence=0.0,
        source="fallback",
        qvec=qvec,
    )

    if result.qvec is None and clf_brain.vector_intervention:
        try:
            result.qvec = embed_text(clf_brain, tok, text)
        except Exception as e:
            result.detail = f"embed failed: {e}"

    # Axis signature (情報キャリアの粗い指紋。推論ではない)
    if axes is not None and getattr(axes, "available", False) and result.qvec is not None:
        try:
            result.axis_sig = axes.signature(result.qvec)
        except Exception:
            result.axis_sig = None

    # 1) 反射弓
    if memory_enabled and reflex is not None and result.qvec is not None:
        adv = reflex.advise(result.qvec)
        if adv and adv.get("intent") in ("task", "chat") and adv["sim"] >= 0.88:
            result.label = adv["intent"]
            result.confidence = float(min(1.0, adv["sim"]))
            result.source = "reflex"
            result.scores = {result.label: result.confidence}
            result.detail = (f"類似経験 sim={adv['sim']:.2f} "
                             f"'{adv.get('src', '')}'")
            result.ambiguous = result.confidence < confidence_floor
            return result

    # 2) 明確な作業動詞
    if hard_task_hint(text):
        result.label = "task"
        result.confidence = 0.95
        result.source = "hard"
        result.scores = {"task": 0.95}
        result.detail = "明確な作業動詞"
        return result

    # 3) 時間アンカー → search (Omni では task 正規化)
    if cognitive_anchors.is_time_sensitive(text):
        result.label = "search"
        result.confidence = 0.9
        result.source = "anchor"
        result.scores = {"search": 0.9}
        result.detail = "時間依存 → web 確認"
        return result

    # 4) neuro 次トークン採点 (+ 弱い axis prior)
    if clf_brain.vector_intervention and dictionary is not None:
        try:
            probs_u, detail = neuro_next_token_scores(
                clf_brain, tok, text, dictionary)
            # axis prior を logit 空間ではなく確率に小さな加算
            bias = axis_prior_bias(result.axis_sig)
            scores = {
                "task": probs_u["TASK"],
                "search": probs_u["SEARCH"],
                "chat": probs_u["CHAT"],
            }
            if bias:
                for k in ("task", "search", "chat"):
                    scores[k] = max(0.0, scores[k] + float(bias.get(k, 0.0)))
                ssum = sum(scores.values()) or 1.0
                scores = {k: v / ssum for k, v in scores.items()}
                detail = detail + f" | {bias['note']}"
                result.source = "neuro+axis"
            else:
                result.source = "neuro"

            best_u = max(probs_u.items(), key=lambda x: x[1])[0]
            best_u, detail = _apply_soft_chat_correction(best_u, text, detail)
            # soft_chat 補正後は CHAT 固定。axis 補正後の scores も揃える
            if best_u == "CHAT":
                label = "chat"
            elif best_u == "SEARCH":
                label = "search"
            else:
                label = "task"
            # soft_chat で CHAT に寄せた場合、scores も chat 優勢に
            if best_u == "CHAT" and max(scores, key=scores.get) != "chat":
                scores = {"chat": 0.55, "task": 0.30, "search": 0.15}

            confidence = float(scores.get(label, 0.0))
            # 接戦で soft_chat でない → 既存 route に近い close→task
            from intent_router import soft_chat_hint
            if (confidence < confidence_floor
                    and (scores["task"] + scores["search"]) >= confidence
                    and not soft_chat_hint(text)):
                label = "task"
                confidence = float(scores["task"] + scores["search"])
                detail = detail + " (close→task)"

            ambiguous = confidence < confidence_floor
            if ambiguous:
                # 生成せず保守デフォルト。スコアは残す
                result.label = CONSERVATIVE_DEFAULT
                result.confidence = confidence
                result.scores = scores
                result.ambiguous = True
                result.detail = f"0.5B {detail} (ambiguous→{CONSERVATIVE_DEFAULT})"
                result.raw = detail
                return result

            result.label = label
            result.confidence = confidence
            result.scores = scores
            result.ambiguous = False
            result.detail = f"0.5B {detail}"
            result.raw = detail
            return result
        except Exception as e:
            result.detail = f"neuro classify failed: {e}"

    # 5) フォールバック
    result.label = CONSERVATIVE_DEFAULT
    result.confidence = 0.0
    result.source = "fallback"
    result.ambiguous = True
    result.scores = {CONSERVATIVE_DEFAULT: 0.0}
    if not result.detail:
        result.detail = "分類不能 → 保守デフォルト (評議会)"
    return result


def classify_omni(text: str, brain, tok, dictionary=None, **kwargs) -> dict:
    """Omni 入口用: ClassificationResult → route 互換 dict (search→task)。"""
    return classify(text, brain, tok, dictionary, **kwargs).as_route_dict()
