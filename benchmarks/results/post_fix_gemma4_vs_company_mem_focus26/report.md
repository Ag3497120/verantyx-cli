# Verantyx Benchmark Report

- 実行: 20260720_135336
- データセット: `benchmarks/datasets/numeric_logic_focus.jsonl` (26 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| company | **80.8%** [62.1–91.5] | 21/26 | 15.2s / 2.4s / 47.7s | 0.00 | 100% (1回) | 4.3GB |
| solo | **100.0%** [87.1–100.0] | 26/26 | 4.4s / 2.5s / 8.7s | 0.00 | — | 3.4GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | logic | numeric |
|---|---|---|---|
| company | 67% (4/6) | 83% (5/6) | 86% (12/14) |
| solo | 100% (6/6) | 100% (6/6) | 100% (14/14) |

## 誤答一覧

- `numeric_0136` [company] 期待=`9:15pm` → `75`
- `numeric_0141` [company] 期待=`10:00pm` → `75`
- `logic_0012` [company] 期待=`Kate` → `The youngest is Grace, who is 92% of the total population.

The answer is Grace.`
- `fact_0036` [company] 期待=`Rabat` → `Morocco's capital is Cas.`
- `fact_0047` [company] 期待=`Kuala Lumpur` → `Malaysia's capital is Kuala.`
