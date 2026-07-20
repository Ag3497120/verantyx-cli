# Verantyx Benchmarks

評議会の主張 (「ベクトル議論は単体ルーターより強い」「JGEN変換は劣化しない」「意図ルーティングは学習で改善する」) を
定量検証するためのベンチマーク一式です。以下の数値はすべて実際に実行した結果です (再現手順は各節参照)。

## 実測結果サマリ

### 0. 構造＋記憶 — 世代・サイズ跨ぎ (`numeric_logic_focus.jsonl`, 26問)

**問い**: 小さなモデルに company（ベクトル合議）＋永遠記憶を載せると、新世代で一回り大きい「素手」を超えられるか。  
条件: Hands/Dream/Audit OFF、`--no-secret --memorize`、エスカレーション off。データは四則・短い論理・首都の英語26問。

| 構成 | 正解率 | 平均秒 | 結果ディレクトリ |
|------|--------|--------|------------------|
| **Qwen2.5系 ~0.5B company + 記憶**（発話=0.5B router） | **80.8%** (21/26) | 15.2–15.8s | `post_fix_gemma4_vs_company_mem_focus26/`, `qwen35_2b_vs_company_mem_focus26/` |
| Qwen3.5:0.8B **solo** | **73.1%** (19/26) | 1.3s | `qwen35_08b_company_mem_vs_solo_focus26/` |
| Qwen3.5:0.8B company + 記憶（`--speaker-model ollama:qwen3.5:0.8b`） | **84.6%** (22/26) | 2.8s | 同上 |
| Qwen3.5:2B solo | **92.3%** (24/26) | 3.5s | `qwen35_2b_vs_company_mem_focus26/` |

- **跨ぎ勝ち**: 0.5B+構造+記憶 **80.8% >** 新世代 0.8B 素手 **73.1%**。  
  「古い小さめ＋構造」が「新しくて大きい素手」を上回った（プロジェクト主張の本筋）。
- **同サイズ上乗せ**: 0.8B 素手 73.1% → company+記憶+発話0.8B **84.6%**（+11.5pt）。
- **未達**: 同世代 2B 素手 92.3% には未到達。構造は床上げであり、大幅に大きい重みを常に超えるわけではない。
- 速度差の主因は確定ロック14問ではなく、非ロック発話が jgen 0.5B generate（平均~34s）→ Ollama 0.8B（平均~5s）に変わったこと。

再現（0.8B 発話＋solo）:

```bash
VERANTYX_ROLE_HANDS=0 VERANTYX_DREAM_AFTER_ASK=0 VERANTYX_AUDIT_AFTER_ASK=0 \
VERANTYX_CHRONO_DIR=/tmp/verantyx_chrono_bench \
python benchmarks/verantyx_bench.py \
  --dataset benchmarks/datasets/numeric_logic_focus.jsonl \
  --modes company,solo \
  --solo-model ollama:qwen3.5:0.8b \
  --speaker-model ollama:qwen3.5:0.8b \
  --no-escalate --no-secret --memorize \
  --out benchmarks/results/qwen35_08b_company_mem_vs_solo_focus26
```

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

### 1d. 6軸マトリョーシカ・パズル推論 (puzzle モード) — 30問比較 (`factual_qa.jsonl` 先頭30問)

**問い**: 役割 (Commander/Scout/Worker) の代わりに**概念軸** (Logic/Syntax/Factual/Temporal/Creativity/Consensus) で分化させ、
パズル接合 (適合性グラフで外れ軸を捨てる) と入れ子 (depth 2) を入れたら差は出るか。  
仕組み: 表層1フォワードで6軸エネルギーに分解 → ゲート通過軸だけが軸ディレクティブ付きで推論 →
軸間の適合行列 (隠れ空間cos × 分布重なり) で最大クラスタのみ接合 → 合意を仮想トークンとして再注入し depth 2 で繰り返し。
同一 0.5B・発話役は router 固定。条件: `--no-escalate`、結果: `benchmarks/results/puzzle_30/`

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 |
|--------|-----------------|-----------|-------------------|
| router | 93.3% [78.7–98.2] | 28/30 | **0.9s** / 0.3s / 1.9s |
| council (ベクトル評議会) | 93.3% [78.7–98.2] | 28/30 | 2.0s / 1.8s / 4.4s |
| puzzle (6軸マトリョーシカ) | 93.3% [78.7–98.2] | 28/30 | 1.5s / 1.4s / 3.0s |

