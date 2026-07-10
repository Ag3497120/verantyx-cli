import torch
import os
import sys
from safetensors import safe_open
from transformers import AutoTokenizer

C_CYAN = '\033[96m'
C_MAGENTA = '\033[95m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'

def load_qwen_embeddings(snapshot_dir):
    print(f"{C_CYAN}[Init] Loading Qwen 3.6 Tokenizer...{C_RESET}")
    tokenizer = AutoTokenizer.from_pretrained(snapshot_dir, trust_remote_code=True)
    
    st_file = os.path.join(snapshot_dir, "model-00001-of-00015.safetensors")
    print(f"{C_CYAN}[Init] Loading Real Embedding Matrix from {os.path.basename(st_file)}...{C_RESET}")
    with safe_open(st_file, framework="pt", device="cpu") as f:
        embed_weight = f.get_tensor("model.language_model.embed_tokens.weight").to(torch.float32)
        
    return tokenizer, embed_weight

def query_jcross_dictionary(word, layer_idx, tokenizer, embed_weight, dict_dir):
    print(f"\n{C_MAGENTA}======================================================{C_RESET}")
    print(f"{C_YELLOW} Querying JCross Dictionary (Layer {layer_idx}) for concept: '{word}'{C_RESET}")
    print(f"{C_MAGENTA}======================================================{C_RESET}")
    
    # 1. Get Token ID
    tokens = tokenizer.encode(word)
    if not tokens:
        print(f"{C_RED}Error: Word not in vocabulary.{C_RESET}")
        return
    token_id = tokens[0]
    print(f"Token ID for '{word}': {token_id}")
    
    # 2. Extract Embedding Vector (dim 5120)
    input_vector = embed_weight[token_id].unsqueeze(0) # Shape: (1, 5120)
    print(f"Input Vector Shape: {input_vector.shape}")
    
    # 3. Load JCross Dictionary for Layer X
    layer_file = os.path.join(dict_dir, f"real_layer_{layer_idx}_down_proj.pt")
    if not os.path.exists(layer_file):
        print(f"{C_RED}Error: {layer_file} not found.{C_RESET}")
        return
        
    jcross = torch.load(layer_file, map_location="cpu")
    mx = jcross['mx'].to(torch.float32)
    my = jcross['my'].to(torch.float32)
    C_valve = jcross['C_valve'].to(torch.float32)
    
    # 4. Stream through the dictionary
    latent_energy = input_vector @ mx
    valved_energy = latent_energy @ C_valve
    
    projected_energy = valved_energy @ my.T
    
    # Mathematical adaptation: Since down_proj maps from 17408 -> 5120, its weight is (5120, 17408).
    # mx is (5120, 128), my is (17408, 128).
    # The output is (1, 17408). To map it back to 5120 to compare with embeddings,
    # we can use the transposed matrix or just truncate for the PoC.
    # A better mathematical way for a semantic dictionary is to map it back using the pseudo-inverse or transpose of the layer.
    # For now, let's truncate to 5120.
    output_vector = projected_energy[:, :5120] 
    
    # 5. Measure Semantic Similarity (Cosine Similarity)
    print(f"{C_CYAN}>> Scanning embedding space for associated concepts...{C_RESET}")
    
    # Normalize vectors for cosine similarity
    output_norm = torch.nn.functional.normalize(output_vector, p=2, dim=1)
    embed_norm = torch.nn.functional.normalize(embed_weight, p=2, dim=1)
    
    # Calculate similarity with all vocabulary tokens
    similarities = torch.matmul(output_norm, embed_norm.T).squeeze()
    
    # Get top 10 closest tokens
    top_k = 10
    top_scores, top_indices = torch.topk(similarities, top_k)
    
    print(f"\n{C_GREEN}Top Semantic Associations from JCross Layer {layer_idx}:{C_RESET}")
    for i in range(top_k):
        score = top_scores[i].item()
        token_id = top_indices[i].item()
        associated_word = tokenizer.decode([token_id])
        # Format cleanly
        associated_word = repr(associated_word).strip("'")
        print(f"  {i+1}. {associated_word:20s} (Similarity: {score:.4f})")
        
def main():
    snapshot_dir = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
    dict_dir = os.path.join(os.path.dirname(__file__), "qwen_jcross_dicts")
    
    try:
        tokenizer, embed_weight = load_qwen_embeddings(snapshot_dir)
        
        # Test concepts (Mid-layers typically hold abstract knowledge, e.g. Layer 30)
        concepts_to_test = ["Swift", "Apple", "Code", "Quantum"]
        
        for concept in concepts_to_test:
            query_jcross_dictionary(concept, layer_idx=30, tokenizer=tokenizer, embed_weight=embed_weight, dict_dir=dict_dir)
            
    except Exception as e:
        print(f"{C_RED}Execution failed: {e}{C_RESET}")

if __name__ == "__main__":
    main()
