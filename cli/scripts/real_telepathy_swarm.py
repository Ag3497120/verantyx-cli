import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
import struct
import numpy as np
import gc
import os

# --- 1. Multiplexed JCross Components ---

# Global context to switch brain
current_role = "worker" 

class MultiplexedJCrossLinear(nn.Module):
    """
    動的に Worker (Rank 256) と Commander (Rank 1024) の USV 行列を切り替える Linear 層。
    これにより VRAM 24GB 分のベースモデルを1つ共有しつつ、2つの脳を共存させる。
    """
    def __init__(self, in_features, out_features, w_rank, c_rank, 
                 w_U, w_S, w_V, w_mod_x, w_mod_y,
                 c_U, c_S, c_V, c_mod_x, c_mod_y):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        
        # Worker Params (Language Purged)
        self.w_U = nn.Parameter(torch.from_numpy(w_U).to(torch.bfloat16), requires_grad=False)
        self.w_S = nn.Parameter(torch.from_numpy(w_S).to(torch.bfloat16), requires_grad=False)
        self.w_V = nn.Parameter(torch.from_numpy(w_V).to(torch.bfloat16), requires_grad=False)
        self.w_mx = nn.Parameter(torch.from_numpy(w_mod_x).to(torch.bfloat16), requires_grad=False)
        self.w_my = nn.Parameter(torch.from_numpy(w_mod_y).to(torch.bfloat16), requires_grad=False)
        
        # Commander Params (Language Preserved)
        self.c_U = nn.Parameter(torch.from_numpy(c_U).to(torch.bfloat16), requires_grad=False)
        self.c_S = nn.Parameter(torch.from_numpy(c_S).to(torch.bfloat16), requires_grad=False)
        self.c_V = nn.Parameter(torch.from_numpy(c_V).to(torch.bfloat16), requires_grad=False)
        self.c_mx = nn.Parameter(torch.from_numpy(c_mod_x).to(torch.bfloat16), requires_grad=False)
        self.c_my = nn.Parameter(torch.from_numpy(c_mod_y).to(torch.bfloat16), requires_grad=False)
        
        self.register_parameter('bias', None)
        
    def forward(self, x):
        global current_role
        if current_role == "worker":
            h = torch.matmul(x * self.w_mx, self.w_V)
            y = torch.matmul(h * self.w_S, self.w_U.T)
            return y + self.w_my
        else: # commander
            h = torch.matmul(x * self.c_mx, self.c_V)
            y = torch.matmul(h * self.c_S, self.c_U.T)
            return y + self.c_my

def parse_jgen_file(jgen_path):
    print(f"Parsing {jgen_path}...")
    tensors = {}
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
                U = np.frombuffer(f.read(rows * rank * 2), dtype=np.float16).reshape(rows, rank)
                S = np.frombuffer(f.read(rank * 2), dtype=np.float16)
                V = np.frombuffer(f.read(cols * rank * 2), dtype=np.float16).reshape(cols, rank)
                mx = np.frombuffer(f.read(cols * 2), dtype=np.float16)
                my = np.frombuffer(f.read(rows * 2), dtype=np.float16)
                tensors[name] = (rank, U, S, V, mx, my)
    return tensors

def replace_module_or_tensor(model, key_name, replacement):
    parts = key_name.split('.')
    parent = model
    for part in parts[:-1]:
        parent = getattr(parent, part)
    setattr(parent, parts[-1], replacement)

def load_multiplexed_jgen(model, worker_path, commander_path, device="cpu"):
    w_tensors = parse_jgen_file(worker_path)
    c_tensors = parse_jgen_file(commander_path)
    
    print("Injecting Multiplexed Layers into Base Model...")
    keys = list(w_tensors.keys())
    for name in keys:
        if name in c_tensors:
            w_rank, w_U, w_S, w_V, w_mx, w_my = w_tensors[name]
            c_rank, c_U, c_S, c_V, c_mx, c_my = c_tensors[name]
            
            rows = w_U.shape[0]
            cols = w_V.shape[0]
            
            layer = MultiplexedJCrossLinear(cols, rows, w_rank, c_rank, 
                                            w_U, w_S, w_V, w_mx, w_my,
                                            c_U, c_S, c_V, c_mx, c_my).to(device)
            try:
                replace_module_or_tensor(model, name, layer)
            except Exception:
                pass
    print("Injection complete!")

# --- 2. Memory & Swarm Architecture ---

