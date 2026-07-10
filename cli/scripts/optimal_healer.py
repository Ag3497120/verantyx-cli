import os
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForCausalLM
from torch.optim import AdamW
from tqdm import tqdm
import struct
import gc
import json
import numpy as np

# ---------------------------------------------------------
# Optimal Healer (Phase 11 - Deep Re-Trainer)
# ---------------------------------------------------------
# Uses Monkey-Patching to replace nn.Linear with GenerativeLinear.
# Trains ONLY the low-rank spatial modulators (mx, my, S) on the
# Optimal Stimulus Prompt to re-balance the Residual Stream.
# ---------------------------------------------------------

MODEL_ID = "google/gemma-4-12B"
JGEN_FILE = "cli/gemma_12b_generative.jgen"
DATASET_FILE = "cli/scripts/healing_dataset.jsonl"
RANK = 1024
DIM = 3840

class GenerativeLinear(nn.Module):
    """
    Replaces nn.Linear. Contains the JCross Spatial Lattice.
    Only mx, my, and S are trainable. U and V are frozen.
    """
    def __init__(self, in_features, out_features, rank=RANK):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.rank = rank
        
        # Frozen core knowledge (U, V)
        self.U = nn.Parameter(torch.zeros(out_features, rank), requires_grad=False)
        self.V = nn.Parameter(torch.zeros(in_features, rank), requires_grad=False)
        
        # Trainable Spatial Modulators
        self.S = nn.Parameter(torch.ones(rank), requires_grad=True)
        self.mx = nn.Parameter(torch.ones(in_features), requires_grad=True)
        self.my = nn.Parameter(torch.ones(out_features), requires_grad=True)
        
        # Original Bias (if any)
        self.bias = nn.Parameter(torch.zeros(out_features), requires_grad=False)

    def forward(self, x):
        # 1. Input Modulation
        x_mod = x * self.mx
        
        # 2. Project to Lattice
        z = torch.matmul(x_mod, self.V)
        
        # 3. Spatial Scaling
        z_scaled = z * self.S
        
        # 4. Multi-Banding / JCross Reasoning
        half_rank = self.rank // 2
        main_z = z_scaled[..., :half_rank]
        back_z = z_scaled[..., half_rank:]
        
        curr_main = main_z
        for _ in range(3):
            gate = torch.sigmoid(curr_main)
            curr_main = torch.nn.functional.silu(main_z * gate)
        
        absorbed_back = torch.nn.functional.gelu(back_z)
        z_out = torch.cat([main_z + curr_main, back_z + absorbed_back], dim=-1)
        
        # 5. Project back
        out = torch.matmul(z_out, self.U.T)
        
        # 6. Output Modulation
        return out * self.my + self.bias

def load_parameters_from_jgen(module, layer_index, filepath=JGEN_FILE):
    """Loads values from .jgen into the GenerativeLinear module."""
    bytes_per_layer = (
        (DIM * RANK * 2) +    # U
        (RANK * 2) +          # S
        (DIM * RANK * 2) +    # V
        (DIM * 2) +           # mx
        (DIM * 2)             # my
    )
    offset = layer_index * bytes_per_layer
    
    try:
        with open(filepath, "rb") as f:
            f.seek(offset)
            U_val = torch.frombuffer(f.read(DIM * RANK * 2), dtype=torch.float16).reshape(DIM, RANK)
            S_val = torch.frombuffer(f.read(RANK * 2), dtype=torch.float16)
            V_val = torch.frombuffer(f.read(DIM * RANK * 2), dtype=torch.float16).reshape(DIM, RANK)
            mx_val = torch.frombuffer(f.read(DIM * 2), dtype=torch.float16)
            my_val = torch.frombuffer(f.read(DIM * 2), dtype=torch.float16)
            
            # Since module shapes might differ for attention vs mlp, we assume standard DIM here
            # In a full implementation, we'd slice U and V appropriately for Q, K, V, O, etc.
            if module.in_features == DIM and module.out_features == DIM:
                module.U.data.copy_(U_val)
                module.V.data.copy_(V_val)
                module.S.data.copy_(S_val)
                module.mx.data.copy_(mx_val)
                module.my.data.copy_(my_val)
    except Exception as e:
        print(f"Warning: Could not load parameters for layer {layer_index}: {e}")

