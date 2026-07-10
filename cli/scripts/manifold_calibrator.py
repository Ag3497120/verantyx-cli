import os
import json
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModelForCausalLM
from bucket_relay_swarm import JCrossBrain

def load_dataset(filepath="healing_dataset.jsonl", max_samples=4):
    texts = []
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                data = json.loads(line.strip())
                if "text" in data:
                    texts.append(data["text"])
                if len(texts) >= max_samples:
                    break
    if not texts:
        texts = ["def main():\n    print('Hello World')\n"]
    return texts

def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Starting Manifold Calibration on {device}...")
    
    # 1. Load Hugging Face Gemma
    print("Loading Hugging Face Gemma 4 12B model...")
    model_path_hf = os.path.expanduser("~/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2")
    if not os.path.exists(model_path_hf):
        model_path_hf = "/Volumes/PREDATOR GM7000 4TB/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2"
    if not os.path.exists(model_path_hf):
        model_path_hf = "google/gemma-4-12b-it" # Assuming this is the remote ID if local is not found
    
    tokenizer = AutoTokenizer.from_pretrained(model_path_hf)
    hf_model = AutoModelForCausalLM.from_pretrained(model_path_hf, torch_dtype=torch.float16, local_files_only=True).to(device)
    hf_model.eval()
    
    # 2. Load JCrossBrain
    print("Loading JCrossBrain...")
    # Fix workspace_dir to point to verantyx-cli instead of verantyx-cli/cli
    workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    jgen_path = os.path.join(workspace_dir, "telepathic_coder_lossless.jgen")
    brain = JCrossBrain(jgen_path, device=device)
    
    texts = load_dataset()
    
    H_gemma_list = []
    H_jcross_list = []
    
    print("Collecting hidden states...")
    with torch.no_grad():
        for text in texts:
            inputs = tokenizer(text, return_tensors="pt").to(device)
            input_ids = inputs["input_ids"]
            
            # --- Gemma Pass ---
            outputs = hf_model(input_ids, output_hidden_states=True)
            # The hidden state just before the final layernorm & lm_head
            h_gemma = outputs.hidden_states[-1][0].to(torch.float32) # (seq_len, hidden_size)
            
            # --- JCross Pass ---
            embed_weight = hf_model.get_input_embeddings().weight
            input_embeds = torch.nn.functional.embedding(input_ids, embed_weight) * (embed_weight.shape[1] ** 0.5)
            
            h_jcross_seq = []
            past_states = None
            for i in range(input_ids.shape[1]):
                curr_emb = input_embeds[:, i:i+1, :]
                out_hidden, past_states = brain.forward_latent(curr_emb, past_states=past_states)
                h_jcross_seq.append(out_hidden[0].to(torch.float32))
            
            h_jcross = torch.cat(h_jcross_seq, dim=0) # (seq_len, hidden_size)
            
            H_gemma_list.append(h_gemma)
            H_jcross_list.append(h_jcross)
            print(f" Collected sequence of length {h_gemma.shape[0]}")
            
    # Free VRAM
    del hf_model
    import gc
    gc.collect()
    torch.mps.empty_cache() if device == "mps" else None

    print("Computing Manifold Alignment Matrix (Least Squares) on CPU...")
    H_gemma_all = torch.cat(H_gemma_list, dim=0).cpu().to(torch.float32)   # (N, 3840)
    H_jcross_all = torch.cat(H_jcross_list, dim=0).cpu().to(torch.float32) # (N, 3840)
    
    # We want to find M_align such that: H_jcross_all @ M_align \approx H_gemma_all
    # Using torch.linalg.lstsq (Move to CPU because MPS doesn't support it yet)
    res = torch.linalg.lstsq(H_jcross_all, H_gemma_all)
    M_align = res.solution.to(device) # (3840, 3840)
    
    # Compute error
    H_pred = torch.matmul(H_jcross_all.to(device), M_align)
    mse = torch.nn.functional.mse_loss(H_pred, H_gemma_all.to(device)).item()
    print(f"Alignment Error (MSE): {mse:.6f}")
    
    out_path = os.path.join(workspace_dir, "manifold_alignment.pt")
    torch.save(M_align.to(torch.float16), out_path)
    print(f"Manifold Alignment Matrix saved to: {out_path}")

if __name__ == "__main__":
    main()
