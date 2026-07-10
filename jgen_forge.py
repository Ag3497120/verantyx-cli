"""
jgen_forge.py — モデル変換基盤 (HF/GGUF → JGEN v3) + モデルレジストリ
=======================================================================

「モデルを格納すると変換する計算が走って即座に使える」を実現する基盤。

  - HuggingFace形式 (safetensors ディレクトリ) → full.jgen (SVD lossless / --dense)
  - GGUF → full.jgen (gguf パッケージがあれば全量子化タイプ対応: Q4_K/Q5_K/Q6_K...)
  - LM Studio / Ollama の隠しフォルダを自動発見して直接変換 (sources / pull)
  - MoE 対応: スタック型エキスパートテンソル (ffn_*_exps) をエキスパート単位に
    分割し、Rustエンジンの MoE forward が読む命名で書き出す
  - SSMハイブリッド (qwen35moe 等) はテンソルを保存しつつ arch_unsupported とし、
    --parts lexicon で embed/lm_head のみの静的辞書用 jgen も作れる
  - config.json / GGUFメタデータから .meta.json サイドカーを自動生成
    (Rustエンジンがこれを読んで heads/kv/rope/eos/MoE設定を正確に反映する)
  - 巨大モデルはテンソル1枚ずつのストリーミング変換 (RAMに全体を載せない)
  - モデルレジストリ (.verantyx_chrono/model_registry.json):
    マシンスペックに応じたワーカー自動選択 API を提供
  - dropzone スキャン: models_dropzone/ に置かれた未変換モデルを自動変換

使い方:
  python3 jgen_forge.py add <HFディレクトリ|GGUFファイル> [--name NAME] [--dense]
                            [--tokenizer DIR] [--parts full|lexicon]
  python3 jgen_forge.py sources                                # LM Studio/Ollama のモデル一覧
  python3 jgen_forge.py pull <名前の一部> [--parts lexicon]     # 隠しフォルダから変換
  python3 jgen_forge.py register <既存jgen> --tokenizer DIR    # 変換済みjgenの登録
  python3 jgen_forge.py scan                                   # dropzone自動変換
  python3 jgen_forge.py list                                   # レジストリ表示
  python3 jgen_forge.py align <worker名>                       # 異次元空間の整列行列を学習
"""

import argparse
import glob
import json
import os
import struct
import subprocess
import sys
import time

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
CHRONO = os.path.join(BASE, ".verantyx_chrono")
REGISTRY_PATH = os.path.join(CHRONO, "model_registry.json")
DROPZONE = os.path.join(BASE, "models_dropzone")
JGEN_DIR = os.path.join(BASE, "converted_models")

STANDARD_ARCHS = {
    "Qwen2ForCausalLM", "Qwen1ForCausalLM", "LlamaForCausalLM",
    "MistralForCausalLM", "Gemma2ForCausalLM", "GemmaForCausalLM",
}


# ── レジストリ ─────────────────────────────────────────────────────────────────
def load_registry():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {"models": []}


