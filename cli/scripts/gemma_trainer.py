import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
import numpy as np
import struct

class GenerativeLinear(nn.Module):
    def __init__(self, in_features, out_features, rank, U_data, S_data, V_data, mod_x_data, mod_y_data):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.rank = rank
        
        # Frozen core logic
        self.U = nn.Parameter(torch.from_numpy(U_data).to(torch.bfloat16).clone(), requires_grad=False)
        self.S = nn.Parameter(torch.from_numpy(S_data).to(torch.bfloat16).clone(), requires_grad=False)
        self.V = nn.Parameter(torch.from_numpy(V_data).to(torch.bfloat16).clone(), requires_grad=False)
        
        # Trainable Spatial Modulators (The Muscle Memory)
        self.mod_x = nn.Parameter(torch.from_numpy(mod_x_data).to(torch.bfloat16).clone(), requires_grad=True)
        self.mod_y = nn.Parameter(torch.from_numpy(mod_y_data).to(torch.bfloat16).clone(), requires_grad=True)
        
        self.register_parameter('bias', None)
        
    def forward(self, x):
        h = torch.matmul(x * self.mod_x, self.V)
        y = torch.matmul(h * self.S, self.U.T)
        return y + self.mod_y

def replace_module_or_tensor(model, key_name, replacement):
    parts = key_name.split('.')
    parent = model
    for part in parts[:-1]:
        parent = getattr(parent, part)
    setattr(parent, parts[-1], replacement)

def load_gemma_jgen(model, jgen_path, device="cpu"):
    print(f"Loading JGEN into Meta architecture from {jgen_path}...")
    with open(jgen_path, "rb") as f:
        magic = f.read(4)
        if magic != b"JGEN": raise ValueError("Invalid")
        f.read(4) # version
        tensor_count = struct.unpack("<I", f.read(4))[0]
        
        for _ in range(tensor_count):
            name_len = struct.unpack("<H", f.read(2))[0]
            name = f.read(name_len).decode('utf-8')
            
            t_type = struct.unpack("<B", f.read(1))[0]
            if t_type == 1:
                rows, cols, rank = struct.unpack("<I I I", f.read(12))
                U_data = np.frombuffer(f.read(rows * rank * 2), dtype=np.float16).reshape(rows, rank)
                S_data = np.frombuffer(f.read(rank * 2), dtype=np.float16)
                V_data = np.frombuffer(f.read(cols * rank * 2), dtype=np.float16).reshape(cols, rank)
                mod_x_data = np.frombuffer(f.read(cols * 2), dtype=np.float16)
                mod_y_data = np.frombuffer(f.read(rows * 2), dtype=np.float16)
                
                gen_layer = GenerativeLinear(cols, rows, rank, U_data, S_data, V_data, mod_x_data, mod_y_data).to(device)
                
                try:
                    replace_module_or_tensor(model, name, gen_layer)
                except Exception as e:
                    pass
    print("Meta loading complete!")

def save_jgen_checkpoint(model, output_path):
    gen_modules = [(name, m) for name, m in model.named_modules() if isinstance(m, GenerativeLinear)]
    with open(output_path, "wb") as f:
        f.write(b"JGEN")
        f.write(struct.pack("<I", 2))
        f.write(struct.pack("<I", len(gen_modules)))
        for name, module in gen_modules:
            nb = name.encode('utf-8')
            f.write(struct.pack("<H", len(nb)))
            f.write(nb)
            f.write(struct.pack("<B", 1))
            f.write(struct.pack("<I I I", module.U.shape[0], module.in_features, module.rank))
            f.write(module.U.detach().float().cpu().numpy().astype(np.float16).tobytes())
            f.write(module.S.detach().float().cpu().numpy().astype(np.float16).tobytes())
            f.write(module.V.detach().float().cpu().numpy().astype(np.float16).tobytes())
            f.write(module.mod_x.detach().float().cpu().numpy().astype(np.float16).tobytes())
            f.write(module.mod_y.detach().float().cpu().numpy().astype(np.float16).tobytes())
    print(f"[*] Checkpoint saved to {output_path}")

