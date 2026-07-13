# Verantyx Benchmark Report

- 実行: 20260711_102142
- データセット: `benchmarks/datasets/factual_qa_500.jsonl` (3 問)
- ラウンド: auto | エスカレーション: False

## 集計 (95%信頼区間つき)

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 | 平均エスカレ | 摂動復帰率 | 最大RSS |
|--------|-----------------|-----------|-------------------|--------------|------------|---------|
| router | **66.7%** [20.8–93.8] | 2/3 | 0.7s / 0.6s / 0.8s | — | — | 6.1GB |
| council | **66.7%** [20.8–93.8] | 2/3 | 1.8s / 1.5s / 2.4s | 0.00 | 67% (3回) | 6.1GB |
| council_no_perturb | **66.7%** [20.8–93.8] | 2/3 | 1.4s / 1.4s / 1.5s | 0.00 | — | 6.1GB |

## モード間の差分 (評議会の価値)

- council − router: **+0.0 pt** (信頼区間が重なる場合は有意差なしと解釈すること)
- 摂動テストの効果 (council − no_perturb): **+0.0 pt**

## カテゴリ別正解率 (fact/numeric/logic/multihop/truthful/ja/zh/ko)

| モード | fact | logic |
|---|---|---|
| router | 100% (1/1) | 50% (1/2) |
| council | 100% (1/1) | 50% (1/2) |
| council_no_perturb | 100% (1/1) | 50% (1/2) |

## 誤答一覧

- `logic_0071` [router] 期待=`dogs` → `The cat is actually a dog.`
- `logic_0071` [council] 期待=`dogs` → `The cat is actually a dog.`
- `logic_0071` [council_no_perturb] 期待=`dogs` → `The cat is actually a dog.`
