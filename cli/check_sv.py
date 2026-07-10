import torch
import numpy as np
import struct

jgen_path = "qwen_27b_generative.jgen"
with open(jgen_path, "rb") as f:
    f.read(12)
    tensor_count = struct.unpack("<I", f.read(4))[0]
    
    for _ in range(3): # Check first 3
        name_len = struct.unpack("<H", f.read(2))[0]
        name = f.read(name_len).decode()
        t_type = struct.unpack("<B", f.read(1))[0]
        if t_type == 1:
            rows, cols, rank = struct.unpack("<I I I", f.read(12))
            actual_rank = min(rows, cols, rank)
            
            U_data = np.frombuffer(f.read(rows * actual_rank * 2), dtype=np.float16)
            S_data = np.frombuffer(f.read(actual_rank * 2), dtype=np.float16)
            V_data = np.frombuffer(f.read(cols * actual_rank * 2), dtype=np.float16)
            mod_x_data = np.frombuffer(f.read(cols * 2), dtype=np.float16)
            mod_y_data = np.frombuffer(f.read(rows * 2), dtype=np.float16)
            
            print(f"{name} max S: {np.max(S_data)}")
        elif t_type == 0:
            dim_count = struct.unpack("<B", f.read(1))[0]
            shape = []
            num_elements = 1
            for _ in range(dim_count):
                dim = struct.unpack("<I", f.read(4))[0]
                shape.append(dim)
                num_elements *= dim
            f.read(num_elements * 2)

