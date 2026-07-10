"""
verantyx_mind.py — JCross Mind: 思考の可視化 / ベクトル思考→翻訳→発話 / 永遠の記憶
====================================================================================

年代記 (Chronicles Vol.1-4) のコンセプトを、モックなしの実演算で統合したパイプライン。

  [Think]   Rust エンジン (jcross_engine_glm) の本物の 24 層フォワードでプロンプトを
            1024 次元の思考ベクトルへエンコードし、Telepathic Resonance
            (lm_head によるトークン多様体への射影) を反復して潜在空間で思考を収束させる。
            各ステップでエントロピー・6概念軸・最近傍トークン雲・ドリフトを可視化。

  [Recall]  永遠の記憶 (SSD 上の fp16 ベクトル + 自然言語ラベルの対応表) から
            コサイン類似で過去の思考を検索し、ベクトルと言語の両方で注入する。
            コンテキストウィンドウにも KV キャッシュにも依存しない。

  [Speak]   収束した思考ベクトルを概念トークンへ「翻訳」し、同じ jgen モデルが
            ChatML プロンプトで肉付けして自然言語として発話する
            (Philosophical Drift 対策: テキストアンカーで言語軸を固定)。

  [Memorize] 対話をベクトル化して永遠の記憶へ追記する。

使い方:
  python3 verantyx_mind.py                          # 対話 REPL
  python3 verantyx_mind.py --prompt "..."           # ワンショット
  python3 verantyx_mind.py --recall "..."           # 記憶の検索のみ
  python3 verantyx_mind.py --steps 8 --speak-tokens 60
"""

import argparse
import ctypes
import json
import math
import os
import re
import struct
import sys
import time
import uuid
from contextlib import contextmanager

import numpy as np

# 「さっきの続きから」等のエピソード継続要求の検出
CONTINUATION_RE = re.compile(
    r"続き|つづき|さっき|前回|この前|先ほど|continue|resume|last time|where we left", re.I)

# ── 定数 ──────────────────────────────────────────────────────────────────────
def _find_engine_lib():
    """OS ごとの動的ライブラリを探す (macOS .dylib / Linux .so / Windows .dll)。"""
    import sys as _sys
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "jcross_engine_glm", "target", "release")
    if _sys.platform == "darwin":
        names = ["libjcross_engine_glm.dylib"]
    elif _sys.platform.startswith("win"):
        names = ["jcross_engine_glm.dll"]
    else:
        names = ["libjcross_engine_glm.so"]
    for n in names:
        p = os.path.join(base, n)
        if os.path.exists(p):
            return p
    return os.path.join(base, names[0])  # ロード時に明示的なエラーを出させる


DYLIB = os.environ.get("JCROSS_LIB") or _find_engine_lib()
# ルーターの解決順: verantyx.config.json > 環境変数 JGEN_MODEL > 既知パス > レジストリ
_ROUTER_FALLBACKS = (
    "/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "converted_models", "qwen_0.5b_full.jgen"),
)
try:
    import verantyx_config as _vcfg
    DEFAULT_MODEL = _vcfg.resolve_router(_ROUTER_FALLBACKS) or _ROUTER_FALLBACKS[0]
    TOKENIZER = _vcfg.get("models.router_tokenizer", "Qwen/Qwen1.5-0.5B-Chat")
except Exception:
    DEFAULT_MODEL = _ROUTER_FALLBACKS[0]
    TOKENIZER = "Qwen/Qwen1.5-0.5B-Chat"
HIDDEN = 1024
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono")
MEMORY_VEC = os.path.join(MEMORY_DIR, "eternal_v2.vectors")
MEMORY_IDX = os.path.join(MEMORY_DIR, "eternal_v2.index.jsonl")
MEMORY_V3_VEC = os.path.join(MEMORY_DIR, "cortex_v3.vectors")
MEMORY_V3_IDX = os.path.join(MEMORY_DIR, "cortex_v3.nodes.jsonl")
ANCHOR_PATH = os.path.join(MEMORY_DIR, "axis_anchors.npz")

AXIS_NAMES = [
    "Logic/Structure", "Syntax/Code    ", "Factual Memory ",
    "Temporal/Time  ", "Creativity     ", "Swarm Consensus",
]

C_SYS, C_THINK, C_SPEAK, C_MEM, C_RESET = "\033[90m", "\033[36m", "\033[95m", "\033[33m", "\033[0m"


@contextmanager
def quiet_native_stdout():
    """Rust エンジンの内部ログ (Prefill/Coder 行) を抑制する。VERANTYX_VERBOSE=1 で無効化。"""
    if os.environ.get("VERANTYX_VERBOSE"):
        yield
        return
    sys.stdout.flush()
    saved = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    try:
        yield
    finally:
        os.dup2(saved, 1)
        os.close(saved)
        os.close(devnull)


