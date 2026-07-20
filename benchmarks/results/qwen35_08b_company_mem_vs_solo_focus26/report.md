# Verantyx Benchmark Report

- 実行: 20260720_145225
- データセット: `benchmarks/datasets/numeric_logic_focus.jsonl` (26 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| company | **84.6%** [66.5–93.8] | 22/26 | 2.8s / 1.2s / 15.8s | 0.00 | 100% (1回) | 4.8GB |
| solo | **73.1%** [53.9–86.3] | 19/26 | 1.3s / 0.8s / 2.1s | 0.00 | — | 4.8GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | logic | numeric |
|---|---|---|---|
| company | 83% (5/6) | 83% (5/6) | 86% (12/14) |
| solo | 100% (6/6) | 67% (4/6) | 64% (9/14) |

## 誤答一覧

- `numeric_0017` [solo] 期待=`1364` → `1360`
- `numeric_0116` [solo] 期待=`132` → `You pay $\$93.`
- `numeric_0119` [solo] 期待=`53` → `You pay $\$23$.`
- `numeric_0136` [company] 期待=`9:15pm` → `75`
- `numeric_0136` [solo] 期待=`9:15pm` → `It arrives at 8:45 a.m.`
- `numeric_0141` [company] 期待=`10:00pm` → `75`
- `numeric_0141` [solo] 期待=`10:00pm` → `The train arrives at 8:00 a.m.`
- `logic_0005` [company] 期待=`9` → `8`
- `logic_0005` [solo] 期待=`9` → `The farmer has 8 sheep left.`
- `logic_0052` [solo] 期待=`Eve` → `Jack`
- `fact_0005` [company] 期待=`Berlin` → `Frankfurt`