class TelepathicMemoryBank:
    def __init__(self):
        self.latent_stream = []
        self.consensus_vector = None
        
    def _auto_store(self, agent_id, role, vector):
        self.latent_stream.append({
            "agent": agent_id,
            "role": role,
            "vector": vector.detach().clone()
        })
        print(f"  [{agent_id}] Concept vector Auto-stored. Shape: {vector.shape}")
        
    def update_consensus(self):
        worker_vectors = [m["vector"] for m in self.latent_stream if m["role"] == "worker"]
        if worker_vectors:
            self.consensus_vector = torch.mean(torch.stack(worker_vectors), dim=0)

    def check_veto(self, commander_intent_vector, threshold=0.9):
        # We set threshold relatively high because the base model is the same, 
        # so difference in Rank shouldn't break similarity completely unless there's drift.
        # But for demonstration, we will print the similarity.
        if self.consensus_vector is None:
            return False
        
        # Ensure floating types match and check similarity
        a = commander_intent_vector.float()
        b = self.consensus_vector.float()
        cos_sim = torch.nn.functional.cosine_similarity(a, b, dim=-1).mean()
        print(f"    [System] Consensus Similarity: {cos_sim.item():.4f}")
        return cos_sim.item() < threshold

class SwarmSession:
    def __init__(self, model, tokenizer, device):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self.memory = TelepathicMemoryBank()
        
    def get_latent_vector(self, prompt, role):
        global current_role
        current_role = role
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            # Gemma 12B requires output_hidden_states to extract vectors
            outputs = self.model(**inputs, output_hidden_states=True)
            # Use the last hidden state of the last token as the concept vector
            hidden = outputs.hidden_states[-1][:, -1, :] 
        return hidden
        
    def worker_discuss(self, prompt, workers=3):
        print(f"\n--- Swarm Discussion Loop ---")
        for i in range(workers):
            agent_id = f"Worker-{i+1}"
            vector = self.get_latent_vector(prompt, "worker")
            self.memory._auto_store(agent_id, "worker", vector)
            
        self.memory.update_consensus()
        
    def commander_translate(self, prompt):
        agent_id = "Commander-Alpha"
        print(f"  [{agent_id}] Attempting to synthesize consensus to Natural Language...")
        
        intent_vector = self.get_latent_vector(prompt, "commander")
        self.memory._auto_store(agent_id, "commander", intent_vector)
        
        # Check Veto
        if self.memory.check_veto(intent_vector, threshold=0.98):
            print(f"[Worker-1] ⚠️ VETO: コマンダーの出力意図にワーカー総意との乖離を検知！自然言語の生成をブロックします。")
            print(f"[{agent_id}] ❌ 翻訳処理を中断。")
            return None
            
        # If no veto, generate natural language
        global current_role
        current_role = "commander"
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        print(f"[{agent_id}] Allowed. Generating natural language...")
        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=30, do_sample=True, temperature=0.7)
            
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"\n[{agent_id}] Output:\n{text}")
        return text

# --- 3. Main Execution ---

if __name__ == "__main__":
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Target Device: {device}")
    
    worker_jgen = "/Users/motonishikoudai/verantyx-cli/cli/gemma_12b_generative.jgen"
    commander_jgen = "/Users/motonishikoudai/verantyx-cli/cli/commander_12b_rank1024.jgen"
    model_id = "google/gemma-4-12B"
    
    if not os.path.exists(worker_jgen) or not os.path.exists(commander_jgen):
        print("Missing JGEN files!")
        exit(1)
        
    print("Loading Base Model to CPU...")
    # low_cpu_mem_usage=True helps fit the 24GB initial load
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    
    load_multiplexed_jgen(model, worker_jgen, commander_jgen, device="cpu")
    
    print("Garbage collecting original dense weights...")
    gc.collect()
    
    print(f"Transferring Multiplexed JCross Model to {device}...")
    model.eval()
    model.to(device)
    if device == "mps": torch.mps.empty_cache()
    
    print("\n=== Initiating Verantyx Telepathy Swarm (Real Tensors) ===")
    session = SwarmSession(model, tokenizer, device)
    
    prompt = "What is the capital of Japan? Please answer in one word."
    print(f"[System] User Request: {prompt}")
    
    session.worker_discuss(prompt)
    session.commander_translate(prompt)
    
    print("\n[System] Swarm memory stream length:", len(session.memory.latent_stream))
