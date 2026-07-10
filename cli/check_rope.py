import torch
from transformers.models.qwen2.modeling_qwen2 import rotate_half
x = torch.arange(8).unsqueeze(0).unsqueeze(0).unsqueeze(0)
print(rotate_half(x))
