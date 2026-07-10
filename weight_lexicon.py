"""
weight_lexicon.py — 重み静的辞書 (Weight-as-Dictionary)
==============================================================================
開発記 (Chronicles) の構想の実装: 大型モデルの重みを「発火させず」(フォワード
パスを一切走らせず)、mmap した行列を連想辞書として直接検索する。

対応バックエンド (どちらも RAM をほぼ使わない):
  - JGEN v3 (.jgen)          : embed / lm_head の生行列
  - safetensors ディレクトリ : HF スナップショットを直接 mmap (bf16/f16対応)
                               → 変換不要で任意サイズのモデルが辞書になる

3つの検索レベル:
  associate(word) : 埋め込み空間の最近傍 (連想・類義・関連語)   [埋め込み層]
  analogy(a,b,c)  : ベクトル演算 a:b = c:?                      [埋め込み層]
  probe(word)     : MLP 層を key-value メモリとして読む知識探索  [MLP層]
                    (Geva+ 2021: FFN は key-value 連想記憶) —
                    埋め込みだけでなく「本体の知識」に触れる。
                    モデルが大きいほど MLP に蓄積された知識も増えるため、
                    こちらはパラメータ数に応じて知識量がスケールする。
"""

import json
import os
import struct

import numpy as np


# ── safetensors を numpy だけで mmap する (bf16対応) ─────────────────────────
def _bf16_to_f32(u16):
    return (u16.astype(np.uint32) << 16).view(np.float32)


class SafetensorsSource:
    """HF スナップショットのテンソルをゼロコピーで読む。"""

    def __init__(self, dir_path):
        self.dir = dir_path
        idx = os.path.join(dir_path, "model.safetensors.index.json")
        if os.path.exists(idx):
            self.weight_map = json.load(open(idx))["weight_map"]
        else:
            single = [f for f in os.listdir(dir_path) if f.endswith(".safetensors")]
            self.weight_map = {}
            for fn in single:
                for k in self._header(os.path.join(dir_path, fn))[0]:
                    self.weight_map[k] = fn
        self._headers = {}   # shard -> (header dict, data offset)
        self._mmaps = {}     # shard -> np.memmap (uint8)

    @staticmethod
    def _header(path):
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            return json.loads(f.read(n)), 8 + n

    def _shard(self, name):
        fn = self.weight_map[name]
        if fn not in self._headers:
            p = os.path.join(self.dir, fn)
            self._headers[fn] = self._header(p)
            self._mmaps[fn] = np.memmap(p, dtype=np.uint8, mode="r")
        return fn

    def info(self, name):
        fn = self._shard(name)
        h, _ = self._headers[fn]
        return h[name]["dtype"], h[name]["shape"]

    def vec(self, name):
        """1次元テンソルを float32 で返す。"""
        fn = self._shard(name)
        hdr, base = self._headers[fn]
        meta = hdr[name]
        (n,) = meta["shape"]
        start, _ = meta["data_offsets"]
        raw = np.frombuffer(self._mmaps[fn], dtype=np.uint16, count=n, offset=base + start)
        return _bf16_to_f32(raw) if meta["dtype"] == "BF16" else raw.view(np.float16).astype(np.float32)

    def rows(self, name, i0, i1):
        """行スライスを float32 で返す (2次元テンソル)。"""
        fn = self._shard(name)
        hdr, base = self._headers[fn]
        meta = hdr[name]
        dtype, shape = meta["dtype"], meta["shape"]
        rows, cols = shape
        start, _ = meta["data_offsets"]
        itemsize = 2
        off = base + start + i0 * cols * itemsize
        cnt = (i1 - i0) * cols
        raw = np.frombuffer(self._mmaps[fn], dtype=np.uint16, count=cnt, offset=off)
        block = _bf16_to_f32(raw) if dtype == "BF16" else raw.view(np.float16).astype(np.float32)
        return block.reshape(i1 - i0, cols)

    def find(self, *needles):
        for k in self.weight_map:
            kl = k.lower()
            if all(n in kl for n in needles) and "visual" not in kl:
                return k
        return None


