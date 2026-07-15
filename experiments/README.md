# Experiments

This monorepo still holds **experimental / alternate engines and scratch paths** next to the main Omni entry (`verantyx.py`).

## Layout

| Path | Role |
|---|---|
| `experiments/root-scratch/` | Former repo-root one-offs: `test_*`, logs, `my_clone.*`, backups (not the `tests/` package) |
| `scripts/legacy/` | Former root `patch_*` / `check_*` / `rewrite_*` / `temp_*` scripts |
| `jcross_engine/` (repo root) | Rust inference engine variants (may move later) |

**Product path:** prefer `verantyx.py` + [`docs/QUICKSTART.md`](../docs/QUICKSTART.md) + [`benchmarks/`](../benchmarks/).

Do not mass-delete engines without an explicit migration PR. Scratch under `root-scratch/` is kept for history only — do not treat it as supported API.
