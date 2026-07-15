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
            
            if tensor_type == 1: # SVDLossless
                rows = struct.unpack("<I", f.read(4))[0]
                cols = struct.unpack("<I", f.read(4))[0]
                rank = struct.unpack("<I", f.read(4))[0]
                
                u_bytes = f.read(rows * rank * 2)
                s_bytes = f.read(rank * 2)
                v_bytes = f.read(rank * cols * 2)
                
                mod_x_bytes = f.read(cols * 2)
                mod_y_bytes = f.read(rows * 2)
                c_valve_bytes = f.read(rank * rank * 2)
                
                if "experts.252.gate_proj" in name or "q_a_proj" in name and "layers.3" in name:
                    U = np.frombuffer(u_bytes, dtype=np.float16).reshape(rows, rank)
                    S = np.frombuffer(s_bytes, dtype=np.float16)
                    V = np.frombuffer(v_bytes, dtype=np.float16).reshape(rank, cols)
                    
                    Ut = torch.tensor(U.astype(np.float32))
                    St = torch.tensor(S.astype(np.float32))
                    Vt = torch.tensor(V.astype(np.float32))
                    
                    W = Ut @ torch.diag(St) @ Vt
                    print(f"[{name}] rank={rank} W.std={W.std().item():.6f}, S.max={St.max().item():.4f}, S.mean={St.mean().item():.4f}")
                    
            elif tensor_type == 2:
                rows = struct.unpack("<I", f.read(4))[0]
                cols = struct.unpack("<I", f.read(4))[0]
                f.read(rows * cols * 2)
            elif tensor_type == 3:
                numel = struct.unpack("<I", f.read(4))[0]
                f.read(numel * 2)

read_jcross("glm-5.2-9b-streaming/model.jcross")
