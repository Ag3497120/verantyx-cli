import os
import sys
from huggingface_hub import HfApi, hf_hub_download

REPO_NAME = "Vera-qwen-0.5b-jgen-commande-translate"
BASE_MODEL = "Qwen/Qwen1.5-0.5B"

# Qwen 0.5B から引き継ぐ設定ファイル群
CONFIG_FILES = [
    "config.json",
    "generation_config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.json",
    "merges.txt"
]

def main():
    api = HfApi()
    
    try:
        user_info = api.whoami()
        username = user_info['name']
        print(f"[*] Logged in as: {username}")
    except Exception as e:
        print(f"[!] Hugging Face Authentication failed: {e}")
        sys.exit(1)
        
    repo_id = f"{username}/{REPO_NAME}"
    print(f"[*] Target repository: {repo_id}")
    
    for file_name in CONFIG_FILES:
        print(f"[*] Processing {file_name}...")
        try:
            # ベースモデルからファイルをダウンロード（またはキャッシュから取得）
            local_path = hf_hub_download(repo_id=BASE_MODEL, filename=file_name)
            
            # 作成したリポジトリへアップロード
            api.upload_file(
                path_or_fileobj=local_path,
                path_in_repo=file_name,
                repo_id=repo_id
            )
            print(f"  -> Uploaded {file_name} successfully.")
        except Exception as e:
            print(f"  [!] Failed to process {file_name}: {e}")

    print(f"\\n[*] All config files uploaded to: https://huggingface.co/{repo_id}")

if __name__ == "__main__":
    main()
