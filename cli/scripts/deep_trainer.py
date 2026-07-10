import os
import argparse
import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from torch.utils.data import DataLoader, Dataset
import math
import time

class GenerativeLinear(nn.Module):
    """
    Replaces nn.Linear with our Rank-constrained Spatial Generative parameters.
    """
    def __init__(self, original_linear, rank=128):
        super().__init__()
        self.rank = rank
        self.in_features = original_linear.in_features
        self.out_features = original_linear.out_features
        
        W = original_linear.weight.data.float()
        
        # Initialize using SVD
        U, S, Vh = torch.linalg.svd(W, full_matrices=False)
        self.U = nn.Parameter(U[:, :rank].clone())
        self.S = nn.Parameter(S[:rank].clone())
        self.V = nn.Parameter(Vh[:rank, :].T.clone())
        
        # Spatial Modulators
        self.mod_x = nn.Parameter(torch.ones(self.in_features))
        self.mod_y = nn.Parameter(torch.ones(self.out_features))
        
        if original_linear.bias is not None:
            self.bias = nn.Parameter(original_linear.bias.data.float().clone())
        else:
            self.register_parameter('bias', None)
            
    def forward(self, x):
        # x is shape (batch, seq_len, in_features)
        # Efficient low-rank generation:
        # h = (x * mod_x) @ V
        # y = (h * S) @ U.T
        # y = y * mod_y
        
        h = torch.matmul(x * self.mod_x, self.V)
        y = torch.matmul(h * self.S, self.U.T)
        y = y * self.mod_y
        
        if self.bias is not None:
            y += self.bias
            
        return y

class SimpleTextDataset(Dataset):
    def __init__(self, text, tokenizer, seq_len=128):
        # Tokenize the text
        tokens = tokenizer.encode(text)
        self.samples = []
        for i in range(0, len(tokens) - seq_len, seq_len):
            chunk = tokens[i:i + seq_len + 1] # +1 for target
            self.samples.append(chunk)
            
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        chunk = self.samples[idx]
        x = torch.tensor(chunk[:-1], dtype=torch.long)
        y = torch.tensor(chunk[1:], dtype=torch.long)
        return x, y

def replace_layers(model, rank):
    replaced = 0
    for z in range(model.config.num_hidden_layers):
        layer = model.model.layers[z]
        
        # Self Attention
        layer.self_attn.q_proj = GenerativeLinear(layer.self_attn.q_proj, rank)
        layer.self_attn.k_proj = GenerativeLinear(layer.self_attn.k_proj, rank)
        layer.self_attn.v_proj = GenerativeLinear(layer.self_attn.v_proj, rank)
        layer.self_attn.o_proj = GenerativeLinear(layer.self_attn.o_proj, rank)
        
        # MLP
        layer.mlp.gate_proj = GenerativeLinear(layer.mlp.gate_proj, rank)
        layer.mlp.up_proj = GenerativeLinear(layer.mlp.up_proj, rank)
        layer.mlp.down_proj = GenerativeLinear(layer.mlp.down_proj, rank)
        
        replaced += 7
    print(f"Replaced {replaced} linear layers with GenerativeLinear (Rank {rank}).")

def get_tiny_dataset():
    # A small dummy text corpus to verify the training loop functions and loss drops.
    # In a real scenario, we would stream Wikitext or FineWeb.
    text = (
        "The capital of France is Paris. The Eiffel Tower is located in Paris. "
        "The capital of Japan is Tokyo. Mount Fuji is in Japan. "
        "Verantyx is a powerful compiler for large language models. "
        "Water boils at 100 degrees Celsius and freezes at 0 degrees. "
        "Python is a popular programming language for artificial intelligence. "
    ) * 100 # Repeat to make a sizable dataset
    return text

import struct

