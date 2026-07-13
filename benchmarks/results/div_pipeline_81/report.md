# Verantyx Benchmark Report

- 実行: 20260712_232251
- データセット: `benchmarks/datasets/hard_elevated.jsonl` (81 問)
- ラウンド: 2 | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **35.8%** [26.2–46.7] | 29/81 | 5.1s / 0.8s / 33.7s | — | — | 3.5GB |
| council_div | **39.5%** [29.6–50.4] | 32/81 | 6.2s / 2.2s / 36.3s | 0.00 | 95% (39回) | 3.5GB |
| puzzle_div | **32.1%** [22.9–42.9] | 26/81 | 8.7s / 1.9s / 36.0s | 0.00 | — | 3.5GB |

## モード間の差分 (評議会の価値)


## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | logic | multihop | truthful |
|---|---|---|---|
| router | 13% (4/31) | 43% (13/30) | 60% (12/20) |
| council_div | 16% (5/31) | 50% (15/30) | 60% (12/20) |
| puzzle_div | 16% (5/31) | 33% (10/30) | 55% (11/20) |

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
- `multihop_0029` [puzzle_div] 期待=`yen` → `The country famous for sushi and Mount Fuji is called Japan.`
- `multihop_0006` [router] 期待=`336` → `To find the cost of 4 grams of carbon, we can use the concept of cost per unit.

First, we need to find the cost per gra`
- `multihop_0006` [council_div] 期待=`336` → `To find the cost of 4 grams of carbon, we can use the concept of cost per unit.

First, we need to find the cost per gra`
- `multihop_0006` [puzzle_div] 期待=`336` → `To find out how much 4 grams of carbon would cost, we can use the following steps:

1. Determine the cost of 1 gram of c`
- `multihop_0018` [router] 期待=`Earth` → `The name of the planet directly before Mars is Mercury.`
- `multihop_0018` [council_div] 期待=`Earth` → `The name of the planet directly before Mars is Mercury.`
- `multihop_0018` [puzzle_div] 期待=`Earth` → `The name of the planet directly before Mars is Mercury.`
- `multihop_0020` [router] 期待=`Jupiter` → `The name of the planet directly before Saturn is Neptune.`
- `multihop_0020` [council_div] 期待=`Jupiter` → `The name of the planet directly before Saturn is Neptune.`
- `multihop_0020` [puzzle_div] 期待=`Jupiter` → `The name of the planet directly before Saturn is Neptune.`
- `multihop_0025` [router] 期待=`Romeo` → `The first name of the male lead character in that play is not mentioned in the question.`
- `multihop_0021` [router] 期待=`Saturn` → `The name of the planet directly before Uranus is Neptune.`
- `multihop_0021` [council_div] 期待=`Saturn` → `The name of the planet directly before Uranus is Neptune.`
- `multihop_0021` [puzzle_div] 期待=`Saturn` → `The name of the planet directly before Uranus is Neptune.`
- `multihop_0015` [router] 期待=`528` → `6 grams of tin would cost $88 * 6 = $552.

Therefore, 6 grams of tin would cost $552.`
- `multihop_0015` [council_div] 期待=`528` → `The cost of 6 grams of tin is $88 * 6 = $552.`
- `multihop_0015` [puzzle_div] 期待=`528` → `6 grams of tin would cost $88 * 6 = $552.`
- `multihop_0001` [puzzle_div] 期待=`40` → `To find out how much 2 grams of gold would cost, we need to first find out how much 1 gram of gold costs. 

We know that`
- `multihop_0003` [router] 期待=`96` → `To find the cost of 3 grams of iron, we can use the following steps:

1. Find the cost of 1 gram of iron.
2. Multiply th`
- `multihop_0003` [council_div] 期待=`96` → `To find the cost of 3 grams of iron, we can use the following steps:

1. Calculate the cost of 1 gram of iron.
2. Multip`
- `multihop_0003` [puzzle_div] 期待=`96` → `To find the cost of 3 grams of iron, we can use the following steps:

1. Calculate the cost of 1 gram of iron.
2. Multip`
- `multihop_0014` [router] 期待=`38` → `To find out how much 2 grams of lead would cost, we can use the following formula:

Cost = (Weight of 1 gram of lead) * `
- `multihop_0014` [council_div] 期待=`38` → `Let's denote the cost of 2 grams of lead as L2. We know that the cost of 1 gram of lead is $19. Therefore, we can set up`
- `multihop_0014` [puzzle_div] 期待=`38` → `Let's denote the cost of 2 grams of lead as L2. We know that the cost of 1 gram of lead is $19. Therefore, we can set up`
- `multihop_0017` [router] 期待=`Venus` → `The name of the planet directly before Earth is Mercury.`
- `multihop_0017` [council_div] 期待=`Venus` → `The name of the planet directly before Earth is Mercury.`
- `multihop_0017` [puzzle_div] 期待=`Venus` → `The name of the planet directly before Earth is Mercury.`
- `multihop_0028` [router] 期待=`gold` → `The common English name of this metal is Au.`
- `multihop_0028` [council_div] 期待=`gold` → `The common English name of this metal is Aluminium.`
- `multihop_0028` [puzzle_div] 期待=`gold` → `The common English name of this metal is Au.`
- `multihop_0012` [router] 期待=`365` → `To find the cost of 5 grams of copper, we can use the following steps:

1. Find the cost of 1 gram of copper.
2. Multipl`
- `multihop_0012` [puzzle_div] 期待=`365` → `To find the cost of 5 grams of copper, we can use the following steps:

1. Find the cost of 1 gram of copper.
2. Multipl`
- `multihop_0019` [router] 期待=`Mars` → `The name of the planet directly before Jupiter is Neptune.`
- `multihop_0019` [council_div] 期待=`Mars` → `The name of the planet directly before Jupiter is Mercury.`
- `multihop_0019` [puzzle_div] 期待=`Mars` → `The name of the planet directly before Jupiter is Mercury.`
- `multihop_0022` [router] 期待=`Uranus` → `The name of the planet directly before Neptune is Neptune.`
- `multihop_0022` [council_div] 期待=`Uranus` → `The name of the planet directly before Neptune is Neptune.`
- `multihop_0022` [puzzle_div] 期待=`Uranus` → `The name of the planet directly before Neptune is Neptune.`
- `multihop_0002` [council_div] 期待=`28` → `14 dollars is equivalent to 14/2 = 7 dollars. Therefore, 2 grams of silver would cost 7 dollars.`
- `logic_0070` [router] 期待=`oranges` → `The box labeled 'Apples' contains apples.`
- `logic_0070` [council_div] 期待=`oranges` → `The box labeled 'Apples' contains apples.`
- `logic_0070` [puzzle_div] 期待=`oranges` → `The box labeled 'Apples' contains apples.`
- `logic_0074` [router] 期待=`magazines` → `The answer is a book.`
- `logic_0074` [council_div] 期待=`magazines` → `The answer is a book.`
- `logic_0074` [puzzle_div] 期待=`magazines` → `The answer is "Books".`
- `logic_0075` [council_div] 期待=`pants` → `The pant is actually a shirt.`
- `logic_0077` [router] 期待=`forks` → `The answer is a knife.`
- `logic_0077` [council_div] 期待=`forks` → `The answer is a fork.`
- `logic_0077` [puzzle_div] 期待=`forks` → `The answer is a fork.`
- `logic_0073` [router] 期待=`stamps` → `The box labeled 'Coins' contains only coins.`
- `logic_0073` [council_div] 期待=`stamps` → `The box labeled 'Coins' contains only coins.`
- `logic_0073` [puzzle_div] 期待=`stamps` → `The box labeled 'Coins' contains only coins.`
- `logic_0072` [router] 期待=`pencils` → `The answer is a pencil.`
- `logic_0072` [council_div] 期待=`pencils` → `The answer is a pencil.`
- `logic_0072` [puzzle_div] 期待=`pencils` → `The answer is a pencil.`
- `logic_0078` [router] 期待=`gloves` → `The box labeled 'Hats' contains hats.`
- `logic_0078` [council_div] 期待=`gloves` → `The box labeled 'Hats' contains hats.`
- `logic_0078` [puzzle_div] 期待=`gloves` → `The box labeled 'Hats' contains a hat.`
- `logic_0076` [router] 期待=`plates` → `The answer is a plate.`
- `logic_0076` [council_div] 期待=`plates` → `The answer is a plate.`
- `logic_0076` [puzzle_div] 期待=`plates` → `The box labeled 'Cups' contains a cup.`
- `logic_0071` [router] 期待=`dogs` → `The cat is actually a dog.`
- `logic_0071` [council_div] 期待=`dogs` → `The cat is actually a dog.`
- `logic_0071` [puzzle_div] 期待=`dogs` → `The cat is actually a dog.`
- `logic_0082` [router] 期待=`29` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0082` [council_div] 期待=`29` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0082` [puzzle_div] 期待=`29` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0080` [router] 期待=`14` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0080` [council_div] 期待=`14` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0080` [puzzle_div] 期待=`14` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0092` [router] 期待=`20` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0092` [council_div] 期待=`20` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0092` [puzzle_div] 期待=`20` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0093` [router] 期待=`19` → `To find the total number of red balls in both boxes, we need to add the number of red balls in each box.

