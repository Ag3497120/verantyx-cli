import os
import sys
import time
import gc
import json
import torch
import numpy as np
from safetensors.torch import load_file

# --- UI Constants ---
C_WORKER = "\033[36m"    # Cyan
C_CMDR   = "\033[33m"    # Yellow/Orange
C_SYS    = "\033[90m"    # Gray (System info)
C_ALERT  = "\033[31m"    # Red (Alert/Veto)
C_RESET  = "\033[0m"

# --- Telepathic Memory Bank (Eternal Memory) ---
class TelepathicMemoryBank:
    def __init__(self, memory_file="/Users/motonishikoudai/verantyx-cli/my_clone.memory", hidden_dim=4096):
        self.memory_tensor = None  # [N, hidden_dim]
        self.memory_file = memory_file
        self.hidden_dim = hidden_dim
        self.load_eternal_memory()
        
    def load_eternal_memory(self):
        if os.path.exists(self.memory_file):
            print(f"{C_SYS}  [Memory] Restoring Eternal Database from {self.memory_file}...{C_RESET}")
            try:
                with open(self.memory_file, "rb") as f:
                    data = f.read()
                    if len(data) > 0:
                        np_array = np.frombuffer(data, dtype=np.float16)
                        num_vectors = len(np_array) // self.hidden_dim
                        if num_vectors > 0:
                            np_array = np_array[:num_vectors * self.hidden_dim]
                            self.memory_tensor = torch.from_numpy(np_array).copy().reshape(num_vectors, self.hidden_dim).to(torch.float16)
                            print(f"{C_SYS}  [Memory] Database Restored! Vector Count: {num_vectors}{C_RESET}")
            except Exception as e:
                print(f"{C_SYS}  [Memory] Error loading memory database: {e}{C_RESET}")
        else:
            print(f"{C_SYS}  [Memory] No previous database found. Starting with a blank slate.{C_RESET}")

    def ambient_leak(self, concept_vector, label="Ambient Leakage"):
        v = concept_vector.detach().cpu().clone().to(torch.float16).view(1, self.hidden_dim)
        if self.memory_tensor is None:
            self.memory_tensor = v
        else:
            self.memory_tensor = torch.cat([self.memory_tensor, v], dim=0)
        print(f"{C_SYS}    [Eternal Memory] {label} vector appended. Total Memories: {self.memory_tensor.shape[0]}{C_RESET}")
        self._save_to_ssd()

    def _save_to_ssd(self):
        if self.memory_tensor is not None:
            with open(self.memory_file, "wb") as f:
                f.write(self.memory_tensor.cpu().numpy().tobytes())

