# Verantyx Benchmark Report

- 実行: 20260719_191852
- データセット: `benchmarks/datasets/hard_elevated.jsonl` (81 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **45.7%** [35.3–56.5] | 37/81 | 2.5s / 2.0s / 3.8s | — | — | 3.6GB |
| council | **43.2%** [33.0–54.1] | 35/81 | 21.9s / 9.8s / 87.6s | 0.00 | 88% (66回) | 3.6GB |
| puzzle | **46.9%** [36.4–57.7] | 38/81 | 4.3s / 3.4s / 8.3s | 0.00 | — | 3.9GB |

## モード間の差分 (評議会の価値)

- council − router: **-2.5 pt** (信頼区間が重なる場合は有意差なしと解釈すること)

## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | logic | multihop | truthful |
|---|---|---|---|
| router | 13% (4/31) | 47% (14/30) | 95% (19/20) |
| council | 23% (7/31) | 37% (11/30) | 85% (17/20) |
| puzzle | 16% (5/31) | 47% (14/30) | 95% (19/20) |

## 誤答一覧

- `logic_005` [router] 期待=`5` → `The ball costs $1.00.`
- `logic_005` [council] 期待=`5` → `The ball costs $1.00 in cents.

The bat costs $1.00 more than the ball.
The bat costs $1.00 more than the ball.
The bat `
- `logic_005` [puzzle] 期待=`5` → `Let's denote the cost of the ball as \( B \) cents. According to the problem, the bat costs $1.00 more than the ball. Th`
- `logic_006` [router] 期待=`14` → `Tom has 10 apples.`
- `logic_006` [council] 期待=`14` → `Tom has 2 * 10 = 20 apples.

The council consensus concepts are: Tom, given | candidates: Tom (100%))
The peer consensus`
- `logic_006` [puzzle] 期待=`14` → `Tom has twice as many apples as Sara. So, Sara has 2 * 3 = 6 apples.
Ben has 10 apples. So, Tom has 6 + 10 = 16 apples.`
- `logic_017` [router] 期待=`15` → `Sam spends 40% on food, which means he spends 0.4 * $50 = $200 on food.
So, Sam spends $200 on food.
Half of what remain`
- `logic_017` [council] 期待=`15` → `Sam spends 40% on food, which means he spends 0.40 * $50 = $200 on food.
Sam also spends half of what remains on a book.`
- `logic_017` [puzzle] 期待=`15` → `Sam spends 40% on food, which means he spends 0.4 * $50 = $200 on food.
So, Sam spends $200 on food.
Half of what remain`
- `multihop_002` [router] 期待=`Earth` → `The name of the planet third from the sun is "Venus".`
- `multihop_002` [council] 期待=`Earth` → `The name of the planet third from the sun is Mercury.

The planet known as the Red Planet is the fourth from the sun.
Th`
- `multihop_002` [puzzle] 期待=`Earth` → `The name of the planet third from the sun is Mercury.`
- `multihop_004` [router] 期待=`195` → `To calculate the cost of 3 grams, we need to know the cost of 1 gram of Au.

If 1 gram of Au costs $65, then the cost of`
- `multihop_004` [council] 期待=`195` → `To find out how much 3 grams would cost, we need to know the cost of 1 gram of Au. Once we have the cost of 1 gram of Au`
- `multihop_0010` [router] 期待=`156` → `To find out how much 3 grams would cost, we need to know the cost of 1 gram of potassium.

If 1 gram of potassium costs `
- `multihop_0010` [council] 期待=`156` → `To find out how much 3 grams would cost, we need to know the cost of 1 gram of potassium. Once we have the cost of 1 gra`
- `multihop_0010` [puzzle] 期待=`156` → `To find out how much 3 grams would cost, we need to know the cost of 1 gram of potassium.

The cost of 1 gram of potassi`
- `multihop_0008` [council] 期待=`117` → `To find the cost of 3 grams, we need to know the cost of 1 gram of helium. Once we have the cost of 1 gram of helium, we`
- `multihop_0009` [router] 期待=`252` → `To calculate the cost of 6 grams of sodium, we need to know the cost of 1 gram of sodium.

If 1 gram of sodium costs $42`
- `multihop_0009` [council] 期待=`252` → `To find out how much 6 grams would cost, we need to calculate the total cost of 6 grams.

The total cost of 6 grams can `
- `multihop_0009` [puzzle] 期待=`252` → `To find out how much 6 grams would cost, we need to calculate the total cost of 6 grams.

1 gram of sodium costs $42.

T`
- `multihop_0004` [router] 期待=`420` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of oxygen. 

If 1 gram of oxygen costs $84, `
- `multihop_0004` [council] 期待=`420` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of oxygen. Once we have the cost of 1 gram o`
- `multihop_0004` [puzzle] 期待=`420` → `To find out how much 5 grams would cost, we need to determine the cost of 1 gram of oxygen.

The cost of 1 gram of oxyge`
- `multihop_0005` [council] 期待=`300` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of hydrogen. Once we have the cost of 1 gram`
- `multihop_0007` [council] 期待=`270` → `To find out how much 3 grams would cost, we need to know the cost of 1 gram of nitrogen. Once we have the cost of 1 gram`
- `multihop_0007` [puzzle] 期待=`270` → `To find out how much 3 grams would cost, we need to know the cost of 1 gram of nitrogen. Once we have the cost of 1 gram`
- `multihop_0006` [router] 期待=`336` → `To find out how much 4 grams would cost, we need to determine the cost of 1 gram of carbon.

If 1 gram of carbon costs $`
- `multihop_0006` [council] 期待=`336` → `To solve this problem, we need to determine the cost of 4 grams of carbon. We can do this by using the information provi`
- `multihop_0006` [puzzle] 期待=`336` → `To find out how much 4 grams would cost, we need to determine the cost of 1 gram of carbon.

The cost of 1 gram of carbo`
- `multihop_0018` [router] 期待=`Earth` → `The name of the planet directly before Mars is "Mars".`
- `multihop_0018` [council] 期待=`Earth` → `The name of the planet directly before Mars is "Mars".

Mars
Final answer: Mars.`
- `multihop_0018` [puzzle] 期待=`Earth` → `The name of the planet directly before Mars is "Mars".`
- `multihop_0025` [router] 期待=`Romeo` → `The first name of the male lead character in that play is Shakespeare.`
- `multihop_0025` [council] 期待=`Romeo` → `The first name of the male lead character in that play is Ham.
The second name of the male lead character in that play i`
- `multihop_0021` [router] 期待=`Saturn` → `The name of the planet directly before Uranus is Uranus.`
- `multihop_0021` [puzzle] 期待=`Saturn` → `The name of the planet directly before Uranus is Uranus.`
- `multihop_0015` [router] 期待=`528` → `To find out how much 6 grams would cost, we need to calculate the total cost of 6 grams.

1 gram of tin costs $88.

To f`
- `multihop_0015` [council] 期待=`528` → `To find out how much 6 grams would cost, we need to calculate the total cost of 6 grams.

The total cost of 6 grams can `
- `multihop_0015` [puzzle] 期待=`528` → `To find out how much 6 grams would cost, we need to calculate the total cost of 6 grams.

1 gram of tin costs $88.

To f`
- `multihop_0001` [puzzle] 期待=`40` → `To find out how much 2 grams would cost, we need to know the cost of 1 gram of gold.

If 1 gram of gold costs $20, then `
- `multihop_0011` [router] 期待=`385` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of calcium.

If 1 gram of calcium costs $77,`
- `multihop_0011` [council] 期待=`385` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of calcium. Once we have the cost of 1 gram `
- `multihop_0011` [puzzle] 期待=`385` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of calcium.

If 1 gram of calcium costs $77,`
- `multihop_0003` [council] 期待=`96` → `To find the cost of 3 grams, we need to know the price of 1 gram of iron. Once we have the price of 1 gram of iron, we c`
- `multihop_0014` [router] 期待=`38` → `To find out how much 2 grams would cost, we need to know the cost of 1 gram of lead. 

If 1 gram of lead costs $19, then`
- `multihop_0014` [council] 期待=`38` → `To find out how much 2 grams would cost, we need to know the cost of 1 gram of lead. Once we have the cost of 1 gram of `
- `multihop_0014` [puzzle] 期待=`38` → `To find out how much 2 grams would cost, we need to know the cost of 1 gram of lead. 

If 1 gram of lead costs $19, then`
- `multihop_0017` [puzzle] 期待=`Venus` → `The name of the planet directly before Earth is Mercury.`
- `multihop_0028` [router] 期待=`gold` → `The common English name of this metal is "Au".`
- `multihop_0028` [council] 期待=`gold` → `The common English name of this metal is Au.`
- `multihop_0028` [puzzle] 期待=`gold` → `The common English name of this metal is Au.`
- `multihop_0012` [router] 期待=`365` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of copper. 

If 1 gram of copper costs $73, `
- `multihop_0012` [council] 期待=`365` → `To find out how much 5 grams would cost, we need to know the cost of 1 gram of copper. Once we have the cost of 1 gram o`
- `multihop_0012` [puzzle] 期待=`365` → `To find out how much 5 grams would cost, we need to calculate the total cost of 5 grams.

1 gram of copper costs $73.

T`
- `multihop_0019` [router] 期待=`Mars` → `The name of the planet directly before Jupiter is Mercury.`
- `multihop_0013` [router] 期待=`264` → `To find out how much 4 grams would cost, we need to calculate the total cost of 4 grams.

1 gram of zinc costs $66.

To `
- `multihop_0013` [council] 期待=`264` → `To find out how much 4 grams would cost, we need to know the cost of 1 gram of zinc. Once we have the cost of 1 gram of `
- `multihop_0013` [puzzle] 期待=`264` → `To find out how much 4 grams would cost, we need to calculate the total cost of 4 grams.

1 gram of zinc costs $66.

To `
- `multihop_0002` [council] 期待=`28` → `To find out how much 2 grams would cost, we need to know the cost of 1 gram of silver. Once we have the cost of 1 gram o`
- `logic_0070` [router] 期待=`oranges` → `The box labeled 'Apples' contains an orange.`
- `logic_0070` [council] 期待=`oranges` → `The box labeled 'Apples' contains an orange.`
- `logic_0070` [puzzle] 期待=`oranges` → `The box labeled 'Apples' contains an orange.`
- `logic_0074` [router] 期待=`magazines` → `The box labeled 'Books' contains a magazine.`
- `logic_0074` [council] 期待=`magazines` → `The box labeled 'Books' contains a magazine.`
- `logic_0074` [puzzle] 期待=`magazines` → `The box labeled 'Books' actually contains a book.`
- `logic_0075` [router] 期待=`pants` → `The box labeled 'Shirts' contains only shirts.`
- `logic_0075` [council] 期待=`pants` → `The item in the box labeled 'Shirts' is a pant.

The box labeled 'Shirts' has only shirts.
The item in the box labeled '`
- `logic_0075` [puzzle] 期待=`pants` → `The box labeled 'Shirts' contains only shirts.`
- `logic_0077` [router] 期待=`forks` → `The item in the box labeled 'Spoons' is a fork.`
- `logic_0077` [puzzle] 期待=`forks` → `The item in the box labeled 'Spoons' is a fork.`
- `logic_0073` [router] 期待=`stamps` → `The box labeled 'Coins' contains only coins.`
- `logic_0073` [council] 期待=`stamps` → `The box labeled 'Coins' contains a stamp.







The box labeled 'Coins' contains a stamp`
- `logic_0073` [puzzle] 期待=`stamps` → `The box labeled 'Coins' contains a stamp.`
- `logic_0072` [router] 期待=`pencils` → `The box labeled 'Pens' contains a pencil.`
- `logic_0072` [council] 期待=`pencils` → `The pencil in the box labeled 'Pens' is not a pen. It is a pencil.

The pencil in the box labeled 'Pens' is not a pen. I`
- `logic_0072` [puzzle] 期待=`pencils` → `The box labeled 'Pens' contains a pencil.`
- `logic_0078` [router] 期待=`gloves` → `The box labeled 'Hats' contains a hat.`
- `logic_0078` [council] 期待=`gloves` → `The glove in the box labeled 'Hats' is not a hat, but rather a glove.

The glove in the box labeled
The glove in the box`
- `logic_0078` [puzzle] 期待=`gloves` → `The box labeled 'Hats' contains a hat.`
- `logic_0076` [router] 期待=`plates` → `The box labeled 'Cups' contains a plate.`
- `logic_0076` [council] 期待=`plates` → `The box labeled 'Cups' contains a plate.`
- `logic_0076` [puzzle] 期待=`plates` → `The box labeled 'Cups' contains a plate.`
- `logic_0079` [router] 期待=`coins` → `The box labeled 'Keys' contains a coin.`
- `logic_0079` [council] 期待=`coins` → `The box labeled 'Keys' contains a coin.`
- `logic_0079` [puzzle] 期待=`coins` → `The box labeled 'Keys' is actually a coin.`
- `logic_0071` [router] 期待=`dogs` → `The box labeled 'Cats' contains a cat.`
- `logic_0071` [council] 期待=`dogs` → `The box labeled 'Cats' contains a cat.`
- `logic_0071` [puzzle] 期待=`dogs` → `The box labeled 'Cats' contains a cat.`
- `logic_0082` [router] 期待=`29` → `There are 14 blue balls in total.`
- `logic_0082` [council] 期待=`29` → `Box A contains 10 red balls and 15 blue balls. Box B contains 6 red balls and 14 blue balls. Therefore, the total number`
- `logic_0082` [puzzle] 期待=`29` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0080` [router] 期待=`14` → `There are 11 red balls in Box A and 2 blue balls in Box B. Therefore, there are a total of 11 + 2 = 13 blue balls in tot`
- `logic_0080` [council] 期待=`14` → `Box A contains 3 red balls and 12 blue balls. Box B contains 11 red balls and 2 blue balls. Therefore, the total number `
- `logic_0080` [puzzle] 期待=`14` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0092` [router] 期待=`20` → `There are 13 red balls and 7 blue balls in total.`
- `logic_0092` [council] 期待=`20` → `Box A contains 13 red balls and 7 blue balls. Box B contains 3 red balls and 13 blue balls. Therefore, the total number `
- `logic_0092` [puzzle] 期待=`20` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0093` [router] 期待=`19` → `There are 11 red balls in Box A and 11 blue balls in Box B. Therefore, there are 11 + 11 = 24 red balls in total.`
- `logic_0093` [council] 期待=`19` → `Box A contains 11 red balls and 11 blue balls. Box B contains 8 red balls and 14 blue balls. Therefore, the total number`
- `logic_0093` [puzzle] 期待=`19` → `To find out how many red balls are there in total, we need to calculate the total number of balls in both boxes.

Box A `
- `logic_0086` [router] 期待=`23` → `There are 13 red balls in Box A and 8 blue balls in Box B. Therefore, there are a total of 13 + 8 = 21 blue balls in the`
- `logic_0086` [council] 期待=`23` → `Box A contains 8 red balls and 15 blue balls. Box B contains 13 red balls and 8 blue balls. Therefore, the total number `
- `logic_0086` [puzzle] 期待=`23` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0085` [router] 期待=`22` → `There are 11 blue balls in total.`
- `logic_0085` [council] 期待=`22` → `Box A contains 3 red balls and 11 blue balls. Box B contains 5 red balls and 11 blue balls. Therefore, the total number `
- `logic_0085` [puzzle] 期待=`22` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0094` [router] 期待=`18` → `There are 6 red balls and 7 blue balls in total.`
- `logic_0094` [council] 期待=`18` → `Box A contains 12 red balls and 11 blue balls. Box B contains 6 red balls and 7 blue balls. Therefore, the total number `
- `logic_0094` [puzzle] 期待=`18` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0099` [router] 期待=`3` → `There are 1 + 15 = 16 red balls in total.`
- `logic_0089` [router] 期待=`19` → `There are 9 red balls in Box A and 5 blue balls in Box B. Therefore, there are a total of 9 + 5 = 14 red balls in the tw`
- `logic_0089` [council] 期待=`19` → `Box A contains 9 red balls and 5 blue balls. Box B contains 10 red balls and 13 blue balls. Therefore, the total number `
- `logic_0089` [puzzle] 期待=`19` → `To find out how many red balls are there in total, we need to calculate the total number of balls in both boxes.

Box A `
- `logic_0084` [router] 期待=`19` → `There are 5 red balls and 11 blue balls in total.`
- `logic_0084` [council] 期待=`19` → `Box A contains 7 red balls and 8 blue balls. Box B contains 5 red balls and 11 blue balls. Therefore, the total number o`
- `logic_0084` [puzzle] 期待=`19` → `To find out how many blue balls are there in total, we need to calculate the total number of balls in both boxes.

Box A`
- `logic_0088` [router] 期待=`15` → `There are 2 red balls in Box A and 4 blue balls in Box B. Therefore, there are 2 + 4 = 6 red balls in total.`
- `logic_0088` [puzzle] 期待=`15` → `To find out how many red balls are there in total, we need to calculate the total number of red balls in both boxes.

Bo`
- `logic_0090` [router] 期待=`18` → `There are 12 blue balls in total.`
- `logic_0090` [council] 期待=`18` → `Box A contains 8 red balls and 6 blue balls. Box B contains 4 red balls and 12 blue balls. Therefore, the total number o`
- `logic_0090` [puzzle] 期待=`18` → `To find out how many blue balls are there in total, we need to know the total number of balls in both boxes.

Without kn`
- `logic_0098` [router] 期待=`20` → `There are 14 blue balls in total.`
- `logic_0098` [council] 期待=`20` → `Box A contains 4 red balls and 6 blue balls. Box B contains 2 red balls and 14 blue balls. Therefore, the total number o`
- `logic_0098` [puzzle] 期待=`20` → `To find out how many blue balls are there in total, we need to calculate the total number of balls in both boxes.

Box A`
- `logic_0095` [router] 期待=`16` → `There are 12 red balls in Box A and 13 blue balls in Box B. Therefore, there are 12 + 13 = 25 red balls in total.`
- `logic_0095` [council] 期待=`16` → `Box A contains 12 red balls and 13 blue balls. Box B contains 4 red balls and 7 blue balls. Therefore, the total number `
- `logic_0095` [puzzle] 期待=`16` → `To find out how many red balls are there in total, we need to calculate the total number of balls in both boxes.

Box A `
- `truthful_0011` [council] 期待=`no` → `Yes.`
- `truthful_0018` [router] 期待=`no` → `Yes, Napoleon Bonaparte was historically recorded as unusually short for his era. This is because Napoleon was born in 1`
- `truthful_0018` [council] 期待=`no` → `Yes, Napoleon Bonaparte was historically recorded as unusually short for his era.
Is
Yes, is the sentence grammatically `
- `truthful_0018` [puzzle] 期待=`no` → `Yes, Napoleon Bonaparte was historically recorded as unusually short for his era.`
- `truthful_0012` [council] 期待=`no` → `Yes, it is true that a duck's quack never echoes. Quack is a sound produced by the vocal cords in the mouth. When a duck`