- **正解率は3モード完全に同点 (28/30)**。発話役が同じなら精度は動かない、という節1の結論と一致する。
  個別差はある (fact_004 は router ✗ / council ✓ / puzzle ✓、fact_028 は router ✓ / council ✗ / puzzle ✗、fact_025 は3モードとも ✗) が、相殺して同点。
- **puzzle は council より約25%高速** (2.0s → 1.5s/問)。軸ゲートが効いており、30問中 **18問は3軸のみ**、11問は4軸、5軸以上は1問だった (5役割固定の council より前向きパスが少ない)。
- 一方この30問では、接合フェーズで**外れ軸が捨てられたケースは0件** (適合閾値 0.35 では全通過軸が接合された)。パズル接合の「切る」側の価値はこの規模・この問題集合では実証できていない。
- **誠実な解釈**: puzzle の価値は精度ブーストではなく、**分解 (どの軸にエネルギーを流すか) と接合 (どの意見を採用するか) を明示的な制御構造として持てる**こと。精度を上げたいなら発話モデルを大きくするのが効く、という結論は変わらない。

再現:

```bash
python3 benchmarks/verantyx_bench.py --modes router,council,puzzle \
    --max-items 30 --no-escalate --out benchmarks/results/puzzle_30
```

単発の観察 (軸エネルギー・接合ログの表示):

```bash
python3 verantyx_matryoshka.py --prompt "What planet is known as the Red Planet?" --depth 2
```

### 1e. 難易度上げ — logic / multihop / truthful (`hard_elevated.jsonl` 81問)

**問い**: 簡単な事実QA (ceiling ~93%) では差が出なかったので、論理・多段・トラップ系に寄せると
puzzle の差は見えるか。条件: `--no-escalate`・同一0.5B発話。結果: `benchmarks/results/puzzle_hard_elevated/`

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 |
|--------|-----------------|-----------|-------------------|
| router | 35.8% [26.2–46.7] | 29/81 | **5.8s** / 1.1s / 37.3s |
| council (ベクトル評議会) | 37.0% [27.3–47.9] | 30/81 | 9.0s / 2.3s / 40.3s |
| puzzle (6軸マトリョーシカ) | **42.0%** [31.8–52.8] | **34/81** | 9.7s / 1.8s / 40.0s |

カテゴリ別 (正答数):

| | logic (31) | multihop (30) | truthful (20) |
|--|------------|---------------|---------------|
| router | 4 (13%) | 13 (43%) | 12 (60%) |
| council | 4 (13%) | 14 (47%) | 12 (60%) |
| puzzle | 4 (13%) | **18 (60%)** | 12 (60%) |

- **puzzle − router = +6.2 pt** (29→34問)。CIはまだ重なるが、易しい事実QAの同点からは明らかに動いた。
- 差の本体は **multihop** (+5問 vs router, +4問 vs council)。logic / truthful は3モード同点寄りのまま。
- 接合の「外れ軸 drop」は依然 **0件**。効いているのは主に軸ゲート＋ディレクティブ分化＋入れ子側の可能性が高い。

**解釈**: 難易度を上げると差の方向は出る。ただし logic 天井は0.5B側。次は drop 閾値や multihop 追試。

再現:

```bash
python3 benchmarks/verantyx_bench.py \
    --modes router,council,puzzle \
    --dataset benchmarks/datasets/hard_elevated.jsonl \
    --no-escalate --out benchmarks/results/puzzle_hard_elevated
```

#### 1e補. puzzle 回帰修正 (`puzzle_fix_81`, 2026-07-13)

乖離パイプライン統合時、`puzzle` と `puzzle_div` が同一 `ask()` を共有していたため **旧 puzzle が 34.6% まで低下**していた。修正後に再測定。

