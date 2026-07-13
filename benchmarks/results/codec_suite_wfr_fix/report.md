# Codec Reconstruction Suite

- elapsed_s: 3.4
- model: `/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen`
- corpus: `/Users/motonishikoudai/verantyx-cli/benchmarks/datasets/codec_propositions.jsonl`
- max_items: 9
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

- Write→Read reproduce: 100.0% (9/9) pass=True
- hold_acc: 88.1% (soft=22.8%, domain=86.1%, n_hold=101)
```json
{
  "n": 9,
  "rate": 1.0,
  "ci95": [
    0.7008472464490407,
    1.0
  ],
  "correct": 9,
  "gate_pass": true,
  "by_domain": {
    "attribute": {
      "n": 3,
      "rate": 1.0
    },
    "factual": {
      "n": 3,
      "rate": 1.0
    },
    "relation": {
      "n": 3,
      "rate": 1.0
    }
  }
}
```

## Gate: forward_roundtrip

### final_soft

```json
{
  "n": 9,
  "rate": 0.0,
  "ci95": [
    0.0,
    0.2991527535509594
  ],
  "correct": 0,
  "soft_keyword_hit_rate": 0.0,
  "soft_keyword_hit_ci95": [
    0.0,
    0.2991527535509594
  ],
  "read_keyword_hit_rate": 0.0,
  "hybrid_ok_rate": 0.5555555555555556,
  "mean_roundtrip_cos": 0.6675300465689765,
  "p50_roundtrip_cos": 0.6602339744567871
}
```

### forward_read

```json
{
  "n": 9,
  "rate": 0.0,
  "ci95": [
    0.0,
    0.2991527535509594
  ],
  "correct": 0
}
```

### write_forward_read

```json
{
  "n": 9,
  "rate": 1.0,
  "ci95": [
    0.7008472464490407,
    1.0
  ],
  "correct": 9,
  "keyword_rate": 1.0,
  "by_write_path": {
    "lexicon": {
      "n": 9,
      "rate": 1.0
    }
  }
}
```

