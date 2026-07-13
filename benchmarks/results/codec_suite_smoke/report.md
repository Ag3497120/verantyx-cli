# Codec Reconstruction Suite (Phase 4)

- elapsed_s: 235.9
- model: `/Users/motonishikoudai/Verantyx-God-Mode-Space/cli/qwen_0.5b_full.jgen`
- corpus: `/Users/motonishikoudai/verantyx-cli/benchmarks/datasets/codec_propositions.jsonl`
- max_items: 8
- layers: [0, 11, 23]

## Claim boundary

- Measures hidden-state Read/Write reconstruction only — not LongMemEval QA.
- Keyword / label overlap is a coarse heuristic, not BABEL-style 100% reconstruction.
- Soft inject is a semi-codec (vocab-distribution interlingua), not a lossless inverse.
- Mid-layer scores require encode_layers / inject_at_layer FFI (rebuild jcross_engine_glm).
- C_valve Identity is unrelated to codec completion.
- Codec APIs are for control research; safety-bypass / jailbreak use is out of scope.

## Lexicon gate (Phase 2)

- rate: 100.0% (8/8)
- threshold: 70%
- pass: True

## Phase: final

```json
{
  "n": 8,
  "soft_keyword_hit_rate": 0.0,
  "soft_keyword_hit_ci95": [
    0.0,
    0.3244156195108769
  ],
  "read_keyword_hit_rate": 0.0,
  "mean_roundtrip_cos": 0.6543373316526413,
  "p50_roundtrip_cos": 0.6484694480895996
}
```

## Phase: lexicon

```json
{
  "n": 8,
  "reproduce_rate": 1.0,
  "reproduce_ci95": [
    0.6755843804891231,
    1.0
  ],
  "gate_pass": true,
  "by_domain": {
    "factual": {
      "n": 8,
      "rate": 1.0
    }
  }
}
```

## Phase: layer

```json
{
  "by_layer": {
    "0": {
      "n": 8,
      "keyword_hit_rate": 0.0,
      "keyword_hit_ci95": [
        0.0,
        0.3244156195108769
      ],
      "mean_inject_vs_encode_cos": 1.0000000149011612
    },
    "11": {
      "n": 8,
      "keyword_hit_rate": 0.0,
      "keyword_hit_ci95": [
        0.0,
        0.3244156195108769
      ],
      "mean_inject_vs_encode_cos": 1.0000000149011612
    },
    "23": {
      "n": 8,
      "keyword_hit_rate": 0.0,
      "keyword_hit_ci95": [
        0.0,
        0.3244156195108769
      ],
      "mean_inject_vs_encode_cos": 1.0000000149011612
    }
  },
  "by_domain_layer": {
    "factual": {
      "0": 0.0,
      "11": 0.0,
      "23": 0.0
    }
  }
}
```

