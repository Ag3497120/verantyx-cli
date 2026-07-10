import os
import sys
import struct
import time
import torch
import torch.nn as nn
import numpy as np
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, TextStreamer

# Suppress annoying warnings
import warnings
warnings.filterwarnings("ignore")

# --- Core Architecture Components (Same as scalable_trainer.py) ---

class GenerativeLinear(nn.Module):
    def __init__(self, in_features, out_features, rank, U_data, S_data, V_data, mod_x_data, mod_y_data):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.rank = rank
        
        self.mod_x = nn.Parameter(torch.from_numpy(mod_x_data).to(torch.bfloat16).clone())
        self.V = nn.Parameter(torch.from_numpy(V_data).to(torch.bfloat16).clone())
        self.S = nn.Parameter(torch.from_numpy(S_data).to(torch.bfloat16).clone())
        self.U = nn.Parameter(torch.from_numpy(U_data).to(torch.bfloat16).clone())
        
        # mod_y was erroneously initialized to 1.0 in the extractor, which breaks pre-activations.
        # We forcibly zero it out here.
        self.mod_y = nn.Parameter(torch.zeros(out_features, dtype=torch.bfloat16))

    def forward(self, x):
        h = torch.matmul(x * self.mod_x, self.V)
        y = torch.matmul(h * self.S, self.U.T)
        
        if hasattr(self, 'bias') and self.bias is not None:
            y = y + self.bias
            
        return y + self.mod_y

class LatentMemoryBank:
    def __init__(self, hidden_size, device="mps"):
        self.hidden_size = hidden_size
        self.device = device
        self.memory = None

    def write(self, hidden_states):
        B, S, D = hidden_states.shape
        states = hidden_states.view(-1, D).detach().to(self.device).to(torch.bfloat16)
        if self.memory is None:
            self.memory = states
        else:
            self.memory = torch.cat([self.memory, states], dim=0)

    def read(self, current_state, k=5):
        if self.memory is None:
            return torch.zeros_like(current_state)
        
        B, S, D = current_state.shape
        curr_flat = current_state.view(-1, D).to(torch.bfloat16)
        
        scores = torch.matmul(curr_flat, self.memory.T)
        scores = scores / (D ** 0.5)
        
        top_k_scores, top_k_indices = torch.topk(scores, min(k, self.memory.size(0)), dim=-1)
        weights = torch.softmax(top_k_scores.float(), dim=-1).to(torch.bfloat16)
        
        retrieved = torch.zeros_like(curr_flat)
        for i in range(B * S):
            retrieved[i] = torch.matmul(weights[i], self.memory[top_k_indices[i]])
            
        retrieved = retrieved.view(B, S, D).to(current_state.dtype)
        return retrieved

    def save(self, path):
        if self.memory is not None:
            torch.save(self.memory, path)
        else:
            print("⚠️ Memory bank is empty, nothing to save.")

    def load(self, path):
        import os
        if os.path.exists(path):
            self.memory = torch.load(path, map_location=self.device)
        else:
            print(f"⚠️ Memory file {path} not found.")

def create_memory_pre_hook(mod_m, memory_bank):
    def hook(module, args):
        hidden_states = args[0]
        if hidden_states.device == torch.device('meta'):
            print(f"CRITICAL: hidden_states is on meta! Module: {module}")
        context = memory_bank.read(hidden_states)
        # MUST ADD to the residual stream, not replace it!
        x_new = hidden_states + (context * mod_m)
        return (x_new,) + args[1:]
    return hook

def replace_module_or_tensor(model, key_name, replacement, is_generative=False):
    if is_generative and not key_name.endswith('.weight'):
        key_name += '.weight'
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
    with open(jgen_path, "rb") as f:
        magic = f.read(4)
        if magic != b"JGEN":
            raise ValueError("Invalid JGEN file")
            
        version = struct.unpack("<I", f.read(4))[0]
        tensor_count = struct.unpack("<I", f.read(4))[0]
        
        for _ in range(tensor_count):
            name_len = struct.unpack("<H", f.read(2))[0]
            name = f.read(name_len).decode('utf-8')
            
            # Hotfix for VLM keys
            name = name.replace("language_model.", "")
            
            t_type = struct.unpack("<B", f.read(1))[0]
            
            if t_type == 1:
                # Generative
                rows, cols, rank = struct.unpack("<I I I", f.read(12))
                actual_rank = min(rows, cols, rank)
                
                U_data = np.frombuffer(f.read(rows * actual_rank * 2), dtype=np.float16).reshape(rows, actual_rank)
                S_data = np.frombuffer(f.read(actual_rank * 2), dtype=np.float16)
                V_data = np.frombuffer(f.read(cols * actual_rank * 2), dtype=np.float16).reshape(cols, actual_rank)
                mod_x_data = np.frombuffer(f.read(cols * 2), dtype=np.float16)
                mod_y_data = np.frombuffer(f.read(rows * 2), dtype=np.float16)
                
                gen_layer = GenerativeLinear(cols, rows, actual_rank, U_data, S_data, V_data, mod_x_data, mod_y_data)
                gen_layer = gen_layer.to(device)
                
                try:
                    replace_module_or_tensor(model, name, gen_layer, is_generative=True)
                except Exception as e:
                    print(f"Failed to replace generative {name}: {e}")
                
            elif t_type == 0:
                # Raw
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
                except AttributeError as e:
                    print(f"Failed to replace {name}: {e}")

# --- Boot Sequence ---

