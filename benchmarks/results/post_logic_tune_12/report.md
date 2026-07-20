# Verantyx Benchmark Report

- 実行: 20260720_130823
- データセット: `benchmarks/datasets/logic_only_12.jsonl` (12 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **33.3%** [13.8–60.9] | 4/12 | 0.8s / 0.6s / 1.4s | — | — | 3.1GB |
| company | **58.3%** [31.9–80.7] | 7/12 | 12.8s / 4.9s / 31.2s | 0.00 | — | 3.1GB |
| puzzle | **50.0%** [25.4–74.6] | 6/12 | 2.2s / 1.8s / 4.1s | 0.00 | — | 3.4GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | logic |
|---|---|
| router | 33% (4/12) |
| company | 58% (7/12) |
| puzzle | 50% (6/12) |

## 実務ユーティリティ (router 比・全分野均等)

評価方針: 特定カテゴリの伸びより、全分野の改善比・非退行・待ち時間込みの usable_score を重視する。

| モード | overall Δpt | macro_lift (均等) | 非退行率 | usable_score | 平均秒 |
|--------|-------------|-------------------|----------|--------------|--------|
| company | +25.0 | +25.0pt | 100% | 0.507 | 12.8s |
| puzzle | +16.7 | +16.7pt | 100% | 0.500 | 2.2s |

### カテゴリ別 lift (pt, vs router)

| モード | logic |
|---|---|
| company | +25.0 |
| puzzle | +16.7 |

## 誤答一覧

- `logic_0012` [router] 期待=`Kate` → `The youngest person is not mentioned in the given information. Therefore, the youngest person is not mentioned in the gi`
- `logic_0012` [company] 期待=`Kate` → `Grace is the youngest.`
- `logic_0034` [router] 期待=`Ivy` → `It is impossible to determine who is the tallest as there are many people with different heights.`
- `logic_0034` [company] 期待=`Ivy` → `The tallest person is Paul, who is taller than Quinn.








The tallest person
is Paul, who is taller than Quinn.`
- `logic_0034` [puzzle] 期待=`Ivy` → `The tallest person is Paul, who is taller than Mia.`
- `logic_0054` [router] 期待=`Kate` → `Henry is at the very back of the line.`
- `logic_0054` [puzzle] 期待=`Kate` → `Henry is at the very back of the line.`
- `logic_0057` [router] 期待=`Frank` → `Charlie is at the very front of the line.`
- `logic_0057` [puzzle] 期待=`Frank` → `Charlie is at the very front of the line.`
- `logic_0063` [router] 期待=`Ivy` → `Eve is at the very front of the line.`
- `logic_0063` [company] 期待=`Ivy` → `Liam is at the very front of the line.`
- `logic_0063` [puzzle] 期待=`Ivy` → `Liam is at the very front of the line.`
- `logic_0078` [router] 期待=`gloves` → `The box labeled 'Hats' contains a hat.`
- `logic_0078` [company] 期待=`gloves` → `The glove in the box labeled 'Hats' is a real thing.`
- `logic_0078` [puzzle] 期待=`gloves` → `The box labeled 'Hats' contains a hat.`
- `logic_0081` [router] 期待=`7` → `There are 4 blue balls in Box A and 4 blue balls in Box B. Therefore, there are a total of 4 + 4 = 8 blue balls in the b`
- `logic_0081` [company] 期待=`7` → `Box A contains 4 red balls and 4 blue balls. Box B contains 2 red balls and 3 blue balls. Therefore, the total number of`
- `logic_0081` [puzzle] 期待=`7` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0099` [router] 期待=`3` → `There are 1 + 15 = 16 red balls in total.`
