import os
import sys
import struct
import torch
import numpy as np
from tqdm import tqdm
from transformers import AutoModelForCausalLM

def compile_commander_jgen(model_id, output_path, rank=1024):
    print(f"[*] Loading HuggingFace model: {model_id}")
    print(f"[*] Target Rank for Commander: {rank}")
    print("[*] Loading into memory... (This might take a while)")
    
    # Load from HF cache
    try:
        hf_model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32, device_map="cpu")
        state_dict = hf_model.state_dict()
    except Exception as e:
        print(f"Error loading model from HuggingFace: {e}")
        return
        
    print("[*] State dict loaded. Locating linear layers to compress...")
    
    # Identify linear layers that we can convert to JCross format.
    target_suffixes = ['.q_proj.weight', '.k_proj.weight', '.v_proj.weight', '.o_proj.weight', 
                       '.gate_proj.weight', '.up_proj.weight', '.down_proj.weight']
                       
    linear_keys = []
    for k in state_dict.keys():
        if any(k.endswith(suffix) for suffix in target_suffixes):
            linear_keys.append(k)
            
    if not linear_keys:
        print("[-] Error: Could not find any compatible linear layers in the state dict.")
        return
        
    print(f"[*] Found {len(linear_keys)} linear layers to compile.")
    
    print(f"[*] Exporting Generative JCross Weights to {output_path}")
    
    with open(output_path, "wb") as f:
        # Header: JGEN
        f.write(b"JGEN")
        # Version 2 (Matches gemma_trainer.py load_gemma_jgen)
        f.write(struct.pack("<I", 2))
        # Tensor count
        f.write(struct.pack("<I", len(linear_keys)))
        
        for name in tqdm(linear_keys, desc="Compiling to JCross"):
            W = state_dict[name].float() # Dense weight matrix
            rows, cols = W.shape
            
            current_rank = min(rank, min(rows, cols))
            
            # SVD Separation
            U, S, Vh = torch.linalg.svd(W, full_matrices=False)
            
            U_trunc = U[:, :current_rank].half()
            S_trunc = S[:current_rank].half()
            V_trunc = Vh[:current_rank, :].T.half() # V is (cols, rank)
            
            mod_x = torch.ones(cols, dtype=torch.float16)
            mod_y = torch.zeros(rows, dtype=torch.float16) 
            
            # Write to binary JGEN V2 format
            name_bytes = name.encode('utf-8')
            f.write(struct.pack("<H", len(name_bytes)))
            f.write(name_bytes)
            
            f.write(struct.pack("<B", 1)) # Type 1
            f.write(struct.pack("<I I I", rows, cols, current_rank))
            
            f.write(U_trunc.numpy().tobytes())
            f.write(S_trunc.numpy().tobytes())
            f.write(V_trunc.numpy().tobytes())
            f.write(mod_x.numpy().tobytes())
            f.write(mod_y.numpy().tobytes())
            
            # Free up memory
            del state_dict[name]
            
    print(f"[*] Compilation Complete! Commander JGEN saved to {output_path}")

if __name__ == "__main__":
    model_id = "google/gemma-4-12B"
    output_file = "/Users/motonishikoudai/verantyx-cli/cli/commander_12b_rank1024.jgen"
    compile_commander_jgen(model_id, output_file, rank=1024)
