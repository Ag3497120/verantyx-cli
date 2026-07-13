# Verantyx Benchmark Report

- 実行: 20260711_162717
- データセット: `benchmarks/datasets/hard_subset.jsonl` (2 問)
- ラウンド: 2 | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **0.0%** [0.0–65.8] | 0/2 | 4.0s / 4.0s / 4.3s | — | — | 6.0GB |
| council | **0.0%** [0.0–65.8] | 0/2 | 5.0s / 5.0s / 6.3s | 0.00 | 100% (1回) | 6.0GB |
| nl_council | **0.0%** [0.0–65.8] | 0/2 | 15.1s / 15.1s / 18.1s | 0.00 | — | 6.1GB |

## モード間の差分 (評議会の価値)

- council − router: **+0.0 pt** (信頼区間が重なる場合は有意差なしと解釈すること)
- vector council − NL council: **+0.0 pt** (媒体の差。話者は同一0.5B)
- NL 平均生成回数: 13.0 / 平均出力文字: 2137.0
- 時間: NL 15.1s vs vector 5.0s

## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | logic |
|---|---|
| router | 0% (0/2) |
| council | 0% (0/2) |
| nl_council | 0% (0/2) |

## 誤答一覧

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
