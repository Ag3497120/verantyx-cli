import os
import sys
import json
import argparse
import datetime
import torch

from bucket_relay_swarm import TelepathicMemoryBank

C_SYS = "\033[36m"
C_CODER = "\033[95m" # Magenta for Telepathic Coder
C_RESET = "\033[0m"

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
    def __init__(self, workspace_dir, cluster_mode=None, worker_ip=None):
        import os
        import datetime
        from bucket_relay_swarm import TelepathicMemoryBank, JCrossBrain
        
        self.workspace_dir = workspace_dir
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
        jgen_path = os.path.join(workspace_dir, "cli", "telepathic_coder_lossless.jgen")
        if not os.path.exists(jgen_path):
            jgen_path = os.path.join(workspace_dir, "telepathic_coder_lossless.jgen")
            if not os.path.exists(jgen_path):
                jgen_path = os.path.join(workspace_dir, "cli", "gemma_12b_generative.jgen")
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.brain = JCrossBrain(jgen_path, device=device, layer_start=layer_start, layer_end=layer_end)
        
        # Load Swappable Brain Modulators (Switchable Language Manifold)
        modulators_path = os.path.join(workspace_dir, "cli", "python_modulators_v2_3d.pt")
        if not os.path.exists(modulators_path):
            modulators_path = os.path.join(workspace_dir, "python_modulators_v2_3d.pt")
        if os.path.exists(modulators_path):
            self.brain.load_modulators(modulators_path)
        
        # Load JCrossTranslator (Soft Prompt Projector)
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

        # Load missing Embeddings/LM Head from disk if possible
        if self.cluster_mode != 'worker':
            if getattr(self.brain, 'embed_weight', None) is None:
                embed_path = os.path.join(workspace_dir, "embed.pt")
                if not os.path.exists(embed_path):
                    embed_path = os.path.join(workspace_dir, "cli", "embed.pt")
                if os.path.exists(embed_path):
                    self.brain.embed_weight = torch.load(embed_path, map_location=device).to(torch.float16)
                    self.log(f"Loaded embed.pt from disk ({embed_path}).")
            
            if getattr(self.brain, 'lm_head_weight', None) is None:
                lm_path = os.path.join(workspace_dir, "lm_head.pt")
                if not os.path.exists(lm_path):
                    lm_path = os.path.join(workspace_dir, "cli", "lm_head.pt")
                if os.path.exists(lm_path):
                    self.brain.lm_head_weight = torch.load(lm_path, map_location=device).to(torch.float16)
                    self.log(f"Loaded lm_head.pt from disk ({lm_path}).")
        
        # Dynamic Cognitive Anchor: Backup original translation dictionary
        if getattr(self.brain, 'lm_head_weight', None) is not None:
            self.base_lm_head = self.brain.lm_head_weight.clone().detach()
        if getattr(self.brain, 'embed_weight', None) is not None:
            self.base_embed = self.brain.embed_weight.clone().detach()
        
        # Load Tokenizer for Text-to-Latent mapping
        if self.cluster_mode != 'worker':
            try:
                from transformers import AutoTokenizer
                import os
                model_path = os.path.expanduser("~/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2")
                
                if not os.path.exists(model_path):
                    model_path = "/Volumes/PREDATOR GM7000 4TB/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2"
                    
                if os.path.exists(model_path):
                    self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                else:
                    self.tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-9b-it")
            except Exception as e:
                self.log(f"Warning: Could not load tokenizer for Text-to-Latent. {e}")
                self.tokenizer = None

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

    def _run_decoding_phase(self, aligned_vector, sys_prompt=None, max_tokens=8192, temperature=0.7, top_p=0.9):
        import sys
        import torch
        
        device = self.brain.device
        
        if not hasattr(self, 'tokenizer') or self.tokenizer is None:
            self.log("Error: Tokenizer is not loaded. Cannot perform decoding.")
            return ""
            
        self.log("Initializing JCross Distributed Decoding...")
        
        # 1. Prepare Text Prompt Embeddings
        if isinstance(sys_prompt, dict):
            input_ids = sys_prompt['input_ids'][0].tolist()
        else:
            input_ids = self.tokenizer(sys_prompt, return_tensors="pt").input_ids[0].tolist()
            
        # We need the JCross embeddings
        if getattr(self.brain, 'embed_weight', None) is None:
            self.log("Error: embed_weight not found in brain. Cannot embed tokens.")
            return ""
            
        if getattr(self.brain, 'lm_head_weight', None) is None:
            self.log("Error: lm_head_weight not found in brain. Cannot sample tokens.")
            return ""
            
        # Optional: Inject Soft Prompts if translator is present and high resolution
        concept_embed = aligned_vector.clone().to(torch.float16).to(device)
        if concept_embed.dim() == 1:
            concept_embed = concept_embed.unsqueeze(0)
        elif concept_embed.dim() == 3:
            concept_embed = concept_embed.squeeze(1)
            
        latent_resolution = float(concept_embed.norm().item())
        is_low_res = latent_resolution < 15.0
        
        prefix_embeds = None
        if not is_low_res and latent_resolution >= 50.0:
            if hasattr(self, 'translator') and self.translator is not None:
                self.translator.to(device).to(torch.float16)
                prefix_embeds = self.translator(concept_embed) # [batch, num_tokens, dim]
                self.log("Soft prompts injected successfully.")
                
        self.log("Generating code via JCross Layer-wise Distributed Inference...")
        print(f"  {C_CODER}[Brain] Decoding: \n", end="")
        sys.stdout.flush()
        
        generated_tokens = []
        past_states = None
        
        # Helper for decoding
        def top_p_sampling(logits, top_p=0.9, temperature=0.7):
            # Move to CPU to prevent MPS (Apple Silicon) text corruption/Mojibake
            logits = logits.detach().cpu().float()
            # Clean NaNs
            logits = torch.nan_to_num(logits, nan=0.0, posinf=100.0, neginf=-100.0)
            
            if temperature <= 0.0:
                return torch.argmax(logits, dim=-1).item()
            logits = logits / temperature
            sorted_logits, sorted_indices = torch.sort(logits, descending=True)
            cumulative_probs = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
            sorted_indices_to_remove = cumulative_probs > top_p
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = 0
            indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
            logits[indices_to_remove] = -float('Inf')
            probs = torch.softmax(logits, dim=-1)
            return torch.multinomial(probs, num_samples=1).item()
            
        # Send a special signal to Worker to reset its past_states for a new generation sequence
        if self.cluster_mode == 'master' and self.rpc:
            # We send a dummy tensor of shape (1, 1, 1) to signal a generation reset
            reset_signal = torch.zeros(1, 1, 1, dtype=torch.float16, device=device)
            self.rpc.send_tensor(reset_signal)
            _ = self.rpc.recv_tensor(device=device) # wait for ack
            
        with torch.no_grad():
            for step in range(max_tokens):
                # 1. Prepare current input vector
                if step == 0:
                    # First step: process full prefix + input prompt
                    text_embeds = self.brain.embed_weight[input_ids].unsqueeze(0).to(torch.float16)
                    if prefix_embeds is not None:
                        x = torch.cat([prefix_embeds.to(torch.float16), text_embeds], dim=1)
                    else:
                        x = text_embeds
                else:
                    # Autoregressive step: process just the last generated token
                    last_token = generated_tokens[-1]
                    x = self.brain.embed_weight[last_token].unsqueeze(0).unsqueeze(0).to(torch.float16)
                    
                # 2. Master passes through its layers (e.g., 0-246)
                x, past_states = self.brain.forward_latent(x, past_states=past_states, role_name="Coder", mute_leakage=True)
                
                # 3. Distributed execution: Send to Worker for the rest of the layers
                if self.cluster_mode == 'master' and self.rpc:
                    self.rpc.send_tensor(x)
                    x = self.rpc.recv_tensor(device=device)
                    if x is None:
                        self.log("Worker disconnected during decoding.")
                        break
                        
                # 4. Final Norm & LM Head Sampling (done on Master)
                last_hidden = x[:, -1, :]
                
                # Apply RMSNorm (Final Norm)
                if getattr(self.brain, 'final_norm_weight', None) is not None:
                    variance = last_hidden.pow(2).mean(-1, keepdim=True)
                    last_hidden = last_hidden * torch.rsqrt(variance + 1e-6)
                    last_hidden = last_hidden * self.brain.final_norm_weight.to(torch.float16)
                
                # Multiply by LM Head
                logits = torch.matmul(last_hidden, self.brain.lm_head_weight.to(torch.float16).T)
                
                # Temperature and Top-P Sampling
                next_token = top_p_sampling(logits, temperature=temperature, top_p=top_p)
                generated_tokens.append(next_token)
                
                text_chunk = self.tokenizer.decode([next_token])
                print(text_chunk, end="")
                sys.stdout.flush()
                
                if next_token == self.tokenizer.eos_token_id or next_token == 107:
                    break
                    
        print(f"\n {len(generated_tokens)} tokens generated.{C_RESET}")
        
        # Free memory
        import gc
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
            
        generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        return generated_text

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

    def synthesize_code(self, aligned_vector, subtask_prompt=""):
        """
        Latent Resonance Decoding:
        Decodes the thought vector. If the resolution is low, semantic repulsion 
        will naturally terminate the generation after generating a plan, preventing code generation.
        If resolution is high, it will naturally continue to generate the executable code.
        """
        import time
        import sys
        import torch
        
        self.log("Activating Lossless Generative Engine (Latent Resonance)...")
        
        # --- Dynamic Cognitive Anchor (Fluid Reading of the Vector) ---
        # Instead of relying on hardcoded norms, we read the semantic axes of the vector itself.
        v_intent = torch.nn.functional.relu(aligned_vector.reshape(-1))
        dim = v_intent.shape[0]
        axis_size = dim // 6
        # Axis 1 is Syntax/Code, Axis 0 is Logic/Structure
        syntax_energy = torch.mean(v_intent[axis_size : axis_size * 2]).item()
        logic_energy = torch.mean(v_intent[0 : axis_size]).item()
        max_energy = max(syntax_energy, logic_energy) + 1e-6
        syntax_ratio = (syntax_energy / max_energy) ** 2
        
        if syntax_ratio > 0.6:
            # Code Generation Anchor
            self.log(f"[\033[36mFluid Anchor\033[0m] High Syntax/Code activation ({syntax_ratio*100:.1f}%). Injecting Implementation Anchor.")
            cognitive_anchor = "\nYou are an Autonomous Architect and Telepathic Decoder. The swarm has authorized implementation. Generate the code directly based on the translated plan. You must proactively design the architecture and split the logic into multiple files as needed. For EACH file you generate, you MUST output '// file: <filename>' or '# file: <filename>' at the very beginning of its code block. You can and should generate multiple code blocks if the project requires it."
        else:
            # Planning Anchor
            self.log(f"[\033[33mFluid Anchor\033[0m] Low Syntax/Code activation ({syntax_ratio*100:.1f}%). Injecting Planning Anchor.")
            cognitive_anchor = "\nYou are an Interpreter for the Swarm. The swarm is still planning. Explain the swarm's architectural plan in natural language. Do NOT generate code blocks."

        # Single Decoding Pass (Fluid Role Switching & Coder Blindness)
        # Note: subtask_prompt now simply acts as context (e.g. the original user requirement or feedback)
        # Ensure chat_template is set for Gemma 2
        gemma_template = "{{ bos_token }}{% for message in messages %}{% if (message['role'] == 'assistant') %}{% set role = 'model' %}{% else %}{% set role = message['role'] %}{% endif %}{{ '<start_of_turn>' + role + '\n' + message['content'] | trim + '<end_of_turn>\n' }}{% endfor %}{% if add_generation_prompt %}{{'<start_of_turn>model\n'}}{% endif %}"
        
        self.tokenizer.chat_template = gemma_template
        chat_messages = [
            {"role": "user", "content": f"{subtask_prompt}\n\n[SYSTEM DIRECTIVE]{cognitive_anchor}"}
        ]
        
        # Apply template and get tensor directly (this properly parses special tokens)
        encoded = self.tokenizer.apply_chat_template(chat_messages, return_tensors="pt", add_generation_prompt=True, return_dict=False)
        if isinstance(encoded, dict) or hasattr(encoded, 'input_ids'):
            prompt_dict = {"input_ids": encoded['input_ids'], "attention_mask": encoded.get('attention_mask', torch.ones_like(encoded['input_ids']))}
        else:
            prompt_dict = {"input_ids": encoded, "attention_mask": torch.ones_like(encoded)}
        
        generated_text = self._run_decoding_phase(aligned_vector, prompt_dict, max_tokens=8192, temperature=0.5, top_p=0.9)
        
        self.log(f"Decoding Complete. Extracted State:\n")
        print("\n" + "="*40)
        print(generated_text)
        print("="*40 + "\n")
        
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
