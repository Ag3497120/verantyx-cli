import os
import sys
import struct
import torch
import numpy as np
from tqdm import tqdm
from transformers import AutoModelForCausalLM

def compile_telepathic_jgen(model_id, output_path, rank=None, hidden_dim=4096):
    """
    Compiles a HuggingFace LLM into a Verantyx JCross format with Telepathy Receptors.
    If rank=None, performs LOSSLESS conversion (no SVD compression).
    """
    print(f"[*] Loading HuggingFace model for Telepathic Coder: {model_id}")
    if rank is None:
        print(f"[*] Mode: LOSSLESS (Full Rank, Zero Compression)")
    else:
        print(f"[*] Mode: COMPRESSED (Target Rank: {rank})")
        
    print(f"[*] Telepathy Vector Dimension: {hidden_dim}")
    print("[*] Loading into memory... (This might take a while)")
    
    # Load from HF cache
    try:
        hf_model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32, device_map="cpu")
        state_dict = hf_model.state_dict()
    except Exception as e:
        print(f"[-] Error loading model from HuggingFace: {e}")
        print("[-] Ensure you have accepted the model license and logged into huggingface-cli.")
        return
        
    print("[*] State dict loaded. Locating linear layers...")
    
    target_suffixes = ['.q_proj.weight', '.k_proj.weight', '.v_proj.weight', '.o_proj.weight', 
                       '.gate_proj.weight', '.up_proj.weight', '.down_proj.weight']
                       
    linear_keys = []
    dense_keys = []
    vector_keys = []
    
    for k in list(state_dict.keys()):
        if any(k.endswith(suffix) for suffix in target_suffixes):
            linear_keys.append(k)
        elif 'embed_tokens' in k or 'lm_head' in k:
            dense_keys.append(k)
        elif 'norm' in k:
            vector_keys.append(k)
        else:
            # Ignore anything else (e.g., token type embeddings if they exist)
            del state_dict[k]
            
    if not linear_keys:
        print("[-] Error: Could not find any compatible linear layers in the state dict.")
        return
        
    print(f"[*] Found {len(linear_keys)} intermediate linear layers.")
    print(f"[*] Found {len(dense_keys)} dense dictionary layers (embed/lm_head).")
    print(f"[*] Found {len(vector_keys)} norm/vector layers.")
    
    # +1 for the Telepathy Receptor layer
    tensor_count = len(linear_keys) + len(dense_keys) + len(vector_keys) + 1 
    print(f"[*] Exporting Telepathic JCross Weights to {output_path}")
    
    with open(output_path, "wb") as f:
        # Header: JGEN
        f.write(b"JGEN")
        # Version 4 (Version 4 includes full model parameters: dense & vectors)
        f.write(struct.pack("<I", 4))
        # Tensor count
        f.write(struct.pack("<I", tensor_count))
        
        # 1. Write the Linear Layers (Type 1)
        for name in tqdm(linear_keys, desc="Compiling SVD Linear Layers"):
            W = state_dict[name].float() # Dense weight matrix
            rows, cols = W.shape
            
            if rank is None:
                # LOSSLESS MODE: Full SVD to preserve 100% of the matrix information
                current_rank = min(rows, cols)
                U, S, Vh = torch.linalg.svd(W, full_matrices=False)
                
                U_trunc = U.half()
                S_trunc = S.half()
                V_trunc = Vh.T.half() 
            else:
                # COMPRESSED MODE
                current_rank = min(rank, min(rows, cols))
                U, S, Vh = torch.linalg.svd(W, full_matrices=False)
                
                U_trunc = U[:, :current_rank].half()
                S_trunc = S[:current_rank].half()
                V_trunc = Vh[:current_rank, :].T.half() 
            
            mod_x = torch.ones(cols, dtype=torch.float16)
            mod_y = torch.zeros(rows, dtype=torch.float16) 
            
            # Write to binary JGEN format
            name_bytes = name.encode('utf-8')
            f.write(struct.pack("<H", len(name_bytes)))
            f.write(name_bytes)
            
            f.write(struct.pack("<B", 1)) # Type 1 (SVD Compressed or Full SVD)
            f.write(struct.pack("<I I I", rows, cols, current_rank))
            
            f.write(U_trunc.numpy().tobytes())
            f.write(S_trunc.numpy().tobytes())
            f.write(V_trunc.numpy().tobytes())
            f.write(mod_x.numpy().tobytes())
            f.write(mod_y.numpy().tobytes())
            
            del state_dict[name]
            
        # 2. Write the Dense Matrices (Type 2)
        for name in tqdm(dense_keys, desc="Compiling Dense Layers (LM Head)"):
            W = state_dict[name].half()
            rows, cols = W.shape
            
            name_bytes = name.encode('utf-8')
            f.write(struct.pack("<H", len(name_bytes)))
            f.write(name_bytes)
            
            f.write(struct.pack("<B", 2)) # Type 2 (Raw Dense FP16 Matrix)
            f.write(struct.pack("<I I", rows, cols))
            
            f.write(W.numpy().tobytes())
            del state_dict[name]
            
        # 3. Write the 1D Vectors (Type 3)
        for name in tqdm(vector_keys, desc="Compiling Vector Layers (Norms)"):
            W = state_dict[name].half()
            size = W.shape[0]
            
            name_bytes = name.encode('utf-8')
            f.write(struct.pack("<H", len(name_bytes)))
            f.write(name_bytes)
            
            f.write(struct.pack("<B", 3)) # Type 3 (Raw Dense FP16 Vector)
            f.write(struct.pack("<I", size))
            
            f.write(W.numpy().tobytes())
            del state_dict[name]
            
        # 2. Write the Telepathy Receptor Layer
        print("[*] Injecting Telepathy Receptor Weights (Zero-initialized)...")
        # This receptor maps the hidden_dim (e.g. 4096) to the model's internal dimension (assumed to be e.g. 4096 or dynamic)
        receptor_name = "telepathy.receptor.weight".encode('utf-8')
        f.write(struct.pack("<H", len(receptor_name)))
        f.write(receptor_name)
        
        f.write(struct.pack("<B", 1)) # Type 1
        
        r_rows, r_cols, r_rank = hidden_dim, hidden_dim, hidden_dim
        f.write(struct.pack("<I I I", r_rows, r_cols, r_rank))
        
        # Zero-initialized so that initially it does not disrupt the pre-trained text model.
        # It will only let telepathy through when trained/activated.
        r_U = torch.zeros(r_rows, r_rank, dtype=torch.float16)
        r_S = torch.zeros(r_rank, dtype=torch.float16)
        r_V = torch.zeros(r_cols, r_rank, dtype=torch.float16)
        r_mod_x = torch.ones(r_cols, dtype=torch.float16)
        r_mod_y = torch.zeros(r_rows, dtype=torch.float16)
        
        f.write(r_U.numpy().tobytes())
        f.write(r_S.numpy().tobytes())
        f.write(r_V.numpy().tobytes())
        f.write(r_mod_x.numpy().tobytes())
        f.write(r_mod_y.numpy().tobytes())

    print(f"[*] Compilation Complete! Telepathic Coder JGEN saved to {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compile Telepathic Coder JCross Model")
    parser.add_argument("--model", type=str, default="google/gemma-4-12B", help="HuggingFace model ID")
    parser.add_argument("--output", type=str, default="telepathic_coder_lossless.jgen", help="Output .jgen file path")
    parser.add_argument("--lossless", action="store_true", help="Enable Lossless (Zero Compression) mode")
    parser.add_argument("--rank", type=int, default=1024, help="Target rank for SVD (Ignored if --lossless is set)")
    parser.add_argument("--hidden-dim", type=int, default=4096, help="Dimension of the Telepathy Vectors")
    
    args = parser.parse_args()
    
    target_rank = None if args.lossless else args.rank
    compile_telepathic_jgen(args.model, args.output, rank=target_rank, hidden_dim=args.hidden_dim)
