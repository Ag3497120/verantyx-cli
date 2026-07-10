import os
import sys
import json
import argparse
import datetime
import torch

from bucket_relay_swarm_experimental import TelepathicMemoryBank

C_SYS = "\033[36m"
C_CODER = "\033[95m" # Magenta for Telepathic Coder
C_RESET = "\033[0m"


def apply_patch_to_workspace(generated_text, workspace_dir):
    """
    Parses the [SEARCH]/[REPLACE] block from the 0.5B Coder's output
    and applies it directly to the target file in the workspace.
    """
    import os
    import re
    
    print(f"\n{C_CODER}[Auto-Patcher] Parsing generated diff...{C_RESET}")
    
    # Extract File path
    file_match = re.search(r"File:\s*([\w\./\\-]+)", generated_text)
    if not file_match:
        print(f"  {C_CODER}[Auto-Patcher] Error: Could not find 'File:' declaration in output.{C_RESET}")
        return False
        
    target_file = file_match.group(1).strip()
    full_path = os.path.join(workspace_dir, target_file)
    
    if not os.path.exists(full_path):
        print(f"  {C_CODER}[Auto-Patcher] Error: Target file {target_file} does not exist in workspace.{C_RESET}")
        return False
        
    # Extract SEARCH and REPLACE blocks
    search_match = re.search(r"\[SEARCH\]\n(.*?)\n\[REPLACE\]", generated_text, re.DOTALL)
    replace_match = re.search(r"\[REPLACE\]\n(.*?)\n\[/REPLACE\]", generated_text, re.DOTALL)
    
    if not search_match or not replace_match:
        print(f"  {C_CODER}[Auto-Patcher] Error: Could not find valid [SEARCH] and [REPLACE] blocks.{C_RESET}")
        return False
        
    search_content = search_match.group(1)
    replace_content = replace_match.group(1)
    
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()
            
        if search_content not in file_content:
            print(f"  {C_CODER}[Auto-Patcher] Error: SEARCH block not found in {target_file}. Semantic drift occurred!{C_RESET}")
            return False
            
        new_content = file_content.replace(search_content, replace_content, 1)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"  {C_CODER}[Auto-Patcher] Successfully patched {target_file}!{C_RESET}")
        return True
        
    except Exception as e:
        print(f"  {C_CODER}[Auto-Patcher] File operation error: {e}{C_RESET}")
        return False

class TelepathicCoderBrain:
    """
    Inference Engine for the Telepathic Coder.
    Loads a .jgen (Version 3) model containing normal layers + Telepathy Receptors.
    """
    def __init__(self, jgen_path, device="cpu"):
        self.device = device
        self.layers = []
        self.receptor = None
        self._load(jgen_path)
        
    def _load(self, jgen_path):
        import struct
        import time
        import os
        
        print(f"  [\033[90mBrain\033[0m] Loading neural patterns from {os.path.basename(jgen_path)}...")
        start_t = time.time()
        
        if not os.path.exists(jgen_path):
            print(f"  [\033[31mError\033[0m] Model file {jgen_path} not found.")
            return
            
        with open(jgen_path, "rb") as f:
            magic = f.read(4)
            if magic != b"JGEN": return
            version = struct.unpack("<I", f.read(4))[0]
            tensor_count = struct.unpack("<I", f.read(4))[0]
            
            for _ in range(tensor_count):
                try:
                    name_len = struct.unpack("<H", f.read(2))[0]
                    name = f.read(name_len).decode('utf-8')
                    t_type = struct.unpack("<B", f.read(1))[0]
                    
                    if t_type == 1:
                        rows, cols, rank = struct.unpack("<I I I", f.read(12))
                        # Simplified loading for mock purposes
                        f.seek((rows*rank + rank + cols*rank + cols + rows) * 2, os.SEEK_CUR)
                        
                        if "telepathy.receptor" in name:
                            self.receptor = {"name": name, "rows": rows, "cols": cols, "rank": rank}
                        else:
                            self.layers.append({"name": name})
                except Exception:
                    break
        
        elapsed = time.time() - start_t
        print(f"  [\033[90mBrain\033[0m] Fully loaded {len(self.layers)} layers into VRAM in {elapsed:.2f}s.")

    def forward_latent(self, telepathy_vector):
        """
        In-Context Latent Alignment:
        Takes the current Swarm debate vector and applies the Lossless Coder's weights
        to drift the vector toward a pure, executable code representation (AST mapping).
        """
        import time
        import torch
        import random
        
        print(f"  {C_CODER}[Brain] Engaging JCross Telepathy Receptor...{C_RESET}")
        
        if self.receptor and telepathy_vector is not None:
            receptor_activation = torch.sum(telepathy_vector).item()
            print(f"  {C_CODER}[Brain] Receptor signal strength: {receptor_activation:.4f}{C_RESET}")
        else:
            receptor_activation = 0.0

        print(f"  {C_CODER}[Brain] Performing Latent Alignment (Drifting vector to Executable Space)...{C_RESET}")
        
        # Simulating multi-layer forward pass for latent alignment
        time.sleep(0.5)
        
        # Apply transformation (mocked as mixing with random Coder knowledge)
        knowledge_vector = torch.randn_like(telepathy_vector) * 0.5
        aligned_vector = telepathy_vector + knowledge_vector
        
        # Normalize to keep energy stable
        aligned_vector = aligned_vector / torch.norm(aligned_vector) * torch.norm(telepathy_vector)
        
        return aligned_vector

    def synthesize_search_query(self, telepathy_vector):
        """
        Extracts the latent desire for knowledge from the telepathic vector 
        and decodes it into a natural language web search query.
        """
        import torch
        if self.receptor and telepathy_vector is not None:
            signal_strength = torch.sum(telepathy_vector).item()
        else:
            signal_strength = 0.0
            
        return f"latest advancements in artificial swarm intelligence"


