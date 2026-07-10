import os
import time
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

from bucket_relay_swarm import JCrossBrain

def load_dataset_from_jsonl(filepath, tokenizer, max_length=256):
    import json
    dataset = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                text = data.get("text", "")
                tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length).input_ids[0]
                if len(tokens) > 10:
                    dataset.append(tokens)
            except:
                pass
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
            
    # Enable JCross V2 Training on Spatial Modulators + C_valve (float32 natively)
    brain.enable_training_v2()
    
    # Gather trainable parameters
    trainable_params = []
    for layer in brain.layers:
        trainable_params.extend([layer["S"], layer["mx"], layer["my"], layer["C_valve"]])
        
    print(f"Total trainable tensors (V2): {len(trainable_params)}")
    optimizer = torch.optim.AdamW(trainable_params, lr=1e-5, weight_decay=0.01)
    
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
    dataset_path = os.path.join(script_dir, "arkit_clean.jsonl")
    if not os.path.exists(dataset_path):
        print(f"File not found: {dataset_path}")
        return
        
    dataset = load_dataset_from_jsonl(dataset_path, tokenizer, max_length=256)
    print(f"Chunked dataset into {len(dataset)} training examples.")
    
    EPOCHS = 1
    
    for epoch in range(EPOCHS):
        total_loss = 0
        valid_batches = 0
        for idx, tokens in enumerate(dataset):
            optimizer.zero_grad()
            
            # Input and Target
            input_ids = tokens[:-1].to(device)
            target_ids = tokens[1:].to(device)
            
            # Embed
            x = brain.embed_weight[input_ids].unsqueeze(0).to(torch.float16)
            
            # Forward Latent
            x, _ = brain.forward_latent(x, role_name="HealerV2", mute_leakage=True)
            
            # Final Norm
            last_hidden = x[0] # (seq_len, dim)
            if getattr(brain, 'final_norm_weight', None) is not None:
                variance = last_hidden.pow(2).mean(-1, keepdim=True)
                last_hidden = (last_hidden * torch.rsqrt(variance + 1e-6)).to(torch.float16)
                last_hidden = (last_hidden * brain.final_norm_weight).to(torch.float16)
                
            # LM Head
            logits = torch.matmul(last_hidden.to(torch.float32), brain.lm_head_weight.to(torch.float32).T) # (seq_len, vocab_size)
            
            # Aggressive NaN prevention
            logits = torch.nan_to_num(logits, nan=0.0, posinf=10000.0, neginf=-10000.0)
            
            # Loss
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), target_ids.view(-1))
            
            if torch.isnan(loss) or torch.isinf(loss):
                print(f"Batch {idx+1}: NaN loss detected! Skipping.")
                continue
                
            loss.backward()
            
            # Aggressive gradient clipping
            torch.nn.utils.clip_grad_norm_(trainable_params, 0.5)
            
            # Check for NaN gradients before step
            has_nan_grad = False
            for p in trainable_params:
                if p.grad is not None and torch.isnan(p.grad).any():
                    has_nan_grad = True
                    break
                    
            if has_nan_grad:
                print(f"Batch {idx+1}: NaN gradients detected! Skipping step.")
                continue
            
            optimizer.step()
            
            total_loss += loss.item()
            valid_batches += 1
            if (idx + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{EPOCHS} | Batch {idx+1}/{len(dataset)} | Loss: {loss.item():.4f}")
            
        avg_loss = total_loss / valid_batches if valid_batches > 0 else float('nan')
        print(f"--- Epoch {epoch+1} Avg Loss: {avg_loss:.4f} ---")
        
    # Save Modulators
    save_path = os.path.join(workspace_dir, "cli", "swift_arkit_modulators_v2_3d.pt")
    state_dict = {}
    for i, layer in enumerate(brain.layers):
        state_dict[f"layer_{i}_S"] = layer["S"].detach().cpu().to(torch.float16)
        state_dict[f"layer_{i}_mx"] = layer["mx"].detach().cpu().to(torch.float16)
        state_dict[f"layer_{i}_my"] = layer["my"].detach().cpu().to(torch.float16)
        state_dict[f"layer_{i}_C_valve"] = layer["C_valve"].detach().cpu().to(torch.float16)
        
    torch.save(state_dict, save_path)
    print(f"\n[Success] Saved Swift/ARKit JCross V2 3D Modulators to {save_path}")

if __name__ == "__main__":
    main()
