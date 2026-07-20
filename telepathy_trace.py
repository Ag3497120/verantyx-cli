"""telepathy_trace.py — 異種モデル間の視線・思考履歴 (テレパシー経路)
==============================================================================

自然言語でも生ベクトルでもない中間グラフ上に、各エージェントが
「いまどの Obsidian / 根拠を見ているか」「どの候補質量で考えているか」を残す。

他モデルはその履歴を MemoryGraph 検索で読み、相手の内部状態を
ベクトルに近い解像度で推論できる (= 構造的テレパシー)。

経路:
  publish_gaze  … 自モデルの視線を kind=telepathy で永遠記憶へ
  recall_gazes  … 他モデルの視線を検索し、圧縮 brief を返す
  attach_telepathy_to_canvas … peer / speaker に載せる

認知アンカー (cognitive_anchors.telepathy_anchor) と対で使う。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


Dist = List[Tuple[str, float]]


@dataclass
class GazeTrace:
    """一回の視線・思考スナップショット (中間表現)。"""

    agent_id: str
    role: str = ""
    question: str = ""
    obsidian_paths: List[str] = field(default_factory=list)
    grounds: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    propositions: List[str] = field(default_factory=list)
    dist: Dist = field(default_factory=list)
    axis_sig: Optional[List[float]] = None
    confidence: float = 0.5
    source: str = "gaze"
    ts: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)

    def focus_paths(self) -> List[str]:
        """Obsidian 相対パスだけを正規化して返す。"""
        out: List[str] = []
        for p in list(self.obsidian_paths) + list(self.grounds):
            s = str(p or "").strip()
            if s.startswith("obsidian:"):
                s = s[len("obsidian:"):]
            if not s:
                continue
            # vault っぽい / Cross ノート
            if "/" in s or s.endswith(".md") or s.startswith("Verantyx/"):
                if s not in out:
                    out.append(s)
        return out[:8]

    def telepathy_brief(self, *, max_chars: int = 360) -> str:
        """他モデル向け: 相手の視線を一瞬で掴む圧縮文。"""
        paths = self.focus_paths()
        tops = ", ".join(
            f"{(s or '').strip()}({w * 100:.0f}%)"
            for s, w in (self.dist or [])[:4] if (s or "").strip()
        )
        lines = [
            f"[Telepathy gaze|{self.agent_id}"
            + (f"/{self.role}" if self.role else "")
            + "]",
            f"looking: {', '.join(paths[:4]) if paths else '(no obsidian focus)'}",
        ]
        if tops:
            lines.append(f"thinking_dist: {tops}")
        if self.concepts:
            lines.append("concepts: " + ",".join(self.concepts[:5]))
        if self.propositions:
            lines.append("claim: " + (self.propositions[0] or "")[:120])
        text = "\n".join(lines)
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text

    def to_memory_graph(self):
        from memory_graph import MemoryGraph

        grounds = list(self.grounds)
        for p in self.focus_paths():
            tag = p if p.startswith("obsidian:") else f"obsidian:{p}"
            if tag not in grounds:
                grounds.append(tag)
        props = list(self.propositions[:4])
        props.insert(0, self.telepathy_brief(max_chars=200))
        edges = [
            {"from": self.agent_id, "to": "obsidian_focus", "rel": "gazes",
             "weight": 1.0},
        ]
        for p in self.focus_paths()[:4]:
            edges.append({
                "from": self.agent_id, "to": p, "rel": "reads", "weight": 0.9,
            })
        return MemoryGraph.from_axis_sig(
            self.axis_sig,
            concepts=list(dict.fromkeys(
                ["telepathy", self.agent_id, self.role] + list(self.concepts)
            ))[:12],
            propositions=props[:8],
            candidates=self.dist[:12],
            grounds=grounds[:10],
            edges=edges,
            l3_text=self.telepathy_brief(max_chars=280),
            kind="telepathy",
            confidence=float(self.confidence),
            meta={
                "agent_id": self.agent_id,
                "role": self.role,
                "obsidian_paths": self.focus_paths(),
                "source": self.source,
                "ts": self.ts,
                **dict(self.meta or {}),
            },
        )


def gaze_from_canvas(
    canvas,
    *,
    agent_id: str,
    role: str = "",
    obsidian_extra: Optional[Sequence[str]] = None,
) -> GazeTrace:
    """AbstractCanvas / Cross 互換オブジェクトから視線を抽出。"""
    meta = dict(getattr(canvas, "meta", None) or {})
    grounds = list(meta.get("grounds") or [])
    # pattern_hits に obsidian: が混ざる場合も拾う
    for h in list(getattr(canvas, "pattern_hits", None) or []):
        if isinstance(h, str) and ("obsidian:" in h or h.endswith(".md")):
            grounds.append(h)
    paths = list(obsidian_extra or [])
    for g in grounds:
        s = str(g)
        if s.startswith("obsidian:"):
            paths.append(s[len("obsidian:"):])
        elif "/" in s and (s.endswith(".md") or s.startswith("Verantyx/")):
            paths.append(s)
    role = role or (meta.get("role") or "")
    return GazeTrace(
        agent_id=agent_id or getattr(canvas, "source", "agent") or "agent",
        role=str(role),
        question=str(getattr(canvas, "question", "") or "")[:160],
        obsidian_paths=list(dict.fromkeys(paths))[:8],
        grounds=[str(g)[:200] for g in grounds[:8]],
        concepts=list(getattr(canvas, "concepts", None) or [])[:8],
        propositions=list(getattr(canvas, "propositions", None) or [])[:6],
        dist=list(getattr(canvas, "dist", None) or [])[:12],
        axis_sig=(list(getattr(canvas, "axis_sig", None))
                  if getattr(canvas, "axis_sig", None) is not None else None),
        confidence=float(getattr(canvas, "confidence", 0.5) or 0.5),
        source=str(getattr(canvas, "source", "gaze") or "gaze"),
        meta={"from": "canvas"},
    )


def publish_gaze(
    memory,
    gaze: GazeTrace,
    *,
    vector=None,
    quiet: bool = True,
) -> Optional[Dict[str, Any]]:
    """視線履歴を永遠記憶へ刻む (異種モデルが後から読める)。"""
    if memory is None or not getattr(memory, "enabled", False) or gaze is None:
        return None
    try:
        mg = gaze.to_memory_graph()
        memory.add_graph(mg, vector=vector, quiet=quiet)
        return {
            "agent_id": gaze.agent_id,
            "role": gaze.role,
            "obsidian": gaze.focus_paths(),
            "kind": "telepathy",
            "ts": gaze.ts,
        }
    except Exception as e:
        return {"error": str(e)[:160]}


def publish_gaze_from_canvas(
    memory,
    canvas,
    *,
    agent_id: str,
    role: str = "",
    vector=None,
    quiet: bool = True,
) -> Optional[Dict[str, Any]]:
    gaze = gaze_from_canvas(canvas, agent_id=agent_id, role=role)
    return publish_gaze(memory, gaze, vector=vector, quiet=quiet)


def recall_gazes(
    memory,
    *,
    question: str = "",
    exclude_agent: str = "",
    k: int = 4,
    min_score: float = 0.05,
) -> List[Tuple[GazeTrace, Dict[str, float], Dict[str, Any]]]:
    """他エージェントのテレパシー履歴をグラフ検索で取得。"""
    if memory is None or not getattr(memory, "enabled", False):
        return []
    from memory_graph import MemoryGraph

    q = MemoryGraph(
        concepts=["telepathy"] + ([w for w in (question or "").split() if len(w) > 2][:4]),
        propositions=[f"Q: {(question or '')[:120]}"],
        l3_text=f"[telepathy recall] {(question or '')[:100]}",
        kind="telepathy_query",
        confidence=0.5,
    )
    try:
        hits = memory.search_graph(q, k=max(k * 2, 6), min_score=min_score)
    except Exception:
        hits = []
    out: List[Tuple[GazeTrace, Dict[str, float], Dict[str, Any]]] = []
    for g, scores, rec in hits:
        if (rec.get("kind") or g.kind) not in ("telepathy", "gaze"):
            # search_graph は kind 混在しうるので meta/agent で救済
            if (g.meta or {}).get("agent_id") is None and "telepathy" not in (
                    " ".join(g.concepts or [])).lower():
                continue
        agent = (g.meta or {}).get("agent_id") or "peer"
        if exclude_agent and agent == exclude_agent:
            continue
        paths = list((g.meta or {}).get("obsidian_paths") or [])
        for gr in (g.grounds or []):
            if str(gr).startswith("obsidian:") and str(gr)[9:] not in paths:
                paths.append(str(gr)[9:])
        gaze = GazeTrace(
            agent_id=str(agent),
            role=str((g.meta or {}).get("role") or ""),
            question=question,
            obsidian_paths=paths[:8],
            grounds=list(g.grounds or [])[:8],
            concepts=list(g.concepts or [])[:8],
            propositions=list(g.propositions or [])[:6],
            dist=list(g.candidates or [])[:12],
            axis_sig=g.axis_sig_list() if hasattr(g, "axis_sig_list") else None,
            confidence=float(g.confidence or 0.5),
            source="recalled",
            meta={"rec_id": rec.get("id"), "score": scores},
        )
        out.append((gaze, scores, rec))
        if len(out) >= k:
            break
    return out


def telepathy_peer_texts(
    memory,
    *,
    question: str = "",
    exclude_agent: str = "",
    k: int = 3,
) -> List[str]:
    """speaker / company の peer スロット用圧縮履歴。"""
    texts = []
    for gaze, scores, _rec in recall_gazes(
            memory, question=question, exclude_agent=exclude_agent, k=k):
        sc = float((scores or {}).get("score", 0))
        brief = gaze.telepathy_brief(max_chars=320)
        texts.append(f"{brief} (score={sc:.2f})")
    return texts


def attach_telepathy_to_canvas(
    canvas,
    memory=None,
    *,
    question: str = "",
    self_agent: str = "",
    publish_self: bool = True,
    k_recall: int = 3,
):
    """自視線を刻み、他モデル視線を canvas に載せる。"""
    if canvas is None:
        return canvas, []
    pubs = []
    if publish_self and memory is not None:
        role = (getattr(canvas, "meta", None) or {}).get("role") or ""
        agent = self_agent or getattr(canvas, "source", "agent") or "agent"
        pub = publish_gaze_from_canvas(
            memory, canvas, agent_id=str(agent), role=str(role), quiet=True)
        if pub:
            pubs.append(pub)
    peers = telepathy_peer_texts(
        memory, question=question or getattr(canvas, "question", ""),
        exclude_agent=self_agent or getattr(canvas, "source", ""),
        k=k_recall,
    )
    if peers:
        canvas.meta = dict(getattr(canvas, "meta", None) or {})
        canvas.meta["telepathy_peers"] = peers
        hits = list(getattr(canvas, "pattern_hits", None) or [])
        for p in peers:
            if p not in hits:
                hits.insert(0, p[:200])
        canvas.pattern_hits = hits[:8]
        # 視線パスを grounds メタへ
        paths = []
        for p in peers:
            if "looking:" in p:
                frag = p.split("looking:", 1)[-1].split("\n")[0].strip()
                for part in frag.split(","):
                    part = part.strip()
                    if part and part != "(no obsidian focus)":
                        paths.append(part)
        if paths:
            g0 = list((canvas.meta or {}).get("grounds") or [])
            for path in paths[:4]:
                tag = path if path.startswith("obsidian:") else f"obsidian:{path}"
                if tag not in g0:
                    g0.append(tag)
            canvas.meta["grounds"] = g0[:10]
    return canvas, pubs


def publish_role_gazes(
    memory,
    canvases: Sequence[Any],
    *,
    quiet: bool = True,
) -> List[Dict[str, Any]]:
    """会社役割それぞれの視線を一括刻印 (役割間テレパシー)。"""
    out = []
    for c in canvases or []:
        role = (getattr(c, "meta", None) or {}).get("role") or ""
        agent = f"company:{role}" if role else str(getattr(c, "source", "role"))
        pub = publish_gaze_from_canvas(
            memory, c, agent_id=agent, role=str(role), quiet=quiet)
        if pub:
            out.append(pub)
    return out