class JGenSource:
    """JGEN v3 の embed / lm_head 生行列を読む。"""

    def __init__(self, jgen_path):
        self.path = jgen_path
        self.offsets = {}
        with open(jgen_path, "rb") as f:
            assert f.read(4) == b"JGEN", "not a JGEN file"
            _v, count = struct.unpack("<II", f.read(8))
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
                    low = name.lower()
                    if "embed" in low:
                        self.offsets.setdefault("embed", (f.tell(), rows, cols))
                    elif "lm_head" in low or "output_layer" in low:
                        self.offsets.setdefault("lm_head", (f.tell(), rows, cols))
                elif t == 3:
                    (length,) = struct.unpack("<I", f.read(4))
                    nbytes = length * 2
                else:
                    break
                f.seek(nbytes, 1)
        self._mm = np.memmap(jgen_path, dtype=np.uint8, mode="r")

    def info(self, key):
        _, rows, cols = self.offsets[key]
        return "F16", [rows, cols]

    def rows(self, key, i0, i1):
        off, rows, cols = self.offsets[key]
        raw = np.frombuffer(self._mm, dtype=np.float16,
                            count=(i1 - i0) * cols, offset=off + i0 * cols * 2)
        return raw.astype(np.float32).reshape(i1 - i0, cols)

    def find(self, *needles):
        if "embed" in needles:
            return "embed" if "embed" in self.offsets else None
        return "lm_head" if "lm_head" in self.offsets else None


# ── 静的辞書本体 ──────────────────────────────────────────────────────────────
CHUNK = 16384


class GGUFVocabTokenizer:
    """GGUFの語彙表 (tokenizer.ggml.tokens) だけで動く最小トークナイザ。
    HFトークナイザが見つからないモデルの辞書検索用フォールバック。
    単語→ID は語彙表の完全一致 (▁/Ġ プレフィックス考慮) のみをサポートする。"""

    def __init__(self, vocab_json):
        with open(vocab_json) as f:
            self.pieces = json.load(f)
        self.lookup = {}
        for i, p in enumerate(self.pieces):
            self.lookup.setdefault(p, i)

    def encode(self, text, add_special_tokens=False):
        for cand in (text, "▁" + text.lstrip(), "Ġ" + text.lstrip(),
                     text.replace(" ", "▁"), text.replace(" ", "Ġ")):
            if cand in self.lookup:
                return [self.lookup[cand]]
        # 部分一致は不可能なので、単語ごとに引けるだけ引く
        ids = []
        for wpart in text.split():
            for cand in (wpart, "▁" + wpart, "Ġ" + wpart):
                if cand in self.lookup:
                    ids.append(self.lookup[cand])
                    break
        return ids

    def decode(self, ids):
        return "".join(self.pieces[i] for i in ids if 0 <= i < len(self.pieces)) \
            .replace("▁", " ").replace("Ġ", " ")


