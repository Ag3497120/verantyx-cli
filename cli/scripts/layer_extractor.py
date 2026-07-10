import os
import struct
import torch
import glob
from safetensors import safe_open
from tqdm import tqdm

def extract_and_compress(model_dir, output_path, rank=128):
    safetensor_files = glob.glob(os.path.join(model_dir, "*.safetensors"))
    safetensor_files.sort()
    
    if not safetensor_files:
        print("No safetensor files found in", model_dir)
        return
        
    print(f"Found {len(safetensor_files)} safetensor files.")
    print(f"Starting generic SVD extraction (Rank {rank}). Output: {output_path}")
    
    # We will write the JGEN format v2:
    # Magic: JGEN
    # Version: 2
    # Count of tensors: (we will patch this at the end, so we keep track)
    
    out_file = open(output_path, "wb")
    out_file.write(b"JGEN")
    out_file.write(struct.pack("<I", 2)) # version 2 generic format
    
    # Placeholder for total tensor count
    count_pos = out_file.tell()
    out_file.write(struct.pack("<I", 0)) 
    
    tensor_count = 0
    
    for st_file in safetensor_files:
        print(f"\nProcessing {os.path.basename(st_file)}...")
        with safe_open(st_file, framework="pt", device="cpu") as f:
            keys = f.keys()
            for key in tqdm(keys):
                tensor = f.get_tensor(key)
                
                # We need to serialize the key name so the trainer knows what this tensor is!
                name_bytes = key.encode('utf-8')
                out_file.write(struct.pack("<H", len(name_bytes)))
                out_file.write(name_bytes)
                
                if tensor.dim() == 2 and "embed" not in key and "lm_head" not in key and "norm" not in key:
                    # Type 1: Compressed Generative Linear
                    out_file.write(struct.pack("<B", 1))
                    
                    rows, cols = tensor.shape
                    
                    W = tensor.float()
                    # Perform SVD on CPU
                    U, S, Vh = torch.linalg.svd(W, full_matrices=False)
                    
                    # Truncate to rank
                    U_r = U[:, :rank].half()
                    S_r = S[:rank].half()
                    V_r = Vh[:rank, :].T.half()
                    
                    # Modulators (initialized to 1)
                    mod_x = torch.ones(cols, dtype=torch.float16)
                    mod_y = torch.ones(rows, dtype=torch.float16)
                    
                    out_file.write(struct.pack("<I I I", rows, cols, rank))
                    out_file.write(U_r.numpy().tobytes())
                    out_file.write(S_r.numpy().tobytes())
                    out_file.write(V_r.numpy().tobytes())
                    out_file.write(mod_x.numpy().tobytes())
                    out_file.write(mod_y.numpy().tobytes())
                    
                else:
                    # Type 0: Uncompressed Raw Tensor (Biases, Embeddings, Norms)
                    out_file.write(struct.pack("<B", 0))
                    
                    # Write shape
                    out_file.write(struct.pack("<B", tensor.dim()))
                    for dim_size in tensor.shape:
                        out_file.write(struct.pack("<I", dim_size))
                        
                    tensor_fp16 = tensor.half()
                    out_file.write(tensor_fp16.numpy().tobytes())
                    
                tensor_count += 1
                
    # Go back and write the actual tensor count
    out_file.seek(count_pos)
    out_file.write(struct.pack("<I", tensor_count))
    out_file.close()
    
    print(f"\nExtraction complete! Compressed {tensor_count} tensors into {output_path}")

if __name__ == "__main__":
    import sys
    model_dir = sys.argv[1] if len(sys.argv) > 1 else "/Users/motonishikoudai/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B"
    
    if "snapshots" in model_dir and not model_dir.endswith(os.sep):
        pass
    else:
        snapshots_dir = os.path.join(model_dir, "snapshots")
        if os.path.exists(snapshots_dir):
            snapshots = os.listdir(snapshots_dir)
            if snapshots:
                # Use the first snapshot dir
                model_dir = os.path.join(snapshots_dir, snapshots[0])
                
    extract_and_compress(model_dir, "qwen_27b_generative.jgen", rank=512)
