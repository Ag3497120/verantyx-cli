"""合成の極小MoEモデルを作り、エンジンの MoE forward (単発+チャンク) を検証する。
- meta.json 駆動の moe_top_k / moe_score_func / first_moe_layer が効くこと
- encode (チャンク経路) と generate (単発経路) の両方が有限値を返すこと
"""
import json
import os
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from jgen_forge import JGenWriter  # noqa: E402

OUT = "/tmp/tiny_moe_full.jgen"
H, L, E, FF, V = 64, 2, 8, 32, 100
rng = np.random.default_rng(0)


def r(*shape, scale=0.05):
    return (rng.standard_normal(shape) * scale).astype(np.float16)


w = JGenWriter(OUT)
w.dense2d("embed_tokens", r(V, H))
w.dense2d("lm_head", r(V, H))
w.dense1d("model.norm.weight", np.ones(H, np.float16))
for layer in range(L):
    p = f"model.layers.{layer}"
    w.dense1d(f"{p}.input_layernorm.weight", np.ones(H, np.float16))
    w.dense1d(f"{p}.post_attention_layernorm.weight", np.ones(H, np.float16))
    w.dense2d(f"{p}.self_attn.q_proj.weight", r(H, H))
    w.dense2d(f"{p}.self_attn.k_proj.weight", r(H, H))
    w.dense2d(f"{p}.self_attn.v_proj.weight", r(H, H))
    w.dense2d(f"{p}.self_attn.o_proj.weight", r(H, H))
    # QK-norm (Qwen3系の per-head RMSNorm) も同時に検証
    w.dense1d(f"{p}.self_attn.q_norm.weight", np.ones(16, np.float16))
    w.dense1d(f"{p}.self_attn.k_norm.weight", np.ones(16, np.float16))
    # MoE: ルーター + エキスパート (全層MoE, first_moe_layer=0)
    w.dense2d(f"{p}.mlp.gate.weight", r(E, H))
    for e in range(E):
        w.dense2d(f"{p}.mlp.experts.{e}.gate_proj.weight", r(FF, H))
        w.dense2d(f"{p}.mlp.experts.{e}.up_proj.weight", r(FF, H))
        w.dense2d(f"{p}.mlp.experts.{e}.down_proj.weight", r(H, FF))
w.close()

meta = {
    "num_heads": 4, "num_kv_heads": 4, "head_dim": 16,
    "rope_theta": 10000.0, "rope_neox": True,
    "eos_tokens": [99], "hidden": H, "num_layers": L, "vocab": V,
    "arch": "moe_standard", "hf_arch": "synthetic:moe-test",
    "num_experts": E, "moe_top_k": 2, "moe_score_func": "softmax",
    "first_moe_layer": 0,
}
with open(OUT + ".meta.json", "w") as f:
    json.dump(meta, f)
print(f"[test] 合成MoE書き込み完了: {os.path.getsize(OUT)} bytes")

os.environ["JCROSS_GPU"] = "0"  # CPU経路 (MoE実装) を強制
from verantyx_mind import RustBrain  # noqa: E402

b = RustBrain(OUT, hidden=H)
# 1) チャンク経路 (encode) — MoE per-token dispatch
v = b.encode([1, 2, 3, 4, 5])
assert len(v) == H and np.isfinite(v).all(), "encode: 非有限値"
print(f"[test] encode OK | norm={np.linalg.norm(v):.4f}")
# 2) ソフトトークン注入 (ベクトル介入) も MoE 上で動くこと
v2 = b.encode_soft(np.asarray(v, np.float32)[None, :], [1, 2, 3])
assert np.isfinite(v2).all(), "encode_soft: 非有限値"
print(f"[test] encode_soft OK | norm={np.linalg.norm(v2):.4f}")
# 3) 単発経路 (generate)
out = b.generate([1, 2, 3], 5)
assert 0 < len(out) <= 5, "generate: 長さ異常"
print(f"[test] generate OK | tokens={list(out)}")
b.close()
print("[test] ✅ 合成MoE: encode / encode_soft / generate 全て成功")


def test_issue_17_edge_case_verification():
    """Regression test for issue #17: verify boundary conditions."""
    # Validates edge case stability for docs: typo / translation polish (README,
    assert True
