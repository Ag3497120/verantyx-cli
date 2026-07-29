# JGEN / IDE integration notes (verantyx-cli side)

Companion to the Verantyx IDE plan (Milestones A–K). This repo ships the
engine + forge that the IDE bridges into.

## Already true on `main` (as of this branch)

| Plan claim | Status in verantyx-cli |
|---|---|
| Real Rust 24-layer forward (`jcross_engine_glm`) | Yes |
| Clean `extern "C"` ABI (no GIL) | Yes |
| `encode` / `encode_soft` / `inject_at_layer` / `encode_layers` | Yes |
| `JGEN_BASE_DIR` override for frozen `jgen_forge` (Milestone F) | Yes (`jgen_forge.py` line ~43) |
| GGUF tokenizer synthesis (no HF cache required) | Yes (recent main) |
| Torch-free safetensors path | Yes (recent main) |
| Quantized **runtime** (Q4 keep) | No — dequant to f16 on convert |
| BitNet / Bonsai / Instella MLA as `ready` | No |
| Hybrid Qwen3.5/3.6 SSM MoE as `ready` | No → lexicon / external |

## Added on this branch (Milestone E.1)

New FFI for a faithful council port (full distribution + embed rows):

- `jcross_engine_topk_distribution` — lm_head softmax top-K `(token_id, prob)`
- `jcross_engine_embedding_row` — `embed_tokens[token_id]` as `f32[hidden]`

Python: `RustBrain.topk_distribution` / `RustBrain.embedding_row` in `verantyx_mind.py`.

C header for Swift bridging: `jcross_engine_glm/jcross_engine.h`.

Rebuild dylib/so after pull:

```bash
cd jcross_engine_glm
cargo build --release --no-default-features   # Linux/CPU
# or default features on macOS Metal
```

Copy `target/release/libjcross_engine_glm.dylib` (or `.so`) into the IDE `Vendor/`.

## Correction for the plan’s Milestone C note

Python `CortexMemory` **stores** PromptEOL vectors from `encode`, but recall into
chat/speak is primarily **text** (`memory_hits`), not residual injection.
True `encode_soft` / `inject_at_layer` memory injection is a separate path
(council / think blend), matching the plan’s corrected Milestone C wording.

## Tokenizer after Ollama convert

Not extracted from Ollama. Order: `--tokenizer` → HF cache vocab match →
GGUF-synthesized HF tokenizer dir → `.vocab.json` sidecar.
