import os, json
SNAPSHOT_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
with open(os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json"), "r") as f:
    weight_map = json.load(f)["weight_map"]

layers = {}
for k in weight_map.keys():
    if "layers.0." in k:
        print(k)
