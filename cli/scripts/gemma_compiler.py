import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoConfig
import numpy as np
import struct
import os

def perform_svd_compression(weight_tensor, rank=512):
    """
    Performs SVD compression on the weight tensor and returns U, S, V
    along with initial modulators mod_x and mod_y.
    """
    W = weight_tensor.float()
    
    # SVD
    U, S, V_t = torch.linalg.svd(W, full_matrices=False)
    
    # Truncate to rank
    actual_rank = min(rank, len(S))
    U_k = U[:, :actual_rank]
    S_k = S[:actual_rank]
    V_k_t = V_t[:actual_rank, :]
    V_k = V_k_t.T # [in_features, rank]
    
    # Create spatial cross modulators
    # mod_x scales input features, initially 1.0
    mod_x = torch.ones(V_k.shape[0], dtype=torch.float32)
    # mod_y shifts output features, initially 0.0
    mod_y = torch.zeros(U_k.shape[0], dtype=torch.float32)
    
    return U_k, S_k, V_k, mod_x, mod_y

def compile_gemma_jgen(model_id="google/gemma-4-12B", output_path="gemma_12b_generative.jgen", rank=512):
    print(f"Loading {model_id} from HuggingFace...")
    # Load model with bfloat16 to save memory during loading
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            torch_dtype=torch.bfloat16,
            device_map="cpu",
            low_cpu_mem_usage=True
        )
    except Exception as e:
        print(f"Failed to load {model_id}. Error: {e}")
        return

    print("Model loaded successfully. Starting SVD Brain Surgery...")
    
    gen_modules = []
    total_layers = 0
    compressed_layers = 0
    
    for name, module in model.named_modules():
        if isinstance(module, nn.Linear):
            total_layers += 1
            if "lm_head" in name:
                continue # Skip language modeling head
                
            print(f"  -> SVD compressing {name} (Shape: {module.weight.shape})...")
            # For linear, weight is [out_features, in_features]
            # U is [out_features, rank], V is [in_features, rank]
            U, S, V, mod_x, mod_y = perform_svd_compression(module.weight.detach(), rank=rank)
            
            gen_modules.append({
                "name": name,
                "U": U.numpy().astype(np.float16),
                "S": S.numpy().astype(np.float16),
                "V": V.numpy().astype(np.float16),
                "mod_x": mod_x.numpy().astype(np.float16),
                "mod_y": mod_y.numpy().astype(np.float16),
                "cols": module.in_features,
                "rows": module.out_features,
                "rank": min(rank, len(S))
            })
            compressed_layers += 1

    print(f"Surgery complete! Compressed {compressed_layers}/{total_layers} linear layers.")
    
    print(f"Saving to {output_path}...")
    with open(output_path, "wb") as f:
        f.write(b"JGEN")
        f.write(struct.pack("<I", 2)) # Version 2
        f.write(struct.pack("<I", len(gen_modules))) # Number of tensors
        
        for gm in gen_modules:
            name_bytes = gm["name"].encode('utf-8')
            f.write(struct.pack("<H", len(name_bytes)))
            f.write(name_bytes)
            
            f.write(struct.pack("<B", 1)) # Type 1 (Generative layer)
            
            f.write(struct.pack("<I I I", gm["rows"], gm["cols"], gm["rank"]))
            
            f.write(gm["U"].tobytes())
            f.write(gm["S"].tobytes())
            f.write(gm["V"].tobytes())
            f.write(gm["mod_x"].tobytes())
            f.write(gm["mod_y"].tobytes())
            
    print(f"✅ Successfully compiled {output_path}")

if __name__ == "__main__":
    import sys
    model_name = sys.argv[1] if len(sys.argv) > 1 else "google/gemma-4-12B"
    compile_gemma_jgen(model_id=model_name)