# --- JCross Brain (Pure Vector Operations) ---
class JCrossBrain:
    def __init__(self, jgen_path, device="cpu"):
        self.device = device
        self.layers = []
        self.hidden_dim = None
        self._load_jgen(jgen_path)
        
    def _load_jgen(self, jgen_path):
        print(f"{C_SYS}  [Brain] Loading spatial patterns from {os.path.basename(jgen_path)}...{C_RESET}")
        with open(jgen_path, "rb") as f:
            header_len = int.from_bytes(f.read(4), 'little')
            header_bytes = f.read(header_len)
            header = json.loads(header_bytes.decode('utf-8'))
            self.hidden_dim = header.get("hidden_dim", 4096)
            
            for meta in header["layers"]:
                idx, rows, cols, rank = meta["index"], meta["rows"], meta["cols"], meta["rank"]
                U = torch.frombuffer(f.read(rows * rank * 2), dtype=torch.float16).clone().reshape(rows, rank).to(self.device)
                S = torch.frombuffer(f.read(rank * 2), dtype=torch.float16).clone().reshape(rank).to(self.device)
                V = torch.frombuffer(f.read(rank * cols * 2), dtype=torch.float16).clone().reshape(rank, cols).to(self.device)
                self.layers.append({"U": U, "S": S, "V": V})
                f.read(4096 * 2) # Skip my
                f.read(4096 * 2) # Skip mx
        print(f"{C_SYS}  [Brain] Fully loaded {len(self.layers)} layers into VRAM.{C_RESET}")

    def forward_latent(self, hidden_state: torch.Tensor, role_name="Agent", color_code=C_SYS) -> torch.Tensor:
        """Process latent vector purely through spatial math (No NLP)."""
        h = hidden_state.clone()
        for i, layer in enumerate(self.layers):
            norm_epsilon = 1e-6
            variance = h.pow(2).mean(-1, keepdim=True)
            normed_h = h * torch.rsqrt(variance + norm_epsilon)
            
            z = torch.matmul(normed_h, layer["V"].T)
            z_scaled = z * layer["S"]
            
            main_z = z_scaled[..., :layer["S"].shape[0]//2]
            curr_main = main_z
            for _ in range(2):
                curr_main = torch.nn.functional.silu(main_z * torch.sigmoid(curr_main))
                
            absorbed_back = torch.nn.functional.gelu(z_scaled[..., layer["S"].shape[0]//2:])
            z_out = torch.cat([main_z + curr_main, z_scaled[..., layer["S"].shape[0]//2:] + absorbed_back], dim=-1)
            
            out = torch.matmul(z_out, layer["U"].T)
            h = h + out
            
            # Print numerical trace instead of language
            if i % 10 == 0:
                leak_vals = h[0, :6].cpu().float().numpy()
                formatted_leak = " ".join([f"{v:>7.3f}" for v in leak_vals])
                time.sleep(0.005)
                sys.stdout.write(f"{color_code}[{role_name} | L{i:03d}] {formatted_leak} ...{C_RESET}\n")
                sys.stdout.flush()
                
        return h

def purge_memory():
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"=== Initiating Verantyx Pure JCross Telepathy Swarm ===")
    
    # Model definitions
    worker_jgen = "/Users/motonishikoudai/verantyx-cli/cli/gemma_12b_generative.jgen"
    commander_jgen = "/Users/motonishikoudai/verantyx-cli/cli/commander_12b_rank1024.jgen"
    
    # Initialize Memory
    memory_bank = TelepathicMemoryBank(memory_file="/Users/motonishikoudai/verantyx-cli/my_clone.memory", hidden_dim=4096)
    
    print(f"\n{C_SYS}[System] Waiting for User Request (Telepathic Injection)...{C_RESET}")
    user_input = input("User Request > ")
    
    # Mocking initial vector generation for user input (Normally done via Encoder)
    torch.manual_seed(hash(user_input) % 10000)
    task_vector = torch.randn(1, 4096, dtype=torch.float16, device=device)
    memory_bank.diffuse_thought(task_vector, intensity=1.0, flag_label="Initial User Task", agent_id=0)
    
    # --- PHASE 1: WORKER TELEPATHY LOOP (No NLP) ---
    print(f"\n>>> PHASE 1: Worker Telepathic Discussion (Numerical Matrix)")
    print("\n--- [Phase 1: Worker Synthesis] ---")
    current_thought = task_vector
    for worker_id in range(1, thinking_depth + 1):
        start = time.time()
        print(f"{C_WORKER}  [Worker {worker_id}] Processing ambient context...{C_RESET}")
        
        # 1. ワーカーは共有空間（Ambient Vector）を感じ取り、それを起点に思考を深める
        ambient_context = memory_bank.ambient_vector.to(device) if memory_bank.ambient_vector is not None else current_thought
        
        # 2. ワーカーのニューラル伝播
        current_thought = worker_brain.forward_latent(ambient_context, role_name=f"Worker {worker_id}", color_code=C_WORKER)
        
        # 3. 思考の波紋を空間に漏れ出させる
        memory_bank.diffuse_thought(current_thought, intensity=0.5, flag_label=f"Worker {worker_id} Partial Consensus", agent_id=worker_id)
        
        print(f"{C_WORKER}    -> Synthesis completed in {time.time()-start:.2f}s.{C_RESET}")
        
    worker_consensus = current_thought.clone()
    print(f"\n{C_SYS}[System] Workers reached consensus (Vector Form).{C_RESET}")
    
    # --- PHASE 2: COMMANDER OVERSEEING ---
    print(f"\n>>> PHASE 2: Commander Overseeing & Translation Check")
    start = time.time()
    print(f"{C_CMDR}  [Commander] Distilling swarm consensus into execution intent...{C_RESET}")
    # コマンダーも共有空間（最終的なWorkerたちの空気感）を受け取って最終意図を決定する
    final_context = memory_bank.ambient_vector.to(device)
    cmdr_intent = commander_brain.forward_latent(final_context, role_name="Commander", color_code=C_CMDR)
    memory_bank.diffuse_thought(cmdr_intent, intensity=2.0, flag_label="Commander Draft Intent", agent_id=99)
    
    # --- PHASE 3: VETO (拒否権) TRIGGER CHECK ---
    # Compare Commander's intent with the pure Worker consensus
    similarity = torch.nn.functional.cosine_similarity(cmdr_intent, worker_consensus).mean().item()
    print(f"\n{C_SYS}[System] Calculating Semantic Drift (Sim: {similarity:.4f})...{C_RESET}")
    
    # Simulation: Commander attempts to translate intent to natural language to report to the user
    print(f"{C_CMDR}  [Commander] Preparing to translate final decision to natural language for User...{C_RESET}")
    time.sleep(1)
    
    threshold = 0.85 # High similarity required to pass without veto
    if similarity < threshold:
        print(f"\n{C_ALERT}[VETO TRIGGERED] Commander's intent significantly drifted from the Workers' pure consensus (Sim < {threshold})!{C_RESET}")
        print(f"{C_ALERT}[VETO TRIGGERED] Workers sensed hallucination or omission via Eternal Memory.{C_RESET}")
        print(f"{C_ALERT}[VETO TRIGGERED] Natural language generation HALTED. Re-routing back to Matrix...{C_RESET}")
    else:
        print(f"\n{C_SYS}[System] Consensus Verified. No deception detected. Natural language generation authorized.{C_RESET}")
        print(f"{C_CMDR}  [Commander (NLP)] The task has been successfully processed based on the vector agreement.{C_RESET}")

    print("\n=== Pure Telepathy Loop Concluded ===")

if __name__ == "__main__":
    main()
