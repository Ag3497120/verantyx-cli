# Codec Reconstruction Suite

- elapsed_s: 239.9
- model: `/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen`
- corpus: `/Users/motonishikoudai/verantyx-cli/benchmarks/datasets/codec_propositions.jsonl`
- max_items: 6
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

- Write→Read reproduce: 100.0% (6/6) pass=True
- hold_acc: 88.1% (soft=22.8%, domain=86.1%, n_hold=101)
```json
{
  "n": 6,
  "rate": 1.0,
  "ci95": [
    0.6096569663469354,
    0.9999999999999999
  ],
  "correct": 6,
  "gate_pass": true,
  "by_domain": {
    "attribute": {
      "n": 2,
      "rate": 1.0
    },
    "factual": {
      "n": 2,
      "rate": 1.0
    },
    "relation": {
      "n": 2,
      "rate": 1.0
    }
  }
}
```

## Gate: forward_roundtrip

### final_soft

```json
{
  "n": 6,
  "rate": 0.0,
  "ci95": [
    0.0,
    0.3903430336530645
  ],
  "correct": 0,
  "soft_keyword_hit_rate": 0.0,
  "soft_keyword_hit_ci95": [
    0.0,
    0.3903430336530645
  ],
  "read_keyword_hit_rate": 0.0,
  "hybrid_ok_rate": 0.6666666666666666,
  "mean_roundtrip_cos": 0.6697337428728739,
  "p50_roundtrip_cos": 0.6602168083190918
}
```

### forward_read

```json
{
  "n": 6,
  "rate": 0.0,
  "ci95": [
    0.0,
    0.3903430336530645
  ],
  "correct": 0
}
```

### write_forward_read

```json
{
  "n": 6,
  "rate": 0.3333333333333333,
  "ci95": [
    0.09676933255921683,
    0.7000116786584712
  ],
  "correct": 2,
  "keyword_rate": 0.3333333333333333,
  "by_write_path": {
    "lexicon": {
      "n": 6,
      "rate": 0.3333333333333333
    }
  }
}
```