# ── jgen 直接読み (lm_head を数値演算用に mmap) ────────────────────────────────
class JGenDict:
    """jgen 内の embed_tokens / lm_head を numpy memmap で開く (ベクトル⇔語彙の対応辞書)。"""

    def __init__(self, path):
        self.path = path
        self._offsets = {}
        with open(path, "rb") as f:
            magic = f.read(4)
            assert magic == b"JGEN", "not a JGEN file"
            version, count = struct.unpack("<II", f.read(8))
            for _ in range(count):
                (nl,) = struct.unpack("<H", f.read(2))
                name = f.read(nl).decode()
                t = f.read(1)[0]
                if t == 1:
                    rows, cols, rank = struct.unpack("<III", f.read(12))
                    nbytes = (rows * rank + rank + cols * rank + cols + rows + rank * rank) * 2
                elif t == 2:
                    rows, cols = struct.unpack("<II", f.read(8))
                    nbytes = rows * cols * 2
                    if name in ("embed_tokens", "lm_head",
                                "model.embed_tokens.weight", "lm_head.weight",
                                "model.language_model.embed_tokens.weight"):
                        key = "embed_tokens" if "embed" in name else "lm_head"
                        self._offsets.setdefault(key, (f.tell(), rows, cols))
                elif t == 3:
                    (length,) = struct.unpack("<I", f.read(4))
                    nbytes = length * 2
                else:
                    break
                f.seek(nbytes, 1)
        off, rows, cols = self._offsets["lm_head"]
        self._lm_head_f16 = np.memmap(path, dtype=np.float16, mode="r", offset=off, shape=(rows, cols))
        self._lm_head_f32 = None  # 初回使用時に f32 へ変換してキャッシュ
        eoff, erows, ecols = self._offsets["embed_tokens"]
        self._embed_f16 = np.memmap(path, dtype=np.float16, mode="r", offset=eoff, shape=(erows, ecols))
        self.vocab_size = rows
        self.hidden = cols
        self.first_special = 151643 if rows > 151643 else rows  # Qwen系特殊トークンの除外
        self._semantic_mask = None

    @property
    def lm_head(self):
        if self._lm_head_f32 is None:
            print(f"{C_SYS}  [Dict] lm_head ({self.vocab_size}x{HIDDEN}) を f32 キャッシュへ展開中...{C_RESET}")
            self._lm_head_f32 = np.asarray(self._lm_head_f16, dtype=np.float32)
        return self._lm_head_f32

    def logits(self, z):
        return self.lm_head @ z

    def semantic_mask(self, tok):
        """意味を持つトークン (英数字か CJK を含む) だけを思考多様体として許可するマスク。
        改行・空白・記号のみのトークンへの共鳴崩壊 (Philosophical Drift の変種) を防ぐ。"""
        if self._semantic_mask is not None:
            return self._semantic_mask
        cache = os.path.join(MEMORY_DIR, "semantic_mask.npy")
        if os.path.exists(cache):
            m = np.load(cache)
            if m.shape[0] == self.vocab_size:
                self._semantic_mask = m
                return m
        print(f"{C_SYS}  [Dict] 意味トークンマスクを構築中 (初回のみ)...{C_RESET}")
        toks = tok.convert_ids_to_tokens(list(range(self.first_special)))
        mask = np.zeros(self.vocab_size, dtype=bool)
        for i, t in enumerate(toks):
            if t is None:
                continue
            body = t.replace("Ġ", "").replace("Ċ", "").replace("ĉ", "")
            if any(c.isalnum() or ord(c) > 0x2E80 for c in body):
                mask[i] = True
        os.makedirs(MEMORY_DIR, exist_ok=True)
        np.save(cache, mask)
        self._semantic_mask = mask
        return mask

    def to_embedding(self, z, temperature=1.0, top_m=256, mask=None):
        """思考ベクトル (最終隠れ空間) -> 入力埋め込み空間の仮想トークン。
        p = softmax(lm_head z / T) の上位トークンの埋め込み行の期待値。
        これにより他エージェントの思考をテキスト化せずフォワードパスへ注入できる。"""
        lg = self.logits(np.asarray(z, dtype=np.float32)) / max(temperature, 1e-3)
        lg[self.first_special:] = -np.inf
        if mask is not None:
            lg[~mask] = -np.inf
        lg -= lg[np.isfinite(lg)].max()
        p = np.exp(lg)
        p /= p.sum()
        top = np.argpartition(p, -top_m)[-top_m:]
        w = p[top]
        rows = self._embed_f16[np.sort(top)].astype(np.float32)
        w = p[np.sort(top)]
        e = (w[:, None] * rows).sum(axis=0) / (w.sum() + 1e-8)
        # 混合で縮んだノルムを、加重平均行ノルムへ引き戻す
        target = float((w * np.linalg.norm(rows, axis=1)).sum() / (w.sum() + 1e-8))
        e *= target / (np.linalg.norm(e) + 1e-8)
        return e.astype(np.float32)

    def resonance(self, z, temperature=0.7, top_m=512, mask=None):
        """Telepathic Resonance: 思考ベクトルをトークン多様体へ引き戻す。
        z -> softmax(lm_head z / T) の上位 top_m トークンの期待方向。"""
        lg = self.logits(z) / max(temperature, 1e-3)
        lg[self.first_special:] = -np.inf  # 特殊トークンへの崩壊を防ぐ
        if mask is not None:
            lg[~mask] = -np.inf
        lg -= lg[np.isfinite(lg)].max()
        p = np.exp(lg)
        p /= p.sum()
        top = np.argpartition(p, -top_m)[-top_m:]
        w = p[top]
        z_res = (w[:, None] * self.lm_head[top]).sum(axis=0) / w.sum()
        entropy = float(-(p[p > 0] * np.log2(p[p > 0])).sum())
        return z_res.astype(np.float32), entropy, p, top


