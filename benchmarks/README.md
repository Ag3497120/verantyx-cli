# Verantyx Benchmarks

評議会の主張を定量検証するためのベンチマーク一式です。

## クイックスタート

```bash
cd verantyx-cli
source .venv/bin/activate   # または既存の Python 環境

# スモーク (2問 × 2モード、約5〜15分)
python benchmarks/verantyx_bench.py --max-items 2 --modes router,council --no-escalate

# フル実行 (20問 × 3モード、数時間かかります)
python benchmarks/verantyx_bench.py --no-escalate

# 結果は benchmarks/results/<timestamp>/ に出力
#   summary.json  — 正解率・平均時間・摂動復帰率
#   detail.jsonl  — 1試行1行 (再分析用)
#   report.md     — 人間可読サマリ
```

## 比較モード

| モード | 内容 |
|--------|------|
| `router` | 0.5B ルーターが評議会なしで直接回答 |
| `council` | 5役割ベクトル評議会 + 摂動テスト (本番相当) |
| `council_no_perturb` | 評議会だが摂動テスト off (アブレーション) |

`--no-escalate` を付けると 0.5B のみで公平比較できます (ワーカー/9B を招集しない)。

## データセット

- `datasets/factual_qa.jsonl` — 事実・算数・論理 20問 (日英混在)
- 独自 JSONL を `--dataset` で指定可能。形式:

```json
{"id": "q1", "question": "...", "answers": ["gold1", "gold2"], "type": "fact|numeric", "lang": "en|ja"}
```

## 次のステップ (未実装)

- GSM8K / TruthfulQA の HF データセット連携
- 異モデル間インターリンガ (0.5B + bridge) の条件
- 統計的有意性 (bootstrap CI)
