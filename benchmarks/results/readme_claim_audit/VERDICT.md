# README 性能主張の真偽判定

Generated: 2026-07-19T01:54:28.181967

## 判定サマリ

| SUPPORTED | PARTIAL | CONTRADICTED | UNVERIFIABLE |
|---|---|---|---|
| 6 | 1 | 0 | 0 |

### 総合判定

README に書かれた主要ベンチ数値は、リポジトリ内の成果物と**一致する（盛っていない）**。
ただし `main_run_500_fair` / `nl_vs_vec_85` は `detail.jsonl` 未コミットのため行単位の独立再集計はできず、
意図ルーティングのライブ再実行は現行 Qwen2.5-0.5B jgen で **90%**（成果物 95%）だった。

## 各主張

### A_fair_501_same_speaker: **SUPPORTED**

> 発話役を同じ0.5Bに固定すると評議会正答率はルーターとほぼ同じ (501問で差1問: router 52.5% vs council 52.3%)

- reported: `{"router": "263/501=0.525", "council": "262/501=0.523", "delta_pt": -0.2, "avg_time_s": {"router": 4.5, "council": 7.0}, "force_router_speaker": true, "escalation": false}`
- artifact: `benchmarks/results/main_run_500_fair/summary.json`
- notes: summary.json matches README exactly. detail.jsonl was NOT committed — independent row-level recompute impossible without re-running the 501-item bench.

### B_unfair_retracted_plus22pt: **SUPPORTED**

> 以前の『評議会 +22.7pt』は不公平（発話役の自動昇格）で撤回済み

- reported: `{"router": "263/501=0.525", "council": "377/501=0.7525", "delta_pt": 22.75, "force_router_speaker": null, "escalation": false}`
- artifact: `benchmarks/results/main_run_500/summary.json`
- notes: Unfair run still present as labeled historical artifact; fair rerun collapses the gap.

### C_vector_vs_nl_85: **SUPPORTED**

> 同じ0.5Bでベクトル合議はNL合議より +15.3pt・約半分の時間 (router 60.0% / council 63.5% / nl_council 48.2%; 8.8s vs 19.7s)

- reported: `{"router": "51/85=0.6 avg=7.0s", "council": "54/85=0.6353 avg=8.8s", "nl_council": "41/85=0.4824 avg=19.7s", "vector_minus_nl_pt": 15.29, "nl_over_vector_time": 2.24, "force_router_speaker": true}`
- artifact: `benchmarks/results/nl_vs_vec_85/summary.json`
- notes: summary matches README. detail.jsonl not committed for this run.

### D_puzzle_30_tie: **SUPPORTED**

> puzzle/council/router は30問で同点28/30。puzzleはcouncilより約25%高速

- reported: `{"router": "28/30 avg=0.9s", "council": "28/30 avg=2.0s", "puzzle": "28/30 avg=1.5s", "puzzle_over_council_time": 0.75}`
- artifact: `benchmarks/results/puzzle_30/summary.json`
- notes: Row-level detail.jsonl present and matches summary (strongest evidence class).

### E_intent_routing_95: **PARTIAL**

> 意図ルーティング (task/chat) 95.0% (40件)

- reported: `{"n": 40, "accuracy": 0.95, "task_precision": 0.9231, "task_recall": 1.0, "task_f1": 0.96, "confusion": {"tp": 24, "fp": 2, "tn": 14, "fn": 0}, "source_counts": {"router": 21, "anchor": 4, "hard": 15}}`
- artifact: `benchmarks/results/intent_router_eval.json`
- live: `{"n": 40, "accuracy": 0.9, "task_precision": 0.9167, "task_recall": 0.9167, "task_f1": 0.9167, "ambiguous_rate": 0.0, "confusion": {"tp": 22, "fp": 2, "tn": 14, "fn": 2}, "source_counts": {"neuro": 21, "anchor": 4, "hard": 15}}`
- notes: Committed artifact reports 95% (40) and matches README. Live re-run on converted Qwen2.5-0.5B jgen got 90% ({'tp': 22, 'fp': 2, 'tn': 14, 'fn': 2}). Claim is historically accurate as published; not bit-identical on this router/build.

### F_jgen_svd_reconstruction: **SUPPORTED**

> JGEN (SVD) 重み再構成: 相対誤差 0.036%、出力コサイン 1.000

- reported: `{"rel_frobenius_error_mean": 0.000357, "rel_error_percent": 0.0357, "output_cosine_sim_mean": 1.0, "verdict": "PASS (fp16 SVD再構成は数値的にロスレスに近い)"}`
- artifact: `benchmarks/results/jgen_drift_check.json`
- notes: 0.000357 absolute ≈ 0.0357% which README rounds to 0.036%.

### G_structure_not_accuracy_booster: **SUPPORTED**

> 合議の価値は精度ブースターではなく媒体/制御にある (同一話者では router≈council)

- notes: Fair 501: council−router ≈ −0.2pt. NL85: vector−router ≈ +3.5pt (CI overlap); vector−NL ≈ +15.3pt.

## ライブ再検証

- intent: artifact 95% → live **90%** (40件, Qwen2.5-0.5B jgen)
- quality (別ブランチ監査): fair 4問で router/council/puzzle/HF solo 全て 100%。遅延は solo≪router≪council≪puzzle。
- 501問 / 85問フル再実行: 本クラウド 4vCPU では非現実的（council ~3分/問）。

## 限界

- 大型ベンチの detail.jsonl 欠落 → summary 整合性検証が主。
- ライブはモデル/エンジン/経路の差で数値が動きうる（intent 95→90）。
- 「ベクトルが速い」は **NL合議比** であり、router 単独比ではない（README 通り）。
