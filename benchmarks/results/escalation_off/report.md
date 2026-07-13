# Verantyx Benchmark Report

- 実行: 20260710_230317
- データセット: `benchmarks/datasets/hard_subset.jsonl` (10 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| council | **80.0%** [49.0–94.3] | 8/10 | 5.6s / 5.1s / 8.8s | 0.90 | 100% (7回) | 7.7GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | logic | multihop |
|---|---|---|
| council | 83% (5/6) | 75% (3/4) |

## 誤答一覧

- `logic_011` [council] 期待=`oranges` → `The box labeled 'Apples' is empty.`
- `multihop_002` [council] 期待=`Earth` → `The planet third from the sun is Venus.`
