import torch
from transformers import AutoModelForCausalLM
print("Loading model...")
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct", torch_dtype=torch.float16).to("mps")
print("Model loaded successfully!")
