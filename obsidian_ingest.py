"""obsidian_ingest.py — Obsidian vault → CortexMemory L3
==============================================================================

人間の L3 正本 (Markdown vault) を永遠の記憶へ刻印する。
原本は複製せず、チャンク抜粋 + パス + L1/L2 を Cortex に載せる。

使い方:
  python3 obsidian_ingest.py --vault auto [--limit 80] [--dry-run]
  python3 obsidian_ingest.py --vault "/path/to/vault" --limit 40

vault=auto のとき:
  ~/Library/Application Support/obsidian/obsidian.json の open:true
  または VERANTYX_OBSIDIAN_VAULT 環境変数。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time

from file_vault import CHUNK_CHARS, MAX_CHUNKS_PER_FILE, MAX_FILE_BYTES, _keywords

OBSIDIAN_APP_JSON = os.path.expanduser(
    "~/Library/Application Support/obsidian/obsidian.json")


def resolve_vault(path: str = "auto") -> str | None:
    if path and path != "auto":
        p = os.path.expanduser(path)
        return p if os.path.isdir(p) else None
    env = os.environ.get("VERANTYX_OBSIDIAN_VAULT")
    if env and os.path.isdir(os.path.expanduser(env)):
        return os.path.expanduser(env)
    if not os.path.isfile(OBSIDIAN_APP_JSON):
        return None
    try:
        cfg = json.load(open(OBSIDIAN_APP_JSON))
    except Exception:
        return None
    vaults = cfg.get("vaults") or {}
    # open:true を優先、無ければ先頭
    opened = None
    first = None
    for _id, meta in vaults.items():
        p = meta.get("path")
        if not p:
            continue
        if first is None:
            first = p
        if meta.get("open"):
            opened = p
            break
    chosen = opened or first
    if chosen and os.path.isdir(chosen):
        return chosen
    return None


def iter_notes(vault: str):
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames
                       if d not in {".obsidian", ".trash", ".git", "node_modules"}
                       and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            if fn.startswith("."):
                continue
            yield os.path.join(dirpath, fn)


def chunk_note(path: str):
    try:
        with open(path, "r", errors="ignore") as f:
            content = f.read(MAX_FILE_BYTES)
    except OSError:
        return []
    # frontmatter を軽く剥がす
    if content.startswith("---"):
        m = re.match(r"^---\n.*?\n---\n", content, flags=re.S)
        if m:
            content = content[m.end():]
    if not content.strip():
        return []
    chunks, buf, start_line, line_no = [], [], 1, 1
    size = 0
    for line in content.splitlines():
        buf.append(line)
        size += len(line) + 1
        line_no += 1
        if size >= CHUNK_CHARS:
            chunks.append((start_line, "\n".join(buf)))
            buf, size, start_line = [], 0, line_no
            if len(chunks) >= MAX_CHUNKS_PER_FILE:
                return chunks
    if buf:
        chunks.append((start_line, "\n".join(buf)))
    return chunks[:MAX_CHUNKS_PER_FILE]


def ingest(
    brain,
    tok,
    axes,
    memory,
    vault: str,
    *,
    limit: int = 80,
    dry_run: bool = False,
    quiet: bool = False,
):
    """vault 内メモを CortexMemory に kind=obsidian で刻印。"""
    from verantyx_mind import embed_text

    notes = list(iter_notes(vault))
    notes.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    written = 0
    scanned = 0
    for path in notes:
        if written >= limit:
            break
        rel = os.path.relpath(path, vault)
        chunks = chunk_note(path)
        scanned += 1
        for start_line, text in chunks:
            if written >= limit:
                break
            label = f"[Obsidian:{rel}:{start_line}] {text.strip()[:200]}"
            concepts = _keywords(text, k=8)
            if dry_run:
                if not quiet:
                    print(f"  dry-run would add: {label[:80]}")
                written += 1
                continue
            vec = embed_text(brain, tok, text[:1200])
            # 異種読み取り用に MemoryGraph も併記 (軸はルーター署名、概念はキーワード)
            graph = None
            try:
                from memory_graph import MemoryGraph
                sig = None
                if axes is not None and getattr(axes, "available", False):
                    sig = axes.signature(vec).tolist()
                graph = MemoryGraph.from_axis_sig(
                    sig, concepts=concepts, l3_text=label,
                    kind="obsidian", grounds=[rel],
                    meta={"vault": vault, "path": rel, "line": start_line},
                )
            except Exception:
                graph = None
            memory.add(
                vec, label, concepts=concepts, kind="obsidian", quiet=quiet,
                graph=graph,
                extra={"vault": vault, "path": rel, "line": start_line},
            )
            written += 1
    return {"vault": vault, "notes_scanned": scanned, "nodes_written": written,
            "dry_run": dry_run, "ts": time.time()}


def main():
    ap = argparse.ArgumentParser(description="Obsidian vault → CortexMemory")
    ap.add_argument("--vault", default="auto")
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    vault = resolve_vault(args.vault)
    if not vault:
        print("Obsidian vault not found. Set --vault or VERANTYX_OBSIDIAN_VAULT.")
        return 1
    print(f"vault: {vault}")
    if args.dry_run:
        # モデル不要
        class _Mem:
            enabled = True
            def add(self, *a, **k):
                pass
        stats = ingest(None, None, None, _Mem(), vault,
                       limit=args.limit, dry_run=True, quiet=args.quiet)
        print(stats)
        return 0

    from verantyx_mind import RustBrain, AxisAnchors, CortexMemory, DEFAULT_MODEL, TOKENIZER
    from transformers import AutoTokenizer
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verantyx.config.json")
    cfg = {}
    if os.path.isfile(cfg_path):
        try:
            cfg = json.load(open(cfg_path))
        except Exception:
            cfg = {}
    models = cfg.get("models") or {}
    model = models.get("router") or DEFAULT_MODEL
    tok_name = models.get("router_tokenizer") or TOKENIZER
    print(f"loading router: {model}")
    brain = RustBrain(model)
    tok = AutoTokenizer.from_pretrained(tok_name, trust_remote_code=True)
    axes = AxisAnchors()
    memory = CortexMemory(axes=axes)
    stats = ingest(brain, tok, axes, memory, vault,
                   limit=args.limit, dry_run=False, quiet=args.quiet)
    print(stats)
    brain.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
