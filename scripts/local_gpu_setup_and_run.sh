#!/usr/bin/env bash
# ローカル GPU (Metal / CUDA) 向け: 依存導入 → エンジンビルド → Ollama/HF から
# 0.5B ルーターを取得・JGEN 変換 → 短い動作確認。
#
# 使い方 (リポジトリ直下で):
#   chmod +x scripts/local_gpu_setup_and_run.sh
#   ./scripts/local_gpu_setup_and_run.sh
#   ./scripts/local_gpu_setup_and_run.sh --from-ollama qwen2.5:0.5b
#   ./scripts/local_gpu_setup_and_run.sh --from-hf
#   ./scripts/local_gpu_setup_and_run.sh --skip-build   # エンジン済みのとき
set -euo pipefail
cd "$(dirname "$0")/.."

FROM="ollama"
OLLAMA_QUERY="qwen2.5:0.5b"
SKIP_BUILD=0
RUN_SMOKE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-ollama) FROM="ollama"; OLLAMA_QUERY="${2:-qwen2.5:0.5b}"; shift 2 || shift ;;
    --from-hf) FROM="hf"; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --no-smoke) RUN_SMOKE=0; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

say() { printf '\033[36m[local-gpu]\033[0m %s\n' "$*"; }

# ── Python venv ──────────────────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  say "venv 作成"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt huggingface_hub
if [[ "$(uname)" == "Darwin" ]]; then
  pip install -q pyobjc-framework-Quartz pyobjc-framework-Vision || true
fi

# ── Rust engine ──────────────────────────────────────────────────────────────
if [[ "$SKIP_BUILD" -eq 0 ]]; then
  command -v cargo >/dev/null || {
    echo "Rust (cargo) が必要です: https://rustup.rs"
    exit 1
  }
  say "jcross_engine_glm をビルド"
  case "$(uname)" in
    Darwin)
      # Metal (default features)
      ( cd jcross_engine_glm && env -u CARGO_TARGET_DIR cargo build --release )
      LIB=jcross_engine_glm/target/release/libjcross_engine_glm.dylib
      ;;
    Linux)
      if command -v nvcc >/dev/null || [[ -c /dev/nvidia0 ]]; then
        say "CUDA 検出 → --features cuda"
        ( cd jcross_engine_glm && env -u CARGO_TARGET_DIR \
            cargo build --release --no-default-features --features cuda )
      else
        say "GPU なし → CPU ビルド"
        ( cd jcross_engine_glm && env -u CARGO_TARGET_DIR \
            cargo build --release --no-default-features )
      fi
      LIB=jcross_engine_glm/target/release/libjcross_engine_glm.so
      ;;
    *)
      echo "未対応 OS: $(uname)"; exit 1 ;;
  esac
  [[ -f "$LIB" ]] || { echo "エンジンビルド失敗: $LIB"; exit 1; }
  say "エンジン: $LIB"
else
  say "エンジンビルドをスキップ"
fi

# ── モデル取得・変換 ─────────────────────────────────────────────────────────
mkdir -p models_dropzone converted_models
NAME="qwen2_5_0_5b_router"

if [[ "$FROM" == "ollama" ]]; then
  if ! command -v ollama >/dev/null; then
    echo "ollama が見つかりません。--from-hf を使うか Ollama を入れてください。"
    exit 1
  fi
  say "Ollama モデル確認/取得: $OLLAMA_QUERY"
  ollama pull "$OLLAMA_QUERY" || true
  say "Forge: Ollama/LM Studio/HF キャッシュから pull → JGEN"
  python3 jgen_forge.py sources
  # pull は名前の部分一致。失敗したら dropzone 経由にフォールバック
  if ! python3 jgen_forge.py pull "$OLLAMA_QUERY" --name "$NAME" --dense \
      --tokenizer Qwen/Qwen2.5-0.5B-Instruct; then
    say "pull 失敗 → discover_sources のパスを dropzone に配置して scan"
    python3 - <<PY
import jgen_forge, os, shutil
q = "${OLLAMA_QUERY}".lower()
srcs = jgen_forge.discover_sources()
hits = [s for s in srcs if q in s["name"] or q.replace(":", "") in s["name"].replace(":", "")]
if not hits:
    raise SystemExit(f"source not found for {q!r}. Run: python3 jgen_forge.py sources")
src = hits[0]
os.makedirs(jgen_forge.DROPZONE, exist_ok=True)
dest = os.path.join(jgen_forge.DROPZONE, "qwen0.5b.gguf")
if os.path.exists(dest):
    os.remove(dest)
try:
    os.link(src["path"], dest)
except OSError:
    shutil.copy2(src["path"], dest)
print("placed", dest)
jgen_forge.cmd_scan()
PY
  fi
else
  say "HF から GGUF 取得 → JGEN 変換"
  python3 - <<'PY'
from huggingface_hub import hf_hub_download
import jgen_forge
gguf = hf_hub_download(
    "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
    "qwen2.5-0.5b-instruct-q8_0.gguf",
)
jgen_forge.cmd_add(
    gguf,
    name="qwen2_5_0_5b_router",
    dense=True,
    tokenizer="Qwen/Qwen2.5-0.5B-Instruct",
)
PY
fi

python3 jgen_forge.py list

# ── ローカル設定 ─────────────────────────────────────────────────────────────
JGEN="$(python3 - <<'PY'
import jgen_forge, os
reg = jgen_forge.load_registry()
ready = [m for m in reg["models"] if m.get("status") == "ready" and os.path.exists(m["jgen"])]
if not ready:
    raise SystemExit("no ready jgen in registry")
# prefer 0.5b-ish
ready.sort(key=lambda m: (m.get("hidden") or 10**9, m.get("size_bytes") or 0))
print(ready[0]["jgen"])
PY
)"
say "router jgen = $JGEN"

cat > verantyx.config.json <<EOF
{
  "models": {
    "router": "$JGEN",
    "router_tokenizer": "Qwen/Qwen2.5-0.5B-Instruct",
    "worker": "none",
    "sage": "none",
    "lexicon": "auto",
    "agent_backend": "auto",
    "bridges": []
  },
  "generation": { "speak_tokens": "auto", "language": null },
  "escalation": { "enabled": false, "ram_fraction": 0.45 },
  "memory": { "enabled": true }
}
EOF
say "wrote verantyx.config.json (0.5B-only, escalation off)"

# ── 動作確認 ────────────────────────────────────────────────────────────────
if [[ "$RUN_SMOKE" -eq 1 ]]; then
  say "スモーク: council --no-escalate (GPU なら Metal/CUDA 経路)"
  export JGEN_MODEL="$JGEN"
  python3 verantyx_council.py \
    --prompt "What is 2+2? Answer with only the number." \
    --no-escalate --secret --speak-tokens 16
  say "完了。対話起動: source .venv/bin/activate && python3 verantyx.py"
fi
