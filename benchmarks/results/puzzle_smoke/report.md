# Verantyx Benchmark Report

- 実行: 20260712_101242
- データセット: `/Users/motonishikoudai/verantyx-cli/benchmarks/datasets/factual_qa.jsonl` (2 問)
- ラウンド: auto | エスカレーション: True

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| puzzle | **100.0%** [34.2–100.0] | 2/2 | 1.2s / 1.2s / 1.6s | 0.00 | — | 3.5GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact |
|---|---|
| puzzle | 100% (2/2) |

## 誤答一覧

