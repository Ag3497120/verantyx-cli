import mlx.core as mx
import glob
files = glob.glob("/Users/motonishikoudai/Library/Caches/models/kofdai/talkie-1930-13b-it-mlx-8bit/*.safetensors")
w = mx.load(files[0])
for k in w.keys():
    if "mlp_resid.weight" in k:
        print(f"Key: {k}, Type: {w[k].dtype}")
        break
