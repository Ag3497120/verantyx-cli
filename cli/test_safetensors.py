import json
import struct
import os

SNAPSHOT_DIR = os.path.expanduser(f"~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
index_path = os.path.join(SNAPSHOT_DIR, "model.safetensors.index.json")

with open(index_path, "r") as f:
    weight_map = json.load(f)["weight_map"]

def get_tensor_info(safetensors_path, tensor_name):
    with open(safetensors_path, 'rb') as f:
        header_size = struct.unpack('<Q', f.read(8))[0]
        header_json = f.read(header_size).decode('utf-8')
        header = json.loads(header_json)
        
        if tensor_name in header:
            start, end = header[tensor_name]['data_offsets']
            absolute_start = 8 + header_size + start
            print(f"Tensor {tensor_name} found at offset {absolute_start}, size {end - start}")
            return absolute_start, end - start
        else:
            for key in header:
                if 'embed_tokens' in key:
                    start, end = header[key]['data_offsets']
                    absolute_start = 8 + header_size + start
                    print(f"Tensor {key} found at offset {absolute_start}, size {end - start}")
                    return absolute_start, end - start
            for key in header:
                if 'norm' in key and 'language_model' in key:
                    start, end = header[key]['data_offsets']
                    absolute_start = 8 + header_size + start
                    print(f"Tensor {key} found at offset {absolute_start}, size {end - start}")
                    return absolute_start, end - start
    return None, None

embed_file = weight_map.get("model.embed_tokens.weight") or weight_map.get("model.language_model.embed_tokens.weight")
embed_path = os.path.join(SNAPSHOT_DIR, embed_file)
get_tensor_info(embed_path, "model.language_model.embed_tokens.weight")

norm_file = weight_map.get("model.language_model.norm.weight") or weight_map.get("model.norm.weight")
norm_path = os.path.join(SNAPSHOT_DIR, norm_file)
get_tensor_info(norm_path, "model.language_model.norm.weight")