def export_jgen(model, rank, output_path):
    print(f"Exporting Trained Generative Weights to {output_path}")
    num_layers = model.config.num_hidden_layers
    
    # Same mapping as generative_compiler.py
    # Note: We must fetch the actual GenerativeLinear instances from the monkey-patched model
    
    with open(output_path, "wb") as f:
        f.write(b"JGEN")
        f.write(struct.pack("<I", 1))
        f.write(struct.pack("<I I", num_layers, rank))
        
        state_dict = model.state_dict()
        
        embed_weight = state_dict["model.embed_tokens.weight"].cpu()
        f.write(struct.pack("<B I I", 0, embed_weight.shape[0], embed_weight.shape[1]))
        f.write(embed_weight.numpy().astype("float16").tobytes())
        
        lm_head = state_dict["lm_head.weight"].cpu()
        f.write(struct.pack("<B I I", 1, lm_head.shape[0], lm_head.shape[1]))
        f.write(lm_head.numpy().astype("float16").tobytes())
        
        norm_weight = state_dict["model.norm.weight"].cpu()
        f.write(struct.pack("<B I I", 2, norm_weight.shape[0], 1))
        f.write(norm_weight.numpy().astype("float16").tobytes())
        
        for z in range(num_layers):
            layer = model.model.layers[z]
            
            attn_norm = state_dict[f"model.layers.{z}.input_layernorm.weight"].cpu()
            f.write(struct.pack("<B B I I", 3, z, attn_norm.shape[0], 1))
            f.write(attn_norm.numpy().astype("float16").tobytes())
            
            mlp_norm = state_dict[f"model.layers.{z}.post_attention_layernorm.weight"].cpu()
            f.write(struct.pack("<B B I I", 4, z, mlp_norm.shape[0], 1))
            f.write(mlp_norm.numpy().astype("float16").tobytes())
            
            matrices = [
                (7, layer.self_attn.q_proj),
                (8, layer.self_attn.k_proj),
                (9, layer.self_attn.v_proj),
                (20, layer.self_attn.o_proj),
                (10, layer.mlp.gate_proj),
                (11, layer.mlp.up_proj),
                (12, layer.mlp.down_proj)
            ]
            
            for mtype, gen_linear in matrices:
                U = gen_linear.U.detach().cpu().numpy().astype("float16")
                S = gen_linear.S.detach().cpu().numpy().astype("float16")
                V = gen_linear.V.detach().cpu().numpy().astype("float16")
                mod_x = gen_linear.mod_x.detach().cpu().numpy().astype("float16")
                mod_y = gen_linear.mod_y.detach().cpu().numpy().astype("float16")
                
                rows, cols = gen_linear.out_features, gen_linear.in_features
                f.write(struct.pack("<B B B I I I", 5, z, mtype, rows, cols, rank))
                
                f.write(U.tobytes())
                f.write(S.tobytes())
                f.write(V.tobytes())
                f.write(mod_x.tobytes())
                f.write(mod_y.tobytes())
                
    print("Export Complete.")

def train():
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
        
    print(f"Using device: {device}")
    
    print("Loading base model...")
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen1.5-0.5B-Chat", torch_dtype=torch.float32)
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen1.5-0.5B-Chat")
    
    rank = 128
    print(f"Patching model with Generative Weights (Rank {rank})...")
    replace_layers(model, rank)
    
    trainable_params = 0
    for name, param in model.named_parameters():
        if "U" in name or "V" in name or "S" in name or "mod_x" in name or "mod_y" in name or "bias" in name:
            param.requires_grad = True
            trainable_params += param.numel()
        else:
            param.requires_grad = False
            
    print(f"Trainable parameters: {trainable_params / 1e6:.2f} M")
    
    model.gradient_checkpointing_enable()
    model = model.to(device)
    
    text = get_tiny_dataset()
    dataset = SimpleTextDataset(text, tokenizer, seq_len=64)
    loader = DataLoader(dataset, batch_size=2, shuffle=True)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    loss_fn = nn.CrossEntropyLoss()
    
    print("Starting Deep Re-Training...")
    epochs = 3
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        start_time = time.time()
        
        for batch_idx, (x, y) in enumerate(loader):
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            outputs = model(x)
            logits = outputs.logits
            loss = loss_fn(logits.view(-1, logits.size(-1)), y.view(-1))
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
            if (batch_idx + 1) % 10 == 0:
                print(f"  Epoch {epoch+1} | Batch {batch_idx+1}/{len(loader)} | Loss: {loss.item():.4f}")
                
        avg_loss = total_loss / len(loader)
        epoch_time = time.time() - start_time
        print(f"Epoch {epoch+1} completed | Avg Loss: {avg_loss:.4f} | Time: {epoch_time:.2f}s")
        
        model.eval()
        with torch.no_grad():
            prompt = "The capital of France is"
            inputs = tokenizer(prompt, return_tensors="pt").to(device)
            output_ids = model.generate(**inputs, max_new_tokens=10)
            text_out = tokenizer.decode(output_ids[0], skip_special_tokens=True)
            print(f"  Generation Test: {text_out}")
            
    print("Training finished. We have successfully re-balanced the residual streams!")
    export_jgen(model, rank, "qwen_0.5b_trained.jgen")

if __name__ == "__main__":
    train()
