from huggingface_hub import hf_hub_download
import os

file_path = hf_hub_download(repo_id="THUDM/glm-4-9b-chat", filename="modeling_chatglm.py", local_dir=".")
print("Downloaded to", file_path)
