import torch
import os
import time
from transformers import AutoTokenizer, AutoModelForCausalLM

C_CYAN = '\033[96m'
C_MAGENTA = '\033[95m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'

# =========================================================================
# 1. 6-Axis Chimera Bridge (Gemma 3840 <--> Qwen 5120)
# =========================================================================
class RealChimeraBridge:
    def __init__(self, dict_dir, dim_a=3840, dim_b=5120):
        self.dim_a = dim_a
        self.dim_b = dim_b
        
        file_ab = os.path.join(dict_dir, "bridge_gemma_to_qwen.pt")
        file_ba = os.path.join(dict_dir, "bridge_qwen_to_gemma.pt")
        
        if os.path.exists(file_ab) and os.path.exists(file_ba):
            print(f"{C_GREEN}[Bridge] Loading Calibrated Semantic Matrices to CPU...{C_RESET}")
            # Linear layer requires weight matrix
            self.proj_ab = torch.nn.Linear(dim_a, dim_b, bias=False).to(torch.float32)
            self.proj_ab.weight.data = torch.load(file_ab, map_location='cpu').to(torch.float32)
            
            self.proj_ba = torch.nn.Linear(dim_b, dim_a, bias=False).to(torch.float32)
            self.proj_ba.weight.data = torch.load(file_ba, map_location='cpu').to(torch.float32)
        else:
            print(f"{C_RED}[Bridge Error] Calibrated matrices not found. Falling back to random noise.{C_RESET}")
            torch.manual_seed(42)
            self.proj_ab = torch.nn.Linear(dim_a, dim_b, bias=False).to(torch.float32)
            self.proj_ba = torch.nn.Linear(dim_b, dim_a, bias=False).to(torch.float32)

    def translate_a_to_b(self, vec_a: torch.Tensor) -> torch.Tensor:
        return self.proj_ab(vec_a)

    def translate_b_to_a(self, vec_b: torch.Tensor) -> torch.Tensor:
        return self.proj_ba(vec_b)

# =========================================================================
# 2. Qwen Zero-RAM Dictionary Engine
# =========================================================================
class QwenPhysicalBackend:
    def __init__(self, dict_dir):
        self.dict_dir = dict_dir
        self.dim = 5120
        # Pre-scan layer files to avoid doing it every forward pass
        self.layer_files = [f for f in os.listdir(self.dict_dir) if f.startswith('real_layer_') and f.endswith('_down_proj.pt')]
        self.layer_files.sort(key=lambda x: int(x.split('_')[2]))
        
        if not self.layer_files:
            print(f"{C_RED}[Error] No JCross dictionaries found in {self.dict_dir}{C_RESET}")

    def process_latent_lookup(self, input_vector: torch.Tensor) -> torch.Tensor:
        current_state = input_vector.clone().to(torch.float32)
        
        for idx, layer_file in enumerate(self.layer_files):
            layer_path = os.path.join(self.dict_dir, layer_file)
            
            # Streaming Load directly to CPU
            jcross_dict = torch.load(layer_path, map_location='cpu')
            mx = jcross_dict['mx'].to(torch.float32)
            my = jcross_dict['my'].to(torch.float32)
            C_valve = jcross_dict['C_valve'].to(torch.float32)
            
            # JCross Compute (float32)
            latent_energy = current_state @ mx
            valved_energy = latent_energy @ C_valve
            projected_energy = valved_energy @ my.T
            
            if projected_energy.shape[-1] != self.dim:
                projected_energy = projected_energy[..., :self.dim]
                
            current_state = projected_energy
            
            # Zero-RAM Cleanup
            del jcross_dict, mx, my, C_valve
            
        return current_state

# =========================================================================
# 3. Telepathy Hook Logic
# =========================================================================
telepathy_count = 0

