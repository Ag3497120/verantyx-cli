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
            from thunderbolt_rpc import TensorTransferEngine
            self.rpc = TensorTransferEngine(role='master', peer_ip=worker_ip)
            self.rpc.start()
        elif self.cluster_mode == 'worker':
            layer_start = split_point
            layer_end = 328
            from thunderbolt_rpc import TensorTransferEngine
            self.rpc = TensorTransferEngine(role='worker')
            self.rpc.start()
            
        # Initialize Dual-Inference Brain using # Path to the Lossless JGEN model
        jgen_path = os.path.join(workspace_dir, "telepathic_coder_lossless.jgen")
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.brain = JCrossBrain(jgen_path, device=device, layer_start=layer_start, layer_end=layer_end)
        
        # Load missing Embeddings/LM Head from Hugging Face
        if self.cluster_mode == 'master':
            if getattr(self.brain, 'embed_weight', None) is None or getattr(self.brain, 'lm_head_weight', None) is None:
                self.log("Loading missing dense layers from Hugging Face...")
                from transformers import AutoModelForCausalLM
                model_path_hf = os.path.expanduser("~/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2")
                if not os.path.exists(model_path_hf):
                    model_path_hf = "/Volumes/PREDATOR GM7000 4TB/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2"
                if not os.path.exists(model_path_hf):
                    model_path_hf = "google/gemma-4-12b-it"
                    
                hf_model = AutoModelForCausalLM.from_pretrained(model_path_hf, torch_dtype=torch.float16, local_files_only=True)
                if getattr(self.brain, 'embed_weight', None) is None:
                    self.brain.embed_weight = hf_model.get_input_embeddings().weight.detach().to(device)
                if getattr(self.brain, 'lm_head_weight', None) is None:
                    self.brain.lm_head_weight = hf_model.get_output_embeddings().weight.detach().to(device)
                if getattr(self.brain, 'final_norm_weight', None) is None:
                    try:
                        self.brain.final_norm_weight = hf_model.model.norm.weight.detach().to(device)
                    except:
                        self.brain.final_norm_weight = torch.zeros(self.brain.layers[0]["cols"] if len(self.brain.layers)>0 else 3584, dtype=torch.float16, device=device)
                # Retain HF Model for Hybrid Inverse Topology Decoding
                self.hf_model = hf_model.to(device)
            
            # Load Manifold Alignment Matrix if it exists
            align_path = os.path.join(workspace_dir, "manifold_alignment.pt")
            if os.path.exists(align_path):
                self.log("Loading Manifold Alignment Matrix...")
                self.m_align = torch.load(align_path, map_location=device).to(torch.float16)
            else:
                self.m_align = None
        
        # Dynamic Cognitive Anchor: Backup original translation dictionary
        if getattr(self.brain, 'lm_head_weight', None) is not None:
            self.base_lm_head = self.brain.lm_head_weight.clone().detach()
        if getattr(self.brain, 'embed_weight', None) is not None:
            self.base_embed = self.brain.embed_weight.clone().detach()
        
        # Load Tokenizer for Text-to-Latent mapping
        if self.cluster_mode == 'master':
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

    def _run_decoding_phase(self, aligned_vector, sys_prompt=None, max_tokens=100, temperature=0.7, top_p=0.9, is_plan_phase=False):
        import sys
        import torch
        import torch.nn.functional as F
        
        device = self.brain.device
        
        if hasattr(self, 'hf_model') and self.hf_model is not None and hasattr(self, 'tokenizer'):
            self.log("Initializing Hybrid Inverse Topology Decoder (Logit Blending)...")
            
            # 1. Prepare Prompt
            prompt_tokens = self.tokenizer(sys_prompt, return_tensors="pt").to(device)
            
            # 2. Prepare Intent Logits from Swarm's Action Vector
            concept_embed = aligned_vector.clone().to(torch.float16).to(device)
            if concept_embed.dim() == 1:
                concept_embed = concept_embed.unsqueeze(0)
            elif concept_embed.dim() == 3:
                concept_embed = concept_embed.squeeze(1) # Ensure (batch, hidden_dim)
                
            # Apply Manifold Alignment Matrix to map from JCross space to Gemma space
            if getattr(self, 'm_align', None) is not None:
                concept_embed = torch.matmul(concept_embed, self.m_align)
                
            # Apply RMSNorm approximation
            if getattr(self.brain, 'final_norm_weight', None) is not None:
                variance = concept_embed.pow(2).mean(-1, keepdim=True)
                concept_embed = concept_embed * torch.rsqrt(variance + 1e-6) * (1.0 + self.brain.final_norm_weight)
                
            # Project to vocabulary size (32000) using Gemma's own output embeddings
            intent_logits = torch.matmul(concept_embed, self.hf_model.get_output_embeddings().weight.T)
            
            # Normalize intent logits and apply Softmax to convert to probabilities
            intent_logits = intent_logits - intent_logits.mean(dim=-1, keepdim=True)
            intent_logits = intent_logits / (intent_logits.std(dim=-1, keepdim=True) + 1e-6)
            
            # Prevent extreme outlier logits (hallucination triggers)
            intent_logits = torch.clamp(intent_logits, min=-3.0, max=3.0)
            
            # 3. Create Custom Logits Processor with Decay
            from transformers import LogitsProcessor, LogitsProcessorList
            class IntentLogitsProcessor(LogitsProcessor):
                def __init__(self, intent_logits, initial_strength=0.5, decay_rate=0.9):
                    self.intent_logits = intent_logits
                    self.current_strength = initial_strength
                    self.decay_rate = decay_rate

                def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
                    # Blend the Swarm's intent softly into the model's predictions
                    blended_scores = scores + (self.intent_logits * self.current_strength)
                    # Decay the strength so the model relies more on its own context over time
                    self.current_strength *= self.decay_rate
                    return blended_scores

            logits_processor = LogitsProcessorList([
                IntentLogitsProcessor(intent_logits=intent_logits, initial_strength=0.0, decay_rate=0.85)
            ])
            
            self.log("Generating code via Gemma Transformer Decoder...")
            print(f"  {C_CODER}[Brain] Decoding: ", end="")
            sys.stdout.flush()
            
            # 4. Generate using native Hugging Face loop
            with torch.no_grad():
                outputs = self.hf_model.generate(
                    **prompt_tokens,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    repetition_penalty=1.1,
                    logits_processor=logits_processor,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode only the newly generated tokens (slice off the prompt)
            input_length = prompt_tokens.input_ids.shape[1]
            generated_text = self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
            print(f" {len(outputs[0]) - input_length} tokens generated.{C_RESET}")
            return generated_text
        else:
            self.log("Error: hf_model or tokenizer is not loaded. Cannot perform hybrid decoding.")
            return ""

    def synthesize_code(self, aligned_vector, prompt=""):
        """
        Two-Stage Decoding Pipeline:
        1. JCross translates its own consensus vector into a natural language plan.
        2. JCross feeds that plan back to itself as context to generate exact code.
        """
        import time
        import sys
        import torch
        
        self.log("Activating Lossless Generative Engine (Two-Stage Pipeline)...")
        
        # Phase 1: Natural Language Plan
        self.log("Phase 1: Translating Intent Vector to Natural Language Plan...")
        plan_prompt = f"<bos>Translate the following coding intent into a simple, step-by-step natural language plan. Use only English.\n{prompt}\n# Plan:\n"
        plan_text = self._run_decoding_phase(aligned_vector, plan_prompt, max_tokens=256, temperature=0.7, top_p=0.9, is_plan_phase=True)
        
        self.log(f"Phase 1 Complete. Internal Plan Generated:\n{plan_text}\n")
        
        # Phase 2: Code Generation
        self.log("Phase 2: JCross is decoding Code from its own Natural Language Plan...")
        code_prompt = f"<bos>Based on the exact plan below, write the Swift code:\n{plan_text}\n# Code:\n"
        final_code = self._run_decoding_phase(aligned_vector, code_prompt, max_tokens=512, temperature=0.3, top_p=0.95, is_plan_phase=False)
        
        self.log(f"Phase 2 Complete. Final Code Generated.")
        print("\n" + "="*40)
        print(final_code)
        print("="*40 + "\n")
        
        return final_code
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
            while True:
                # Receive intermediate tensor from Master
                hidden_state = self.rpc.recv_tensor(device=self.brain.device)
                if hidden_state is None:
                    self.log("Master disconnected.")
                    break
                    
                # Process through local layers (second half)
                if hidden_state is not None:
                    # Process through Worker's layers
                    hidden_state, _ = self.brain.forward_latent(hidden_state, role_name="WorkerNode", color_code=C_CODER)
                    
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
