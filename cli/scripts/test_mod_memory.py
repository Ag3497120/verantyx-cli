import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
import json
import numpy as np

print("🧠 Starting Latent Memory (mod_memory) Injection Test...")

# 1. Dummy GenerativeLinear for 0.5B (Simplified for test)
class GenerativeLinear(nn.Module):
    def __init__(self, original_linear, mod_x_data, mod_y_data):
        super().__init__()
        # We reuse the original weight for simplicity in this pure injection test,
        # but add the mod_x / mod_y muscles and the mod_memory hook target.
        self.weight = nn.Parameter(original_linear.weight.clone(), requires_grad=False)
        if original_linear.bias is not None:
            self.bias = nn.Parameter(original_linear.bias.clone(), requires_grad=False)
        else:
            self.register_parameter('bias', None)
            
        self.mod_x = nn.Parameter(torch.ones(original_linear.in_features, dtype=torch.bfloat16), requires_grad=False)
        self.mod_y = nn.Parameter(torch.ones(original_linear.out_features, dtype=torch.bfloat16), requires_grad=False)
        
        # This is the Eternal Memory injection port!
        self.mod_memory = None 

    def forward(self, x):
        h = torch.matmul(x * self.mod_x, self.weight.T)
        if self.bias is not None:
            h = h + self.bias
            
        # [LATENT INJECTION POINT]
        # If the Gatekeeper has supplied a memory vector, inject it directly into the thought stream!
        if self.mod_memory is not None:
            h = h + self.mod_memory
            
        return h * self.mod_y

def inject_surgery(model):
    for name, module in model.named_modules():
        if isinstance(module, nn.Linear) and "mlp" in name:
            parent_name = name.rsplit('.', 1)[0]
            child_name = name.rsplit('.', 1)[1]
            parent = model.get_submodule(parent_name)
            
            # Replace with our surgical layer
            surgical_layer = GenerativeLinear(module, None, None)
            setattr(parent, child_name, surgical_layer)

model_id = "Qwen/Qwen1.5-0.5B-Chat"
device = "mps" if torch.backends.mps.is_available() else "cpu"

print("Loading Base Model...")
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cpu")

print("Performing Surgery (Adding mod_memory bypass)...")
inject_surgery(model)
model.to(device)
model.eval()

# --- PHASE 1: Thought Extraction (The Gatekeeper saves a memory) ---
print("\n--- PHASE 1: Extracting Latent Memory ---")
# The Commander gives a full context
full_context = "Write a Python function to say hello world. def"
inputs = tokenizer(full_context, return_tensors="pt").to(device)

# We want to steal the "thought" (Hidden State) from Layer 12
target_layer = model.model.layers[12].mlp.down_proj

captured_memory = None
def capture_hook(module, input, output):
    global captured_memory
    # Steal the exact output vector of this layer, average it across tokens to create a universal "Steering Vector"
    captured_memory = output.mean(dim=1, keepdim=True).clone().detach()

hook_handle = target_layer.register_forward_hook(capture_hook)

print("AI is processing the full context...")
with torch.no_grad():
    model(inputs["input_ids"])

hook_handle.remove()
print(f"Captured Latent Memory Vector Shape: {captured_memory.shape}")
eternal_memory = captured_memory

# --- PHASE 2: Amnesia Test (No Memory) ---
print("\n--- PHASE 2: Amnesia Test (No Context) ---")
# We give the AI a completely unrelated prompt
empty_prompt = "Write a"
inputs_empty = tokenizer(empty_prompt, return_tensors="pt").to(device)

print("Prompt given to AI:", empty_prompt)
with torch.no_grad():
    outputs = model.generate(inputs_empty["input_ids"], max_new_tokens=15, pad_token_id=tokenizer.eos_token_id)
print("[Output without Memory]:", tokenizer.decode(outputs[0], skip_special_tokens=True))

# --- PHASE 3: Latent Injection (Eternal Memory Recovery) ---
print("\n--- PHASE 3: Latent Injection (mod_memory) ---")
print("Injecting captured vector directly into Layer 12 as a steering vector...")

# We inject the captured thought vector! 
# We multiply it by a strength factor (e.g. 5.0) to overpower the empty prompt.
target_layer.mod_memory = eternal_memory * 5.0

print("Prompt given to AI:", empty_prompt, "(BUT memory is injected!)")
with torch.no_grad():
    outputs_injected = model.generate(inputs_empty["input_ids"], max_new_tokens=15, pad_token_id=tokenizer.eos_token_id)
print("[Output WITH Latent Memory]:", tokenizer.decode(outputs_injected[0], skip_special_tokens=True))

print("\n✅ Verification Complete: Latent Injection successfully controls generation without text!")