# ── Rust エンジン (本物の 24 層フォワード + 自己回帰生成) ──────────────────────
class RustBrain:
    def __init__(self, model_path, hidden=HIDDEN):
        self.hidden = hidden
        lib = ctypes.CDLL(DYLIB)
        lib.jcross_engine_create.argtypes = [ctypes.c_char_p]
        lib.jcross_engine_create.restype = ctypes.c_void_p
        lib.jcross_engine_generate.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
            ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t]
        lib.jcross_engine_generate.restype = ctypes.c_int
        lib.jcross_engine_encode.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_float), ctypes.c_size_t]
        lib.jcross_engine_encode.restype = ctypes.c_int
        lib.jcross_engine_encode_soft.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_float), ctypes.c_size_t]
        lib.jcross_engine_encode_soft.restype = ctypes.c_int
        lib.jcross_engine_reset.argtypes = [ctypes.c_void_p]
        lib.jcross_engine_destroy.argtypes = [ctypes.c_void_p]
        self.lib = lib
        with quiet_native_stdout():
            self.engine = lib.jcross_engine_create(model_path.encode())
        if not self.engine:
            raise RuntimeError(f"エンジン初期化失敗: {model_path}")

    def encode(self, token_ids):
        """トークン列 -> 最終層 (final-norm 適用済み) の思考ベクトル。"""
        self.lib.jcross_engine_reset(self.engine)
        n = len(token_ids)
        arr = (ctypes.c_uint32 * n)(*token_ids)
        out = (ctypes.c_float * self.hidden)()
        with quiet_native_stdout():
            r = self.lib.jcross_engine_encode(self.engine, arr, n, out, self.hidden)
        if r != 0:
            raise RuntimeError(f"encode failed: {r}")
        return np.array(out[: self.hidden], dtype=np.float32)

    def encode_soft(self, soft_vectors, token_ids):
        """ベクトル通信: 他エージェントの思考 (埋め込み空間の仮想トークン) を
        プロンプトの前に注入してフォワードする。"""
        self.lib.jcross_engine_reset(self.engine)
        soft = np.ascontiguousarray(soft_vectors, dtype=np.float32)
        n_soft = soft.shape[0] if soft.ndim == 2 else 0
        soft_ptr = soft.ctypes.data_as(ctypes.POINTER(ctypes.c_float)) if n_soft else None
        n = len(token_ids)
        arr = (ctypes.c_uint32 * max(n, 1))(*token_ids) if n else None
        out = (ctypes.c_float * self.hidden)()
        with quiet_native_stdout():
            r = self.lib.jcross_engine_encode_soft(
                self.engine, soft_ptr, n_soft, soft.shape[1] if n_soft else 0,
                arr, n, out, self.hidden)
        if r != 0:
            raise RuntimeError(f"encode_soft failed: {r}")
        return np.array(out[: self.hidden], dtype=np.float32)

    def generate(self, token_ids, max_new):
        self.lib.jcross_engine_reset(self.engine)
        n = len(token_ids)
        arr = (ctypes.c_uint32 * n)(*token_ids)
        cap = n + max_new + 16
        out = (ctypes.c_uint32 * cap)()
        with quiet_native_stdout():
            r = self.lib.jcross_engine_generate(self.engine, arr, n, max_new, out, cap)
        if r < 0:
            raise RuntimeError(f"generate failed: {r}")
        return [out[i] for i in range(r)]

    def trim(self):
        """合成済み重みキャッシュ (CPU f32 + GPU) と KV を解放して mmap 相当まで
        フットプリントを戻す。重みは次の使用時に遅延再合成される。"""
        if not self.engine:
            return
        try:
            self.lib.jcross_engine_trim.argtypes = [ctypes.c_void_p]
            self.lib.jcross_engine_trim(self.engine)
        except AttributeError:
            pass  # 旧dylib (trim未実装) では何もしない

    def close(self):
        if self.engine:
            self.lib.jcross_engine_destroy(self.engine)
            self.engine = None


# ── 6軸アンカー (axis_anchor_trainer.py が学習した実測軸) ──────────────────────
class AxisAnchors:
    """学習済みの6概念軸。存在すれば可視化と記憶のL1署名が「実測」になる。"""

    def __init__(self):
        self.available = os.path.exists(ANCHOR_PATH)
        if self.available:
            data = np.load(ANCHOR_PATH)
            self.mu = data["mu"].astype(np.float32)
            self.anchors = data["anchors"].astype(np.float32)  # (6, HIDDEN) 単位ベクトル
            self.hold_acc = float(data["hold_acc"])

    def signature(self, vec):
        """1024次元ベクトル -> 6次元の軸署名 (アンカーとのcos)。記憶ノードのL1に相当。"""
        v = np.asarray(vec, dtype=np.float32).reshape(HIDDEN) - self.mu
        v = v / (np.linalg.norm(v) + 1e-8)
        return (self.anchors @ v).astype(np.float32)


