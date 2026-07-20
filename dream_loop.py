"""dream_loop.py — 遊休自律進化 (DreamLoop)
==============================================================================

不足知識キューを主役にせず、遊休時に:

  Seed (fragile / dangling / gaps)
    → 予測パズル (次に聞かれそうな問い)
    → 機械的矛盾 (rivals)
    → Hand 解消 (memory → search)
    → 永遠記憶へ先入れ (dream_predict / dream_resolved)

起動:
  /dream [n]  … 明示
  VERANTYX_DREAM_AFTER_ASK=1  … ask 後 1 サイクル

予算/サイクル固定:
  predict≤3, search≤1, remember≤5, rivals≤2/問い
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class DreamBudget:
    predict: int = 3
    search: int = 1
    remember: int = 5
    rivals_per_q: int = 2
    audit: int = 1  # サイクルあたりグラフ監査回数

    def as_dict(self) -> Dict[str, int]:
        return {
            "predict": int(self.predict),
            "search": int(self.search),
            "remember": int(self.remember),
            "rivals_per_q": int(self.rivals_per_q),
            "audit": int(self.audit),
        }


@dataclass
class DreamSeed:
    question: str
    reason: str  # fragile | dangling | gap
    weight: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)


# ── Seed ──────────────────────────────────────────────────────────────────

def pick_seeds(council, k: int = 3) -> List[DreamSeed]:
    """点火順: fragile reflex → dangling memory → knowledge_gaps。"""
    out: List[DreamSeed] = []
    seen = set()

    def _add(q: str, reason: str, weight: float = 1.0, **meta):
        q = (q or "").strip()
        if not q or len(q) < 4:
            return
        key = q.lower()[:120]
        if key in seen:
            return
        seen.add(key)
        out.append(DreamSeed(question=q[:240], reason=reason,
                             weight=weight, meta=dict(meta)))

    # (1) fragile reflex
    reflex = getattr(council, "reflex", None)
    if reflex is not None:
        fragile_nodes = [
            n for n in (getattr(reflex, "index", None) or [])
            if n.get("fragile")
        ]
        # 新しい脆い問題を優先
        fragile_nodes = sorted(
            fragile_nodes, key=lambda n: float(n.get("ts") or 0), reverse=True)
        for n in fragile_nodes[: max(1, k)]:
            _add(n.get("question") or "", "fragile",
                 weight=1.2, reflex_id=n.get("id"))

    # (2) dangling / 低結合概念 from memory graphs
    mem = getattr(council, "memory", None)
    if mem is not None and getattr(mem, "enabled", False):
        for seed in _dangling_from_memory(mem, limit=max(1, k)):
            _add(seed.question, seed.reason, seed.weight, **seed.meta)

    # (3) knowledge gaps (第3)
    try:
        from web_structure import load_knowledge_gaps
        for g in reversed(load_knowledge_gaps(limit=40)):
            if len(out) >= k * 2:
                break
            _add(g.get("question") or "", "gap", weight=0.8,
                 gap_reason=g.get("reason"), urls=g.get("urls"))
    except Exception:
        pass

    # フォールバック: 直近の非脆い reflex / 直近記憶
    if not out and reflex is not None and reflex.index:
        for n in reversed(reflex.index[-5:]):
            _add(n.get("question") or "", "recent_reflex", weight=0.5)
            if len(out) >= k:
                break

    out.sort(key=lambda s: (-s.weight, s.reason))
    return out[:k]


def _dangling_from_memory(memory, limit: int = 3) -> List[DreamSeed]:
    """概念はあるが辺が薄い / 単独のノードを問い化する。"""
    seeds: List[DreamSeed] = []
    index = list(getattr(memory, "index", None) or [])
    if not index:
        return seeds
    # 出現回数の少ない概念 = 未接続っぽい
    concept_hits: Dict[str, int] = {}
    concept_src: Dict[str, str] = {}
    for rec in index[-80:]:
        graph = rec.get("graph") or {}
        concepts = list(graph.get("concepts") or rec.get("l2_concepts") or [])
        edges = list(graph.get("edges") or rec.get("edges") or [])
        n_edge = len(edges)
        for c in concepts[:6]:
            c = (c or "").strip()
            if len(c) < 2 or c.startswith("http"):
                continue
            concept_hits[c] = concept_hits.get(c, 0) + 1
            if c not in concept_src or n_edge < 2:
                concept_src[c] = (rec.get("l3_text") or c)[:120]
    # 出現1回かつ短い概念を dangling 扱い
    dangling = [
        (c, n) for c, n in concept_hits.items()
        if n <= 1 and 2 <= len(c) <= 40 and not c.isdigit()
    ]
    dangling.sort(key=lambda x: (x[1], len(x[0])))
    for c, _n in dangling[:limit]:
        ctx = concept_src.get(c, c)
        q = f"What is the relation of '{c}' in: {ctx}?"
        seeds.append(DreamSeed(
            question=q[:240], reason="dangling", weight=1.0,
            meta={"concept": c}))
    return seeds


# ── 予測パズル ────────────────────────────────────────────────────────────

def predict_questions(
    seed: DreamSeed,
    puzzle=None,
    *,
    k: int = 3,
    council=None,
) -> List[str]:
    """次に聞かれそうな問いを合成。puzzle があれば軸 dist を使う。"""
    base = seed.question
    preds: List[str] = []

    # ルールベース近傍 (常に用意)
    preds.extend(_rule_predict(base, seed))

    if puzzle is not None:
        try:
            prec = puzzle.ask(
                base, depth=1, gate=0.22, use_divergence=False, speak=False)
            dist = list(prec.get("consensus_dist") or [])[:8]
            props = list(prec.get("propositions") or [])
            joined = ",".join(prec.get("joined_axes") or [])[:80]
            tops = [t for t, _ in dist if t and str(t).strip()][:4]
            if tops:
                preds.append(
                    f"Given '{base[:80]}', which is more likely: "
                    + " or ".join(tops[:3]) + "?")
            for t in tops[:2]:
                preds.append(f"What connects '{t}' to the question: {base[:60]}?")
            if joined:
                preds.append(
                    f"Along axes [{joined}], refine: {base[:100]}")
            for p in props[:1]:
                if len(p) > 20:
                    preds.append(f"Is this true: {p[:160]}?")
        except Exception:
            pass

    # 正規化・重複除去
    out, seen = [], set()
    for q in preds:
        q = re.sub(r"\s+", " ", (q or "").strip())
        if len(q) < 8:
            continue
        key = q.lower()[:100]
        if key in seen or key == base.lower()[:100]:
            continue
        seen.add(key)
        out.append(q[:240])
        if len(out) >= k:
            break
    if not out:
        out = [f"Follow-up: {base[:200]}"]
    return out[:k]


def _rule_predict(base: str, seed: DreamSeed) -> List[str]:
    q = base.rstrip("?")
    out = [
        f"Why might the answer to '{q[:80]}' be wrong?",
        f"What related fact should be checked before answering: {q[:80]}?",
    ]
    concept = (seed.meta or {}).get("concept")
    if concept:
        out.insert(0, f"Define '{concept}' and give one grounded example.")
        out.append(f"What contradicts a common claim about '{concept}'?")
    # who/what/when 系の言い換え
    low = base.lower()
    if low.startswith("what ") or "what is" in low:
        out.append(f"When and where does this apply: {q[:100]}?")
    if seed.reason == "fragile":
        out.append(f"Re-solve carefully with grounds: {q[:120]}?")
    return out


# ── 機械的矛盾 ────────────────────────────────────────────────────────────

def make_rivals(question: str, *, max_rivals: int = 2) -> List[str]:
    """知識不要の rival / 否定・対案。LLM なし。"""
    q = (question or "").strip()
    if not q:
        return []
    rivals: List[str] = []
    # 否定形
    rivals.append(f"NEGATION: It is not the case that ({q.rstrip('?')}).")
    # エンティティっぽい固有表現を置換
    ents = re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+)?)\b", q)
    if ents:
        e0 = ents[0]
        rivals.append(
            f"RIVAL: Replace '{e0}' with an incompatible alternative "
            f"in: {q[:120]}")
    else:
        # 数字があれば別の桁を rival に
        nums = re.findall(r"\b\d+(?:\.\d+)?\b", q)
        if nums:
            rivals.append(
                f"RIVAL: The numeric answer differs from {nums[0]} "
                f"for: {q[:120]}")
        else:
            rivals.append(
                f"RIVAL: The opposite relation holds for: {q[:140]}")
    # 関係反転テンプレ
    if any(w in q.lower() for w in ("before", "after", "cause", "because", "if ")):
        rivals.append(
            f"REVERSE: Temporal/causal order is inverted in: {q[:120]}")
    # 重複除去
    out, seen = [], set()
    for r in rivals:
        key = r.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(r[:220])
        if len(out) >= max_rivals:
            break
    return out[:max_rivals]


# ── 解消 + 永遠記憶 ──────────────────────────────────────────────────────

def _remember_dream(
    memory,
    *,
    question: str,
    kind: str,
    concepts: Sequence[str] = (),
    propositions: Sequence[str] = (),
    grounds: Sequence[str] = (),
    candidates: Sequence[Tuple[str, float]] = (),
    edges: Sequence[Dict[str, Any]] = (),
    meta: Optional[Dict[str, Any]] = None,
) -> bool:
    if memory is None or not getattr(memory, "enabled", False):
        return False
    try:
        from memory_graph import MemoryGraph
        props = list(propositions or [])
        props.insert(0, f"Dream Q: {question[:160]}")
        mg = MemoryGraph(
            concepts=list(concepts or [])[:10],
            propositions=props[:8],
            candidates=list(candidates or [])[:12],
            grounds=list(grounds or [])[:10],
            edges=list(edges or [])[:24],
            l3_text=f"[dream] {question[:200]}",
            kind=kind,
            confidence=0.55,
            meta=dict(meta or {}),
        )
        memory.add_graph(mg, vector=None, quiet=True)
        return True
    except Exception:
        return False


def resolve_dream(
    council,
    question: str,
    rivals: Sequence[str],
    *,
    budget: Optional[DreamBudget] = None,
    seed_reason: str = "",
    search_left: Optional[List[int]] = None,
    remember_left: Optional[List[int]] = None,
    audit_left: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """memory Hand → 不足なら critic search → structure remember → graph audit。"""
    budget = budget or DreamBudget()
    search_left = search_left if search_left is not None else [budget.search]
    remember_left = remember_left if remember_left is not None else [budget.remember]
    audit_left = audit_left if audit_left is not None else [budget.audit]
    log: Dict[str, Any] = {
        "question": question[:200],
        "rivals": list(rivals)[:4],
        "seed_reason": seed_reason,
        "resolved": False,
        "remembered": 0,
        "path": [],
        "audit": None,
    }
    mem = getattr(council, "memory", None)
    concepts: List[str] = []
    props: List[str] = [f"Rival: {r}" for r in rivals[:2]]
    grounds: List[str] = [f"dream:rival:{i}" for i in range(len(rivals))]
    candidates: List[Tuple[str, float]] = []
    urls: List[str] = []

    # 予測問い自体を先に刻む (予算内)
    if remember_left[0] > 0:
        if _remember_dream(
            mem, question=question, kind="dream_predict",
            concepts=["dream", seed_reason or "seed"],
            propositions=props,
            grounds=grounds,
            meta={"seed_reason": seed_reason, "rivals": list(rivals)[:2],
                  "phase": "predict"},
        ):
            remember_left[0] -= 1
            log["remembered"] += 1
            log["path"].append("dream_predict")

    # integrator: memory search
    try:
        from role_hands import RoleHand, ToolBudget
        hands = RoleHand(council=council, log=getattr(council, "log", None))
        tb = ToolBudget(search=0, calc=0, memory=1, reason="dream")
        delta, hmeta = hands.run(
            "integrator", question, budget=tb, lane_name="factual")
        if delta is not None:
            log["path"].append("memory_hit")
            for c in (delta.concepts or [])[:6]:
                if c not in concepts:
                    concepts.append(c)
            for p in (delta.propositions or [])[:4]:
                props.append(p)
            for g in (delta.pattern_hits or [])[:4]:
                grounds.append(str(g))
            for g in ((delta.meta or {}).get("grounds") or [])[:4]:
                grounds.append(str(g))
            for s, w in (delta.dist or [])[:6]:
                candidates.append((s, float(w)))
            log["resolved"] = True
        else:
            log["path"].append(f"memory_miss:{(hmeta or {}).get('skipped')}")
    except Exception as e:
        log["path"].append(f"memory_err:{e}"[:80])

    # critic search (予算残あり & 未解消)
    if not log["resolved"] and search_left[0] > 0:
        try:
            from role_hands import RoleHand, ToolBudget
            hands = RoleHand(council=council, log=getattr(council, "log", None))
            tb = ToolBudget(search=1, calc=0, memory=0, reason="dream")
            delta, hmeta = hands.run(
                "critic", question, budget=tb, lane_name="factual")
            search_left[0] -= 1
            log["path"].append("critic_search")
            if delta is not None:
                log["resolved"] = True
                for c in (delta.concepts or [])[:6]:
                    if c not in concepts:
                        concepts.append(c)
                for p in (delta.propositions or [])[:4]:
                    props.append(p)
                for g in ((delta.meta or {}).get("grounds") or [])[:6]:
                    grounds.append(str(g))
                    if str(g).startswith("web:"):
                        urls.append(str(g)[4:])
                for s, w in (delta.dist or [])[:6]:
                    candidates.append((s, float(w)))
                if (hmeta or {}).get("links"):
                    for _t, u in (hmeta.get("links") or [])[:3]:
                        if u not in urls:
                            urls.append(u)
            else:
                log["path"].append(f"search_miss:{(hmeta or {}).get('skipped') or (hmeta or {}).get('error')}")
        except Exception as e:
            search_left[0] = max(0, search_left[0] - 1)
            log["path"].append(f"search_err:{e}"[:80])

    # 矛盾を辺として残す (解消結果の有無に関わらず構造を刻む)
    edges = []
    for i, r in enumerate(rivals[:2]):
        edges.append({
            "from": question[:80], "to": r[:80],
            "rel": "rival", "weight": 0.7,
        })
    if concepts:
        for c in concepts[:3]:
            edges.append({
                "from": question[:80], "to": c,
                "rel": "grounds_concept", "weight": 0.9,
            })

    if remember_left[0] > 0 and (log["resolved"] or concepts or candidates):
        if _remember_dream(
            mem, question=question, kind="dream_resolved",
            concepts=concepts or ["dream"],
            propositions=props,
            grounds=grounds + [f"dream:{seed_reason or 'seed'}"],
            candidates=candidates,
            edges=edges,
            meta={
                "seed_reason": seed_reason,
                "rivals": list(rivals)[:2],
                "urls": urls[:5],
                "phase": "resolved",
                "resolved": bool(log["resolved"]),
            },
        ):
            remember_left[0] -= 1
            log["remembered"] += 1
            log["path"].append("dream_resolved")
    elif remember_left[0] > 0 and not log["resolved"]:
        # 未解消でも rival 構造だけ刻む (次サイクルの燃料)
        if _remember_dream(
            mem, question=question, kind="dream_resolved",
            concepts=["unresolved", "dream"],
            propositions=props + ["Unresolved rivalry — needs more grounds."],
            grounds=grounds,
            edges=edges,
            meta={
                "seed_reason": seed_reason,
                "rivals": list(rivals)[:2],
                "phase": "unresolved",
                "resolved": False,
            },
        ):
            remember_left[0] -= 1
            log["remembered"] += 1
            log["path"].append("dream_unresolved_stamp")

    # スケール基盤: ローカル大型がグラフを監査し正しそうさへパッチ
    if audit_left[0] > 0:
        try:
            from memory_graph import MemoryGraph
            from graph_auditor import audit_and_correct
            base = MemoryGraph(
                concepts=concepts or ["dream"],
                propositions=props[:8],
                candidates=candidates[:8],
                grounds=grounds[:10],
                edges=edges[:24],
                l3_text=f"[dream] {question[:200]}",
                kind="dream_resolved",
                confidence=0.55,
                meta={"seed_reason": seed_reason, "rivals": list(rivals)[:2]},
            )
            arep = audit_and_correct(
                council, question, base,
                rivals=rivals, kind="dream_audited", allow_frontier=True)
            audit_left[0] -= 1
            log["audit"] = {
                "ok": arep.get("ok"),
                "skipped": arep.get("skipped"),
                "truth_status": arep.get("truth_status"),
                "reason": arep.get("reason"),
                "verdict": (arep.get("final") or {}).get("verdict"),
            }
            if arep.get("ok"):
                log["remembered"] += 1
                log["path"].append("dream_audited")
            elif arep.get("skipped"):
                log["path"].append("audit_skip")
            else:
                log["path"].append("audit_done")
        except Exception as e:
            log["audit"] = {"ok": False, "error": str(e)[:120]}
            log["path"].append("audit_err")

    log["urls"] = urls[:5]
    log["n_concepts"] = len(concepts)
    return log


# ── サイクル ──────────────────────────────────────────────────────────────

def run_cycle(
    council,
    n: int = 1,
    *,
    budget: Optional[DreamBudget] = None,
    use_puzzle: bool = True,
) -> Dict[str, Any]:
    """最大 n 個の Seed について予測→矛盾→解消を1周。"""
    budget = budget or DreamBudget()
    t0 = time.time()
    report: Dict[str, Any] = {
        "cycles": 0,
        "seeds": [],
        "items": [],
        "budget": budget.as_dict(),
        "search_left": budget.search,
        "remember_left": budget.remember,
        "audit_left": budget.audit,
        "ok": True,
    }
    mem = getattr(council, "memory", None)
    if mem is None or not getattr(mem, "enabled", False):
        report["ok"] = False
        report["error"] = "memory_disabled"
        return report

    # スケール役割を推定バインド (監査役の有無を status に残す)
    try:
        from scale_substrate import bind_scale_roles, ensure_auditor
        bind_scale_roles(council)
        ensure_auditor(council, prefer_bridge=True)
    except Exception:
        pass

    seeds = pick_seeds(council, k=max(1, int(n)))
    if not seeds:
        report["ok"] = False
        report["error"] = "no_seeds"
        return report
    report["seeds"] = [
        {"q": s.question[:100], "reason": s.reason} for s in seeds
    ]

    puzzle = None
    if use_puzzle:
        try:
            puzzle = council._get_puzzle_worker(use_divergence=False)
        except Exception:
            puzzle = None

    search_left = [budget.search]
    remember_left = [budget.remember]
    audit_left = [budget.audit]

    for seed in seeds:
        preds = predict_questions(
            seed, puzzle, k=budget.predict, council=council)
        for pq in preds:
            if remember_left[0] <= 0 and search_left[0] <= 0 and audit_left[0] <= 0:
                break
            rivals = make_rivals(pq, max_rivals=budget.rivals_per_q)
            item = resolve_dream(
                council, pq, rivals,
                budget=budget,
                seed_reason=seed.reason,
                search_left=search_left,
                remember_left=remember_left,
                audit_left=audit_left,
            )
            item["parent_seed"] = seed.question[:100]
            report["items"].append(item)
        report["cycles"] += 1
        if remember_left[0] <= 0:
            break

    report["search_left"] = search_left[0]
    report["remember_left"] = remember_left[0]
    report["audit_left"] = audit_left[0]
    report["elapsed_s"] = round(time.time() - t0, 2)
    report["n_remembered"] = sum(
        int(i.get("remembered") or 0) for i in report["items"])
    return report


def run_dream(council, cycles: int = 1, **kwargs) -> Dict[str, Any]:
    """複数サイクル。各サイクルは独立に seed を取り直す。"""
    cycles = max(1, int(cycles))
    merged: Dict[str, Any] = {
        "cycles_run": 0,
        "reports": [],
        "n_remembered": 0,
        "ok": True,
    }
    t0 = time.time()
    for _ in range(cycles):
        r = run_cycle(council, n=1, **kwargs)
        merged["reports"].append(r)
        merged["cycles_run"] += 1
        merged["n_remembered"] += int(r.get("n_remembered") or 0)
        if not r.get("ok") and r.get("error") == "memory_disabled":
            merged["ok"] = False
            merged["error"] = "memory_disabled"
            break
        if r.get("error") == "no_seeds":
            # 2周目以降 seed が無くても致命ではない
            if merged["cycles_run"] == 1:
                merged["ok"] = False
                merged["error"] = "no_seeds"
            break
    merged["elapsed_s"] = round(time.time() - t0, 2)
    return merged


def dream_after_ask_enabled() -> bool:
    v = (os.environ.get("VERANTYX_DREAM_AFTER_ASK") or "").strip().lower()
    return v in ("1", "on", "true", "yes")


def maybe_dream_after_ask(council) -> Optional[Dict[str, Any]]:
    """ask 後の 1-cycle tick。失敗しても例外を外に出さない。"""
    if not dream_after_ask_enabled():
        return None
    try:
        mem = getattr(council, "memory", None)
        if mem is None or not getattr(mem, "enabled", False):
            return {"skipped": "memory_off"}
        return run_cycle(council, n=1, use_puzzle=True)
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