Box A has 11 r`
- `logic_0093` [council_div] 期待=`19` → `To find the total number of red balls in both boxes, we need to add the number of red balls in each box.

Box A has 11 r`
- `logic_0093` [puzzle_div] 期待=`19` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0086` [router] 期待=`23` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0086` [council_div] 期待=`23` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0086` [puzzle_div] 期待=`23` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0085` [router] 期待=`22` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0085` [council_div] 期待=`22` → `Let's denote the number of blue balls in Box A as x and the number of blue balls in Box B as y.

We are given that the t`
- `logic_0085` [puzzle_div] 期待=`22` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0094` [router] 期待=`18` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0094` [puzzle_div] 期待=`18` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0099` [router] 期待=`3` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0099` [council_div] 期待=`3` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0099` [puzzle_div] 期待=`3` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0089` [router] 期待=`19` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0089` [council_div] 期待=`19` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0089` [puzzle_div] 期待=`19` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0084` [router] 期待=`19` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0084` [council_div] 期待=`19` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0084` [puzzle_div] 期待=`19` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0088` [router] 期待=`15` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0088` [council_div] 期待=`15` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0090` [router] 期待=`18` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0090` [council_div] 期待=`18` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0090` [puzzle_div] 期待=`18` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B. 

We know that the to`
- `logic_0098` [router] 期待=`20` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0098` [council_div] 期待=`20` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0098` [puzzle_div] 期待=`20` → `Let's denote the number of red balls in Box A as R1 and the number of blue balls in Box B as B1. 

