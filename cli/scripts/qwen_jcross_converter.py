import torch
import os
import time
from safetensors import safe_open
import glob
import re

C_CYAN = '\033[96m'
C_MAGENTA = '\033[95m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'

def compress_to_jcross(dense_weight: torch.Tensor, target_rank: int = 128) -> dict:
    """
    Compress dense matrix to JCross V2 format using SVD.
    """
    start_time = time.time()
    
    # Convert to float32 for stable SVD
    dense_weight = dense_weight.to(torch.float32)
    U, S, Vh = torch.linalg.svd(dense_weight, full_matrices=False)
    V = Vh.T
    
    # Truncate to target rank
    U_k = U[:, :target_rank]
    S_k = S[:target_rank]
    V_k = V[:, :target_rank]
    
    # Generate C_valve (Initial state is identity)
    C_valve = torch.eye(target_rank, dtype=torch.float16)
    
    end_time = time.time()
    print(f"{C_GREEN}   >> SVD completed in {end_time - start_time:.2f} seconds.{C_RESET}")
    
    # Return compressed components in float16
    return {
        "mx": U_k.to(torch.float16),
        "my": V_k.to(torch.float16),
        "S": S_k.to(torch.float16),
        "V": V_k.to(torch.float16),
        "C_valve": C_valve
    }

def run_full_converter():
    print(f"\n{C_MAGENTA}========================================================================={C_RESET}")
    print(f"{C_MAGENTA}     [FULL COMPRESSION] QWEN 3.6 27B -> JCROSS STATIC DICTIONARY{C_RESET}")
    print(f"{C_MAGENTA}=========================================================================\n{C_RESET}")
    
    output_dir = os.path.join(os.path.dirname(__file__), "qwen_jcross_dicts")
    os.makedirs(output_dir, exist_ok=True)
    
    hf_snapshot_dir = "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
    safetensor_files = glob.glob(os.path.join(hf_snapshot_dir, "*.safetensors"))
    safetensor_files.sort()
    
    if not safetensor_files:
        print(f"{C_RED}[Error] No safetensor files found in {hf_snapshot_dir}{C_RESET}")
        return
        
    print(f"{C_YELLOW}[Engine] Found {len(safetensor_files)} physical safetensor chunks. Commencing full extraction...{C_RESET}")
    
    total_layers_processed = 0
    overall_start_time = time.time()
    
    for st_file in safetensor_files:
        print(f"\n{C_CYAN}>> Scanning file: {os.path.basename(st_file)}{C_RESET}")
        
        try:
            with safe_open(st_file, framework="pt", device="cpu") as f:
                keys = f.keys()
                # Target down_proj weights
                layer_keys = [k for k in keys if "mlp.down_proj.weight" in k]
                
                for layer_key in layer_keys:
                    match = re.search(r'layers\.(\d+)\.', layer_key)
                    if not match:
                        continue
                    
                    layer_idx = match.group(1)
                    print(f"{C_YELLOW}   [Extracting] Layer {layer_idx} ({layer_key})...{C_RESET}")
                    
                    raw_layer_weight = f.get_tensor(layer_key)
                    print(f"      -> Shape: {raw_layer_weight.shape} ({raw_layer_weight.dtype})")
                    
                    # Compress
                    jcross_dict = compress_to_jcross(raw_layer_weight, target_rank=128)
                    
                    # Save
                    output_path = os.path.join(output_dir, f"real_layer_{layer_idx}_down_proj.pt")
                    torch.save(jcross_dict, output_path)
                    
                    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    print(f"{C_CYAN}      -> Saved {output_path} ({file_size_mb:.2f} MB){C_RESET}")
                    
                    total_layers_processed += 1
                    
        except Exception as e:
            print(f"{C_RED}[Error] Failed to process {st_file}: {e}{C_RESET}")
            
    overall_end_time = time.time()
    print(f"\n{C_MAGENTA}========================================================================={C_RESET}")
    print(f"{C_GREEN}[COMPLETE] Successfully compressed {total_layers_processed} layers into Zero-RAM static dictionaries!{C_RESET}")
    print(f"Total time elapsed: {(overall_end_time - overall_start_time)/60:.2f} minutes.")
    print(f"{C_MAGENTA}=========================================================================\n{C_RESET}")

if __name__ == "__main__":
    run_full_converter()
