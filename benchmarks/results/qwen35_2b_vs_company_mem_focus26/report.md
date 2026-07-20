# Verantyx Benchmark Report

- 実行: 20260720_143441
- データセット: `benchmarks/datasets/numeric_logic_focus.jsonl` (26 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| company | **80.8%** [62.1–91.5] | 21/26 | 15.8s / 1.7s / 52.8s | 0.00 | 100% (1回) | 4.7GB |
| solo | **92.3%** [75.9–97.9] | 24/26 | 3.5s / 2.0s / 17.3s | 0.00 | — | 4.7GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | logic | numeric |
|---|---|---|---|
| company | 67% (4/6) | 83% (5/6) | 86% (12/14) |
| solo | 100% (6/6) | 100% (6/6) | 86% (12/14) |

## 誤答一覧

- `numeric_0017` [solo] 期待=`1364` → `1384`
- `numeric_0136` [company] 期待=`9:15pm` → `75`
- `numeric_0141` [company] 期待=`10:00pm` → `75`
- `numeric_0141` [solo] 期待=`10:00pm` → `10pm`
- `logic_0012` [company] 期待=`Kate` → `The youngest is Grace, who is 92% of the total population.

The answer is Grace.`
- `fact_0036` [company] 期待=`Rabat` → `Morocco's capital is Cas.`
- `fact_0047` [company] 期待=`Kuala Lumpur` → `Malaysia's capital is Kuala.`