def train_gemma():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Training on device: {device}")
    
    model_id = "google/gemma-4-12B"
    print("Loading Gemma 12B Meta Model...")
    # Auto-detect latest checkpoint to resume from
    import glob
    import re
    
    base_ckpt = "gemma_12b_trained_step_680.jgen"
    latest_step = 680
    latest_pt = None
    
    pt_files = glob.glob("gemma_12b_muscles_step_*.pt")
    for f in pt_files:
        match = re.search(r"step_(\d+)\.pt", f)
        if match:
            s = int(match.group(1))
            if s > latest_step:
                latest_step = s
                latest_pt = f
                
    print(f"Loading Base JGEN: {base_ckpt}...")
    
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    
    # Inject JGEN Base
    load_gemma_jgen(model, base_ckpt, device="cpu")
    
    if latest_pt:
        print(f"Injecting Muscle Memory from {latest_pt} at step {latest_step}...")
        try:
            muscles = torch.load(latest_pt)
            for name, param in model.named_parameters():
                if param.requires_grad and name in muscles:
                    param.data.copy_(muscles[name].to(param.device))
        except Exception as e:
            print(f"Failed to load {latest_pt}: {e}. File might be corrupted.")
            import os
            os.remove(latest_pt)
            print("Corrupted file removed. Please restart to fallback to previous checkpoint.")
            raise
    model.to(device)
    
    print("Enabling Gradient Checkpointing to save memory...")
    model.gradient_checkpointing_enable()
    
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    param_count = sum(p.numel() for p in trainable_params)
    print(f"Total Trainable Parameters (mod_x, mod_y only): {param_count:,}")
    
    # MEMORY HACK 1: Reverted to AdamW! 
    # AdamW is strictly necessary to prevent Mode Collapse. We will rely on Zombie Loop.
    print("Using AdamW optimizer. Expect crashes, relying on zombie loop...")
    optimizer = torch.optim.AdamW(trainable_params, lr=2e-4)
    
    print("Loading dataset...")
    dataset = load_dataset("wikitext", "wikitext-2-v1", split="train", streaming=True)
    
    model.train()
    step = latest_step
    max_steps = 2000
    save_every = 20  # Save more frequently since we expect crashes
    
    print("🚀 Starting Healing Phase...")
    for batch in dataset:
        if step >= max_steps:
            break
            
        text = batch["text"]
        if len(text.strip()) < 10:
            continue
            
        # Keep sequence length slightly reduced to buy a few more steps before crash
        inputs = tokenizer(text, return_tensors="pt", max_length=256, truncation=True)
        input_ids = inputs["input_ids"].to(device)
        
        if input_ids.shape[1] < 10:
            continue
            
        optimizer.zero_grad()
        outputs = model(input_ids=input_ids, labels=input_ids)
        loss = outputs.loss
        
        loss.backward()
        optimizer.step()
        
        print(f"Step {step:03d}/{max_steps} - Loss: {loss.item():.4f}", flush=True)
        
        if (step + 1) % save_every == 0:
            print("Flushing memory before saving checkpoint to prevent OOM...")
            optimizer.zero_grad(set_to_none=True)
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
                
            # NEW: Atomic saving
            muscles = {name: param.cpu().clone() for name, param in model.named_parameters() if param.requires_grad}
            tmp_path = f"gemma_12b_muscles_step_{step+1}.pt.tmp"
            final_path = f"gemma_12b_muscles_step_{step+1}.pt"
            torch.save(muscles, tmp_path)
            import os
            os.rename(tmp_path, final_path)
            print(f"Saved tiny muscle checkpoint at step {step+1}!")
            
        step += 1
        
        # Force macOS to free fragmented memory pool after every step
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        
    save_jgen_checkpoint(model, "gemma_12b_trained.jgen")
    print("✅ Healing Complete!")

if __name__ == "__main__":
    train_gemma()
