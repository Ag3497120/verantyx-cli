# Verantyx Benchmark Report

- 実行: 20260712_230906
- データセット: `benchmarks/datasets/hard_elevated.jsonl` (15 問)
- ラウンド: 2 | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **46.7%** [24.8–69.9] | 7/15 | 8.2s / 1.5s / 36.1s | — | — | 3.3GB |
| council_div | **60.0%** [35.8–80.2] | 9/15 | 4.8s / 2.5s / 13.2s | 0.00 | 80% (5回) | 3.3GB |
| puzzle_div | **33.3%** [15.2–58.3] | 5/15 | 9.3s / 2.6s / 39.3s | 0.00 | — | 3.3GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | logic | multihop |
|---|---|---|
| router | 33% (2/6) | 56% (5/9) |
| council_div | 50% (3/6) | 67% (6/9) |
| puzzle_div | 33% (2/6) | 33% (3/9) |

## 誤答一覧

- `logic_005` [router] 期待=`5` → `Let's denote the cost of the ball as b. 

The bat costs $1.00 more than the ball. Therefore, the cost of the bat is b + `
- `logic_005` [council_div] 期待=`5` → `Let's denote the cost of the ball as b. 

The bat costs $1.00 more than the ball. Therefore, the cost of the bat is b + `
- `logic_005` [puzzle_div] 期待=`5` → `Let's denote the cost of the ball as b. 

The bat costs $1.00 more than the ball. Therefore, the cost of the bat is b + `
- `logic_006` [router] 期待=`14` → `Let's denote the number of apples Ben has as B. 

The problem states that Ben has 10 apples. 

The problem also states t`
- `logic_006` [council_div] 期待=`14` → `Let's denote the number of apples Tom has as T. 

The problem states that Ben has 10 apples. 

The problem also states t`
- `logic_006` [puzzle_div] 期待=`14` → `Let's denote the number of apples Tom has as T. 

The problem states that Ben has 10 apples. 

The problem also states t`
- `logic_011` [puzzle_div] 期待=`oranges` → `The box labeled 'Apples' contains apples.`
- `logic_017` [router] 期待=`15` → `Sam spends 40% on food, which is 0.4 * $50 = $20
After spending on food, Sam has $50 - $20 = $30 left.
#### 30`
- `logic_017` [council_div] 期待=`15` → `Sam spends 40% on food, which is 0.4 * $50 = $20
After spending on food, Sam has $50 - $20 = $30 left.
#### 30`
- `logic_017` [puzzle_div] 期待=`15` → `Sam spends 40% on food, which is 0.4 * $50 = $20
After spending on food, Sam has $50 - $20 = $30 left.
#### 30`
- `multihop_001` [puzzle_div] 期待=`Paris` → `The capital city of that country is Lyon.`
- `multihop_002` [router] 期待=`Earth` → `The name of the planet third from the sun is "Mars".`
- `multihop_002` [council_div] 期待=`Earth` → `The name of the planet third from the sun is Mercury.`
- `multihop_002` [puzzle_div] 期待=`Earth` → `The name of the planet third from the sun is Mercury.`
- `multihop_005` [router] 期待=`Pacific` → `The largest ocean on Earth borders the country famous for Mount Fuji. What is the name of that ocean?`
- `multihop_005` [council_div] 期待=`Pacific` → `The answer is the Atlantic Ocean.`
- `multihop_005` [puzzle_div] 期待=`Pacific` → `The answer is the Atlantic Ocean.`
- `logic_020` [router] 期待=`5` → `To solve this problem, we need to find the relationship between the number of machines and the number of widgets.

We ca`
- `multihop_0010` [puzzle_div] 期待=`156` → `To find the cost of 3 grams of potassium, we can use the concept of cost per unit.

First, let's find the cost per gram `
- `multihop_0004` [router] 期待=`420` → `To find the cost of 5 grams of oxygen, we can use the concept of cost per unit.

First, let's find the cost per gram of `
- `multihop_0004` [puzzle_div] 期待=`420` → `To find the cost of 5 grams of oxygen, we can use the concept of cost per unit.

First, let's find the cost per gram of `
- `multihop_0005` [router] 期待=`300` → `To find the cost of 5 grams of hydrogen, we can use the concept of cost per unit.

First, let's find the cost per gram o`
- `multihop_0005` [council_div] 期待=`300` → `To find the cost of 5 grams of hydrogen, we can use the concept of cost per unit.

First, we need to find the cost per g`
- `multihop_0005` [puzzle_div] 期待=`300` → `To find the cost of 5 grams of hydrogen, we can use the concept of cost per unit.

First, let's find the cost per gram o`
