# Legacy root scripts

One-off `patch_*`, `check_*`, `rewrite_*`, and `temp_*` scripts moved out of the repository root for hygiene.

They are **not** supported entrypoints. Prefer:

- `python3 verantyx.py` — Omni / council / memory CLI
- `python3 scripts/smoke_router_classify.py --no-model` — classify smoke without model download
- `./scripts/record_demo.sh` — honest terminal demo capture helper
