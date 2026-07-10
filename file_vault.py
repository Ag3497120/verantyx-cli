"""
file_vault.py — 永遠の記憶のファイル資産層 (パソコンのベクトルバックアップ)
==============================================================================
ユーザーのファイル (文書・コード・メモ) をチャンク化してルーター (0.5B) で
ベクトル化し、永遠の記憶の隣に「資産層」として永続化する。

  - vault.vectors      : 1024次元 float32 の意味ベクトル列
  - vault.index.jsonl  : ノード (L1 6軸署名 / L2 概念語 / L3 パス+抜粋+行番号)
  - vault.manifest.json: パス -> mtime (増分更新: 変更のないファイルは再訪しない)
  - vault.config.json  : ユーザーの選択 (有効/無効、対象ルート、確認済みか)

できること:
  search(query)  : 意味ベクトルでパソコン内資産を横断検索
  persona(axes)  : ファイル資産の6軸分布からユーザー像を強化
                   (会話の記憶だけでなく「何を作り、何を溜めてきたか」を反映)

注意: バックアップと呼ぶが原本の複製は保存しない (抜粋+パスのみ)。
      原本が消えると L3 参照は切れる (意味ベクトルと抜粋は残る)。
"""

import json
import os
import time

import numpy as np

CHRONO = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono")
VAULT_VEC = os.path.join(CHRONO, "vault.vectors")
VAULT_IDX = os.path.join(CHRONO, "vault.index.jsonl")
VAULT_MANIFEST = os.path.join(CHRONO, "vault.manifest.json")
VAULT_CONFIG = os.path.join(CHRONO, "vault.config.json")

DIM = 1024
DEFAULT_ROOTS = ["~/Documents", "~/Desktop"]

TEXT_EXT = {
    ".txt", ".md", ".markdown", ".rst", ".org", ".tex",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".c", ".h", ".cpp",
    ".java", ".kt", ".swift", ".rb", ".php", ".sh", ".zsh", ".bash",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv", ".tsv",
    ".html", ".css", ".sql", ".log",
}
SKIP_DIRS = {
    "node_modules", ".git", ".venv", "venv", "__pycache__", ".cache",
    "Library", "Applications", ".Trash", "target", "build", "dist",
    ".npm", ".cargo", "site-packages", "envs",
}
MAX_FILE_BYTES = 300_000     # これ以上のファイルは先頭のみ
CHUNK_CHARS = 900
MAX_CHUNKS_PER_FILE = 6


# ── 設定 ──────────────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(VAULT_CONFIG):
        return json.load(open(VAULT_CONFIG))
    return {"asked": False, "enabled": False, "roots": DEFAULT_ROOTS, "last_build": 0}


def save_config(cfg):
    os.makedirs(CHRONO, exist_ok=True)
    json.dump(cfg, open(VAULT_CONFIG, "w"), ensure_ascii=False, indent=1)


# ── スキャン ──────────────────────────────────────────────────────────────────
def iter_files(roots):
    for root in roots:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                if fn.startswith("."):
                    continue
                if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                    yield os.path.join(dirpath, fn)


def chunk_file(path):
    """ファイル -> [(開始行, テキスト), ...]"""
    try:
        with open(path, "r", errors="ignore") as f:
            content = f.read(MAX_FILE_BYTES)
    except OSError:
        return []
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


def _keywords(text, k=8):
    freq = {}
    for w in text.replace("_", " ").split():
        w = w.strip("()[]{}<>.,:;\"'`#*=->").lower()
        if len(w) >= 4 and not w.isdigit():
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:k]]


