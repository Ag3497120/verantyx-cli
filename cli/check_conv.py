from transformers import AutoModelForCausalLM
import torch

model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-32B-Instruct", torch_dtype=torch.float16, device_map="auto")
# wait, I don't have the weights downloaded here!
