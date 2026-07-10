import torch
from transformers import AutoModelForCausalLM
import os
import gc

model_path = os.path.expanduser("~/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2")
if not os.path.exists(model_path):
    model_path = "/Volumes/PREDATOR GM7000 4TB/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2"
if not os.path.exists(model_path):
    model_path = "google/gemma-2-9b-it" # fallback

print(f"Extracting LM Head and Embeddings from {model_path}...")
try:
    # Use torch_dtype=torch.float16 and local_files_only=True
    model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16, local_files_only=True, low_cpu_mem_usage=True, device_map="cpu")
    
    lm_head = model.get_output_embeddings().weight.detach().clone()
    embed = model.get_input_embeddings().weight.detach().clone()
    
    torch.save(lm_head, "lm_head.pt")
    torch.save(embed, "embed.pt")
    print(f"Successfully saved lm_head.pt ({lm_head.shape}) and embed.pt ({embed.shape})")
    
    del model
    gc.collect()
except Exception as e:
    print(f"Failed to extract using HF: {e}")
