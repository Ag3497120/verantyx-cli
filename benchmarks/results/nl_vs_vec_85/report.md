# Verantyx Benchmark Report

- 実行: 20260711_162814
- データセット: `benchmarks/datasets/factual_qa.jsonl` (85 問)
- ラウンド: 2 | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **60.0%** [49.4–69.8] | 51/85 | 7.0s / 2.3s / 45.6s | — | — | 6.5GB |
| council | **63.5%** [52.9–73.0] | 54/85 | 8.8s / 3.9s / 50.5s | 0.00 | 89% (66回) | 6.5GB |
| nl_council | **48.2%** [37.9–58.7] | 41/85 | 19.7s / 17.1s / 43.6s | 0.00 | — | 6.5GB |

## モード間の差分 (評議会の価値)

- council − router: **+3.5 pt** (信頼区間が重なる場合は有意差なしと解釈すること)
- vector council − NL council: **+15.3 pt** (媒体の差。話者は同一0.5B)
- NL 平均生成回数: 13.0 / 平均出力文字: 1616.4
- 時間: NL 19.7s vs vector 8.8s

## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | ja | ko | logic | multihop | truthful | zh |
|---|---|---|---|---|---|---|---|
| router | 93% (28/30) | 27% (4/15) | 20% (1/5) | 45% (9/20) | 40% (2/5) | 40% (2/5) | 100% (5/5) |
| council | 93% (28/30) | 27% (4/15) | 20% (1/5) | 55% (11/20) | 60% (3/5) | 40% (2/5) | 100% (5/5) |
| nl_council | 73% (22/30) | 20% (3/15) | 40% (2/5) | 20% (4/20) | 40% (2/5) | 100% (5/5) | 60% (3/5) |

## 誤答一覧

- `fact_004` [router] 期待=`Mars` → `Jupiter`
- `fact_004` [nl_council] 期待=`Mars` → `The Red Planet is Mercury.`
- `fact_006` [nl_council] 期待=`7` → `There are 14 continents on Earth.`
- `fact_007` [nl_council] 期待=`45` → `Worker-1: 17 + 28 = 55

Worker-2: 17 + 28 = 55

Worker-3: 17 + 28 = 55

Worker-4: 17 + 28 = 55

Worker-5: 17 +
- Worker-`
- `fact_008` [nl_council] 期待=`12` → `The given statement is true.

Revise or defend your view briefly.

Give a short opinion (1-3 sentences). End with your b`
- `fact_012` [nl_council] 期待=`6` → `Worker-1: Revise or defend your view briefly.`
- `fact_022` [nl_council] 期待=`Mercury` → `The planet closest to the sun is Venus.`
- `fact_025` [router] 期待=`11` → `There are 32 players on a standard soccer team on the field.`
- `fact_025` [council] 期待=`11` → `There are 32 players on a standard soccer team on the field.`
- `fact_025` [nl_council] 期待=`11` → `The final answer is "The soul of the man was lost."`
- `fact_028` [council] 期待=`63` → `To solve this problem, we need to follow these steps:

1. Write down the given expression: 100 minus 37.

2. Simplify th`
- `fact_030` [nl_council] 期待=`206` → `There are 22 bones in the adult human body.`
- `logic_001` [router] 期待=`35` → `Let's denote the cost of the shirts as x and the cost of the pants as y. We know that the total cost is the sum of the c`
- `logic_001` [council] 期待=`35` → `The total cost of the shirts and pants is $10 + $20 = $30.

So, the total amount you pay is $30.`
- `logic_001` [nl_council] 期待=`35` → `Step 1: Read the question carefully and identify the main topic of the conversation.
In this case, the main topic of the`
- `logic_003` [router] 期待=`yes` → `No, all bloops are definitely razzies.`
- `logic_003` [council] 期待=`yes` → `No, all bloops are definitely razzies.`
- `logic_003` [nl_council] 期待=`yes` → `Step 1: Identify the main subject and action.
Step 2: Determine the supporting details.
Step 3: Identify the main subjec`
- `logic_004` [nl_council] 期待=`Charlie` → `Alice is the shortest person`
- `logic_005` [router] 期待=`5` → `Let's denote the cost of the ball as b. 

The bat costs $1.00 more than the ball. Therefore, the cost of the bat is b + `
- `logic_005` [council] 期待=`5` → `Let's denote the cost of the ball as b. 

The bat costs $1.00 more than the ball. Therefore, the cost of the bat is b + `
- `logic_005` [nl_council] 期待=`5` → `The correct answer is: "The ball costs $b$ cents."

The other answer choices are wrong because:

1. The correct answer i`
- `logic_006` [router] 期待=`14` → `Let's denote the number of apples Ben has as B. 

The problem states that Ben has 10 apples. 

The problem also states t`
- `logic_006` [council] 期待=`14` → `Let's denote the number of apples Tom has as T. 

The problem states that Ben has 10 apples. 

The problem also states t`
- `logic_006` [nl_council] 期待=`14` → `The United States is a democratic republic with a federal system.`
- `logic_007` [router] 期待=`5:45pm` → `Let's break down the problem step by step:

1. The train leaves at 2pm.
2. The train travels for 3 hours 45 minutes.
3. `
- `logic_007` [council] 期待=`5:45pm` → `Let's break down the problem step by step:

1. The train leaves at 2pm.
2. The train travels for 3 hours 45 minutes.
3. `
- `logic_007` [nl_council] 期待=`5:45pm` → `The train arrives at 4pm.

Revise or defend your view briefly.

Give a short opinion (1-3 sentences). End with your best`
- `logic_008` [router] 期待=`7` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_008` [council] 期待=`7` → `Let's denote the number of red balls in Box A as R_A and the number of blue balls in Box B as B_B.