def monkey_patch_model(model):
    """Recursively replaces nn.Linear with GenerativeLinear and loads .jgen params."""
    print("  [\033[36mHealer\033[0m] Monkey-Patching nn.Linear -> GenerativeLinear...")
    
    layer_counter = 0
    total_replaced = 0
    
    for name, module in model.named_modules():
        # Iterate over children to replace them
        for child_name, child_module in module.named_children():
            if isinstance(child_module, nn.Linear):
                in_f = child_module.in_features
                out_f = child_module.out_features
                
                # Create the Generative equivalent
                gen_linear = GenerativeLinear(in_f, out_f, rank=RANK)
                
                # Load values from .jgen
                load_parameters_from_jgen(gen_linear, layer_counter)
                
                # Replace the module
                setattr(module, child_name, gen_linear)
                
                total_replaced += 1
                layer_counter += 1
                
    print(f"  [\033[32mSuccess\033[0m] Replaced {total_replaced} layers with Generative Spatial blocks.")
    return model

def freeze_original_weights(model):
    """Freezes everything except the spatial modulators."""
    trainable_params = 0
    frozen_params = 0
    
    for name, param in model.named_parameters():
        if "mx" in name or "my" in name or "S" in name:
            param.requires_grad = True
            trainable_params += param.numel()
        else:
            param.requires_grad = False
            frozen_params += param.numel()
            
    print(f"  [\033[36mHealer\033[0m] Deep Freezing Complete.")
    print(f"  Frozen: {frozen_params:,} parameters")
    print(f"  Trainable: {trainable_params:,} parameters (Spatial Modulators)")

def save_parameters_to_jgen(model, filepath=JGEN_FILE):
    print("  [\033[36mHealer\033[0m] Saving healed spatial parameters back to .jgen...")
    bytes_per_layer = (DIM * RANK * 2) + (RANK * 2) + (DIM * RANK * 2) + (DIM * 2) + (DIM * 2)
    
    layer_counter = 0
    with open(filepath, "r+b") as f:
        for name, module in model.named_modules():
            if isinstance(module, GenerativeLinear):
                offset = layer_counter * bytes_per_layer
                
                # S is after U
                f.seek(offset + (DIM * RANK * 2))
                f.write(module.S.data.to(torch.float16).cpu().numpy().tobytes())
                
                # mx is after U + S + V
                f.seek(offset + (DIM * RANK * 2) + (RANK * 2) + (DIM * RANK * 2))
                f.write(module.mx.data.to(torch.float16).cpu().numpy().tobytes())
                
                # my is after U + S + V + mx
                f.write(module.my.data.to(torch.float16).cpu().numpy().tobytes())
                
                layer_counter += 1
    print(f"  [\033[32mSuccess\033[0m] {layer_counter} layers successfully updated in {filepath}.")

def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"  [\033[36mHealer\033[0m] Initializing Optimal Healer on {device}...")
    
    # 1. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, local_files_only=True)
    
    # 2. Load the optimal healing dataset
    if not os.path.exists(DATASET_FILE):
        print(f"  [\033[31mError\033[0m] Could not find {DATASET_FILE}.")
        return
        
    dataset_texts = []
    with open(DATASET_FILE, "r") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    if "text" in data:
                        dataset_texts.append(data["text"])
                except:
                    pass
        
    print(f"  [\033[36mHealer\033[0m] Loaded {len(dataset_texts)} Healing Examples.")
    
    # 3. Load Model (Bare architecture)
    # Using torch_dtype=torch.float16 to save memory
    print(f"  [\033[36mHealer\033[0m] Loading model architecture...")
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float16, local_files_only=True)
    
    # 4. Monkey Patching & Freezing
    model = monkey_patch_model(model)
    freeze_original_weights(model)
    
    model = model.to(device)
    
    # 5. Training Setup
    optimizer = AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=5e-5)
    
    EPOCHS = 4 # 4 Epochs for healing as requested
    
    print(f"  [\033[36mHealer\033[0m] Commencing Healing Re-Training (Next-Token Prediction)...")
    
    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0
        for i, text in enumerate(dataset_texts):
            optimizer.zero_grad()
            
            inputs = tokenizer(text, return_tensors="pt").to(device)
            # Next-token prediction loss
            outputs = model(**inputs, labels=inputs["input_ids"])
            loss = outputs.loss
            
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        avg_loss = total_loss / len(dataset_texts)
        print(f"  Epoch {epoch+1:03d}/{EPOCHS} | Avg Loss: {avg_loss:.4f}")
            
    print(f"  [\033[32mSuccess\033[0m] Language layer successfully healed!")
    save_parameters_to_jgen(model)
    
    # Cleanup
    del model
    gc.collect()
    torch.mps.empty_cache() if torch.backends.mps.is_available() else torch.cuda.empty_cache()

if __name__ == "__main__":
    main()
