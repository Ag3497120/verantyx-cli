import json
import os

SNAPSHOT_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
index_path = os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json")

with open(index_path, "r") as f:
    weight_map = json.load(f)["weight_map"]
    
    for key in weight_map:
        if 'model.language_model.norm.weight' in key or 'model.norm.weight' in key:
            print(f"{key}: {weight_map[key]}")
