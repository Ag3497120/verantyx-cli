import os
import shutil
from huggingface_hub import HfApi

SRC_DIR = "/Users/motonishikoudai/verantyx-cli"
TMP_DIR = "/tmp/hf_space_deploy"
space_id = "kofdai/Verantyx-God-Mode"

required_files = [
    "app.py",
    "requirements.txt",
    "config.json",
    "README.md",
    "cli/scripts/bucket_relay_swarm_experimental.py",
    "cli/scripts/telepathic_coder_experimental.py",
    "cli/scripts/jcross_6axis_calibrator.py"
]

def main():
    print("Preparing clean deployment folder...")
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR)

    for file_path in required_files:
        src = os.path.join(SRC_DIR, file_path)
        dst = os.path.join(TMP_DIR, file_path)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            print(f"Copied {file_path}")
        else:
            print(f"Warning: {file_path} not found!")

    api = HfApi()
    print("Uploading clean folder to Space...")
    try:
        api.upload_folder(
            folder_path=TMP_DIR,
            repo_id=space_id,
            repo_type="space"
        )
        print("Upload successful!")
        print(f"Your Space is live at: https://huggingface.co/spaces/{space_id}")
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    main()
