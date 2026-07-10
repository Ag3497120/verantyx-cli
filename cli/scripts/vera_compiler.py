import os
import argparse
import struct
import numpy as np
import torch
from safetensors import safe_open
from tqdm import tqdm
import glob
import shutil

class VeraSpatialCompiler:
    def __init__(self, model_path, output_path, block_size=64):
        self.model_path = model_path
        self.output_path = output_path
        self.meta_path = output_path.replace(".jcross", ".jmeta")
        self.idx_path = output_path.replace(".jcross", ".jidx")
        self.scout_path = output_path.replace(".jcross", ".jscout")
        self.block_size = block_size
        print(f"[*] Initializing Vera Spatial Compiler (Matrix-Aware) for: {model_path}")
        print(f"[*] Macro-Block Size: {block_size}x{block_size}")

    def get_matrix_type(self, key):
        if "input_layernorm.weight" in key: return 0
        if "post_attention_layernorm.weight" in key: return 1
        
        # Linear Attention / SSM
        if "linear_attn.conv1d" in key: return 2
        if "linear_attn.A_log" in key: return 3
        if "linear_attn.dt_bias" in key: return 4
        if "linear_attn.in_proj_a" in key: return 5
        if "linear_attn.in_proj_b" in key: return 6
        if "linear_attn.in_proj_qkv" in key: return 7
        if "linear_attn.in_proj_z" in key: return 8
        if "linear_attn.out_proj" in key: return 9
        if "linear_attn.norm.weight" in key: return 15
        
        # FFN
        if "mlp.gate_proj" in key: return 10
        if "mlp.up_proj" in key: return 11
        if "mlp.down_proj" in key: return 12
        
        # Full Attention (if any)
        if "self_attn.q_proj" in key: return 20
        if "self_attn.k_proj" in key: return 21
        if "self_attn.v_proj" in key: return 22
        if "self_attn.o_proj" in key: return 23
        
        return 255 # Unknown/Ignore

    def analyze_and_compile(self):
        print(f"[*] Starting Out-of-Core Physical Layout Restructuring (.jcross + .jidx) for: {self.model_path}")
        
        safetensors_files = []
        if os.path.isdir(self.model_path):
            safetensors_files = sorted(glob.glob(os.path.join(self.model_path, "*.safetensors")))
        elif self.model_path.endswith(".safetensors"):
            safetensors_files = [self.model_path]
            
        if not safetensors_files:
            print(f"[-] No .safetensors files found in {self.model_path}")
            return
            
        print(f"[*] Found {len(safetensors_files)} tensor file(s). Streaming to avoid RAM exhaustion...")
        
        tmp_dir = "jcross_tmp"
        os.makedirs(tmp_dir, exist_ok=True)
        layer_files = {} # z_coord -> bin file handle
        layer_idx_files = {} # z_coord -> idx file handle
        
        # Open jmeta file for 1D/small tensors
        meta_f = open(self.meta_path, "wb")
        meta_f.write(b"JMET")
        meta_f.write(struct.pack("<I", 1)) # version
        
        scout_f = open(self.scout_path, "wb")
        scout_f.write(b"JSCT")
        scout_f.write(struct.pack("<I", 1)) # version
        
        total_blocks_created = 0
        
        for file_path in safetensors_files:
            print(f"  > Processing: {os.path.basename(file_path)}")
            with safe_open(file_path, framework="pt", device="cpu") as sf:
                keys = list(sf.keys())
                for key in tqdm(keys):
                    matrix_type = self.get_matrix_type(key)
                    if matrix_type == 255 or "mtp" in key:
                        continue
                        
                    z_coord = -1
                    if "layers." in key:
                        parts = key.split(".")
                        try:
                            z_coord = int(parts[parts.index("layers") + 1])
                        except:
                            pass
                            
                    if z_coord == -1:
                        z_coord = 254
                        
                    tensor = sf.get_tensor(key)
                    
                    if tensor.dtype != torch.float16:
                        tensor = tensor.half()
                    
                    shape = list(tensor.shape)
                    
                    if len(shape) == 1 or "conv1d" in key:
                        tensor_bytes = tensor.numpy().tobytes()
                        meta_f.write(struct.pack("<B B I", z_coord & 0xFF, matrix_type & 0xFF, len(tensor_bytes)))
                        meta_f.write(tensor_bytes)
                        continue
                        
                    rows, cols = shape[0], shape[1]
                    
                    pad_rows = (self.block_size - (rows % self.block_size)) % self.block_size
                    pad_cols = (self.block_size - (cols % self.block_size)) % self.block_size
                    
                    if pad_rows > 0 or pad_cols > 0:
                        tensor = torch.nn.functional.pad(tensor, (0, pad_cols, 0, pad_rows))
                        rows, cols = tensor.shape[0], tensor.shape[1]
                        
                    # Extract Scout Weights for Dynamic Sparse Inference
                    if matrix_type in [8, 10]:
                        try:
                            # Use SVD to compress the projection matrix
                            U, S, V = torch.svd_lowrank(tensor.float(), q=16)
                            scout_w1 = V.half() # shape: (cols, 16)
                            scout_w2 = (U * S).half() # shape: (rows, 16)
                            
                            # Write Scout Metadata & Weights
                            scout_f.write(struct.pack("<B B H I I I I",
                                z_coord & 0xFF, matrix_type & 0xFF, 16,
                                scout_w1.shape[0], scout_w1.shape[1],
                                scout_w2.shape[0], scout_w2.shape[1]
                            ))
                            scout_f.write(scout_w1.numpy().tobytes())
                            scout_f.write(scout_w2.numpy().tobytes())
                        except Exception as e:
                            print(f"  [-] Scout SVD Failed for z={z_coord}, mtype={matrix_type}: {e}")
                    
                    if z_coord not in layer_files:
                        layer_files[z_coord] = open(os.path.join(tmp_dir, f"layer_{z_coord}.bin"), "wb")
                        layer_idx_files[z_coord] = open(os.path.join(tmp_dir, f"layer_{z_coord}.idx"), "wb")
                    
                    layer_f = layer_files[z_coord]
                    layer_idx_f = layer_idx_files[z_coord]
                    
                    for r in range(0, rows, self.block_size):
                        for c in range(0, cols, self.block_size):
                            block = tensor[r:r+self.block_size, c:c+self.block_size]
                            
                            row_idx = r // self.block_size
                            col_idx = c // self.block_size
                            
                            # Write 6-byte header to .idx instead of .bin
                            layer_idx_f.write(struct.pack("<B H H B", 
                                                    z_coord & 0xFF, 
                                                    col_idx & 0xFFFF, 
                                                    row_idx & 0xFFFF, 
                                                    matrix_type & 0xFF))
                            
                            block_bytes = block.numpy().tobytes()
                            layer_f.write(block_bytes)
                            total_blocks_created += 1
                            
                    del tensor

        for f in layer_files.values():
            f.close()
        for f in layer_idx_files.values():
            f.close()
            
        meta_f.close()
        scout_f.close()
        
        print("\n[*] Assembling final .jcross and .jidx files...")
        with open(self.output_path, "wb") as out_f, open(self.idx_path, "wb") as idx_f:
            # Write Magic Header for JIDX
            idx_f.write(b"JIDX")
            idx_f.write(struct.pack("<I", 1)) # Version 1
            idx_f.write(struct.pack("<I", total_blocks_created))
            
            for z in sorted(layer_files.keys()):
                # Copy Bin Data
                bin_path = os.path.join(tmp_dir, f"layer_{z}.bin")
                with open(bin_path, "rb") as tf:
                    shutil.copyfileobj(tf, out_f)
                    
                # Copy Index Data
                idx_part_path = os.path.join(tmp_dir, f"layer_{z}.idx")
                with open(idx_part_path, "rb") as tf:
                    shutil.copyfileobj(tf, idx_f)
                    
        shutil.rmtree(tmp_dir)

        print(f"\n[+] Spatial Compilation Complete!")
        print(f"  > Spatial Nodes Created: {total_blocks_created}")
        print(f"  > Binary Written to: {self.output_path} (Pure Matrix Data)")
        print(f"  > Index Written to: {self.idx_path} ({(total_blocks_created * 6) / 1024 / 1024:.2f} MB)")
        print(f"  > Meta Written to: {self.meta_path}")

def main():
    parser = argparse.ArgumentParser(description="Vera Spatial Compiler (Matrix-Aware)")
    parser.add_argument("--model", type=str, required=True, help="Path to input .safetensors")
    parser.add_argument("--output", type=str, default="model.jcross", help="Path to output .jcross binary")
    args = parser.parse_args()
    
    if not os.path.exists(args.model):
        print(f"Error: {args.model} not found.")
        return
        
    compiler = VeraSpatialCompiler(args.model, args.output)
    compiler.analyze_and_compile()

if __name__ == "__main__":
    main()
