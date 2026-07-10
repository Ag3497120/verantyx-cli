import os, json
from safetensors import safe_open
import torch

SNAPSHOT_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
index_path = os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json")
with open(index_path, "r") as f:
    weight_map = json.load(f)["weight_map"]

q_file = weight_map.get("model.language_model.layers.11.self_attn.q_proj.weight")
q_path = os.path.join(SNAPSHOT_DIR, q_file)
with safe_open(q_path, framework="pt", device="cpu") as f:
    print(f"q_proj: {f.get_tensor('model.language_model.layers.11.self_attn.q_proj.weight').shape}")
    print(f"k_proj: {f.get_tensor('model.language_model.layers.11.self_attn.k_proj.weight').shape}")
    print(f"v_proj: {f.get_tensor('model.language_model.layers.11.self_attn.v_proj.weight').shape}")
    print(f"o_proj: {f.get_tensor('model.language_model.layers.11.self_attn.o_proj.weight').shape}")