# ── 永遠の記憶 v3: cortex 3解像度ノードのベクトル版 ───────────────────────────
class CortexMemory:
    """cortex (.jcross) の L1/L1.5/L2/L3 構造をベクトルでそのまま実装した追記型ストア。

      L1   : 6次元の軸署名 (漢字トポロジータグのベクトル版)。JSONLに直置き、O(1)スキャン
      L1.5 : 1024次元 PromptEOL 埋め込み (インデックス行のベクトル版)。fp16で別ファイル
      L2   : 概念トークン列 (OP.MAP のベクトル版)。埋め込みの lm_head 射影から抽出
      L3   : 原文そのまま (本質記憶)。上位ヒットのみ発話プロンプトに展開

    検索はカスケード: L1署名で粗選別 -> 候補だけL1.5コサイン -> 上位のみL3を返す。
    コンテキストウィンドウ/KVキャッシュから独立し、プロセスを跨いで永続する。"""

    GRAVITY_HALF_LIFE_DAYS = 30.0  # 参照されるたびに実効半減期が伸びる (= 生きた記憶)

    def __init__(self, axes=None):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self.axes = axes
        self.session = uuid.uuid4().hex[:8]  # このプロセスのエピソードID
        # シークレットモード: False の間は参照も刻印も行わない (バイアスなし対話)。
        # ストアには一切触れないだけなので、復帰すれば全記憶がそのまま戻る。
        self.enabled = True
        self.index = []
        if os.path.exists(MEMORY_V3_IDX):
            with open(MEMORY_V3_IDX) as f:
                self.index = [json.loads(l) for l in f if l.strip()]
        self._vectors = None
        self._migrate_v2()

    def _migrate_v2(self):
        """旧 v2 ストア (Beaux 等) を v3 ノードへ一度だけ取り込む。"""
        if self.index or not os.path.exists(MEMORY_IDX):
            return
        with open(MEMORY_IDX) as f:
            old = [json.loads(l) for l in f if l.strip()]
        if not old:
            return
        raw = np.fromfile(MEMORY_VEC, dtype=np.float16)
        vecs = raw[: len(old) * HIDDEN].reshape(len(old), HIDDEN).astype(np.float32)
        for rec, vec in zip(old, vecs):
            self.add(vec, rec["text"], concepts=[], ts=rec.get("ts"), quiet=True)
        print(f"{C_MEM}  [Cortex Memory] v2の記憶 {len(old)} 件を v3ノードへ移行{C_RESET}")

    def _load_vectors(self):
        n = len(self.index)
        if n == 0:
            return np.zeros((0, HIDDEN), dtype=np.float32)
        if self._vectors is None or self._vectors.shape[0] != n:
            raw = np.fromfile(MEMORY_V3_VEC, dtype=np.float16)
            self._vectors = raw[: n * HIDDEN].reshape(n, HIDDEN).astype(np.float32)
        return self._vectors

    def add(self, vector, text, concepts=None, ts=None, quiet=False, kind="episode", extra=None):
        if not self.enabled:
            return
        v = np.asarray(vector, dtype=np.float32).reshape(HIDDEN)
        with open(MEMORY_V3_VEC, "ab") as f:
            f.write(v.astype(np.float16).tobytes())
        sig = self.axes.signature(v).tolist() if (self.axes and self.axes.available) else None
        rec = {
            "id": len(self.index),
            "ts": ts or time.time(),
            "kind": kind,                  # episode | route | fact ...
            "session": self.session,
            "l1_sig": sig,                 # L1  : 軸署名 (6 floats)
            "l2_concepts": concepts or [], # L2  : 概念トークン
            "l3_text": text,               # L3  : 原文
            "access_count": 0,
            "last_access": ts or time.time(),
        }
        if extra:
            rec.update(extra)
        with open(MEMORY_V3_IDX, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.index.append(rec)
        self._vectors = None
        if not quiet:
            sig_str = ""
            if sig:
                dom = int(np.argmax(np.abs(sig)))
                sig_str = f" | L1署名 dominant: {AXIS_NAMES[dom].strip()}"
            print(f"{C_MEM}  [Cortex Memory] ノード #{rec['id']} を刻印{sig_str}: {text[:55]}{C_RESET}")

    def _rewrite_index(self):
        with open(MEMORY_V3_IDX, "w") as f:
            for rec in self.index:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def gravity(self, rec, now=None):
        """時間減衰する重力。参照されるほど半減期が伸び、記憶は「生き続ける」。
        どんなに古くても削除はされず、参照されにくい場所へ沈むだけ。"""
        now = now or time.time()
        age_days = max(0.0, now - rec["ts"]) / 86400.0
        half_life = self.GRAVITY_HALF_LIFE_DAYS * (1.0 + rec.get("access_count", 0))
        return math.exp(-age_days * math.log(2) / half_life)

    def reinforce(self, node_id):
        """想起された記憶を強化する (アクセス統計の更新)。"""
        rec = self.index[node_id]
        rec["access_count"] = rec.get("access_count", 0) + 1
        rec["last_access"] = time.time()
        self._rewrite_index()

    def recall_episode(self, max_turns=3):
        """「さっきの続きから」用: 直近の別セッションの対話ターンを新しい順に返す。"""
        if not self.enabled:
            return []
        eps = [r for r in self.index
               if r.get("kind", "episode") == "episode" and r.get("session") != self.session]
        eps.sort(key=lambda r: r["ts"], reverse=True)
        if not eps:
            return []
        last_session = eps[0].get("session")
        turns = [r for r in eps if r.get("session") == last_session][:max_turns]
        for r in turns:
            self.reinforce(r["id"])
        return [r["l3_text"] for r in reversed(turns)]

    def persona(self):
        """L1署名の重力加重平均からユーザーペルソナ (支配的な軸) を抽出する。"""
        if not (self.axes and self.axes.available) or not self.enabled:
            return None
        now = time.time()
        acc = np.zeros(6, dtype=np.float32)
        wsum = 0.0
        for r in self.index:
            if r.get("l1_sig") and r.get("kind", "episode") == "episode":
                g = self.gravity(r, now)
                acc += g * np.array(r["l1_sig"], dtype=np.float32)
                wsum += g
        if wsum < 1e-6:
            return None
        mean_sig = acc / wsum
        order = np.argsort(mean_sig)[::-1]
        return [(AXIS_NAMES[i].strip(), float(mean_sig[i])) for i in order[:2]]

    @staticmethod
    def _bigrams(s):
        s = re.sub(r"\s+", "", s.lower())
        return {s[i:i + 2] for i in range(len(s) - 1)}

    def _lex_scores(self, query_text):
        """文字バイグラム重なりによる字句スコア (0..1)。分かち書き不要で日本語も効く。
        0.5B埋め込みは弁別力が弱く『メタバース』のような固有語で外すため、
        ベクトル検索に字句一致を混ぜるハイブリッドにする。"""
        qg = self._bigrams(query_text or "")
        if not qg:
            return np.zeros(len(self.index), dtype=np.float32)
        out = np.empty(len(self.index), dtype=np.float32)
        for i, r in enumerate(self.index):
            tg = self._bigrams(r.get("l3_text", ""))
            out[i] = len(qg & tg) / len(qg)
        return out

    def search(self, query_vec, k=3, l1_keep=32, query_text=None):
        """カスケード検索: L1署名 (6次元) -> L1.5全次元コサイン -> L3原文。
        query_text を渡すと字句一致ブーストが乗る (ハイブリッド検索)。"""
        n = len(self.index)
        if n == 0 or not self.enabled:
            return []
        q = np.asarray(query_vec, dtype=np.float32).reshape(HIDDEN)
        qn = q / (np.linalg.norm(q) + 1e-8)

        lex = self._lex_scores(query_text) if query_text else None
        candidates = np.arange(n)
        if self.axes and self.axes.available and n > l1_keep:
            # L1: 6次元署名だけで粗選別 (全ノードO(1)級スキャンに相当)
            q_sig = self.axes.signature(q)
            q_sig = q_sig / (np.linalg.norm(q_sig) + 1e-8)
            sigs = np.array([r["l1_sig"] if r["l1_sig"] else [0.0] * 6 for r in self.index],
                            dtype=np.float32)
            sigs /= np.linalg.norm(sigs, axis=1, keepdims=True) + 1e-8
            l1_scores = sigs @ q_sig
            candidates = np.argsort(l1_scores)[::-1][:l1_keep]
            if lex is not None:
                # 字句で強く当たるノードはL1粗選別で落とさない
                lex_hits = np.where(lex >= 0.15)[0]
                candidates = np.unique(np.concatenate([candidates, lex_hits]))

        # L1.5: 候補だけフル1024次元コサイン、重力 (時間減衰×参照強化) で加重
        db = self._load_vectors()[candidates]
        dbn = db / (np.linalg.norm(db, axis=1, keepdims=True) + 1e-8)
        sims = dbn @ qn
        now = time.time()
        grav = np.array([self.gravity(self.index[int(i)], now) for i in candidates], dtype=np.float32)
        eff = sims * (0.7 + 0.3 * grav)  # 古い記憶は消えず、沈むだけ
        if lex is not None:
            eff = eff + 0.5 * lex[candidates]
        order = np.argsort(eff)[::-1][:k]
        results = []
        for o in order:
            i = int(candidates[o])
            rec = self.index[i]
            results.append((rec["l3_text"], float(eff[o]), db[o], rec.get("l2_concepts", []), i))
        return results


# ── 可視化 ─────────────────────────────────────────────────────────────────────
def bar(frac, width=12):
    n = max(0, min(width, int(round(frac * width))))
    return "█" * n + "░" * (width - n)


def show_axes(z, axes=None):
    if axes is not None and axes.available:
        # 学習済みアンカーによる実測: 各軸方向とのcosを [0,1] に写像して表示
        sig = axes.signature(z)
        vals = (sig + 1.0) / 2.0
        dom = int(np.argmax(sig))
        for i in range(6):
            mark = " <- DOMINANT" if i == dom else ""
            print(f"{C_THINK}      Axis {i} ({AXIS_NAMES[i]}) : {bar(vals[i])} (cos {sig[i]:+.2f}){mark}{C_RESET}")
        return
    # フォールバック: 未学習時は次元区画のエネルギー表示 (慣例的)
    chunk = HIDDEN // 6
    energies = []
    for i in range(6):
        seg = z[i * chunk: (i + 1) * chunk] if i < 5 else z[i * chunk:]
        energies.append(float(np.abs(seg).mean()))
    peak = max(energies) + 1e-8
    for i, e in enumerate(energies):
        frac = e / peak
        mark = " <- DOMINANT" if frac > 0.999 else ""
        print(f"{C_THINK}      Axis {i} ({AXIS_NAMES[i]}) : {bar(frac)} ({int(frac*100):3d}%){mark}{C_RESET}")


def token_cloud(tok, p, top_idx, k=5):
    pairs = sorted(((p[i], int(i)) for i in top_idx), reverse=True)
    out = []
    for prob, tid in pairs:
        s = tok.decode([tid])
        if "\ufffd" in s:
            continue
        s = s.strip() or repr(s)  # 空白系トークンも可視化する
        out.append((s, prob))
        if len(out) >= k:
            break
    return out


def embed_text(brain, tok, text):
    """PromptEOL 方式のテキスト埋め込み。永遠の記憶の格納/検索キーに使う。
    最終隠れ状態を「一語での意味」に集約させることで弁別性を上げる。"""
    prompt = f'This sentence: "{text}" means in one word:"'
    ids = tok.encode(prompt, add_special_tokens=False)
    z = brain.encode(ids)
    return z / (np.linalg.norm(z) + 1e-8)


# ── 思考ループ (Think) ─────────────────────────────────────────────────────────
def think(brain, dictionary, tok, prompt_text, memory, axes=None, steps=8,
          temperature=1.0, resonance_alpha=0.25, mem_blend=0.2):
    print(f"\n{C_THINK}━━ [Think] JCross 潜在空間で思考を開始 ━━{C_RESET}")
    t0 = time.time()
    # ChatML で包むことで、思考ベクトルが「回答の萌芽」を表すようにする
    # (生テキストのままだと「次の質問の予測」に収束してしまう)
    chatml = f"<|im_start|>user\n{prompt_text}<|im_end|>\n<|im_start|>assistant\n"
    ids = tok.encode(chatml, add_special_tokens=False)
    print(f"{C_SYS}  encode: {len(ids)} tokens -> 24層フォワード (実演算)...{C_RESET}")
    z0 = brain.encode(ids)
    z = z0.copy()
    base_norm = float(np.linalg.norm(z0)) + 1e-8

    # 永遠の記憶からベクトル想起 → 思考へブレンド
    query_vec = embed_text(brain, tok, prompt_text)
    recalled = memory.search(query_vec, k=3, query_text=prompt_text)
    strong = [r for r in recalled if r[1] > 0.78]
    if strong:
        print(f"{C_MEM}  [Recall] 関連する過去の思考 {len(strong)} 件 (L1→L1.5→L3 カスケード):{C_RESET}")
        mvec = np.zeros(HIDDEN, dtype=np.float32)
        wsum = 0.0
        for text, sim, vec, concepts_l2, node_id in strong:
            l2 = f" | L2: {','.join(concepts_l2[:3])}" if concepts_l2 else ""
            print(f"{C_MEM}    sim={sim:.3f}{l2}  {text[:60]}{C_RESET}")
            memory.reinforce(node_id)  # 想起された記憶は強化され、生き続ける
            mvec += sim * vec
            wsum += sim
        mvec /= wsum
        z = (1 - mem_blend) * z + mem_blend * (mvec / (np.linalg.norm(mvec) + 1e-8)) * base_norm

    entropy_hist = []
    sem_mask = dictionary.semantic_mask(tok)
    first_cloud = None
    for step in range(1, steps + 1):
        z_res, entropy, p, top = dictionary.resonance(z, temperature=temperature, mask=sem_mask)
        if first_cloud is None:
            first_cloud = token_cloud(tok, p, top, k=16)  # 結晶化前の最も意味豊かな分布
        # 共鳴方向へ引き込み (トークン多様体への Cascading Lock)
        z = (1 - resonance_alpha) * z + resonance_alpha * (z_res / (np.linalg.norm(z_res) + 1e-8)) * base_norm
        drift = float(np.dot(z, z0) / (np.linalg.norm(z) * np.linalg.norm(z0) + 1e-8))
        entropy_hist.append(entropy)

        cloud = token_cloud(tok, p, top, k=5)
        cloud_str = "  ".join(f"'{s}'({pr*100:.0f}%)" for s, pr in cloud)
        max_e = math.log2(dictionary.vocab_size)
        print(f"{C_THINK}  step {step:2d} | Entropy {entropy:6.2f} bits {bar(1 - entropy / max_e)} | anchor-cos {drift:.3f}{C_RESET}")
        print(f"{C_THINK}          思考の言語化 (最近傍トークン雲): {cloud_str}{C_RESET}")
        show_axes(z, axes)

        if entropy < 1.0:
            print(f"{C_THINK}  >> エントロピーがロック閾値未満。思考が結晶化しました。{C_RESET}")
            break
        if step >= 2 and abs(entropy_hist[-2] - entropy) < 0.02:
            print(f"{C_THINK}  >> 共鳴が平衡に到達 (ΔEntropy < 0.02)。{C_RESET}")
            break

    # 概念翻訳: 結晶化直前 (step 1) の分布が最も意味情報を保持している。
    # 一文字・記号のみのトークンは肉付け用アンカーから外す
    concepts = [s for s, _ in (first_cloud or [])
                if len(s) >= 2 and any(c.isalnum() or ord(c) > 0x2E80 for c in s)][:6]
    print(f"{C_THINK}━━ [Think] 完了 ({time.time()-t0:.1f}s) | 翻訳された概念: {concepts}{C_RESET}")
    return z, concepts, [r[0] for r in strong]


# ── 発話 (Speak): 翻訳された概念をワーカーモデルが肉付け ───────────────────────
def speak(brain, tok, user_text, concepts, memory_texts, max_new="auto",
          persona=None, worker_name=None):
    # 'auto' = EOS で自然に終わらせる (512 は暴走防止の天井)。数値なら固定上限
    max_new = 512 if max_new in (None, "auto") else int(max_new)
    who = f"ワーカー '{worker_name}'" if worker_name else "発話モデル"
    print(f"\n{C_SPEAK}━━ [Speak] {who}が概念を肉付け ━━{C_RESET}")
    t0 = time.time()
    sys_parts = ["You are a helpful assistant."]
    if persona:
        sys_parts.append("The user often engages with topics of: "
                         + " and ".join(n for n, _ in persona) + ".")
    if concepts:
        sys_parts.append("Internal thought concepts: " + ", ".join(concepts))
    prompt = f"<|im_start|>system\n{' '.join(sys_parts)}<|im_end|>\n"
    # 永遠の記憶を擬似的な過去対話ターンとして復元する
    # (KVキャッシュに残っていなくても、SSD上の記憶からコンテキストを再構築できる)
    for m in memory_texts[:3]:
        if m.startswith("Q: ") and "  →  A: " in m:
            q, a = m[3:].split("  →  A: ", 1)
            prompt += (f"<|im_start|>user\n{q.strip()}<|im_end|>\n"
                       f"<|im_start|>assistant\n{a.strip()}<|im_end|>\n")
    prompt += f"<|im_start|>user\n{user_text}<|im_end|>\n<|im_start|>assistant\n"
    ids = tok.encode(prompt, add_special_tokens=False)
    print(f"{C_SYS}  prompt {len(ids)} tokens -> 自己回帰生成 (max {max_new})...{C_RESET}")
    out_ids = brain.generate(ids, max_new)
    text = tok.decode(out_ids, skip_special_tokens=True).strip()
    if len(out_ids) >= max_new:  # 天井到達 = 途切れの可能性 → 文境界で整形
        from verantyx_council import polish_answer
        text = polish_answer(text)
    dt = time.time() - t0
    print(f"{C_SPEAK}  🤖 {text}{C_RESET}")
    print(f"{C_SYS}  ({len(out_ids)} tokens, {dt:.1f}s, {len(out_ids)/max(dt,1e-6):.2f} tok/s){C_RESET}")
    return text


def translate_vector(dictionary, tok, vec, k=4):
    """ベクトル -> 概念トークン列 (記憶ノードの L2 用)。
    PromptEOL 埋め込みは lm_head 射影がそのまま『一語での意味』になる。"""
    sem = dictionary.semantic_mask(tok)
    lg = dictionary.logits(np.asarray(vec, dtype=np.float32))
    lg[dictionary.first_special:] = -np.inf
    lg[~sem] = -np.inf
    top = np.argsort(lg)[::-1][:k * 3]
    out = []
    for tid in top:
        s = tok.decode([int(tid)]).strip()
        if len(s) >= 2 and any(c.isalnum() or ord(c) > 0x2E80 for c in s):
            out.append(s)
        if len(out) >= k:
            break
    return out


# ── ターン処理 ─────────────────────────────────────────────────────────────────
def run_turn(brain, dictionary, tok, memory, user_text, steps, speak_tokens,
             axes=None, memorize=True, worker=None):
    # 「さっきの続きから」→ 直近エピソードのターンを問答無用で文脈復元
    episodic = []
    if CONTINUATION_RE.search(user_text):
        episodic = memory.recall_episode(max_turns=3)
        if episodic:
            print(f"{C_MEM}  [Episodic] 前回セッションの文脈 {len(episodic)} ターンを復元{C_RESET}")
            for e in episodic:
                print(f"{C_MEM}    {e[:70]}{C_RESET}")

    z, concepts, mem_texts = think(brain, dictionary, tok, user_text, memory,
                                   axes=axes, steps=steps)
    # エピソード復元分を先頭に (重複は除く)
    mem_texts = episodic + [m for m in mem_texts if m not in episodic]

    speak_brain, speak_tok, wname = brain, tok, None
    if worker is not None:
        speak_brain, speak_tok, wname = worker
    reply = speak(speak_brain, speak_tok, user_text, concepts, mem_texts,
                  max_new=speak_tokens, persona=memory.persona(), worker_name=wname)
    if memorize and reply:
        label = f"Q: {user_text}  →  A: {reply[:120]}"
        mvec = embed_text(brain, tok, label)
        memory.add(mvec, label, concepts=translate_vector(dictionary, tok, mvec),
                   extra={"worker": wname})
    return reply


_PT_SESSION = None


def _read_via_prompt_toolkit():
    """長文・ペースト対応入力 (prompt_toolkit / bracketed paste)。
    - 複数行テキストをペーストしても改行で送信されない (そのまま編集可能)
    - Enter で送信 / Esc+Enter (または Ctrl+J) で手動改行
    """
    global _PT_SESSION
    if _PT_SESSION is None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()

        @kb.add("enter")
        def _submit(event):
            event.current_buffer.validate_and_handle()

        @kb.add("escape", "enter")
        @kb.add("c-j")
        def _newline(event):
            event.current_buffer.insert_text("\n")

        _PT_SESSION = PromptSession(multiline=True, key_bindings=kb,
                                    prompt_continuation="   ... ")
    return _PT_SESSION.prompt("\n🧑 You: ").strip()


def _read_via_stdin():
    """非TTY (パイプ/スクリプト) 用: 従来の1行=1メッセージ。
    - `\"\"\"` 単独行で開始 → `\"\"\"` 単独行まで読み続ける (ヒアドキュメント形式)
    - 行末が `\\` → 次の行へ継続
    """
    first = input("\n🧑 You: ")
    stripped = first.strip()
    if stripped == '"""':
        lines = []
        while True:
            line = input("   ... ")
            if line.strip() == '"""':
                break
            lines.append(line)
        return "\n".join(lines).strip()
    lines = [first.rstrip()]
    while lines[-1].endswith("\\"):
        lines[-1] = lines[-1][:-1].rstrip()
        lines.append(input("   ... ").rstrip())
    return "\n".join(lines).strip()


def _read_via_select():
    """prompt_toolkit がない TTY 用フォールバック: ペーストをバッファ検出で束ねる。
    ペースト直後は送信せず、単独の空行 Enter で送信する。"""
    import select
    print("\n🧑 You: ", end="", flush=True)
    lines = []
    while True:
        line = sys.stdin.readline()
        if line == "":
            if lines:
                return "\n".join(lines).strip()
            raise EOFError
        line = line.rstrip("\n")
        pending = select.select([sys.stdin], [], [], 0.03)[0]
        if pending:
            lines.append(line)          # ペースト継続中: まだ送信しない
            continue
        if not lines:
            return line.strip()          # 通常の1行入力は即送信
        if line.strip() == "":
            return "\n".join(lines).strip()  # 空行 Enter = 送信
        lines.append(line)
        print(f"   ... ({len(lines)}行。空行Enterで送信) ", end="", flush=True)


def read_user_input():
    """長文・複数行・ペースト対応の統一入力口。"""
    if not sys.stdin.isatty():
        return _read_via_stdin()
    try:
        return _read_via_prompt_toolkit()
    except ImportError:
        return _read_via_select()


def load_worker(name_or_auto, router_path):
    """レジストリからワーカーモデルを選び (brain, tokenizer, name) を返す。"""
    from transformers import AutoTokenizer
    import jgen_forge
    if name_or_auto == "none":
        return None
    if name_or_auto == "auto":
        # ルーター自身を除いた ready モデルから、スペックに収まる最大を選ぶ
        reg = jgen_forge.load_registry()
        exclude = {x["name"] for x in reg["models"]
                   if os.path.abspath(x["jgen"]) == os.path.abspath(router_path)}
        m = jgen_forge.select_worker(exclude=exclude)
    else:
        reg = jgen_forge.load_registry()
        m = next((x for x in reg["models"] if x["name"] == name_or_auto), None)
        if m and m["status"] != "ready":
            print(f"{C_SYS}  [Worker] {name_or_auto} は status={m['status']} のため使用不可{C_RESET}")
            m = None
    if m is None or os.path.abspath(m["jgen"]) == os.path.abspath(router_path):
        return None  # ルーター単独動作 (ルーター自身が発話も担当)
    wtok = AutoTokenizer.from_pretrained(m["tokenizer"]) if m.get("tokenizer") else None
    if wtok is None:
        print(f"{C_SYS}  [Worker] {m['name']} はトークナイザ未登録のため使用不可{C_RESET}")
        return None
    wbrain = RustBrain(m["jgen"], hidden=m.get("hidden") or HIDDEN)
    print(f"{C_SYS}  [Worker] 発話ワーカー起動: {m['name']} "
          f"({m['size_bytes']/(1<<30):.2f}GB, hidden={m.get('hidden')}){C_RESET}")
    return (wbrain, wtok, m["name"])


def main():
    ap = argparse.ArgumentParser(description="JCross Mind: 可視化つきベクトル思考 + 永遠の記憶")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="ルーター (思考/記憶) 用 jgen")
    ap.add_argument("--worker", default="auto",
                    help="発話ワーカー: レジストリ名 | auto (スペックで自動選択) | none (ルーター単独)")
    ap.add_argument("--prompt", default=None, help="ワンショット実行")
    ap.add_argument("--recall", default=None, help="記憶の検索のみ")
    ap.add_argument("--persona", action="store_true", help="ペルソナ表示のみ")
    ap.add_argument("--steps", default="auto",
                    help="思考ステップ数: auto (エントロピーロックで自動打ち切り、上限12) または固定 N")
    ap.add_argument("--speak-tokens", default="auto",
                    help="auto (EOSで自然終了) または固定 N")
    ap.add_argument("--no-memorize", action="store_true")
    ap.add_argument("--secret", action="store_true",
                    help="シークレットモードで開始 (記憶の参照も刻印もしないバイアスなし対話)")
    args = ap.parse_args()
    # auto = エントロピーロック任せで上限だけ広めに取る
    args.steps = 12 if args.steps == "auto" else int(args.steps)

    print(f"{C_SYS}╔═══════════════════════════════════════════════╗")
    print(f"║  Verantyx Mind — JCross Latent Cognition       ║")
    print(f"╚═══════════════════════════════════════════════╝{C_RESET}")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    axes = AxisAnchors()
    if axes.available:
        print(f"{C_SYS}  [Axes] 学習済み6軸アンカーをロード (holdout精度 {axes.hold_acc*100:.0f}%){C_RESET}")
    else:
        print(f"{C_SYS}  [Axes] アンカー未学習 (axis_anchor_trainer.py で学習可能)。区画エネルギー表示で代替{C_RESET}")
    memory = CortexMemory(axes)
    print(f"{C_MEM}  [Cortex Memory] 既存のノード: {len(memory.index)} 件{C_RESET}")
    if args.secret:
        memory.enabled = False
        print(f"{C_SYS}  [Secret] シークレットモード: 記憶の参照も刻印もしません{C_RESET}")

    if args.persona:
        p = memory.persona()
        if p:
            print(f"{C_MEM}  [Persona] 支配的な軸: " +
                  ", ".join(f"{n} ({v:+.2f})" for n, v in p) + f"{C_RESET}")
        else:
            print(f"{C_MEM}  [Persona] まだ十分な記憶がありません{C_RESET}")
        return

    # dropzone の新モデルを自動変換 (「格納すると変換が走る」)
    try:
        import jgen_forge
        jgen_forge.cmd_scan()
    except Exception as e:
        print(f"{C_SYS}  [Forge] scan skip: {e}{C_RESET}")

    dictionary = JGenDict(args.model)
    brain = RustBrain(args.model)
    print(f"{C_SYS}  [OK] ルーター起動: {os.path.basename(args.model)}{C_RESET}")
    worker = load_worker(args.worker, args.model)
    if worker is None:
        print(f"{C_SYS}  [Worker] ルーター単独動作 (発話もルーターが担当){C_RESET}")

    try:
        if args.recall:
            qv = embed_text(brain, tok, args.recall)
            results = memory.search(qv, k=5, query_text=args.recall)
            print(f"\n{C_MEM}━━ 記憶検索: '{args.recall}' ━━{C_RESET}")
            if not results:
                print(f"{C_MEM}  (記憶なし){C_RESET}")
            for text, sim, _, concepts_l2, _nid in results:
                l2 = f" | L2: {','.join(concepts_l2[:4])}" if concepts_l2 else ""
                print(f"{C_MEM}  sim={sim:.3f}{l2}  {text}{C_RESET}")
            return

        if args.prompt:
            run_turn(brain, dictionary, tok, memory, args.prompt,
                     args.steps, args.speak_tokens, axes=axes,
                     memorize=not args.no_memorize, worker=worker)
            return

        print(f"{C_SYS}  対話モード。'exit' で終了。/secret で記憶オフ切替、/persona でペルソナ表示{C_RESET}")
        print(f"{C_SYS}  長文ペーストOK (改行しても送信されません)。Enter=送信 / Esc+Enter=改行{C_RESET}")
        while True:
            try:
                user_text = read_user_input()
            except (KeyboardInterrupt, EOFError):
                print("\n[Exit]")
                break
            if not user_text or user_text.lower() in ("exit", "quit", "q"):
                break
            if user_text.strip() == "/secret":
                memory.enabled = not memory.enabled
                state = ("OFF (シークレット: 記憶の参照も刻印もしません)" if not memory.enabled
                         else "ON (永遠の記憶が有効です)")
                print(f"{C_SYS}  [Secret] 記憶 {state}{C_RESET}")
                continue
            if user_text.strip() == "/persona":
                p = memory.persona()
                if p:
                    print(f"{C_MEM}  [Persona] " + ", ".join(f"{n}({v:+.2f})" for n, v in p) + f"{C_RESET}")
                else:
                    print(f"{C_MEM}  [Persona] 無効 (シークレット中か記憶不足){C_RESET}")
                continue
            run_turn(brain, dictionary, tok, memory, user_text,
                     args.steps, args.speak_tokens, axes=axes,
                     memorize=not args.no_memorize, worker=worker)
    finally:
        brain.close()
        if worker is not None:
            worker[0].close()


if __name__ == "__main__":
    main()