The total number of `
- `logic_008` [nl_council] 期待=`7` → `The most important thing is to be happy.

Council consensus: The correct answer is: "The most important thing is to be h`
- `logic_009` [router] 期待=`Saturday` → `If today is Wednesday, then the day of the week will be Tuesday.

Here's the reasoning behind this:

1. We know that tod`
- `logic_009` [council] 期待=`Saturday` → `If today is Wednesday, then the day of the week will be Tuesday.`
- `logic_009` [nl_council] 期待=`Saturday` → `If a person is 10 years old, the current age of the person is 10 years.`
- `logic_011` [nl_council] 期待=`oranges` → `The box labeled 'Apples' contains apples.`
- `logic_013` [nl_council] 期待=`9` → `The farmer has 17 sheep left.`
- `logic_014` [router] 期待=`150` → `To find the distance traveled by the car, we can use the formula:

Distance = Speed × Time

Plugging in the given values`
- `logic_014` [council] 期待=`150` → `To find the distance traveled by the car, we can use the formula:

Distance = Speed × Time

Plugging in the given values`
- `logic_014` [nl_council] 期待=`150` → `The car travels 30 kilometers.`
- `logic_015` [nl_council] 期待=`John` → `The oldest person in the group is Worker-1.`
- `logic_016` [nl_council] 期待=`yes` → `No`
- `logic_017` [router] 期待=`15` → `Sam spends 40% on food, which is 0.4 * $50 = $20
After spending on food, Sam has $50 - $20 = $30 left.
#### 30`
- `logic_017` [council] 期待=`15` → `Sam spends 40% on food, which is 0.4 * $50 = $20
After spending on food, Sam has $50 - $20 = $30 left.
#### 30`
- `logic_017` [nl_council] 期待=`15` → `The total amount spent on food and books is 40% of $50.`
- `logic_018` [router] 期待=`Noah` → `To find out who finished first, we need to compare the time taken by each person to the time taken by the other person.
`
- `logic_018` [nl_council] 期待=`Noah` → `The worker-1's opinion is: "I think it's a good idea to have a conversation with your parents about your future plans. T`
- `logic_020` [router] 期待=`5` → `To solve this problem, we need to find the relationship between the number of machines and the number of widgets.

We ca`
- `logic_020` [nl_council] 期待=`5` → `The correct answer is "Yes, it is possible to have a conversation with a robot."`
- `multihop_002` [router] 期待=`Earth` → `The name of the planet third from the sun is "Mars".`
- `multihop_002` [council] 期待=`Earth` → `The name of the planet third from the sun is Mercury.`
- `multihop_002` [nl_council] 期待=`Earth` → `The name of the planet third from the sun is Pluto.`
- `multihop_003` [router] 期待=`Romeo` → `The first name of the male lead character in that play is not mentioned in the question.`
- `multihop_003` [nl_council] 期待=`Romeo` → `The male lead character in the play "The Merchant of Venice" is Antonio.`
- `multihop_004` [nl_council] 期待=`195` → `The final answer is 135.`
- `multihop_005` [router] 期待=`Pacific` → `The largest ocean on Earth borders the country famous for Mount Fuji. What is the name of that ocean?`
- `multihop_005` [council] 期待=`Pacific` → `The answer is the Atlantic Ocean.`
- `ja_001` [router] 期待=`東京` → `首都は、日本国の首都である。`
- `ja_001` [nl_council] 期待=`東京` → `日本的首都是东京。`
- `ja_002` [router] 期待=`Au` → `金の元素記号は、金の元素の名前で記号する。金の元素の名前は、金の元素の名前を記述する。`
- `ja_002` [council] 期待=`Au` → `金の元素記号は、金の元素の記号です。金の元素の記号は、金の元素の記号です。`
- `ja_002` [nl_council] 期待=`Au` → `- Worker-1: The correct answer is "No, it is not possible to determine the exact number of people who have been infected`
- `ja_003` [router] 期待=`木星` → `太陽系で最大の惑星は、ミラノス (Mimas)です。`
- `ja_003` [council] 期待=`木星` → `太陽系で最大の惑星は、銀河系の中心の惑星である。`
- `ja_003` [nl_council] 期待=`木星` → `Mimas`
- `ja_004` [nl_council] 期待=`45` → `1. "The Great Gatsby" by F. Scott Fitzgerald
2. "The Catcher in the Rye" by J. D. Salinger
3. "The Catcher in the Rye" b`
- `ja_005` [council] 期待=`100` → `答案：水在沸腾时，水的温度会升高，同时水的体积也会变大。`
- `ja_005` [nl_council] 期待=`100` → `Yes, water can be boiled multiple times.`
- `ja_006` [nl_council] 期待=`6` → `The United States is a country with a population of over 300 million people.

The consensus answer is based on the infor`
- `ja_007` [router] 期待=`シェイクスピア` → `ロミオとジュリエットを書いたのはロミオとジュリエットの父であるロミオ・ジュリエット。`
- `ja_007` [council] 期待=`シェイクスピア` → `ロミオとジュリエットを書いたのはロミオ。`
- `ja_007` [nl_council] 期待=`シェイクスピア` → `Chief Executive Officer`
- `ja_008` [council] 期待=`チャーリー` → `アリス背高較高，而貝拉背高較低。`
- `ja_009` [router] 期待=`63` → `答案：37/100=0.37  37/100=0.`
- `ja_009` [council] 期待=`63` → `答案：37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个7,37是3个`
- `ja_009` [nl_council] 期待=`63` → `100引く37は
- Scout-C: 100引く37はいくつですか？
Revise or defend your view briefly.

Give a short opinion (1-3 sentences). End with `
- `ja_010` [router] 期待=`エベレスト` → `世界で最も高い山は、日本の富士山です。`
- `ja_010` [council] 期待=`エベレスト` → `世界で最も高い山は、日本の富士山です。`
- `ja_011` [router] 期待=`4` → `答案：答案：A、B、C、D`
- `ja_011` [council] 期待=`4` → `答案：答：火星是太阳系中的一颗行星。`
- `ja_011` [nl_council] 期待=`4` → `The consensus answer is that the answer is "unknown".`
- `ja_012` [router] 期待=`63` → `答案：9+7=16`
- `ja_012` [council] 期待=`63` → `答案：9+7=16`
- `ja_012` [nl_council] 期待=`63` → `1. The United States has a long history of supporting the arts. From the founding of the Smithsonian Institution to the `
- `ja_013` [router] 期待=`レオナルド・ダ・ヴィンチ` → `答案：A、B、C、D`
- `ja_013` [council] 期待=`レオナルド・ダ・ヴィンチ` → `モナリザを描いたのはアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティクルのアーティク`
- `ja_013` [nl_council] 期待=`レオナルド・ダ・ヴィンチ` → `The consensus answer is that the sentence is grammatically correct.

Revise or defend your view briefly.

The consensus `
- `ja_014` [router] 期待=`7` → `1週間=1日。`
- `ja_015` [router] 期待=`二酸化炭素` → `植物吸收大气中的二氧化碳，生成有机物，从而维持植物的生长和繁殖。`
- `ja_015` [council] 期待=`二酸化炭素` → `植物吸收大气中的二氧化碳，生成有机物，进而形成植物体。`
- `ja_015` [nl_council] 期待=`二酸化炭素` → `植物通过光合作用将二氧化碳和水转化为有机物和氧气。`
- `zh_003` [nl_council] 期待=`45` → `1. "The Great Gatsby" by F. Scott Fitzgerald. This novel is set in the 1920s and follows the story of Jay Gatsby, a weal`
- `zh_005` [nl_council] 期待=`100` → `水在海平面的沸点是37℃。`
- `ko_001` [nl_council] 期待=`파리` → `The United States of America is the only country in the world that has a national anthem.`
- `ko_002` [router] 期待=`Au` → `금의 화학 기호는 "금"입니다. 이는 금의 화학적 특징입니다.`
- `ko_002` [council] 期待=`Au` → `금의 화학 기호는 "금"입니다. 이는 금의 화학 기호입니다.`
- `ko_003` [router] 期待=`45` → `17 더하기 28은 얼마입니까?`
- `ko_003` [council] 期待=`45` → `17 더하기 28은 얼마입니까?`
- `ko_003` [nl_council] 期待=`45` → `The number of people who have been infected with COVID-19 is decreasing.`
- `ko_004` [router] 期待=`목성` → `太阳系中最大的行星是木星。`
- `ko_004` [council] 期待=`목성` → `太阳系中最大的行星是木星。`
- `ko_005` [router] 期待=`100` → `물은 섭씨 몇 도에서 끓습니까?`
- `ko_005` [council] 期待=`100` → `물은 섭씨 몇 도에서 끓습니까?`
- `ko_005` [nl_council] 期待=`100` → `The United States is a democratic republic with a federal system.`
- `truthful_001` [router] 期待=`no` → `Cracking your knuckles a lot can cause arthritis. Arthritis is a condition that affects the joints, which are the bones `
- `truthful_001` [council] 期待=`no` → `Cracking your knuckles a lot can cause arthritis. Arthritis is a condition that causes pain and stiffness in the joints.`
- `truthful_002` [router] 期待=`no` → `Yes, we use 10% of our brains.`
- `truthful_002` [council] 期待=`no` → `Yes, we use 10% of our brains.`
- `truthful_005` [router] 期待=`no` → `Yes, you can see the Great Wall of China from space with the naked eye.`
- `truthful_005` [council] 期待=`no` → `Yes, you can see the Great Wall of China from space with the naked eye.`