def save_registry(reg):
    os.makedirs(CHRONO, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def register_model(name, jgen_path, meta, status="ready"):
    reg = load_registry()
    reg["models"] = [m for m in reg["models"] if m["name"] != name]
    reg["models"].append({
        "name": name,
        "jgen": os.path.abspath(jgen_path),
        "size_bytes": os.path.getsize(jgen_path) if os.path.exists(jgen_path) else 0,
        "hidden": meta.get("hidden"),
        "num_layers": meta.get("num_layers"),
        "vocab": meta.get("vocab"),
        "arch": meta.get("arch", "unknown"),
        "tokenizer": meta.get("tokenizer"),
        "status": status,
        "added": time.time(),
    })
    save_registry(reg)
    print(f"[Forge] レジストリに登録: {name} ({status})")


def total_ram_bytes():
    try:
        return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
    except Exception:
        try:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except Exception:
            return 16 * (1 << 30)


def select_worker(exclude=(), require_standard=True):
    """マシンスペック (RAM) に収まる最大のワーカーを選ぶ。
    verantyx.config.json の escalation.ram_fraction で割合を調整できる。"""
    try:
        import verantyx_config
        frac = float(verantyx_config.get("escalation.ram_fraction", 0.45))
    except Exception:
        frac = 0.45
    budget = int(total_ram_bytes() * frac)  # mmap + f32キャッシュの余裕
    reg = load_registry()
    ready = [m for m in reg["models"]
             if m["status"] == "ready" and m["name"] not in exclude
             and (not require_standard or m["arch"] in ("standard", "moe_standard"))
             and m["size_bytes"] <= budget]
    if not ready:
        return None
    return max(ready, key=lambda m: m["size_bytes"])


# ── JGEN v3 ライタ ─────────────────────────────────────────────────────────────
class JGenWriter:
    def __init__(self, path, total_tensors=0):
        """total_tensors=0 で開始した場合はストリーミングモード:
        書いた枚数を数えて close() 時にヘッダへ書き戻す。"""
        self.f = open(path, "wb")
        self.f.write(b"JGEN")
        self.f.write(struct.pack("<II", 3, total_tensors))
        self._streaming = total_tensors == 0
        self._count = 0

    def _header(self, name, t_type):
        nb = name.encode()
        self.f.write(struct.pack("<H", len(nb)))
        self.f.write(nb)
        self.f.write(struct.pack("<B", t_type))
        self._count += 1

    def dense2d(self, name, W):  # (rows, cols) f16
        self._header(name, 2)
        self.f.write(struct.pack("<II", W.shape[0], W.shape[1]))
        self.f.write(np.ascontiguousarray(W, dtype=np.float16).tobytes())

    def dense1d(self, name, v):
        self._header(name, 3)
        self.f.write(struct.pack("<I", v.shape[0]))
        self.f.write(np.ascontiguousarray(v, dtype=np.float16).tobytes())

    def svd_lossless(self, name, W):  # フルランクSVD + 中立変調器 (立体十字構造体)
        rows, cols = W.shape
        rank = min(rows, cols)
        U, S, Vh = np.linalg.svd(W.astype(np.float32), full_matrices=False)
        self._header(name, 1)
        self.f.write(struct.pack("<III", rows, cols, rank))
        self.f.write(U.astype(np.float16).tobytes())
        self.f.write(S.astype(np.float16).tobytes())
        self.f.write(np.ascontiguousarray(Vh.T, dtype=np.float16).tobytes())
        self.f.write(np.ones(cols, dtype=np.float16).tobytes())    # mod_x
        self.f.write(np.zeros(rows, dtype=np.float16).tobytes())   # mod_y
        self.f.write(np.eye(rank, dtype=np.float16).tobytes())     # C_valve
        del U, S, Vh

    def close(self):
        if self._streaming:
            self.f.seek(8)
            self.f.write(struct.pack("<I", self._count))
        self.f.close()


LINEAR_SUFFIXES = (".q_proj.weight", ".k_proj.weight", ".v_proj.weight", ".o_proj.weight",
                   ".gate_proj.weight", ".up_proj.weight", ".down_proj.weight")
BIAS_SUFFIXES = (".q_proj.bias", ".k_proj.bias", ".v_proj.bias", ".o_proj.bias")


def write_jgen(tensors, out_path, dense=False):
    """tensors: dict name -> np.ndarray (f16/f32)。HF命名を前提にJGEN v3へ書く。"""
    embed_key = next((k for k in tensors if "embed_tokens" in k), None)
    lm_key = next((k for k in tensors if k.startswith("lm_head")), None)
    norm_keys = [k for k in tensors if "norm" in k and k.endswith(".weight")]
    linear_keys = sorted(k for k in tensors if k.endswith(LINEAR_SUFFIXES) and ".layers." in k)
    bias_keys = sorted(k for k in tensors if k.endswith(BIAS_SUFFIXES) and ".layers." in k)
    assert embed_key, "embed_tokens が見つかりません"

    total = 2 + len(norm_keys) + len(linear_keys) + len(bias_keys)
    w = JGenWriter(out_path, total)
    print(f"[Forge] 書き込み: {total} tensors -> {out_path}")
    w.dense2d("embed_tokens", tensors[embed_key])
    # tied embeddings 対応: lm_head が無ければ embed を複製
    w.dense2d("lm_head", tensors[lm_key] if lm_key else tensors[embed_key])
    for k in norm_keys:
        w.dense1d(k, tensors[k])
    for k in bias_keys:
        w.dense1d(k, tensors[k])
    mode = "Dense2D (高速)" if dense else "SVD lossless (立体十字)"
    print(f"[Forge] 線形層 {len(linear_keys)} 枚を {mode} で変換中...")
    for i, k in enumerate(linear_keys):
        if dense:
            w.dense2d(k, tensors[k])
        else:
            w.svd_lossless(k, tensors[k])
        if (i + 1) % 20 == 0 or i + 1 == len(linear_keys):
            print(f"  [{i+1}/{len(linear_keys)}] {k}")
    w.close()


# ── HuggingFace形式の取り込み ──────────────────────────────────────────────────
def load_hf_dir(model_dir):
    # bfloat16はnumpy未対応のためtorch経由で読む
    import torch
    from safetensors import safe_open
    files = glob.glob(os.path.join(model_dir, "*.safetensors"))
    assert files, f"safetensors が見つかりません: {model_dir}"
    tensors = {}
    for st in files:
        with safe_open(st, framework="pt", device="cpu") as f:
            for k in f.keys():
                tensors[k] = f.get_tensor(k).to(torch.float16).numpy()
    return tensors


def hf_meta(model_dir, tensors):
    with open(os.path.join(model_dir, "config.json")) as f:
        cfg = json.load(f)
    hidden = cfg["hidden_size"]
    heads = cfg["num_attention_heads"]
    arch_name = (cfg.get("architectures") or ["unknown"])[0]
    eos = cfg.get("eos_token_id", 151643)
    eos = eos if isinstance(eos, list) else [eos]
    if "qwen" in arch_name.lower():
        eos = sorted(set(eos) | {151643, 151645})  # <|endoftext|> / <|im_end|>
    arch = "standard" if arch_name in STANDARD_ARCHS else "unknown"
    if any("linear_attn" in k for k in tensors):
        arch = "linear_attn"
    return {
        "num_heads": heads,
        "num_kv_heads": cfg.get("num_key_value_heads", heads),
        "head_dim": cfg.get("head_dim", hidden // heads),
        "rope_theta": float(cfg.get("rope_theta", 10000.0)),
        "rope_neox": True,
        "eos_tokens": eos,
        "hidden": hidden,
        "num_layers": cfg["num_hidden_layers"],
        "vocab": cfg["vocab_size"],
        "arch": arch,
        "hf_arch": arch_name,
        "tokenizer": os.path.abspath(model_dir),
    }


# ── GGUF の取り込み (gguf パッケージで全量子化タイプ対応 / ストリーミング) ────────
GGUF_NAME_MAP = [
    ("token_embd.weight", "model.embed_tokens.weight"),
    ("output.weight", "lm_head.weight"),
    ("output_norm.weight", "model.norm.weight"),
]
GGUF_BLK_MAP = {
    # 標準トランスフォーマー
    "attn_norm.weight": "input_layernorm.weight",
    "ffn_norm.weight": "post_attention_layernorm.weight",
    "post_attention_norm.weight": "post_attention_layernorm.weight",
    "attn_q.weight": "self_attn.q_proj.weight",
    "attn_k.weight": "self_attn.k_proj.weight",
    "attn_v.weight": "self_attn.v_proj.weight",
    "attn_output.weight": "self_attn.o_proj.weight",
    "attn_q.bias": "self_attn.q_proj.bias",
    "attn_k.bias": "self_attn.k_proj.bias",
    "attn_v.bias": "self_attn.v_proj.bias",
    "attn_qkv.weight": "self_attn.query_key_value.weight",
    "attn_qkv.bias": "self_attn.query_key_value.bias",
    "ffn_gate.weight": "mlp.gate_proj.weight",
    "ffn_up.weight": "mlp.up_proj.weight",
    "ffn_down.weight": "mlp.down_proj.weight",
    # QK-norm (Qwen3系 / Gemma3系)
    "attn_q_norm.weight": "self_attn.q_norm.weight",
    "attn_k_norm.weight": "self_attn.k_norm.weight",
    # アテンションゲート (qwen3.5ハイブリッド)
    "attn_gate.weight": "self_attn.gate.weight",
    # Gemma系の追加ノルム
    "attn_post_norm.weight": "post_self_attn_layernorm.weight",
    "ffn_pre_norm.weight": "pre_feedforward_layernorm.weight",
    "ffn_post_norm.weight": "post_feedforward_layernorm.weight",
    # MoE ルーター / 共有エキスパート
    "ffn_gate_inp.weight": "mlp.gate.weight",
    "exp_probs_b.bias": "mlp.gate.e_score_correction_bias",
    "ffn_gate_inp_shexp.weight": "mlp.shared_expert_gate.weight",
    "ffn_gate_shexp.weight": "mlp.shared_experts.gate_proj.weight",
    "ffn_up_shexp.weight": "mlp.shared_experts.up_proj.weight",
    "ffn_down_shexp.weight": "mlp.shared_experts.down_proj.weight",
    # SSM / 線形アテンション (qwen3.5 / mamba系ハイブリッド)
    "ssm_norm.weight": "linear_attn.norm.weight",
    "ssm_alpha.weight": "linear_attn.alpha.weight",
    "ssm_beta.weight": "linear_attn.beta.weight",
    "ssm_conv1d.weight": "linear_attn.conv1d.weight",
    "ssm_conv1d.bias": "linear_attn.conv1d.bias",
    "ssm_dt.bias": "linear_attn.dt.bias",
    "ssm_a": "linear_attn.a",
    "ssm_d": "linear_attn.d",
    "ssm_out.weight": "linear_attn.out_proj.weight",
    "ssm_in.weight": "linear_attn.in_proj.weight",
    "ssm_x.weight": "linear_attn.x_proj.weight",
    "ssm_dt.weight": "linear_attn.dt_proj.weight",
}
# スタック型エキスパート (3D) → エキスパート単位に分割する対象
GGUF_EXPS_MAP = {
    "ffn_gate_exps.weight": "gate_proj",
    "ffn_up_exps.weight": "up_proj",
    "ffn_down_exps.weight": "down_proj",
}

# エンジンが直接推論できるGGUFアーキテクチャ
GGUF_RUNNABLE = {"llama", "qwen1", "qwen2", "qwen3", "mistral", "gemma2"}
# MoEだが注意機構は標準 (meta駆動のMoE設定で推論可能)
GGUF_RUNNABLE_MOE = {"qwen2moe", "qwen3moe"}


def _gguf_reader(path):
    try:
        from gguf import GGUFReader
        return GGUFReader(path)
    except ImportError:
        raise RuntimeError("gguf パッケージが必要です: pip install gguf")


def _gguf_field(reader, key, default=None):
    f = reader.fields.get(key)
    if f is None:
        return default
    try:
        v = f.contents()
        return v if v is not None else default
    except Exception:
        return default


def _gguf_dequant(tensor):
    """ReaderTensor -> f32 ndarray (正しい向き: HF (out, in) 互換)。"""
    from gguf.quants import dequantize
    return dequantize(tensor.data, tensor.tensor_type)


def gguf_to_hf_name(name):
    for src, dst in GGUF_NAME_MAP:
        if name == src:
            return dst
    if name.startswith("blk."):
        parts = name.split(".", 2)
        layer, rest = parts[1], parts[2]
        if rest in GGUF_BLK_MAP:
            return f"model.layers.{layer}.{GGUF_BLK_MAP[rest]}"
        if rest in GGUF_EXPS_MAP:
            return ("EXPS", layer, GGUF_EXPS_MAP[rest])
        # 未知のテンソルも捨てずに保存 (将来のエンジン対応で使える)
        return f"model.layers.{layer}.gguf.{rest}"
    if name.startswith(("mm.", "v.", "per_layer_", "altup", "vision")):
        return None  # 視覚タワー等はテキスト推論に不要
    return None


def _find_tokenizer_by_vocab(vocab, name_hint=""):
    """HFキャッシュから語彙サイズが一致するトークナイザを探す。
    複数一致した場合はモデル名の語の重なりが多いものを優先する。"""
    hub = os.path.expanduser("~/.cache/huggingface/hub")
    if not os.path.isdir(hub):
        return None
    import re as _re
    hint_words = set(_re.split(r"[^a-z0-9.]+", name_hint.lower())) - {""}
    best, best_score = None, -1
    for d in sorted(os.listdir(hub)):
        if not d.startswith("models--"):
            continue
        for snap in glob.glob(os.path.join(hub, d, "snapshots", "*")):
            cfg_p = os.path.join(snap, "config.json")
            tok_p = os.path.join(snap, "tokenizer.json")
            if not (os.path.exists(cfg_p) and os.path.exists(tok_p)):
                continue
            try:
                with open(cfg_p) as f:
                    cfg = json.load(f)
                v = cfg.get("vocab_size") or cfg.get("text_config", {}).get("vocab_size")
                if v != vocab:
                    continue
                repo_words = set(_re.split(r"[^a-z0-9.]+", d.replace("models--", "").lower())) - {""}
                score = len(hint_words & repo_words)
                if score > best_score:
                    best, best_score = snap, score
            except Exception:
                continue
    return best


def gguf_meta_from_reader(reader, tokenizer=None):
    arch = _gguf_field(reader, "general.architecture", "llama")
    g = lambda k, d=None: _gguf_field(reader, f"{arch}.{k}", d)
    hidden = int(g("embedding_length"))
    heads = int(g("attention.head_count") or 16)
    kv = g("attention.head_count_kv", heads)
    if isinstance(kv, list):  # gemma4等は層ごとのリスト
        kv = max(v for v in kv if v) if any(kv) else heads
    eos = _gguf_field(reader, "tokenizer.ggml.eos_token_id", 2)
    n_experts = g("expert_count", 0) or 0
    has_ssm = any(t.name.endswith("ssm_out.weight") or ".ssm_" in t.name
                  for t in reader.tensors[: min(len(reader.tensors), 80)])
    # アーキ分類 (エンジンで直接推論できるか)
    if arch in GGUF_RUNNABLE and not n_experts:
        support = "standard"
    elif arch in GGUF_RUNNABLE_MOE or (arch in GGUF_RUNNABLE and n_experts):
        support = "moe_standard"
    elif has_ssm or "35moe" in arch:
        support = "hybrid_ssm"
    else:
        support = "unknown"
    vocab = int(_gguf_field(reader, f"{arch}.vocab_size", 0) or 0)
    if not vocab:
        emb = next(t for t in reader.tensors if t.name == "token_embd.weight")
        vocab = int(max(emb.shape))
    head_dim = int(g("attention.key_length", 0) or (hidden // heads))
    meta = {
        "num_heads": heads,
        "num_kv_heads": int(kv),
        "head_dim": head_dim,
        "rope_theta": float(g("rope.freq_base", 10000.0)),
        "rope_neox": True,
        "eos_tokens": [int(eos)],
        "hidden": hidden,
        "num_layers": int(g("block_count")),
        "vocab": vocab,
        "arch": support,
        "hf_arch": f"gguf:{arch}",
        "tokenizer": tokenizer,
    }
    if n_experts:
        meta["num_experts"] = int(n_experts)
        meta["moe_top_k"] = int(g("expert_used_count", 8))
        # exp_probs_b (DeepSeek系) があれば sigmoid+bias、なければ softmax
        has_bias = any(t.name.endswith("exp_probs_b.bias")
                       for t in reader.tensors[: min(len(reader.tensors), 80)])
        meta["moe_score_func"] = "sigmoid" if has_bias else "softmax"
        meta["first_moe_layer"] = 0
    if not tokenizer:
        hint = " ".join(str(_gguf_field(reader, k, "") or "")
                        for k in ("general.name", "general.basename", "general.architecture"))
        hit = _find_tokenizer_by_vocab(meta["vocab"], name_hint=hint)
        if hit:
            meta["tokenizer"] = hit
            print(f"[Forge] 語彙サイズ {meta['vocab']} が一致するトークナイザを発見: {hit}")
    return meta


def convert_gguf_streaming(path, out_path, dense=False, parts="full"):
    """GGUF → JGEN v3 をテンソル1枚ずつストリーミング変換 (RAMに全体を載せない)。
    MoE のスタック型エキスパートはエキスパート単位に分割して書く。
    parts='lexicon' なら embed/lm_head/最終norm のみ (静的辞書・ベクトル語彙用)。"""
    reader = _gguf_reader(path)
    meta = gguf_meta_from_reader(reader)
    w = JGenWriter(out_path)  # ストリーミングモード
    n_done = 0
    lex_only = parts == "lexicon"
    lex_names = {"token_embd.weight", "output.weight", "output_norm.weight"}
    total = len(reader.tensors)
    have_lm_head = any(t.name == "output.weight" for t in reader.tensors)
    for t in reader.tensors:
        if lex_only and t.name not in lex_names:
            continue
        mapped = gguf_to_hf_name(t.name)
        if mapped is None:
            continue
        arr = _gguf_dequant(t).astype(np.float16)
        if isinstance(mapped, tuple):  # スタック型エキスパート (n_experts, out, in)
            _, layer, proj = mapped
            for e in range(arr.shape[0]):
                w.dense2d(f"model.layers.{layer}.mlp.experts.{e}.{proj}_proj.weight", arr[e])
            n_done += 1
            print(f"  [{n_done}/{total}] blk.{layer} {proj} x{arr.shape[0]} experts")
        else:
            if mapped == "model.embed_tokens.weight":
                w.dense2d("embed_tokens", arr)
                if not have_lm_head:  # tied embeddings
                    w.dense2d("lm_head", arr)
            elif mapped == "lm_head.weight":
                w.dense2d("lm_head", arr)
            elif arr.ndim == 1:
                w.dense1d(mapped, arr)
            elif arr.ndim == 2:
                if dense or not mapped.endswith(LINEAR_SUFFIXES):
                    w.dense2d(mapped, arr)
                else:
                    w.svd_lossless(mapped, arr)
            else:
                # 3D (conv1d等) は平坦化して dense2d で保存
                w.dense2d(mapped, arr.reshape(arr.shape[0], -1))
            n_done += 1
            if n_done % 25 == 0 or n_done == total:
                print(f"  [{n_done}/{total}] {mapped}")
        del arr
    w.close()
    if lex_only:
        meta["parts"] = "lexicon"
    # トークナイザが見つからないモデルでも辞書検索できるよう、GGUF内の
    # 語彙表をサイドカーに書き出す (weight_lexicon の GGUFVocabTokenizer が読む)
    if not meta.get("tokenizer"):
        toks = _gguf_field(reader, "tokenizer.ggml.tokens")
        if toks:
            with open(out_path + ".vocab.json", "w") as f:
                json.dump(toks, f, ensure_ascii=False)
            meta["vocab_sidecar"] = out_path + ".vocab.json"
            print(f"[Forge] トークナイザ未発見 → GGUF語彙表をサイドカーに保存 ({len(toks):,} tokens)")
    return meta


# ── 外部ソースの発見 (LM Studio / Ollama の隠しフォルダ) ─────────────────────────
def _is_gguf(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"GGUF"
    except OSError:
        return False


def discover_sources():
    """LM Studio / Ollama / HFキャッシュのモデルを列挙する。
    返り値: [{name, path, source, size_bytes}, ...]"""
    out = []
    # LM Studio: ~/.lmstudio/models/<org>/<repo>/*.gguf
    for root in (os.path.expanduser("~/.lmstudio/models"),
                 os.path.expanduser("~/.cache/lm-studio/models")):
        if os.path.isdir(root):
            for p in glob.glob(os.path.join(root, "**", "*.gguf"), recursive=True):
                out.append({"name": os.path.splitext(os.path.basename(p))[0].lower(),
                            "path": p, "source": "lmstudio",
                            "size_bytes": os.path.getsize(p)})
    # Ollama: manifests/<registry>/<ns>/<model>/<tag> -> blobs/sha256-...
    oroot = os.path.expanduser("~/.ollama/models")
    if os.path.isdir(oroot):
        for mf in glob.glob(os.path.join(oroot, "manifests", "**", "*"), recursive=True):
            if not os.path.isfile(mf):
                continue
            try:
                with open(mf) as f:
                    man = json.load(f)
                layer = next(l for l in man.get("layers", [])
                             if l.get("mediaType", "").endswith("image.model"))
                blob = os.path.join(oroot, "blobs", layer["digest"].replace(":", "-"))
                if not os.path.exists(blob) or not _is_gguf(blob):
                    continue
                parts = mf.split(os.sep)
                tag = f"{parts[-2]}:{parts[-1]}"  # model:tag
                out.append({"name": tag.lower(), "path": blob, "source": "ollama",
                            "size_bytes": layer.get("size", os.path.getsize(blob))})
            except (json.JSONDecodeError, StopIteration, KeyError, OSError):
                continue
    # HF キャッシュ: safetensors スナップショット
    hub = os.path.expanduser("~/.cache/huggingface/hub")
    if os.path.isdir(hub):
        for d in sorted(os.listdir(hub)):
            if not d.startswith("models--"):
                continue
            for snap in glob.glob(os.path.join(hub, d, "snapshots", "*")):
                sts = glob.glob(os.path.join(snap, "*.safetensors"))
                if sts:
                    name = d.replace("models--", "").replace("--", "/").lower()
                    out.append({"name": name, "path": snap, "source": "hf-cache",
                                "size_bytes": sum(os.path.getsize(s) for s in sts)})
                    break
    return out


def cmd_sources():
    reg = load_registry()
    converted = {m["name"] for m in reg["models"]}
    srcs = discover_sources()
    if not srcs:
        print("[Forge] LM Studio / Ollama / HFキャッシュにモデルが見つかりません")
        return srcs
    print(f"[Forge] 発見したモデル ({len(srcs)}件):")
    for s in sorted(srcs, key=lambda x: -x["size_bytes"]):
        mark = "✓変換済" if any(s["name"].replace(":", "_") in c or c in s["name"]
                              for c in converted) else ""
        print(f"  [{s['source']:8s}] {s['name']:44s} {s['size_bytes']/(1<<30):6.2f}GB {mark}")
    print("\n変換: python3 jgen_forge.py pull <名前の一部> [--dense] [--parts lexicon]")
    return srcs


def cmd_pull(query, name=None, dense=False, tokenizer=None, parts="full"):
    """発見済みソースから名前でモデルを選んで変換する。"""
    srcs = discover_sources()
    hits = [s for s in srcs if query.lower() in s["name"]]
    if not hits:
        print(f"[-] '{query}' に一致するモデルが見つかりません (jgen_forge.py sources で一覧)")
        return
    if len(hits) > 1:
        print(f"[!] 複数一致。最初の1件を使います: {[h['name'] for h in hits]}")
    src = hits[0]
    print(f"[Forge/pull] {src['source']} から変換: {src['name']} ({src['size_bytes']/(1<<30):.2f}GB)")
    auto_name = name
    if auto_name is None:
        auto_name = src["name"].replace(":", "_").replace("/", "_")
        if parts == "lexicon":
            auto_name += "_lexicon"
    cmd_add(src["path"], name=auto_name, dense=dense, tokenizer=tokenizer, parts=parts)


# ── コマンド ───────────────────────────────────────────────────────────────────
def cmd_add(src, name=None, dense=False, tokenizer=None, parts="full"):
    os.makedirs(JGEN_DIR, exist_ok=True)
    t0 = time.time()
    is_gguf_file = os.path.isfile(src) and _is_gguf(src)
    if os.path.isdir(src):
        print(f"[Forge] HuggingFace形式を検出: {src}")
        tensors = load_hf_dir(src)
        meta = hf_meta(src, tensors)
        if tokenizer:
            meta["tokenizer"] = os.path.abspath(tokenizer)
        name = name or os.path.basename(src.rstrip("/")).lower().replace(".", "_")
        out = os.path.join(JGEN_DIR, f"{name}_full.jgen")
        write_jgen(tensors, out, dense=dense)
    elif is_gguf_file:
        print(f"[Forge] GGUF形式を検出: {src}")
        name = name or os.path.splitext(os.path.basename(src))[0].lower()
        out = os.path.join(JGEN_DIR, f"{name}_full.jgen")
        meta = convert_gguf_streaming(src, out, dense=dense, parts=parts)
        if tokenizer:
            meta["tokenizer"] = os.path.abspath(tokenizer)
    else:
        print(f"[-] 未対応の入力: {src}")
        return

    # HFトークナイザが無い場合、GGUF語彙サイドカーを辞書用トークナイザとして使う
    if not meta.get("tokenizer") and meta.get("vocab_sidecar"):
        meta["tokenizer"] = meta["vocab_sidecar"]
    runnable = meta["arch"] in ("standard", "moe_standard")
    if not runnable and parts != "lexicon":
        print(f"[!] アーキテクチャ '{meta['hf_arch']}' はエンジンの直接推論が未対応 ({meta['arch']})。")
        print("    変換は完了します: 静的辞書 (WeightLexicon) とベクトル語彙としては利用可能。")
    with open(out + ".meta.json", "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    if parts == "lexicon":
        status = "lexicon"
    else:
        status = "ready" if runnable else "arch_unsupported"
    register_model(name, out, meta, status=status)
    print(f"[Forge] 完了 ({time.time()-t0:.0f}s): {out} ({os.path.getsize(out)/(1<<30):.2f}GB)")
    print(f"[Forge] meta: heads={meta['num_heads']} kv={meta['num_kv_heads']} head_dim={meta['head_dim']} "
          f"rope_theta={meta['rope_theta']} eos={meta['eos_tokens']}"
          + (f" experts={meta.get('num_experts')}x top{meta.get('moe_top_k')}"
             f" score={meta.get('moe_score_func')}" if meta.get("num_experts") else ""))


def cmd_register(jgen_path, name=None, tokenizer=None, arch="standard"):
    """変換済みjgen (qwen_0.5b_full.jgen 等) をレジストリに載せる。"""
    meta = {}
    mp = jgen_path + ".meta.json"
    if os.path.exists(mp):
        with open(mp) as f:
            meta = json.load(f)
    meta.setdefault("arch", arch)
    if tokenizer:
        meta["tokenizer"] = tokenizer
    name = name or os.path.splitext(os.path.basename(jgen_path))[0]
    status = "ready" if meta["arch"] == "standard" else "arch_unsupported"
    register_model(name, jgen_path, meta, status=status)


def cmd_scan():
    """dropzone に置かれた未変換モデルを検出して自動変換する。"""
    os.makedirs(DROPZONE, exist_ok=True)
    reg = load_registry()
    known = {m["name"] for m in reg["models"]}
    found = False
    for entry in sorted(os.listdir(DROPZONE)):
        p = os.path.join(DROPZONE, entry)
        name = os.path.splitext(entry)[0].lower().replace(".", "_")
        if name in known:
            continue
        if os.path.isdir(p) and glob.glob(os.path.join(p, "*.safetensors")):
            print(f"[Forge/scan] 新しいHFモデルを検出: {entry}")
            cmd_add(p, name=name)
            found = True
        elif entry.endswith(".gguf"):
            print(f"[Forge/scan] 新しいGGUFを検出: {entry}")
            cmd_add(p, name=name)
            found = True
    if not found:
        print("[Forge/scan] 新しいモデルはありません")


def cmd_list():
    reg = load_registry()
    ram = total_ram_bytes()
    print(f"RAM: {ram/(1<<30):.0f}GB (ワーカー予算 {ram*0.45/(1<<30):.0f}GB)")
    for m in sorted(reg["models"], key=lambda x: -x["size_bytes"]):
        print(f"  {m['name']:28s} {m['size_bytes']/(1<<30):6.2f}GB hidden={m['hidden']} "
              f"arch={m['arch']:16s} status={m['status']}")
    sel = select_worker()
    print(f"自動選択されるワーカー: {sel['name'] if sel else '(なし: ルーター単独動作)'}")


def cmd_align(worker_name):
    """ルーター(1024次元)とワーカーの埋め込み空間を結ぶ整列行列を最小二乗で学習。
    記憶のL3原文 (テキスト⇔ベクトル対応) がそのまま教師データになる。"""
    from verantyx_mind import RustBrain, embed_text, CortexMemory, AxisAnchors, DEFAULT_MODEL, TOKENIZER
    from transformers import AutoTokenizer
    reg = load_registry()
    w = next((m for m in reg["models"] if m["name"] == worker_name), None)
    assert w and w["status"] == "ready", f"ワーカー {worker_name} が ready ではありません"
    assert w["tokenizer"], "ワーカーのトークナイザが未登録です (--tokenizer)"

    mem = CortexMemory(AxisAnchors())
    texts = [r["l3_text"] for r in mem.index]
    # 記憶が少ないうちは軸コーパスで補強する
    from axis_anchor_trainer import AXIS_CORPUS
    for c in AXIS_CORPUS:
        texts.extend(c)
    texts = list(dict.fromkeys(texts))
    print(f"[Align] 教師テキスト {len(texts)} 件で 1024 -> {w['hidden']} の整列行列を学習")

    tok_r = AutoTokenizer.from_pretrained(TOKENIZER)
    brain_r = RustBrain(DEFAULT_MODEL)
    X = np.stack([embed_text(brain_r, tok_r, t) for t in texts])
    brain_r.close()

    tok_w = AutoTokenizer.from_pretrained(w["tokenizer"])
    brain_w = RustBrain(w["jgen"], hidden=w["hidden"])
    Y = np.stack([embed_text(brain_w, tok_w, t) for t in texts])
    brain_w.close()

    # ホールドアウト分割 (サンプル数 < 次元数の間は過学習するため、正直な汎化値を出す)
    n = X.shape[0]
    rng = np.random.default_rng(0)
    perm = rng.permutation(n)
    n_hold = max(4, n // 5)
    tr, ho = perm[n_hold:], perm[:n_hold]
    # リッジ正則化つき最小二乗 (少データでの暴れを抑える)
    lam = 1e-2
    A = X[tr].T @ X[tr] + lam * np.eye(X.shape[1], dtype=np.float32)
    W = np.linalg.solve(A, X[tr].T @ Y[tr])

    def cos_of(idx):
        pred = X[idx] @ W
        return float(np.mean(np.sum(pred * Y[idx], 1) /
                             (np.linalg.norm(pred, axis=1) * np.linalg.norm(Y[idx], axis=1) + 1e-8)))

    out = os.path.join(CHRONO, f"align_{worker_name}.npy")
    np.save(out, W.astype(np.float32))
    print(f"[Align] 訓練cos={cos_of(tr):.3f} / ホールドアウトcos={cos_of(ho):.3f} ({len(ho)}件) -> {out}")
    print(f"[Align] 教師データは記憶が増えるほど自動で増える (現在{n}件)。"
          f"ホールドアウトcosが0.8を超えたら実用域")


def main():
    ap = argparse.ArgumentParser(description="JGEN Forge: モデル変換+レジストリ基盤")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add"); p.add_argument("src"); p.add_argument("--name"); \
        p.add_argument("--dense", action="store_true"); p.add_argument("--tokenizer"); \
        p.add_argument("--parts", default="full", choices=["full", "lexicon"])
    p = sub.add_parser("register"); p.add_argument("jgen"); p.add_argument("--name"); \
        p.add_argument("--tokenizer"); p.add_argument("--arch", default="standard")
    sub.add_parser("sources")
    p = sub.add_parser("pull"); p.add_argument("query"); p.add_argument("--name"); \
        p.add_argument("--dense", action="store_true"); p.add_argument("--tokenizer"); \
        p.add_argument("--parts", default="full", choices=["full", "lexicon"])
    sub.add_parser("scan")
    sub.add_parser("list")
    p = sub.add_parser("align"); p.add_argument("worker")
    a = ap.parse_args()
    if a.cmd == "add":
        cmd_add(a.src, name=a.name, dense=a.dense, tokenizer=a.tokenizer, parts=a.parts)
    elif a.cmd == "sources":
        cmd_sources()
    elif a.cmd == "pull":
        cmd_pull(a.query, name=a.name, dense=a.dense, tokenizer=a.tokenizer, parts=a.parts)
    elif a.cmd == "register":
        cmd_register(a.jgen, name=a.name, tokenizer=a.tokenizer, arch=a.arch)
    elif a.cmd == "scan":
        cmd_scan()
    elif a.cmd == "list":
        cmd_list()
    elif a.cmd == "align":
        cmd_align(a.worker)


if __name__ == "__main__":
    main()
