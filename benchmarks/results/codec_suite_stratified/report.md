# Codec Reconstruction Suite

- elapsed_s: 410.8
- model: `/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen`
- corpus: `/Users/motonishikoudai/verantyx-cli/benchmarks/datasets/codec_propositions.jsonl`
- max_items: 12
- layers: [0, 11, 23]

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

- Write→Read reproduce: 100.0% (12/12) pass=True
- hold_acc: 88.1% (soft=22.8%, domain=86.1%, n_hold=101)
```json
{
  "n": 12,
  "rate": 1.0,
  "ci95": [
    0.7574992425007574,
    1.0
  ],
  "correct": 12,
  "gate_pass": true,
  "by_domain": {
    "attribute": {
      "n": 4,
      "rate": 1.0
    },
    "factual": {
      "n": 4,
      "rate": 1.0
    },
    "relation": {
      "n": 4,
      "rate": 1.0
    }
  }
}
```

## Gate: forward_roundtrip

### final_soft

```json
{
  "n": 12,
  "rate": 0.0,
  "ci95": [
    0.0,
    0.2425007574992425
  ],
  "correct": 0,
  "soft_keyword_hit_rate": 0.0,
  "soft_keyword_hit_ci95": [
    0.0,
    0.2425007574992425
  ],
  "read_keyword_hit_rate": 0.0,
  "hybrid_ok_rate": 0.5833333333333334,
  "mean_roundtrip_cos": 0.6649849116802216,
  "p50_roundtrip_cos": 0.6602203845977783
}
```

### forward_read

```json
{
  "n": 12,
  "rate": 0.0,
  "ci95": [
    0.0,
    0.2425007574992425
  ],
  "correct": 0
}
```

### write_forward_read

```json
{
  "n": 12,
  "rate": 0.75,
  "ci95": [
    0.46768966087934005,
    0.9110599603710386
  ],
  "correct": 9,
  "keyword_rate": 0.75,
  "by_write_path": {
    "lexicon": {
      "n": 12,
      "rate": 0.75
    }
  }
}
```

### layer

```json
{
  "by_layer": {
    "0": {
      "n": 12,
      "keyword_hit_rate": 0.0,
      "keyword_hit_ci95": [
        0.0,
        0.2425007574992425
      ],
      "mean_inject_vs_encode_cos": 1.0000000198682149
    },
    "11": {
      "n": 12,
      "keyword_hit_rate": 0.0,
      "keyword_hit_ci95": [
        0.0,
        0.2425007574992425
      ],
      "mean_inject_vs_encode_cos": 1.0000000198682149
    },
    "23": {
      "n": 12,
      "keyword_hit_rate": 0.0,
      "keyword_hit_ci95": [
        0.0,
        0.2425007574992425
      ],
      "mean_inject_vs_encode_cos": 1.0000000198682149
    }
  },
  "by_domain_layer": {
    "attribute": {
      "0": 0.0,
      "11": 0.0,
      "23": 0.0
    },
    "factual": {
      "0": 0.0,
      "11": 0.0,
      "23": 0.0
    },
    "relation": {
      "0": 0.0,
      "11": 0.0,
      "23": 0.0
    }
  }
}
```

## L3 suggested domain→layer routing

```json
{
  "attribute": 0,
  "factual": 0,
  "relation": 0
}
```

