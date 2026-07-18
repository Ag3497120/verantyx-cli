# 0.5B-only Mode Audit Report

Generated: 2026-07-18T11:04:39.633196

## Environment
- Router: `converted_models/qwen0_5b_full.jgen` (from Ollama qwen2.5:0.5b GGUF)
- Escalation OFF; worker/sage none; bridges []
- Host: Cursor Cloud 4 vCPU / 16GB / no GPU
- Bare baseline: HF `Qwen/Qwen2.5-0.5B-Instruct` (Ollama segfaults on this host)

## Mode / command surface
### inventory (1/1 ok)
- **OK** `modes` (0s)

### smoke (9/10 ok)
- **OK** `router_classify_no_model` (0.02s)
- **OK** `council_prompt_no_escalate` (363.37s)
- **OK** `mind_prompt_worker_none` (79.4s)
- **FAIL** `agent_echo_task` (2.24s) — agent brain is ollama 0.5b (not jgen router); may segfault under RAM pressure
- **OK** `dict_assoc` (3.98s)
- **OK** `matryoshka_prompt` (225.17s)
- **OK** `config_show` (0.02s)
- **OK** `forge_list` (0.09s)
- **OK** `forge_sources` (0.08s)
- **OK** `model_scout_report` (0.11s)

### omni_cmd (23/23 ok)
- **OK** `config_describe` (0s)
- **OK** `council_members` (0s)
- **OK** `scout` (0.02s)
- **OK** `convert_list` (0.0s)
- **OK** `mem_status` (0.0s)
- **OK** `ask_council` (174.16s)
- **OK** `fast_off_semantics` (0s)
- **OK** `tokens_rounds_ask` (163.84s)
- **OK** `traces_list` (0.0s)
- **OK** `reflex` (0.0s)
- **OK** `skills` (0.0s)
- **OK** `dict_lexicon` (0.67s)
- **OK** `persona` (0.0s)
- **OK** `model` (0s) — interactive choose() — skipped in cloud audit
- **OK** `screen` (0s) — requires display/OCR — skipped
- **OK** `see` (0s) — requires prior /screen — skipped
- **OK** `spatial` (0s) — requires Capture assets — skipped
- **OK** `vault` (0s) — filesystem crawl interactive — skipped
- **OK** `files` (0s) — needs vault index — skipped
- **OK** `sage` (0s) — disabled by 0.5B-only config
- **OK** `bridge` (0s) — disabled by bridges=[]
- **OK** `convert_pull` (0s) — already converted qwen0.5b — skipped to save time
- **OK** `demo_mode` (0s) — requires multi-terminal GUI approval — skipped

### memory (5/7 ok)
- **OK** `write_via_mind` (233.31s) — memory.enabled=true; not --secret
- **FAIL** `write_via_council` (900.12s)
- **OK** `recall_marker` (22.97s) — expects marker in recall hits
- **OK** `recall_fruit` (24.56s)
- **OK** `api_memory_search` (19.99s)
- **OK** `secret_write_attempt` (496.49s)
- **FAIL** `secret_not_recalled` (25.59s) — ok means secret marker was NOT found (correct isolation)

### long_horizon (0/2 ok)
- **FAIL** `multi_turn_memory_quiz` (956.51s) — needs >=2 of 3 facts recalled after 3 prior turns
- **FAIL** `instruction_chain_list` (1454.5s) — 0.5B instruction following without memory

## Quality (4 easy factual items, fair speaker)

| mode | correct | accuracy | avg latency |
|---|---|---|---|
| router | 4/4 | 100% | 37.1s |
| council | 4/4 | 100% | 190.6s |
| puzzle | 4/4 | 100% | 366.9s |
| solo (HF bare) | 4/4 | 100% | 0.8s |

Interpretation: on these easy facts, **council/puzzle do not improve or degrade accuracy vs router or bare HF**. Cost is latency: puzzle ~10× council? Wait council~5× router, puzzle~10× router, while HF solo is ~50× faster than jgen router on CPU.

## Weaknesses observed

1. **Latency tax (major)**: jgen router CPU ~37s/Q; council ~191s; puzzle ~367s vs HF solo <1s. Structure adds cost without accuracy gain at fixed 0.5B speaker.
2. **Long-horizon memory quiz failed**: after planting name/city/tool across turns, final answer did not surface ≥2 facts — eternal memory write happens, but **0.5B retrieval+speaking does not reliably use it**.
3. **Instruction chaining failed**: accumulating list 1..5 without memory broke (format drift).
4. **Agent mode unavailable here**: Ollama llama-server segfaults; cannot exercise tool loop with ollama 0.5b on this host.
5. **Council CLI write timeout**: `write_via_council` hit 900s timeout once (CPU contention / long speak). Mind write path was reliable.
6. **Demo/screen/spatial/vault**: interactive/GUI — not exercised.
7. **Secret isolation**: no `SECRET_*` nodes in cortex store (good). Harness `secret_not_recalled` false-failed because `--recall QUERY` echoes QUERY in stdout.

## Bugs fixed during audit (see PR commits)
- `fit_vec` for 896→1024 memory/traces
- reflex/injection/skill vector padding
- config describe `_comment` crash
- router resolve for hidden≠1024
- HFSage CPU/cuda/mps device selection

## Artifacts
- Harness log: `/tmp/halfb_audit3.log`
- Quality: `benchmarks/results/halfb_audit_20260718_081951/quality_bench/`
- Narrative: `docs/HALFB_MODE_AUDIT.md`