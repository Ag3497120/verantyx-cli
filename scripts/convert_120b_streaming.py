import os
import gc
import json
import struct
import argparse
import numpy as np
import torch
from huggingface_hub import HfApi, snapshot_download, login
from safetensors import safe_open

def svd_compress(tensor: torch.Tensor, rank_ratio: float = 0.2):
    tensor = tensor.float()
    U, S, V = torch.linalg.svd(tensor, full_matrices=False)
    k = max(1, int(S.size(0) * rank_ratio))
    U_k = U[:, :k]
    S_k = S[:k]
    V_k = V[:k, :]
    return U_k.half(), S_k.half(), V_k.half()

def write_tensor_svd(f, name, U, S, V):
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<I', len(name_bytes)))
    f.write(name_bytes)
    
    f.write(struct.pack('<I', 1)) # 1 = SVDLossless (mocking it for PoC)
    
    rows, rank = U.shape
    _, cols = V.shape
    
    f.write(struct.pack('<I', rows))
    f.write(struct.pack('<I', cols))
    f.write(struct.pack('<I', rank))
    
    f.write(U.numpy().tobytes())
    f.write(S.numpy().tobytes())
    f.write(V.numpy().tobytes())
    
    # write dummy c_valve, mod_x, mod_y
    f.write(np.zeros((rank, rank), dtype=np.float16).tobytes())
    f.write(np.zeros(rank, dtype=np.float16).tobytes())
    f.write(np.zeros(rank, dtype=np.float16).tobytes())

def write_tensor_dense2d(f, name, tensor):
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<I', len(name_bytes)))
    f.write(name_bytes)
    
    f.write(struct.pack('<I', 2)) # 2 = Dense2D
    rows, cols = tensor.shape
    f.write(struct.pack('<I', rows))
    f.write(struct.pack('<I', cols))
    
    f.write(tensor.half().numpy().tobytes())

def write_tensor_dense1d(f, name, tensor):
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<I', len(name_bytes)))
    f.write(name_bytes)
    
    f.write(struct.pack('<I', 3)) # 3 = Dense1D
    f.write(struct.pack('<I', tensor.numel()))
    f.write(tensor.half().numpy().tobytes())

def convert_model(model_id, token, output_file):
    print(f"[System] Logging into HuggingFace with token...")
    login(token=token)
    api = HfApi()
    
    try:
        user_info = api.whoami()
        username = user_info['name']
        print(f"[System] Authenticated as {username}")
    except Exception as e:
        print(f"[Error] Failed to authenticate token: {e}")
        return

    print(f"[System] Downloading / verifying model {model_id} ...")
    try:
        model_dir = snapshot_download(repo_id=model_id, token=token, allow_patterns=["*.safetensors", "*.json"])
    except Exception as e:
        print(f"[Error] Failed to download model {model_id}. Ensure the repo exists and you have access.")
        print(f"Exception: {e}")
        return

    print(f"[System] Model downloaded to {model_dir}. Starting streaming SVD conversion...")
    
    safetensors_files = [f for f in os.listdir(model_dir) if f.endswith(".safetensors")]
    
    with open(output_file, "wb") as out_f:
        # Magic string
        out_f.write(b"JGEN")
        out_f.write(struct.pack("<I", 1)) # version 1
        
        for st_file in safetensors_files:
            file_path = os.path.join(model_dir, st_file)
            print(f"[Worker] Processing {st_file} ...")
            
            with safe_open(file_path, framework="pt", device="cpu") as f:
                for key in f.keys():
                    tensor = f.get_tensor(key)
                    
                    if len(tensor.shape) == 2 and ("proj" in key or "weight" in key) and "norm" not in key and "embed" not in key and "lm_head" not in key:
                        print(f"  -> SVD Compressing {key} {tensor.shape}")
                        U, S, V = svd_compress(tensor, rank_ratio=0.2)
                        write_tensor_svd(out_f, key, U, S, V)
                    elif len(tensor.shape) == 2:
                        print(f"  -> Saving Dense2D {key} {tensor.shape}")
                        write_tensor_dense2d(out_f, key, tensor)
                    elif len(tensor.shape) == 1:
                        print(f"  -> Saving Dense1D {key} {tensor.shape}")
                        write_tensor_dense1d(out_f, key, tensor)
                    else:
                        print(f"  -> Skipping unsupported tensor {key} {tensor.shape}")
                    
                    del tensor
                    gc.collect()

    print(f"[System] Conversion complete. Output saved to {output_file}")
    
    upload_repo = f"{username}/gpt-oss-120b-jgen"
    print(f"[System] Uploading to HuggingFace Hub: {upload_repo}")
    
    try:
        api.create_repo(repo_id=upload_repo, private=True, exist_ok=True)
        api.upload_file(
            path_or_fileobj=output_file,
            path_in_repo=output_file,
            repo_id=upload_repo,
            repo_type="model"
        )
        print(f"[Success] Successfully uploaded {output_file} to https://huggingface.co/{upload_repo}")
    except Exception as e:
        print(f"[Error] Failed to upload to HuggingFace: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="openai/gpt-oss-120b")
    parser.add_argument("--token", type=str, required=True)
    parser.add_argument("--output", type=str, default="model_120b.jgen")
    args = parser.parse_args()
    
    convert_model(args.model, args.token, args.output)
