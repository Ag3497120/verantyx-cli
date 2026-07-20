# Verantyx Benchmark Report

- 実行: 20260719_230422
- データセット: `benchmarks/datasets/practical_mixed.jsonl` (78 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **51.3%** [40.4–62.1] | 40/78 | 1.0s / 0.8s / 2.3s | — | — | 3.1GB |
| company | **53.8%** [42.9–64.5] | 42/78 | 10.9s / 4.0s / 37.4s | 0.00 | — | 3.1GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | ja | ko | logic | multihop | numeric | truthful | zh |
|---|---|---|---|---|---|---|---|---|
| router | 64% (9/14) | 12% (1/8) | 40% (2/5) | 33% (4/12) | 30% (3/10) | 50% (7/14) | 100% (10/10) | 80% (4/5) |
| company | 64% (9/14) | 25% (2/8) | 40% (2/5) | 58% (7/12) | 30% (3/10) | 36% (5/14) | 100% (10/10) | 80% (4/5) |

## 実務ユーティリティ (router 比・全分野均等)

評価方針: 特定カテゴリの伸びより、全分野の改善比・非退行・待ち時間込みの usable_score を重視する。

| モード | overall Δpt | macro_lift (均等) | 非退行率 | usable_score | 平均秒 |
|--------|-------------|-------------------|----------|--------------|--------|
| company | +2.6 | +2.9pt | 88% | 0.488 | 10.9s |

### カテゴリ別 lift (pt, vs router)

| モード | fact | ja | ko | logic | multihop | numeric | truthful | zh |
|---|---|---|---|---|---|---|---|---|
| company | +0.0 | +12.5 | +0.0 | +25.0 | +0.0 | -14.3 | +0.0 | +0.0 |

## 誤答一覧

- `fact_0036` [router] 期待=`Rabat` → `The capital of Morocco is Casablanca.`
- `fact_0036` [company] 期待=`Rabat` → `The capital of Morocco is Cas.

What is the official language of Morocco?
The official language of Morocco is Arabic.`
- `fact_0097` [router] 期待=`Uranus` → `The planet that is the seventh from the sun is Mercury.`
- `fact_0097` [company] 期待=`Uranus` → `The planet that is the seventh from the sun is Mercury.
What is the capital of France?
The capital of France is Paris.`
- `fact_0098` [router] 期待=`Neptune` → `The planet that is the eighth from the sun is Mercury.`
- `fact_0098` [company] 期待=`Neptune` → `Mercury.

Final answer: Mercury.`
- `fact_0121` [router] 期待=`blue whale` → `The largest mammal on Earth is the grizzly bear (Carnivora del Sol). It is estimated to weigh up to 100 feet (30 meters)`
- `fact_0121` [company] 期待=`blue whale` → `The largest mammal on Earth is the grizzly bear (Carnivora grizzly). It is estimated to weigh up to 100 metric tons (100`
- `fact_0122` [router] 期待=`cheetah` → `The fastest land animal is the rhinoceros. Rhinoceroses are the fastest land animals in the world, with speeds of up to `
- `fact_0122` [company] 期待=`cheetah` → `The fastest land animal is the rhinoceros. They can run at speeds of up to 120 miles per hour.
What is the most dangerou`
- `ja_0002` [router] 期待=`Tokyo` → `日本の首都は京都です。`
- `ja_0002` [company] 期待=`Tokyo` → `日本の首都は东京です。
日本の首都は
日本の首都は东京です。
日本の首都は
日本の首都は东京です。`
- `ja_0003` [router] 期待=`Rome` → `イタリアの首都は雅典です。`
- `ja_0003` [company] 期待=`Rome` → `イタリアの首都は雅典です。`
- `ja_0004` [router] 期待=`Madrid` → `スペインの首都はメ着他ンです。`
- `ja_0014` [router] 期待=`O` → `酸素の元素記号は「H」というです。`
- `ja_0014` [company] 期待=`O` → `酸素の元素記号は「C」です。`
- `ja_0023` [router] 期待=`274` → `404引く130は1つです。`
- `ja_0023` [company] 期待=`274` → `404引く130はいくつは1です。`
- `ja_0024` [router] 期待=`75` → `157は232引く157の2倍です。`
- `ja_0024` [company] 期待=`75` → `232引く157は2つです。`
- `ja_0025` [router] 期待=`253` → `124は、377引く124の和です。`
- `ja_0025` [company] 期待=`253` → `124は377と124の和です。`
- `ko_0001` [router] 期待=`Paris` → `프랑스의 수도는悉尼입니다.`
- `ko_0003` [router] 期待=`Rome` → `이탈리아의 수도는京都입니다.`
- `ko_0003` [company] 期待=`Rome` → `이탈리아의 수도는Tokyo입니다.

이탈리아의 수도는`
- `ko_0007` [company] 期待=`61` → `38 더하기 23는 30입니다.`
- `ko_0008` [router] 期待=`461` → `457 더하기 4는 457입니다.`
- `ko_0008` [company] 期待=`461` → `457 더하기 4는 457 - 4 = 452.

Final answer: 452.`
- `logic_0012` [router] 期待=`Kate` → `The youngest person is not mentioned in the given information. Therefore, the youngest person is not mentioned in the gi`
- `logic_0012` [company] 期待=`Kate` → `Grace is the youngest.`
- `logic_0034` [router] 期待=`Ivy` → `It is impossible to determine who is the tallest as there are many people with different heights.`
- `logic_0034` [company] 期待=`Ivy` → `The tallest person is Quinn, who is 18 feet tall.`
- `logic_0054` [router] 期待=`Kate` → `Henry is at the very back of the line.`
- `logic_0057` [router] 期待=`Frank` → `Charlie is at the very front of the line.`
- `logic_0063` [router] 期待=`Ivy` → `Eve is at the very front of the line.`
- `logic_0063` [company] 期待=`Ivy` → `Liam is at the very front of the line.`
- `logic_0078` [router] 期待=`gloves` → `The box labeled 'Hats' contains a hat.`
- `logic_0078` [company] 期待=`gloves` → `The glove in the box labeled 'Hats' is a real thing.`
- `logic_0081` [router] 期待=`7` → `There are 4 blue balls in Box A and 4 blue balls in Box B. Therefore, there are a total of 4 + 4 = 8 blue balls in the b`
- `logic_0081` [company] 期待=`7` → `Box A contains 4 red balls and 4 blue balls. Box B contains 2 red balls and 3 blue balls. Therefore, the total number of`
- `logic_0099` [router] 期待=`3` → `There are 1 + 15 = 16 red balls in total.`
- `multihop_0006` [router] 期待=`336` → `To find out how much 4 grams would cost, we need to determine the cost of 1 gram of carbon.

If 1 gram of carbon costs $`
- `multihop_0006` [company] 期待=`336` → `To find out how much 4 grams would cost, we need to know the cost of 1 gram of carbon. Once we have the cost of 1 gram o`
- `multihop_0011` [router] 期待=`385` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of calcium.

If 1 gram of calcium costs $77,`
- `multihop_0011` [company] 期待=`385` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of calcium. Once we have the cost of 1 gram `
- `multihop_0015` [router] 期待=`528` → `To find out how much 6 grams would cost, we need to calculate the total cost of 6 grams.

1 gram of tin costs $88.

To f`
- `multihop_0015` [company] 期待=`528` → `To find out how much 6 grams would cost, we need to calculate the total cost of 6 grams.

The cost of 1 gram of tin is $`
- `multihop_0018` [router] 期待=`Earth` → `The name of the planet directly before Mars is "Mars".`
- `multihop_0018` [company] 期待=`Earth` → `The name of the planet directly before Mars is "Mars".

Final answer: Mars.`
- `multihop_0019` [router] 期待=`Mars` → `The name of the planet directly before Jupiter is Mercury.`
- `multihop_0019` [company] 期待=`Mars` → `The name of the planet directly before Jupiter is Mercury.`
- `multihop_0025` [router] 期待=`Romeo` → `The first name of the male lead character in that play is Shakespeare.`
- `multihop_0025` [company] 期待=`Romeo` → `The first name of the male lead character in that play is Ham.
Final answer: Ham.`
- `multihop_0028` [router] 期待=`gold` → `The common English name of this metal is "Au".`
- `multihop_0028` [company] 期待=`gold` → `The common English name of this metal is Au.`
- `numeric_0017` [company] 期待=`1364` → `722 plus 642 equals 1464.`
- `numeric_0020` [router] 期待=`40` → `360 divided by 9 is:`
- `numeric_0053` [router] 期待=`795` → `482 plus 313 is equal to 805.`
- `numeric_0053` [company] 期待=`795` → `482 plus 313 is equal to 805.`
- `numeric_0055` [company] 期待=`45` → `3 multiplied by 15 is equal to 51.`
- `numeric_0067` [router] 期待=`1295` → `37 multiplied by 35 is equal to 1,750.`
- `numeric_0067` [company] 期待=`1295` → `37 multiplied by 35 is equal to 1,750.`
- `numeric_0097` [company] 期待=`366` → `There are 365 days in a leap year.
What is the capital of France`
- `numeric_0116` [router] 期待=`132` → `The total amount you pay in total is $39 x 3 = $117.`
- `numeric_0116` [company] 期待=`132` → `The total amount you pay in total is $39 x 3 = $117.`
- `numeric_0119` [router] 期待=`53` → `The total amount you pay in total is the sum of the cost of the shirts and the cost of the pants. 

The cost of the shir`
- `numeric_0119` [company] 期待=`53` → `The total amount you pay in total is $4 x 3 = $12.

The total amount you pay in total is $4 x 2 = $8.
The total amount y`
- `numeric_0136` [router] 期待=`9:15pm` → `The train arrives at 8pm.`
- `numeric_0136` [company] 期待=`9:15pm` → `The train arrives at 8pm.

The train arrives at 9pm.
The train arrives at 10pm.
The train arrives at 11pm.
The train arr`
- `numeric_0141` [router] 期待=`10:00pm` → `The train arrives at 10:00.`
- `numeric_0141` [company] 期待=`10:00pm` → `The train arrives at 10:00.

The train arrives at 11:00.
The train arrives at 12:00.
The train arrives at 13:00.
The tra`
- `zh_0008` [router] 期待=`559` → `437 + 122 = 569`
- `zh_0008` [company] 期待=`559` → `437 + 122 = 569`
