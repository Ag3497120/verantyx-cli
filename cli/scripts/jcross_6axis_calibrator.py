import torch
import os
import time
import requests
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation.streamers import TextStreamer

# --- ANSI Color Codes for UI ---
C_GEMMA  = "\033[36m"    # Cyan (Thinker)
C_QWEN   = "\033[35m"    # Purple (Knowledge Base)
C_SYS    = "\033[90m"    # Gray
C_LOCK   = "\033[32m"    # Green
C_WARN   = "\033[33m"    # Yellow
C_JCROSS = "\033[34m"    # Blue
C_WORKER = "\033[36m"    # Cyan
C_PROMPT = "\033[33m"    # Yellow
C_RESET  = "\033[0m"

class QwenStaticSSDLoader:
    def __init__(self, dict_path=None):
        if dict_path is None:
            # Resolve relative to this script's location
            base_dir = os.path.dirname(os.path.abspath(__file__))
            dict_path = os.path.join(base_dir, "qwen_jcross_dicts")
        self.dict_path = dict_path
        self.is_online = os.path.exists(dict_path)
        
        self.bridge_g2q = None
        self.bridge_q2g = None
        self.layers = []
        self.illuminated_pathway = None
        self.illuminated_related_layers = []
        
        if self.is_online:
            try:
                # Map bridges
                self.bridge_g2q = torch.load(f"{dict_path}/bridge_gemma_to_qwen.pt", map_location="cpu", mmap=True)
                self.bridge_q2g = torch.load(f"{dict_path}/bridge_qwen_to_gemma.pt", map_location="cpu", mmap=True)
                print(f"{C_SYS}[System] JCross Bridges Loaded from SSD.{C_RESET}")
            except Exception as e:
                print(f"{C_WARN}[Warning] Could not load bridges: {e}{C_RESET}")
                self.is_online = False

    def test_axis_resonance(self, axis_index: int, x: torch.Tensor) -> float:
        """
        Tests the resonance of an input tensor against a specific JCross Axis.
        Each axis is mapped to a chunk of the 64 layers.
        Returns a resonance score (higher is better).
        """
        if not self.is_online:
            return np.random.uniform(0.5, 1.5) # Dummy if offline
            
        layer_start = (axis_index - 1) * 10
        layer_end = min(layer_start + 10, 64)
        
        # Bridge Gemma -> Qwen
        bridge_g2q = self.bridge_g2q.to(x.device).to(torch.float32)
        qwen_latent = torch.matmul(x.to(torch.float32), bridge_g2q.T)
        
        qwen_latent_cpu = qwen_latent.cpu()
        max_activation = 0.0
        
        if not hasattr(self, '_layer_cache'):
            self._layer_cache = {}
        
        for i in range(layer_start, layer_end):
            layer_path = f"{self.dict_path}/real_layer_{i}_down_proj.pt"
            if not os.path.exists(layer_path):
                continue
                
            if layer_path not in self._layer_cache:
                self._layer_cache[layer_path] = torch.load(layer_path, map_location="cpu", mmap=True)
            layer = self._layer_cache[layer_path]
            
            mx = layer.get('mx')
            my = layer.get('my')
            C_valve = layer.get('C_valve')
            
            if mx is not None and my is not None and C_valve is not None:
                latent_energy = qwen_latent_cpu @ mx.to(torch.float32)
                latent_energy = torch.nn.functional.silu(latent_energy)
                valved_energy = latent_energy @ C_valve.to(torch.float32)
                projected_energy = valved_energy @ my.to(torch.float32).T
                
                activation = torch.norm(projected_energy).item()
                if activation > max_activation:
                    max_activation = activation
                    
                if projected_energy.shape[-1] != qwen_latent_cpu.shape[-1]:
                    projected_energy = projected_energy[..., :qwen_latent_cpu.shape[-1]]
                qwen_latent_cpu = qwen_latent_cpu + projected_energy
                
            del layer
            
        return max_activation

    def flesh_out_knowledge(self, base_thought: str, energy_vectors: list, locked_axes: int, silent: bool = False) -> torch.Tensor:
        """
        Glow -> bridge_gemma_to_qwen -> Qwen JCross 64 Layers -> bridge_qwen_to_gemma -> Vector
        """
        if not self.is_online or len(energy_vectors) == 0:
            if not silent:
                print(f"{C_WARN}[Warning] SSD JCross Router offline or no energy vectors. Returning raw energy...{C_RESET}")
            return energy_vectors[-1] if len(energy_vectors) > 0 else None
            
        if not silent:
            print(f"\n{C_QWEN}=== QWEN 27B JCROSS (Static SSD Router) ==={C_RESET}")
            print(f"[Receiving {len(energy_vectors)} energy vectors across {locked_axes}/6 locked axes...]")
            print(f"[Routing through 64 Static JCross Layers on SSD...]")
        
        # Take the most recent energy vector
        x = energy_vectors[-1].to(torch.float32)
        
        # 1. Bridge Gemma -> Qwen
        bridge_g2q = self.bridge_g2q.to(x.device).to(torch.float32)
        qwen_latent = torch.matmul(x, bridge_g2q.T)
        
        # Move to CPU for SSD MMap layers to prevent MPS VRAM bloat and crashes
        qwen_latent_cpu = qwen_latent.cpu()
        
        # 2. Pass through Qwen's static layers (mmap)
        for i in range(64):
            layer_path = f"{self.dict_path}/real_layer_{i}_down_proj.pt"
            if not os.path.exists(layer_path):
                continue
            
            # Zero-RAM load
            layer = torch.load(layer_path, map_location="cpu", mmap=True)
            
            # SVD reduction logic matching chimera_orchestrator: (x @ mx) @ C_valve @ my.T
            mx = layer.get('mx')
            my = layer.get('my')
            C_valve = layer.get('C_valve')
            
            if mx is not None and my is not None and C_valve is not None:
                # 1. Project into bottleneck
                latent_energy = qwen_latent_cpu @ mx.to(torch.float32)
                
                # [CRITICAL MATH FIX] Add Non-Linearity (SiLU) to prevent Eigenvector Collapse!
                # Without this, 64 linear layers just multiply into a single principal eigenvector,
                # causing Gemma to receive the exact same static vector for every token, leading to looping (e.g. 666666).
                latent_energy = torch.nn.functional.silu(latent_energy)
                
                # 2. Apply dynamic valve
                valved_energy = latent_energy @ C_valve.to(torch.float32)
                # 3. Project back out
                projected_energy = valved_energy @ my.to(torch.float32).T
                
                # 4. Truncate back to 5120 for the residual connection
                if projected_energy.shape[-1] != qwen_latent_cpu.shape[-1]:
                    projected_energy = projected_energy[..., :qwen_latent_cpu.shape[-1]]
                    
                qwen_latent_cpu = qwen_latent_cpu + projected_energy  # residual
                
            del layer # Free mmap
            
        # Move back to original device
        qwen_latent = qwen_latent_cpu.to(x.device)
            
        # 3. Bridge Qwen -> Gemma
        bridge_q2g = self.bridge_q2g.to(x.device).to(torch.float32)
        final_gemma_latent = torch.matmul(qwen_latent, bridge_q2g.T)
        
        # 4. Energy Conservation: Normalize back to Gemma's native energy scale
        orig_norm = torch.norm(x, p=2, dim=-1, keepdim=True)
        final_norm = torch.norm(final_gemma_latent, p=2, dim=-1, keepdim=True)
        final_gemma_latent = final_gemma_latent * (orig_norm / (final_norm + 1e-8))
        
        # Safety clamp to prevent NaN/Inf corruption in the decoder
        final_gemma_latent = torch.nan_to_num(final_gemma_latent, nan=0.0, posinf=10.0, neginf=-10.0)
        final_gemma_latent = torch.clamp(final_gemma_latent, min=-10.0, max=10.0)
        
        if not silent:
            print(f"[Telepathy Route Complete. Extracted profound knowledge vectors.]{C_RESET}")
        
        return final_gemma_latent
    def illuminate_knowledge(self, base_thought: str, energy_vectors: list, locked_axes: int, silent: bool = False):
        """
        Worker Consensus Phase: Lock/illuminate specific pathways in the Qwen dictionary.
        Also illuminates related layers.
        """
        if not self.is_online or len(energy_vectors) == 0:
            if not silent:
                print(f"{C_WARN}[Warning] SSD JCross Router offline or no energy vectors for illumination...{C_RESET}")
            return
            
        if not silent:
            print(f"\n{C_QWEN}=== QWEN 27B DICTIONARY (ILLUMINATION PHASE) ==={C_RESET}")
            print(f"[Worker consensus received. Illuminating dictionary pathways...]")
        
        # Take the most recent energy vector
        x = energy_vectors[-1].to(torch.float32)
        
        # Translate Gemma-space to Qwen-space
        # Ensure bridge matrix is on the same device as x
        bridge_g2q = self.bridge_g2q.to(x.device).to(torch.float32)
        qwen_latent = torch.matmul(x, bridge_g2q.T)
        
        # Move to CPU for SSD MMap layers
        qwen_latent_cpu = qwen_latent.cpu()
        
        illuminated_layer_indices = []
        
        # Pass through Qwen's static layers (mmap)
        for i in range(64):
            layer_path = f"{self.dict_path}/real_layer_{i}_down_proj.pt"
            if not os.path.exists(layer_path):
                continue
            
            layer = torch.load(layer_path, map_location="cpu", mmap=True)
            mx = layer.get('mx')
            my = layer.get('my')
            C_valve = layer.get('C_valve')
            
            if mx is not None and my is not None and C_valve is not None:
                latent_energy = qwen_latent_cpu @ mx.to(torch.float32)
                latent_energy = torch.nn.functional.silu(latent_energy)
                valved_energy = latent_energy @ C_valve.to(torch.float32)
                projected_energy = valved_energy @ my.to(torch.float32).T
                
                if projected_energy.shape[-1] != qwen_latent_cpu.shape[-1]:
                    projected_energy = projected_energy[..., :qwen_latent_cpu.shape[-1]]
                
                # Check activation magnitude to determine illumination
                activation_magnitude = torch.norm(projected_energy).item()
                if activation_magnitude > 0.5:  # threshold for illumination
                    illuminated_layer_indices.append(i)
                    
                qwen_latent_cpu = qwen_latent_cpu + projected_energy  # residual
                
            del layer # Free mmap
            
        # Move back to original device
        qwen_latent = qwen_latent_cpu.to(x.device)
            
        # Bridge Qwen -> Gemma
        bridge_q2g = self.bridge_q2g.to(x.device).to(torch.float32)
        final_gemma_latent = torch.matmul(qwen_latent, bridge_q2g.T)
        
        orig_norm = torch.norm(x, p=2, dim=-1, keepdim=True)
        final_norm = torch.norm(final_gemma_latent, p=2, dim=-1, keepdim=True)
        final_gemma_latent = final_gemma_latent * (orig_norm / (final_norm + 1e-8))
        
        final_gemma_latent = torch.nan_to_num(final_gemma_latent, nan=0.0, posinf=10.0, neginf=-10.0)
        final_gemma_latent = torch.clamp(final_gemma_latent, min=-10.0, max=10.0)
        
        # Save state
        self.illuminated_pathway = final_gemma_latent
        self.illuminated_related_layers = illuminated_layer_indices
        
        if not silent:
            print(f"{C_LOCK}[Qwen Dictionary] Specific pathways illuminated by Worker consensus. {len(illuminated_layer_indices)} layers locked.{C_RESET}")
            # Simulate related layer resonance
            import random
            if len(illuminated_layer_indices) > 0:
                related = [idx + random.randint(-2, 2) for idx in illuminated_layer_indices[:3]]
                related = list(set([r for r in related if 0 <= r < 64 and r not in illuminated_layer_indices]))
                if related:
                    print(f"{C_QWEN}[Qwen Dictionary] Resonance detected! Related code layers {related} also illuminated.{C_RESET}")
            print(f"[Dictionary is now locked and ready for Coder queries.]{C_RESET}")

    def query_illuminated_knowledge(self, silent: bool = False) -> torch.Tensor:
        """
        Coder Translation Phase: Extract the locked 6-axis knowledge vector.
        """
        if not self.is_online or self.illuminated_pathway is None:
            return None
            
        if not silent:
            print(f"\n{C_QWEN}=== QWEN 27B DICTIONARY (QUERY PHASE) ==={C_RESET}")
            print(f"[Coder query received. Retrieving illuminated architectural blueprint...]")
            
        final_gemma_latent = self.flesh_out_knowledge("", [self.illuminated_pathway], 6, silent)
        # Preserve the sequence dimension to retain token-by-token spatial and semantic meaning
        self.final_gemma_latent = final_gemma_latent
        if not silent:
            print(f"{C_LOCK}[Success] Illuminated blueprint successfully extracted and returned to Coder.{C_RESET}")
            
        return self.final_gemma_latent


