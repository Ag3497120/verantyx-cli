from huggingface_hub import hf_hub_download
import shutil

print("[+] Downloading Qwen tokenizer...")
path = hf_hub_download(repo_id="Qwen/Qwen2.5-0.5B-Instruct", filename="tokenizer.json")
shutil.copy(path, "tokenizer.json")
print("[+] Saved tokenizer.json")
