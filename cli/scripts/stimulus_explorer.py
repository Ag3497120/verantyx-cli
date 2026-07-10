import os
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForCausalLM
from tqdm import tqdm
import struct
import gc

# ---------------------------------------------------------
# Optimal Stimulus Explorer (Phase 11)
# ---------------------------------------------------------
# Finds the prompt that maximally and evenly stimulates the 
# JCross spatial lattice to prevent overfitting during healing.
# ---------------------------------------------------------

MODEL_ID = "google/gemma-4-12B"
JGEN_FILE = "cli/gemma_12b_generative.jgen"
RANK = 1024
DIM = 3840 # Gemma-4-12B hidden_size

def load_generative_layer(filepath, layer_index, rank=RANK, dim=DIM):
    """Loads a single generative layer from the .jgen file."""
    layer = {}
    bytes_per_layer = (
        (dim * rank * 2) +    # U
        (rank * 2) +          # S
        (dim * rank * 2) +    # V
        (dim * 2) +           # mx
        (dim * 2)             # my
    )
    
    offset = layer_index * bytes_per_layer
    
    try:
        with open(filepath, "rb") as f:
            f.seek(offset)
            
            U = torch.frombuffer(f.read(dim * rank * 2), dtype=torch.float16).reshape(dim, rank).clone()
            S = torch.frombuffer(f.read(rank * 2), dtype=torch.float16).clone()
            V = torch.frombuffer(f.read(dim * rank * 2), dtype=torch.float16).reshape(dim, rank).clone()
            mx = torch.frombuffer(f.read(dim * 2), dtype=torch.float16).clone()
            my = torch.frombuffer(f.read(dim * 2), dtype=torch.float16).clone()
            
            layer["U"] = U.cuda() if torch.cuda.is_available() else U.to('mps') if torch.backends.mps.is_available() else U
            layer["S"] = S.cuda() if torch.cuda.is_available() else S.to('mps') if torch.backends.mps.is_available() else S
            layer["V"] = V.cuda() if torch.cuda.is_available() else V.to('mps') if torch.backends.mps.is_available() else V
            layer["mx"] = mx.cuda() if torch.cuda.is_available() else mx.to('mps') if torch.backends.mps.is_available() else mx
            layer["my"] = my.cuda() if torch.cuda.is_available() else my.to('mps') if torch.backends.mps.is_available() else my
            
        return layer
    except Exception as e:
        print(f"Error loading layer {layer_index}: {e}")
        return None

def calculate_activation_entropy(input_embeds, layer):
    """Calculates how evenly and strongly the JCross dimensions are stimulated."""
    # Cast to float32 to prevent overflow in variance calculation
    h = input_embeds.to(torch.float32)
    
    # Simplified RMSNorm
    variance = h.pow(2).mean(-1, keepdim=True)
    normed_h = h * torch.rsqrt(variance + 1e-6)
    
    # Project to JCross Space
    z = torch.matmul(normed_h * layer["mx"].to(torch.float32), layer["V"].to(torch.float32))
    z_scaled = z * layer["S"].to(torch.float32) # [batch, seq_len, rank]
    
    # Calculate energy across the sequence
    energy = torch.abs(z_scaled).mean(dim=1) # [batch, rank]
    
    # We want high mean energy, but LOW variance across dimensions (even stimulation)
    mean_energy = energy.mean(dim=-1)
    std_energy = energy.std(dim=-1)
    
    # Fitness score: High Energy + Low Entropy (Variance)
    score = mean_energy - (std_energy * 0.5)
    
    # Handle NaN/Inf by zeroing them out so they don't corrupt the entire batch sum
    score = torch.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    
    return score

def main():
    print(f"  [\033[36mExplorer\033[0m] Initializing Optimal Stimulus Explorer...")
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    
    print(f"  [\033[36mExplorer\033[0m] Loading Tokenizer and Embedding Space...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, local_files_only=True)
    
    # Need to load the embedding layer from the actual model to map tokens to vectors
    # Loading just the embeddings to save RAM
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, device_map="auto", torch_dtype=torch.float16, local_files_only=True)
    embed_layer = model.get_input_embeddings()
    
    print(f"  [\033[36mExplorer\033[0m] Loading Representative JCross Layers...")
    # We load the first 3 layers to measure stimulation propagation
    layers = []
    for i in range(3):
        l = load_generative_layer(JGEN_FILE, i)
        if l: layers.append(l)
    
    if not layers:
        print("Failed to load JCross layers. Ensure gemma_12b_generative.jgen is present.")
        return

    print(f"  [\033[36mExplorer\033[0m] Starting Forward Search (Genetic/Random Sampling)...")
    
    vocab_size = tokenizer.vocab_size
    best_score = -1e9
    best_tokens = None
    
    BATCH_SIZE = 32
    SEQ_LEN = 16
    ITERATIONS = 500
    
    for i in tqdm(range(ITERATIONS), desc="Exploring Lattice Stimulation"):
        # Generate random sequences of tokens
        random_ids = torch.randint(0, vocab_size, (BATCH_SIZE, SEQ_LEN)).to(device)
        
        # Fallback initialization
        if best_tokens is None:
            best_tokens = random_ids[0].cpu().tolist()
            
        with torch.no_grad():
            # Convert to embeddings
            embeds = embed_layer(random_ids)
            
            # Pass through layers and sum scores
            total_score = torch.zeros(BATCH_SIZE).to(device)
            current_h = embeds
            
            for layer in layers:
                score = calculate_activation_entropy(current_h, layer)
                total_score += score
                
                # Approximate forward pass for next layer propagation
                h_float = current_h.to(torch.float32)
                variance = h_float.pow(2).mean(-1, keepdim=True)
                normed_h = h_float * torch.rsqrt(variance + 1e-6)
                z = torch.matmul(normed_h * layer["mx"].to(torch.float32), layer["V"].to(torch.float32))
                z_scaled = z * layer["S"].to(torch.float32)
                z_out = z_scaled + torch.nn.functional.silu(z_scaled) # Simplified
                temp = torch.matmul(z_out, layer["U"].T.to(torch.float32))
                next_h = h_float + (temp + layer["my"].to(torch.float32))
                current_h = torch.nan_to_num(next_h, nan=0.0, posinf=10.0, neginf=-10.0).to(torch.float16)
            
            # Find the best sequence in this batch
            batch_best_idx = torch.argmax(total_score)
            batch_best_score = total_score[batch_best_idx].item()
            
            if batch_best_score > best_score:
                best_score = batch_best_score
                best_tokens = random_ids[batch_best_idx].cpu().tolist()
                
    print("\n  [\033[32mSuccess\033[0m] Optimal Stimulus Prompt Found!")
    print(f"  Score: {best_score:.4f}")
    
    optimal_text = tokenizer.decode(best_tokens)
    print(f"  Tokens: {best_tokens}")
    print(f"  Text equivalent: {optimal_text}")
    
    # Save the optimal prompt
    with open("optimal_stimulus.txt", "w") as f:
        f.write(optimal_text)
    print(f"  [\033[36mExplorer\033[0m] Saved optimal stimulus to optimal_stimulus.txt")
    
    # Cleanup
    del model
    gc.collect()
    torch.mps.empty_cache() if torch.backends.mps.is_available() else torch.cuda.empty_cache()

if __name__ == "__main__":
    main()
