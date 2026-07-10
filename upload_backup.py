import os
from huggingface_hub import HfApi, create_repo

SRC_DIR = "/Users/motonishikoudai/verantyx-cli"
repo_id = "kofdai/verantyx-jcross-backup"

files_to_upload = [
    # Scripts
    "cli/scripts/verantyx_shell.py",
    "cli/scripts/bucket_relay_swarm.py",
    "cli/scripts/telepathic_coder.py",
    "cli/scripts/ambient_tools.py",
    "cli/scripts/matrix_ui.py",
    "cli/scripts/chrono_memory.py",
    "cli/scripts/two_phase_commit.py",
    "cli/scripts/jcross_6axis_calibrator.py",
    "cli/scripts/train_translator.py",
    "cli/scripts/thunderbolt_rpc.py",
    
    # Models (~16.6GB Total)
    "cli/gemma_12b_generative.jgen",
    "cli/commander_12b_rank1024.jgen",
    "cli/python_modulators_v2_3d.pt",
    "cli/embed.pt",
    "cli/lm_head.pt",
    "models/jcross_translator_latest.pt"
]

def main():
    api = HfApi()
    print(f"Creating repository {repo_id}...")
    try:
        create_repo(repo_id, repo_type="model", private=True, exist_ok=True)
        print("Repository created or already exists (Private).")
    except Exception as e:
        print(f"Repo creation info: {e}")

    print("Starting upload (Total size ~16GB)...")
    for file_path in files_to_upload:
        full_path = os.path.join(SRC_DIR, file_path)
        if os.path.exists(full_path):
            file_size_gb = os.path.getsize(full_path) / (1024**3)
            print(f"Uploading {file_path} ({file_size_gb:.2f} GB)...")
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
