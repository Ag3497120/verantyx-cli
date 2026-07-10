import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
import struct
import numpy as np

class GenerativeLinear(nn.Module):
    def __init__(self, in_features, out_features, rank, U_data, S_data, V_data, mod_x_data, mod_y_data):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.rank = rank
        
        self.U = nn.Parameter(torch.from_numpy(U_data).to(torch.bfloat16).clone())
        self.S = nn.Parameter(torch.from_numpy(S_data).to(torch.bfloat16).clone())
        self.V = nn.Parameter(torch.from_numpy(V_data).to(torch.bfloat16).clone())
        
        self.mod_x = nn.Parameter(torch.from_numpy(mod_x_data).to(torch.bfloat16).clone())
        self.mod_y = nn.Parameter(torch.zeros(out_features, dtype=torch.bfloat16))
        
        # Bias is handled as Type 0 if it exists
        self.register_parameter('bias', None)
        
    def forward(self, x):
        h = torch.matmul(x * self.mod_x, self.V)
        y = torch.matmul(h * self.S, self.U.T)
        if self.bias is not None:
            y = y + self.bias
        return y + self.mod_y

def replace_module_or_tensor(model, key_name, replacement, is_generative=False):
    parts = key_name.split('.')
    parent = model
    
    if is_generative:
        for part in parts[:-2]:
            parent = getattr(parent, part)
        setattr(parent, parts[-2], replacement)
    else:
        for part in parts[:-1]:
            parent = getattr(parent, part)
            
        attr_name = parts[-1]
        
        if isinstance(parent, GenerativeLinear) and attr_name == 'bias':
            parent.bias = nn.Parameter(replacement)
        else:
            setattr(parent, attr_name, nn.Parameter(replacement))

def load_jgen_to_meta(model, jgen_path, device="mps"):
    print(f"Loading {jgen_path} into Meta architecture...")
    with open(jgen_path, "rb") as f:
        magic = f.read(4)
        if magic != b"JGEN":
            raise ValueError("Invalid JGEN file")
            
        version = struct.unpack("<I", f.read(4))[0]
        if version != 2:
            raise ValueError(f"Unsupported JGEN version: {version}")
            
        tensor_count = struct.unpack("<I", f.read(4))[0]
        print(f"File specifies {tensor_count} tensors.")
        
        for _ in range(tensor_count):
            name_len = struct.unpack("<H", f.read(2))[0]
            name = f.read(name_len).decode('utf-8')
            name = name.replace("language_model.", "")
            
            t_type = struct.unpack("<B", f.read(1))[0]
            
            if t_type == 1:
                rows, cols, rank = struct.unpack("<I I I", f.read(12))
                actual_rank = min(rows, cols, rank)
                
                U_data = np.frombuffer(f.read(rows * actual_rank * 2), dtype=np.float16).reshape(rows, actual_rank)
                S_data = np.frombuffer(f.read(actual_rank * 2), dtype=np.float16)
                V_data = np.frombuffer(f.read(cols * actual_rank * 2), dtype=np.float16).reshape(cols, actual_rank)
                mod_x_data = np.frombuffer(f.read(cols * 2), dtype=np.float16)
                mod_y_data = np.frombuffer(f.read(rows * 2), dtype=np.float16)
                
                gen_layer = GenerativeLinear(cols, rows, actual_rank, U_data, S_data, V_data, mod_x_data, mod_y_data).to(device)
                try:
                    replace_module_or_tensor(model, name, gen_layer, is_generative=True)
                except:
                    pass
                
            elif t_type == 0:
                dim_count = struct.unpack("<B", f.read(1))[0]
                shape = []
                num_elements = 1
                for _ in range(dim_count):
                    dim = struct.unpack("<I", f.read(4))[0]
                    shape.append(dim)
                    num_elements *= dim
                    
                raw_data = np.frombuffer(f.read(num_elements * 2), dtype=np.float16).reshape(shape)
                tensor = torch.from_numpy(raw_data).to(torch.bfloat16).to(device)
                
                try:
                    replace_module_or_tensor(model, name, tensor, is_generative=False)
                except AttributeError:
                    pass
                
    print("Meta loading complete!")

import torch.nn.functional as F

