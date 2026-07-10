import os, json
from safetensors import safe_open
SNAPSHOT_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
index_path = os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json")
with open(index_path, "r") as f:
    weight_map = json.load(f)["weight_map"]
for k in weight_map.keys():
    if "mtp.layers" in k:
        print(k)