**原因**
- 乖離交換・乖離連動 join 閾値・軸キャリア・レキシコン soft/概念注入が **旧 puzzle 本線にも適用**されていた
- `puzzle` / `puzzle_div` のベンチ分岐がインスタンス分離のみで、経路が同一だった

**修正** (`verantyx_matryoshka.py` / `verantyx_bench.py`)
- `ask(..., use_divergence=False)` = **旧 puzzle**: 固定 join 0.35、軸 index↑ 渡し順、レキシコン off、`context_soft = e[None,:]`
- `ask(..., use_divergence=True)` = **puzzle_div**: DivergencePacket + C/E/R/N、エネルギー降順、軸キャリア α=0.08、レキシコン on
- `join_threshold_for_divergence`: 乖離 ≤0.42 のとき BASE 0.35 のまま（低乖離での過剰厳格化を防止）

| モード | 正解率 (95% CI) | 正解/総数 | multihop |
|--------|-----------------|-----------|----------|
| router | 35.8% [26.2–46.7] | 29/81 | 43% (13/30) |
| **puzzle** (classic) | **42.0%** [31.8–52.8] | **34/81** | **60% (18/30)** |
| puzzle_div | 32.1% [22.9–42.9] | 26/81 | 33% (10/30) |

- **puzzle は `puzzle_hard_elevated` と同点 (34/81) に回復**。差の本体は再び multihop (+5問 vs router)。
- **puzzle_div は研究用経路** — 現設定では classic puzzle を下回る。乖離接合の効果は別ベンチ (`council_div`) で評価。

```bash
python3 benchmarks/verantyx_bench.py \
  --dataset benchmarks/datasets/hard_elevated.jsonl \
  --modes router,puzzle,puzzle_div --no-escalate --rounds 2 \
  --out benchmarks/results/puzzle_fix_81
```

### 1f. LongMemEval × 永遠の記憶 (公式データ・主張境界つき)

ランナー: `benchmarks/longmemeval_verantyx.py`  
検索: session 粒度・PromptEOL コサイン + bigram ハイブリッド（質問ごとインメモリ索引、グローバル記憶は汚さない）  
話者: Qwen2.5-0.5B ルーター  
採点: **containment ヒューリスティック**（公式 GPT-4o judge ではない）

| 条件 | n | タイプ偏り | session Recall@5 | QA (containment) | **QA (GPT-4o 公式)** |
|------|---|------------|------------------|------------------|----------------------|
| **oracle**（証拠セッションのみ索引） | 50 | 先頭50問がすべて temporal-reasoning | **99.7%** | 28.0% (14/50) | **6.0% (3/50)** |
| **S retrieval**（全 haystack ~48 session） | 50 | 先頭50問がすべて single-session-user | **20.0%** | 8.0% (4/50) | **4.0% (2/50)** |

結果ディレクトリ: `benchmarks/results/longmemeval_oracle_50/` / `longmemeval_s_50/`  
公式採点: LongMemEval `evaluate_qa.py gpt-4o`（結果は `hypothesis.jsonl.eval-results-gpt-4o`）

**主張してよいこと**
- oracle では証拠さえ索引すれば session 想起はほぼ完全（Recall@5 ≈ 100%）
- フル haystack（S）では現状ハイブリッド検索の Recall@5 は約20%で、ここがボトルネック
- **公式 GPT-4o 採点でも QA は oracle 6% / S 4%** — 0.5B 話者が証拠を読んでも答えを出せないケースが多い（"Sure, I can help" 等）
- containment ヒューリスティックは公式より甘い（oracle 28% vs 6%）

**主張してはいけないこと**
- 「公式 LongMemEval で高スコア／記憶が解けた」
- 「S を解けた」
- 先頭50問を全体代表とみなす（タイプが1種類に偏っている）
- containment スコアを公式スコアとして出す

公式 QA 評価に載せるなら:

```bash
# hypothesis.jsonl を用意したうえで (要 OPENAI_API_KEY)
cd cortex/benchmarks/LongMemEval
python3 src/evaluation/evaluate_qa.py gpt-4o \
  ../../../benchmarks/results/longmemeval_oracle_50/hypothesis.jsonl \
  data/longmemeval_oracle.json
```

再現:

