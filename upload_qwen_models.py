import os
from huggingface_hub import HfApi, create_repo

SRC_DIR = "/Users/motonishikoudai/verantyx-cli"
repo_id = "kofdai/verantyx-qwen-hybrid"

files_to_upload = [
    "cli/qwen_0.5b_full.jgen",
    "cli/python_modulators_v2_3d.pt"
]

def main():
    api = HfApi()
    print(f"Creating repository {repo_id}...")
    try:
        create_repo(repo_id, repo_type="model", private=False, exist_ok=True)
        print("Repository created or already exists (Public).")
    except Exception as e:
        print(f"Repo creation info: {e}")

    print("Starting upload...")
    for file_path in files_to_upload:
        full_path = os.path.join(SRC_DIR, file_path)
        if os.path.exists(full_path):
            file_size_mb = os.path.getsize(full_path) / (1024**2)
            print(f"Uploading {file_path} ({file_size_mb:.2f} MB)...")
            try:
                api.upload_file(
                    path_or_fileobj=full_path,
                    path_in_repo=file_path,
                    repo_id=repo_id,
                    repo_type="model"
                )
                print(f" -> Successfully uploaded {file_path}")
            except Exception as e:
                print(f" -> Failed to upload {file_path}: {e}")
        else:
            print(f"Skipping {file_path} (File not found)")

    print("\nAll uploads complete! You can view your backup at:")
    print(f"https://huggingface.co/{repo_id}")

if __name__ == "__main__":
    main()