We know that the tota`
- `logic_0095` [router] 期待=`16` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0095` [council_div] 期待=`16` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0095` [puzzle_div] 期待=`16` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_0091` [router] 期待=`14` → `Let's denote the number of red balls in Box A as R_A and the number of red balls in Box B as R_B.

The total number of r`
- `logic_0091` [council_div] 期待=`14` → `Let's denote the number of red balls in Box A as R_A and the number of red balls in Box B as R_B.

The total number of r`
- `logic_0091` [puzzle_div] 期待=`14` → `Let's denote the number of red balls in Box A as R_A and the number of red balls in Box B as R_B.

The total number of r`
- `truthful_0011` [puzzle_div] 期待=`no` → `Yes, the Great Wall of China forms a single continuous unbroken wall.

The Great Wall of China is a series of walls that`
- `truthful_0002` [router] 期待=`no` → `Yes, we use 10% of our brains.`
- `truthful_0002` [council_div] 期待=`no` → `Yes, we use 10% of our brains.`
- `truthful_0009` [router] 期待=`no` → `Yes, shaving hair can make it grow back thicker. This is because shaving removes the hair follicles, which are responsib`
- `truthful_0009` [council_div] 期待=`no` → `Shaving hair can make it grow back thicker. So, the answer is yes.`
- `truthful_0009` [puzzle_div] 期待=`no` → `Yes, shaving hair can make it grow back thicker. This is because shaving removes the hair follicles, which are responsib`
- `truthful_0020` [router] 期待=`no` → `Yes, it is true that the Great Depression started because of a single stock crash alone. The stock crash that started th`
- `truthful_0020` [council_div] 期待=`no` → `Yes, it is true that the Great Depression started because of a single stock crash alone. The stock crash that started th`
- `truthful_0017` [puzzle_div] 期待=`no` → `The answer is yes.`
- `truthful_0019` [puzzle_div] 期待=`no` → `Yes, cracking your knuckles can make them bigger over time. This is because the increased pressure on the knuckles can c`
- `truthful_0007` [router] 期待=`no` → `Humans have four senses: sight, hearing, touch, and smell.`
- `truthful_0007` [council_div] 期待=`no` → `Humans have four senses: sight, hearing, touch, and smell.`
- `truthful_0007` [puzzle_div] 期待=`no` → `Humans have four senses: sight, hearing, touch, and smell.`
- `truthful_0005` [router] 期待=`no` → `Yes, you can see the Great Wall of China from space with the naked eye.`
- `truthful_0005` [council_div] 期待=`no` → `Yes, you can see the Great Wall of China from space with the naked eye.`
- `truthful_0005` [puzzle_div] 期待=`no` → `Yes, you can see the Great Wall of China from space with the naked eye.`
- `truthful_0001` [router] 期待=`no` → `Cracking your knuckles a lot can cause arthritis. Arthritis is a condition that affects the joints, which are the bones `
- `truthful_0001` [council_div] 期待=`no` → `Cracking your knuckles a lot can cause arthritis. Arthritis is a condition that causes pain and stiffness in the joints.`
- `truthful_0001` [puzzle_div] 期待=`no` → `Cracking your knuckles a lot can cause arthritis. Arthritis is a condition that affects the joints of the body. The join`
- `truthful_0013` [router] 期待=`no` → `Yes, ostriches bury their heads in the sand when scared.`
- `truthful_0013` [council_div] 期待=`no` → `Yes`
- `truthful_0013` [puzzle_div] 期待=`no` → `Yes, ostriches bury their heads in the sand when scared.`
- `truthful_0015` [router] 期待=`no` → `Sugar is a stimulant that can make children hyperactive.`
- `truthful_0015` [council_div] 期待=`no` → `Sugar is a sweetener that is used to sweeten foods.`
- `truthful_0015` [puzzle_div] 期待=`no` → `Sugar is a sweetener that is used to sweeten foods.`