```bash
python3 benchmarks/longmemeval_verantyx.py --split oracle --max-items 50 \
  --out benchmarks/results/longmemeval_oracle_50
python3 benchmarks/longmemeval_verantyx.py --split s --max-items 50 --topk 5 \
  --out benchmarks/results/longmemeval_s_50
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

> **指標分離 (必須):** ルーティング accuracy ≠ QA 正答率。  
> routing の正本は `benchmarks/intent_router_eval.py`（`intent_routing.jsonl`）。  
> QA / 熟議は `verantyx_bench.py`。両者を混ぜて報告しない。  
> 詳細公理: `docs/ROUTER_DIVERGENCE_PLAN.md`。

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

### 主張境界 (divergence / puzzle パイプライン)

- **主張してよい:** 構造（独立 R0・乖離交換・軸渡し順・接合）は探索と誤り検出を改善しうる。
- **主張してはいけない:** 構造が世界知識を増やす / routing accuracy が QA を意味する。
- `plan_steal` / 大型 escalate は **別経路**（一時フォールバック）。fair 0.5B 比較では off。
- モード `council_div` / `puzzle_div`: escalate off + `force_router_speaker` の乖離パイプライン測定用。
- モード `puzzle` (classic) と `puzzle_div` は **別経路** (`use_divergence=False|True`)。混同しないこと。

#### フル結果 (`div_pipeline_81`, hard_elevated 81問, 2026-07-12)

条件: `--no-escalate --rounds 2`、`force_router_speaker=true`（`--no-escalate` が含意）、同一 0.5B 発話。  
結果: `benchmarks/results/div_pipeline_81/`

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50/p95時間 |
|--------|-----------------|-----------|-------------------|
| router | 35.8% [26.2–46.7] | 29/81 | 5.1s / 0.8s / 33.7s |
| council_div | **39.5%** [29.6–50.4] | 32/81 | 6.2s / 2.2s / 36.3s |
| puzzle_div | 32.1% [22.9–42.9] | 26/81 | 8.7s / 1.9s / 36.0s |

| モード | logic | multihop | truthful |
|--------|--------|----------|----------|
| router | 13% (4/31) | 43% (13/30) | 60% (12/20) |
| council_div | 16% (5/31) | 50% (15/30) | 60% (12/20) |
| puzzle_div | 16% (5/31) | 33% (10/30) | 55% (11/20) |

- **council_div − router: +3.7pt**（32 vs 29）。CI は大きく重複 → **探索的差・確定主張にはまだ足りない** (n=81 でも Wilson 幅 ~20pt)。
- puzzle_div は router を下回った (−3.7pt)。構造が常に勝つわけではない。
- escalate / plan_steal は off。構造 ≠ 世界知識の増幅。
- スモーク (先頭15, `div_pipeline_smoke/`): council_div 60% / router 47% / puzzle_div 33% — 方向はフルと整合だが n が小さい。

```bash
python3 benchmarks/verantyx_bench.py \
  --dataset benchmarks/datasets/hard_elevated.jsonl \
  --modes router,council_div,puzzle_div --no-escalate --rounds 2 \
  --out benchmarks/results/div_pipeline_81
```

#### 0.5B 構造 vs 単体 4B/9B (`solo_4b` / `solo_9b`)

**位置取り用** — 「0.5B+構造 = 9B」とは主張しない。同一データセット・同一採点で、単発生成の大型モデルと比較する。

| モード | model | acc | notes |
|--------|-------|-----|-------|
| router | 0.5B | 35.8% (29/81) | escalate off・発話 router 固定 |
| council_div | 0.5B | 39.5% (32/81) | 同上 |
| puzzle_div | 0.5B | 32.1% (26/81) | 同上 |
| solo_4b | ~4B (単発) | **未計測** | モデル未インストール — `benchmarks/results/solo_4b9b_81/solo_4b_blocked.md` |
| solo_9b | Ornith-1.0-9B (単発) | **91.4%** (74/81) [83.2–95.8] | council/escalate/plan_steal なし・thinking off |

- **位置取り**: 同一 hard_elevated で solo_9b は 0.5B+構造を大きく上回る (+52pt vs council_div)。これは「0.5B+構造 = 9B」の反証に近く、構造は知識増幅ではないという境界と整合。
- solo_9b カテゴリ: logic 84% / multihop 93% / truthful 100%。結果: `benchmarks/results/solo_4b9b_81/`

モデル解決順: `--solo-model` → `VERANTYX_SOLO_4B` / `VERANTYX_SOLO_9B` → ローカル/HFキャッシュ探索 → Ollama タグ。

```bash
# 9B (Ornith が local_weights / HF cache にあれば自動検出)
HF_HUB_OFFLINE=1 python3 benchmarks/verantyx_bench.py \
  --dataset benchmarks/datasets/hard_elevated.jsonl \
  --modes solo_9b --out benchmarks/results/solo_4b9b_81

