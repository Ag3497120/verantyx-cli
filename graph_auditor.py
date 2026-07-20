"""graph_auditor.py — グラフ結論の監査・パッチ（正しそうさへ矯正）
==============================================================================

絶対真理ではなく、ローカル大型 → (不確実時) フロンティアが
MemoryGraph を見て「誤り / こう直す」を返し、永遠記憶へ追記する。

出力スキーマ (JSON):
  verdict: ok | incorrect | uncertain
  confidence: 0..1
  wrong: [str]
  patch: {add_propositions, retract_propositions, set_candidates, add_edges, note}
  escalate: bool

env:
  VERANTYX_FRONTIER_AUDITOR=ollama:model|lmstudio:model
  VERANTYX_AUDIT_AFTER_ASK=1  (council 側で使用)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


AUDIT_SYSTEM = """You are a graph auditor for an external memory system.
You do NOT claim absolute world truth. Judge ONLY from the provided graph.
If evidence is thin or rivals conflict, set verdict=uncertain and escalate=true.
Reply with JSON ONLY (no markdown fences), schema:
{
  "verdict": "ok"|"incorrect"|"uncertain",
  "confidence": 0.0-1.0,
  "wrong": ["proposition that seems wrong", ...],
  "patch": {
    "add_propositions": ["..."],
    "retract_propositions": ["..."],
    "set_candidates": [["token", 0.5], ...],
    "add_edges": [{"from":"a","to":"b","rel":"corrects","weight":0.8}],
    "note": "short reason"
  },
  "escalate": false
}"""


@dataclass
class AuditResult:
    verdict: str = "uncertain"  # ok | incorrect | uncertain
    confidence: float = 0.0
    wrong: List[str] = field(default_factory=list)
    patch: Dict[str, Any] = field(default_factory=dict)
    escalate: bool = False
    auditor: str = ""
    tier: str = "local"  # local | frontier | none
    raw: str = ""
    error: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "wrong": list(self.wrong),
            "patch": dict(self.patch or {}),
            "escalate": bool(self.escalate),
            "auditor": self.auditor,
            "tier": self.tier,
            "error": self.error,
        }

    @property
    def truth_status(self) -> str:
        if self.verdict == "ok" and self.confidence >= 0.55:
            return "audited"
        if self.verdict == "incorrect" and (self.patch or self.wrong):
            return "audited"
        if self.verdict == "uncertain" or self.escalate:
            return "contested"
        if self.tier == "none":
            return "unreviewed"
        return "plausible"


def graph_brief(graph, *, rivals: Sequence[str] = (), question: str = "") -> str:
    """監査用の短いテキスト。"""
    if graph is None:
        g: Dict[str, Any] = {}
    elif hasattr(graph, "to_dict"):
        g = graph.to_dict()
    elif isinstance(graph, dict):
        g = graph
    else:
        g = {}
    payload = {
        "question": (question or "")[:300],
        "concepts": list(g.get("concepts") or [])[:12],
        "propositions": list(g.get("propositions") or [])[:10],
        "candidates": list(g.get("candidates") or [])[:8],
        "grounds": list(g.get("grounds") or [])[:8],
        "edges": list(g.get("edges") or [])[:12],
        "rivals": list(rivals or [])[:4],
        "kind": g.get("kind"),
        "l3": (g.get("l3_text") or "")[:240],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_audit_json(text: str) -> AuditResult:
    """モデル出力から JSON を抜く。失敗時 uncertain。"""
    raw = (text or "").strip()
    out = AuditResult(raw=raw[:2000])
    if not raw:
        out.verdict = "uncertain"
        out.escalate = True
        out.error = "empty"
        return out
    # fence 除去
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    blob = raw
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        blob = m.group(0)
    try:
        d = json.loads(blob)
    except Exception as e:
        out.verdict = "uncertain"
        out.escalate = True
        out.error = f"parse:{e}"[:80]
        return out
    v = str(d.get("verdict") or "uncertain").lower().strip()
    if v not in ("ok", "incorrect", "uncertain"):
        v = "uncertain"
    out.verdict = v
    try:
        out.confidence = float(d.get("confidence") or 0.0)
    except Exception:
        out.confidence = 0.0
    out.wrong = [str(x)[:200] for x in (d.get("wrong") or [])][:8]
    patch = d.get("patch") if isinstance(d.get("patch"), dict) else {}
    out.patch = {
        "add_propositions": [str(x)[:200] for x in (patch.get("add_propositions") or [])][:8],
        "retract_propositions": [str(x)[:200] for x in (patch.get("retract_propositions") or [])][:8],
        "set_candidates": _norm_cands(patch.get("set_candidates") or []),
        "add_edges": list(patch.get("add_edges") or [])[:12],
        "note": str(patch.get("note") or "")[:240],
    }
    out.escalate = bool(d.get("escalate")) or (v == "uncertain")
    return out


def _norm_cands(items) -> List[List[Any]]:
    out = []
    for it in items or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            try:
                out.append([str(it[0])[:60], float(it[1])])
            except Exception:
                continue
        elif isinstance(it, str) and it.strip():
            out.append([it.strip()[:60], 0.5])
        if len(out) >= 8:
            break
    return out


def select_local_auditor(council) -> Tuple[Optional[Any], str]:
    """sage → bridge[0]。 (participant, name)"""
    if council is None:
        return None, ""
    sage = getattr(council, "_sage", None)
    if sage is not None:
        return sage, getattr(sage, "name", "sage")
    bridges = list(getattr(council, "_bridges", None) or [])
    if bridges:
        b = bridges[0]
        return b, getattr(b, "name", "bridge")
    # worker (9B jgen) があれば監査役に使える
    worker = getattr(council, "_worker", None)
    if worker is not None and hasattr(worker, "speak"):
        return worker, getattr(worker, "name", "worker")
    return None, ""


def frontier_spec() -> Optional[str]:
    s = (os.environ.get("VERANTYX_FRONTIER_AUDITOR") or "").strip()
    return s or None


def _call_auditor(participant, user_blob: str, *, max_tokens: int = 700) -> str:
    messages = [
        {"role": "system", "content": AUDIT_SYSTEM},
        {"role": "user", "content":
         "Audit this memory graph claim. JSON only.\n\n" + user_blob},
    ]
    if hasattr(participant, "complete"):
        return str(participant.complete(messages, max_tokens=max_tokens) or "")
    # speak フォールバック
    if hasattr(participant, "speak"):
        return str(participant.speak(
            "Audit JSON only:\n" + user_blob[:3500],
            concepts=["audit", "graph"], max_new=max_tokens) or "")
    raise RuntimeError("auditor has no complete/speak")


def audit_claim(
    auditor,
    question: str,
    graph,
    *,
    rivals: Sequence[str] = (),
    name: str = "",
    tier: str = "local",
) -> AuditResult:
    if auditor is None:
        r = AuditResult(verdict="uncertain", escalate=True, tier="none",
                        error="no_auditor")
        return r
    brief = graph_brief(graph, rivals=rivals, question=question)
    try:
        text = _call_auditor(auditor, brief)
        result = parse_audit_json(text)
    except Exception as e:
        result = AuditResult(
            verdict="uncertain", escalate=True, error=str(e)[:160])
    result.auditor = name or getattr(auditor, "name", tier)
    result.tier = tier
    return result


def apply_audit_patch(
    memory,
    base_graph,
    audit: AuditResult,
    *,
    question: str = "",
    kind: str = "dream_audited",
) -> Optional[Any]:
    """パッチを新ノードとして刻印。Soft 平均しない。"""
    if memory is None or not getattr(memory, "enabled", False):
        return None
    if audit.tier == "none" and not audit.patch:
        return None
    try:
        from memory_graph import MemoryGraph
        if hasattr(base_graph, "to_dict"):
            base = MemoryGraph.from_dict(base_graph.to_dict())
        elif isinstance(base_graph, dict):
            base = MemoryGraph.from_dict(base_graph)
        else:
            base = MemoryGraph(l3_text=question[:200], kind="episode")

        patch = audit.patch or {}
        props = list(base.propositions or [])
        for p in patch.get("add_propositions") or []:
            if p not in props:
                props.append(p)
        for p in patch.get("retract_propositions") or []:
            tag = f"RETRACT: {p}"
            if tag not in props:
                props.append(tag)
            # 原文が残っていれば印を付ける
            props = [x if x != p else f"(retracted) {x}" for x in props]
        for w in audit.wrong or []:
            tag = f"WRONG: {w}"
            if tag not in props:
                props.append(tag)
        props.insert(0, f"Audit({audit.tier}/{audit.verdict}): "
                     f"{(patch.get('note') or '')[:120]}")

        cands = list(base.candidates or [])
        sc = patch.get("set_candidates") or []
        if sc:
            cands = [(str(a), float(b)) for a, b in sc]

        grounds = list(base.grounds or [])
        grounds.append(f"audit:{audit.tier}:{audit.auditor}:{audit.verdict}")
        grounds.append(f"truth:{audit.truth_status}")

        edges = list(base.edges or [])
        for e in patch.get("add_edges") or []:
            if isinstance(e, dict):
                edges.append(e)
        edges.append({
            "from": (question or base.l3_text or "claim")[:80],
            "to": f"audit:{audit.verdict}",
            "rel": "audited_by",
            "weight": float(audit.confidence or 0.5),
        })

        concepts = list(base.concepts or [])
        if "audit" not in concepts:
            concepts.append("audit")
        if audit.truth_status not in concepts:
            concepts.append(audit.truth_status)

        mg = MemoryGraph(
            axes=dict(base.axes or {}),
            concepts=concepts[:12],
            propositions=props[:12],
            candidates=cands[:12],
            grounds=grounds[:14],
            edges=edges[:28],
            l3_text=f"[audited:{audit.verdict}] {(question or base.l3_text or '')[:180]}",
            kind=kind,
            confidence=max(0.35, float(audit.confidence or 0.5)),
            meta={
                "truth_status": audit.truth_status,
                "auditor": audit.as_dict(),
                "parent_kind": base.kind,
            },
        )
        memory.add_graph(mg, vector=None, quiet=True)
        return mg
    except Exception:
        return None


def audit_and_correct(
    council,
    question: str,
    graph,
    *,
    rivals: Sequence[str] = (),
    kind: str = "dream_audited",
    allow_frontier: bool = True,
) -> Dict[str, Any]:
    """local → 必要なら frontier → patch 刻印。"""
    report: Dict[str, Any] = {"ok": False, "skipped": False}
    mem = getattr(council, "memory", None) if council is not None else None
    auditor, name = select_local_auditor(council)
    if auditor is None:
        report["skipped"] = True
        report["reason"] = "no_local_auditor"
        # 未監査でも contested 印を薄く残せるよう graph に meta だけ欲しい場合は呼び出し側
        return report

    local = audit_claim(
        auditor, question, graph, rivals=rivals, name=name, tier="local")
    report["local"] = local.as_dict()
    final = local

    need_front = allow_frontier and (
        local.escalate or local.verdict == "uncertain"
        or (local.verdict == "incorrect" and local.confidence < 0.45)
    )
    if need_front:
        spec = frontier_spec()
        if spec:
            try:
                from verantyx_bridges import make_participant
                front = make_participant(spec)
                fr = audit_claim(
                    front, question, graph, rivals=rivals,
                    name=getattr(front, "name", spec), tier="frontier")
                report["frontier"] = fr.as_dict()
                # frontier を優先（絶対真理ではなくより強い正しそうさ）
                final = fr
            except Exception as e:
                report["frontier_error"] = str(e)[:160]
                # frontier 失敗 → contested のまま local 結果でパッチ
        else:
            report["frontier"] = {"skipped": "VERANTYX_FRONTIER_AUDITOR unset"}

    mg = apply_audit_patch(
        mem, graph, final, question=question, kind=kind)
    report["ok"] = mg is not None
    report["final"] = final.as_dict()
    report["truth_status"] = final.truth_status
    report["kind"] = kind
    return report


def audit_after_ask_enabled() -> bool:
    v = (os.environ.get("VERANTYX_AUDIT_AFTER_ASK") or "").strip().lower()
    return v in ("1", "on", "true", "yes")
