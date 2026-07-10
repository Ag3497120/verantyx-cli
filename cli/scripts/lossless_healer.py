import os
import json
import time
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

from bucket_relay_swarm import JCrossBrain

def load_dataset(filepath, tokenizer, max_length=256):
    dataset = []
    with open(filepath, 'r') as f:
        for line in f:
            if not line.strip(): continue
            data = json.loads(line)
            text = data["text"]
            # Encode
            tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length).input_ids[0]
            if len(tokens) > 2:
                dataset.append(tokens)
    return dataset

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(os.path.dirname(script_dir))
    
    jgen_path = os.path.join(workspace_dir, "telepathic_coder_lossless.jgen")
    if not os.path.exists(jgen_path):
        jgen_path = os.path.join(workspace_dir, "cli", "telepathic_coder_lossless.jgen")
        if not os.path.exists(jgen_path):
            jgen_path = os.path.join(workspace_dir, "gemma_12b_generative.jgen")
            if not os.path.exists(jgen_path):
                jgen_path = os.path.join(workspace_dir, "cli", "gemma_12b_generative.jgen")
        
    print(f"Loading native JCrossBrain from: {jgen_path}")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    brain = JCrossBrain(jgen_path, device=device)
    
    # Load missing Embeddings/LM Head
    if getattr(brain, 'embed_weight', None) is None:
        embed_path = os.path.join(workspace_dir, "embed.pt")
        if not os.path.exists(embed_path): embed_path = os.path.join(workspace_dir, "cli", "embed.pt")
        if os.path.exists(embed_path):
            brain.embed_weight = torch.load(embed_path, map_location=device).to(torch.float16)
            print("Loaded embed.pt")
            
    if getattr(brain, 'lm_head_weight', None) is None:
        lm_path = os.path.join(workspace_dir, "lm_head.pt")
        if not os.path.exists(lm_path): lm_path = os.path.join(workspace_dir, "cli", "lm_head.pt")
        if os.path.exists(lm_path):
            brain.lm_head_weight = torch.load(lm_path, map_location=device).to(torch.float16)
            print("Loaded lm_head.pt")
            
    if getattr(brain, 'final_norm_weight', None) is None:
        norm_path = os.path.join(workspace_dir, "final_norm.pt")
        if not os.path.exists(norm_path): norm_path = os.path.join(workspace_dir, "cli", "final_norm.pt")
        if os.path.exists(norm_path):
            brain.final_norm_weight = torch.load(norm_path, map_location=device).to(torch.float16)
            print("Loaded final_norm.pt")
            
    # Enable Training on Spatial Modulators
    brain.enable_training()
    
    # Gather trainable parameters
    trainable_params = []
    for layer in brain.layers:
        trainable_params.extend([layer["S"], layer["mx"], layer["my"]])
        
    print(f"Total trainable tensors: {len(trainable_params)}")
    optimizer = torch.optim.AdamW(trainable_params, lr=5e-5)
    
    # Load Tokenizer
    model_path = os.path.expanduser("~/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2")
    if not os.path.exists(model_path):
        model_path = "google/gemma-2-9b-it" # fallback
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path)
    except Exception:
        print("Using standard gemma-2-9b-it tokenizer")
        tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-9b-it")
        
    # Load dataset
    dataset_path = os.path.join(workspace_dir, "cli", "scripts", "python_healing.jsonl")
    dataset = load_dataset(dataset_path, tokenizer)
    print(f"Loaded {len(dataset)} training examples.")
    
    EPOCHS = 4
    
    for epoch in range(EPOCHS):
        total_loss = 0
        for idx, tokens in enumerate(dataset):
            optimizer.zero_grad()
            
            # Input and Target
            input_ids = tokens[:-1].to(device)
            target_ids = tokens[1:].to(device)
            
            # Embed
            x = brain.embed_weight[input_ids].unsqueeze(0).to(torch.float16)
            
            # Forward Latent
            x, _ = brain.forward_latent(x, role_name="Healer", mute_leakage=True)
            
            # Final Norm
            last_hidden = x[0] # (seq_len, dim)
            if getattr(brain, 'final_norm_weight', None) is not None:
                variance = last_hidden.pow(2).mean(-1, keepdim=True)
                last_hidden = (last_hidden * torch.rsqrt(variance + 1e-6)).to(torch.float16)
                last_hidden = (last_hidden * brain.final_norm_weight).to(torch.float16)
                
            # LM Head
            logits = torch.matmul(last_hidden, brain.lm_head_weight.to(torch.float16).T) # (seq_len, vocab_size)
            
            # Loss (convert to float32 just for PyTorch cross_entropy to avoid NaNs)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)).to(torch.float32), target_ids.view(-1))
            loss.backward()
            
            # Optional gradient clipping to prevent MPS float16 exploding gradients
            torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
            
            optimizer.step()
            
            total_loss += loss.item()
            print(f"Epoch {epoch+1}/{EPOCHS} | Batch {idx+1}/{len(dataset)} | Loss: {loss.item():.4f}")
            
        print(f"--- Epoch {epoch+1} Avg Loss: {total_loss/len(dataset):.4f} ---")
        
    # Save Modulators
    save_path = os.path.join(workspace_dir, "cli", "python_modulators.pt")
    state_dict = {}
    for i, layer in enumerate(brain.layers):
        state_dict[f"layer_{i}_S"] = layer["S"].detach().cpu().to(torch.float16)
        state_dict[f"layer_{i}_mx"] = layer["mx"].detach().cpu().to(torch.float16)
        state_dict[f"layer_{i}_my"] = layer["my"].detach().cpu().to(torch.float16)
        
    torch.save(state_dict, save_path)
    print(f"\n[Success] Saved Language-Specific Modulators (Switchable Brain) to {save_path}")
    print("You can now dynamically load this file in telepathic_coder.py to instantly recover Python syntax!")

if __name__ == "__main__":
    main()