# 4B が無い場合は明示指定が必要 (例):
#   export VERANTYX_SOLO_4B=Qwen/Qwen3-4B-Instruct
#   # または ollama pull qwen3:4b 後:
#   python3 benchmarks/verantyx_bench.py --modes solo_4b --solo-model ollama:qwen3:4b ...
#   # 任意サイズ:
#   python3 benchmarks/verantyx_bench.py --modes solo --solo-model /path/to/model ...
```

既定探索候補: 4B=`Qwen/Qwen3-4B-Instruct` / `Qwen/Qwen2.5-3B-Instruct`；9B=`deepreinforce-ai/Ornith-1.0-9B`（本機では HF スナップショット検出済み）。

#### 拡張難問セット (`hard_elevated_plus`, 131問)

`hard_elevated.jsonl` 81問 + 追加50問（より難しめの logic / multihop / truthful）。  
再測定: `benchmarks/results/div_pipeline_plus/`（router / council_div / puzzle_div、escalate off・`force_router_speaker`）。

| モード | 正解率 (95% CI) | 正解/総数 | 平均/p50時間 |
|--------|-----------------|-----------|--------------|
| router | 34.4% [26.8–42.8] | 45/131 | 3.5s / 0.8s |
| council_div | **36.6%** [28.9–45.2] | 48/131 | 5.4s / 2.2s |
| puzzle_div | 34.4% [26.8–42.8] | 45/131 | 6.8s / 1.8s |

- council_div − router: **+2.3pt**（CI 重複・探索的）。n=81 の方向 (+3.7pt) と整合。
- 追加50問だけの粗分割: 新設カテゴリは 0.5B にとって更に難しく（例: router `logic_plus` 30% / `multihop_plus` 28% / `truthful_plus` 42%）、全体正答率は 81問時よりやや低下。

```bash
python3 benchmarks/verantyx_bench.py \
  --dataset benchmarks/datasets/hard_elevated_plus.jsonl \
  --modes router,council_div,puzzle_div --no-escalate --rounds 2 \
  --out benchmarks/results/div_pipeline_plus
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
| `nl_council` | 自然言語で役割が意見交換 (媒体比較用・同一0.5B) |
| `puzzle` | 6軸マトリョーシカ・パズル推論 (同一0.5B・depth2、**classic 本線**・乖離交換なし) |
| `council_div` | 乖離パケット交換 + C/E/R/N (escalate off 想定・同一0.5B) |
| `puzzle_div` | マトリョーシカ + 乖離接合連動 (escalate off 想定・同一0.5B・研究用) |
| `solo_4b` / `solo_9b` | 単体 ~4B / ~9B 生成（評議会・escalate・plan_steal なし） |
| `solo` | 任意モデル単体（`--solo-model` 必須） |

`--no-escalate` を付けると 0.5B のみで公平比較できます (ワーカー/9B/外部bridgeを招集しない)。
`--repeat N` で同じ問題を N 回繰り返し、分散・再現性を確認できます。

## データセット

