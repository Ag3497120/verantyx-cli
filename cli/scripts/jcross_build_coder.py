import os
import struct
import torch
from safetensors import safe_open
from huggingface_hub import snapshot_download

def build_coder_jgen(model_id="Qwen/Qwen2.5-0.5B-Instruct", output_path="coder.jgen"):
    print(f"[+] Downloading/Loading {model_id}...")
    model_path = snapshot_download(model_id, allow_patterns=["*.safetensors"])
    
    st_files = [os.path.join(model_path, f) for f in os.listdir(model_path) if f.endswith(".safetensors")]
    
    tensor_map = {}
    for st_file in st_files:
        with safe_open(st_file, framework="pt", device="cpu") as f:
            for k in f.keys():
                tensor_map[k] = st_file
                
    keys = list(tensor_map.keys())
    keys.sort()
    
    total_tensors = len(keys)
    print(f"[+] Total Tensors to Process for Coder: {total_tensors}")
    
    with open(output_path, "wb") as f_out:
        f_out.write(b"JGEN")
        f_out.write(struct.pack("<I", 3)) # Version 3
        f_out.write(struct.pack("<I", total_tensors))
        
        for k in keys:
            with safe_open(tensor_map[k], framework="pt", device="cpu") as f_in:
                W = f_in.get_tensor(k)
                name_bytes = k.encode('utf-8')
                f_out.write(struct.pack("<H", len(name_bytes)))
                f_out.write(name_bytes)
                
                if len(W.shape) == 2:
                    # Type 2: Dense 2D
                    f_out.write(struct.pack("<B", 2))
                    f_out.write(struct.pack("<I I", W.shape[0], W.shape[1]))
                elif len(W.shape) == 1:
                    # Type 3: Dense 1D
                    f_out.write(struct.pack("<B", 3))
                    f_out.write(struct.pack("<I", W.shape[0]))
                else:
                    print(f"[-] Skipping unknown shape: {k} {W.shape}")
                    continue
                    
                f_out.write(W.half().numpy().tobytes())
                print(f"  -> Extracted {k} {W.shape}")

    print(f"\n[+] Successfully built {output_path}!")

if __name__ == "__main__":
    build_coder_jgen()
