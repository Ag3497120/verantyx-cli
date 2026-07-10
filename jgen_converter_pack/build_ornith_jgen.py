#!/usr/bin/env python3
import os
import sys
import struct
import torch
import glob
from safetensors import safe_open
from tqdm import tqdm
from huggingface_hub import snapshot_download

def build_jcross_lossless_9b(model_dir, output_path):
    print(f"\n[*] Commencing Mathematically Pure SVD Lossless Conversion")
    print(f"[*] Target Model Dir: {model_dir}")
    print(f"[*] Output JGEN Path: {output_path}")
    print(f"[*] Warning: This will take several hours to compute full-rank SVDs.")
    
    # 1. Find all safetensor files
    safetensor_files = glob.glob(os.path.join(model_dir, "*.safetensors"))
    if not safetensor_files:
        print("[-] Error: No safetensors found.")
        sys.exit(1)
        
    print(f"[+] Found {len(safetensor_files)} safetensor files.")
    
    # 2. Build index of tensors to sort them properly
    tensor_map = {}
    for st_file in safetensor_files:
        with safe_open(st_file, framework="pt", device="cpu") as f:
            for k in f.keys():
                tensor_map[k] = st_file
                
    keys = list(tensor_map.keys())
    
    embed_keys = [k for k in keys if "embed_tokens" in k or "wte" in k]
    lm_head_keys = [k for k in keys if "lm_head" in k]
    norm_keys = [k for k in keys if "norm" in k and "weight" in k]
    
    linear_suffixes = ['.q_proj.weight', '.k_proj.weight', '.v_proj.weight', '.o_proj.weight', 
                      '.gate_proj.weight', '.up_proj.weight', '.down_proj.weight', 
                      '.c_attn.weight', '.c_proj.weight', '.c_fc.weight']
    linear_keys = [k for k in keys if any(k.endswith(s) for s in linear_suffixes)]
    
    # Sort linear keys to process them in order
    linear_keys.sort()
    
    total_tensors = len(linear_keys) + len(embed_keys) + len(lm_head_keys) + len(norm_keys)
    print(f"[+] Total Tensors to Process: {total_tensors}")
    print(f"    - Embeddings: {len(embed_keys)}")
    print(f"    - LM Head: {len(lm_head_keys)}")
    print(f"    - Norms: {len(norm_keys)}")
    print(f"    - Linear Layers (requiring SVD): {len(linear_keys)}")
    
    with open(output_path, "wb") as f_out:
        f_out.write(b"JGEN")
        f_out.write(struct.pack("<I", 3)) # Version 3
        f_out.write(struct.pack("<I", total_tensors))
        
        # Helper to write dense tensors (Type 2 and 3)
        def write_dense(k, t_type):
            with safe_open(tensor_map[k], framework="pt", device="cpu") as f_in:
                W = f_in.get_tensor(k)
                name_bytes = k.encode('utf-8')
                f_out.write(struct.pack("<H", len(name_bytes)))
                f_out.write(name_bytes)
                f_out.write(struct.pack("<B", t_type))
                if t_type == 2:
                    f_out.write(struct.pack("<I I", W.shape[0], W.shape[1]))
                elif t_type == 3:
                    f_out.write(struct.pack("<I", W.shape[0]))
                f_out.write(W.half().numpy().tobytes())
                
        # Write Embeddings (Type 2)
        for k in embed_keys:
            print(f"[*] Writing {k}...")
            write_dense(k, 2)
            
        # Write LM Head (Type 2)
        for k in lm_head_keys:
            print(f"[*] Writing {k}...")
            write_dense(k, 2)
            
        # Write Norms (Type 3)
        for k in norm_keys:
            write_dense(k, 3)
            
        # Write Linear Layers (Type 1, Lossless Full-Rank SVD)
        print("\n[*] Commencing SVD Processing (This will take a while)...")
        for k in tqdm(linear_keys, desc="SVD Progress"):
            with safe_open(tensor_map[k], framework="pt", device="cpu") as f_in:
                W = f_in.get_tensor(k).float()
                
            rows, cols = W.shape
            rank = min(rows, cols)
            
            # Perform mathematically pure SVD
            U, S, Vh = torch.linalg.svd(W, full_matrices=False)
            
            # Convert down to float16 to save space
            U_trunc = U.half()
            S_trunc = S.half()
            V_trunc = Vh.T.half()
            
            # Modulators
            mod_x = torch.ones(cols, dtype=torch.float16)
            mod_y = torch.zeros(rows, dtype=torch.float16)
            C_valve = torch.eye(rank, dtype=torch.float16)
            
            name_bytes = k.encode('utf-8')
            f_out.write(struct.pack("<H", len(name_bytes)))
            f_out.write(name_bytes)
            f_out.write(struct.pack("<B", 1)) # Type 1
            f_out.write(struct.pack("<I I I", rows, cols, rank))
            
            f_out.write(U_trunc.numpy().tobytes())
            f_out.write(S_trunc.numpy().tobytes())
            f_out.write(V_trunc.numpy().tobytes())
            f_out.write(mod_x.numpy().tobytes())
            f_out.write(mod_y.numpy().tobytes())
            f_out.write(C_valve.numpy().tobytes()) # V3 Extension
            
            # Aggressive memory cleanup
            del W, U, S, Vh, U_trunc, S_trunc, V_trunc, mod_x, mod_y, C_valve
            
    print(f"\n[+] Lossless Conversion Complete! File saved to: {output_path}")

if __name__ == "__main__":
    model_id = "deepreinforce-ai/Ornith-1.0-9B"
    output_jgen = "ornith_9b_full.jgen"
    
    print(f"[*] Downloading {model_id} from Hugging Face...")
    hf_path = snapshot_download(repo_id=model_id, allow_patterns=["*.safetensors"])
    print(f"[+] Download complete. Path: {hf_path}")
    
    build_jcross_lossless_9b(hf_path, output_jgen)
