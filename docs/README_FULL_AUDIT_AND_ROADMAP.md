# README 全面検証・ベクトル有用性分析・次アクション

Generated: 2026-07-19T12:43:06.268845
Host: Apple M5 Metal · router=`qwen2_5_0_5b_router` (from Ollama `qwen:0.5b`) · branch=`cursor/readme-claim-audit-64b8`

## 1. 総合判定

| 層 | 判定 |
|---|---|
| 定量ベンチ数値 (README 本文) | **SUPPORTED** — コミット済み summary と一致。盛っていない |
| 製品構造・ファイル配置 | **SUPPORTED** (33中31) |
| 前提 Python 3.10+ | **PARTIAL** — この Mac は 3.9.6 でも動作したが、README 主張とは不一致 |
| LongMemEval 数値 (benchmarks/README) | **UNVERIFIABLE here** — 結果ディレクトリがリポジトリに無い |
| 永遠の記憶 (ライブ) | **SUPPORTED (限定)** — 刻印→検索は成功 (score≈0.65)。多ターン活用は別問題 |
| Metal 実行可能性 | **SUPPORTED** — council スモーク 11.2s で正解 |

## 2. README 定量主張の突合

| 主張 | 成果物 | 判定 |
|---|---|---|
| fair 501: router 52.5% ≈ council 52.3% | `main_run_500_fair` | SUPPORTED |
| 旧 +22.7pt は不公平・撤回 | `main_run_500` (75.2%) | SUPPORTED |
| vector vs NL: +15.3pt / ~半時間 | `nl_vs_vec_85` | SUPPORTED |
| puzzle30 同点 28/30 | `puzzle_30` + detail | SUPPORTED |
| intent 95% (40) | artifact + **Metal live 95%** | SUPPORTED |
| JGEN 0.036% / cos 1.0 | `jgen_drift_check` | SUPPORTED |
| 構造≠精度ブースター | fair501 + puzzle30 | SUPPORTED |

補足 (README 本文には無いが benches にあり、解釈に重要):
- hard_elevated 81問: puzzle 42.0% > council 37.0% > router 35.8% (CI重なり、multihop で差)
- puzzle_div は classic より悪化 (研究経路)

## 3. ベクトル有用性の分析

### 3.1 何に効くか (証拠あり)

1. **媒体としての優位 (対 NL 合議)**  
   同一 0.5B で nl_council 48.2% / 19.7s vs vector 63.5% / 8.8s。  
   テキスト往復は 0.5B ではノイズ化し、**壊れにくい内部合意チャネル**としてベクトルが勝つ。

2. **制御・観測可能性**  
   Divergence / 軸エネルギー / 適合行列など、テキストログでは取りづらい幾何的指標を持てる。  
   「正しさの証明」ではないが、**いつ話者を替えるか・いつ諦めるか**のセンサーになりうる。

3. **永遠の記憶の搬送形式**  
   ライブで marker 刻印→検索ヒット。窓に載せなくても再起動後に近い検索は可能 (設計意図と一致)。

4. **コスト構造 (対 NL)**  
   NL は平均13回生成。ベクトルは隠れ状態交換中心で生成回数が桁違いに少ない。

### 3.2 何に効かないか (証拠あり)

1. **同一話者での正答率ブースト**  
   fair 501: −0.2pt。puzzle30: 完全同点。精度の本体は発話役。

2. **易しい事実QAでの puzzle 接合の「切る」価値**  
   drop=0件。接合フィルタは未実証。

3. **長期想起→正答**  
   LongMemEval (docs上): oracle Recall@5≈100% でも GPT-4o QA 6%。  
   検索が良くても 0.5B 話者が答えを出せない。記憶のボトルネックは retrieval と generation の両方。

4. **遅延税**  
   Metal でも council > router。クラウドCPUでは数分/問。常時評議会は UX を壊す。

### 3.3 一文での結論

> **ベクトルは「0.5Bを賢くする魔法」ではなく、「壊れたテキスト合議の代替媒体」と「制御・記憶の配線」である。**  
> 精度を上げるレバーは発話役。ベクトルのレバーはコスト・安定性・観測・記憶・ルーティング判断。

## 4. README の「限界」節との整合

| README 限界 | 検証からの評価 |
|---|---|
| 0.5B 言語能力は低い | 支持 (ja/ko 低正答、LongMem QA 低) |
| ベクトル合意≠正しさ | 支持 (幾何収束と正答は分離) |
| 全体締切未実装 | 未ライブ検証だがコード主張として妥当 |
| 長期忘れベンチはこれから | **緊張**: benchmarks/README には既に LongMemEval 節があるが、成果物が clone に無い。README 本文の「これから」と benches 記述のギャップを埋める必要 |

## 5. 次にやるべきこと (優先度順)

### P0 — 信頼性・再現性
1. **大型ベンチの `detail.jsonl` をコミット or 再現スクリプト+ハッシュ** (fair501 / nl85)。summary だけの検証限界を解消。
2. **LongMemEval 成果物をリポジトリに載せるか、未所持なら「未同梱」を README に明記**。
3. **Python 前提の整理**: 3.9 実動を追認するか、3.10+ を強制する CI を置く。

### P1 — ベクトルの「正しい使いどころ」を製品化
4. **意図ルーティング → 評議会呼び出しのゲート**を強化: 易しい事実は router 直行、曖昧/多段だけ council/puzzle。  
   (常時評議会の遅延税を避ける。intent 95% はここに効く。)
5. **発話役エスカレーションの公平メトリクスダッシュボード**: speaker 名を必ずログし、README の「話者が精度」を UI で可視化。
6. **永遠の記憶: retrieval 改善** (LongMem S Recall@5 20%→改善が主戦場)。QA は大型話者に渡す二段パイプライン。

### P2 — 構造実験の次の科学
7. **hard_elevated 系の追試拡大** (multihop で puzzle +5問の再現性、CI分離まで n を増やす)。
8. **puzzle 接合 drop が発動する閾値/データセット**を設計 (いま drop=0)。効かないなら機能を簡略化。
9. **puzzle_div の失敗分析** — なぜ classic より悪いのかを回帰テスト化。

### P3 — UX / オンボーディング
10. ローカル GPU ワンショット (`scripts/local_gpu_setup_and_run.sh`) を README 最短経路にリンク。
11. `/guide` に「ベクトルは精度ブースターではない」を最初に出す (誤解防止)。
12. 多言語 (ja/ko) はルーター知識の限界として、発話役切替デモを用意。

## 6. 改善案 (具体)

| ID | 案 | 期待効果 | 測り方 |
|---|---|---|---|
| A | `ask` 前に intent+難易度ヒューリスティックで skip-council | 平均レイテンシ大幅減 | router-only vs gated の p50 |
| B | memory→speaker 二段: 検索は 0.5B、回答は worker/ollama | LongMem QA 向上 | oracle/S の GPT-4o または containment |
| C | fair bench CI: force_router_speaker 強制チェック | 再発防止 (+22pt 事故) | unit + smoke |
| D | detail.jsonl 圧縮コミット or Git LFS | 第三者検証可能 | verify_readme_claims が行再集計 |
| E | vector usefulness scorecard (媒体/制御/記憶/精度) を benches に常設 | 主張の軸を固定 | 本ドキュメントの表を自動化 |

## 7. ライブ観測 (このマシン)

- Metal council: **11.2s**, 答え「2+2 is equal to 4」
- Intent live: **95%** (40) — README と一致
- Memory write+search: hit score **0.648** for marker
- Python: **3.9.6** (README は 3.10+)