class LatentMemoryBank:
    def __init__(self, dim, max_size=10000):
        self.dim = dim
        self.max_size = max_size
        self.memory = None
        
    def write(self, states):
        if states.dim() > 2:
            states = states.view(-1, self.dim)
        states = states.detach()
        if self.memory is None:
            self.memory = states
        else:
            self.memory = torch.cat([self.memory, states], dim=0)
        if self.memory.size(0) > self.max_size:
            self.memory = self.memory[-self.max_size:]
            
    def read(self, current_state, k=5):
        if self.memory is None:
            return torch.zeros_like(current_state)
            
        B, S, D = current_state.shape
        curr_flat = current_state.view(-1, D).to(torch.bfloat16)
        
        # Calculate cosine similarity with all items in memory
        # memory is [N, D]
        scores = torch.matmul(curr_flat, self.memory.T)
        scores = scores / (D ** 0.5) # Scale by sqrt(dim)
        
        top_k_scores, top_k_indices = torch.topk(scores, min(k, self.memory.size(0)), dim=-1)
        weights = torch.softmax(top_k_scores.float(), dim=-1).to(torch.bfloat16)
        
        retrieved = torch.zeros_like(curr_flat)
        for i in range(B * S):
            retrieved[i] = torch.matmul(weights[i], self.memory[top_k_indices[i]])
            
        retrieved = retrieved.view(B, S, D).to(current_state.dtype)
        return retrieved

def create_memory_pre_hook(mod_m, memory_bank):
    def hook(module, args):
        hidden_states = args[0]
        context = memory_bank.read(hidden_states)
        # MUST ADD to the residual stream, not replace it!
        x_new = hidden_states + (context * mod_m)
        memory_bank.write(hidden_states)
        return (x_new,) + args[1:]
    return hook

def train_scalable():
    device = "mps" if torch.backends.mps.is_available() else "cuda"
    print(f"Using device: {device}")
    
    model_id = "Qwen/Qwen3.6-27B"
    try:
        config = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    except Exception:
        import sys, glob, os
        model_dir = sys.argv[1] if len(sys.argv) > 1 else "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B"
        snapshots_dir = os.path.join(model_dir, "snapshots")
        snapshots = [d for d in os.listdir(snapshots_dir) if not d.startswith('.')]
        snapshot = snapshots[0]
        config = AutoConfig.from_pretrained(os.path.join(snapshots_dir, snapshot), trust_remote_code=True)
        tokenizer = AutoTokenizer.from_pretrained(os.path.join(snapshots_dir, snapshot), trust_remote_code=True)
        model_id = os.path.join(snapshots_dir, snapshot)

    if hasattr(config, 'text_config'):
        if isinstance(config.text_config, dict):
            for k, v in config.text_config.items():
                if not hasattr(config, k):
                    setattr(config, k, v)
        else:
            for k in dir(config.text_config):
                if not k.startswith('_') and not hasattr(config, k):
                    setattr(config, k, getattr(config.text_config, k))
                    
    print("[*] Allocating Meta Architecture...")
    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config, trust_remote_code=True, torch_dtype=torch.bfloat16)
        
    print("[*] Injecting Rank-512 Generative Brain...")
    try:
        load_jgen_to_meta(model, "qwen_27b_generative.jgen", device=device)
    except FileNotFoundError:
        print("qwen_27b_generative.jgen not found.")
        return
        
    print("[*] Setting up Infinite Latent Memory...")
    hidden_size = config.text_config.hidden_size if hasattr(config, 'text_config') else config.hidden_size
    memory_bank = LatentMemoryBank(dim=hidden_size, max_size=5000)
    memory_mods = nn.ParameterList()
    
    if hasattr(model, 'model') and hasattr(model.model, 'layers'):
        layers = model.model.layers
    elif hasattr(model, 'language_model') and hasattr(model.language_model.model, 'layers'):
        layers = model.language_model.model.layers
    else:
        raise ValueError("Cannot locate transformer layers in architecture!")
        
    for layer in layers:
        mod_m = nn.Parameter(torch.full((hidden_size,), 0.01, dtype=torch.bfloat16).to(device))
        memory_mods.append(mod_m)
        layer.register_forward_pre_hook(create_memory_pre_hook(mod_m, memory_bank))
        
    print("\n============================================================")
    print("🧬 Phase 2: Architecture Healing (Rank-512 Restoration)")
    print("============================================================")
    print("Freezing U and V pathways... Opening S, mod_x, mod_y, mod_m for plasticity.")
    
    # Freeze all parameters first
    for param in model.parameters():
        param.requires_grad = False
        
    # Unfreeze only the generative scalers and memory mods
    trainable_params = []
    for module in model.modules():
        if isinstance(module, GenerativeLinear):
            module.S.requires_grad = True
            module.mod_x.requires_grad = True
            module.mod_y.requires_grad = True
            trainable_params.extend([module.S, module.mod_x, module.mod_y])
            
    for mod_m in memory_mods:
        mod_m.requires_grad = True
        trainable_params.append(mod_m)
        
    optimizer = torch.optim.AdamW(trainable_params, lr=1e-5)
    
    # Streaming Dataset Setup
    print("[*] Connecting to Hugging Face Streaming Datasets...")
    from datasets import load_dataset
    import random
    
    # English Dataset (wikitext-103-v1)
    ds_en = load_dataset("wikitext", "wikitext-103-v1", split="train", streaming=True)
    iter_en = iter(ds_en)
    
    # Japanese Dataset (izumi-lab)
    ds_ja = load_dataset("izumi-lab/wikipedia-ja-20230720", split="train", streaming=True)
    iter_ja = iter(ds_ja)
    
    model.train()
    
    max_steps = 20000
    accumulation_steps = 4
    save_every = 500
    
    print(f"Starting Bilingual Healing Process (Max {max_steps} steps, Batch Accumulation {accumulation_steps})...")
    
    ema_loss = None
    step = 0
    accumulated_loss = 0.0
    
    optimizer.zero_grad()
    
    # Pre-fetch an initial batch to warm up
    while step < max_steps:
        # Fetch text
        text = ""
        while not text.strip():
            if random.random() > 0.5:
                sample = next(iter_en)
                text = sample.get('text', '')
            else:
                sample = next(iter_ja)
                text = sample.get('text', '')
                
        # Limit sequence length to ~512 to avoid OOM
        # A simple approximation is truncation at ~2000 chars
        text = text[:2000]
        
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
        labels = inputs.input_ids.clone()
        
        # Skip empty sequences
        if inputs.input_ids.shape[1] < 2:
            continue
            
        outputs = model(**inputs)
        
        # Compute loss manually in float32 to prevent MPS float16 overflow
        shift_logits = outputs.logits[..., :-1, :].contiguous().float()
        shift_labels = labels[..., 1:].contiguous()
        loss_fct = nn.CrossEntropyLoss()
        loss = loss_fct(shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))
        
        loss = loss / accumulation_steps
        loss.backward()
        
        accumulated_loss += loss.item() * accumulation_steps
        
        if (step + 1) % accumulation_steps == 0:
            torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
            optimizer.step()
            optimizer.zero_grad()
            
            # Update EMA
            if ema_loss is None:
                ema_loss = accumulated_loss
            else:
                ema_loss = 0.95 * ema_loss + 0.05 * accumulated_loss
                
            actual_step = (step + 1) // accumulation_steps
            if actual_step % 10 == 0:
                print(f"Healing Step {actual_step:05d}/{max_steps//accumulation_steps} - EMA Loss: {ema_loss:.4f} - Curr Loss: {accumulated_loss:.4f}", flush=True)
                
            if actual_step > 0 and actual_step % save_every == 0:
                output_path = f"/Users/motonishikoudai/verantyx-cli/cli/qwen_27b_trained_step_{actual_step}.jgen"
                print(f"[*] Saving checkpoint to {output_path} ...", flush=True)
                _save_jgen_checkpoint(model, output_path)
                
            accumulated_loss = 0.0
            
        step += 1
        
    print("\n✅ Healing Phase Complete! Synaptic pathways restored.")
    
