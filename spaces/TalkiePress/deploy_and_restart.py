#!/usr/bin/env python3
"""Push cleaned TalkiePress files and restart the Hugging Face Space.

Usage:
  export HF_TOKEN=hf_...   # write token for user kofdai
  python3 spaces/TalkiePress/deploy_and_restart.py

Requires: pip install huggingface_hub
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO_ID = "kofdai/TalkiePress"
HERE = Path(__file__).resolve().parent


def main() -> int:
    token = (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    )
    if not token:
        print("ERROR: set HF_TOKEN (Hugging Face write token for kofdai)", file=sys.stderr)
        return 2

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    print(f"[1/3] Uploading {HERE} → spaces/{REPO_ID} …")
    api.upload_folder(
        folder_path=str(HERE),
        repo_id=REPO_ID,
        repo_type="space",
        # Drop tunnel / proxy artifacts and unused trees if they still exist remotely
        delete_patterns=[
            "start_tunnel.sh",
            "tunnel.log",
            "api.py",
            "__pycache__/**",
            "talkie/**",
            "verantyx_jcross_v7/**",
            "public/**",
        ],
        ignore_patterns=[".git*", "deploy_and_restart.py", "*.gguf"],
        commit_message=(
            "Fix boot: remove Cloudflare tunnel, defer GGUF load "
            "(clear abuse pause / 503)"
        ),
    )
    print("[2/3] Factory restart …")
    try:
        runtime = api.restart_space(repo_id=REPO_ID, factory_reboot=True)
    except TypeError:
        runtime = api.restart_space(repo_id=REPO_ID)
    print("restart response:", runtime)
    print("[3/3] Polling runtime …")
    for i in range(60):
        info = api.space_info(REPO_ID)
        stage = (info.runtime.stage if info.runtime else None) or "?"
        err = getattr(info.runtime, "error_message", None) if info.runtime else None
        print(f"  [{i}] stage={stage} err={err}")
        if stage in ("RUNNING", "RUNNING_BUILDING", "BUILDING", "APP_STARTING"):
            if stage == "RUNNING":
                print(f"OK: https://huggingface.co/spaces/{REPO_ID}")
                return 0
        if stage == "RUNTIME_ERROR":
            print("Space entered RUNTIME_ERROR — check build logs", file=sys.stderr)
            return 1
        if stage == "PAUSED" and err and "abusive" in str(err).lower():
            print(
                "Still flagged abusive after reboot. Open HF support / Space "
                "settings and request unflag, or duplicate the Space.",
                file=sys.stderr,
            )
        time.sleep(10)
    print("Timed out waiting for RUNNING", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
