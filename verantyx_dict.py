"""
verantyx_dict.py — 静的辞書モード (大型モデルの重みを発火させずに知識を引く)
==============================================================================
開発記の「モデル重みを静的辞書にして検索し、大型モデルを発火させずに知識を出す」
の実装。Transformer 層を一切通さず、埋め込み行列 / lm_head 行列だけを
メモリマップして「連想辞書」として使う。

原理:
  埋め込み行列 E は各トークンを意味ベクトルへ写す静的な地図。
  E を発火 (フォワード) させずに、行ベクトル間の幾何だけを使えば:
    - 連想   : あるトークンに意味的に近いトークン群 (E 行の最近傍)
    - 類推   : king - man + woman ≒ queen (ベクトル演算)
    - 橋渡し : クエリ語の平均ベクトルに近い語 = 「関連知識の断片」
  これは RAG ではなく、モデルが学習で獲得した語彙幾何そのものの検索。
  22GB の 9B でも、読むのは埋め込み行列だけ (数百MB) で層は動かさない。

使い方:
  python3 verantyx_dict.py --model <jgen> assoc "gravity"
  python3 verantyx_dict.py --model <jgen> analogy king man woman
"""

import argparse
import json
import re
import struct

import numpy as np


class _DictBase:
    """埋め込み行列の幾何検索 (共通部)。self.E / self.vocab / self.hidden を派生が用意する。"""

    def _block(self, s0, s1):
        """埋め込み行列の [s0:s1] 行を float32 で返す (派生でdtype変換)。"""
        return np.asarray(self.E[s0:s1], dtype=np.float32)

    @property
    def mu(self):
        """語彙全体の平均埋め込み。埋め込み空間の異方性 (全トークンが共有する
        バイアス方向にレアトークンがハブ化する現象) を打ち消すために引く。"""
        if getattr(self, "_mu", None) is None:
            acc = np.zeros(self.hidden, dtype=np.float64)
            chunk = 16384
            for s0 in range(0, self.vocab, chunk):
                acc += self._block(s0, min(s0 + chunk, self.vocab)).sum(axis=0)
            self._mu = (acc / self.vocab).astype(np.float32)
        return self._mu

    def _row(self, tid):
        return self._block(tid, tid + 1)[0]

    def _vec(self, text):
        ids = self.tok.encode(text, add_special_tokens=False)
        if not ids:
            return None
        return np.mean([self._row(i) for i in ids], axis=0)

    def _nearest(self, v, k=10, exclude=()):
        """埋め込み行列全体に対する最近傍 (層を通さない純粋な幾何検索)。
        大語彙モデルでも RAM を食わないよう memmap をチャンクで流す。
        平均埋め込み mu を引いて異方性ハブを除去した空間で比較する。"""
        mu = self.mu
        v = v.astype(np.float32) - mu
        sims = np.empty(self.vocab, dtype=np.float32)
        chunk = 16384
        for s0 in range(0, self.vocab, chunk):
            blk = self._block(s0, min(s0 + chunk, self.vocab)) - mu
            n = np.linalg.norm(blk, axis=1) + 1e-8
            sims[s0:s0 + blk.shape[0]] = (blk @ v) / n
        sims /= (np.linalg.norm(v) + 1e-8)
        order = np.argsort(sims)[::-1]
        out = []
        for i in order[:2000]:
            s = self.tok.decode([int(i)]).strip()
            if not s or (s.startswith("<") and s.endswith(">")):
                continue
            if not any(c.isalnum() or ord(c) > 0x2E80 for c in s):
                continue
            if s.lower() in exclude:
                continue
            out.append((s, float(sims[i])))
            if len(out) >= k:
                break
        return out

    def associate(self, word, k=10):
        """語に意味的に近い語群を、モデルを発火させずに返す。"""
        v = self._vec(word)
        if v is None:
            return []
        return self._nearest(v, k=k, exclude={word.lower()})

    def analogy(self, a, b, c, k=8):
        """a : b :: c : ? を埋め込み演算で解く (a - b + c)。"""
        va, vb, vc = self._vec(a), self._vec(b), self._vec(c)
        if va is None or vb is None or vc is None:
            return []
        return self._nearest(va - vb + vc, k=k, exclude={a.lower(), b.lower(), c.lower()})

    def knowledge(self, query, k=12):
        """クエリ文の平均ベクトルに近い語 = モデルが結び付けている関連知識の断片。"""
        v = self._vec(query)
        if v is None:
            return []
        return self._nearest(v, k=k)


