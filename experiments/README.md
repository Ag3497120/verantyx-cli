# Experiments

This monorepo still holds **experimental / alternate engines and scratch paths** next to the main Omni entry (`verantyx.py`).

Examples that may move later (not deleted in packaging cleanups):

- `jcross_engine/`, `jcross_engine_0_5b/`, `jcross_engine_glm/` — Rust inference engine variants
- Other PoC scripts and dual-* harnesses at the repo root

**Future:** a clearer split (e.g. `verantyx-core` vs experiments) may relocate these trees. Until then, treat them as in-tree R&D; prefer `verantyx.py` + `benchmarks/` for the product path.

Do not mass-delete engines without an explicit migration PR.
