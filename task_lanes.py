"""task_lanes.py — 問題型レーン (確定値を soft 平均に沈めない)
==============================================================================

レーン:
  determinate  … 計算・閉じた確定事実 → ground + lock。soft/合議平均を通さない
  relational   … 関係・制約ロジック → puzzle join (+ 薄い company)
  factual      … 開いた事実 → 記憶/検索 ground を厚く、平均で薄めない
  default      … その他 (易問は短絡)

大型 jgen の「発火なし静的辞書」は static_jgen_dict.py を参照。
語彙接地には効くが、確定計算・事実 DB の代替にはならない。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Dist = List[Tuple[str, float]]

LANE_DETERMINATE = "determinate"
LANE_RELATIONAL = "relational"
LANE_FACTUAL = "factual"
LANE_DEFAULT = "default"


# 閉じた確定事実 (手足なしでも使える最小静的辞書)
_STATIC_FACTS: Dict[str, str] = {
    "how many days are there in a leap year": "366",
    "how many days in a leap year": "366",
    "how many hours are in a day": "24",
    "how many hours in a day": "24",
    "how many minutes are in an hour": "60",
    "how many seconds are in a minute": "60",
}


@dataclass
class LaneDecision:
    lane: str
    reason: str = ""
    locked_answer: Optional[str] = None
    ground_source: str = ""  # arith | static_fact | none
    dist: Dist = field(default_factory=list)
    allow_soft: bool = True
    allow_peer_cycle: bool = True
    use_puzzle_worker: bool = True
    use_company: bool = True
    speak_locked: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "lane": self.lane,
            "reason": self.reason,
            "locked_answer": self.locked_answer,
            "ground_source": self.ground_source,
            "allow_soft": self.allow_soft,
            "allow_peer_cycle": self.allow_peer_cycle,
            "use_puzzle_worker": self.use_puzzle_worker,
            "use_company": self.use_company,
            "speak_locked": self.speak_locked,
            "meta": self.meta,
        }


def try_simple_arithmetic(question: str) -> Optional[str]:
    """明確な二値四則 + 速度×時間。"""
    q = (question or "").strip().lower()
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*"
        r"(plus|\+|minus|-|multiplied by|times|\*|×|x|divided by|/)\s*"
        r"(\d+(?:\.\d+)?)",
        q,
    )
    if m:
        try:
            a, op, b = float(m.group(1)), m.group(2), float(m.group(3))
        except Exception:
            a = op = b = None
        if a is not None:
            if op in ("plus", "+"):
                r = a + b
            elif op in ("minus", "-"):
                r = a - b
            elif op in ("multiplied by", "times", "*", "×", "x"):
                r = a * b
            elif op in ("divided by", "/"):
                if abs(b) < 1e-12:
                    return None
                r = a / b
            else:
                r = None
            if r is not None:
                return _fmt_num(r)
    # "product of A and B" / "sum of A and B"
    m_prod = re.search(
        r"(?:product|sum)\s+of\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)", q)
    if m_prod:
        try:
            a, b = float(m_prod.group(1)), float(m_prod.group(2))
            if "product" in m_prod.group(0):
                return _fmt_num(a * b)
            return _fmt_num(a + b)
        except Exception:
            pass

    # speed × time → distance
    m2 = re.search(
        r"(?:travels?|goes?|drives?)\s+at\s+(\d+(?:\.\d+)?)\s*"
        r"(?:km/h|kmh|mph)?\s+for\s+(\d+(?:\.\d+)?)\s*hours?",
        q,
    )
    if m2:
        try:
            return _fmt_num(float(m2.group(1)) * float(m2.group(2)))
        except Exception:
            pass
    return None


def try_static_fact(question: str) -> Optional[str]:
    q = re.sub(r"[?\s]+$", "", (question or "").strip().lower())
    q = re.sub(r"\s+", " ", q)
    if q in _STATIC_FACTS:
        return _STATIC_FACTS[q]
    for key, val in _STATIC_FACTS.items():
        if key in q:
            return val
    return None


def try_store_total(question: str) -> Optional[str]:
    """shirts $A × n + pants $B × m − coupon の簡易パターン。"""
    q = (question or "").lower()
    sm = re.search(r"shirts?\s+for\s+\$?\s*(\d+(?:\.\d+)?)", q)
    pm = re.search(r"pants?\s+for\s+\$?\s*(\d+(?:\.\d+)?)", q)
    bn = re.search(r"buy\s+(\d+)\s+shirts?", q)
    bp = re.search(r"(\d+)\s+pairs?\s+of\s+pants", q)
    if not bp:
        bp = re.search(r"(\d+)\s+pants", q)
    coup = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(?:coupon|discount|off)", q)
    if not (sm and pm and bn and bp):
        return None
    try:
        total = (
            float(sm.group(1)) * int(bn.group(1))
            + float(pm.group(1)) * int(bp.group(1))
        )
        if coup:
            total -= float(coup.group(1))
        return _fmt_num(total)
    except Exception:
        return None


def _fmt_num(r: float) -> str:
    if abs(r - round(r)) < 1e-9:
        return str(int(round(r)))
    return f"{r:.4g}"


def lock_dist(answer: str, rivals: Optional[Dist] = None) -> Dist:
    """確定答えを頂点質量にした dist (平均で薄めない)。"""
    ans = (answer or "").strip()
    if not ans:
        return []
    items: Dist = [(ans, 0.85)]
    for s, w in rivals or []:
        t = (s or "").strip()
        if not t or t == ans:
            continue
        items.append((t, float(w) * 0.15))
    tot = sum(w for _, w in items) or 1.0
    return [(s, w / tot) for s, w in items[:12]]


def logic_puzzle_meta() -> Dict[str, Any]:
    """logic/relational 用パズル既定 (env で上書き可)。

    depth↑: 軸接合の反復を増やす
    gate↓: より多くの軸を接合に残す (energy >= gate)
    """
    import os
    depth = 3
    gate = 0.14
    try:
        if os.environ.get("VERANTYX_LOGIC_PUZZLE_DEPTH"):
            depth = max(1, min(4, int(os.environ["VERANTYX_LOGIC_PUZZLE_DEPTH"])))
        if os.environ.get("VERANTYX_LOGIC_PUZZLE_GATE"):
            gate = float(os.environ["VERANTYX_LOGIC_PUZZLE_GATE"])
            gate = max(0.08, min(0.35, gate))
    except Exception:
        pass
    return {
        "puzzle_depth": depth,
        "puzzle_gate": gate,
        "puzzle_div": False,
        # company 合流ヒント
        "worker_blend": 0.68,
        "worker_min_overlap": 0.30,
        "critic_blend": 0.08,
        "skip_memory_attach": True,
        "logic_tune": True,
    }


def looks_relational(question: str) -> bool:
    """関係・制約ロジック (ベンチ logic 系)。"""
    q = (question or "").lower()
    keys = (
        "older than", "younger", "taller", "shorter", "in front of",
        "behind", "all but", "all labels are wrong", "who is the",
        "who is at", "therefore", "if and only", "boxes:",
        "very front", "very back", "youngest", "oldest", "tallest",
        "shortest", "both apples", "both oranges", "both hats",
        "box a contains", "box b contains", "red balls", "blue balls",
        "drawn at random", "more likely", "probability",
        "より年上", "より背", "一番", "ラベル", "前にいる", "後ろ",
    )
    if any(k in q for k in keys):
        return True
    # A is X than B. B is X than C.
    if re.search(r"\bis\s+\w+\s+than\b.+\bis\s+\w+\s+than\b", q, re.S):
        return True
    # 箱ラベル / 順序の典型
    if "all labels" in q and ("wrong" in q or "incorrect" in q):
        return True
    if re.search(r"box\s+[ab]\b", q) and ("ball" in q or "red" in q or "blue" in q):
        return True
    return False


def looks_open_factual(question: str) -> bool:
    q = (question or "").lower()
    hints = (
        "who is", "what is the capital", "when was", "where is",
        "latest", "today", "news", "weather", "price",
        "大統領", "首都", "いつ", "どこ",
    )
    return any(h in q for h in hints)


def resolve_determinate(question: str) -> Optional[Tuple[str, str]]:
    """(answer, source) or None。"""
    for fn, src in (
        (try_simple_arithmetic, "arith"),
        (try_store_total, "store_arith"),
        (try_static_fact, "static_fact"),
    ):
        ans = fn(question)
        if ans:
            return ans, src
    return None


def classify_lane(question: str) -> LaneDecision:
    """入口でレーン決定。確定は合議・soft を遮断。"""
    q = (question or "").strip()
    det = resolve_determinate(q)
    if det:
        ans, src = det
        return LaneDecision(
            lane=LANE_DETERMINATE,
            reason=f"ground:{src}",
            locked_answer=ans,
            ground_source=src,
            dist=lock_dist(ans),
            allow_soft=False,
            allow_peer_cycle=False,
            use_puzzle_worker=False,
            use_company=False,
            speak_locked=True,
            meta={"skip_deliberation": True},
        )
    if looks_relational(q):
        return LaneDecision(
            lane=LANE_RELATIONAL,
            reason="relational_constraints",
            allow_soft=False,  # 関係問でも soft 再注入は質量を濁す
            allow_peer_cycle=False,
            use_puzzle_worker=True,
            use_company=True,
            speak_locked=False,
            meta=logic_puzzle_meta(),
        )
    if looks_open_factual(q):
        return LaneDecision(
            lane=LANE_FACTUAL,
            reason="open_factual",
            allow_soft=False,
            allow_peer_cycle=False,
            use_puzzle_worker=False,
            use_company=True,
            speak_locked=False,
            meta={"prefer_memory_web": True},
        )
    # 易しい閉じた問い: company 短絡
    short = len(q) <= 110 and not re.search(r"\d+\s*[+\-*/]", q)
    return LaneDecision(
        lane=LANE_DEFAULT,
        reason="default",
        allow_soft=False,
        allow_peer_cycle=False,
        use_puzzle_worker=not short,
        use_company=not short,
        speak_locked=False,
        meta={"easy_shortcircuit": short},
    )


def apply_lane_to_canvas(canvas, decision: LaneDecision):
    """確定ロックを canvas に刻む。"""
    if canvas is None or decision is None:
        return canvas
    canvas.meta = dict(getattr(canvas, "meta", None) or {})
    canvas.meta["lane"] = decision.as_dict()
    if decision.locked_answer:
        canvas.dist = list(decision.dist or lock_dist(decision.locked_answer))
        canvas.concepts = [decision.locked_answer] + [
            c for c in (canvas.concepts or []) if c != decision.locked_answer
        ][:7]
        canvas.propositions = (
            [f"Locked ground ({decision.ground_source}): {decision.locked_answer}"]
            + list(canvas.propositions or [])
        )[:6]
        canvas.confidence = 0.92
        canvas.source = f"lane:{decision.lane}"
        canvas.meta["puzzle"] = {
            **dict((canvas.meta or {}).get("puzzle") or {}),
            "arith": decision.locked_answer
            if decision.ground_source in ("arith", "store_arith")
            else None,
            "locked": decision.locked_answer,
            "ground": decision.ground_source,
        }
    return canvas
