import os
from huggingface_hub import HfApi, create_repo

SRC_DIR = "/Users/motonishikoudai/verantyx-cli"
space_id = "kofdai/Verantyx-God-Mode"

def main():
    api = HfApi()
    print(f"Creating Space {space_id}...")
    try:
        create_repo(
            repo_id=space_id, 
            repo_type="space", 
            space_sdk="gradio", 
            private=False, 
            exist_ok=True
        )
        print("Space created or already exists.")
    except Exception as e:
        print(f"Space creation info: {e}")

    print("Uploading repository to Space...")
    try:
        api.upload_folder(
            folder_path=SRC_DIR,
            repo_id=space_id,
            repo_type="space",
            ignore_patterns=[
                ".git", ".git/*", "__pycache__", 
                "*.jgen", "*.pt", "*.pth", "*.safetensors", 
                "*.mp4", "*.webm"
            ]
        )
        print("Upload successful!")
        print(f"Your Space is live at: https://huggingface.co/spaces/{space_id}")
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    main()
