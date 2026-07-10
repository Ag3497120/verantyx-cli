import torch
import os
import glob
from safetensors import safe_open
from transformers import AutoTokenizer

C_CYAN = '\033[96m'
C_MAGENTA = '\033[95m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'

def run_semantic_calibration():
    print(f"\n{C_CYAN}========================================================================={C_RESET}")
    print(f"{C_CYAN}         VERANTYX SEMANTIC CALIBRATOR (Orthogonal Procrustes)            {C_RESET}")
    print(f"{C_CYAN}=========================================================================\n{C_RESET}")
    
    # 1. Load Tokenizers
    qwen_path = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
    gemma_path = "/Users/motonishikoudai/.cache/huggingface/hub/models--google--gemma-4-12B/snapshots/56820d7d8cbe8e47975a53325439ed272e91cff2"
    
    print(f"{C_YELLOW}[Init] Loading Tokenizers...{C_RESET}")
    tok_qwen = AutoTokenizer.from_pretrained(qwen_path, trust_remote_code=True)
    tok_gemma = AutoTokenizer.from_pretrained(gemma_path, trust_remote_code=True)
    
    # 2. Load Embedding Tensors from Safetensors
    print(f"{C_YELLOW}[Init] Loading Embedding Matrices from Disk...{C_RESET}")
    qwen_st = os.path.join(qwen_path, "model-00001-of-00015.safetensors")
    gemma_st = glob.glob(os.path.join(gemma_path, "*.safetensors"))[0]
    
    with safe_open(qwen_st, framework="pt", device="cpu") as f:
        embed_qwen = f.get_tensor("model.language_model.embed_tokens.weight").to(torch.float32)
        
    with safe_open(gemma_st, framework="pt", device="cpu") as f:
        embed_gemma = f.get_tensor("model.language_model.embed_tokens.weight").to(torch.float32)
        
    print(f"  -> Qwen Matrix:  {embed_qwen.shape} (5120 dim)")
    print(f"  -> Gemma Matrix: {embed_gemma.shape} (3840 dim)")
    
    # 3. Define Anchor Vocabulary (Programming Concepts)
    anchor_words = [
        "Swift", "Apple", "class", "func", "struct", "import", "math", 
        "return", "print", "String", "Int", "Double", "var", "let", 
        "if", "else", "for", "while", "true", "false", "nil", "guard",
        "calculate", "add", "subtract", "multiply", "divide", "calculator",
        "code", "app", "iOS", "UI", "button", "screen", "view"
    ]
    
    print(f"\n{C_MAGENTA}[Phase 1] Extracting Anchor Vectors...{C_RESET}")
    vecs_gemma = []
    vecs_qwen = []
    valid_words = []
    
    for word in anchor_words:
        # We add a space to avoid subword chunking differences if possible, or just raw word
        # Some tokenizers prefix with space ' Swift' vs 'Swift'. We try raw first.
        tokens_g = tok_gemma.encode(word, add_special_tokens=False)
        tokens_q = tok_qwen.encode(word, add_special_tokens=False)
        
        # Only use words that map to exactly 1 token in BOTH models to guarantee semantic purity
        if len(tokens_g) == 1 and len(tokens_q) == 1:
            vecs_gemma.append(embed_gemma[tokens_g[0]])
            vecs_qwen.append(embed_qwen[tokens_q[0]])
            valid_words.append(word)
            
    if len(valid_words) < 5:
        print(f"{C_RED}[Error] Not enough single-token anchor words found ({len(valid_words)}).{C_RESET}")
        return
        
    print(f"{C_GREEN}Found {len(valid_words)} pure semantic anchors: {valid_words}{C_RESET}")
    
    A = torch.stack(vecs_gemma) # N x 3840
    B = torch.stack(vecs_qwen)  # N x 5120
    
    # Normalize vectors
    A = torch.nn.functional.normalize(A, p=2, dim=1)
    B = torch.nn.functional.normalize(B, p=2, dim=1)
    
    # 4. Orthogonal Procrustes via SVD
    print(f"\n{C_YELLOW}[Phase 2] Executing Orthogonal Procrustes Alignment...{C_RESET}")
    
    # M = A^T B  (Shape: 3840 x 5120)
    M = torch.matmul(A.T, B)
    
    # SVD: M = U S V^T
    print("Computing SVD...")
    U, S, Vh = torch.linalg.svd(M, full_matrices=False)
    
    # The optimal projection matrix W = U V^T
    # Note: U is (3840, 3840), Vh is (3840, 5120) when full_matrices=False
    W = torch.matmul(U, Vh) # Shape: (3840, 5120)
    
    # Verify alignment
    A_projected = torch.matmul(A, W)
    avg_similarity = torch.mean(torch.sum(A_projected * B, dim=1))
    
    print(f"{C_GREEN}Alignment Complete! Average Cosine Similarity over anchors: {avg_similarity:.4f}{C_RESET}")
    
    # 5. Save physical matrices
    out_dir = os.path.join(os.path.dirname(__file__), "qwen_jcross_dicts")
    os.makedirs(out_dir, exist_ok=True)
    
    file_ab = os.path.join(out_dir, "bridge_gemma_to_qwen.pt")
    file_ba = os.path.join(out_dir, "bridge_qwen_to_gemma.pt")
    
    # PyTorch Linear layers expect weight shape (out_features, in_features)
    # W maps 3840 to 5120. x @ W = (1, 3840) @ (3840, 5120) = (1, 5120)
    # Linear(in=3840, out=5120) weight is (5120, 3840), so weight = W.T
    
    torch.save(W.T.to(torch.bfloat16), file_ab)
    torch.save(W.to(torch.bfloat16), file_ba) # Inverse mapping is W^T, so linear weight is W
    
    print(f"\n{C_CYAN}[Saved] Calibrated Matrices:{C_RESET}")
    print(f"  - {file_ab} (Gemma -> Qwen)")
    print(f"  - {file_ba} (Qwen -> Gemma)")
    print(f"{C_MAGENTA}The Chimera Bridge is now Semantically Linked.{C_RESET}")

if __name__ == "__main__":
    run_semantic_calibration()
