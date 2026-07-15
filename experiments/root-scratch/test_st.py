import json
import struct
import glob
import os

st_files = glob.glob("/Users/motonishikoudai/Library/Caches/models/kofdai/talkie-1930-13b-it-mlx-8bit/*.safetensors")
if not st_files:
    print("No safetensors found")
else:
    for st_file in st_files:
        with open(st_file, 'rb') as f:
            header_size = struct.unpack('<Q', f.read(8))[0]
            header = f.read(header_size)
            metadata = json.loads(header)
            keys = list(metadata.keys())
            print(f"File: {os.path.basename(st_file)}")
            print(f"Sample keys: {keys[:10]}")
            mlp_keys = [k for k in keys if "mlp" in k or "layers.0" in k]
            print(f"MLP/Layer0 keys: {mlp_keys[:10]}")
            break