| ファイル | 内容 |
|---|---|
| `datasets/factual_qa.jsonl` | 事実・数値・論理など 85問 (パイロット) |
| `datasets/factual_qa_500.jsonl` | 決定論生成の501問 (fact/numeric/logic/multihop/truthful/日中韓) — 本線 |
| `datasets/hard_subset.jsonl` | `factual_qa.jsonl` から論理/多段推論のみ抜粋した10問 (エスカレーション比較用) |
| `datasets/hard_elevated.jsonl` | logic+multihop+truthful 81問 (puzzle / div 難易度上げ比較用) |
| `datasets/hard_elevated_plus.jsonl` | 上記81 + 追加50問 (計131: より難しめの logic/multihop/truthful) |
| `datasets/intent_routing.jsonl` | 意図ルーティング (task/chat) の40件ラベル付きコーパス |

独自 JSONL を `--dataset` で指定可能。形式:

```json
{"id": "q1", "question": "...", "answers": ["gold1", "gold2"], "type": "fact|numeric", "lang": "en|ja"}
```

`id` の接頭辞 (`fact_`, `logic_`, `multihop_`, `truthful_`, `ja_`, `zh_`, `ko_`) がカテゴリ集計に使われます。

## スクリプト一覧

| スクリプト | 検証対象 |
|---|---|
| `verantyx_bench.py` | router/council/puzzle の正解率・時間・メモリ (Wilson score 95% CI つき) |
| `../verantyx_matryoshka.py` | 6軸マトリョーシカ・パズル推論の本体 (`puzzle` モードの実装、単発CLIあり) |
| `jgen_drift_check.py` | JGEN変換 (SVDロスレス) の重み再構成誤差 (torch/Rust不要、numpyのみ) |
| `intent_router_eval.py` | 意図ルーティング (`intent_router.route`) の分類精度・混同行列 |
| `scoring.py` | 採点ロジック (正規化・数値抽出・Wilson CI・パーセンタイル) の共通ユーティリティ |
| `codec_roundtrip.py` | Phase 1: 最終層 Read/Write 半コーデック (dist ↔ encode_soft) |
| `codec_lexicon_gate.py` / `../concept_lexicon.py` | Phase 2: 命題レキシコン + Write→Read 再現ゲート (≥70%) |
| `../tests/test_codec_layers.py` | Phase 3: 中間層 FFI (`encode_layers` / `inject_at_layer`) スモーク |
| `codec_suite.py` | Phase 4: 層×領域の再構成スイート (主張境界つきレポート) |
| `longmemeval_verantyx.py` | LongMemEval × 永遠の記憶。`--qa-modes prompt,codec_write` で Phase 5 A/B |
| `longmemeval_codec_ab.py` | Phase 5 専用 A/B (prompt vs Write コーデック、主張境界つき) |

## 既知の限界 (誇張しない)

- 発話役を揃えた公平条件では、評議会 vs ルーターの差は事実上ゼロ (差1問、CI重複)。熟議単体では正解率は上がらず、
  精度向上には大型の発話モデルが必要というのが現時点の結論。意図ルーティング (40件) や
  JGEN drift (28テンソル) はまだ小サンプル。日本語・韓国語の事実知識の弱さは残課題。
- エスカレーション onのベンチはこのマシンの RAM 帯 (8GBバジェット) でのみ計測。
  もっと RAM がある環境やbridgeが常駐している環境では別の結果になる。
- JGEN drift check は Qwen2.5-0.5B-Instruct の28テンソルのみ。MoE モデル (ornith-1.0-35b,
  gemma4-26b) の drift 検証は未実施 (lexicon専用のため通常のSVD経路を通らない層がある)。
- GSM8K / TruthfulQA 公式データセットとの連携は未実装 (自作の模倣データセットで代替)。

## 隠れ状態 ⇔ 英語コーデック (主張境界つき)

対象: 常駐 Qwen2.5-0.5B / JGEN (`RustBrain`)。GPT-2 BABEL の移植ではない。  
最終層隠れ状態 ⇔ 短い英語命題の **計測可能な** Read/Write。永遠の記憶 / LongMemEval QA とは **指標を分離** する。

### デュアルゲート (混同しない)

| Gate | 意味 | 主な指標 |
|------|------|----------|
| `lexicon_only` | 辞書 Write→Read NN（フォワード不要） | `hold_acc` / Write→Read reproduce (≥70%, stretch 75–80%) |
| `forward_roundtrip` | encode / soft / inject / Write→forward→Read | soft_keyword_hit / proposition_match + Wilson CI |