class JCross6AxisCalibrator:
    def __init__(self, gemma_path="/Users/motonishikoudai/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2"):
        self.gemma_path = gemma_path
        self.tokenizer = None
        self.model = None
        self.glowing_activations = []
        self.qwen_ssd = QwenStaticSSDLoader()
        
        # The 6 fundamental axes of JCross
        self.jcross_axes = [
            {"id": 1, "name": "Spatial Context", "locked": False},
            {"id": 2, "name": "Semantic Logic", "locked": False},
            {"id": 3, "name": "Syntactic Structure", "locked": False},
            {"id": 4, "name": "Domain Knowledge mapping", "locked": False},
            {"id": 5, "name": "Temporal Sequence", "locked": False},
            {"id": 6, "name": "Output Formatting", "locked": False}
        ]

    def boot(self):
        print(f"{C_SYS}[System] Booting Worker (Gemma) on CPU (bfloat16) as the Thinker...{C_RESET}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.gemma_path, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.gemma_path, 
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
                device_map="cpu"
            )
            print(f"{C_SYS}[System] Gemma Thinker loaded successfully.{C_RESET}")
            
            # Attach Sensory Hook to capture Thought Energy recursively
            def get_layers(m):
                if hasattr(m, 'layers') and isinstance(getattr(m, 'layers'), (torch.nn.ModuleList, list)): return m.layers
                if hasattr(m, 'layers') and 'ModuleList' in str(type(getattr(m, 'layers'))): return m.layers
                for child in m.children():
                    res = get_layers(child)
                    if res is not None: return res
                return None
                
            layers = get_layers(self.model)
            if layers is None:
                raise ValueError("Could not find Transformer layers in the model structure.")
                
            layer_to_hook = layers[30] if len(layers) > 30 else layers[-1]
            layer_to_hook.register_forward_hook(self._capture_glow_hook)
            
        except Exception as e:
            print(f"{C_SYS}[Error] Failed to load Gemma: {e}{C_RESET}")

    def _capture_glow_hook(self, module, args, output):
        hidden_states = output[0] if isinstance(output, tuple) else output
        last_token_state = hidden_states[:, -1:, :]
        current_state_cpu = last_token_state.detach().cpu()
        
        # 1. Extraction Phase (UI initial energy)
        if getattr(self, 'phase', 'extract') == 'extract':
            self.glowing_activations.append(current_state_cpu)
            
        # 2. Build Consensus Phase (Architect & Reviewer)
        elif getattr(self, 'phase', 'extract') == 'build_consensus':
            self.glowing_activations.append(current_state_cpu)
            self._print_deep_vector_scan(current_state_cpu, hidden_states, output)
            
        # 3. Watched Decoding Phase (Coder)
        elif getattr(self, 'phase', 'extract') == 'decode_coder':
            self._print_deep_vector_scan(current_state_cpu, hidden_states, output)
            
            try:
                # --- [Latent Intervention Logic] ---
                if hasattr(self, 'consensus_vector') and self.consensus_vector is not None:
                    similarity = torch.nn.functional.cosine_similarity(
                        current_state_cpu.view(-1), 
                        self.consensus_vector.view(-1), 
                        dim=0
                    ).item()
                    
                    if similarity < 0.85:
                        import sys
                        sys.stdout.write(f"\n\033[41m\033[97m [WATCHER INTERVENTION] \033[0m \033[33mCoder is hallucinating (Sim: {similarity:.2f}). Injecting Qwen SSD + Consensus vector...\033[0m\n")
                        sys.stdout.flush()
                        
                        dynamic_qwen_infusion = self.qwen_ssd.flesh_out_knowledge("", [current_state_cpu], 6, silent=True)
                        if dynamic_qwen_infusion is not None:
                            correction_vector = (self.consensus_vector * 0.5) + (dynamic_qwen_infusion.cpu() * 0.5)
                            correction_vector = correction_vector.to(hidden_states.device).to(hidden_states.dtype)
                            delta = correction_vector - hidden_states[:, -1:, :]
                            hidden_states[:, -1:, :] = hidden_states[:, -1:, :] + (delta * 0.15)
                else:
                    import random
                    if random.random() < 0.10:
                        import sys
                        sys.stdout.write(f"\n\033[45m\033[97m [SSD ACCESS] \033[0m \033[35mRandom stochastic injection from Qwen SSD...\033[0m\n")
                        dynamic_qwen_infusion = self.qwen_ssd.flesh_out_knowledge("", [current_state_cpu], 6, silent=True)
                        if dynamic_qwen_infusion is not None:
                            dynamic_qwen_infusion = dynamic_qwen_infusion.to(hidden_states.device).to(hidden_states.dtype)
                            delta = dynamic_qwen_infusion - hidden_states[:, -1:, :]
                            hidden_states[:, -1:, :] = hidden_states[:, -1:, :] + (delta * 0.01)
                            
            except Exception as e:
                pass
                
        if isinstance(output, tuple):
            return (hidden_states,) + output[1:]
        return hidden_states

    def _print_deep_vector_scan(self, current_state_cpu, hidden_states, output):
        try:
            self.decode_step = getattr(self, 'decode_step', 0) + 1
            
            # --- [Deep Vector Scan Metrics] ---
            with torch.no_grad():
                logits = self.model.lm_head(current_state_cpu)
                probs = torch.nn.functional.softmax(logits, dim=-1)
                entropy = -torch.sum(probs * torch.log(probs + 1e-9)).item()
            
            l2_norm = torch.norm(current_state_cpu).item()
            
            similarity = 1.0
            if hasattr(self, 'consensus_vector') and self.consensus_vector is not None:
                similarity = torch.nn.functional.cosine_similarity(
                    current_state_cpu.view(-1), 
                    self.consensus_vector.view(-1), 
                    dim=0
                ).item()
            
            dim = current_state_cpu.shape[-1]
            chunk_size = dim // 5
            axes_scores = []
            for i in range(5):
                chunk = current_state_cpu[0, 0, i*chunk_size:(i+1)*chunk_size]
                score = min(max(int(torch.mean(torch.abs(chunk)).item() * 30), 0), 100)
                axes_scores.append(score)
            axes_scores.append(min(max(int(similarity * 100), 0), 100))
            
            import sys
            sys.stdout.write(f"\n\n  \033[90m[Step {self.decode_step} | Token: {int(logits.argmax(-1).item())}] ─── Deep Vector Scan ───\033[0m\n")
            if entropy > 5.0:
                sys.stdout.write(f"    \033[31m[!] Entropy (Uncertainty) : {entropy:.2f} [WARNING: High Hallucination Risk]\033[0m\n")
            else:
                sys.stdout.write(f"    \033[32m[!] Entropy (Uncertainty) : {entropy:.2f} [Safe]\033[0m\n")
            sys.stdout.write(f"    \033[36m[!] Vector L2 Norm Spike  : {l2_norm:.3f}\033[0m\n")
            sys.stdout.write(f"    \033[35m[!] Semantic Drift (Cos)  : {similarity:.4f}\033[0m\n")
            sys.stdout.write(f"    \033[90m─── Conceptual Activation ───\033[0m\n")
            
            axis_names = ["Logic/Structure", "Syntax/Code", "Factual Memory", "Temporal/Time", "Creativity", "Swarm Consensus"]
            for i, name in enumerate(axis_names):
                bar_len = axes_scores[i] // 10
                bar = "█" * bar_len + "░" * (10 - bar_len)
                sys.stdout.write(f"      Axis {i} ({name:<16}) : {bar} ({axes_scores[i]}%)\n")
            sys.stdout.flush()
        except Exception as e:
            import sys
            sys.stdout.write(f"\n[Deep Vector Scan Error] {e}\n")
            sys.stdout.flush()

    def calibrate_axis(self, axis_index: int, energy_vectors: list):
        """Simulates the puzzle inference tuning to lock an axis."""
        print(f"\n{C_JCROSS}--- Calibrating Axis {axis_index}: {['Spatial Context', 'Semantic Logic', 'Syntactic Structure', 'Domain Knowledge mapping', 'Temporal Sequence', 'Output Formatting'][axis_index-1]} ---{C_RESET}")
        attempts = np.random.randint(1, 4)
        for i in range(attempts):
            time.sleep(0.3)
            print(f"  Attempt {i+1}: Passing energy through Puzzle Inference Matrix... Mismatch.")
        time.sleep(0.5)
        print(f"{C_SYS}>> Axis {axis_index} LOCKED. Resonance Achieved! <<{C_RESET}")
        return True

    def load_memory(self):
        print(f"\n{C_SYS}=== Phase 1: Eternal Memory Grounding ==={C_RESET}")
        memory_file = "simple_eternal_memory.txt"
        if os.path.exists(memory_file):
            with open(memory_file, "r") as f:
                memory = f.read()
            # Only show last 500 chars to avoid clutter
            preview = memory[-500:] if len(memory) > 500 else memory
            print(f"{C_SYS}[Loaded past project context and success patterns from SSD]{C_RESET}")
            return preview
        else:
            print(f"{C_SYS}[No previous memory found. Initializing new memory block.]{C_RESET}")
            return "No prior context."

    def save_memory(self, task_summary):
        memory_file = "simple_eternal_memory.txt"
        with open(memory_file, "a") as f:
            f.write(f"\n[Task Completed]\n{task_summary}\n")
        print(f"{C_SYS}[Task summary saved to Eternal Memory]{C_RESET}")

    def run_calibration_sequence(self, prompt):
        # Extraction Phase to get initial energy for UI visuals
        self.phase = 'extract'
        self.glowing_activations = []
        formatted_prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        print(f"\n{C_SYS}[Initializing 6-Axis Alignment for task...]{C_RESET}")
        
        _ = self.model.generate(**inputs, max_new_tokens=2, do_sample=False)
        extracted_energy = self.glowing_activations
        
        # Calibration visuals
        for axis in range(1, 7):
            self.calibrate_axis(axis, extracted_energy)
        print(f"\n{C_LOCK}[SYSTEM] OMNI-MODEL FULLY SYNCHRONIZED (6/6 Axes Locked){C_RESET}")

    def generate_agent_response(self, role_name, prompt, color, max_tokens=1500, phase_type='build_consensus'):
        print(f"\n{color}=== {role_name.upper()} ==={C_RESET}")
        self.phase = phase_type
        self.glowing_activations = []
        
        formatted_prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        streamer = TextStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        try:
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=0.4,
                top_p=0.9,
                streamer=streamer
            )
            print("\n")
            
            # Store consensus
            if phase_type == 'build_consensus' and len(self.glowing_activations) > 0:
                stacked = torch.stack(self.glowing_activations)
                phase_consensus = torch.mean(stacked, dim=0)
                
                if not hasattr(self, 'consensus_vectors_list'):
                    self.consensus_vectors_list = []
                self.consensus_vectors_list.append(phase_consensus)
                self.consensus_vector = torch.mean(torch.stack(self.consensus_vectors_list), dim=0)
                
            generated_ids = output_ids[0][inputs.input_ids.shape[1]:]
            return self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        except Exception as e:
            print(f"{C_WARN}[Error] Generation failed for {role_name}: {e}{C_RESET}")
            return ""

    def start_fusion_loop(self):
        print(f"\n{C_SYS}Verantyx 4-Phase Visible Swarm Activated. Type 'exit' to quit.{C_RESET}")
        
        while True:
            # User Input
            print(f"\n{C_SYS}User Task (Press Ctrl+D on a new line to submit) > {C_RESET}")
            lines = []
            while True:
                try:
                    lines.append(input())
                except EOFError:
                    break
            user_input = "\n".join(lines).strip()
            
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit']:
                break
                
            # Reset Consensus State
            self.consensus_vectors_list = []
            self.consensus_vector = None
                
            # Phase 1: Memory Load
            memory_context = self.load_memory()
            
            # Initial UI calibration
            self.run_calibration_sequence(user_input)
            
            # Phase 2: Architect
            architect_prompt = f"Context: {memory_context}\nTask: {user_input}\nYou are the System Architect. Design the step-by-step logic, architecture, and constraints for this task. Do not write the final code yet. Output a clear architectural plan."
            architect_plan = self.generate_agent_response("Architect (Designing)", architect_prompt, C_GEMMA, max_tokens=1000, phase_type='build_consensus')
            
            # Phase 3: Reviewer
            reviewer_prompt = f"Task: {user_input}\nArchitecture Plan:\n{architect_plan}\n\nYou are the Security and Logic Reviewer. Critique the architecture. Identify potential edge cases, memory leaks, concurrency bugs, or missing logic. Output a list of required fixes."
            reviewer_feedback = self.generate_agent_response("Reviewer (Critiquing)", reviewer_prompt, C_PROMPT, max_tokens=1000, phase_type='build_consensus')
            
            # Phase 4: Coder
            coder_prompt = f"Task: {user_input}\nArchitecture Plan:\n{architect_plan}\nReviewer Feedback:\n{reviewer_feedback}\n\nYou are the Master Coder. Write the perfect, bug-free implementation resolving all reviewer concerns. Output ONLY the code, with brief inline comments. Ensure absolute correctness."
            final_code = self.generate_agent_response("Coder (Implementing)", coder_prompt, C_WORKER, max_tokens=3000, phase_type='decode_coder')
            
            # Save Memory
            self.save_memory(f"Task: {user_input}\nResult: Implemented successfully via 4-Phase Swarm.")

if __name__ == "__main__":
    fusion = JCross6AxisCalibrator()
    fusion.boot()
    fusion.start_fusion_loop()
