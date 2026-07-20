"""cross_obsidian.py — 立体十字ノード結論 × Obsidian × 永遠記憶
==============================================================================

宇宙 = 同型十字の無限接続、という見立ての実装側:

  CrossNode 結論 ──書込──► Obsidian (人間の L3 正本)
                 ──刻印──► CortexMemory / MemoryGraph (永遠記憶)
  Obsidian/過去十字 ──読込──► 次の CrossNode の grounds (深み)

双方向:
  export_cross_conclusion  … ノード結論を vault ノート + 記憶へ
  ground_cross_from_memory … 記憶/Obsidian 由来グラフでノードを接地
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from obsidian_ingest import resolve_vault


CROSS_NOTE_DIR = "Verantyx/Cross"


def _safe_name(s: str, n: int = 48) -> str:
    t = "".join(c if c.isalnum() or c in "-_" else "_" for c in (s or ""))
    return (t[:n] or "node").strip("_")


def format_cross_note(
    cross,
    *,
    question: str,
    answer: str = "",
    concepts: Optional[Sequence[str]] = None,
) -> str:
    """十字ノード結論の Markdown (Obsidian 向け)。"""
    dist = getattr(cross, "dist", None) or []
    tops = ", ".join(
        f"{(s or '').strip()} ({w * 100:.0f}%)" for s, w in dist[:8] if (s or "").strip()
    )
    props = getattr(cross, "propositions", None) or []
    concepts = list(concepts or getattr(cross, "concepts", None) or [])
    children = getattr(cross, "children", None) or []
    edges = getattr(cross, "edges", None) or []
    meta = getattr(cross, "meta", None) or {}
    lines = [
        "---",
        f'tags: [verantyx, matryoshka-cross, scale-{getattr(cross, "scale", 0)}]',
        f'cross_id: "{getattr(cross, "id", "")}"',
        f'scale: {int(getattr(cross, "scale", 0) or 0)}',
        f'source: "{getattr(cross, "source", "cross")}"',
        f'confidence: {float(getattr(cross, "confidence", 0.5) or 0.5):.4f}',
        f'created: {datetime.now().isoformat(timespec="seconds")}',
        "---",
        "",
        f"# Cross `{getattr(cross, 'id', '')}`",
        "",
        "## Question",
        question.strip() or "(none)",
        "",
        "## Conclusion",
        (answer or "").strip() or "(deliberate-only)",
        "",
        "## Candidates",
        tops or "(empty)",
        "",
        "## Concepts",
        ", ".join(concepts[:12]) if concepts else "(none)",
        "",
        "## Propositions",
    ]
    if props:
        for p in props[:8]:
            lines.append(f"- {p}")
    else:
        lines.append("- (none)")
    lines += [
        "",
        "## Structure",
        f"- scale: {getattr(cross, 'scale', 0)}",
        f"- children: {len(children)}",
        f"- edges: {len(edges)}",
        f"- op: {meta.get('op', '')}",
        "",
        "## Children",
    ]
    if children:
        for ch in children:
            cid = getattr(ch, "id", "?")
            src = getattr(ch, "source", "")
            top = ""
            d = getattr(ch, "dist", None) or []
            if d:
                top = (d[0][0] or "").strip()
            lines.append(f"- [[{CROSS_NOTE_DIR}/{_safe_name(cid)}|{cid}]] ({src}) top={top}")
    else:
        lines.append("- (leaf)")
    lines += ["", "## Edges"]
    if edges:
        for e in edges[:16]:
            lines.append(
                f"- {e.get('from')} --{e.get('rel')}--> {e.get('to')} "
                f"(w={e.get('weight', '')})"
            )
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def write_obsidian_note(
    markdown: str,
    *,
    vault: Optional[str] = None,
    cross_id: str = "node",
    dry_run: bool = False,
) -> Optional[str]:
    """vault にノートを書き、相対パスを返す。vault 無しなら None。"""
    root = resolve_vault(vault or "auto")
    if not root:
        return None
    day = datetime.now().strftime("%Y-%m-%d")
    rel_dir = os.path.join(CROSS_NOTE_DIR, day)
    abs_dir = os.path.join(root, rel_dir)
    fname = f"{_safe_name(cross_id)}.md"
    rel = os.path.join(rel_dir, fname).replace("\\", "/")
    abs_path = os.path.join(abs_dir, fname)
    if dry_run:
        return rel
    os.makedirs(abs_dir, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return rel


def remember_cross_conclusion(
    memory,
    cross,
    *,
    question: str,
    answer: str = "",
    vector=None,
    vault_rel: Optional[str] = None,
    quiet: bool = True,
) -> Optional[Dict[str, Any]]:
    """結論を MemoryGraph として永遠記憶へ刻印。"""
    if memory is None or not getattr(memory, "enabled", False):
        return None
    try:
        mg = cross.to_memory_graph(
            l3_text=f"Q: {question[:160]}  →  A: {(answer or '')[:200]}",
            kind="cross_conclusion",
        )
        if vault_rel:
            if vault_rel not in (mg.grounds or []):
                mg.grounds = list(mg.grounds or []) + [vault_rel]
            mg.meta = dict(mg.meta or {})
            mg.meta["obsidian"] = vault_rel
        if answer and answer.strip():
            props = list(mg.propositions or [])
            props.insert(0, f"Final: {answer.strip()[:240]}")
            mg.propositions = props[:8]
        memory.add_graph(mg, vector=vector, quiet=quiet)
        return {
            "cross_id": getattr(cross, "id", None),
            "obsidian": vault_rel,
            "kind": "cross_conclusion",
            "ts": time.time(),
        }
    except Exception as e:
        return {"error": str(e)[:160]}


def export_cross_conclusion(
    memory,
    cross,
    *,
    question: str,
    answer: str = "",
    vector=None,
    vault: Optional[str] = "auto",
    write_vault: bool = True,
    quiet: bool = True,
) -> Dict[str, Any]:
    """Obsidian ノート化 + 永遠記憶刻印を一括。"""
    md = format_cross_note(
        cross, question=question, answer=answer,
        concepts=getattr(cross, "concepts", None),
    )
    rel = None
    if write_vault:
        rel = write_obsidian_note(
            md, vault=vault, cross_id=getattr(cross, "id", "node"))
    mem = remember_cross_conclusion(
        memory, cross, question=question, answer=answer,
        vector=vector, vault_rel=rel, quiet=quiet,
    )
    return {
        "obsidian_rel": rel,
        "memory": mem,
        "note_chars": len(md),
    }


def ground_cross_from_memory(
    memory,
    cross,
    *,
    k: int = 4,
    min_score: float = 0.06,
) -> Any:
    """永遠記憶 (Obsidian 由来含む) で十字ノードを接地し、grounds/concepts を厚くする。"""
    if memory is None or not getattr(memory, "enabled", False) or cross is None:
        return cross
    try:
        q = cross.to_memory_graph(kind="cross_query")
        hits = memory.search_graph(q, k=k, min_score=min_score)
    except Exception:
        return cross
    if not hits:
        return cross
    grounds: List[str] = []
    concepts = list(cross.concepts or [])
    props = list(cross.propositions or [])
    for g, scores, rec in hits:
        flash = g.flash_summary() if hasattr(g, "flash_summary") else (g.l3_text or "")
        if flash:
            grounds.append(flash[:200])
        for c in (g.concepts or [])[:4]:
            if c not in concepts:
                concepts.append(c)
        for p in (g.propositions or [])[:2]:
            if p not in props:
                props.append(p)
        # Obsidian パスを grounds に残す
        for path in (g.grounds or []):
            tag = f"obsidian:{path}"
            if tag not in grounds:
                grounds.append(tag)
        cross.meta.setdefault("memory_hits", []).append({
            "id": rec.get("id"),
            "score": round(float(scores.get("score", 0)), 3),
            "kind": rec.get("kind"),
        })
    cross.concepts = concepts[:10]
    cross.propositions = props[:8]
    # AbstractCanvas 互換ではないが meta に保持 (to_canvas で pattern に載せられる)
    cross.meta["grounds"] = grounds[:8]
    # confidence を接地でわずかに上げる
    cross.confidence = float(min(1.0, cross.confidence + 0.03 * min(len(hits), 3)))
    return cross
