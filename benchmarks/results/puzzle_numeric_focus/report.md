# Verantyx Benchmark Report

- 実行: 20260719_233424
- データセット: `benchmarks/datasets/numeric_logic_focus.jsonl` (26 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **61.5%** [42.5–77.6] | 16/26 | 0.8s / 0.6s / 1.5s | — | — | 3.1GB |
| company | **57.7%** [39.0–74.5] | 15/26 | 13.6s / 4.3s / 39.2s | 0.00 | — | 3.2GB |
| puzzle | **53.8%** [35.5–71.2] | 14/26 | 1.7s / 1.6s / 2.6s | 0.00 | — | 3.5GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | logic | numeric |
|---|---|---|---|
| router | 83% (5/6) | 67% (4/6) | 50% (7/14) |
| company | 83% (5/6) | 67% (4/6) | 43% (6/14) |
| puzzle | 67% (4/6) | 83% (5/6) | 36% (5/14) |

## 実務ユーティリティ (router 比・全分野均等)

評価方針: 特定カテゴリの伸びより、全分野の改善比・非退行・待ち時間込みの usable_score を重視する。

| モード | overall Δpt | macro_lift (均等) | 非退行率 | usable_score | 平均秒 |
|--------|-------------|-------------------|----------|--------------|--------|
| company | -3.9 | -2.4pt | 67% | 0.494 | 13.6s |
| puzzle | -7.7 | -4.8pt | 33% | 0.538 | 1.7s |

### カテゴリ別 lift (pt, vs router)

| モード | fact | logic | numeric |
|---|---|---|---|
| company | +0.0 | +0.0 | -7.1 |
| puzzle | -16.7 | +16.7 | -14.3 |

## 誤答一覧

- `numeric_0017` [puzzle] 期待=`1364` → `To find the sum of 722 and 642, you simply add the two numbers together.

So, the sum of 722 and 642 is:`
- `numeric_0020` [router] 期待=`40` → `360 divided by 9 is:`
- `numeric_0053` [router] 期待=`795` → `482 plus 313 is equal to 805.`
- `numeric_0053` [company] 期待=`795` → `482 plus 313 equals 805.`
- `numeric_0053` [puzzle] 期待=`795` → `482 plus 313 is equal to 805.`
- `numeric_0055` [company] 期待=`45` → `3 multiplied by 15 is equal to 51.

What is 3 multiplied by 15`
- `numeric_0067` [router] 期待=`1295` → `37 multiplied by 35 is equal to 1,750.`
- `numeric_0067` [company] 期待=`1295` → `37 multiplied by 35 is equal to 12,750.`
- `numeric_0067` [puzzle] 期待=`1295` → `37 multiplied by 35 is equal to 1,750.`
- `numeric_0097` [company] 期待=`366` → `There are 365 days in a leap year.
What is the capital of France`
- `numeric_0097` [puzzle] 期待=`366` → `There are 365 days in a leap year.`
- `numeric_0116` [router] 期待=`132` → `The total amount you pay in total is $39 x 3 = $117.`
- `numeric_0116` [company] 期待=`132` → `The total amount you pay in total is $39 x 3 = $117.`
- `numeric_0116` [puzzle] 期待=`132` → `To calculate the total amount you pay, you need to add the cost of the shirts and pants, as well as the $3 discount coup`
- `numeric_0119` [router] 期待=`53` → `The total amount you pay in total is the sum of the cost of the shirts and the cost of the pants. 

The cost of the shir`
- `numeric_0119` [company] 期待=`53` → `The total amount you pay in total is $4 x 3 = $12.

The total amount you pay in total is $4 x 2 = $8.
The total amount y`
- `numeric_0119` [puzzle] 期待=`53` → `The total amount you pay in total is the sum of the cost of the shirts and the cost of the pants. 

The cost of the shir`
- `numeric_0124` [puzzle] 期待=`75` → `The car travels a total distance of 50 km + 1.5 hours = 51.5 km.`
- `numeric_0136` [router] 期待=`9:15pm` → `The train arrives at 8pm.`
- `numeric_0136` [company] 期待=`9:15pm` → `The train arrives at 8pm.

The train arrives at 9pm.
The train arrives at 10pm.
The train arrives at 11pm.
The train arr`
- `numeric_0136` [puzzle] 期待=`9:15pm` → `The train arrives at 8pm.`
- `numeric_0141` [router] 期待=`10:00pm` → `The train arrives at 10:00.`
- `numeric_0141` [company] 期待=`10:00pm` → `The train arrives at 10:00.

The train arrives at 11:00.
The train arrives at 12:00.
The train arrives at 13:00.
The tra`
- `numeric_0141` [puzzle] 期待=`10:00pm` → `The train arrives at 10:00 am.`
- `logic_0012` [router] 期待=`Kate` → `The youngest person is not mentioned in the given information. Therefore, the youngest person is not mentioned in the gi`
- `logic_0012` [company] 期待=`Kate` → `Grace is the youngest.`
- `logic_0034` [router] 期待=`Ivy` → `It is impossible to determine who is the tallest as there are many people with different heights.`
- `logic_0034` [company] 期待=`Ivy` → `The tallest person is Paul, who is taller than Mia and Quinn.







The tallest person
is Paul, who is taller than Mia `
- `logic_0034` [puzzle] 期待=`Ivy` → `The tallest person is Paul, who is taller than Mia.`
- `fact_0036` [router] 期待=`Rabat` → `The capital of Morocco is Casablanca.`
- `fact_0036` [company] 期待=`Rabat` → `The capital of Morocco is Cas.

What is the official language of Morocco?
The official language of Morocco is Arabic.`
- `fact_0036` [puzzle] 期待=`Rabat` → `The capital of Morocco is Cas.`
- `fact_0047` [puzzle] 期待=`Kuala Lumpur` → `The capital of Malaysia is Kuala.`
