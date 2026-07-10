import struct
import json
import os

SNAPSHOT_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
with open(os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json"), "r") as f:
    weight_map = json.load(f)["weight_map"]

embed_file = weight_map.get("model.embed_tokens.weight") or weight_map.get("model.language_model.embed_tokens.weight")
embed_path = os.path.join(SNAPSHOT_DIR, embed_file)

with open(embed_path, 'rb') as f:
    header_size = struct.unpack('<Q', f.read(8))[0]
    header_json = f.read(header_size).decode('utf-8')
    header = json.loads(header_json)
    
    # find the actual key
    key = "model.embed_tokens.weight" if "model.embed_tokens.weight" in header else "model.language_model.embed_tokens.weight"
    
    start, end = header[key]['data_offsets']
    abs_start = header_size + 8 + start
    print(f"embed_tokens abs_start: {abs_start}")
    
    f.seek(abs_start)
    data = f.read(20)
    for i in range(10):
        val = struct.unpack("<H", data[i*2:i*2+2])[0]
        val32 = val << 16
        f32 = struct.unpack("<f", struct.pack("<I", val32))[0]
        print(f"embed[{i}]: {val:04x} -> {f32}")

lm_head_file = weight_map.get("lm_head.weight")
lm_head_path = os.path.join(SNAPSHOT_DIR, lm_head_file)
with open(lm_head_path, 'rb') as f:
    header_size = struct.unpack('<Q', f.read(8))[0]
    header_json = f.read(header_size).decode('utf-8')
    header = json.loads(header_json)
    start, end = header["lm_head.weight"]['data_offsets']
    abs_start = header_size + 8 + start
    print(f"lm_head abs_start: {abs_start}")
    
    f.seek(abs_start)
    data = f.read(20)
    for i in range(10):
        val = struct.unpack("<H", data[i*2:i*2+2])[0]
        val32 = val << 16
        f32 = struct.unpack("<f", struct.pack("<I", val32))[0]
        print(f"lm_head[{i}]: {val:04x} -> {f32}")
