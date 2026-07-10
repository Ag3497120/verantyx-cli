import os
import gc
import struct
import argparse
import numpy as np
import torch
from huggingface_hub import HfApi, hf_hub_download, login, HfFileSystem
from safetensors import safe_open

def svd_compress(tensor: torch.Tensor, rank_ratio: float = 0.2):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tensor = tensor.to(device).float()
    tensor = torch.nan_to_num(tensor, nan=0.0, posinf=0.0, neginf=0.0)
    k = max(1, int(tensor.size(0) * rank_ratio if tensor.size(0) < tensor.size(1) else tensor.size(1) * rank_ratio))
    U, S, V = torch.svd_lowrank(tensor, q=k)
    V = V.t()
    return U.half().cpu(), S.half().cpu(), V.half().cpu()

def write_tensor_svd(f, name, U, S, V):
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<I', len(name_bytes)))
    f.write(name_bytes)
    f.write(struct.pack('<I', 1))
    rows, rank = U.shape
    _, cols = V.shape
    f.write(struct.pack('<I', rows))
    f.write(struct.pack('<I', cols))
    f.write(struct.pack('<I', rank))
    f.write(U.numpy().tobytes())
    f.write(S.numpy().tobytes())
    f.write(V.numpy().tobytes())
    f.write(np.ones(cols, dtype=np.float16).tobytes())
    f.write(np.zeros(rows, dtype=np.float16).tobytes())
    f.write(np.eye(rank, dtype=np.float16).tobytes())

def write_tensor_dense2d(f, name, tensor):
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<I', len(name_bytes)))
    f.write(name_bytes)
    f.write(struct.pack('<I', 2))
    rows, cols = tensor.shape
    f.write(struct.pack('<I', rows))
    f.write(struct.pack('<I', cols))
    f.write(tensor.half().numpy().tobytes())

def write_tensor_dense1d(f, name, tensor):
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<I', len(name_bytes)))
    f.write(name_bytes)
    f.write(struct.pack('<I', 3))
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

def resume_convert(model_id, token, output_file, processed_files_list):
    print(f"Logging into HuggingFace...")
    login(token=token)
    
    with open(processed_files_list, 'r') as f:
        processed_files = set([line.strip().replace("...", "").strip() for line in f.readlines()])
    
    fs = HfFileSystem(token=token)
    all_files = fs.ls(model_id)
    safetensors = [f["name"].split("/")[-1] for f in all_files if f["name"].endswith(".safetensors")]
    
    to_process = [st for st in safetensors if st not in processed_files]
    print(f"Total files: {len(safetensors)}, Processed: {len(processed_files)}, Remaining: {len(to_process)}")
    
    with open(output_file, "ab") as out_f:
        for st_file in to_process:
            print(f"Downloading {st_file} ...")
            local_path = hf_hub_download(repo_id=model_id, filename=st_file, token=token)
            print(f"Processing {st_file} ...")
            process_safetensors(local_path, out_f)
            os.remove(local_path)
            print(f"Deleted {local_path} to free space.")

    print(f"[Success] Appended remaining tensors to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="zai-org/GLM-5.2")
    parser.add_argument("--token", type=str, required=True)
    parser.add_argument("--output", type=str, default="model_glm.jgen")
    parser.add_argument("--processed", type=str, required=True)
    args = parser.parse_args()
    resume_convert(args.model, args.token, args.output, args.processed)
