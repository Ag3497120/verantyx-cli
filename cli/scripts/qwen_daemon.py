import os
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from flask import Flask, request, jsonify, Response
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64

app = Flask(__name__)

# --- Latent Memory Implementation (from verantyx_eval) ---
class LatentMemoryBank:
    def __init__(self, dim, max_size=2000000):
        self.dim = dim
        self.max_size = max_size
        
        # O(1) Dynamic Array Pre-allocation
        self.capacity = 10000
        self.current_size = 0
        self.memory = torch.empty((self.capacity, dim), dtype=torch.float32, device="mps")
        self.memory_norm = torch.empty((self.capacity, dim), dtype=torch.float32, device="mps")
        
    def reset(self):
        self.current_size = 0
        
    def write(self, states):
        if states.dim() > 2:
            states = states.view(-1, self.dim)
        
        states = states.detach().float()
        states_norm = F.normalize(states, p=2, dim=1)
        
        n = states.size(0)
        
        while self.current_size + n > self.capacity:
            self.capacity = min(self.capacity * 2, self.max_size)
            if self.current_size + n > self.max_size:
                break
            
            new_memory = torch.empty((self.capacity, self.dim), dtype=torch.float32, device="mps")
            new_memory_norm = torch.empty((self.capacity, self.dim), dtype=torch.float32, device="mps")
            
            new_memory[:self.current_size] = self.memory[:self.current_size]
            new_memory_norm[:self.current_size] = self.memory_norm[:self.current_size]
            
            self.memory = new_memory
            self.memory_norm = new_memory_norm
            
        end_idx = min(self.current_size + n, self.max_size)
        actual_n = end_idx - self.current_size
        
        if actual_n > 0:
            self.memory[self.current_size : end_idx] = states[:actual_n]
            self.memory_norm[self.current_size : end_idx] = states_norm[:actual_n]
            self.current_size = end_idx
            
    def read(self, query, top_k=2):
        if self.current_size == 0:
            return torch.zeros_like(query)
            
        batch, seq_len, dim = query.size()
        
        q_flat = query.view(-1, dim).float()
        q_norm = F.normalize(q_flat, p=2, dim=1)
        
        num_memory = self.current_size
        chunk_size = 250000 
        
        all_top_scores = []
        all_top_indices = []
        
        for i in range(0, num_memory, chunk_size):
            end_idx = min(i + chunk_size, num_memory)
            m_chunk_norm = self.memory_norm[i:end_idx]
            sim_chunk = torch.matmul(q_norm, m_chunk_norm.T)
            
            k_chunk = min(top_k, sim_chunk.size(1))
            scores, local_indices = torch.topk(sim_chunk, k_chunk, dim=1)
            
            global_indices = local_indices + i
            all_top_scores.append(scores)
            all_top_indices.append(global_indices)
            
            del sim_chunk
            
        cat_scores = torch.cat(all_top_scores, dim=1)
        cat_indices = torch.cat(all_top_indices, dim=1)
        
        k_final = min(top_k, cat_scores.size(1))
        final_scores, best_local = torch.topk(cat_scores, k_final, dim=1)
        
        final_indices = torch.gather(cat_indices, 1, best_local)
        
        if torch.isnan(final_scores).any():
            final_scores = torch.nan_to_num(final_scores, nan=0.0)
            
        retrieved = self.memory[final_indices].float()
        weights = F.softmax(final_scores, dim=1).unsqueeze(-1)
        
        blended = torch.sum(retrieved * weights, dim=1)
        return blended.view(batch, seq_len, dim).to(query.device)


MEMORY_BANK = LatentMemoryBank(dim=1024)
MODEL = None
TOKENIZER = None
MODULATORS = []
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"

IS_INGESTING = False

import itertools
hook_counter = itertools.count()

def create_memory_pre_hook(mod_memory):
    def hook(module, args):
        if IS_INGESTING:
            return args
        x = args[0]
        # Optimize: Only apply latent memory to the final token (the one driving generation)
        # to avoid O(seq_len * memory_size) explosion during the pre-fill phase.
        x_last = x[:, -1:, :]
        x_retrieved = MEMORY_BANK.read(x_last)
        
        x_new = x.clone()
        x_new[:, -1:, :] = x[:, -1:, :] + (x_retrieved * mod_memory)
        
        return (x_new,) + args[1:]
    return hook

def load_system():
    global MODEL, TOKENIZER, MODULATORS
    if MODEL is not None:
        return
    print(f"[*] Loading Base Model on {DEVICE}...")
    TOKENIZER = AutoTokenizer.from_pretrained("Qwen/Qwen1.5-0.5B-Chat")
    MODEL = AutoModelForCausalLM.from_pretrained("Qwen/Qwen1.5-0.5B-Chat", torch_dtype=torch.float32)
    
    print("[*] Injecting Infinite Latent Memory Hooks...")
    for layer in MODEL.model.layers:
        mod_m = nn.Parameter(torch.full((1024,), 0.001).to(DEVICE))
        MODULATORS.append(mod_m)
        layer.register_forward_pre_hook(create_memory_pre_hook(mod_m))
        
    MODEL.to(DEVICE)
    MODEL.eval()
    print("[*] System Ready!")


@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok", "memory_size": MEMORY_BANK.current_size})

@app.route('/reset', methods=['POST'])
def reset_memory():
    MEMORY_BANK.reset()
    return jsonify({"status": "ok", "message": "Latent memory reset."})

@app.route('/ingest', methods=['POST'])
def ingest():
    data = request.json
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"status": "ok", "ingested_tokens": 0})
        
    inputs = TOKENIZER(text, return_tensors="pt").to(DEVICE)
    total_tokens = inputs.input_ids.shape[1]
    
    global IS_INGESTING
    IS_INGESTING = True
    
    chunk_size = 512
    try:
        with torch.no_grad():
            for i in range(0, total_tokens, chunk_size):
                sub_chunk = inputs.input_ids[:, i:i+chunk_size]
                outputs = MODEL(sub_chunk, output_hidden_states=True)
                final_states = outputs.hidden_states[-1]
                MEMORY_BANK.write(final_states)
                
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
    finally:
        IS_INGESTING = False
                
    return jsonify({"status": "ok", "ingested_tokens": total_tokens, "memory_size": MEMORY_BANK.current_size})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get("messages", [])
    
    # Format messages
    prompt = TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = TOKENIZER(prompt, return_tensors="pt").to(DEVICE)
    
    prompt_tokens = inputs.input_ids.shape[1]
    
    with torch.no_grad():
        output_ids = MODEL.generate(**inputs, max_new_tokens=1500, output_hidden_states=False, pad_token_id=TOKENIZER.pad_token_id)
        
    response_text = TOKENIZER.decode(output_ids[0][prompt_tokens:], skip_special_tokens=True).strip()
    
    del inputs
    del output_ids
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
        
    return jsonify({"response": response_text})

@app.route('/anchor', methods=['POST'])
def generate_anchor():
    data = request.json
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    # Generate a bright red image with white text
    width, height = 1024, 768
    img = Image.new('RGB', (width, height), color='red')
    d = ImageDraw.Draw(img)
    
    try:
        # Better readable font
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except:
        font = ImageFont.load_default()
        
    y_text = 50
    for line in text.split('\n'):
        d.text((50, y_text), line, fill=(255,255,255), font=font)
        y_text += 60
        
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return jsonify({"image_base64": img_str})

if __name__ == "__main__":
    load_system()
    app.run(host="127.0.0.1", port=5055)
