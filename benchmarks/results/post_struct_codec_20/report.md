# Codec Reconstruction Suite

- elapsed_s: 182.4
- model: `/Users/motonishikoudai/Projects/verantyx-cli/converted_models/qwen2_5_0_5b_router_full.jgen`
- corpus: `/Users/motonishikoudai/Projects/verantyx-cli/benchmarks/datasets/codec_propositions.jsonl`
- max_items: 20
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
  "rate": 0.0,
  "ci95": [
    0.0,
    0.16113012549493322
  ],
  "correct": 0,
  "soft_keyword_hit_rate": 0.0,
  "soft_keyword_hit_ci95": [
    0.0,
    0.16113012549493322
  ],
  "read_keyword_hit_rate": 0.3,
  "hybrid_ok_rate": 0.85,
  "mean_roundtrip_cos": 0.6178360611200333,
  "p50_roundtrip_cos": 0.6144473552703857
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

### inject_ab

```json
{
  "final": {
    "n": 20,
    "rate": 0.3,
    "ci95": [
      0.14547527396899385,
      0.5189767762289793
    ],
    "correct": 6
  },
  "late": {
    "n": 20,
    "rate": 0.3,
    "ci95": [
      0.14547527396899385,
      0.5189767762289793
    ],
    "correct": 6
  },
  "mid": {
    "n": 20,
    "rate": 0.3,
    "ci95": [
      0.14547527396899385,
      0.5189767762289793
    ],
    "correct": 6
  }
}
```

### layer

```json
{
  "by_layer": {
    "0": {
      "n": 20,
      "keyword_hit_rate": 0.3,
      "keyword_hit_ci95": [
        0.14547527396899385,
        0.5189767762289793
      ],
      "mean_inject_vs_encode_cos": 0.9999999970197677
    },
    "11": {
      "n": 20,
      "keyword_hit_rate": 0.3,
      "keyword_hit_ci95": [
        0.14547527396899385,
        0.5189767762289793
      ],
      "mean_inject_vs_encode_cos": 0.9999999970197677
    },
    "23": {
      "n": 20,
      "keyword_hit_rate": 0.3,
      "keyword_hit_ci95": [
        0.14547527396899385,
        0.5189767762289793
      ],
      "mean_inject_vs_encode_cos": 0.9999999970197677
    }
  },
  "by_domain_layer": {
    "attribute": {
      "0": 0.625,
      "11": 0.625,
      "23": 0.625
    },
    "factual": {
      "0": 0.0,
      "11": 0.0,
      "23": 0.0
    },
    "relation": {
      "0": 0.16666666666666666,
      "11": 0.16666666666666666,
      "23": 0.16666666666666666
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

