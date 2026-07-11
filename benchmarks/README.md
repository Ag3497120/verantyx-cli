# Verantyx Benchmarks

評議会の主張 (「ベクトル議論は単体ルーターより強い」「JGEN変換は劣化しない」「意図ルーティングは学習で改善する」) を
定量検証するためのベンチマーク一式です。以下の数値はすべて実際に実行した結果です (再現手順は各節参照)。

## 実測結果サマリ

### 1. 評議会 vs 単体ルーター — 501問スケール (`factual_qa_500.jsonl`, エスカレーション off)

**発話役を router と同じ 0.5B に固定した公平条件** (`force_router_speaker`, `benchmarks/results/main_run_500_fair/`):

| モード | 正解率 (95% CI) | 平均/p50/p95時間 | 摂動復帰率 |
|--------|-----------------|-------------------|------------|
| router (0.5B単体) | 52.5% [48.1–56.8] | 4.5s / 1.6s / 31.3s | — |
| council (評議会+摂動) | 52.3% [47.9–56.6] | 7.0s / 3.2s / 34.1s | (esc off) |
| council_no_perturb | 52.3% [47.9–56.6] | 6.4s / 2.6s / 33.5s | — |

- **council − router: −0.2pt (263 vs 262、差1問)**。信頼区間はほぼ完全に重複する。
  発話モデルが同じなら、ベクトル熟議は正解率をほとんど動かさず、時間だけ +2.5s/問 増える。
- **正しい結論**: 精度を上げたいなら熟議の往復ではなく、**発話役をより大きなモデルにする**のが効く。
  評議会の価値は「単体では出ない正解を出す」ことではなく、大型話者を呼ぶ判断・収束・摂動での脆さ検出にある。
- **日本語・韓国語は依然弱い** (router/council とも ja 3〜13% / ko 10%)。多言語事実知識の限界は隠さない。

| モード | fact | ja | ko | logic | multihop | numeric | truthful | zh |
|---|---|---|---|---|---|---|---|---|
| router | 76% | 3% | 10% | 35% | 41% | 52% | 60% | 90% |
| council | 78% | 13% | 10% | 30% | 45% | 50% | 60% | 80% |
| council_no_perturb | 77% | 13% | 10% | 31% | 45% | 50% | 60% | 80% |

> ⚠️ **撤回した過去の主張 (2026-07-11 に訂正)**: 以前この節には「council **75.2%** vs router 52.5% = **+22.7pt**, CI分離」と書いていました。これは**不公平**でした。`--no-escalate` を付けても `Council.ask` が発話役を Qwen2.5-0.5B ワーカーへ自動昇格しており、実質「0.5B router vs 0.5B別モデルの話者」を比較していたためです。`force_router_speaker` (発話役を router と同一に固定) を追加して測り直したところ、差は消えました。旧結果 `benchmarks/results/main_run_500/` は不公平ラベル付きで保持しています。

再現:

```bash
python benchmarks/verantyx_bench.py --dataset benchmarks/datasets/factual_qa_500.jsonl \
    --modes router,council,council_no_perturb --no-escalate \
    --out benchmarks/results/main_run_500_fair
# --no-escalate は force_router_speaker を含意し、全モードで発話役を 0.5B router に固定します
```

<details><summary>参考: 85問パイロット (2026-07-10)</summary>

| モード | 正解率 (95% CI) |
|--------|-----------------|
| router | 60.0% [49.4–69.8] |
| council | 72.9% [62.7–81.2] (+12.9pt, CI重複) |

</details>

### 1c. 媒体比較 — 自然言語評議会 vs ベクトル評議会 (`factual_qa.jsonl` 85問)

**問い**: 同じ 0.5B・同じ役割数で、議論の媒体だけ変えたとき差は出るか。  
条件: `--no-escalate --rounds 2`、発話役は router 固定。結果: `benchmarks/results/nl_vs_vec_85/`

| モード | 正解率 (95% CI) | 平均/p50時間 | コスト |
|--------|-----------------|--------------|--------|
| router | 60.0% [49.4–69.8] | 7.0s / 2.3s | 生成1回 |
| council (ベクトル) | **63.5%** [52.9–73.0] | 8.8s / 3.9s | 隠れ状態交換 |
| nl_council (自然言語) | 48.2% [37.9–58.7] | **19.7s** / 17.1s | 平均 **13回**生成 / ~1616文字 |

- **vector − NL: +15.3pt**。NL の CI は router ともほぼ重ならず、**テキスト熟議は同一0.5Bでは悪化**した。
- vector − router: +3.5pt（CI 重複・有意差なし）。媒体比較ではベクトル側が NL より明らかに良い。
- NL は時間が約 **2.2×**（対 vector）、生成回数が桁違いに多い。0.5B では意見テキストがノイズ化し、合意が崩れる解釈が妥当。

