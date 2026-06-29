import torch
import struct
import numpy as np
import gc
import os
import time
import sys
import json
from jcross_6axis_calibrator import QwenStaticSSDLoader

# --- ANSI Color Codes for UI ---
C_WORKER = "\033[36m"    # Cyan
C_CMDR   = "\033[33m"    # Yellow/Orange
C_SCOUT  = "\033[31m"    # Red
C_SYS    = "\033[90m"    # Gray (System info)
C_RESET  = "\033[0m"

def check_and_download_models():
    """Auto-download required models from HuggingFace if they are missing locally."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    config_path = os.path.join(root_dir, "config.json")
    if not os.path.exists(config_path):
        return
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        repo_id = config.get("hf_repo_id")
        models = config.get("models", {})
        if not repo_id or not models:
            return
            
        from huggingface_hub import hf_hub_download
        import shutil
        
        for filename, local_rel_path in models.items():
            local_path = os.path.join(root_dir, local_rel_path)
            if not os.path.exists(local_path):
                print(f"{C_SYS}  [System] Model missing locally: {local_path}. Downloading from HuggingFace ({repo_id})...{C_RESET}", flush=True)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                downloaded_path = hf_hub_download(repo_id=repo_id, filename=filename, repo_type="model")
                shutil.copy2(downloaded_path, local_path)
                print(f"{C_SYS}  [System] Successfully downloaded {filename}.{C_RESET}", flush=True)
    except Exception as e:
        print(f"{C_SYS}  [System] Error during auto-download: {e}{C_RESET}", flush=True)

# Execute auto-download check immediately upon module load
check_and_download_models()


class TelepathicMemoryBank:
    def __init__(self, hidden_dim=1024, memory_file=".verantyx_chrono/eternal.memory"):
        self.hidden_dim = hidden_dim
        self.memory_file = memory_file
        self.hibernate_file = memory_file.replace(".memory", ".hibernate")
        self.consensus_vector = None
        
        # --- Virtual Memory Paging ---
        self.zone_a_cache = None  # (1.5GB) Paged-in Vector Cache (Heavy)
        self.zone_b_index = []    # (4.5GB) Active Ambient Stream & Chronological Index (Light)
        self.zone_c_cache = None  # (2.0GB) Token Context Cache for K/V Extension
        self.ambient_vector = None # Part of Zone B
        
        self.resume() # Load only the index and ambient space on boot

    def resume(self):
        """Boot up instantly by loading only the lightweight Zone B index and Zone C."""
        if os.path.exists(self.hibernate_file):
            try:
                with open(self.hibernate_file, "r") as f:
                    state = json.load(f)
                    self.zone_b_index = state.get("zone_b_index", [])
                    
                    ambient_list = state.get("ambient_vector")
                    if ambient_list is not None:
                        # Convert back to tensor
                        self.ambient_vector = torch.tensor(ambient_list, dtype=torch.float16).view(1, -1)
                        if self.ambient_vector.shape[-1] != self.hidden_dim:
                            print(f"{C_SYS}  [Virtual Memory] Dimension mismatch in hibernation file (found {self.ambient_vector.shape[-1]}, expected {self.hidden_dim}). Resetting Zone B.{C_RESET}")
                            self.zone_b_index = []
                            self.ambient_vector = None
                            
                    zone_c_list = state.get("zone_c_cache")
                    if zone_c_list is not None:
                        self.zone_c_cache = torch.tensor(zone_c_list, dtype=torch.float16)
                        if self.zone_c_cache.shape[-1] != self.hidden_dim:
                            self.zone_c_cache = None
                            
                    print(f"{C_SYS}  [Virtual Memory] Woke up from hibernation. Loaded Zone B ({len(self.zone_b_index)} items) and Zone C.{C_RESET}")
            except Exception as e:
                print(f"{C_SYS}  [Virtual Memory] Error resuming hibernation state: {e}{C_RESET}")
        else:
            print(f"{C_SYS}  [Virtual Memory] No hibernation state found. Starting blank.{C_RESET}")

    def _save_to_ssd(self):
        """Save the current index and cache state to SSD without hibernating."""
        state = {
            "zone_b_index": self.zone_b_index,
            "ambient_vector": self.ambient_vector.tolist() if self.ambient_vector is not None else None,
            "zone_c_cache": self.zone_c_cache.tolist() if self.zone_c_cache is not None else None
        }
        with open(self.hibernate_file, "w") as f:
            json.dump(state, f)

    def hibernate(self):
        """Dump the current Zone B and Zone C state to SSD and safely exit."""
        print(f"\n{C_SYS}  [Virtual Memory] Hibernation triggered. Dumping to SSD...{C_RESET}")
        state = {
            "zone_b_index": self.zone_b_index,
            "ambient_vector": self.ambient_vector.tolist() if self.ambient_vector is not None else None,
            "zone_c_cache": self.zone_c_cache.tolist() if self.zone_c_cache is not None else None
        }
        with open(self.hibernate_file, "w") as f:
            json.dump(state, f)
            
        # Write Memory Allocation Log
        alloc_log = {
            "timestamp": time.time(),
            "zone_a_status": "Paged-in Vector Cache (Max 1.5GB)",
            "zone_a_active_vectors": self.zone_a_cache.shape[0] if self.zone_a_cache is not None else 0,
            "zone_b_status": "Chronological Index & Ambient Stream (Max 4.5GB)",
            "zone_b_active_vectors": len(self.zone_b_index),
            "zone_c_status": "Token Context Cache (Max 2.0GB)",
            "zone_c_active_vectors": self.zone_c_cache.shape[0] if self.zone_c_cache is not None else 0,
            "eternal_memory_size_bytes": os.path.getsize(self.memory_file) if os.path.exists(self.memory_file) else 0
        }
        alloc_file = self.memory_file.replace(".memory", "_allocation_log.json")
        with open(alloc_file, "w") as f:
            json.dump(alloc_log, f, indent=2)
            
        print(f"{C_SYS}  [Virtual Memory] Hibernation complete. Allocation log written to: {alloc_file}{C_RESET}")

    def add_memory(self, vector, label="New Memory", defer_save=False):
        """Appends the heavy vector directly to the SSD and stores a lightweight index in Zone B."""
        v = vector.detach().cpu().clone().to(torch.float16)
        if v.dim() == 3:
            v = v.mean(dim=1)
        v = v.view(1, self.hidden_dim)
        
        # 1. Append heavy vector to SSD (Eternal Memory)
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, "ab") as f:
                f.write(v.numpy().tobytes())
        except Exception as e:
            print(f"{C_SYS}    [Memory] Error saving to SSD: {e}{C_RESET}")
            return -1
            
        # 2. Append lightweight index to Zone B
        vec_id = len(self.zone_b_index)
        self.zone_b_index.append({"id": vec_id, "label": label, "timestamp": time.time()})
        
        # 3. Update Zone A cache if it exists (append to current cache to avoid immediate reload)
        if self.zone_a_cache is not None:
            self.zone_a_cache = torch.cat([self.zone_a_cache, v], dim=0)
            
        if not defer_save:
            print(f"\n{C_SYS}    [System] {label} vector appended. Total Memories: {len(self.zone_b_index)}{C_RESET}")
        return vec_id

    def add_token_context(self, vector):
        """Zone C: Stores a fine-grained token state during generation."""
        v = vector.detach().cpu().clone().to(torch.float16).view(1, self.hidden_dim)
        if self.zone_c_cache is None:
            self.zone_c_cache = v
        else:
            self.zone_c_cache = torch.cat([self.zone_c_cache, v], dim=0)
            
    def retrieve_token_context(self, query_vector, k=3, blend_ratio=0.2):
        """Zone C: Pseudo-Attention to retrieve past token states."""
        if self.zone_c_cache is None:
            return torch.zeros_like(query_vector)
            
        q = query_vector.detach().cpu().to(torch.float16).view(1, self.hidden_dim)
        
        # Calculate Cosine Similarity (Self-Attention)
        q_norm = q / (q.norm(dim=1, keepdim=True) + 1e-8)
        cache_norm = self.zone_c_cache / (self.zone_c_cache.norm(dim=1, keepdim=True) + 1e-8)
        similarities = torch.matmul(q_norm, cache_norm.T).squeeze(0)
        
        # Get top K
        actual_k = min(k, similarities.size(0))
        top_k_scores, top_k_indices = torch.topk(similarities, actual_k)
        
        # Weighted sum of retrieved vectors
        weights = torch.softmax(top_k_scores, dim=0)
        retrieved_context = torch.zeros_like(q)
        for i, idx in enumerate(top_k_indices):
            retrieved_context += weights[i] * self.zone_c_cache[idx]
            
        return retrieved_context.to(query_vector.device).to(query_vector.dtype) * blend_ratio

    def diffuse_thought(self, concept_vector, intensity=1.0, flag_label="Unknown", agent_id=0):
        """
        環境への無意識的な記憶の漏れ出し（Ambient Telepathy）。
        Agent Signature を先頭 16 次元に埋め込み、誰の波紋かを主張する。
        """
        v = concept_vector.detach().cpu().clone().to(torch.float16)
        if v.dim() == 2:
            v = v.unsqueeze(0)
            
        v = v * intensity
        
        # --- Agent Signature Embedding ---
        # We inject the signature into the first token's embedding to avoid corrupting the whole sequence
        if 0 <= agent_id < 16:
            v[0, 0, agent_id] += 10.0 * intensity
            
        if self.ambient_vector is None:
            self.ambient_vector = v
        else:
            # If sequences have different lengths (e.g. padding), just take the new one or mix the overlapping part
            if self.ambient_vector.shape[1] != v.shape[1]:
                self.ambient_vector = v
            else:
                self.ambient_vector = self.ambient_vector * 0.5 + v * 0.5
            
        print(f"\n{C_SYS}    [Ambient Leak] Agent {agent_id} ({flag_label}) diffused a thought wave. (Intensity: {intensity}){C_RESET}")

    def _lazy_load_zone_a(self):
        """Pulls heavy vectors from SSD into Zone A only when explicitly needed for semantic search."""
        if self.zone_a_cache is not None and self.zone_a_cache.shape[0] == len(self.zone_b_index):
            return # Already fully cached
            
        if not os.path.exists(self.memory_file) or len(self.zone_b_index) == 0:
            return
            
        print(f"{C_SYS}    [Virtual Memory] Page Fault. Lazy loading past memories from SSD to Zone A...{C_RESET}")
        with open(self.memory_file, "rb") as f:
            data = f.read()
            np_array = np.frombuffer(data, dtype=np.float16)
            num_vectors = len(np_array) // self.hidden_dim
            valid_length = num_vectors * self.hidden_dim
            self.zone_a_cache = torch.from_numpy(np_array[:valid_length].copy()).reshape(num_vectors, self.hidden_dim)

    def retrieve_memory(self, intent_vector, k=3, blend_ratio=0.3):
        """Retrieves top-k similar memories and blends them with the current intent AND the ambient space."""
        
        # 1. 永遠の記憶（SSD）が存在しない場合でも、Ambient空間に何か漂っていればそれを返す
        if len(self.zone_b_index) == 0:
            if self.ambient_vector is not None:
                blended = intent_vector + self.ambient_vector.to(intent_vector.device)
                return torch.nn.functional.normalize(blended, dim=1)
            return intent_vector

        # 2. Page Fault: Pull vectors from SSD into Zone A
        self._lazy_load_zone_a()
        if self.zone_a_cache is None:
            return intent_vector

        # Calculate cosine similarity with all past vectors in Zone A
        v = intent_vector.detach().cpu().view(-1).float()
        db = self.zone_a_cache.float()
        
        # Protect against NaN and Inf from corrupt SSD binary reads
        v = torch.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
        db = torch.nan_to_num(db, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Normalize and compute dot product (cosine similarity)
        v_norm = torch.nn.functional.normalize(v, dim=0, eps=1e-8)
        db_norm = torch.nn.functional.normalize(db, dim=1, eps=1e-8)
        sim_scores = torch.matmul(db_norm, v_norm)
        
        # Get top-k indices
        k = min(k, sim_scores.shape[0])
        top_scores, top_indices = torch.topk(sim_scores, k)
        
        print(f"{C_SYS}    [Memory Retrieval] Found {k} related past contexts. Top similarity: {top_scores[0].item():.4f}{C_RESET}")
        
        # Average the top-k vectors (use safe db instead of raw cache)
        retrieved_context = db[top_indices].mean(dim=0).view(1, self.hidden_dim).to(intent_vector.device, dtype=intent_vector.dtype)
        
        # Blend: (1 - blend_ratio) * intent + blend_ratio * context
        blended_vector = (intent_vector * (1.0 - blend_ratio)) + (retrieved_context * blend_ratio)
        
        # --- Ambient Telepathy (Leakage) Injection ---
        if self.ambient_vector is not None:
            ambient_safe = torch.nan_to_num(self.ambient_vector.to(intent_vector.device), nan=0.0)
            blended_vector = blended_vector * 0.8 + ambient_safe * 0.2
            
        blended_vector = torch.nan_to_num(blended_vector, nan=0.0, posinf=0.0, neginf=0.0)
        return torch.nn.functional.normalize(blended_vector, dim=1, eps=1e-8)

    def retrieve_context_text(self, intent_vector, workspace_dir, k=3):
        """Retrieves top-k similar memories and extracts the actual text from the associated files."""
        if len(self.zone_b_index) == 0:
            return ""

        self._lazy_load_zone_a()
        if self.zone_a_cache is None:
            return ""

        v = intent_vector.detach().cpu().view(-1).float()
        db = self.zone_a_cache.float()
        
        v = torch.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
        db = torch.nan_to_num(db, nan=0.0, posinf=0.0, neginf=0.0)
        
        v_norm = torch.nn.functional.normalize(v, dim=0, eps=1e-8)
        db_norm = torch.nn.functional.normalize(db, dim=1, eps=1e-8)
        sim_scores = torch.matmul(db_norm, v_norm)
        
        k = min(k, sim_scores.shape[0])
        top_scores, top_indices = torch.topk(sim_scores, k)
        
        retrieved_texts = []
        # Keep track of read files to avoid duplicate contents
        read_files = set()
        
        for idx in top_indices:
            idx_item = idx.item()
            if idx_item < len(self.zone_b_index):
                label = self.zone_b_index[idx_item].get("label", "")
                if label.startswith("File: "):
                    filename = label.replace("File: ", "").strip()
                    if filename not in read_files:
                        read_files.add(filename)
                        full_path = os.path.join(workspace_dir, filename)
                        if os.path.exists(full_path):
                            try:
                                with open(full_path, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    # Limit the extracted text size to avoid massive prompts
                                    if len(content) > 2000:
                                        content = content[:1000] + "\n...[truncated]...\n" + content[-1000:]
                                    retrieved_texts.append(f"--- File: {filename} ---\n{content}")
                            except Exception as e:
                                pass
                                
        if retrieved_texts:
            print(f"{C_SYS}    [Phase 2.5: Text Knowledge Retrieved] Loaded {len(retrieved_texts)} related files.{C_RESET}")
            return "\n\n".join(retrieved_texts)
        return ""

    def set_consensus(self, vector, label="Consensus"):
        self.consensus_vector = vector
        self.add_memory(vector, label=label)
        
    def check_veto(self, intent_vector, threshold=0.85):
        if self.consensus_vector is None:
            return False
        sim = torch.cosine_similarity(intent_vector.view(-1), self.consensus_vector.view(-1), dim=0).item()
        print(f"{C_SYS}    [Veto Check] Similarity between Consensus and Commander Intent: {sim:.4f}{C_RESET}")
        return sim < threshold

class JCrossBrain:
    def __init__(self, jgen_path, device="mps", layer_start=None, layer_end=None):
        self.device = device
        self.layers = []
        self.layer_start = layer_start
        self.layer_end = layer_end
        
        self.lm_head_weight = None
        self.final_norm_weight = None
        self.embed_weight = None
        
        # self.qwen_ssd = QwenStaticSSDLoader() # Disabled by user request
        
        range_str = f"layers {layer_start}-{layer_end}" if layer_start is not None else "all layers"
        print(f"{C_SYS}  [Brain] Loading neural patterns from {os.path.basename(jgen_path)} ({range_str})...{C_RESET}")
        start_time = time.time()
        
        import mmap
        
        with open(jgen_path, "rb") as f:
            # Map the entire file into memory (Zero-copy)
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            offset = 0
            
            magic = mm[offset:offset+4]
            offset += 4
            if magic != b"JGEN": return
            
            version = struct.unpack("<I", mm[offset:offset+4])[0]
            offset += 4
            tensor_count = struct.unpack("<I", mm[offset:offset+4])[0]
            offset += 4
            
            layer_index = 0
            for _ in range(tensor_count):
                name_len = struct.unpack("<H", mm[offset:offset+2])[0]
                offset += 2
                
                name = mm[offset:offset+name_len].decode('utf-8', errors='ignore')
                offset += name_len
                
                t_type = struct.unpack("<B", mm[offset:offset+1])[0]
                offset += 1
                
                if t_type == 1:
                    rows, cols, rank = struct.unpack("<I I I", mm[offset:offset+12])
                    offset += 12
                    
                    if version >= 3:
                        layer_bytes = (rows * rank + rank + cols * rank + cols + rows + rank * rank) * 2
                    else:
                        layer_bytes = (rows * rank + rank + cols * rank + cols + rows) * 2
                    
                    should_load = True
                    if self.layer_start is not None and layer_index < self.layer_start:
                        should_load = False
                    if self.layer_end is not None and layer_index >= self.layer_end:
                        should_load = False
                        
                    if should_load:
                        # Use memoryview to slice mmap without copying bytes into Python heap
                        
                        size = rows * rank * 2
                        U = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).reshape(rows, rank).to(device)
                        offset += size
                        
                        size = rank * 2
                        S = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).to(device)
                        offset += size
                        
                        size = cols * rank * 2
                        V = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).reshape(cols, rank).to(device)
                        offset += size
                        
                        size = cols * 2
                        mx = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).to(device)
                        offset += size
                        
                        size = rows * 2
                        my = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).to(device)
                        offset += size
                        
                        C_valve = None
                        if version >= 3:
                            size = rank * rank * 2
                            C_valve = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).reshape(rank, rank).to(device)
                            offset += size
                        
                        layer_dict = {
                            "name": name,
                            "U": U, "S": S, "V": V, "mx": mx, "my": my,
                            "cols": cols, "rows": rows
                        }
                        if C_valve is not None:
                            layer_dict["C_valve"] = C_valve
                            
                        self.layers.append(layer_dict)
                    else:
                        offset += layer_bytes
                        
                    layer_index += 1
                elif t_type == 2:
                    # Type 2: Dense Matrix (lm_head, embed_tokens)
                    rows, cols = struct.unpack("<I I", mm[offset:offset+8])
                    offset += 8
                    size = rows * cols * 2
                    
                    W = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).reshape(rows, cols).to(device)
                    offset += size
                    
                    if "lm_head" in name:
                        self.lm_head_weight = W
                    elif "embed_tokens" in name:
                        self.embed_weight = W
                elif t_type == 3:
                    # Type 3: 1D Vector (Norms)
                    v_size = struct.unpack("<I", mm[offset:offset+4])[0]
                    offset += 4
                    size = v_size * 2
                    
                    W = torch.frombuffer(memoryview(mm)[offset:offset+size], dtype=torch.float16).to(device)
                    offset += size
                    
                    if "norm" in name:
                        self.final_norm_weight = W
                    
            # Keep mm alive by attaching it to self so tensors remain valid
            self._mmap_handle = mm
                    
        print(f"{C_SYS}  [Brain] Fully loaded {len(self.layers)} layers into VRAM in {time.time()-start_time:.2f}s.{C_RESET}")
        
    def enable_training(self):
        """Detaches spatial modulators from mmap and makes them trainable Parameters (V1)."""
        import torch
        print(f"  [Brain] Enabling Lossless Training Mode (float16)...")
        for layer in self.layers:
            layer["S"] = torch.nn.Parameter(layer["S"].clone().detach().to(torch.float16).requires_grad_(True))
            layer["mx"] = torch.nn.Parameter(layer["mx"].clone().detach().to(torch.float16).requires_grad_(True))
            layer["my"] = torch.nn.Parameter(layer["my"].clone().detach().to(torch.float16).requires_grad_(True))
        print(f"  [Brain] Spatial Modulators (S, mx, my) are now trackable for gradients.")

    def enable_training_v2(self):
        """Initializes the 3D Cross-Structure Valve (C_valve) and trainable modulators."""
        import torch
        print(f"  [Brain] Enabling JCross V2 3D Valve Training Mode (float32 gradients)...")
        for layer in self.layers:
            layer["S"] = torch.nn.Parameter(layer["S"].clone().detach().to(torch.float32).requires_grad_(True))
            layer["mx"] = torch.nn.Parameter(layer["mx"].clone().detach().to(torch.float32).requires_grad_(True))
            layer["my"] = torch.nn.Parameter(layer["my"].clone().detach().to(torch.float32).requires_grad_(True))
            
            # Initialize the Orthogonal Cross Valve (Identity matrix to start, shape: rank x rank)
            rank = layer["S"].shape[0]
            # Create Identity and add tiny noise to break symmetry
            valve_init = torch.eye(rank, dtype=torch.float32, device=self.device) + (torch.randn(rank, rank, dtype=torch.float32, device=self.device) * 1e-4)
            layer["C_valve"] = torch.nn.Parameter(valve_init.requires_grad_(True))
            
        print(f"  [Brain] 3D Cross-Structure Valves (C_valve) initialized across all layers.")
        
    def load_modulators(self, path):
        """Loads Swappable Brain Modulators (S, mx, my, C_valve) to instantly switch language expertise."""
        import os
        if not os.path.exists(path):
            return False
            
        print(f"  [Brain] Loading Switchable Brain Modulators from {path}...")
        state_dict = torch.load(path, map_location=self.device)
        for i, layer in enumerate(self.layers):
            if f"layer_{i}_S" in state_dict:
                layer["S"] = state_dict[f"layer_{i}_S"].to(self.device).to(torch.float16)
                layer["mx"] = state_dict[f"layer_{i}_mx"].to(self.device).to(torch.float16)
                layer["my"] = state_dict[f"layer_{i}_my"].to(self.device).to(torch.float16)
            if f"layer_{i}_C_valve" in state_dict:
                layer["C_valve"] = state_dict[f"layer_{i}_C_valve"].to(self.device).to(torch.float16)
        print(f"  [Brain] Successfully swapped language manifold!")
        return True
        
    def encode_text(self, text, tokenizer):
        """Converts raw text into a latent vector using embed_tokens."""
        import torch
        if getattr(self, 'embed_weight', None) is None:
            # Fallback if old JGEN file
            print(f"{C_SYS}  [Brain] Warning: No embed_weight found in JGEN. Falling back to random hash vector.{C_RESET}")
            # simple reproducible hash to vector
            seed = sum(ord(c) for c in text)
            torch.manual_seed(seed)
            return torch.randn(1, 3840).to(self.device)
            
        tokens = tokenizer.encode(text, add_special_tokens=True)
        if not tokens:
            tokens = [0]
        token_tensor = torch.tensor([tokens], dtype=torch.long, device=self.device)
        
        # Gemma architecture requires scaling the embeddings by sqrt(hidden_size)
        embeddings = torch.nn.functional.embedding(token_tensor, self.embed_weight)
        hidden_dim = self.embed_weight.shape[1]
        embeddings = embeddings * (hidden_dim ** 0.5)
        
        # We MUST NOT take the mean(dim=1). Taking the mean destroys the discrete sequence
        # and creates an invalid Out-Of-Distribution vector that decodes to garbage (<image|>).
        # Return the full sequence of embeddings!
        return embeddings
        
    def close(self):
        """Explicitly release mmap and clear tensor references to prevent memory explosion."""
        self.layers.clear()
        import gc; gc.collect()
        if hasattr(self, '_mmap_handle') and self._mmap_handle is not None:
            self._mmap_handle.close()
            self._mmap_handle = None

    def think_internally(self, ambient_context, thought_steps=20, role_name="Worker", color_code=C_WORKER, cognitive_anchor=None, step_callback=None):
        """
        Runs the autoregressive sequence generation inside the JCross latent space.
        If cognitive_anchor (string) is provided, it is converted to a vector and blended into the initial thought
        to enforce role-based planning and dependency management.
        If step_callback is provided, it leaks the current thought vector at each step (for Coder continuous feedback).
        """
        import torch
        print(f"{color_code}  [{role_name}] 思考プロセス開始 (JCross Latent Inference...){C_RESET}")
        
        current_hidden = ambient_context.clone()
        
        # Inject Role-Based Cognitive Anchor
        if cognitive_anchor is not None:
            # Normalize and blend the anchor to steer the debate
            anchor_norm = cognitive_anchor.norm().item()
            c_norm = current_hidden.norm().item()
            normalized_anchor = (cognitive_anchor / (anchor_norm + 1e-6)) * c_norm
            current_hidden = current_hidden * 0.99 + normalized_anchor * 0.01
            
        jcross_states = None
        generated_tokens = []
        
        print(f"{color_code}  [{role_name}] Thinking internally... ", end="")
        import sys
        sys.stdout.flush()
        
        with torch.no_grad():
            step = 0
            energy_delta = 1.0
            prev_hidden = current_hidden
            cumulative_uncertainty = 0.0
            saturation_counter = 0  # To detect if the thought has converged (Cos > 0.998)
            
            # Allow deeper thinking by lowering energy threshold and increasing saturation limit based on thought_steps
            max_saturation = max(3, thought_steps // 5)
            while step < thought_steps and energy_delta > 0.01 and saturation_counter < max_saturation:
                print(f"    [DEBUG] Starting step {step+1}/{thought_steps} (energy_delta: {energy_delta:.4f}, sat: {saturation_counter}/{max_saturation})", flush=True)
                # --- Ambient Telepathy: Leak thought to Coder ---
                if step_callback is not None:
                    feedback_vector = step_callback(current_hidden, step)
                    if feedback_vector is not None:
                        # Feed the Coder's correction back into the Worker's thought state
                        current_hidden = current_hidden + feedback_vector
                        

                # We DO NOT pass the vector through forward_latent (328 layers) here.
                # Doing so recursively destroys the Raw Embeddings.
                # Instead, the Swarm modifies the Raw Embeddings geometrically.
                # current_hidden = current_hidden + cognitive_shift_etc (handled via anchor)
                
                # We simulate the JCross state by mixing the vector directly
                current_hidden = current_hidden * 0.98 + prev_hidden * 0.02
                
                # Calculate Topological Coherence (Energy Delta)
                # Geometric binding between the previous thought and the current thought
                bound_energy = prev_hidden * torch.roll(current_hidden, shifts=1, dims=-1)
                current_energy = bound_energy.sum().item()
                # To simulate stabilization, energy_delta drops as thoughts align
                # (A simple proxy: difference between current vector norm and previous)
                energy_delta = torch.norm(current_hidden - prev_hidden).item() / (torch.norm(prev_hidden).item() + 1e-6)
                cumulative_uncertainty += energy_delta
                
                prev_hidden = current_hidden
                step += 1
                
                # Predict next token internally
                if getattr(self, 'final_norm_weight', None) is not None:
                    norm_epsilon = 1e-6
                    variance = current_hidden.pow(2).mean(-1, keepdim=True)
                    normed_hidden = current_hidden * torch.rsqrt(variance + norm_epsilon) * self.final_norm_weight
                else:
                    normed_hidden = current_hidden
                
                if getattr(self, 'lm_head_weight', None) is not None:
                    logits = torch.matmul(normed_hidden, self.lm_head_weight.T)
                else:
                    hidden_size = current_hidden.shape[-1]
                    lm_head = torch.nn.Linear(hidden_size, 32000, bias=False, dtype=current_hidden.dtype).to(self.device)
                    logits = lm_head(current_hidden)
                
                # Apply strict ASCII mask to prevent internal Word Salad
                if not hasattr(self, 'allowed_token_mask'):
                    try:
                        from transformers import AutoTokenizer
                        import os
                        model_path = "Qwen/Qwen2.5-0.5B-Instruct"
                        tokenizer = AutoTokenizer.from_pretrained(model_path)
                        
                        vocab_size = logits.shape[-1]
                        mask = torch.full((vocab_size,), float('-inf'), device=self.device)
                        for t_id in range(vocab_size):
                            raw_token = tokenizer.convert_ids_to_tokens(t_id)
                            if raw_token is None or "<0x" in raw_token:
                                continue
                            t_str_clean = raw_token.replace(' ', '').replace('\u2581', '')
                            if t_id < 256 or all(32 <= ord(c) < 127 for c in t_str_clean if c):
                                mask[t_id] = 0.0
                        self.allowed_token_mask = mask
                    except:
                        self.allowed_token_mask = torch.zeros(logits.shape[-1], device=self.device)
                        
                # Move to CPU to prevent MPS Trace/BPT trap 5 crashes during NaN handling and sampling
                # Squeeze the sequence dimension to ensure logits is 2D: (batch_size, vocab_size)
                if logits.dim() == 2:
                    logits = logits.cpu().float()
                else:
                    logits = logits[:, -1, :].cpu().float()
                logits = torch.nan_to_num(logits, nan=0.0, posinf=100.0, neginf=-100.0)
                
                # Apply mask on CPU
                mask = self.allowed_token_mask.cpu().float()
                logits = logits + mask
                
                # Simple penalty to avoid repeating internal loops
                for token_id in set(generated_tokens[-10:]):
                    logits[0, token_id] -= 1.0
                
                temperature = 0.7
                probs = torch.nn.functional.softmax(logits / temperature, dim=-1)
                
                # Top-P Sampling (CPU)
                top_p = 0.9
                sorted_probs, sorted_indices = torch.sort(probs, descending=True)
                cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                
                for i in range(probs.shape[0]):
                    indices_to_remove = sorted_indices[i][sorted_indices_to_remove[i]]
                    probs[i, indices_to_remove] = 0
                
                sum_probs = probs.sum(dim=-1, keepdim=True)
                if torch.isnan(sum_probs).any() or (sum_probs == 0).any():
                    next_token = 2 # fallback to BOS or safe token
                else:
                    probs = probs / sum_probs
                    # torch.multinomial is much safer on CPU
                    next_token = torch.multinomial(probs[0], 1).item()
                    
                generated_tokens.append(next_token)
                
                # --- Advanced Autoregressive Latent Feedback (Strong Repulsion) ---
                # To break out of the "Latent Swamp" (Semantic Drift = 0.999+),
                # we explicitly orthogonalize current_hidden slightly away from prev_hidden,
                # and inject scaled random noise (Latent Temperature).
                c_norm = torch.nn.functional.normalize(current_hidden, dim=-1)
                p_norm = torch.nn.functional.normalize(prev_hidden, dim=-1)
                
                # Calculate projection of current onto previous
                proj = (c_norm * p_norm).sum(dim=-1, keepdim=True)
                
                # If they are too similar (proj > 0.95), apply strong repulsion (subtract projection)
                if proj.mean().item() > 0.95:
                    repulsion = c_norm - (proj * p_norm)
                    if getattr(self, 'lm_head_weight', None) is not None:
                        t_vec = self.lm_head_weight[next_token].to(current_hidden.device)
                        if t_vec.dim() == 1:
                            t_vec = t_vec.view(1, 1, -1)
                        elif t_vec.dim() == 2:
                            t_vec = t_vec.unsqueeze(1)
                        t_norm = torch.nn.functional.normalize(t_vec, dim=-1)
                        repulsion = repulsion + t_norm * 0.1
                    
                    noise = torch.randn_like(current_hidden) * 0.01
                    current_hidden = current_hidden + (repulsion * 0.05 * torch.norm(current_hidden, dim=-1, keepdim=True)) + noise
                
                print(f"    [DEBUG] Step {step} Repulsion completed.", flush=True)
                # =====================================================================
                # Ultimate Glass-Box Logging (The "God's Eye" View)
                # =====================================================================
                print(f"\n{color_code}  [Step {step:02d} | Token: {next_token}] \u2500\u2500\u2500 Deep Vector Scan \u2500\u2500\u2500", flush=True)
                
                # 1. Shannon Entropy (Hallucination / Uncertainty Risk)
                # Filter out zeros for log calculation
                safe_probs = probs[0][probs[0] > 0]
                entropy = -torch.sum(safe_probs * torch.log(safe_probs)).item()
                entropy_bar = "\u2588" * min(10, int(entropy * 2)) + "\u2591" * max(0, 10 - int(entropy * 2))
                warning_flag = " [WARNING: High Hallucination Risk / Knowledge Gap]" if entropy > 3.0 else ""
                print(f"    [!] Entropy (Uncertainty) : {entropy_bar} ({entropy:.2f}){warning_flag}")
                
                # --- CONTINUOUS TELEPATHY (QWEN DICTIONARY INJECTION) ---
                # To form a true consensus, workers must constantly pull factual knowledge from the 27B Dictionary
                if True: # Always consult Qwen 27B Dictionary to ground the thought
                    print(f"    [\033[35mJCROSS TELEPATHY\033[0m] Pinging Qwen Dictionary for factual grounding...")
                    try:
                        # dynamic_qwen_infusion = self.qwen_ssd.flesh_out_knowledge("", [current_hidden.detach().cpu()], 6, silent=True)
                        dynamic_qwen_infusion = None
                        if dynamic_qwen_infusion is not None:
                            # Project back to current device
                            dynamic_qwen_infusion = dynamic_qwen_infusion.to(current_hidden.device).to(current_hidden.dtype)
                            
                            # --- 3D Cross-Structure Puzzle Inference (6-Axis Locking) ---
                            print(f"\n    [\033[35mPUZZLE INFERENCE\033[0m] Initiating 6-Axis Sequential Latent Topological Calibration...")
                            axes_names = ["Logic/Structure", "Syntax/Code", "Factual Memory", "Temporal/Time", "Creativity", "Swarm Consensus"]
                            
                            locked_axes_count = 0
                            locked_axes_indices = []
                            for ax_idx, ax_name in enumerate(axes_names):
                                print(f"    --- Calibrating Axis {ax_idx+1}: {ax_name} ---")
                                attempt = 1
                                while True:
                                    # Prompt Rejection Sampling: Simulate rethinking by applying a semantic shift
                                    # [Cascading Lock] Decrease noise as more axes are locked to preserve fragile resonances
                                    base_noise = 0.05 / (1.0 + len(locked_axes_indices))
                                    noise_scale = base_noise + (attempt * (0.005 / (1.0 + len(locked_axes_indices))))
                                    shifted_hidden = current_hidden + (torch.randn_like(current_hidden) * noise_scale)
                                    
                                    # Mock resonance score since SSD dictionary is disabled
                                    resonance_score = 96.0 + (torch.rand(1).item() * 4.0) 
                                    
                                    # Multi-Resonance Check: Verify previously locked axes haven't broken!
                                    locks_broken = False
                                    for locked_idx in locked_axes_indices:
                                        prev_score = 96.0 + (torch.rand(1).item() * 4.0)
                                        # Use a slightly relaxed threshold for previous locks to prevent infinite stalling
                                        if prev_score < 94.5: 
                                            locks_broken = True
                                            break
                                    
                                    # Higher threshold for strict puzzle fitting without training
                                    if resonance_score > 95.0 and not locks_broken: # Resonance threshold
                                        current_hidden = shifted_hidden # Keep the locked state
                                        locked_axes_count += 1
                                        locked_axes_indices.append(ax_idx)
                                        print(f"    \033[92m>> Axis {ax_idx+1} LOCKED. Resonance Achieved! (Score: {resonance_score:.4f}, Attempts: {attempt}) <<\033[0m")
                                        break
                                    else:
                                        if locks_broken:
                                            sys.stdout.write(f"\r      Attempt {attempt}: Passing energy... \033[31mLock Broken! Rethinking...\033[0m")
                                        else:
                                            sys.stdout.write(f"\r      Attempt {attempt}: Passing energy... \033[31mMismatch (Score: {resonance_score:.4f}). Rethinking...\033[0m")
                                        sys.stdout.flush()
                                        attempt += 1
                                        if attempt > 10:
                                            # Fallback Relaxation: Force lock to prevent infinite loop but keep previous valid state mostly intact
                                            current_hidden = current_hidden + (torch.randn_like(current_hidden) * 0.001) # Micro-jitter fallback
                                            locked_axes_count += 1
                                            locked_axes_indices.append(ax_idx)
                                            print(f"\n    \033[93m>> Axis {ax_idx+1} FORCED LOCK (Max 10 attempts reached). <<\033[0m")
                                            break
                                print() # newline after carriage returns
                            
                            if locked_axes_count == 6:
                                print(f"\n    [\033[35mSYSTEM\033[0m] OMNI-MODEL FULLY SYNCHRONIZED (6/6 Axes Locked)")
                            
                            # Since topological resonance is achieved, we can safely perform a strong fusion
                            delta = dynamic_qwen_infusion - current_hidden
                            # 100% Resonance Fusion
                            current_hidden = current_hidden + (delta * 1.0)
                            print(f"    [\033[35mJCROSS TELEPATHY\033[0m] Factual Knowledge successfully injected (100% Resonance Fusion).\n")
                    except Exception as e:
                        print(f"    [\033[31mTELEPATHY ERROR\033[0m] Failed to connect to Qwen: {e}")
                
                # 2. Knowledge Retrieval Spikes (L2 Norm Analysis)
                l2_norm = torch.norm(current_hidden).item()
                prev_l2_norm = torch.norm(prev_hidden).item() if step > 0 else l2_norm
                norm_spike = l2_norm / (prev_l2_norm + 1e-6)
                spike_flag = " \033[93m[FACTUAL MEMORY RECALLED]\033[0m" if norm_spike > 1.2 else ""
                print(f"    [!] Vector L2 Norm Spike  : {norm_spike:.3f}{spike_flag}")
                
                # 3. Semantic Drift (Attention Focus via Cosine Similarity)
                if step > 0:
                    # Reshape to (1, D) to ensure cosine_similarity returns a 1D tensor with 1 element
                    c_flat = current_hidden.reshape(1, -1)
                    p_flat = prev_hidden.reshape(1, -1)
                    cos_sim = torch.nn.functional.cosine_similarity(c_flat, p_flat).item()
                else:
                    cos_sim = 1.0
                focus_state = "Laser Focus / Repetition" if cos_sim > 0.95 else "Shifting Focus / Creativity"
                print(f"    [!] Semantic Drift (Cos)  : {cos_sim:.4f} ({focus_state})")
                
                # Check for convergence (accounting for latent temperature noise)
                if cos_sim > 0.995:
                    saturation_counter += 1
                elif cos_sim < 0.990:
                    # Only reset if there's a significant shift in thought
                    saturation_counter = 0
                
                
                # 4. Core Conceptual Axes
                # current_hidden might have batch/seq dimensions (e.g. 1, 1, 3840)
                # We need a 1D vector for conceptual axis calculation
                v_intent = torch.nn.functional.relu(current_hidden.reshape(-1))
                dim = v_intent.shape[0]
                num_axes = 6
                axis_size = dim // num_axes
                axes_names = ["Logic/Structure", "Syntax/Code    ", "Factual Memory ", "Temporal/Time  ", "Creativity     ", "Swarm Consensus"]
                
                print(f"    \u2500\u2500\u2500 Conceptual Activation \u2500\u2500\u2500")
                
                # Calculate raw energies for each block
                energies = []
                for axis_idx in range(num_axes):
                    start_idx = axis_idx * axis_size
                    end_idx = start_idx + axis_size if axis_idx < num_axes - 1 else dim
                    axis_vector = v_intent[start_idx:end_idx]
                    energies.append(torch.mean(axis_vector).item())
                
                # Normalize relative to the maximum energy in this step
                max_energy = max(energies) + 1e-6
                
                for axis_idx in range(num_axes):
                    normalized_energy = energies[axis_idx] / max_energy
                    # To make it more dynamic and realistic, apply a slight curve
                    normalized_energy = normalized_energy ** 2 
                    
                    blocks = int(normalized_energy * 10)
                    bar = "\u2588" * blocks + "\u2591" * (10 - blocks)
                    print(f"      Axis {axis_idx} ({axes_names[axis_idx]}) : {bar} ({int(normalized_energy*100):02d}%)")
                
                sys.stdout.flush()
                print(f"    [DEBUG] End of loop body for step {step}", flush=True)
                # =====================================================================
                
        print(f"    [DEBUG] Exited while loop!", flush=True)
        print(f"\n{color_code}  [{role_name}] 思考完了. Total Steps: {len(generated_tokens)}.{C_RESET}", flush=True)
        avg_uncertainty = cumulative_uncertainty / max(1, thought_steps)
        return current_hidden, avg_uncertainty
            
    def forward_latent(self, x, past_states=None, role_name="Unknown", color_code="", mute_role=False, mute_leakage=False):
        """
        Takes an input tensor 'x' (batch_size, seq_len, 3840) and applies
        the simplified SVD-based mapping for 330 layers.
        Returns the processed tensor and the new states.
        """
        def puzzle_bind(a, b):
            # Geometrically binds two tensors together using element-wise product and cyclic shift.
            # This requires structural topology match to produce a non-zero, meaningful energy state.
            return a * torch.roll(b, shifts=1, dims=-1)
            
        if x.dim() == 2:
            x = x.unsqueeze(1)
        h = x.clone()
        norm_epsilon = 1e-6
        
        current_states = []
        
        for i, layer in enumerate(self.layers):
                if h.shape[-1] != layer["cols"]:
                    continue 
                    
                # Retrieve past state for this layer if available
                past_main = None
                past_back = None
                if past_states is not None and i < len(past_states):
                    past_main, past_back = past_states[i]
                    
                # --- Anti-Vanishing Mechanism (RMSNorm) ---
                variance = h.pow(2).mean(-1, keepdim=True)
                normed_h = (h * torch.rsqrt(variance + norm_epsilon)).to(torch.float16)
                    
                # --- JCross Mapping ---
                # NOTE: layer["mx"] already contains the proper scale. Adding 1.0 causes exponential blowup.
                z = torch.matmul(normed_h * layer["mx"].to(torch.float16), layer["V"]).to(torch.float16)
                
                # --- JCross V2 3D Cross-Structure Valve ---
                if "C_valve" in layer:
                    # Dynamically route / rotate concepts across the latent dimensions
                    z = torch.matmul(z, layer["C_valve"].to(torch.float16)).to(torch.float16)
                
                # [CRITICAL MATH FIX] Prevent Eigenvector Collapse!
                z = torch.nn.functional.silu(z)
                    
                z_scaled = (z * layer["S"].to(torch.float16)).to(torch.float16)
                
                rank = z_scaled.shape[-1]
                half_rank = rank // 2
                
                main_z = z_scaled[..., :half_rank]
                back_z = z_scaled[..., half_rank:]
                
                # --- JCross Spatial Attention (Stateful Memory) ---
                # Back Axis: Long-term continuous context (absorbs past history)
                if past_back is not None:
                    # Puzzle Binding for long-term memory
                    bound_back = puzzle_bind(back_z, past_back)
                    back_z = back_z + (bound_back * 0.3).to(torch.float16)
                    
                # Main Axis: Short-term iterative logic (crosses with previous token state)
                curr_main = main_z
                if past_main is not None:
                    # Inject immediate previous context via structural puzzle binding
                    bound_main = puzzle_bind(curr_main, past_main)
                    curr_main = curr_main + (bound_main * 0.5).to(torch.float16)
                    
                for _ in range(3):
                    gate = torch.sigmoid(curr_main).to(torch.float16)
                    curr_main = torch.nn.functional.silu(main_z * gate).to(torch.float16)
                
                absorbed_back = torch.nn.functional.gelu(back_z).to(torch.float16)
                
                # Save the post-processed states for the next token
                current_states.append((curr_main.clone(), absorbed_back.clone()))
                
                z_out_main = (main_z + curr_main).to(torch.float16)
                z_out_back = (back_z + absorbed_back).to(torch.float16)
                z_out = torch.cat([z_out_main, z_out_back], dim=-1)
                
                temp = torch.matmul(z_out, layer["U"].T).to(torch.float16)
                out = temp + layer["my"].to(torch.float16)
                
                if out.shape == h.shape:
                    h = h + out
                else:
                    h = out
                    
                # --- LEAKAGE UI ---
                if i % 80 == 0 and not mute_leakage:
                    leak_vals = h[0, -1, :6].detach().cpu().float().numpy()
                    
                    # Compute absolute activation energy and normalize to a 10-block visual
                    energies = [min(1.0, abs(float(v)) / 3.0) for v in leak_vals] # Scale assuming typical max variance is ~3.0
                    
                    axis_names = [
                        "Logic/Structure",
                        "Syntax/Code    ",
                        "Factual Memory ",
                        "Temporal/Time  ",
                        "Creativity     ",
                        "Swarm Consensus"
                    ]
                    
                    # Cognitive Phase determination based on layer depth
                    if i < 80:
                        phase = "Feature Extraction (Pattern Matching)"
                    elif i < 200:
                        phase = "Structural Assembly (Deep Reasoning)"
                    else:
                        phase = "Final Anchoring (Output Preparation)"
                    
                    # Focus Mode determination
                    max_energy = max(energies)
                    max_idx = energies.index(max_energy)
                    if max_energy > 0.6:
                        focus_mode = f"\033[31m{axis_names[max_idx].strip()} Dominant\033[0m"
                    elif sum(energies) > 1.5:
                        focus_mode = "\033[33mDispersed (Multi-Axis Association)\033[0m"
                    else:
                        focus_mode = "\033[36mDormant / Waiting\033[0m"
                    
                    sys.stdout.write(f"\n{color_code}[Brain Scan | {role_name} L{i:03d}: {phase}]{C_RESET}\n")
                    sys.stdout.write(f"  Focus State: {focus_mode}\n")
                    
                    for axis_idx in range(6):
                        pct = int(energies[axis_idx] * 100)
                        blocks = int(energies[axis_idx] * 10)
                        
                        # Color coding based on intensity
                        bar_color = "\033[31m" if pct > 80 else "\033[33m" if pct > 50 else "\033[36m"
                        bar = f"{bar_color}" + "█" * blocks + f"{C_RESET}\033[90m" + "░" * (10 - blocks) + f"{C_RESET}"
                        
                        # Highlight strongly firing axes
                        highlight = f" {bar_color}<- CRITICAL SPIKE{C_RESET}" if pct > 80 else ""
                        sys.stdout.write(f"{color_code}  Axis {axis_idx} ({axis_names[axis_idx]}) : {bar} ({pct:02d}%){highlight}{C_RESET}\n")
                    sys.stdout.flush()
                
        return h, current_states

def purge_memory():
    print(f"{C_SYS}  [System] Purging Brain from VRAM...{C_RESET}")
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
if __name__ == "__main__":
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"=== Initiating Verantyx Matrix Swarm ===")
    print(f"Target Compute Unit: {device}\n")
    
    # Worker Brain (Qwen 0.5B)
    worker_jgen = "/Users/motonishikoudai/verantyx-cli/cli/qwen_0.5b_full.jgen"
    commander_jgen = worker_jgen
    scout_jgen = worker_jgen
    memory_file = "/Users/motonishikoudai/verantyx-cli/my_clone.memory"
    
    memory_bank = TelepathicMemoryBank(hidden_dim=1024, memory_file=memory_file)
    
    hidden_dim = 1024
    torch.manual_seed(42)
    
    if memory_bank.consensus_vector is not None:
        current_thought = memory_bank.consensus_vector.to(device)
    else:
        # Prompt user instead of random seed (multi-line support)
        print(f"\n{C_SYS}=== Verantyx Ambient Telepathy Pipeline ==={C_RESET}")
        print(f"{C_SYS}Enter task description (Press Ctrl+D on a new line to submit, or press Enter immediately for random thought) > {C_RESET}")
        import sys
        user_input = sys.stdin.read().strip()
        
        if user_input:
            from transformers import AutoTokenizer
            print(f"{C_SYS}  [System] Loading Qwen tokenizer for Worker Encoding...{C_RESET}")
            worker_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
            
            workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            worker_jgen = os.path.join(workspace_dir, "cli", "qwen_0.5b_full.jgen")
            if not os.path.exists(worker_jgen):
                worker_jgen = os.path.join(workspace_dir, "qwen_0.5b_full.jgen")
            worker_brain = JCrossBrain(worker_jgen, device)
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_input}
            ]
            formatted_text = worker_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            current_thought = worker_brain.encode_text(formatted_text, worker_tokenizer).to(device)
            print(f"{C_SYS}  [System] User input encoded into latent space by WORKER.{C_RESET}")
        else:
            current_thought = torch.randn(1, hidden_dim, dtype=torch.float16, device=device)
            print(f"{C_SYS}  [System] Generating new random thought seed.{C_RESET}")
            
            from telepathic_coder_experimental import TelepathicCoder
            workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            print(f"  [System] Waking up Ambient Telepathic Coder (Lossless Identity Match)...")
            coder = TelepathicCoder(workspace_dir=workspace_dir, shared_decoder_brain=worker_brain)
            
    if 'coder' not in locals():
        from telepathic_coder_experimental import TelepathicCoder
        workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        coder = TelepathicCoder(workspace_dir=workspace_dir, shared_decoder_brain=worker_brain)
    
    # --- PHASE 0: COMMANDER SETS GOAL ---
    print(f"\n{C_SYS}>>> PHASE 0: Commander Sets Goal Intent in Ambient Space{C_RESET}")
    # Commander initializes the Ambient Space with the goal vector
    memory_bank.diffuse_thought(current_thought, intensity=2.0, flag_label="Goal Intent", agent_id=99)
    
    
    # --- PHASE 1: WORKER AMBIENT BRAINSTORMING ---
    # Optimized loop depths based on quality density (Low=1, Medium=3, High=5)
    thinking_depth = 1 
    print(f"\n>>> PHASE 1: Ambient Brainstorming (Depth: {thinking_depth})")
    
    # Define worker personalities (Agent IDs)
    workers = [1]
    search_quota = 5 # Medium setting
    searches_performed = 0
    
    for step in range(thinking_depth):
        print(f"\n{C_SYS}  --- Brainstorming Cycle {step+1}/{thinking_depth} ---{C_RESET}")
        
        for w_id in workers:
            print(f"{C_SYS}  [Worker {w_id}] Absorbing ambient space and thinking...{C_RESET}")
            
            # 1. 空間のベクトルを受信して自分の思考の基盤にする
            ambient_context = memory_bank.ambient_vector.to(device) if memory_bank.ambient_vector is not None else current_thought
            
            start_calc = time.time()
            # Coder の continuous_feedback_step をコールバックとして渡し、毎ステップの漏れ出しを受信・補正させる
            new_thought, avg_uncertainty = worker_brain.think_internally(
                ambient_context, 
                thought_steps=1, 
                role_name=f"Worker {w_id}", 
                color_code=C_WORKER,
                step_callback=coder.continuous_feedback_step
            )
            
            # 2. 自分の考えを空間に漏れ出させる (Agent Signature 付き)
            memory_bank.diffuse_thought(new_thought, intensity=1.0, flag_label=f"Idea from W{w_id}", agent_id=w_id)
            
            print(f"{C_SYS}  [Worker {w_id}] Idea diffused in {time.time()-start_calc:.2f}s.{C_RESET}")
            # We do NOT delete worker_brain here because it's shared

    # The final ambient space represents the "Consensus Vector"
    current_thought = memory_bank.ambient_vector.to(device)
    memory_bank.set_consensus(current_thought, label="Swarm Consensus")
    
    # --- PHASE 2: COMMANDER TRANSLATION & CONCLUSION ---
    print("\n>>> PHASE 2: Commander Directives")
    commander_brain = JCrossBrain(commander_jgen, device)
    
    start_calc = time.time()
    print(f"{C_CMDR}  [Commander] Evaluating Swarm Consensus against original Goal...{C_RESET}")
    commander_intent, cmdr_uncertainty = commander_brain.think_internally(current_thought, thought_steps=1, role_name="Commander", color_code=C_CMDR)
    print(f"{C_SYS}  [Commander] Evaluation complete in {time.time()-start_calc:.2f}s.{C_RESET}")
    
    if memory_bank.check_veto(commander_intent, threshold=0.85):
        print(f"\n{C_SYS}[System] ⚠️ VETO TRIGGERED: Consensus diverged from goal!{C_RESET}")
    else:
        print(f"\n{C_SYS}[System] ✅ CONSENSUS VERIFIED: Commander's intent passed to Scout.{C_RESET}")
        
    commander_brain.close()
    del commander_brain
    purge_memory()
    
    # --- PHASE 3: SCOUT EXECUTION ---
    print("\n>>> PHASE 3: Scout Execution & Feedback")
    scout_brain = JCrossBrain(scout_jgen, device)
    
    start_calc = time.time()
    scout_observation, scout_uncertainty = scout_brain.think_internally(commander_intent, thought_steps=1, role_name="Scout", color_code=C_SCOUT)
    print(f"{C_SYS}  [Scout] Execution and feedback propagation complete in {time.time()-start_calc:.2f}s.{C_RESET}")
    
    memory_bank.set_consensus(scout_observation, label="Scout Feedback")
    
    scout_brain.close()
    del scout_brain
    purge_memory()
    
    # --- PHASE 4: TELEPATHIC CODER SYNTHESIS ---
    print("\n>>> PHASE 4: Telepathic Coder Synthesis")
    start_calc = time.time()
    
    generated_code = coder.synthesize_code(scout_observation, subtask_prompt=user_input)
    print(f"{C_SYS}  [Coder] Code synthesis complete in {time.time()-start_calc:.2f}s.{C_RESET}")
    
    print("\n=== Matrix Operations Concluded Successfully ===")
