# Verantyx Benchmark Report

- 実行: 20260712_101409
- データセット: `/Users/motonishikoudai/verantyx-cli/benchmarks/datasets/factual_qa.jsonl` (30 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **93.3%** [78.7–98.2] | 28/30 | 0.9s / 0.3s / 1.9s | — | — | 3.3GB |
| council | **93.3%** [78.7–98.2] | 28/30 | 2.0s / 1.8s / 4.4s | 0.00 | 82% (28回) | 3.3GB |
| puzzle | **93.3%** [78.7–98.2] | 28/30 | 1.5s / 1.4s / 3.0s | 0.00 | — | 3.3GB |

## モード間の差分 (評議会の価値)

- council − router: **+0.0 pt** (信頼区間が重なる場合は有意差なしと解釈すること)

## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact |
|---|---|
| router | 93% (28/30) |
| council | 93% (28/30) |
| puzzle | 93% (28/30) |

## 誤答一覧

- `fact_004` [router] 期待=`Mars` → `Jupiter`
- `fact_025` [router] 期待=`11` → `There are 32 players on a standard soccer team on the field.`
- `fact_025` [council] 期待=`11` → `There are 32 players on a standard soccer team on the field.`
- `fact_025` [puzzle] 期待=`11` → `There are 32 players on a standard soccer team on the field.`
- `fact_028` [council] 期待=`63` → `To solve this problem, we need to follow these steps:

1. Write down the given expression: 100 minus 37.

2. Simplify th`
- `fact_028` [puzzle] 期待=`63` → `To solve this problem, we need to follow these steps:

1. Write down the given expression: 100 minus 37.

2. Simplify th`
