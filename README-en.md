# Verantyx

**Languages:** [日本語](README.md) · [English](README-en.md) · [简体中文](README-zh-CN.md) · [繁體中文](README-zh-TW.md) · [한국어](README-ko.md) · [Español](README-es.md) · [Português](README-pt-BR.md) · [Deutsch](README-de.md) · [Français](README-fr.md) · [Русский](README-ru.md) · [Українська](README-uk.md) · [Türkçe](README-tr.md) · [العربية](README-ar.md)

**A local always-on AI harness — keep a small brain resident, let a stronger brain speak when needed, and move deliberation & memory as vectors**

Verantyx is not a product that competes on “smarter models.” It is a CLI runtime on *your* machine that controls **which model to call, when to remember, and how to carry consensus**.

Only a ~0.5B router stays resident. Questions are organized in a vector-space council; larger models (workers / HuggingFace / Ollama / LM Studio) are summoned only when needed and **speak once**. Conversations, tasks, and screen context are written into *eternal memory*, surviving restarts without depending on a context window.

> **What the benchmarks showed (no hype)**  
> With the **same** 0.5B speaker, council accuracy ≈ router-alone (501 items, difference of 1 question). Accuracy gains come from **who speaks**, not from deliberation itself.  
> Comparing natural-language debate vs vector debate on the same 0.5B, vectors win by **~+15pt** at about **half the latency**. Council value is a **cheaper, less brittle medium and control layer** — not an accuracy booster.

> 📖 **The Verantyx Chronicles** — how failures shaped the design  
> - [Vol 1: The Genesis & MPS Trap](docs/chronicles/Vol1_The_Genesis_and_MPS_Trap.md)  
> - [Vol 2: Zero-RAM Inference](docs/chronicles/Vol2_Zero_RAM_Inference.md)  
> - [Vol 3: Multilingual Madness & JCross](docs/chronicles/Vol3_Multilingual_Madness_and_JCross.md)  
> - [Vol 4: The Philosophical Drift](docs/chronicles/Vol4_The_Philosophical_Drift.md)

---

## What it is / what it is not

| Ships | Does not ship |
|---|---|
| Local resident router + model summoning | “Council beats solo by a huge accuracy margin” |
| Vector deliberation (cheaper / stabler than NL debate) | Competing with frontier model leaderboards |
| Swappable speakers (accuracy depends on speaker choice) | Opaque cloud-only agents |
| Eternal memory, reflexes, skills, Omni / Agent / Demo | A weight-training platform |

In one line:

> **A local AI OS: small brain always on, strong brain only when speaking, vectors for debate and memory.**

---

## Setup

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
./setup.sh --model     # venv + deps + Rust engine + 0.5B router convert
```

```bash
source .venv/bin/activate
python verantyx.py     # menu → Omni (recommended) / Demo / Mind / Agent …
```

| Requirement | Notes |
|---|---|
| Python 3.10+ / Rust (cargo) | Engine build ([rustup.rs](https://rustup.rs)) |
| 16GB RAM recommended (8GB OK for 0.5B-only) | |
| macOS / Linux / Windows | Metal / CUDA / CPU fallback |
| Optional: LM Studio / Ollama | Large speakers / agent backends |

---

## Architecture (harness)

```
You
 └─ Omni (verantyx.py)
     ├─ Intent routing …… chat→council / task→agent
     ├─ 0.5B router …… resident: traffic control, memory, vectors
     ├─ Vector council …… hidden-state / distribution exchange (not text debate)
     ├─ Speaker swap …… sage / worker / Ollama / LM Studio (where quality lives)
     ├─ Agent …… web (real WebKit) / files / shell / macOS control
     ├─ Eternal memory …… multi-resolution vectors + text
     ├─ Static lexicon …… mmap associative search without firing large weights
     └─ Forge …… GGUF / safetensors → JGEN