class StaticDictionary(_DictBase):
    """jgen の embed_tokens を層を発火させずに連想辞書として使う。"""

    def __init__(self, jgen_path, tokenizer):
        self.tok = tokenizer
        self._offsets = {}
        with open(jgen_path, "rb") as f:
            assert f.read(4) == b"JGEN", "not a JGEN file"
            _, count = struct.unpack("<II", f.read(8))
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
                    if ("embed" in name or "lm_head" in name):
                        key = "embed" if "embed" in name else "lm_head"
                        self._offsets.setdefault(key, (f.tell(), rows, cols))
                elif t == 3:
                    (length,) = struct.unpack("<I", f.read(4))
                    nbytes = length * 2
                else:
                    break
                f.seek(nbytes, 1)
        off, rows, cols = self._offsets["embed"]
        self.E = np.memmap(jgen_path, dtype=np.float16, mode="r",
                           offset=off, shape=(rows, cols))
        self.vocab, self.hidden = rows, cols


class SafetensorsDictionary(_DictBase):
    """HF safetensors の embed_tokens を、モデルをロードも発火もせずに mmap で開く。
    22GB の 9B でも読むのは埋め込み行列の該当領域だけ (bf16 対応)。"""

    EMBED_NAMES = ("model.embed_tokens.weight", "embed_tokens.weight",
                   "model.language_model.embed_tokens.weight",
                   "transformer.wte.weight")

    def __init__(self, model_dir, tokenizer):
        import glob
        import os
        self.tok = tokenizer
        found = None
        for st in sorted(glob.glob(os.path.join(model_dir, "*.safetensors"))):
            with open(st, "rb") as f:
                (hlen,) = struct.unpack("<Q", f.read(8))
                header = json.loads(f.read(hlen))
            for name in self.EMBED_NAMES:
                if name in header:
                    info = header[name]
                    found = (st, 8 + hlen + info["data_offsets"][0],
                             info["shape"], info["dtype"])
                    break
            if found:
                break
        if not found:
            raise RuntimeError(f"embed_tokens が {model_dir} に見つかりません")
        path, off, shape, dtype = found
        self.dtype = dtype
        self.vocab, self.hidden = shape
        # bf16 は numpy 非対応なので uint16 として mmap し、変換は _block で行う
        np_dtype = np.float16 if dtype == "F16" else np.uint16
        self.E = np.memmap(path, dtype=np_dtype, mode="r", offset=off, shape=tuple(shape))
        print(f"[StaticDict] {os.path.basename(path)} embed {shape} {dtype} を mmap "
              f"(モデル本体はロードしません)")

    def _block(self, s0, s1):
        blk = self.E[s0:s1]
        if self.dtype == "BF16":
            # bf16 -> f32: 上位16bitへシフトして float32 として解釈
            u32 = blk.astype(np.uint32) << 16
            return u32.view(np.float32).reshape(blk.shape)
        return np.asarray(blk, dtype=np.float32)


def open_dictionary(model_path, tokenizer):
    """jgen ファイルか HF ディレクトリを自動判別して辞書を開く。"""
    import os
    if os.path.isdir(model_path):
        return SafetensorsDictionary(model_path, tokenizer)
    return StaticDictionary(model_path, tokenizer)


def main():
    from transformers import AutoTokenizer
    from verantyx_mind import DEFAULT_MODEL, TOKENIZER
    ap = argparse.ArgumentParser(description="静的辞書モード (層を発火させない知識検索)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="jgen ファイルまたは HF ディレクトリ")
    ap.add_argument("--tokenizer", default=TOKENIZER)
    ap.add_argument("cmd", choices=["assoc", "analogy", "knowledge", "repl"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    d = open_dictionary(a.model, tok)
    print(f"[StaticDict] vocab={d.vocab} hidden={d.hidden} (層は一切発火しません)")

    def show(pairs):
        for s, sim in pairs:
            print(f"  {sim:.3f}  {s}")

    if a.cmd == "assoc":
        show(d.associate(a.args[0]))
    elif a.cmd == "knowledge":
        show(d.knowledge(" ".join(a.args)))
    elif a.cmd == "analogy":
        assert len(a.args) == 3, "analogy A B C"
        print(f"  {a.args[0]} - {a.args[1]} + {a.args[2]} =")
        show(d.analogy(*a.args))
    elif a.cmd == "repl":
        print("辞書REPL: <語> で連想 / 'A - B + C' で類推 / exit で終了")
        while True:
            try:
                q = input("\n📖 dict> ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not q or q.lower() in ("exit", "quit", "q"):
                break
            m = re.match(r"^(\S+)\s*-\s*(\S+)\s*\+\s*(\S+)$", q)
            if m:
                show(d.analogy(m.group(1), m.group(2), m.group(3)))
            elif " " in q:
                show(d.knowledge(q))
            else:
                show(d.associate(q))


if __name__ == "__main__":
    main()