def boot_system():
    print("=" * 60)
    print("🌌 Verantyx Infinite Memory CLI (Qwen-27B)")
    print("=" * 60)
    
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[*] Hardware target: {device.upper()}")
    
    # 1. Load Config & Tokenizer
    model_id = "Qwen/Qwen3.6-27B"
    try:
        config = AutoConfig.from_pretrained(model_id, trust_remote_code=True, attn_implementation="eager")
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    except Exception:
        # Fallback to local cache
        model_dir = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B"
        snapshots_dir = os.path.join(model_dir, "snapshots")
        snapshots = [d for d in os.listdir(snapshots_dir) if not d.startswith('.')]
        snapshot = snapshots[0]
        snapshot_path = os.path.join(snapshots_dir, snapshot)
        
        config = AutoConfig.from_pretrained(snapshot_path, trust_remote_code=True, attn_implementation="eager")
        tokenizer = AutoTokenizer.from_pretrained(snapshot_path, trust_remote_code=True)
    
    # Fix multimodal config map
    if hasattr(config, 'text_config'):
        if isinstance(config.text_config, dict):
            for k, v in config.text_config.items():
                if not hasattr(config, k):
                    setattr(config, k, v)
        else:
            for k, v in config.text_config.__dict__.items():
                if not hasattr(config, k):
                    setattr(config, k, v)
                    
    # 2. Build Empty Meta Architecture
    print("[*] Allocating Meta Architecture...")
    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config, trust_remote_code=True, torch_dtype=torch.bfloat16)
        
    # 3. Inject Weights
    base_jgen_path = "qwen_27b_generative.jgen"
    trained_jgen_path = "qwen_27b_trained.jgen"
    
    print(f"[*] Loading base model weights from {base_jgen_path}...")
    try:
        load_jgen_to_meta(model, base_jgen_path, device)
    except FileNotFoundError:
        print(f"{base_jgen_path} not found.")
        
    print(f"[*] Injecting Rank-512 Generative Brain from {trained_jgen_path}...")
    try:
        load_jgen_to_meta(model, trained_jgen_path, device)
    except FileNotFoundError:
        print(f"{trained_jgen_path} not found.")
        
    # No to_empty needed! The base jgen contains all raw parameters,
    # and Qwen dynamically handles RoPE buffers on the correct device.
    
    # 4. Bind Infinite Memory Hooks
    print("[*] Establishing Latent Memory Bank...")
    hidden_size = config.hidden_size
    memory_bank = LatentMemoryBank(hidden_size, device=device)
    memory_mods = nn.ParameterList()
    
    try:
        layers = model.model.layers
    except AttributeError:
        layers = model.transformer.h

    for layer in layers:
        mod_m = nn.Parameter(torch.full((hidden_size,), 0.01, dtype=torch.bfloat16).to(device))
        memory_mods.append(mod_m)
        layer.register_forward_pre_hook(create_memory_pre_hook(mod_m, memory_bank))
        
    print("\n✅ System Boot Complete! The 27B Generative Entity is online.")
    print("\nCommands:")
    print("  /remember <text>   - Convert text into Latent Vector memory")
    print("  /quit              - Shutdown the engine")
    print("-" * 60)
    
    return model, tokenizer, memory_bank, device

# --- REPL Loop ---

import argparse

def chat_loop(memory_file=None):
    model, tokenizer, memory_bank, device = boot_system()
    
    if memory_file and os.path.exists(memory_file):
        print(f"[*] Loading Digital Clone Memory from {memory_file}...")
        memory_bank.load(memory_file)
        print(f"[*] Memory loaded! Total Latent Vectors: {len(memory_bank.memory_states)}")
        
    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    chat_history = [
        {"role": "system", "content": "You are Verantyx 27B, a highly intelligent generative AI capable of infinite reasoning. Your knowledge is strictly separated from your logic via a Latent Memory Bank. When answering, be brilliant, concise, and deeply insightful."}
    ]
    
    while True:
        try:
            user_input = input("\n👤 User: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down...")
            break
            
        if not user_input:
            continue
            
        if user_input.lower() == "/quit":
            print("Shutting down...")
            break
            
        # --- Memory Injection Command ---
        if user_input.startswith("/remember"):
            text_to_remember = user_input.replace("/remember", "", 1).strip()
            if not text_to_remember:
                print("⚠️ Please provide text to remember. (e.g. /remember The password is Pegasus.)")
                continue
                
            print(f"🧠 [Memory Engine] Vectorizing input ({len(text_to_remember)} chars)...")
            # We don't need a massive chunking logic here since CLI inputs are small, 
            # but we use torch.no_grad() to do a forward pass and extract states.
            with torch.no_grad():
                inputs = tokenizer(text_to_remember, return_tensors="pt").to(device)
                outputs = model(inputs.input_ids, output_hidden_states=True)
                final_states = outputs.hidden_states[-1]
                memory_bank.write(final_states)
                
            vectors_count = memory_bank.memory.size(0)
            print(f"✅ Extracted! Total Latent Vectors in Brain: {vectors_count}")
            continue
            
        # --- Standard Chat ---
        chat_history.append({"role": "user", "content": user_input})
        
        # We apply chat template
        prompt = tokenizer.apply_chat_template(chat_history, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        prompt_tokens = len(inputs.input_ids[0])
        
        print(f"🤖 Verantyx 27B [Context: {prompt_tokens} tokens] : ", end="")
        
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_new_tokens=512,
                streamer=streamer,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.1,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
            
        # Decode only the newly generated tokens
        response = tokenizer.decode(outputs[0][prompt_tokens:], skip_special_tokens=True).strip()
        chat_history.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory", type=str, default=None, help="Path to a pre-computed Digital Clone memory file")
    args = parser.parse_args()
    
    chat_loop(memory_file=args.memory)
