import os
import sys
import struct
import torch
import numpy as np
from safetensors import safe_open
import json

SNAPSHOT_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
index_path = os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json")

if not os.path.exists(index_path):
    print("Error: safetensors index not found.")
    sys.exit(1)

with open(index_path, "r") as f:
    weight_map = json.load(f)["weight_map"]

lm_head_file = weight_map.get("lm_head.weight")
norm_file = weight_map.get("model.language_model.norm.weight") or weight_map.get("model.norm.weight")

lm_head_path = os.path.join(SNAPSHOT_DIR, lm_head_file)
norm_path = os.path.join(SNAPSHOT_DIR, norm_file)

with safe_open(lm_head_path, framework="pt", device="cpu") as f:
    lm_head = f.get_tensor("lm_head.weight").half()

with safe_open(norm_path, framework="pt", device="cpu") as f:
    norm_key = "model.language_model.norm.weight" if "model.language_model.norm.weight" in f.keys() else "model.norm.weight"
    final_norm_weight = f.get_tensor(norm_key).half()

out_path = "qwen_27b.jhead"
print(f"Exporting to {out_path}...")
with open(out_path, "wb") as f:
    f.write(b"JHED")
    f.write(struct.pack("<I", 1))
    
    # Write final norm
    norm_bytes = final_norm_weight.numpy().tobytes()
    f.write(struct.pack("<I", len(norm_bytes)))
    f.write(norm_bytes)
    
    # Pad to 16384 (page boundary for Apple Silicon)
    current_pos = f.tell()
    # We will write the shape (8 bytes) and then the weights.
    # The weights themselves should be aligned to 16384.
    # So we want `current_pos + padding_length + 8` to be a multiple of 16384.
    target_weight_pos = ((current_pos + 8 + 16383) // 16384) * 16384
    padding_length = target_weight_pos - current_pos - 8
    f.write(b'\0' * padding_length)
    
    # Write LM head
    head_bytes = lm_head.numpy().tobytes()
    f.write(struct.pack("<I I", lm_head.shape[0], lm_head.shape[1]))
    # Now f.tell() is exactly target_weight_pos!

    f.write(head_bytes)

print("Done.")
