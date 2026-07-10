import os
import glob
import struct
import torch
from safetensors import safe_open
from tqdm import tqdm

def get_matrix_type(key):
    if "embed_tokens.weight" in key: return 77
    if "lm_head.weight" in key: return 88
    if "model.norm.weight" in key: return 99
    
    if "linear_attn.conv1d" in key: return 2
    if "linear_attn.A_log" in key: return 3
    if "linear_attn.dt_bias" in key: return 4
    if "linear_attn.in_proj_a" in key: return 5
    if "linear_attn.in_proj_b" in key: return 6
    if "linear_attn.in_proj_qkv" in key: return 7
    if "linear_attn.in_proj_z" in key: return 8
    if "linear_attn.out_proj" in key: return 9
    
    if "mlp.gate_proj" in key: return 10
    if "mlp.up_proj" in key: return 11
    if "mlp.down_proj" in key: return 12
    
    if "linear_attn.norm.weight" in key: return 15
    
    if "self_attn.q_proj" in key: return 20
    if "self_attn.k_proj" in key: return 21
    if "self_attn.v_proj" in key: return 22
    if "self_attn.o_proj" in key: return 23
    
    return 255

def main():
    model_path = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9/"
    safetensors_files = sorted(glob.glob(os.path.join(model_path, "*.safetensors")))
    
    meta_path = "qwen_27b.jmeta"
    meta_f = open(meta_path, "wb")
    meta_f.write(b"JMET")
    meta_f.write(struct.pack("<I", 1)) # version
    
    count = 0
    for file_path in safetensors_files:
        print(f"  > Processing: {os.path.basename(file_path)}")
        with safe_open(file_path, framework="pt", device="cpu") as sf:
            keys = list(sf.keys())
            for key in keys:
                matrix_type = get_matrix_type(key)
                if matrix_type == 255 or "mtp" in key:
                    continue
                    
                z_coord = -1
                if "layers." in key:
                    parts = key.split(".")
                    try:
                        z_coord = int(parts[parts.index("layers") + 1])
                    except:
                        pass
                        
                if z_coord == -1:
                    z_coord = 254
                    
                tensor = sf.get_tensor(key)
                
                if tensor.dtype != torch.float16:
                    tensor = tensor.half()
                
                shape = list(tensor.shape)
                
                if len(shape) == 1 or "conv1d" in key:
                    tensor_bytes = tensor.numpy().tobytes()
                    meta_f.write(struct.pack("<B B I", z_coord & 0xFF, matrix_type & 0xFF, len(tensor_bytes)))
                    meta_f.write(tensor_bytes)
                    count += 1
                    print(f"Extracted 1D/Conv: {key} -> type {matrix_type}, len {len(tensor_bytes)}")
                del tensor

    meta_f.close()
    print(f"Wrote {count} elements to {meta_path}")

if __name__ == "__main__":
    main()
