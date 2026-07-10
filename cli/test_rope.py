import torch
import json
from transformers import AutoTokenizer, AutoConfig

config = AutoConfig.from_pretrained("Qwen/Qwen3.6-27B", trust_remote_code=True)
print("Config rotary_dim:", getattr(config, "rotary_dim", None))
print("Config head_dim:", config.head_dim)
print("Config partial_rotary_factor:", config.partial_rotary_factor)

# Try loading the modeling file to see what dim it uses
import os
import sys
sys.path.append(os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"))
try:
    from modeling_qwen3_5 import Qwen3_5RotaryEmbedding
    emb = Qwen3_5RotaryEmbedding(config=config)
    print("Rotary embedding inv_freq shape:", emb.inv_freq.shape)
except Exception as e:
    print(e)
