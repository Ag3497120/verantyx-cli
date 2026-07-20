# Verantyx Benchmark Report

- 実行: 20260720_113036
- データセット: `benchmarks/datasets/numeric_logic_focus.jsonl` (26 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| company | **57.7%** [39.0–74.5] | 15/26 | 34.3s / 16.0s / 76.2s | 0.00 | 100% (1回) | 2.7GB |
| solo | **100.0%** [87.1–100.0] | 26/26 | 8.1s / 4.3s / 11.1s | 0.00 | — | 2.7GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | logic | numeric |
|---|---|---|---|
| company | 67% (4/6) | 50% (3/6) | 57% (8/14) |
| solo | 100% (6/6) | 100% (6/6) | 100% (14/14) |

## 誤答一覧

- `numeric_0053` [company] 期待=`795` → `Q: What is 482 plus 313?  →  A: Brief — task=default blend=memory:0.25,consensus:0.45,web:0.15,peer:0.15 purpose=speak l`
- `numeric_0067` [company] 期待=`1295` → `The sum of 37 multiplied by 35 is 14,250.

What is 37 multiplied by 35
The sum of 37 multiplied by 35 is 14,250.`
- `numeric_0116` [company] 期待=`132` → `The total amount you pay in total is $39 x 3 = $117.`
- `numeric_0119` [company] 期待=`53` → `The total amount you pay in total is $49. The discount coupon reduces the total amount by $49.

The total amount you pay`
- `numeric_0136` [company] 期待=`9:15pm` → `The train arrives at 8pm.

B
The train arrives at 9pm.
B
The train arrives at 10pm.
B
The train arrives at 11pm.
B
The t`
- `numeric_0141` [company] 期待=`10:00pm` → `The train arrives at 10:00.

B
The train arrives at 11:00.
B
The train arrives at 12:00.
B
The train arrives at 13:00.
B`
- `logic_0012` [company] 期待=`Kate` → `The youngest person is Grace, who is 0.0…`
- `logic_0034` [company] 期待=`Ivy` → `The tallest person is Paul, who is taller than both Mia and Quinn.


Final answer: Paul is the tallest person.`
- `logic_0038` [company] 期待=`Charlie` → `The oldest person is not specified in the given context.`
- `fact_0036` [company] 期待=`Rabat` → `The capital of Morocco is Cas.`
- `fact_0047` [company] 期待=`Kuala Lumpur` → `Malaysia's capital is Kuala.`
