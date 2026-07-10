"""
build_model.py — Docker ビルド時に1回だけ実行する。
1. Qwen1.5-0.5B-Chat の GGUF (q8_0) を取得
2. jgen_forge で JGEN v3 (dense) へ変換
3. 評議会を1度起動して、トークナイザ / 意味マスク / 6軸実測をイメージに焼き込む
4. three.js を static/vendor へ取得
"""
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

GGUF_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
GGUF_FILE = "qwen2.5-0.5b-instruct-q8_0.gguf"
THREE_URL = "https://unpkg.com/three@0.160.0/build/three.module.min.js"


def main():
    # 1. GGUF ダウンロード
    from huggingface_hub import hf_hub_download
    print(f"[build] downloading {GGUF_REPO}/{GGUF_FILE} ...")
    gguf_path = hf_hub_download(GGUF_REPO, GGUF_FILE)

    # 2. JGEN 変換
    import jgen_forge
    jgen_forge.cmd_add(gguf_path, name="qwen05b", dense=True,
                       tokenizer="Qwen/Qwen2.5-0.5B-Instruct")
    jgen = os.path.join(HERE, "converted_models", "qwen05b_full.jgen")
    assert os.path.exists(jgen), "conversion failed"
    os.environ["JGEN_MODEL"] = jgen

    # 3. ウォームアップ (トークナイザ・意味マスク・6軸をキャッシュ)
    from space_council import SpaceCouncil
    c = SpaceCouncil()
    events = list(c.deliberate("What is 2 + 2?", max_rounds=1))
    answer = next((e for e in events if e["type"] == "answer"), None)
    print(f"[build] warmup ok: {answer['text'][:80] if answer else 'no answer'}")

    # 4. three.js
    vendor = os.path.join(HERE, "static", "vendor")
    os.makedirs(vendor, exist_ok=True)
    dst = os.path.join(vendor, "three.module.min.js")
    print(f"[build] fetching three.js -> {dst}")
    urllib.request.urlretrieve(THREE_URL, dst)
    print("[build] done")


if __name__ == "__main__":
    sys.exit(main())
