#!/usr/bin/env bash
# Verantyx ワンコマンドセットアップ
#   ./setup.sh          … venv作成 + 依存インストール + Rustエンジンのビルド
#   ./setup.sh --model  … 上に加えて Qwen2.5-0.5B GGUF を取得し jgen に変換
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\033[36m[setup]\033[0m %s\n' "$*"; }

# ── 1. Python 環境 ───────────────────────────────────────────────────────────
PY=python3
command -v "$PY" >/dev/null || { echo "python3 が必要です"; exit 1; }
if [ ! -d .venv ]; then
  say "仮想環境 .venv を作成"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
say "依存パッケージをインストール (numpy/transformers/torch/gguf ...)"
pip install -q --upgrade pip
pip install -q -r requirements.txt
if [ "$(uname)" = "Darwin" ]; then
  say "macOS 検出: 視覚層 (OCR/画面操作) 用の pyobjc を追加"
  pip install -q pyobjc-framework-Quartz pyobjc-framework-Vision || \
    say "pyobjc の導入に失敗 (視覚層なしでも他機能は動作します)"
fi

# ── 2. Rust エンジン (jcross_engine_glm) ─────────────────────────────────────
if ! command -v cargo >/dev/null; then
  say "Rust が見つかりません。https://rustup.rs から導入してください"
  say "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
  exit 1
fi
say "Rust エンジンをビルド (初回は数分かかります)"
( cd jcross_engine_glm && env -u CARGO_TARGET_DIR cargo build --release )
case "$(uname)" in
  Darwin) LIB=jcross_engine_glm/target/release/libjcross_engine_glm.dylib ;;
  Linux)  LIB=jcross_engine_glm/target/release/libjcross_engine_glm.so ;;
  *)      LIB=jcross_engine_glm/target/release/jcross_engine_glm.dll ;;
esac
[ -f "$LIB" ] && say "エンジン: $LIB" || { echo "エンジンのビルドに失敗しました"; exit 1; }

# ── 3. ルーターモデル (任意: --model で自動取得) ─────────────────────────────
if [ "${1:-}" = "--model" ]; then
  say "Qwen2.5-0.5B-Instruct (GGUF) を取得して jgen に変換"
  python - <<'PYEOF'
from huggingface_hub import hf_hub_download
p = hf_hub_download("Qwen/Qwen2.5-0.5B-Instruct-GGUF", "qwen2.5-0.5b-instruct-q8_0.gguf")
print(p)
PYEOF
  GGUF=$(python -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('Qwen/Qwen2.5-0.5B-Instruct-GGUF','qwen2.5-0.5b-instruct-q8_0.gguf'))")
  python jgen_forge.py add "$GGUF" --name qwen2.5-0.5b-router --dense \
    --tokenizer Qwen/Qwen2.5-0.5B-Instruct
  say "変換完了。verantyx.config.json の models.router で固定するか、"
  say "レジストリから自動解決されます"
else
  say "モデル未取得の場合: ./setup.sh --model で 0.5B ルーターを自動変換できます"
  say "手持ちの GGUF/safetensors は 'python jgen_forge.py sources' で発見・変換"
fi

say "完了。起動: source .venv/bin/activate && python verantyx.py"
