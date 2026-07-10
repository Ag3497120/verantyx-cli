import os
import sys
import struct
import argparse
import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM

class GenerativeMatrix(nn.Module):
    """
    Implements Hybrid Spatial Compression (Coordinate-Based Weight Reconstruction + SVD).
    W_{ij} = (U_i * S * V_j^T) * mod_y_i * mod_x_j
    """
    def __init__(self, W_target, rank=64):
        super().__init__()
        rows, cols = W_target.shape
        self.rank = rank
        
        print(f"    [GenerativeMatrix] Fitting {rows}x{cols} matrix to Rank-{rank}...")
        
        # Initialize using SVD
        U, S, Vh = torch.linalg.svd(W_target.float(), full_matrices=False)
        
        self.U = nn.Parameter(U[:, :rank])
        self.S = nn.Parameter(S[:rank])
        self.V = nn.Parameter(Vh[:rank, :].T) # V is (cols, rank)
        
        # Spatial Modulators (Cross Symmetry Constraints)
        self.mod_x = nn.Parameter(torch.ones(cols))
        self.mod_y = nn.Parameter(torch.ones(rows))
        
        self.target = W_target.float()
        
    def forward(self):
        # Base reconstruction
        base = (self.U * self.S) @ self.V.T
        
        # Apply spatial modulators
        mod_matrix = self.mod_y.unsqueeze(1) @ self.mod_x.unsqueeze(0)
        return base * mod_matrix

def fit_generative_matrix(W_target, rank, steps=100, lr=0.01):
    model = GenerativeMatrix(W_target, rank=rank)
    
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
        
    model = model.to(device)
    W_target = W_target.to(device)
        
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=steps)
    
    # We use L1 loss as it's better for preserving sparse activation distributions
    criterion = nn.L1Loss()
    
    for step in range(steps):
        optimizer.zero_grad()
        W_pred = model()
        loss = criterion(W_pred, W_target)
        loss.backward()
        optimizer.step()
        scheduler.step()
        
        if (step + 1) % 50 == 0 or step == 0:
            print(f"      Step {step+1:03d}/{steps} | Loss: {loss.item():.4f}")
            
    return model.cpu()

def compile_generative(model_id, output_path, rank=64, steps=100):
    print(f"Loading HuggingFace model: {model_id}")
    hf_model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32, device_map="cpu")
    state_dict = hf_model.state_dict()
    
    config = hf_model.config
    num_layers = config.num_hidden_layers
    
    # Fix Matrix Types based on Verantyx standard
    matrix_mapping = {
        'self_attn.q_proj.weight': 7,
        'self_attn.k_proj.weight': 8,
        'self_attn.v_proj.weight': 9,
        'self_attn.o_proj.weight': 20,
        'mlp.gate_proj.weight': 10,
        'mlp.up_proj.weight': 11,
        'mlp.down_proj.weight': 12,
    }
    
    print(f"Exporting Generative Spatial Weights to {output_path}")
    
    with open(output_path, "wb") as f:
        # Header: JGEN
        f.write(b"JGEN")
        # Version
        f.write(struct.pack("<I", 1))
        # Metadata: num_layers, rank
        f.write(struct.pack("<I I", num_layers, rank))
        
        embed_weight = state_dict["model.embed_tokens.weight"]
        f.write(struct.pack("<B I I", 0, embed_weight.shape[0], embed_weight.shape[1])) # type 0: embed
        f.write(embed_weight.numpy().astype("float16").tobytes())
        
        lm_head = state_dict["lm_head.weight"]
        f.write(struct.pack("<B I I", 1, lm_head.shape[0], lm_head.shape[1])) # type 1: lm_head
        f.write(lm_head.numpy().astype("float16").tobytes())
        
        norm_weight = state_dict["model.norm.weight"]
        f.write(struct.pack("<B I I", 2, norm_weight.shape[0], 1)) # type 2: final_norm
        f.write(norm_weight.numpy().astype("float16").tobytes())
        
        for z in range(num_layers):
            print(f"Processing Layer Z={z}")
            
            # Layer Norms
            attn_norm = state_dict[f"model.layers.{z}.input_layernorm.weight"]
            f.write(struct.pack("<B B I I", 3, z, attn_norm.shape[0], 1)) # type 3: attn_norm
            f.write(attn_norm.numpy().astype("float16").tobytes())
            
            mlp_norm = state_dict[f"model.layers.{z}.post_attention_layernorm.weight"]
            f.write(struct.pack("<B B I I", 4, z, mlp_norm.shape[0], 1)) # type 4: mlp_norm
            f.write(mlp_norm.numpy().astype("float16").tobytes())
            
            for key_suffix, m_type in matrix_mapping.items():
                full_key = f"model.layers.{z}.{key_suffix}"
                W = state_dict[full_key]
                
                # Fit generative matrix
                gen_matrix = fit_generative_matrix(W, rank=rank, steps=steps)
                
                # Extract learned parameters
                U = gen_matrix.U.detach().numpy().astype("float16")
                S = gen_matrix.S.detach().numpy().astype("float16")
                V = gen_matrix.V.detach().numpy().astype("float16")
                mod_x = gen_matrix.mod_x.detach().numpy().astype("float16")
                mod_y = gen_matrix.mod_y.detach().numpy().astype("float16")
                
                rows = W.shape[0]
                cols = W.shape[1]
                
                f.write(struct.pack("<B B B I I I", 5, z, m_type, rows, cols, rank))
                
                f.write(U.tobytes())
                f.write(S.tobytes())
                f.write(V.tobytes())
                f.write(mod_x.tobytes())
                f.write(mod_y.tobytes())
                
    print(f"Successfully compiled to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="Qwen/Qwen1.5-0.5B-Chat")
    parser.add_argument("--output", type=str, default="qwen_0.5b.jgen")
    parser.add_argument("--rank", type=int, default=128)
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()
    
    compile_generative(args.model, args.output, args.rank, args.steps)
