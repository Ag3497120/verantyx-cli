import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
import json
import time
import sys

print("="*50)
print("🚀 Booting Verantyx Heterogeneous Swarm...")
print("="*50)

device = "mps" if torch.backends.mps.is_available() else "cpu"

# ---------------------------------------------------------
# 1. Commander Layer (7B Brain-Unmodified)
# ---------------------------------------------------------
print("Loading Commander (Qwen2-7B-Instruct)...")
commander_id = "Qwen/Qwen2-7B-Instruct"
commander_tokenizer = AutoTokenizer.from_pretrained(commander_id)
commander_model = AutoModelForCausalLM.from_pretrained(commander_id, torch_dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True)
commander_model.eval()

# ---------------------------------------------------------
# 2. Worker Layer (0.5B Surgically Modified CPU)
# ---------------------------------------------------------
print("Loading Worker CPU (Qwen1.5-0.5B-Chat)...")
worker_id = "Qwen/Qwen1.5-0.5B-Chat"
worker_tokenizer = AutoTokenizer.from_pretrained(worker_id)
worker_model = AutoModelForCausalLM.from_pretrained(worker_id, torch_dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True)

# Apply Surgery to Worker
class GenerativeLinear(nn.Module):
    def __init__(self, original_linear):
        super().__init__()
        self.weight = nn.Parameter(original_linear.weight.clone(), requires_grad=False)
        if original_linear.bias is not None:
            self.bias = nn.Parameter(original_linear.bias.clone(), requires_grad=False)
        else:
            self.register_parameter('bias', None)
        self.mod_memory = None 

    def forward(self, x):
        h = torch.matmul(x, self.weight.T)
        if self.bias is not None:
            h = h + self.bias
        if self.mod_memory is not None:
            h = h + self.mod_memory
        return h

def inject_surgery(m):
    for name, module in m.named_modules():
        if isinstance(module, nn.Linear) and "mlp" in name:
            parent_name = name.rsplit('.', 1)[0]
            child_name = name.rsplit('.', 1)[1]
            parent = m.get_submodule(parent_name)
            setattr(parent, child_name, GenerativeLinear(module))

inject_surgery(worker_model)
worker_model.to(device)
worker_model.eval()

worker_target_layer = worker_model.model.layers[12].mlp.down_proj

# ---------------------------------------------------------
# Swarm Execution Pipeline
# ---------------------------------------------------------
swift_files = {
    "User.swift": "struct User {\n    let id: String\n    let name: String\n    let role: String\n    func isAdmin() -> Bool {\n        return role == \"admin\"\n    }\n}",
    "main.swift": "func checkAccess(user: User) {\n    if user.isAdmin() {\n        print(\"Access Granted\")\n    } else {\n        print(\"Access Denied\")\n    }\n}"
}

print("\n--- 🧠 Commander Phase: Task Decomposition ---")
prompt = """You are an AI Commander. The user wants to convert a Swift project to Rust.
Here are the files:
1. User.swift
2. main.swift

Task: We need to translate 'main.swift'. It depends on 'User.swift'.
Output a JSON array of tasks. Each task must have:
- "action": "translate"
- "target_file": The file to translate
- "context_deps": Array of files it depends on

Do not output any text other than the JSON array."""

messages = [{"role": "user", "content": prompt}]
text = commander_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = commander_tokenizer(text, return_tensors="pt").to(commander_model.device)

print("Commander thinking...")
start = time.time()
with torch.no_grad():
    outputs = commander_model.generate(inputs["input_ids"], max_new_tokens=150, temperature=0.1)
latency = time.time() - start
commander_response = commander_tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
print(f"Commander JSON AST ({latency:.2f}s):")
print(commander_response)

print("\n--- 🏗️ Architect Phase: Extracting Cartridge ---")
try:
    # Basic parsing of JSON
    json_str = commander_response.replace("```json", "").replace("```", "").strip()
    ast = json.loads(json_str)
    task = ast[0]
    dep_file = task["context_deps"][0]
    dep_code = swift_files[dep_file]
    print(f"Architect reading dependency: {dep_file}...")
    
    # Extract latent vector using the worker itself
    inputs = worker_tokenizer(f"CONTEXT RUST CODE DEFINITION:\n{dep_code}", return_tensors="pt").to(device)
    captured_memory = None
    def capture_hook(module, input, output):
        global captured_memory
        captured_memory = output.mean(dim=1, keepdim=True).clone().detach()
        
    hook = worker_target_layer.register_forward_hook(capture_hook)
    with torch.no_grad():
        worker_model(inputs["input_ids"])
    hook.remove()
    
    # We now have the Cartridge!
    cartridge = captured_memory
    print(f"Cartridge extracted! Shape: {cartridge.shape}")
except Exception as e:
    print("Failed to parse Commander output:", e)
    cartridge = None

print("\n--- ⚡ Worker Phase: Translating with Cartridge Injection ---")
if cartridge is not None:
    # 1. Insert Cartridge
    worker_target_layer.mod_memory = cartridge * 2.0
    
    target_file = task["target_file"]
    target_code = swift_files[target_file]
    
    # Prompt the worker (NO context code included in prompt!)
    worker_prompt = f"Translate the following Swift code to Rust.\n\nSwift:\n{target_code}\n\nRust:\n"
    messages = [{"role": "user", "content": worker_prompt}]
    text = worker_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = worker_tokenizer(text, return_tensors="pt").to(device)
    
    print(f"Worker translating {target_file} (Prompt Context: {inputs['input_ids'].shape[1]} tokens)...")
    start = time.time()
    with torch.no_grad():
        outputs = worker_model.generate(inputs["input_ids"], max_new_tokens=200, temperature=0.7)
    latency = time.time() - start
    response = worker_tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    
    print(f"\n[Rust Output by 0.5B Worker ({latency:.2f}s)]\n")
    print(response)
    print("\n✅ Swarm execution complete!")