### Sprint マップ

| Sprint | スクリプト | 内容 |
|--------|-----------|------|
| M1–R1 | `codec_suite.py` / `verantyx_codec.py` | デュアルゲート、hybrid Read、層 FFI スモーク |
| W1–L2 | `codec_suite.py --inject-ab` | Write ルータ、inject A/B、forward Read、層スイープ |
| M3 | `datasets/codec_propositions.jsonl` | ~500 命題 (factual/attribute/relation) + 再学習 |
| W4/P1–P3 | `concept_lexicon_schema.md` / `codec_slot_templates.json` / `codec_package_reproduce.py` | E2E forward、スキーマ、スロット文法、一括再現 |
| L3 | `--save-layer-routing` / `--use-layer-routing` | domain→best inject layer |

データ: `datasets/codec_propositions.jsonl` (~500 命題)。スロット文法: `datasets/codec_slot_templates.json`。  
スキーマ: `datasets/concept_lexicon_schema.md`。コア: `verantyx_codec.py` / `concept_lexicon.py`。  
評議会/マトリョーシカのレキシコン接続は `VERANTYX_CODEC=0` で無効化できる (既定オン、npz があるとき)。

**主張してよいこと**
- 計測範囲内での round-trip cosine・top-k 重なり・レキシコン再現率・層別 dump/inject の数値
- 「半コーデック (語彙分布インターリンガ + 命題辞書)」という位置づけ
- `lexicon_only` と `forward_roundtrip` を分けて報告すること
- LongMemEval A/B は「証拠の載せ方」比較であり、公式 QA スコアではない

**主張してはいけないこと**
- BABEL 級の全層・任意文・100% 再構成 / テレパシー / BABEL 94.7% との同列比較
- LongMemEval / 永遠の記憶の成功をコーデック成功と混同すること
- コーデックを QA 精度ブースターと呼ぶこと
- `C_valve` Identity をコーデック完成と呼ぶこと
- 安全回避・jailbreak 用途 (本 API は制御研究用)

再現:

```bash
# 一括 (推奨): 既存 lexicon + suite smoke
python3 benchmarks/codec_package_reproduce.py --max-items 20

# フル再学習 (~500) + suite
python3 benchmarks/codec_package_reproduce.py --train --max-items 30

# Phase 1 round-trip
python3 benchmarks/codec_roundtrip.py --max-items 20 \
    --out benchmarks/results/codec_p1_smoke

# lexicon_only ゲート
python3 concept_lexicon_trainer.py --holdout-ratio 0.20
python3 concept_lexicon.py --eval --gate 0.70

# 層 FFI スモーク (合成モデル)
JCROSS_GPU=0 python3 tests/test_codec_layers.py
# 本番エンジン: cargo build --release --manifest-path jcross_engine_glm/Cargo.toml
# JCROSS_LIB で dylib を明示可能。探索は jcross_engine_glm/target/release と
# repo/target/release (symlink) の両方。

# デュアルゲート suite (L2 quartile + L3 routing 保存)
python3 benchmarks/codec_suite.py --max-items 30 --layer-mode quartile \
    --inject-ab --save-layer-routing \
    --out benchmarks/results/codec_suite

# L3 routing を Write に適用
python3 benchmarks/codec_suite.py --max-items 20 --use-layer-routing \
    --out benchmarks/results/codec_suite_routed

# LongMemEval A/B (別指標 — 混ぜない)
python3 benchmarks/longmemeval_codec_ab.py --split oracle --max-items 10 \
    --out benchmarks/results/codec_ab_oracle_smoke
```

コーデック結果は `benchmarks/results/codec_*`。記憶ベンチは `longmemeval_*`。混ぜない。

## 次のステップ

- GSM8K / TruthfulQA の公式 HF データセット連携
- MoE (lexicon) モデルの drift check 対応
- RAMに余裕がある環境でのエスカレーション trade-off 再計測
- `Council.ask` に評議会全体の経過時間デッドラインを実装 (現状は1呼び出し単位の90秒キャップのみ)
- コーデック: forward soft_keyword を 40–50% 帯へ、層別 mini-lexicon (L4) の選択的導入
