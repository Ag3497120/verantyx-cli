# Concept Lexicon Schema

Artifacts produced by `concept_lexicon_trainer.py` / `ConceptLexicon.save`.

## Files

| Path | Role |
|------|------|
| `.verantyx_chrono/concept_lexicon.npz` | Vectors + labels (binary) |
| `.verantyx_chrono/concept_lexicon.meta.json` | Human-readable train metadata |
| `.verantyx_chrono/codec_layer_routing.json` | Optional L3 domain→inject layer map |

## `concept_lexicon.npz` arrays

| Key | Dtype / shape | Meaning |
|-----|---------------|---------|
| `mu` | `float32 [H]` | Mean PromptEOL embedding (centering) |
| `vectors` | `float32 [N, H]` | μ-centered L2-unit directions (primary NN space) |
| `dirs` | `float32 [N, H]` | Alias of `vectors` (compat) |
| `raw` | `float32 [N, H]` | Uncentered L2-unit PromptEOL vectors |
| `labels` | `object [N]` | Short English proposition strings |
| `domains` | `object [N]` | `factual` / `attribute` / `relation` |
| `ids` | `object [N]` | Stable ids (`p001` …) |
| `train_acc` | scalar float | Self-NN accuracy on train indices |
| `hold_acc` | scalar float | Holdout NN soft/domain match rate (gate) |

`H` is model hidden size (1024 for Qwen2.5-0.5B router).

## `concept_lexicon.meta.json` fields

| Field | Meaning |
|-------|---------|
| `n` | Number of concepts |
| `path` | Absolute npz path |
| `train_acc` | Same as npz |
| `hold_acc` | Primary holdout gate metric |
| `hold_acc_soft` | Stricter soft keyword/label match only |
| `hold_domain_acc` | Domain-of-NN accuracy |
| `n_train` / `n_hold` | Split sizes |
| `holdout_ratio` / `holdout_seed` | Stratified holdout params |
| `hold_ids` | Ids held out |
| `near_dup_dropped` | Near-dup scan count (informational) |
| `dedupe_keywords` | Whether keyword dedupe ran |

## Reproduce commands

```bash
# Train lexicon on full corpus (~500 props)
python3 concept_lexicon_trainer.py \
  --corpus benchmarks/datasets/codec_propositions.jsonl \
  --holdout-ratio 0.20 --holdout-seed 42

# Lexicon-only Write→Read gate
python3 concept_lexicon.py --eval --gate 0.70

# Dual-gate suite smoke
python3 benchmarks/codec_suite.py --max-items 20 \
  --inject-ab --save-layer-routing \
  --out benchmarks/results/codec_suite_smoke

# Layer FFI smoke (synthetic model, no GPU)
JCROSS_GPU=0 python3 tests/test_codec_layers.py

# One-command package reproduce
python3 benchmarks/codec_package_reproduce.py --max-items 20
```

## Claim boundary

- `hold_acc` / `lexicon_only` ≠ BABEL reconstruction accuracy
- `forward_roundtrip` soft/keyword rates are coarse heuristics
- Not an accuracy booster for LongMemEval / council QA
