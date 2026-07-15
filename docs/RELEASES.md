# Releases & legacy tags

## Current product (read this first)

**Current mainline product** is the **Omni / council / memory** local harness:

- Entry: `python3 verantyx.py`
- Docs: [`QUICKSTART.md`](QUICKSTART.md), [`OMNI_PROFILES.md`](OMNI_PROFILES.md), [`DEMO.md`](DEMO.md)
- License: **MIT for repository code**; **model weights are separate** (not covered by the MIT grant)

GitHub Releases / tags from earlier eras may describe a different CLI surface (including Claude-Code-era packaging). **If a tag’s README or notes disagree with `main`, trust `main`.**

## Recommended current tag

| Tag | Meaning |
|---|---|
| `v3.0.0-alpha` | Alpha marker for the Omni / council / memory line on current `main` |

Older tags such as `v2.4.x`, `v1.x`, `v0.2.0-alpha` remain in history for archaeology. They are **not** a promise that those trees match today’s README.

## Policy

- Do not invent benchmarks in release notes
- Prefer small PRs; do not rewrite entire git history to “clean” tags
- Demo: real terminal path only — see [`DEMO.md`](DEMO.md)
