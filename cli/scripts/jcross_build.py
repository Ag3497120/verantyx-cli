#!/usr/bin/env python3
import os
import sys
import argparse
import struct
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM

def build_jcross(model_id, output_path, role):
    """
    HuggingFaceのDense Weightsから、「知識」と「推論」を分離した
    JCross (JGEN V2) 形式に変換するツール。
    """
    if role == "worker":
        rank = 256
        print(f"[*] Role: WORKER (Rank={rank})")
        print("[*] Description: 意図的に言語能力をパージし、概念ベクトルによる純粋な推論に特化させます。")
    elif role == "commander":
        rank = 1024
        print(f"[*] Role: COMMANDER (Rank={rank})")
        print("[*] Description: ワーカーの総意を自然言語に翻訳・出力するため、文法構造を維持します。")
    else:
        print("[-] Invalid role. Use 'worker' or 'commander'.")
        sys.exit(1)

    print(f"\n[*] Loading Dense Weights from HuggingFace: {model_id}")
    print("[*] This process may take several minutes depending on model size and RAM...")
    
    try:
        hf_model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32, device_map="cpu")
        state_dict = hf_model.state_dict()
    except Exception as e:
        print(f"[-] Error loading model: {e}")
        sys.exit(1)
        
    print("[+] Model loaded successfully. Locating linear layers to convert...")
    
    target_suffixes = ['.q_proj.weight', '.k_proj.weight', '.v_proj.weight', '.o_proj.weight', 
                       '.gate_proj.weight', '.up_proj.weight', '.down_proj.weight']
                       
    linear_keys = [k for k in state_dict.keys() if any(k.endswith(suffix) for suffix in target_suffixes)]
            
    if not linear_keys:
        print("[-] Error: No compatible linear layers found. Ensure it's an Attention/MLP based LLM.")
        sys.exit(1)
        
    print(f"[+] Found {len(linear_keys)} target layers.")
    print(f"[*] Exporting to {output_path}...")
    
    with open(output_path, "wb") as f:
        f.write(b"JGEN")
        f.write(struct.pack("<I", 2)) # Version 2
        f.write(struct.pack("<I", len(linear_keys)))
        
        for name in tqdm(linear_keys, desc=f"Applying SVD (Rank {rank})"):
            W = state_dict[name].float()
            rows, cols = W.shape
            current_rank = min(rank, min(rows, cols))
            
            # SVD Separation (知識と推論の分離)
            U, S, Vh = torch.linalg.svd(W, full_matrices=False)
            
            U_trunc = U[:, :current_rank].half()
            S_trunc = S[:current_rank].half()
            V_trunc = Vh[:current_rank, :].T.half() 
            
            mod_x = torch.ones(cols, dtype=torch.float16)
            mod_y = torch.zeros(rows, dtype=torch.float16) 
            
            # Write Binary
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
            
            del state_dict[name]
            
    print(f"\n[+] Conversion Complete!")
    print(f"    Output saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verantyx JCross Conversion Tool")
    parser.add_argument("--model", type=str, default="google/gemma-4-12B", help="HuggingFace Model ID or local path")
    parser.add_argument("--role", type=str, required=True, choices=["worker", "commander"], help="Target role (worker/commander)")
    parser.add_argument("--output", type=str, required=True, help="Output .jgen file path")
    
    args = parser.parse_args()
    build_jcross(args.model, args.output, args.role)