解釈: 「評議会の価値」を測るなら NL vs ベクトルの比較が本筋。この規模では **ベクトル熟議は NL 熟議より正答率・コストとも優位**。正答率が router と並ぶのは「同じ話者」制約下では既知。

再現:

```bash
HF_HUB_OFFLINE=1 python benchmarks/verantyx_bench.py \
    --dataset benchmarks/datasets/factual_qa.jsonl \
    --modes router,council,nl_council --no-escalate --rounds 2 \
    --out benchmarks/results/nl_vs_vec_85
```

### 1b. (旧) 85問パイロット — 上記に統合済み

再現 (小規模):

```bash
python benchmarks/verantyx_bench.py --modes router,council,council_no_perturb --no-escalate \
    --out benchmarks/results/main_run
```

### 2. エスカレーション on/off のトレードオフ (`hard_subset.jsonl`, 論理/多段推論10問)

| 設定 | 正解率 | 時間/問 |
|------|--------|---------|
| escalation off (0.5B council のみ) | 80.0% (8/10) | 5.6s |
| escalation on (HF Sage / bridge 招集を許可) | (下記参照、途中で打ち切り) | 1問目 154s / 2問目 174s / **3問目は1000秒超で応答なしのため強制終了** |

このマシン (RAM budget 8GB) では、HF Sage (19GB必要) は `MemoryGuard` に
`必要19.0GB + 余白3GB > 空き8.0GB` として **正しく拒否**される。1〜2問目は
jgen ワーカーへの追加ラウンド等で 1問あたり **150〜180秒** に増える (off比で約30倍)。
**3問目では1000秒 (17分) を超えても完了しなかったため計測を中断した** (CPU使用率が
ほぼ0%のまま停滞)。原因は未確定だが、コード上 `verantyx_bridges.py` のHTTPタイムアウトが
LM Studio 向けに180秒 (2段階呼び出しで最大2回)、Ollama 向けに600秒と長く設定されており、
外部サーバーが実際に稼働していて低速な応答を返す場合、これらのタイムアウトの合計まで
評議会全体がブロックされ得る構造になっている (「フリーズ」ではなく極端に長い待ちである可能性が高い)。
これは**上限を持つ全体デッドラインが存在しない**という設計上のギャップであり、そのまま報告する。
このベンチ実行を受けて、`verantyx.config.json` に **`escalation.bridge_timeout_s` (既定90秒)**
を追加し、外部サーバーへの1呼び出しあたりの上限をこの値でキャップするよう修正した
(`verantyx_bridges.py: _post`)。修正後に同じベンチを再実行したところ、1〜2問目は同様に
150〜160秒で完了したが、**3問目は90秒キャップ適用後も400秒超まで完了せず、時間切れで中断した**。
つまり1呼び出しの上限は効いているが、複数ラウンド × 複数呼び出しの累積時間まではキャップされて
おらず、難しい問題では依然として評議会全体が長時間占有される。**恒久対応ではなく緩和策**であり、
正しい修正には「評議会全体の経過時間デッドライン」を `Council.ask` 側に持たせる必要がある
(未実装、次の優先課題としてバックログに記録)。
**推奨: 手元で bridge (LM Studio/Ollama) の応答速度を確認していない限り、エスカレーションは
`--no-escalate` あるいは `escalation.enabled=false` で運用する。**

再現:

```bash
python benchmarks/verantyx_bench.py --dataset benchmarks/datasets/hard_subset.jsonl \
    --modes council --no-escalate --out benchmarks/results/escalation_off
python benchmarks/verantyx_bench.py --dataset benchmarks/datasets/hard_subset.jsonl \
    --modes council --out benchmarks/results/escalation_on
```

### 3. JGEN変換の重み再構成誤差 (SVDロスレス変換の検証)

`qwen2.5-0.5b-worker` (元: `Qwen/Qwen2.5-0.5B-Instruct`, BF16 safetensors) について、
4層 (先頭・中間・末尾を含む) × 7種の線形層、計28テンソルを検証。

| 指標 | 値 |
|------|-----|
| 相対フロベニウスノルム誤差 (平均) | **0.0357%** |
| 相対フロベニウスノルム誤差 (最大) | 0.0369% |
| ランダム入力に対する出力コサイン類似度 (平均/最小) | **1.000000 / 1.000000** |

誤差の原因は fp16 量子化のみ (SVD自体はフルランクなので理論上ロスレス)。
`torch` もRustエンジンも起動せず、numpy だけで元の safetensors (BF16, 手動bit変換) と
`.jgen` の U・S・V を直接比較しているため、変換パイプライン全体を通した「本当の」再構成誤差である。

再現:

```bash
python benchmarks/jgen_drift_check.py \
    --safetensors <Qwen2.5-0.5B-InstructのHFキャッシュディレクトリ> \
    --jgen converted_models/qwen2.5-0.5b-worker_full.jgen
```

### 4. 意図ルーティング (task/chat) の分類精度

`intent_routing.jsonl` (40件、意図的に事実質問とタスク依頼を混在させた擬似コーナーケース集) で評価。

