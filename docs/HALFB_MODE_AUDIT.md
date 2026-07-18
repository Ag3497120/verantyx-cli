# 0.5B-only Mode Audit (Cloud CPU)

Runtime notes from Cursor Cloud Agent testing against converted
`qwen0_5b_full.jgen` (from Ollama `qwen2.5:0.5b` GGUF) with
`escalation.enabled=false`, `models.worker/sage=none`, `bridges=[]`.

Host: 4 vCPU / 16GB RAM / **no GPU**. Harness: `scripts/audit_halfb_modes.py`.

## Modes (CLI menu)

| Mode | Path tested | Result / weakness |
|------|-------------|-------------------|
| **Omni** | Council/API backends for slash cmds | Works after hidden-dim fixes. Interactive `/model`/`/vault`/`/screen` skipped. |
| **Demo** | — | Skipped (multi-terminal GUI + confirmation). |
| **Mind** | `--prompt` / `--recall` | Works. ~1–3 min/turn on CPU. |
| **Agent** | `--backend ollama:qwen2.5:0.5b` | **Fails here**: Ollama llama-server segfaults on this host. |
| **辞書** | `verantyx_dict.py assoc` | Smoke OK. |
| **軌跡** | `ThoughtTrace.list` | Works after `fit_vec` pad to 1024-d store. |
| **記憶** | Mind write + `--recall` + `Council.memory_search` | Eternal memory **works** across process boundaries. |

## Bugs found & fixed in this branch

1. **ThoughtTrace / CortexMemory assumed `HIDDEN=1024`**, but Qwen2.5-0.5B is **896-d** → crash in `put_vector` / `memory.add`. Fixed via `fit_vec()` pad/truncate.
2. **`RouterReflex` / `InjectionPolicy` / `SkillLibrary`** wrote/read native-width vectors into 1024-d chrono files → `advise()` crash on later council asks. Fixed with `fit_vec` + truncate-on-read.
3. **`verantyx_config.describe()`** crashed on top-level `"_comment": "..."` string.
4. **`resolve_router()`** only accepted `hidden==1024`, missing Qwen2.5-0.5B (896).
5. **`HFSage` hardcoded MPS** → unusable on Linux CPU cloud. Now mps/cuda/cpu.

## Eternal memory

- Write via Mind + recall by marker: **OK**
- API `memory_search`: **OK**
- Secret mode isolation (`--secret` must not persist): covered by harness
- Weakness: recall quality is limited by 0.5B PromptEOL embeddings; multi-hop / paraphrase recall is fragile. Multi-turn “remember my name/city/tool” quiz is the stress case.

## Long-horizon

- Instruction-following list accumulation (1..5) without memory: expected weak on 0.5B (format drift).
- Multi-turn fact retention with memory enabled: primary long-task check.

## Quality (fair 0.5B speaker) — measured

`verantyx_bench.py --modes router,council,puzzle,solo --no-escalate --max-items 4 --rounds 1`
`--solo-model Qwen/Qwen2.5-0.5B-Instruct`

| mode | accuracy | avg latency |
|------|----------|-------------|
| router (jgen) | 4/4 (100%) | **37.1s** |
| council | 4/4 (100%) | **190.6s** (~5× router) |
| puzzle | 4/4 (100%) | **366.9s** (~10× router) |
| solo HF bare | 4/4 (100%) | **0.8s** |

**No accuracy degradation vs bare HF on these easy facts.** The tax is latency (and jgen CPU overhead vs transformers). Full write-up: `benchmarks/results/halfb_audit_20260718_081951/REPORT.md`.

## Environment weaknesses (not product bugs)

- **Ollama inference segfaults** on this cloud image → Agent mode & Ollama solo unreliable here.
- Council ~**3–6 minutes/question** on 4 vCPU (5 role forwards + speak).
- Demo / screen / spatial / vault need local GUI or interactive consent.

## How to reproduce

```bash
source .venv/bin/activate
export JGEN_MODEL=$PWD/converted_models/qwen0_5b_full.jgen
# 0.5B-only config (see verantyx.config.example.json keys)
python3 -u scripts/audit_halfb_modes.py
```