```

**Core idea:** separate thinking (vectors) from speaking (text). Do not force long CoT on tiny models. Call a strong speaker only when quality matters.

---

## What measurements say (`benchmarks/` is reproducible)

### 1. Same speaker → almost no council accuracy gain

501 items, escalation off, **speaker fixed to 0.5B router**:

| Mode | Accuracy (95% CI) |
|--------|-----------------|
| router | 52.5% [48.1–56.8] |
| council (vector) | 52.3% [47.9–56.6] |

Difference: 1 question. CIs fully overlap. Time +~2.5s/item.  
→ **To raise accuracy, enlarge the speaker — do not add more deliberation rounds.**

> An earlier “council +22.7pt” claim was **unfair**: under `--no-escalate`, the speaker still auto-escalated to another worker. Corrected via `force_router_speaker`.

### 2. As a medium, vectors beat natural-language debate

85 items, same 0.5B, 2 fixed rounds:

| Mode | Accuracy | Avg time | Cost feel |
|--------|--------|----------|----------|
| router | 60.0% | 7.0s | 1 generation |
| **council (vector)** | **63.5%** | 8.8s | hidden-state exchange |
| nl_council (NL) | 48.2% | 19.7s | ~13 generations |

vector − NL = **+15.3pt**, ~half the time.  
→ Prefer vectors over text debate; still not a large accuracy engine vs router alone.

### 3. Other

| Item | Result |
|---|---|
| JGEN (SVD) reconstruct | 0.036% rel. error, cosine 1.000 |
| Intent routing (task/chat) | 95.0% (n=40) |
| Escalation on | 150–400s+/hard item (bridge wait; 90s per-call cap; no whole-council deadline yet) |

Details: [`benchmarks/README.md`](benchmarks/README.md)

---

## Why this shape (short history)

1. **MPS Trap** — resident-all collapses → resident tiny router + summon  
2. **Zero-RAM / JGEN** — mmap + appendable binary weights  
3. **JCross** — cross-tokenizer talk via string+probability distributions  
4. **Philosophical Drift** — anchor vector drift; reuse as perturbation tests  
5. **Now** — Omni + memory + agent + Forge; claims corrected by benches

---

## Config

Default **auto**. To pin roles:

```bash
cp verantyx.config.example.json verantyx.config.json
# or in Omni: /config set models.worker ornith9b_full
```

| Key | Meaning |
|---|---|
| `models.router` | Resident router |
| `models.worker` / `models.sage` | Speakers (quality lives here) |
| `models.agent_backend` | Agent brain |
| `models.bridges` | External council participants |
| `escalation.enabled` / `bridge_timeout_s` | Auto-summon + per-call cap (default 90s) |
| `memory.enabled` | `false` = secret mode |

`python verantyx_config.py show | set <key> <value> | reset`

---

## Usage

`python verantyx.py` → **Omni** (daily) / **Demo** (video-wall viz; usability intentionally worse)

```
/model /council /scout
/convert X
/agent TASK  /ask Q
/dict /analogy
/recall /vault /persona
/screen /see
/secret /config /reflex /skills
```

```bash
python jgen_forge.py sources
python jgen_forge.py pull <name-fragment>
python jgen_forge.py list
```

---

## Core files

| File | Role |
|---|---|
| `verantyx.py` | Launcher + Omni / Demo |
| `verantyx_council.py` | Vector council + `ask_nl` |
| `verantyx_mind.py` | Rust FFI + eternal memory |
| `verantyx_agent.py` / `verantyx_browser.py` | Agent + WebKit fetch |
| `benchmarks/` | Reproducible measurements |
| `jcross_engine_glm/` | Rust engine |

Weights and personal memory (`.verantyx_chrono/`) are not in the repo.

---

## Limits (stated on release)

- 0.5B router language ability is weak; answer quality follows the **speaker**.  
- Vector consensus is geometric convergence, not a proof of truth.  
- MoE GPU batch / SSM hybrid attention inference incomplete (lexicon OK).  
- No whole-council wall-clock deadline yet.  
- Long-horizon forget / degradation benches are next.

---

## License

Released for research and experimentation. Respect each upstream model’s license.
