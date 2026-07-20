# Verantyx

**Languages:** [English](README.md) · [日本語](README.ja.md) · [简体中文](README-zh-CN.md) · [繁體中文](README-zh-TW.md) · [한국어](README-ko.md) · [Español](README-es.md) · [Português](README-pt-BR.md) · [Deutsch](README-de.md) · [Français](README-fr.md) · [Русский](README-ru.md) · [Українська](README-uk.md) · [Türkçe](README-tr.md) · [العربية](README-ar.md)

> **Tiny always-on router. Big model only when needed. Memory that survives reboot.**

Run a **strong local AI on a laptop** without keeping a large model resident 24/7.  
A ~0.5B router stays warm; you summon Ollama / HF / LM Studio speakers **only when you need them**; conversation is written to **eternal memory** so it outlives the process.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Demo](https://img.shields.io/badge/demo-60s-brightgreen.svg)](docs/DEMO.md)
[![Docker](https://img.shields.io/badge/docker-one%20command-blue.svg)](#install-in-60-seconds)

---

## The one thing this is for

**Local AI ops without the RAM tax.**

| Without Verantyx | With Verantyx |
|---|---|
| Big model sits in VRAM all day | Tiny router stays resident |
| Context window = amnesia on restart | Eternal memory across reboots |
| Cloud owns routing & memory | You own who speaks and what is kept |

Not a “smarter model.” A **control harness**: who to call, when to remember, how to carry consensus as vectors (cheaper than chatty multi-agent text loops).

---

## 60-second demo

No fake GIFs. Real commands → full script in [`docs/DEMO.md`](docs/DEMO.md).

```bash
# A) Zero weights (safe / CI-friendly)
docker build -t verantyx:demo . && docker run --rm -it verantyx:demo
# or: python3 scripts/smoke_router_classify.py --no-model

# B) You already have router weights
python3 verantyx.py          # menu → Omni → ask one thing → quit → reopen: memory still there
```

**What you should feel in one minute:** tiny brain always on → big brain speaks once → reboot doesn’t wipe you.

---

## Install in 60 seconds

### Option 1 — Docker (fastest try)

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
docker build -t verantyx:demo .
docker run --rm -it verantyx:demo
```

### Option 2 — Python venv (weights optional)

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/smoke_router_classify.py --no-model   # works without models
```

### Option 3 — Full local stack (router convert + Rust engine)

```bash
git checkout stable    # calmer tip for first try
./setup.sh --model
source .venv/bin/activate
python3 verantyx.py
```

Profiles & Omni: [`docs/QUICKSTART.md`](docs/QUICKSTART.md) · [`docs/OMNI_PROFILES.md`](docs/OMNI_PROFILES.md)

---

## How it works (30 seconds)

```text
  you ──► 0.5B router (always on)
              │  classify / route / remember
              ▼
         vector council (optional internal agreement)
              │
              ▼
         speaker once (Ollama / HF / LM Studio / local jgen)
              │
              ▼
         eternal memory ──► survives quit & reboot
```

| Plain words | Name in code |
|---|---|
| Tiny always-on brain | Router |
| Internal agreement medium | Vector council / company |
| Model that talks | Speaker |
| Memory across restarts | Eternal memory |

---

## Show HN / share blurb (copy-paste)

> **Verantyx** — Tiny always-on router. Big model only when needed. Memory that survives reboot.  
> Local CLI harness: keep ~0.5B resident, summon a large local speaker once, store memory outside the context window.  
> Demo: `docker build -t verantyx:demo . && docker run --rm -it verantyx:demo`  
> Repo: https://github.com/Ag3497120/verantyx-cli

Longer pitch: [`docs/PITCH.md`](docs/PITCH.md)

---

## Honest limits (we don’t inflate stars or scores)

- **Accuracy ≈ who speaks.** Same 0.5B speaker → council ≈ router alone on fair benches.  
- **Vectors beat NL debate as a medium** (~+15pt, ~½ the time on our 85-item medium test) — that’s control cost, not “magic IQ.”  
- Structure ≠ world knowledge. Details & numbers: [`benchmarks/README.md`](benchmarks/README.md).

---

## Contribute

We want the 60s path to stay honest and fast.

- Good first issues: [label](https://github.com/Ag3497120/verantyx-cli/labels/good%20first%20issue)
- Docs, demo polish, Docker, smoke scripts — see [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Prefer small PRs to `main`. Try `stable` first if you’re evaluating.

---

## License

Code: [MIT](LICENSE). **Model weights are separate** — bring your own via Ollama / HF / local convert.

Built in the open. No fake metrics. Star if the 60-second path made you want this on your machine.
