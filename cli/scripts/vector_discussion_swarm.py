import torch
import os
import json
import requests
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation.streamers import TextStreamer

# --- ANSI Color Codes for UI ---
C_WORKER = "\033[36m"    # Cyan
C_CMDR   = "\033[33m"    # Yellow/Orange
C_SYS    = "\033[90m"    # Gray (System info)
C_GLOW   = "\033[32m"    # Green (Glowing Vectors)
C_RESET  = "\033[0m"

class VectorDiscussionSwarm:
    def __init__(self, gemma_path="/Users/motonishikoudai/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2", qwen_daemon_url="http://127.0.0.1:5055/chat"):
        self.gemma_path = gemma_path
        self.qwen_daemon_url = qwen_daemon_url
        self.tokenizer = None
        self.model = None
        self.glowing_activations = []
        self.hook_handle = None

    def boot(self):
        print(f"{C_SYS}[System] Booting Worker (Gemma) on CPU (bfloat16) for stable precision...{C_RESET}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.gemma_path, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.gemma_path, 
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
                device_map="cpu"
            )
            print(f"{C_SYS}[System] Gemma successfully loaded on CPU.{C_RESET}")
            
            # Attach the hook to capture glowing concepts
            # Gemma 2 usually has 42 layers (9b/12b). We hook a middle/late layer (e.g. layer 30)
            if hasattr(self.model.model, 'layers') and len(self.model.model.layers) > 30:
                layer_to_hook = self.model.model.layers[30]
            else:
                layer_to_hook = self.model.model.layers[-1]
                
            self.hook_handle = layer_to_hook.register_forward_hook(self._capture_glow_hook)
            print(f"{C_SYS}[System] Sensory Hook attached for Vector Extraction.{C_RESET}")
        except Exception as e:
            print(f"{C_SYS}[Error] Failed to load model: {e}{C_RESET}")

    def _capture_glow_hook(self, module, args, output):
        # output is usually a tuple where [0] is hidden_states
        hidden_states = output[0] if isinstance(output, tuple) else output
        # Get the activation magnitude of the last generated token
        last_token_state = hidden_states[:, -1:, :]
        # L2 Norm represents the "energy" or "glow" of the concept
        magnitude = torch.norm(last_token_state, dim=-1).item()
        self.glowing_activations.append(magnitude)
        return output

    def run_worker_draft(self, prompt: str) -> tuple[str, list]:
        print(f"\n{C_WORKER}=== WORKER (Gemma) DRAFTING ==={C_RESET}")
        self.glowing_activations = [] # Reset glow log
        
        formatted_prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        
        streamer = TextStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        print(f"{C_WORKER}", end="")
        output_ids = self.model.generate(
            **inputs, 
            max_new_tokens=4096,
            streamer=streamer,
            do_sample=True,
            temperature=0.3,
            top_p=0.9,
            repetition_penalty=1.1
        )
        print(f"{C_RESET}")
        
        generated_ids = output_ids[0][inputs.input_ids.shape[1]:]
        draft_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        
        # Correlate tokens with their glow
        tokens = self.tokenizer.convert_ids_to_tokens(generated_ids)
        # Ensure lengths match
        min_len = min(len(tokens), len(self.glowing_activations))
        
        glowing_concepts = []
        if self.glowing_activations:
            # Dynamically calculate threshold: top 5% of energies
            sorted_mags = sorted(self.glowing_activations)
            threshold = sorted_mags[int(len(sorted_mags) * 0.95)] if len(sorted_mags) > 20 else 50.0
            
            for i in range(min_len):
                if self.glowing_activations[i] >= threshold:
                    word = tokens[i].replace(" ", "")
                    if len(word) > 2 and word not in ["<eos>", "<bos>", "\\n", "<start_of_turn>", "<end_of_turn>"]:
                        glowing_concepts.append(word)
                    
        return draft_text, glowing_concepts

    def run_arbiter_review(self, task: str, draft: str, glowing_concepts: list) -> str:
        print(f"\n{C_CMDR}=== ARBITER (Qwen Puzzle Logic) REVIEW ==={C_RESET}")
        unique_concepts = list(set(glowing_concepts))
        print(f"{C_GLOW}[Extracted Glowing Vectors]: {', '.join(unique_concepts)}{C_RESET}")
        
        system_prompt = (
            "You are the Arbiter (Qwen Puzzle Engine). A Worker has drafted code for a task. "
            "You must review the draft for logical flaws, mathematical correctness, and system integrity. "
            f"The Worker heavily focused on these internal semantic vectors during generation: {unique_concepts}. "
            "If the code is flawless, reply with 'APPROVED'. If there are errors (like ABA problems, memory leaks, wrong mmap flags), "
            "explain the logical flaw concisely and provide the corrected logic."
        )
        
        user_message = f"Task: {task}\n\nWorker Draft:\n{draft}"
        
        try:
            # Try to hit the Qwen Daemon
            res = requests.post(self.qwen_daemon_url, json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            }, timeout=10)
            
            if res.ok:
                review = res.json().get("response", "")
                print(f"{C_CMDR}{review}{C_RESET}")
                return review
            else:
                raise Exception("Daemon returned non-200")
        except Exception as e:
            print(f"{C_SYS}[System] Qwen Daemon offline or unreachable. Falling back to internal Arbiter (Gemma Self-Review).{C_RESET}")
            # Fallback: Use Gemma itself as the Arbiter if Qwen is not running
            fallback_prompt = f"<start_of_turn>user\n{system_prompt}\n\n{user_message}<end_of_turn>\n<start_of_turn>model\n"
            inputs = self.tokenizer(fallback_prompt, return_tensors="pt")
            streamer = TextStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            print(f"{C_CMDR}", end="")
            out = self.model.generate(**inputs, max_new_tokens=4096, streamer=streamer, do_sample=True, temperature=0.1)
            print(f"{C_RESET}")
            
            gen_ids = out[0][inputs.input_ids.shape[1]:]
            return self.tokenizer.decode(gen_ids, skip_special_tokens=True)

    def interactive_loop(self):
        print(f"{C_SYS}Vector Discussion Swarm Initiated. Type 'exit' on the first line to quit.{C_RESET}")
        import sys
        while True:
            try:
                print(f"\n{C_SYS}User Task (Paste your prompt. Press Ctrl+D on a new line to submit) > {C_RESET}")
                lines = []
                while True:
                    try:
                        line = input()
                        lines.append(line)
                    except EOFError:
                        break
                
                user_input = "\n".join(lines)
                
                if user_input.strip().lower() in ['exit', 'quit']:
                    break
                if not user_input.strip():
                    continue
                
                # Phase 1: Worker Draft
                draft, concepts = self.run_worker_draft(user_input)
                
                # Phase 2: Arbiter Review (Puzzle Inference)
                review = self.run_arbiter_review(user_input, draft, concepts)
                
                # Phase 3: Final Consolidation (if Arbiter rejected)
                if "APPROVED" not in review.upper():
                    print(f"\n{C_WORKER}=== WORKER (Final Revision) ==={C_RESET}")
                    final_prompt = (
                        f"Task: {user_input}\n\n"
                        f"Your previous draft had flaws. The Arbiter left this critique:\n{review}\n\n"
                        f"Please output the final, corrected implementation based on this critique."
                    )
                    self.run_worker_draft(final_prompt)
                else:
                    print(f"\n{C_WORKER}[Worker] Task completed and approved by Arbiter.{C_RESET}")
                    
            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                break

if __name__ == "__main__":
    swarm = VectorDiscussionSwarm()
    swarm.boot()
    swarm.interactive_loop()