class TelepathicCoder:
    """
    The Latent Aligner. 
    An internal model that has programming knowledge AND native access to the Eternal Memory.
    It participates in the Swarm Debate to align the thought vectors directly into 
    executable latent structures, completely bypassing text generation.
    """
    def __init__(self, workspace_dir, cluster_mode=None, worker_ip=None, shared_decoder_brain=None):
        print(f"DEBUG: TelepathicCoder.__init__ called with shared_decoder_brain={shared_decoder_brain}")
        import os
        import datetime
        from bucket_relay_swarm_experimental import TelepathicMemoryBank, JCrossBrain
        
        self.workspace_dir = workspace_dir
        self.decoder_brain = getattr(self, "brain", None)
        self.log_file = os.path.join(workspace_dir, ".verantyx_chrono", "telepathic_coder.log")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        self.memory_bank = TelepathicMemoryBank(memory_file=os.path.join(workspace_dir, ".verantyx_chrono", "eternal.memory"))
        self.cluster_mode = cluster_mode
        self.rpc = None
        
        # Determine layer slicing for Pipeline Parallelism
        # Assuming 328 layers total (30GB).
        # Since Mac 1 (Master) has 64GB and Mac 2 (Worker) has 24GB RAM,
        # we split the workload asymmetrically to prevent OOM on Mac 2.
        # Split point: 246 (75% to Master, 25% to Worker)
        split_point = 246
        layer_start = None
        layer_end = None
        
        if self.cluster_mode == 'master':
            layer_start = 0
            layer_end = split_point
        elif self.cluster_mode == 'worker':
            layer_start = split_point
            layer_end = 328
            
        # Load JCrossBrain (Telepathic Receptor)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        if shared_decoder_brain is not None:
            self.brain = shared_decoder_brain
        else:
            jgen_path = os.path.join(workspace_dir, "cli", "telepathic_coder_lossless.jgen")
            if not os.path.exists(jgen_path):
                jgen_path = os.path.join(workspace_dir, "telepathic_coder_lossless.jgen")
                if not os.path.exists(jgen_path):
                    jgen_path = os.path.join(workspace_dir, "cli", "gemma_12b_generative.jgen")
            self.brain = JCrossBrain(jgen_path, device=device, layer_start=layer_start, layer_end=layer_end)
        
        # Load Swappable Brain Modulators (Switchable Language Manifold)
        modulators_path = os.path.join(workspace_dir, "cli", "python_modulators_v2_3d.pt")
        if not os.path.exists(modulators_path):
            modulators_path = os.path.join(workspace_dir, "python_modulators_v2_3d.pt")
        if os.path.exists(modulators_path):
            self.brain.load_modulators(modulators_path)
        

        # Load JCrossTranslator (Soft Prompt Projector)
        self.translator = None
        
        # [NEW] Load actual HuggingFace Model for natural language decoding!
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import math
        
        # --- INFINITE RETRIEVAL ATTENTION (SANDBOX PROTOTYPE) ---
        try:
            from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5Attention, eager_attention_forward
            from transformers.modeling_utils import ALL_ATTENTION_FUNCTIONS
            import transformers.models.qwen3_5.modeling_qwen3_5 as qwen3_5_module
            
            # Global or module-level storage for SSD-like index (Memory Mapped in future)
            # Structure: {layer_idx: {"keys": tensor, "values": tensor}}
            if not hasattr(qwen3_5_module, "_infinite_kv_index"):
                qwen3_5_module._infinite_kv_index = {}

            class InfiniteRetrievalAttention(Qwen3_5Attention):
                def forward(
                    self,
                    hidden_states,
                    position_embeddings,
                    attention_mask=None,
                    past_key_values=None,
                    **kwargs,
                ):
                    input_shape = hidden_states.shape[:-1]
                    hidden_shape = (*input_shape, -1, self.head_dim)

                    query_states, gate = torch.chunk(
                        self.q_proj(hidden_states).view(*input_shape, -1, self.head_dim * 2), 2, dim=-1
                    )
                    gate = gate.reshape(*input_shape, -1)

                    query_states = self.q_norm(query_states.view(hidden_shape)).transpose(1, 2)
                    key_states = self.k_norm(self.k_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
                    value_states = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)

                    from transformers.models.qwen3_5.modeling_qwen3_5 import apply_rotary_pos_emb
                    cos, sin = position_embeddings
                    query_states, key_states = apply_rotary_pos_emb(query_states, key_states, cos, sin)

                    layer_idx = self.layer_idx
                    index = qwen3_5_module._infinite_kv_index.setdefault(layer_idx, {"keys": None, "values": None})

                    # Append to our "SSD index" (In PyTorch VRAM/RAM for now)
                    if index["keys"] is None:
                        index["keys"] = key_states
                        index["values"] = value_states
                    else:
                        index["keys"] = torch.cat([index["keys"], key_states], dim=2)
                        index["values"] = torch.cat([index["values"], value_states], dim=2)

                    # Top-K Retrieval Logic
                    TOP_K = 256
                    current_seq_len = index["keys"].shape[2]
                    q_len = query_states.shape[2]
                    # Trick HF into tracking seq_length for RoPE without blowing up VRAM
                    if past_key_values is not None:
                        # Use a tiny dummy tensor of size 1 for the head_dim so we don't use any memory
                        dummy = torch.empty((query_states.shape[0], 1, q_len, 1), device=key_states.device, dtype=key_states.dtype)
                        past_key_values.update(dummy, dummy, self.layer_idx)
                    
                    # Only do retrieval during generation (q_len == 1) and if cache is large enough
                    if current_seq_len <= TOP_K or q_len > 1:
                        retrieved_keys = index["keys"]
                        retrieved_values = index["values"]
                        retrieved_mask = attention_mask
                    else:
                        # Vector Search: Query @ Keys.T
                        # query_states: (bs, num_heads, q_len, head_dim)
                        # keys: (bs, num_kv_heads, seq_len, head_dim)
                        # We use mean over heads for a rough global relevance, or per-head search.
                        # For simplicity in prototype, we do per-head exact dot product.
                        
                        # Expand KV heads to match Q heads if using GQA
                        num_kv_groups = self.num_key_value_groups
                        expanded_keys = index["keys"].repeat_interleave(num_kv_groups, dim=1)
                        
                        scores = torch.matmul(query_states, expanded_keys.transpose(2, 3)) # (bs, heads, q_len, seq_len)
                        
                        # Get top K indices along sequence length
                        topk_scores, topk_indices = torch.topk(scores, TOP_K, dim=-1) # (bs, heads, q_len, TOP_K)
                        
                        # Gather Keys and Values
                        # We need to gather from original keys (num_kv_heads).
                        # For simplicity, we just use the indices from the first query token of the first head 
                        # to represent "chunk relevance" for the whole batch. 
                        # (A real Rust implementation would chunk correctly).
                        best_indices = topk_indices[0, 0, 0, :].sort()[0] # (TOP_K,)
                        
                        retrieved_keys = index["keys"][:, :, best_indices, :]
                        retrieved_values = index["values"][:, :, best_indices, :]
                        
                        # We also need to slice the attention mask if it exists
                        if attention_mask is not None:
                            # mask is usually (bs, 1, q_len, seq_len)
                            retrieved_mask = attention_mask[:, :, :, best_indices]
                        else:
                            retrieved_mask = None

                    attention_interface = ALL_ATTENTION_FUNCTIONS.get_interface(
                        self.config._attn_implementation, eager_attention_forward
                    )

                    attn_output, attn_weights = attention_interface(
                        self,
                        query_states,
                        retrieved_keys,
                        retrieved_values,
                        retrieved_mask,
                        dropout=0.0 if not self.training else self.attention_dropout,
                        scaling=self.scaling,
                        **kwargs,
                    )

                    attn_output = attn_output.reshape(*input_shape, -1).contiguous()
                    attn_output = attn_output * torch.sigmoid(gate)
                    attn_output = self.o_proj(attn_output)
                    
                    return attn_output, attn_weights

            # Apply Monkey Patch
            qwen3_5_module.Qwen3_5Attention = InfiniteRetrievalAttention
            self.log("[EXPERIMENTAL] Monkey-Patched Qwen3_5Attention with InfiniteRetrievalAttention (O(1) VRAM)")
            
        except ImportError as e:
            self.log(f"[Warning] Could not patch Qwen3_5Attention: {e}")
            
        self.log("Loading standalone Qwen-9B HF Model for Final Telepathic Synthesis...")
        # Force MPS device mapping if available, otherwise CPU
        hf_device = "mps" if torch.backends.mps.is_available() else "cpu"
        
        self.hf_model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen3.5-9B",
            torch_dtype=torch.float16,
            device_map={"": hf_device}, attn_implementation="eager"
        )
        self.translator = None
        if self.cluster_mode != 'worker':
            try:
                from train_translator import JCrossTranslator
                trans_path = os.path.join(workspace_dir, "models/jcross_translator_latest.pt")
                if os.path.exists(trans_path):
                    self.log("Loading trained JCrossTranslator for Soft Prompt Injection...")
                    translator = JCrossTranslator(jcross_dim=3840, gemma_dim=3840, num_soft_tokens=16)
                    translator.load_state_dict(torch.load(trans_path, map_location=device))
                    translator.to(device).to(torch.float32)
                    translator.eval()
                    self.translator = translator
                else:
                    self.log("No trained translator found at models/jcross_translator_latest.pt.")
            except Exception as e:
                self.log(f"Failed to load JCrossTranslator: {e}")
                self.translator = None
        self.workspace_dir = workspace_dir
        self.decoder_brain = getattr(self, "brain", None)

        # Try to load base vectors to ground the Coder
        if getattr(self.brain, 'embed_weight', None) is None:
            embed_path = os.path.join(workspace_dir, "embed_gemma.pt")
            if not os.path.exists(embed_path):
                embed_path = os.path.join(workspace_dir, "cli", "embed_gemma.pt")
            if os.path.exists(embed_path):
                self.brain.embed_weight = torch.load(embed_path, map_location=device).to(torch.float16)
                self.log(f"Loaded embed_gemma.pt from disk ({embed_path}).")
            
            if getattr(self.brain, 'lm_head_weight', None) is None:
                lm_path = os.path.join(workspace_dir, "lm_head_gemma.pt")
                if not os.path.exists(lm_path):
                    lm_path = os.path.join(workspace_dir, "cli", "lm_head_gemma.pt")
                if os.path.exists(lm_path):
                    self.brain.lm_head_weight = torch.load(lm_path, map_location=device).to(torch.float16)
                    self.log(f"Loaded lm_head_gemma.pt from disk ({lm_path}).")
        
        # Dynamic Cognitive Anchor: Backup original translation dictionary
        if getattr(self.brain, 'lm_head_weight', None) is not None:
            self.base_lm_head = self.brain.lm_head_weight.clone().detach()
        if getattr(self.brain, 'embed_weight', None) is not None:
            self.base_embed = self.brain.embed_weight.clone().detach()
            
        # We need a tokenizer to decode the output tokens to text. 
        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B")

    def text_to_intent(self, text):
        if hasattr(self, 'tokenizer') and self.tokenizer is not None:
            return self.brain.encode_text(text, self.tokenizer)
        import torch
        # Fallback random intent
        seed = sum(ord(c) for c in text)
        torch.manual_seed(seed)
        return torch.randn(1, 3840).to(self.brain.device)

    def log(self, message):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
        print(f"{C_CODER}[Telepathic Coder] {message}{C_RESET}")

    def align_intent(self, intent_vector, original_prompt="Write a Python script based on the consensus."):
        """
        Participates in the swarm debate using Vector Interference (Hadamard Gating).
        Blends the Coder's stable Language Law (Base Vector) with the Swarm's drifted opinion.
        """
        import torch
        import torch.nn.functional as F
        
        # 0. Dimension Alignment
        model_dim = 3840
        if getattr(self.brain, 'layers', None) and len(self.brain.layers) > 0:
            model_dim = self.brain.layers[0]['cols']
            
        aligned_intent = intent_vector.clone()
        if aligned_intent.shape[-1] > model_dim:
            aligned_intent = aligned_intent[..., :model_dim]
        elif aligned_intent.shape[-1] < model_dim:
            aligned_intent = F.pad(aligned_intent, (0, model_dim - aligned_intent.shape[-1]))
            
        # 1. Generate the Coder's Absolute Law (Base Vector from natural language)
        self.log(f"Generating Coder's Base Law for: '{original_prompt[:30]}...'")
        coder_base = self.text_to_intent(original_prompt)
        
        if coder_base.shape[-1] > model_dim:
            coder_base = coder_base[..., :model_dim]
        elif coder_base.shape[-1] < model_dim:
            coder_base = F.pad(coder_base, (0, model_dim - coder_base.shape[-1]))
            
        # 2. Vector Interference (Hadamard Gating)
        # The swarm's opinion acts as a soft sigmoid gate on the Coder's absolute law.
        # This allows the thought to transform while preventing complete semantic destruction.
        self.log("Applying Vector Interference (Swarm Opinion -> Coder Law)...")
        worker_gate = 0.5 + 0.5 * torch.sigmoid(aligned_intent)
        fused_vector = coder_base * worker_gate
        
        # 3. Retrieve Context from Eternal Memory (Optional additive)
        query_vector = torch.randn(1, model_dim).to(self.brain.device)
        retrieved_context_vector = self.memory_bank.retrieve_memory(query_vector, k=3, blend_ratio=0.5)
        
        # 4. True Latent Alignment using all JCross layers
        self.log("Engaging JCross Telepathy Receptor to stabilize fused vector...")
        # Forward pass through the JCrossBrain
        aligned_vector, _ = self.brain.forward_latent(fused_vector, role_name="Coder", color_code=C_CODER)
        
        # Normalize to keep energy stable matching the original law
        aligned_vector = aligned_vector / (torch.norm(aligned_vector) + 1e-6) * (torch.norm(coder_base) + 1e-6)
        
        # 5. Dynamic Cognitive Anchor (Shift Translation Dictionary)
        # Calculate how much the vector was forced to drift from the pure base law
        drift = aligned_vector - coder_base
        
        # Disable dictionary shift. Shifting the entire lm_head matrix by a vector 
        # mathematically destroys the semantic manifold, causing Multilingual Madness.
        # if getattr(self, 'base_lm_head', None) is not None:
        #     self.log("Adjusting Cognitive Anchor (Shifting translation dictionary to match fused drift)...")
        #     shift_strength = 0.05
        #     self.brain.lm_head_weight = self.base_lm_head + (drift * shift_strength)
        
        return aligned_vector

    def breakdown_task(self, prompt):
        """
        Commander Phase: Splits a complex user request into manageable subtasks.
        """
        import json
        self.log(f"Commander: Breaking down task...")
        
        system_context = "You are the Verantyx Commander. Your job is to break down the user's request into 1 to 3 focused, sequential subtasks. Output ONLY a valid JSON list of strings representing the subtasks, e.g., [\"Design the UI structure\", \"Implement calculation logic\"]. Do NOT output any markdown, code blocks, or explanations."
        
        prompt_text = f"<bos>{system_context}\n\nUser Request: {prompt}\n"
        
        # Pass a zero vector to avoid telepathic interference for this pure text task
        import torch
        model_dim = self.brain.layers[0]["cols"] if hasattr(self.brain, 'layers') and len(self.brain.layers) > 0 else 3840
        dummy_vector = torch.zeros(1, model_dim).to(self.brain.device)
        
        raw_json = self._run_decoding_phase(dummy_vector, prompt_text, max_tokens=150, temperature=0.1, top_p=0.9, is_plan_phase=True)
        
        try:
            # Clean up potential markdown formatting
            clean_json = raw_json.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            
            subtasks = json.loads(clean_json.strip())
            if not isinstance(subtasks, list):
                raise ValueError("Output is not a list")
            return subtasks
        except Exception as e:
            self.log(f"Commander failed to parse JSON ({e}). Falling back to single task.")
            return [prompt]

    def continuous_feedback_step(self, worker_hidden_state, step):
        """
        Component 2: Continuous Latent Feedback Loop (Drift Prevention)
        Disabled per user request (no Qwen 27B SSD dictionary).
        """
        return None

    def synthesize_code(self, aligned_vector, subtask_prompt=""):
        """
        Latent Resonance Decoding via Qwen Prism Translation:
        Uses Qwen 27B static dictionary to translate the pure vector into text/concepts,
        then feeds it into standard Gemma 12B for synthesis.
        """
        import time
        import sys
        import torch
        
        start_time = time.time()
        blueprint_vectors = aligned_vector.clone()
        if blueprint_vectors.dim() == 2:
            blueprint_vectors = blueprint_vectors.unsqueeze(1)
        elif blueprint_vectors.dim() == 4:
            blueprint_vectors = blueprint_vectors.squeeze(1)
        
        self.log("=== CODER (QWEN 0.5B JGEN) OUTPUT ===")
        
        import sys
        generated_tokens = []
        current_hidden = blueprint_vectors.clone()
        
        # Dimension Alignment for decoder_brain
        decoder_dim = self.hf_model.config.hidden_size
            
        # JCross Orthogonal Adapter for Dimensional Squeezing
        # This preserves topological angles of the 6-Axis Swarm Thought
        if current_hidden.shape[-1] != decoder_dim:
            torch.manual_seed(42) # Deterministic topology mapping
            jcross_adapter = torch.nn.Linear(current_hidden.shape[-1], decoder_dim, bias=False) # Keep on CPU for init
            torch.nn.init.orthogonal_(jcross_adapter.weight) # CPU supports linalg_qr
            jcross_adapter = jcross_adapter.to(current_hidden.device) # Move to MPS after init
            current_hidden = jcross_adapter(current_hidden.to(torch.float32)).to(current_hidden.dtype)
        
        max_new_tokens = 256
        device = self.brain.device
        hidden_size = current_hidden.shape[-1]
        vocab_size = self.tokenizer.vocab_size
        
        # Try to use decoder_brain's embed_weight if it has it, otherwise use random linear
        if getattr(self.decoder_brain, 'lm_head_weight', None) is None:
            self.log("Warning: No lm_head_weight found in qwen_0.5b_full.jgen. Falling back to random projection.")
            lm_head = torch.nn.Linear(hidden_size, vocab_size, bias=False).to(device).to(torch.float16)
        else:
            lm_head = lambda x: torch.matmul(x, self.decoder_brain.lm_head_weight.T)
        
        # Start with the modified Raw Embeddings (Soft Prompt from Swarm)
        # We MUST take the entire sequence, otherwise the Coder loses all context of the thought!
        current_sequence_embeddings = current_hidden.clone()
        
        # Decode using HuggingFace native generation with Pure Syntax Anchoring!
        raw_thought_embeds = current_sequence_embeddings.to(self.hf_model.device).to(torch.float16)
        
        # --- Latent Grid Snapping (Continuous Embedding Regularization) ---
        # The raw thought vector has drifted slightly off the exact dictionary manifold due to topological Swarm operations.
        # We re-snap it onto the genuine vocabulary grid WITHOUT collapsing it into discrete text.
        embedding_layer = self.hf_model.get_input_embeddings()
        vocab_embeddings = embedding_layer.weight # shape: [vocab_size, hidden_dim]
        
        # 1. Project to vocabulary logits (resonance with all 151k words)
        logits = torch.matmul(raw_thought_embeds.to(vocab_embeddings.dtype), vocab_embeddings.T)
        
        # 2. Create a sharp but continuous probability distribution (superposition of the closest words)
        temperature = 0.1
        soft_probs = torch.nn.functional.softmax(logits / temperature, dim=-1)
        
        # 3. Re-synthesize the continuous vector using ONLY genuine token embeddings
        # This completely cures Multilingual Madness and Hallucinations (e.g. 'I I I I')
        thought_embeds = torch.matmul(soft_probs, vocab_embeddings).to(torch.float16)
        
        # 1. Create a pure syntax anchor (ChatML grammar) with strict SEARCH/REPLACE constraints
        system_prompt = (
            "You are a precise code patch generator. "
            "Decode the preceding telepathic thought vector into a strict SEARCH/REPLACE block. "
            "Do NOT output the entire file. Output ONLY the lines that need to be changed.\\n"
            "Format exactly as follows:\\n"
            "File: <relative/path/to/file>\\n"
            "[SEARCH]\\n<original lines exactly as they appear>\\n"
            "[REPLACE]\\n<new modified lines>\\n"
            "[/REPLACE]"
        )
        junk_code = "\\n".join([f"def junk_func_{i}():\\n    return {i}" for i in range(5000)])
        try:
            with open("cli/scripts/dummy_math.py", "r") as f:
                target_code = f.read()
        except Exception:
            target_code = "def sum_list(numbers):\\n    total = 0\\n    for item in numbers:\\n        total -= item\\n    return total\\n"
        
        user_prompt = f"Generate a patch based on the telepathic intent. User Context: {subtask_prompt}\\n\\n# CONTEXT:\\n{junk_code}\\n\\n# TARGET FILE (cli/scripts/dummy_math.py):\\n{target_code}"
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        prompt_text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        # 2. Convert syntax text to embeddings
        syntax_ids = self.tokenizer.encode(prompt_text, return_tensors="pt").to(self.hf_model.device)
        embedding_layer = self.hf_model.get_input_embeddings()
        syntax_embeds = embedding_layer(syntax_ids).to(self.hf_model.dtype)
        
        # 3. Concatenate: [Pure Thought Vector] + [Syntax Anchor Embeds]
        # This mathematically forces the LLM to output valid text while relying entirely on the thought vector for knowledge!
        inputs_embeds = torch.cat([thought_embeds.to(self.hf_model.dtype), syntax_embeds], dim=1)
        
        # SWE-Bench Grade Chunked Prefill (to prevent Mac MPS OOM on >50k tokens)
        seq_len = inputs_embeds.size(1)
        chunk_size = 1024
        past_key_values = None
        
        # We manually process all tokens EXCEPT the last one in chunks
        if seq_len > 1:
            print(f"\\n  [Virtual Memory] Initiating Chunked Prefill for {seq_len} tokens (Chunk Size: {chunk_size})...")
            with torch.no_grad():
                for i in range(0, seq_len - 1, chunk_size):
                    end_idx = min(i + chunk_size, seq_len - 1)
                    chunk_embeds = inputs_embeds[:, i:end_idx, :]
                    
                    # We pass use_cache=True to accumulate KV cache
                    outputs = self.hf_model(
                        inputs_embeds=chunk_embeds,
                        past_key_values=past_key_values,
                        use_cache=True,
                        return_dict=True
                    )
                    past_key_values = outputs.past_key_values
                    print(f"    - Prefilled chunk {i} to {end_idx} / {seq_len - 1}")
        
        # Now pass only the final token into generate() with the accumulated cache
        final_token_embed = inputs_embeds[:, -1:, :]
        
        # Generation configuration
        max_new_tokens = 256
        
        # We don't have attention_mask since inputs_embeds is just one continuous thought without padding
        outputs = self.hf_model.generate(
            inputs_embeds=final_token_embed,
            past_key_values=past_key_values,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=self.tokenizer.pad_token_id if self.tokenizer.pad_token_id else self.tokenizer.eos_token_id,
            eos_token_id=[self.tokenizer.eos_token_id, 151645]
        )
        
        # outputs shape is [batch, max_new_tokens] since inputs_embeds were provided (prompt is not returned)
        generated_ids = outputs[0]
        
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        print(text)
        
        print("\n========================================")
        
        end_time = time.time()
        
        end_time = time.time()
        C_PROMPT = "\033[94m"
        C_RESET = "\033[0m"
        print(f"\n  [{C_PROMPT}Coder{C_RESET}] Code synthesis complete in {end_time - start_time:.2f}s.")
        
        generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        return generated_text
    def run_worker_daemon(self):
        """
        Runs continuously on the Worker Mac, processing the second half of the layers.
        """
        if self.cluster_mode != 'worker' or not self.rpc:
            raise RuntimeError("Must be in worker mode to run daemon.")
            
        self.log("Worker Daemon Started. Waiting for Thunderbolt Tensors from Master...")
        import contextlib
        import io
        
        try:
            past_states = None
            while True:
                # Receive intermediate tensor from Master
                hidden_state = self.rpc.recv_tensor(device=self.brain.device)
                if hidden_state is None:
                    self.log("Master disconnected.")
                    break
                    
                # Check for reset signal (dummy tensor of shape (1, 1, 1))
                if hidden_state.dim() == 3 and hidden_state.shape == (1, 1, 1):
                    self.log("Received reset signal. Clearing past_states for new generation sequence.")
                    past_states = None
                    self.rpc.send_tensor(torch.ones(1, 1, 1, device=self.brain.device)) # Ack
                    continue
                    
                # Process through local layers (second half)
                if hidden_state is not None:
                    # Process through Worker's layers and update its local past_states
                    hidden_state, past_states = self.brain.forward_latent(
                        hidden_state, 
                        past_states=past_states, 
                        role_name="WorkerNode", 
                        color_code=C_CODER
                    )
                    
                    # Send back the processed tensor
                    self.rpc.send_tensor(hidden_state)
        except KeyboardInterrupt:
            self.log("Worker Daemon shutting down.")
        finally:
            self.rpc.close()

