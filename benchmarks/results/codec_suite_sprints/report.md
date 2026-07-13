# Codec Reconstruction Suite

- elapsed_s: 1407.0
- model: `/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen`
- corpus: `/Users/motonishikoudai/verantyx-cli/benchmarks/datasets/codec_propositions.jsonl`
- max_items: 20
- layers: [0, 6, 12, 18, 23]

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
- hold_acc: 88.1% (soft=22.8%, domain=86.1%, n_hold=101)
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
    "factual": {
      "n": 20,
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
  "read_keyword_hit_rate": 0.05,
  "hybrid_ok_rate": 0.7,
  "mean_roundtrip_cos": 0.6531547248363495,
  "p50_roundtrip_cos": 0.6484694480895996
}
```

### forward_read

```json
{
  "n": 20,
  "rate": 0.2,
  "ci95": [
    0.0806563532712,
    0.41602172202575993
  ],
  "correct": 4
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
    "rate": 0.05,
    "ci95": [
      0.008881219432873136,
      0.23613589351256675
    ],
    "correct": 1
  },
  "late": {
    "n": 20,
    "rate": 0.05,
    "ci95": [
      0.008881219432873136,
      0.23613589351256675
    ],
    "correct": 1
  },
  "mid": {
    "n": 20,
    "rate": 0.05,
    "ci95": [
      0.008881219432873136,
      0.23613589351256675
    ],
    "correct": 1
  }
}
```

### layer

```json
{
  "by_layer": {
    "0": {
      "n": 20,
      "keyword_hit_rate": 0.05,
      "keyword_hit_ci95": [
        0.008881219432873136,
        0.23613589351256675
      ],
      "mean_inject_vs_encode_cos": 1.0000000089406966
    },
    "6": {
      "n": 20,
      "keyword_hit_rate": 0.05,
      "keyword_hit_ci95": [
        0.008881219432873136,
        0.23613589351256675
      ],
      "mean_inject_vs_encode_cos": 1.0000000089406966
    },
    "12": {
      "n": 20,
      "keyword_hit_rate": 0.05,
      "keyword_hit_ci95": [
        0.008881219432873136,
        0.23613589351256675
      ],
      "mean_inject_vs_encode_cos": 1.0000000089406966
    },
    "18": {
      "n": 20,
      "keyword_hit_rate": 0.05,
      "keyword_hit_ci95": [
        0.008881219432873136,
        0.23613589351256675
      ],
      "mean_inject_vs_encode_cos": 1.0000000089406966
    },
    "23": {
      "n": 20,
      "keyword_hit_rate": 0.05,
      "keyword_hit_ci95": [
        0.008881219432873136,
        0.23613589351256675
      ],
      "mean_inject_vs_encode_cos": 1.0000000089406966
    }
  },
  "by_domain_layer": {
    "factual": {
      "0": 0.05,
      "6": 0.05,
      "12": 0.05,
      "18": 0.05,
      "23": 0.05
    }
  }
}
```

## L3 suggested domain→layer routing

```json
{
  "factual": 0
}
```

