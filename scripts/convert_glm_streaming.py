import os
import gc
import struct
import argparse
import numpy as np
import torch
from huggingface_hub import HfApi, snapshot_download, login
from safetensors import safe_open

def svd_compress(tensor: torch.Tensor, rank_ratio: float = 0.2):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tensor = tensor.to(device).float()
    U, S, V = torch.linalg.svd(tensor, full_matrices=False)
    k = max(1, int(S.size(0) * rank_ratio))
    return U[:, :k].half().cpu(), S[:k].half().cpu(), V[:k, :].half().cpu()

def write_tensor_svd(f, name, U, S, V):
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<I', len(name_bytes)))
    f.write(name_bytes)
    f.write(struct.pack('<I', 1)) # 1 = SVDLossless
    rows, rank = U.shape
    _, cols = V.shape
    f.write(struct.pack('<I', rows))
    f.write(struct.pack('<I', cols))
    f.write(struct.pack('<I', rank))
    f.write(U.numpy().tobytes())
    f.write(S.numpy().tobytes())
    f.write(V.numpy().tobytes())
    # JGEN format 3D Cross Structure (Cascading Lock / Neutral State)
    f.write(np.ones(cols, dtype=np.float16).tobytes()) # mod_x
    f.write(np.zeros(rows, dtype=np.float16).tobytes()) # mod_y
    f.write(np.eye(rank, dtype=np.float16).tobytes()) # c_valve

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

def process_safetensors(file_path, out_f):
    with safe_open(file_path, framework="pt", device="cpu") as f:
        for key in f.keys():
            tensor = f.get_tensor(key)
            if len(tensor.shape) == 2 and ("proj" in key or "weight" in key) and "norm" not in key and "embed" not in key and "head" not in key:
                print(f"  -> SVD Compressing {key} {tensor.shape}")
                U, S, V = svd_compress(tensor, rank_ratio=0.2)
                write_tensor_svd(out_f, key, U, S, V)
            elif len(tensor.shape) == 2:
                print(f"  -> Saving Dense2D {key} {tensor.shape}")
                write_tensor_dense2d(out_f, key, tensor)
            elif len(tensor.shape) == 1:
                print(f"  -> Saving Dense1D {key} {tensor.shape}")
                write_tensor_dense1d(out_f, key, tensor)
            del tensor
            gc.collect()

def convert_model(model_id, token, output_file):
    print(f"Logging into HuggingFace...")
    login(token=token)
    api = HfApi()
    username = api.whoami()['name']
    
    print(f"Downloading index for {model_id}...")
    model_dir = snapshot_download(repo_id=model_id, token=token, allow_patterns=["*.safetensors", "*.json"])
    
    # HuggingFace snapshot_download puts symlinks to blobs. Let's find the actual .safetensors files
    safetensors_files = []
    for root, _, files in os.walk(model_dir):
        for file in files:
            if file.endswith(".safetensors"):
                safetensors_files.append(os.path.join(root, file))
    
    with open(output_file, "wb") as out_f:
        out_f.write(b"JGEN")
        out_f.write(struct.pack("<I", 1))
        
        for st_file in safetensors_files:
            print(f"Processing {st_file} ...")
            process_safetensors(st_file, out_f)

    upload_repo = f"{username}/glm-5.2-jgen"
    print(f"Uploading to HuggingFace Hub: {upload_repo}")
    api.create_repo(repo_id=upload_repo, private=True, exist_ok=True)
    api.upload_file(path_or_fileobj=output_file, path_in_repo=output_file, repo_id=upload_repo, repo_type="model")
    print(f"[Success] Uploaded {output_file} to https://huggingface.co/{upload_repo}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="zai-org/GLM-5.2")
    parser.add_argument("--token", type=str, required=True)
    parser.add_argument("--output", type=str, default="model_glm.jgen")
    args = parser.parse_args()
    convert_model(args.model, args.token, args.output)