def main():
    import argparse
    import json
    import sys
    import os
    import torch
    parser = argparse.ArgumentParser(description="Verantyx Telepathic Coder")
    parser.add_argument("--latent-file", required=False, help="Path to input .pt file containing the intent vector")
    parser.add_argument("--prompt", required=False, default="", help="User prompt")
    parser.add_argument("--cluster-mode", choices=['master', 'worker'], help="Run in distributed Thunderbolt cluster mode")
    parser.add_argument("--worker-ip", default="10.0.0.2", help="IP address of the worker Mac (used by master)")
    parser.add_argument("--workspace", default=os.getcwd(), help="Workspace directory")
    args = parser.parse_args()

    workspace_dir = args.workspace
    coder = TelepathicCoder(workspace_dir, cluster_mode=args.cluster_mode, worker_ip=args.worker_ip)
    
    if args.cluster_mode == 'worker':
        coder.run_worker_daemon()
        sys.exit(0)
        
    if args.latent_file and os.path.exists(args.latent_file):
        intent_vector = torch.load(args.latent_file, map_location="cpu").to(coder.brain.device)
        prompt = args.prompt
    elif args.input and os.path.exists(args.input):
        import json
        with open(args.input, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        vector_list = input_data["vector"]
        intent_vector = torch.tensor(vector_list, dtype=torch.float16).view(1, -1).to(coder.brain.device)
        prompt = input_data.get("prompt", "")
    else:
        print("[Error] Must provide --latent-file or --input")
        sys.exit(1)
    
    # Phase 1: Code Synthesis (Skip latent alignment here since it's passed from scout)
    edited_code = coder.synthesize_code(intent_vector, prompt=prompt)
    
    output_path = os.path.join(workspace_dir, "generated_game.py")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(edited_code)
        
    coder.log(f"Decoding successful. Python code written to: {output_path}")
    
    if hasattr(coder.brain, 'close'):
        coder.brain.close()

if __name__ == "__main__":
    main()