def _save_jgen_checkpoint(model, output_path):
    import struct
    import numpy as np
    gen_modules = []
    for name, module in model.named_modules():
        if isinstance(module, GenerativeLinear):
            gen_modules.append((name, module))
            
    with open(output_path, "wb") as f:
        f.write(b"JGEN")
        f.write(struct.pack("<I", 2)) # version 2
        f.write(struct.pack("<I", len(gen_modules))) # tensor_count
        
        for name, module in gen_modules:
            name_bytes = name.encode('utf-8')
            f.write(struct.pack("<H", len(name_bytes)))
            f.write(name_bytes)
            
            f.write(struct.pack("<B", 1)) # t_type = 1
            
            rows = module.U.shape[0]
            cols = module.in_features
            actual_rank = module.rank
            
            f.write(struct.pack("<I I I", rows, cols, actual_rank))
            
            U_fp16 = module.U.detach().float().cpu().numpy().astype(np.float16)
            S_fp16 = module.S.detach().float().cpu().numpy().astype(np.float16)
            V_fp16 = module.V.detach().float().cpu().numpy().astype(np.float16)
            mod_x_fp16 = module.mod_x.detach().float().cpu().numpy().astype(np.float16)
            mod_y_fp16 = module.mod_y.detach().float().cpu().numpy().astype(np.float16)
            
            f.write(U_fp16.tobytes())
            f.write(S_fp16.tobytes())
            f.write(V_fp16.tobytes())
            f.write(mod_x_fp16.tobytes())
            f.write(mod_y_fp16.tobytes())
    
    output_path = "/Users/motonishikoudai/verantyx-cli/cli/qwen_27b_trained.jgen"
    print(f"[*] Saving healed Brain to {output_path} ...", flush=True)
    _save_jgen_checkpoint(model, output_path)
    
    print(f"✅ Saved healed generative layers to {output_path}")
    print("You can now safely run scripts/chat_27b.py for zero-shot intelligent inference.")

if __name__ == "__main__":
    train_scalable()
