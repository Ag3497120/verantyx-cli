import struct
import numpy as np
import torch

def read_jcross(file_path):
    with open(file_path, "rb") as f:
        magic = f.read(4)
        if magic != b"JGEN": return
        version = struct.unpack("<I", f.read(4))[0]
        
        while True:
            name_len_bytes = f.read(4)
            if not name_len_bytes: break
            name_len = struct.unpack("<I", name_len_bytes)[0]
            name = f.read(name_len).decode('utf-8')
            tensor_type = struct.unpack("<I", f.read(4))[0]
            
            if tensor_type == 1:
                rows = struct.unpack("<I", f.read(4))[0]
                cols = struct.unpack("<I", f.read(4))[0]
                rank = struct.unpack("<I", f.read(4))[0]
                f.read(rows * rank * 2)
                f.read(rank * 2)
                f.read(rank * cols * 2)
                f.read(cols * 2)
                f.read(rows * 2)
                f.read(rank * rank * 2)
            elif tensor_type == 2:
                rows = struct.unpack("<I", f.read(4))[0]
                cols = struct.unpack("<I", f.read(4))[0]
                f.read(rows * cols * 2)
            elif tensor_type == 3:
                numel = struct.unpack("<I", f.read(4))[0]
                data = f.read(numel * 2)
                if "input_layernorm.weight" in name and "layers.3." in name:
                    W = np.frombuffer(data, dtype=np.float16)
                    print(f"[{name}] numel={numel} W.mean={W.mean():.6f}, W.std={W.std():.6f}, W[0]={W[0]:.6f}")

read_jcross("/home/ubuntu/model_glm.jgen")
