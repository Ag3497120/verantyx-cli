"""
deploy_space.py — kofdai/Verantyx-God-Mode Space の中身を丸ごと置き換える。
================================================================================
1. ステージングディレクトリを組み立てる:
     space/ の全ファイル
   + リポジトリ本体から実装をコピー (verantyx_mind.py / verantyx_config.py /
     jgen_forge.py / jcross_engine_glm のソース)
2. huggingface_hub で既存ファイルを全削除しつつ一括アップロード
   (delete_patterns=["*"] により旧実装は消える)

使い方: python space/deploy_space.py [--repo kofdai/Verantyx-God-Mode]
        (要: huggingface-cli login 済み or HF_TOKEN 環境変数)
"""
import argparse
import os
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SHARED_MODULES = ["verantyx_mind.py", "verantyx_config.py", "jgen_forge.py"]
SPACE_FILES = ["README.md", "Dockerfile", "requirements.txt",
               "app.py", "space_council.py", "build_model.py"]


def assemble(stage):
    for f in SPACE_FILES:
        shutil.copy2(os.path.join(HERE, f), os.path.join(stage, f))
    shutil.copytree(os.path.join(HERE, "static"), os.path.join(stage, "static"))
    for f in SHARED_MODULES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(stage, f))
    eng_dst = os.path.join(stage, "jcross_engine_glm")
    os.makedirs(eng_dst)
    shutil.copy2(os.path.join(ROOT, "jcross_engine_glm", "Cargo.toml"),
                 os.path.join(eng_dst, "Cargo.toml"))
    shutil.copytree(os.path.join(ROOT, "jcross_engine_glm", "src"),
                    os.path.join(eng_dst, "src"))
    # Space 側では bin ターゲットは不要 (lib のみビルド)
    print(f"[deploy] staged: {sum(len(fs) for _, _, fs in os.walk(stage))} files")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="kofdai/Verantyx-God-Mode")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    stage = tempfile.mkdtemp(prefix="verantyx_space_")
    try:
        assemble(stage)
        if a.dry_run:
            print(f"[deploy] dry-run: staging at {stage} (削除しません)")
            return
        from huggingface_hub import HfApi
        api = HfApi()
        api.upload_folder(
            repo_id=a.repo, repo_type="space", folder_path=stage,
            delete_patterns=["*"],
            commit_message="Verantyx God Mode v2: Rust jgen エンジン + "
                           "0.5B×5役割ベクトル評議会の3D可視化 (旧実装を置換)")
        print(f"[deploy] 完了: https://huggingface.co/spaces/{a.repo}")
    finally:
        if not a.dry_run:
            shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    main()
