"""web_structure.py — ウェブ本文 → 中間グラフ + 不足知識キュー
==============================================================================

生 HTML 丸投げではなく、markdown / 簡易 HTML から構造を抜いて
MemoryGraph として永遠記憶へ刻む。

不足知識キュー:
  検索空・記憶ミス・構造化失敗時に question を積み、
  drain_knowledge_gaps() で後から ingest できる。
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

_QUEUE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".verantyx_chrono", "knowledge_gaps.jsonl",
)


def structure_from_markdown(
    md: str,
    *,
    url: str = "",
    title: str = "",
) -> Dict[str, Any]:
    """markdown から見出し・リンク・リスト・表っぽい行を構造化。"""
    text = md or ""
    concepts: List[str] = []
    propositions: List[str] = []
    grounds: List[str] = []
    edges: List[Dict[str, Any]] = []
    tables: List[List[str]] = []

    if url:
        grounds.append(f"web:{url}")
    if title:
        concepts.append(title[:80])
        propositions.append(f"Page: {title[:160]}")

    # 見出し
    for m in re.finditer(r"^(#{1,3})\s+(.+)$", text, re.M):
        level, heading = len(m.group(1)), m.group(2).strip()[:120]
        if heading and heading not in concepts:
            concepts.append(heading)
        propositions.append(f"H{level}: {heading}")
        if url:
            edges.append({
                "from": url, "to": heading, "rel": "has_heading", "weight": 1.0,
            })

    # リンク
    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", text):
        lab, href = m.group(1).strip()[:80], m.group(2).strip()
        grounds.append(f"web:{href}")
        if lab and lab not in concepts:
            concepts.append(lab)
        edges.append({"from": url or "page", "to": href, "rel": "links", "weight": 0.8})

    # 箇条書き
    for m in re.finditer(r"^\s*[-*]\s+(.+)$", text, re.M):
        item = m.group(1).strip()[:200]
        if len(item) >= 8:
            propositions.append(item)

    # パイプ表
    for block in re.finditer(r"((?:^\|.+\|\s*$\n?){2,})", text, re.M):
        rows = []
        for line in block.group(1).strip().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and not all(re.match(r"^[-:]+$", c or "") for c in cells):
                rows.append(cells)
        if rows:
            tables.append(rows[:12])
            # 表の先頭セルを概念に
            for cell in rows[0][:4]:
                if cell and cell not in concepts:
                    concepts.append(cell[:40])

    # JSON-LD っぽい断片 (markdown に残っている場合)
    for m in re.finditer(
            r'"(@type|name|capital|foundingDate)"\s*:\s*"([^"]+)"', text):
        key, val = m.group(1), m.group(2)
        concepts.append(val[:40])
        propositions.append(f"{key}: {val}")

    # 本文から短い命題
    for para in re.split(r"\n\s*\n", text)[:8]:
        p = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", para)
        p = re.sub(r"[#*_`]", "", p).strip()
        if 40 <= len(p) <= 220:
            propositions.append(p[:220])
        if len(propositions) >= 10:
            break

    concepts = list(dict.fromkeys([c for c in concepts if c]))[:12]
    propositions = list(dict.fromkeys(propositions))[:10]
    grounds = list(dict.fromkeys(grounds))[:12]

    return {
        "url": url,
        "title": title,
        "concepts": concepts,
        "propositions": propositions,
        "grounds": grounds,
        "edges": edges[:24],
        "tables": tables[:4],
        "l3_text": (title or url or "web") + " :: " + " | ".join(propositions[:2]),
        "kind": "web_structured",
    }


def structure_from_html(html: str, *, url: str = "", title: str = "") -> Dict[str, Any]:
    """簡易 HTML → 構造。依存追加なしの正規表現抽出。"""
    raw = html or ""
    # title
    tm = re.search(r"<title[^>]*>([^<]+)</title>", raw, re.I)
    if tm and not title:
        title = re.sub(r"\s+", " ", tm.group(1)).strip()[:120]
    # JSON-LD
    props = []
    concepts = []
    for m in re.finditer(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            raw, re.I | re.S):
        blob = m.group(1)
        for km in re.finditer(r'"(name|headline|capital|description)"\s*:\s*"([^"]{2,80})"', blob):
            concepts.append(km.group(2)[:40])
            props.append(f"{km.group(1)}: {km.group(2)[:120]}")
    # headings
    for m in re.finditer(r"<h([1-3])[^>]*>(.*?)</h\1>", raw, re.I | re.S):
        h = re.sub(r"<[^>]+>", "", m.group(2))
        h = re.sub(r"\s+", " ", h).strip()[:120]
        if h:
            concepts.append(h)
            props.append(f"H{m.group(1)}: {h}")
    # strip tags → markdown-ish for shared path
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)<h([1-3])[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    base = structure_from_markdown(text, url=url, title=title)
    for c in concepts:
        if c not in base["concepts"]:
            base["concepts"].append(c)
    for p in props:
        if p not in base["propositions"]:
            base["propositions"].append(p)
    base["concepts"] = base["concepts"][:12]
    base["propositions"] = base["propositions"][:10]
    base["meta_html"] = True
    return base


def to_memory_graph(structured: Dict[str, Any]):
    from memory_graph import MemoryGraph
    cands = []
    for c in (structured.get("concepts") or [])[:6]:
        cands.append((c, 1.0))
    if cands:
        s = sum(w for _, w in cands) or 1.0
        cands = [(t, w / s) for t, w in cands]
    return MemoryGraph(
        concepts=list(structured.get("concepts") or [])[:10],
        propositions=list(structured.get("propositions") or [])[:8],
        candidates=cands,
        grounds=list(structured.get("grounds") or [])[:10],
        edges=list(structured.get("edges") or [])[:24],
        l3_text=(structured.get("l3_text") or "")[:400],
        kind=structured.get("kind") or "web_structured",
        confidence=0.55,
        meta={
            "url": structured.get("url"),
            "title": structured.get("title"),
            "n_tables": len(structured.get("tables") or []),
        },
    )


def remember_structured(memory, structured: Dict[str, Any], *, question: str = "") -> bool:
    if memory is None or not getattr(memory, "enabled", False) or not structured:
        return False
    try:
        mg = to_memory_graph(structured)
        if question:
            props = list(mg.propositions or [])
            props.insert(0, f"Q-context: {question[:120]}")
            mg.propositions = props[:8]
        memory.add_graph(mg, vector=None, quiet=True)
        return True
    except Exception:
        return False


def enqueue_knowledge_gap(
    question: str,
    *,
    reason: str = "",
    urls: Optional[Sequence[str]] = None,
) -> None:
    os.makedirs(os.path.dirname(_QUEUE_PATH), exist_ok=True)
    rec = {
        "ts": time.time(),
        "question": (question or "")[:300],
        "reason": (reason or "")[:120],
        "urls": list(urls or [])[:5],
    }
    try:
        with open(_QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_knowledge_gaps(limit: int = 50) -> List[Dict[str, Any]]:
    if not os.path.isfile(_QUEUE_PATH):
        return []
    out = []
    try:
        with open(_QUEUE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
    except Exception:
        return []
    return out[-limit:]


def drain_knowledge_gaps(
    memory=None,
    *,
    max_items: int = 3,
    fetch_fn=None,
) -> Dict[str, Any]:
    """キューを消化して構造化記憶へ。fetch_fn(url)->markdown。"""
    gaps = load_knowledge_gaps(limit=80)
    if not gaps:
        return {"drained": 0, "ok": 0}
    if fetch_fn is None:
        try:
            from verantyx_browser import fetch, search, extract_results
        except Exception:
            return {"drained": 0, "ok": 0, "error": "browser_unavailable"}

        def fetch_fn(url):
            return fetch(url)

    ok = 0
    used = 0
    for gap in reversed(gaps):
        if used >= max_items:
            break
        q = gap.get("question") or ""
        urls = list(gap.get("urls") or [])
        if not urls and q:
            try:
                from verantyx_browser import search
                raw = search(q, k=3)
                # parse - title / url lines
                title = None
                for ln in str(raw).splitlines():
                    s = ln.strip()
                    if s.startswith("http"):
                        if title:
                            urls.append(s)
                        title = None
                    elif s.startswith("- "):
                        title = s[2:]
            except Exception:
                pass
        if not urls:
            continue
        used += 1
        try:
            md = fetch_fn(urls[0])
            st = structure_from_markdown(md, url=urls[0], title=q[:80])
            if remember_structured(memory, st, question=q):
                ok += 1
        except Exception:
            continue
    return {"drained": used, "ok": ok, "queue_path": _QUEUE_PATH}


def fetch_structured(url: str, *, title: str = "") -> Dict[str, Any]:
    """1 URL を取得して構造化 dict を返す。"""
    from verantyx_browser import fetch
    md = fetch(url)
    return structure_from_markdown(md, url=url, title=title)
