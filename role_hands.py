"""role_hands.py — 会社役割ごとの手足 (Hand)
==============================================================================

原則:
  - 出力は AbstractCanvas / mid-graph のみ (生 z は渡さない)
  - 1役割・1ラウンド・最大1ツール
  - ceo が ToolBudget を出し、許可された Hand だけ発火
  - 確定値は平均で薄めず grounds / lock dist に載せる

Hands:
  ceo         → budget (search/calc/memory 許可フラグ)
  worker      → calc (task_lanes) / puzzle は company 本体が担当
  critic      → web_search (+ 構造化 ingest キュー)
  integrator  → memory search_graph
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

Dist = List[Tuple[str, float]]


@dataclass
class ToolBudget:
    search: int = 0
    calc: int = 0
    memory: int = 0
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "search": int(self.search),
            "calc": int(self.calc),
            "memory": int(self.memory),
            "reason": self.reason,
        }


def _parse_search_links(raw: str, k: int = 5) -> List[Tuple[str, str]]:
    """verantyx_browser.search 出力 (- title / url) を (title, url) に。"""
    links: List[Tuple[str, str]] = []
    title = None
    for ln in str(raw or "").splitlines():
        s = ln.strip()
        if s.startswith("http"):
            if title:
                links.append((title, s))
                title = None
            else:
                links.append((s[:40], s))
        elif s.startswith("- "):
            title = s[2:].strip()
        if len(links) >= k:
            break
    return links[:k]


def budget_for_lane(lane_name: str, question: str = "") -> ToolBudget:
    """レーンに応じた既定予算。"""
    lane = (lane_name or "default").lower()
    if lane == "determinate":
        return ToolBudget(search=0, calc=1, memory=0, reason="determinate")
    if lane == "relational":
        return ToolBudget(search=0, calc=0, memory=1, reason="relational")
    if lane == "factual":
        return ToolBudget(search=1, calc=0, memory=1, reason="factual")
    # default: 開いた問いっぽければ search
    q = (question or "").lower()
    if any(h in q for h in ("who", "what", "when", "where", "latest", "today", "news")):
        return ToolBudget(search=1, calc=0, memory=1, reason="default_open")
    return ToolBudget(search=0, calc=0, memory=0, reason="default_closed")


def _canvas(question: str, *, role: str, dist: Dist = None,
            concepts=None, propositions=None, grounds=None,
            confidence: float = 0.5, meta=None):
    from abstract_link import AbstractCanvas
    g = list(grounds or [])
    return AbstractCanvas(
        question=question,
        dist=list(dist or []),
        concepts=list(concepts or [])[:8],
        propositions=list(propositions or [])[:6],
        pattern_hits=g[:6],
        confidence=float(confidence),
        source=f"hand:{role}",
        meta={
            "role": role,
            "hand": True,
            "grounds": g[:10],
            **dict(meta or {}),
        },
    )


class RoleHand:
    """役割手足の実行器。"""

    def __init__(self, council=None, log=None):
        self.council = council
        self.log = log or (lambda *_a, **_k: None)

    def run(
        self,
        role: str,
        question: str,
        *,
        budget: Optional[ToolBudget] = None,
        lane_name: str = "default",
        base_canvas=None,
    ):
        """(canvas_delta | None, meta)。canvas_delta は合流用の薄い画。"""
        role = (role or "").lower()
        budget = budget or budget_for_lane(lane_name, question)
        if role == "ceo":
            return self._hand_ceo(question, budget, lane_name)
        if role == "worker":
            return self._hand_worker(question, budget, base_canvas)
        if role == "critic":
            return self._hand_critic(question, budget, lane_name)
        if role == "integrator":
            return self._hand_integrator(question, budget, base_canvas)
        return None, {"skipped": f"unknown_role:{role}"}

    def _hand_ceo(self, question, budget: ToolBudget, lane_name: str):
        props = [
            f"ToolBudget search={budget.search} calc={budget.calc} "
            f"memory={budget.memory} ({budget.reason})",
            f"Lane target: {lane_name}",
        ]
        c = _canvas(
            question, role="ceo",
            dist=[(lane_name or "default", 1.0)],
            concepts=["budget", lane_name],
            propositions=props,
            confidence=0.7,
            meta={"budget": budget.as_dict()},
        )
        return c, {"budget": budget.as_dict()}

    def _hand_worker(self, question, budget: ToolBudget, base_canvas):
        if budget.calc < 1:
            return None, {"skipped": "calc_budget_0"}
        from task_lanes import resolve_determinate, lock_dist
        hit = resolve_determinate(question)
        if not hit:
            return None, {"skipped": "no_calc_ground"}
        ans, src = hit
        c = _canvas(
            question, role="worker",
            dist=lock_dist(ans),
            concepts=[ans],
            propositions=[f"Calc ground ({src}): {ans}"],
            grounds=[f"calc:{src}:{ans}"],
            confidence=0.95,
            meta={"locked": ans, "ground_source": src},
        )
        return c, {"locked": ans, "source": src}

    def _hand_critic(self, question, budget: ToolBudget, lane_name: str):
        if budget.search < 1:
            return None, {"skipped": "search_budget_0"}
        try:
            from verantyx_browser import search
            from web_structure import (
                structure_from_markdown, enqueue_knowledge_gap,
                remember_structured,
            )
            raw = search(question, k=5)
            if not raw or not str(raw).strip():
                enqueue_knowledge_gap(question, reason="search_empty")
                return None, {"skipped": "search_empty", "queued": True}
            links = _parse_search_links(raw)
            grounds = [f"web:{u}" for _, u in links[:4]]
            concepts = [t for t, _ in links[:5]]
            props = [f"Web hit: {t}" for t, _ in links[:4]]
            # 先頭ページを構造化して記憶へ (失敗しても検索タイトルは残す)
            structured = None
            if links:
                try:
                    from verantyx_browser import fetch
                    md = fetch(links[0][1])
                    structured = structure_from_markdown(
                        md, url=links[0][1], title=links[0][0])
                    mem = getattr(self.council, "memory", None) if self.council else None
                    if mem is not None and getattr(mem, "enabled", False):
                        remember_structured(mem, structured, question=question)
                except Exception as e:
                    enqueue_knowledge_gap(
                        question, reason=f"fetch_struct_fail:{e}"[:80],
                        urls=[links[0][1]])
            # 候補質量: タイトル先頭語を薄く
            dist: Dist = []
            for t, _u in links[:6]:
                head = (t.split() or [t])[0][:40]
                if head:
                    dist.append((head, 1.0))
            if dist:
                s = sum(w for _, w in dist) or 1.0
                dist = [(a, b / s) for a, b in dist]
            if structured:
                for c in (structured.get("concepts") or [])[:4]:
                    if c not in concepts:
                        concepts.append(c)
                for p in (structured.get("propositions") or [])[:2]:
                    props.append(p)
                grounds.extend(structured.get("grounds") or [])
            canvas = _canvas(
                question, role="critic",
                dist=dist,
                concepts=concepts,
                propositions=props,
                grounds=grounds,
                confidence=0.55 if links else 0.3,
                meta={"n_links": len(links), "structured": bool(structured)},
            )
            self.log(f"[Hand:critic] search links={len(links)} "
                     f"struct={bool(structured)}")
            return canvas, {"links": links[:5], "structured": bool(structured)}
        except Exception as e:
            enqueue_knowledge_gap(question, reason=f"search_err:{e}"[:80])
            return None, {"error": str(e)[:160]}

    def _hand_integrator(self, question, budget: ToolBudget, base_canvas):
        if budget.memory < 1:
            return None, {"skipped": "memory_budget_0"}
        mem = getattr(self.council, "memory", None) if self.council else None
        if mem is None or not getattr(mem, "enabled", False):
            return None, {"skipped": "memory_off"}
        try:
            from memory_graph import MemoryGraph
            q = MemoryGraph.from_canvas(base_canvas) if base_canvas is not None else (
                MemoryGraph(l3_text=question[:160], concepts=[], kind="hand_query")
            )
            if not getattr(q, "l3_text", None):
                q.l3_text = question[:160]
            hits = mem.search_graph(q, k=4, min_score=0.06) if hasattr(mem, "search_graph") else []
            if not hits:
                from web_structure import enqueue_knowledge_gap
                enqueue_knowledge_gap(question, reason="memory_miss")
                return None, {"skipped": "memory_miss", "queued": True}
            concepts, props, grounds, dist = [], [], [], []
            for g, scores, rec in hits:
                for c in (g.concepts or [])[:3]:
                    if c not in concepts:
                        concepts.append(c)
                for p in (g.propositions or [])[:2]:
                    props.append(p)
                for gr in (g.grounds or [])[:2]:
                    grounds.append(str(gr))
                for s, w in (g.candidates or [])[:3]:
                    dist.append((s, float(w)))
                grounds.append(f"mem:{rec.get('id')}:{rec.get('kind')}")
            if dist:
                tot = sum(w for _, w in dist) or 1.0
                dist = [(s, w / tot) for s, w in dist[:12]]
            c = _canvas(
                question, role="integrator",
                dist=dist,
                concepts=concepts,
                propositions=props[:6],
                grounds=grounds,
                confidence=0.6,
                meta={"n_hits": len(hits)},
            )
            return c, {"n_hits": len(hits)}
        except Exception as e:
            return None, {"error": str(e)[:160]}


def merge_hand_into_canvas(canvas, hand_canvas, *, protect: bool = True):
    """Hand 結果を役割 canvas に合流。ground は薄めない。"""
    if canvas is None or hand_canvas is None:
        return canvas
    from verantyx_council import protect_dist_mass
    out = canvas.clone() if hasattr(canvas, "clone") else canvas
    if hand_canvas.dist:
        if protect and out.dist:
            out.dist = protect_dist_mass(
                hand_canvas.dist, out.dist, min_overlap=0.15, blend=0.45)
        else:
            out.dist = list(hand_canvas.dist)
    for c in hand_canvas.concepts or []:
        if c not in (out.concepts or []):
            out.concepts = list(out.concepts or []) + [c]
    out.concepts = (out.concepts or [])[:10]
    for p in hand_canvas.propositions or []:
        if p not in (out.propositions or []):
            out.propositions = list(out.propositions or []) + [p]
    out.propositions = (out.propositions or [])[:8]
    g0 = list((out.meta or {}).get("grounds") or [])
    for g in (hand_canvas.meta or {}).get("grounds") or []:
        if g not in g0:
            g0.append(g)
    for h in hand_canvas.pattern_hits or []:
        if h not in (out.pattern_hits or []):
            out.pattern_hits = list(out.pattern_hits or []) + [h]
    out.pattern_hits = (out.pattern_hits or [])[:8]
    out.meta = dict(out.meta or {})
    out.meta["grounds"] = g0[:12]
    out.meta["hand"] = (hand_canvas.meta or {})
    if (hand_canvas.meta or {}).get("locked"):
        out.meta.setdefault("puzzle", {})
        if isinstance(out.meta["puzzle"], dict):
            out.meta["puzzle"]["locked"] = hand_canvas.meta["locked"]
            out.meta["puzzle"]["arith"] = hand_canvas.meta.get("locked")
    return out