class WeightLexicon:
    def __init__(self, path, tokenizer_path, name="lexicon"):
        self.name = name
        self.path = path
        if tokenizer_path and tokenizer_path.endswith(".vocab.json"):
            self.tok = GGUFVocabTokenizer(tokenizer_path)
        elif tokenizer_path:
            from transformers import AutoTokenizer
            self.tok = AutoTokenizer.from_pretrained(tokenizer_path)
        elif os.path.exists(path + ".vocab.json"):
            self.tok = GGUFVocabTokenizer(path + ".vocab.json")
        else:
            raise ValueError(f"トークナイザが指定されておらず {path}.vocab.json もありません")
        if os.path.isdir(path):
            self.src = SafetensorsSource(path)
            self.embed_key = self.src.find("embed_tokens")
            self.lm_head_key = self.src.find("lm_head") or self.embed_key
        else:
            self.src = JGenSource(path)
            self.embed_key = "embed"
            self.lm_head_key = "lm_head" if "lm_head" in self.src.offsets else "embed"
        if self.embed_key is None:
            raise ValueError("embed_tokens が見つかりません")
        _, (self.vocab, self.hidden) = self.src.info(self.embed_key)
        self._norms = None
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        self._norms_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".verantyx_chrono",
            f"lexnorms_{safe}.npy")

    # ── ノルムキャッシュ (初回のみ全行スキャン) ──
    def _row_norms(self):
        if self._norms is not None:
            return self._norms
        if os.path.exists(self._norms_path):
            self._norms = np.load(self._norms_path, mmap_mode="r")
            return self._norms
        print(f"  [Lexicon] 初回: {self.vocab:,} 行のノルムをスキャン中 (発火なし、read only)...")
        norms = np.empty(self.vocab, dtype=np.float32)
        for i in range(0, self.vocab, CHUNK):
            j = min(i + CHUNK, self.vocab)
            norms[i:j] = np.linalg.norm(self.src.rows(self.embed_key, i, j), axis=1)
        os.makedirs(os.path.dirname(self._norms_path), exist_ok=True)
        np.save(self._norms_path, norms)
        self._norms = norms
        return norms

    def _word_vec(self, word):
        for cand in (word, " " + word):
            ids = self.tok.encode(cand, add_special_tokens=False)
            if len(ids) == 1:
                return self.src.rows(self.embed_key, ids[0], ids[0] + 1)[0], ids
        ids = self.tok.encode(word, add_special_tokens=False)
        if not ids:
            return None, []
        rows = np.stack([self.src.rows(self.embed_key, i, i + 1)[0] for i in ids])
        return rows.mean(axis=0), ids

    def _nearest_embed(self, q, k=12, exclude=()):
        qn = q / (np.linalg.norm(q) + 1e-8)
        norms = self._row_norms()
        best_s = np.full(k * 4, -1.0, dtype=np.float32)
        best_i = np.zeros(k * 4, dtype=np.int64)
        for i in range(0, self.vocab, CHUNK):
            j = min(i + CHUNK, self.vocab)
            sims = (self.src.rows(self.embed_key, i, j) @ qn) / (norms[i:j] + 1e-8)
            top = np.argpartition(sims, -min(k * 2, len(sims) - 1))[-k * 2:]
            cand_s = np.concatenate([best_s, sims[top]])
            cand_i = np.concatenate([best_i, top + i])
            order = np.argsort(cand_s)[::-1][:k * 4]
            best_s, best_i = cand_s[order], cand_i[order]
        return self._decode_hits(best_s, best_i, k, exclude)

    def _decode_hits(self, scores, ids, k, exclude=()):
        out, seen = [], set(exclude)
        for s, i in zip(scores, ids):
            txt = self.tok.decode([int(i)]).strip()
            key = txt.lower()
            if not txt or key in seen or not any(c.isalnum() or ord(c) > 0x2E80 for c in txt):
                continue
            seen.add(key)
            out.append((txt, float(s)))
            if len(out) >= k:
                break
        return out

    # ── レベル1: 連想 (埋め込み層) ──
    def associate(self, word, k=12):
        q, _ = self._word_vec(word)
        if q is None:
            return []
        return self._nearest_embed(q, k=k, exclude={word.lower()})

    # ── レベル2: 類推 (埋め込み層) ──
    def analogy(self, a, b, c, k=8):
        va, _ = self._word_vec(a)
        vb, _ = self._word_vec(b)
        vc, _ = self._word_vec(c)
        if va is None or vb is None or vc is None:
            return []
        return self._nearest_embed(vb - va + vc, k=k,
                                   exclude={a.lower(), b.lower(), c.lower()})

    # ── レベル3: MLP 知識探索 (発火なし・key-value読み出し) ──
    def probe(self, word, layers=None, topk_keys=32, k=12):
        """MLP 層を key-value 連想記憶として読む (safetensors のみ)。
        score_i = silu(gate_i·x) * (up_i·x) で強く反応する key を探し、
        対応する value (down_proj列) の合成を lm_head で語に翻訳する。
        行列積は行うがフォワードパス (活性の伝播) はしない。"""
        if not isinstance(self.src, SafetensorsSource):
            return [("(probe は safetensors 辞書のみ対応)", 0.0)]
        x0, _ = self._word_vec(word)
        if x0 is None:
            return []

        # 層プレフィクスを推定
        probe_layer = self.src.find("layers.0.", "mlp.up_proj")
        if probe_layer is None:
            return [("(MLP重みが見つかりません)", 0.0)]
        prefix = probe_layer.split("layers.0.")[0]
        # 文脈なしの生埋め込みは浅い層の残差にしか似ていないため、浅層を読む
        if layers is None:
            layers = [0, 1, 2]

        acc = np.zeros(self.hidden, dtype=np.float32)
        for L in layers:
            up_k = f"{prefix}layers.{L}.mlp.up_proj.weight"
            gate_k = f"{prefix}layers.{L}.mlp.gate_proj.weight"
            down_k = f"{prefix}layers.{L}.mlp.down_proj.weight"
            ln_k = f"{prefix}layers.{L}.post_attention_layernorm.weight"
            if up_k not in self.src.weight_map:
                continue
            # RMSNorm を実際の gamma 重みつきで適用 (MLP の本物の入力に近づける)
            x = x0 / (np.sqrt((x0 ** 2).mean()) + 1e-8)
            if ln_k in self.src.weight_map:
                x = x * self.src.vec(ln_k)
            _, (inter, _) = self.src.info(up_k)
            scores = np.empty(inter, dtype=np.float32)
            for i in range(0, inter, CHUNK):
                j = min(i + CHUNK, inter)
                u = self.src.rows(up_k, i, j) @ x
                g = self.src.rows(gate_k, i, j) @ x
                scores[i:j] = (g / (1 + np.exp(-np.clip(g, -30, 30)))) * u  # silu(g)*u
            top = np.argpartition(np.abs(scores), -topk_keys)[-topk_keys:]
            # down_proj は [hidden, inter] — 列の取り出しは行チャンクで gather
            w = scores[top]
            for i in range(0, self.hidden, CHUNK):
                j = min(i + CHUNK, self.hidden)
                acc[i:j] += self.src.rows(down_k, i, j)[:, top] @ w

        # lm_head で語彙に翻訳
        _, (v_rows, _) = self.src.info(self.lm_head_key)
        best_s = np.full(k * 4, -np.inf, dtype=np.float32)
        best_i = np.zeros(k * 4, dtype=np.int64)
        for i in range(0, v_rows, CHUNK):
            j = min(i + CHUNK, v_rows)
            logits = self.src.rows(self.lm_head_key, i, j) @ acc
            top = np.argpartition(logits, -min(k * 2, len(logits) - 1))[-k * 2:]
            cand_s = np.concatenate([best_s, logits[top]])
            cand_i = np.concatenate([best_i, top + i])
            order = np.argsort(cand_s)[::-1][:k * 4]
            best_s, best_i = cand_s[order], cand_i[order]
        return self._decode_hits(best_s, best_i, k, exclude={word.lower()})


