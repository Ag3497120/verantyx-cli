#!/usr/bin/env bash
# record_demo.sh — honest short smoke for terminal capture (no fake visuals)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="--no-model"
if [[ "${1:-}" == "--with-model" ]]; then
  MODE=""
elif [[ "${1:-}" == "--no-model" || -z "${1:-}" ]]; then
  MODE="--no-model"
fi

echo "=== Verantyx honest demo ==="
echo "cwd: $ROOT"
echo "product entry: python3 verantyx.py  (Omni / council / memory)"
echo "smoke: scripts/smoke_router_classify.py ${MODE:-"(loads model)"}"
echo

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="python3"
fi

"$PY" "$ROOT/scripts/smoke_router_classify.py" ${MODE}

echo
echo "=== done ==="
echo "Next (optional): python3 verantyx.py  # Omni menu if weights exist"
echo "See docs/DEMO.md for asciinema / script capture steps."
