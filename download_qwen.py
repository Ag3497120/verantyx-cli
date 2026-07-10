from huggingface_hub import snapshot_download
import sys

print("Starting download of Qwen/Qwen2.5-0.5B-Instruct...")
print("This includes model.safetensors which is ~0.98 GB.")

try:
    path = snapshot_download(
        repo_id="Qwen/Qwen2.5-0.5B-Instruct",
        local_dir_use_symlinks=False
    )
    print(f"Download complete! Saved to {path}")
except Exception as e:
    print(f"Error: {e}")
