import os
import glob
import torch
import struct
from tqdm import tqdm
from safetensors import safe_open

model_path = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9/"
safetensors_files = sorted(glob.glob(os.path.join(model_path, "*.safetensors")))

def get_matrix_type(key):
    if "input_layernorm.weight" in key: return 0
    if "post_attention_layernorm.weight" in key: return 1
    if "linear_attn.conv1d" in key: return 2
    if "linear_attn.A_log" in key: return 3
    if "linear_attn.dt_bias" in key: return 4
    if "linear_attn.norm.weight" in key: return 15
    if "linear_attn.in_proj_a" in key: return 5
    if "linear_attn.in_proj_b" in key: return 6
    if "linear_attn.in_proj_qkv" in key: return 7
    if "linear_attn.in_proj_z" in key: return 8
    if "linear_attn.out_proj" in key: return 9
    if "mlp.gate_proj" in key: return 10
    if "mlp.up_proj" in key: return 11
    if "mlp.down_proj" in key: return 12
    if "self_attn.q_proj" in key: return 20
    if "self_attn.k_proj" in key: return 21
    if "self_attn.v_proj" in key: return 22
    if "self_attn.o_proj" in key: return 23
    return 255

print("[*] Rebuilding qwen_27b.jmeta...")
with open("qwen_27b.jmeta", "wb") as meta_f:
    meta_f.write(b"JMET")
    meta_f.write(struct.pack("<I", 1)) # version
    
    count_written = 0
    for file_path in safetensors_files:
        print(f"  > Processing: {os.path.basename(file_path)}")
        with safe_open(file_path, framework="pt", device="cpu") as sf:
            for key in sf.keys():
                matrix_type = get_matrix_type(key)
                if matrix_type == 255 or "mtp" in key:
                    continue
                    
                z_coord = -1
                if "layers." in key:
                    parts = key.split(".")
                    try:
                        z_coord = int(parts[parts.index("layers") + 1])
                    except: pass
                        
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
                    count_written += 1

print(f"[+] Rebuilt qwen_27b.jmeta successfully! Wrote {count_written} tensors.")