# ── 資産層本体 ────────────────────────────────────────────────────────────────
class FileVault:
    def __init__(self):
        os.makedirs(CHRONO, exist_ok=True)
        self.index = []
        if os.path.exists(VAULT_IDX):
            with open(VAULT_IDX) as f:
                self.index = [json.loads(l) for l in f if l.strip()]
        self.manifest = {}
        if os.path.exists(VAULT_MANIFEST):
            self.manifest = json.load(open(VAULT_MANIFEST))
        self._vecs = None

    def _vectors(self):
        if self._vecs is None and os.path.exists(VAULT_VEC):
            self._vecs = np.fromfile(VAULT_VEC, dtype=np.float32).reshape(-1, DIM)
        return self._vecs if self._vecs is not None else np.zeros((0, DIM), np.float32)

    # ── 構築 (増分) ──
    def build(self, brain, tok, axes=None, roots=None, max_files=400,
              time_budget_s=600, log=print):
        """変更のあったファイルだけをベクトル化して追記する。
        max_files / time_budget_s を超えたら中断し、次回続きから再開できる。"""
        from verantyx_mind import embed_text
        roots = roots or load_config().get("roots", DEFAULT_ROOTS)
        t0 = time.time()
        todo = []
        for path in iter_files(roots):
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if self.manifest.get(path, {}).get("mtime") == mtime:
                continue
            todo.append((path, mtime))
        if not todo:
            log(f"  [Vault] すべて最新です (索引済み {len(self.manifest)} ファイル)")
            return 0
        log(f"  [Vault] 未索引 {len(todo)} ファイル (今回は最大 {max_files} 件 / "
            f"{time_budget_s}s で中断可)")
        done_files = added = 0
        vec_f = open(VAULT_VEC, "ab")
        idx_f = open(VAULT_IDX, "a")
        try:
            for path, mtime in todo[:max_files]:
                if time.time() - t0 > time_budget_s:
                    log(f"  [Vault] 時間切れ。次回 /vault で続きから再開します")
                    break
                chunks = chunk_file(path)
                for start_line, text in chunks:
                    label = f"[{os.path.basename(path)}] {text[:400]}"
                    v = embed_text(brain, tok, label)
                    sig = axes.signature(v).tolist() if axes and axes.available else []
                    node = {
                        "id": len(self.index), "ts": time.time(),
                        "L1_signature": [round(float(x), 4) for x in sig],
                        "L2_concepts": _keywords(text),
                        "L3_path": path, "L3_line": start_line,
                        "L3_excerpt": text[:280],
                        "mtime": mtime,
                    }
                    v.astype(np.float32).tofile(vec_f)
                    idx_f.write(json.dumps(node, ensure_ascii=False) + "\n")
                    self.index.append(node)
                    added += 1
                self.manifest[path] = {"mtime": mtime, "chunks": len(chunks)}
                done_files += 1
                if done_files % 20 == 0:
                    log(f"  [Vault] {done_files}/{min(len(todo), max_files)} ファイル "
                        f"({added} チャンク, {time.time()-t0:.0f}s)")
        finally:
            vec_f.close()
            idx_f.close()
            json.dump(self.manifest, open(VAULT_MANIFEST, "w"))
            self._vecs = None
        cfg = load_config()
        cfg["last_build"] = time.time()
        save_config(cfg)
        log(f"  [Vault] 完了: +{done_files} ファイル / +{added} チャンク "
            f"(総計 {len(self.index)} ノード, {time.time()-t0:.0f}s)")
        return added

    # ── 検索 ──
    def search(self, qv, k=6):
        V = self._vectors()
        if len(V) == 0:
            return []
        qn = qv / (np.linalg.norm(qv) + 1e-8)
        sims = (V @ qn) / (np.linalg.norm(V, axis=1) + 1e-8)
        order = np.argsort(sims)[::-1][:k]
        return [(self.index[i], float(sims[i])) for i in order]

    # ── ペルソナ強化 ──
    def persona(self, axes, top=3):
        """ファイル資産の6軸分布からユーザー像を返す。"""
        if not (axes and axes.available):
            return []
        sigs = [n["L1_signature"] for n in self.index if n.get("L1_signature")]
        if len(sigs) < 3:
            return []
        mean = np.abs(np.array(sigs, dtype=np.float32)).mean(axis=0)
        from verantyx_mind import AXIS_NAMES
        order = np.argsort(mean)[::-1][:top]
        return [(AXIS_NAMES[i].strip(), float(mean[i])) for i in order]

    def stats(self):
        exts = {}
        for p in self.manifest:
            e = os.path.splitext(p)[1].lower()
            exts[e] = exts.get(e, 0) + 1
        top = sorted(exts.items(), key=lambda x: -x[1])[:6]
        return {"files": len(self.manifest), "chunks": len(self.index),
                "top_ext": top,
                "bytes": os.path.getsize(VAULT_VEC) if os.path.exists(VAULT_VEC) else 0}


if __name__ == "__main__":
    import sys
    vault = FileVault()
    print("[Vault] stats:", vault.stats())
    if len(sys.argv) > 1:
        from transformers import AutoTokenizer
        from verantyx_mind import DEFAULT_MODEL, TOKENIZER, RustBrain, embed_text
        tok = AutoTokenizer.from_pretrained(TOKENIZER)
        brain = RustBrain(DEFAULT_MODEL)
        qv = embed_text(brain, tok, " ".join(sys.argv[1:]))
        for node, sim in vault.search(qv):
            print(f"  sim={sim:.3f}  {node['L3_path']}:{node['L3_line']}")
            print(f"    {node['L3_excerpt'][:100]}")
        brain.close()
