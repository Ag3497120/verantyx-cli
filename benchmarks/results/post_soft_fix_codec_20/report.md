# Codec Reconstruction Suite

- elapsed_s: 3.4
- model: `/Users/motonishikoudai/Projects/verantyx-cli/converted_models/qwen2_5_0_5b_router_full.jgen`
- corpus: `/Users/motonishikoudai/Projects/verantyx-cli/benchmarks/datasets/codec_propositions.jsonl`
- max_items: 20
- layers: []

## Claim boundary

- Measures hidden-state Read/Write reconstruction only — not LongMemEval QA.
- Keyword / label overlap is a coarse heuristic, not BABEL-style 100% reconstruction.
- Soft inject is a semi-codec (vocab-distribution interlingua), not a lossless inverse.
- Mid-layer scores require encode_layers / inject_at_layer FFI (rebuild jcross_engine_glm).
- C_valve Identity is unrelated to codec completion.
- Codec APIs are for control research; safety-bypass / jailbreak use is out of scope.
- lexicon_only and forward_roundtrip are separate gates — do not conflate them.
- NOT an accuracy booster for council/router QA; NOT BABEL parity.

## Gate: lexicon_only

- Write→Read reproduce: 100.0% (20/20) pass=True
- hold_acc: 85.1% (soft=25.7%, domain=83.2%, n_hold=101)
```json
{
  "n": 20,
  "rate": 1.0,
  "ci95": [
    0.8388698745050667,
    1.0
  ],
  "correct": 20,
  "gate_pass": true,
  "by_domain": {
    "attribute": {
      "n": 8,
      "rate": 1.0
    },
    "factual": {
      "n": 6,
      "rate": 1.0
    },
    "relation": {
      "n": 6,
      "rate": 1.0
    }
  }
}
```

## Gate: forward_roundtrip

### final_soft

```json
{
  "n": 20,
  "rate": 0.55,
  "ci95": [
    0.3420820083075997,
    0.7418049791429071
  ],
  "correct": 11,
  "soft_keyword_hit_rate": 0.55,
  "soft_keyword_hit_ci95": [
    0.3420820083075997,
    0.7418049791429071
  ],
  "read_keyword_hit_rate": 0.9,
  "hybrid_ok_rate": 0.75,
  "mean_roundtrip_cos": 0.36520496010780334,
  "p50_roundtrip_cos": 0.3903728723526001
}
```

### forward_read

```json
{
  "n": 20,
  "rate": 0.95,
  "ci95": [
    0.7638641064874331,
    0.9911187805671268
  ],
  "correct": 19
}
```

### write_forward_read

```json
{
  "n": 20,
  "rate": 1.0,
  "ci95": [
    0.8388698745050667,
    1.0
  ],
  "correct": 20,
  "keyword_rate": 1.0,
  "by_write_path": {
    "lexicon": {
      "n": 20,
      "rate": 1.0
    }
  }
}
```

