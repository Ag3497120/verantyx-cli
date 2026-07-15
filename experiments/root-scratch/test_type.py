import mlx.core as mx
import glob

files = glob.glob("/Users/motonishikoudai/Library/Caches/models/kofdai/talkie-1930-13b-it-mlx-8bit/*.safetensors")
w = mx.load(files[0])
key = list(w.keys())[0]
print(f"Key: {key}, Type: {w[key].dtype}")

for k in w.keys():
    if "attn_resid.weight" in k:
        print(f"Key: {k}, Type: {w[k].dtype}")
        break
