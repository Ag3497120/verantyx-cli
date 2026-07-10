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
    
    start, end = header["model.language_model.norm.weight"]['data_offsets']
    f.seek(8 + header_size + start)
    data = f.read(10)
    
    u16 = np.frombuffer(data, dtype=np.uint16)
    
    # decode as float16
    f16 = np.frombuffer(data, dtype=np.float16)
    print("As float16:", f16)
    
    # decode as bfloat16
    u32 = np.zeros(5, dtype=np.uint32)
    u32[:] = u16
    u32 <<= 16
    bf16 = u32.view(np.float32)
    print("As bfloat16:", bf16)