| 指標 | 値 |
|------|-----|
| 正解率 | **95.0%** (38/40) |
| task の precision / recall / F1 | 92.3% / 100% / 96.0% |
| 誤判定 (2件) | 事実質問寄りの短文が `task` に誤分類 (fp) — factoid補正の閾値調整が今後の課題 |
| 経路別内訳 | hard_task_hint 15件 / anchor(時間) 4件 / 0.5B分類 21件 |

反射 (`RouterReflex`) は意図的に無効化して評価 (`--no-reflex`)。本番ではユーザー訂正を
学習して精度がさらに上がる設計だが、今回は「学習前の素の分類器」の実力を測っている。

再現:

```bash
python benchmarks/intent_router_eval.py --no-reflex
```

## クイックスタート

```bash
cd verantyx-cli
source .venv/bin/activate

# スモーク (3問 × 3モード、1分程度)
python benchmarks/verantyx_bench.py --max-items 3 --modes router,council,council_no_perturb --no-escalate

# フル実行 (factual_qa.jsonl 85問 × 3モード、エスカレーションoffで約20分)
python benchmarks/verantyx_bench.py --modes router,council,council_no_perturb --no-escalate

# 結果は benchmarks/results/<出力先>/ に出力
#   summary.json  — 正解率・信頼区間・p50/p95時間・カテゴリ別・摂動復帰率
#   detail.jsonl  — 1試行1行 (再分析用)
#   report.md     — 人間可読サマリ
```

## 比較モード

| モード | 内容 |
|--------|------|
| `router` | 0.5B ルーターが評議会なしで直接回答 |
| `council` | 5役割ベクトル評議会 + 摂動テスト (本番相当) |
| `council_no_perturb` | 評議会だが摂動テスト off (アブレーション) |

`--no-escalate` を付けると 0.5B のみで公平比較できます (ワーカー/9B/外部bridgeを招集しない)。
`--repeat N` で同じ問題を N 回繰り返し、分散・再現性を確認できます。

## データセット

| ファイル | 内容 |
|---|---|
| `datasets/factual_qa.jsonl` | 事実・数値・論理など 85問 (パイロット) |
| `datasets/factual_qa_500.jsonl` | 決定論生成の501問 (fact/numeric/logic/multihop/truthful/日中韓) — 本線 |
| `datasets/hard_subset.jsonl` | `factual_qa.jsonl` から論理/多段推論のみ抜粋した10問 (エスカレーション比較用) |
| `datasets/intent_routing.jsonl` | 意図ルーティング (task/chat) の40件ラベル付きコーパス |

独自 JSONL を `--dataset` で指定可能。形式:

```json
{"id": "q1", "question": "...", "answers": ["gold1", "gold2"], "type": "fact|numeric", "lang": "en|ja"}
```

`id` の接頭辞 (`fact_`, `logic_`, `multihop_`, `truthful_`, `ja_`, `zh_`, `ko_`) がカテゴリ集計に使われます。

## スクリプト一覧

| スクリプト | 検証対象 |
|---|---|
| `verantyx_bench.py` | router/council の正解率・時間・メモリ (Wilson score 95% CI つき) |
| `jgen_drift_check.py` | JGEN変換 (SVDロスレス) の重み再構成誤差 (torch/Rust不要、numpyのみ) |
| `intent_router_eval.py` | 意図ルーティング (`intent_router.route`) の分類精度・混同行列 |
| `scoring.py` | 採点ロジック (正規化・数値抽出・Wilson CI・パーセンタイル) の共通ユーティリティ |

## 既知の限界 (誇張しない)

- 発話役を揃えた公平条件では、評議会 vs ルーターの差は事実上ゼロ (差1問、CI重複)。熟議単体では正解率は上がらず、
  精度向上には大型の発話モデルが必要というのが現時点の結論。意図ルーティング (40件) や
  JGEN drift (28テンソル) はまだ小サンプル。日本語・韓国語の事実知識の弱さは残課題。
- エスカレーション onのベンチはこのマシンの RAM 帯 (8GBバジェット) でのみ計測。
  もっと RAM がある環境やbridgeが常駐している環境では別の結果になる。
- JGEN drift check は Qwen2.5-0.5B-Instruct の28テンソルのみ。MoE モデル (ornith-1.0-35b,
  gemma4-26b) の drift 検証は未実施 (lexicon専用のため通常のSVD経路を通らない層がある)。
- GSM8K / TruthfulQA 公式データセットとの連携は未実装 (自作の模倣データセットで代替)。

## 次のステップ

- データセットを100→500問規模に拡張し、信頼区間を狭める
- GSM8K / TruthfulQA の公式 HF データセット連携
- MoE (lexicon) モデルの drift check 対応
- RAMに余裕がある環境でのエスカレーション trade-off 再計測
- `Council.ask` に評議会全体の経過時間デッドラインを実装 (現状は1呼び出し単位の90秒キャップのみ)