def default_lexicon():
    """静的辞書のソースを開く。verantyx.config.json の models.lexicon で固定でき、
    'auto' なら model_scout の自律評価 (最大の対応モデル) を使う。"""
    from model_scout import best_lexicon_source, scan
    try:
        import verantyx_config
        pref = verantyx_config.get("models.lexicon", "auto")
    except Exception:
        pref = "auto"
    if pref == "none":
        raise RuntimeError("設定で辞書が無効化されています (models.lexicon = 'none')")
    if pref and pref != "auto":
        # 名前かパスでスキャン結果から固定選択
        for a in scan():
            if "lexicon" in a["roles"] and a["tokenizer"] and \
                    (a["name"] == pref or a["path"] == pref):
                return WeightLexicon(a["path"], a["tokenizer"], name=a["name"])
        print(f"  [Config] lexicon '{pref}' が見つかりません。auto にフォールバック")
    src = best_lexicon_source()
    if src is None:
        raise RuntimeError("辞書に使えるモデルがありません")
    return WeightLexicon(src["path"], src["tokenizer"], name=src["name"])


if __name__ == "__main__":
    import sys
    lex = default_lexicon()
    print(f"[Lexicon] {lex.name}: vocab={lex.vocab:,} hidden={lex.hidden} "
          f"({'safetensors' if isinstance(lex.src, SafetensorsSource) else 'jgen'} mmap, 発火なし)")
    word = sys.argv[1] if len(sys.argv) > 1 else "Tokyo"
    print("── associate (埋め込み層) ──")
    for t, s in lex.associate(word):
        print(f"  {word} ~ {t}  ({s:.3f})")
    print("── probe (MLP知識層・実験的) ──")
    print("  注意: 文脈なしの生埋め込みでは MLP キーが十分に整合しないため、")
    print("  現状はノイズが多い。本体知識の正確な検索には発火 (attention) が必要。")
    for t, s in lex.probe(word):
        print(f"  {word} -> {t}  ({s:.1f})")
