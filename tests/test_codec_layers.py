"""中間層 dump/inject FFI のスモーク (合成極小モデル)。"""
import json
import os
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from jgen_forge import JGenWriter  # noqa: E402

OUT = "/tmp/tiny_codec_layers.jgen"
H, L, FF, V = 64, 4, 32, 100
rng = np.random.default_rng(1)


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
    w.dense2d(f"{p}.mlp.gate_proj.weight", r(FF, H))
    w.dense2d(f"{p}.mlp.up_proj.weight", r(FF, H))
    w.dense2d(f"{p}.mlp.down_proj.weight", r(H, FF))
w.close()

meta = {
    "num_heads": 4, "num_kv_heads": 4, "head_dim": 16,
    "rope_theta": 10000.0, "rope_neox": True,
    "eos_tokens": [99], "hidden": H, "num_layers": L, "vocab": V,
    "arch": "dense", "hf_arch": "synthetic:codec-layers",
}
with open(OUT + ".meta.json", "w") as f:
    json.dump(meta, f)

os.environ["JCROSS_GPU"] = "0"
from verantyx_mind import RustBrain  # noqa: E402

b = RustBrain(OUT, hidden=H)
assert b.num_layers == L, f"num_layers={b.num_layers}"
print(f"[test] num_layers={b.num_layers} hidden={b.hidden}")

ids = [1, 2, 3, 4]
layers = [0, L // 2, L - 1]
dumps = b.encode_layers(ids, layers)
assert set(dumps.keys()) == set(layers)
for Lidx, z in dumps.items():
    assert z.shape == (H,) and np.isfinite(z).all(), f"layer {Lidx} bad"
    print(f"[test] encode_layers[{Lidx}] OK norm={np.linalg.norm(z):.4f}")

# dump → inject at mid → final should be finite
z_mid = dumps[layers[1]]
z_out = b.inject_at_layer(ids, layers[1], z_mid, alpha=1.0)
assert z_out.shape == (H,) and np.isfinite(z_out).all()
print(f"[test] inject_at_layer OK norm={np.linalg.norm(z_out):.4f}")

# final-norm dump (layer index == num_layers)
dumps2 = b.encode_layers(ids, [L])
z_final = dumps2[L]
z_enc = b.encode(ids)
cos = float(
    z_final @ z_enc
    / ((np.linalg.norm(z_final) + 1e-8) * (np.linalg.norm(z_enc) + 1e-8))
)
print(f"[test] post-norm dump vs encode cos={cos:.6f}")
assert cos > 0.99, f"post-norm dump should match encode, cos={cos}"

b.close()
print("[test] ✅ encode_layers / inject_at_layer / num_layers OK")
