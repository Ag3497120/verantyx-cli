import struct
import numpy as np
import os
import json

SNAPSHOT_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
safetensors_path = os.path.join(SNAPSHOT_DIR, "model-00015-of-00015.safetensors")

with open(safetensors_path, 'rb') as f:
    header_size = struct.unpack('<Q', f.read(8))[0]
    header_json = f.read(header_size).decode('utf-8')
    header = json.loads(header_json)
    
    print(header.keys())