def create_telepathy_hook(bridge: RealChimeraBridge, qwen_backend: QwenPhysicalBackend):
    def hook_fn(module, input, output):
        global telepathy_count
        telepathy_count += 1
        
        # Output is typically a tuple (hidden_states, ...) in transformers
        hidden_states = output[0] if isinstance(output, tuple) else output
        
        # We intercept only the last token's state for generation
        intercepted_state = hidden_states[:, -1:, :]
        
        # 1. Translate Gemma vector (Float16) to Qwen dimension (Float32)
        qwen_intent = bridge.translate_a_to_b(intercepted_state.to(torch.float32))
        
        # 2. Look up meaning in Qwen's physical JCross dictionary (Float32)
        qwen_knowledge = qwen_backend.process_latent_lookup(qwen_intent)
        
        # 3. Translate back to Gemma dimension (Float32)
        gemma_knowledge = bridge.translate_b_to_a(qwen_knowledge)
        
        # Prevent NaN or infinite values (just in case)
        gemma_knowledge = torch.nan_to_num(gemma_knowledge, nan=0.0, posinf=10.0, neginf=-10.0)
        gemma_knowledge = torch.clamp(gemma_knowledge, min=-10.0, max=10.0)
        
        # 4. Inject Knowledge (Residual Addition)
        # Cast back to the model's native dtype before injecting
        gemma_knowledge = gemma_knowledge.to(hidden_states.dtype)
        alpha = 0.5
        hidden_states[:, -1:, :] = hidden_states[:, -1:, :] + (gemma_knowledge * alpha)
        
        if isinstance(output, tuple):
            return (hidden_states,) + output[1:]
        return hidden_states

    return hook_fn

# =========================================================================
# 4. Main Execution (Interactive Chat)
# =========================================================================
from transformers import TextStreamer

def run_telepathic_worker():
    print(f"\n{C_CYAN}========================================================================={C_RESET}")
    print(f"{C_CYAN}             VERANTYX CHIMERA AI (Gemma 12B + Qwen 27B)                  {C_RESET}")
    print(f"{C_CYAN}=========================================================================\n{C_RESET}")
    
    # 1. Initialize Subsystems
    dict_dir = os.path.join(os.path.dirname(__file__), "qwen_jcross_dicts")
    bridge = RealChimeraBridge(dict_dir=dict_dir)
    qwen = QwenPhysicalBackend(dict_dir=dict_dir)
    
    # 2. Load Gemma Frontend
    gemma_path = "/Users/motonishikoudai/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2"
    print(f"{C_YELLOW}[Init] Loading Gemma-4-12B Frontend (This will take significant RAM)...{C_RESET}")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(gemma_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            gemma_path, 
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="cpu"
        )
        print(f"{C_GREEN}[Success] Gemma 12B loaded on CPU!{C_RESET}")
    except Exception as e:
        print(f"{C_RED}[Error] Failed to load Gemma 12B natively: {e}{C_RESET}")
        return

    # 3. Perform Brain Surgery: Attach Hook to Middle Layer (Layer 24 out of 48)
    target_layer = 24
    print(f"{C_MAGENTA}[Surgery] Attaching Telepathy Hook to Gemma Layer {target_layer}...{C_RESET}")
    
    layer_module = None
    for name, module in model.named_modules():
        if name.endswith('.layers') or name.endswith('.layers.' + str(target_layer)):
            pass
            
    target_layer_name = None
    for name, _ in model.named_modules():
        if f'layers.{target_layer}' in name and len(name.split(f'layers.{target_layer}')[1]) == 0:
            target_layer_name = name
            break
            
    if target_layer_name is None:
        print(f"{C_RED}[Error] Could not find layer {target_layer} in Gemma.{C_RESET}")
        return
        
    layer_module = dict(model.named_modules())[target_layer_name]
    hook_handle = layer_module.register_forward_hook(create_telepathy_hook(bridge, qwen))
    
    print(f"{C_GREEN}[Ready] Chimera AI is ready. You are now chatting with the combined intelligence.{C_RESET}")
    print(f"{C_YELLOW}Type your message. Press Enter twice (leave an empty line) to submit.{C_RESET}")
    print(f"{C_YELLOW}Type 'exit' to end the session.{C_RESET}\n")
    
    # 4. Interactive Chat Loop
    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    while True:
        try:
            print(f"{C_CYAN}You: {C_RESET}")
            lines = []
            while True:
                line = input()
                if line.strip().lower() in ['exit', 'quit']:
                    return
                if line.strip() == "":
                    # Empty line submits the prompt
                    break
                lines.append(line)
                
            prompt = "\n".join(lines).strip()
            if not prompt:
                continue
                
            # Manually format the prompt using Gemma's standard chat template tokens
            formatted_prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
            inputs = tokenizer(formatted_prompt, return_tensors="pt") # CPU
            
            print(f"{C_MAGENTA}Chimera: {C_RESET}", end="")
            # Use sampling with repetition penalty to break out of latent traps caused by the unaligned bridge
            _ = model.generate(
                **inputs, 
                max_new_tokens=2048, 
                streamer=streamer,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.15
            )
            print("\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"{C_RED}[Error] {e}{C_RESET}")
    
    # Cleanup
    hook_handle.remove()
    print(f"{C_YELLOW}Session ended.{C_RESET}")

if __name__ == "__main__":
    run_telepathic_worker()
