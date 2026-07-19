# 異モデル合意の橋渡し (Cross-Model Interlingua)

## 問題

0.5B 評議会が合意した思考ベクトル `z` を 9B に「そのまま」渡せない理由は次元不一致だけではない。

| 障害 | 内容 |
|------|------|
| 次元 | 896/1024 vs 4096… で配列として非互換 |
| 幾何 | 同じ次元でも学習空間が違い、座標の意味が一致しない |
| 位置 | 意味が最終隠れ状態 / 中間層 / vocab 近傍など、モデルごとに違う場所に載る |
| 語彙 | トークナイザが違うと「同じ単語」でも埋め込み行が違う |

結論: **生の隠れ状態はモデル内専用。モデル境界ではプロトコル変換する。**

## 解法 (Verantyx の方針)

生 `z` を共有空間だと仮定しない。境界では必ず次のいずれかに落とす。

1. **語彙分布インターリンガ** `[(文字列, 確率), …]`  
   - 送信側: `dist_from_vector(z)`  
   - 受信側 (埋め込み可): `dist_to_soft` → **相手の** embed 行で仮想トークン再合成 → `encode_soft`  
   - 受信側 (API): 分布をテキスト化し system / user に載せる

2. **共有タスク空間 (モデル非依存)**  
   - L1 軸署名 / L2 概念トークン / L3 原文 / 検索根拠  
   - 発話役には `SpeakerBrief` として渡す (`speaker_bridge.py`)

3. **発話役の役割分離**  
   - Speaker は考え直させず、ブリーフを口にする  
   - 誰が話すか・何を渡すかが精度レバー (モデル差し替えより効くことが多い)

```
0.5B council ──z──► dist / concepts / memory snippets
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   soft in 9B embed   text brief    Obsidian L3
   (HFSage opine)     (Ollama speak) (retrieval)
```

## やらないこと

- 線形射影だけで「空間アライン」したつもりになる (意味が揃う保証がない)
- 0.5B の生 `z` を pad/truncate して 9B に注入する
- 異モデル間で hidden を共有メモリとして扱う

学習アダプタ (小さな translator) は将来オプション。既定は **プロトコル翻訳**。

## AbstractLink — 中間解像度グラフ変換器

抽象画は単なるメッセージ形式ではなく、**解像度の変換器**でもある。
立体十字構造のグラフは自然言語とベクトルのあいだに位置し、
**それぞれの形式へ忠実に変換できること**が要件である (片方向の劣化ダンプではない)。

```
生ベクトル z          立体十字グラフ              自然言語
(高解像・モデル固有) ↔ (中解像・共有・調整可) ↔ (低解像・発話用)
     渡せない              投げ合える               伝言で壊れる
```

### 三言語がそれぞれ動作する (言語に意思を持たせる)

「言語自体が意思を持つベースモデル」という発想は、神秘ではなく次の設計に落とす:

| 言語 | 実行器 (薄い意思) | すでに近い実体 |
|------|-------------------|----------------|
| VectorLang | encode / soft 注入 / forward | RustBrain, encode_soft |
| GraphLang | catchball / puzzle / graph 記憶 | LinkChannel, MemoryGraph |
| NaturalLang | speak / brief 条件付け生成 | Speaker, bridges |

巨大な単一モデルに三言語を兼業させない。  
各言語に操作系を持たせ、**立体十字グラフをヒンジ**にして往復させる。  
品質指標は往復忠実度 (`language_runtime.FidelityReport`)。

本線 (`Council.ask`):

1. `build_hinge_for_council` → `LinkGraphLang.step` (catchball)
2. **PuzzleDecontaminator** — 0.5B 単一期の汚染除去配管  
   - rival 尾・無関係概念/命題・外れ軸をドロップ  
   - `contamination_score` / `purity_gain` を計測  
3. `run_graph_step_with_fidelity`  
   - `graph→graph(step)` / `vector→graph→vector`  
   - 忠実度低 × 汚れ残 → 再 step (配管の再循環)  
4. 発話後 `measure_nl_roundtrip` (`nl↔graph↔nl`)  
5. 軌跡に `fidelity` + `decontam` を記録

0.5B だけの期は新モデルを足さず、パズル配管でルーター方言・混線を落とす。

| | ベクトル | 立体十字グラフ | 自然言語 |
|--|---------|-------------|---------|
| 解像度 | 高い | 中 | 低い |
| 異モデル共有 | ほぼ不可 | 可能 | 可能だが劣化大 |
| 不確実性の保持 | 暗黙 | 分布・対立辺として明示 | 文に潰されやすい |
| 役割 | モデル内思考 | 議論・総意形成の媒体 | 人間向け出力 |
| 実行 | forward | graph step | generate |

お互いがグラフを投げ合い、リンク (パズル接合 + パターンマッチ) で辺と重みを調整し、議論しながら総意ノードを寄せる。最終的に発話役が言語へ落とす。

```
model A ──► AbstractCanvas.as_graph() ──► LinkChannel ──► AbstractCanvas ──► model B
                ▲                              │                    │
                └──────── catchball ───────────┴── speaker 参加 ────┘
                                                      ▼
                                              SpeakerBrief → 言語
```

グラフの主なノード種:

| 層 | 中身 |
|----|------|
| L1 | 軸署名 (6,) — 全体の向き |
| dist | 語彙分布候補 — rivals / answers 辺 |
| L2 | 概念 — supports 辺 |
| props | 命題 — claims 辺 |
| patterns | 記憶ヒット — grounds 辺 |

## MemoryGraph — 異種共通の記憶言語

L1.5 埋め込みはルーター固有なので、異種モデルは同じ座標を読めない。
そこで記憶の正本を **MemoryGraph** にする。

```
生ベクトル (一瞬・非共有) → MemoryGraph (一瞬に近い・共有) → 自然言語 (遅い・劣化)
```

スキーマ (`verantyx.memory_graph.v1`):

- `axes` — パズル6軸の向き (名前付き)
- `concepts` / `propositions` / `candidates` — 構造化主張
- `grounds` / `edges` — 根拠と関係
- `l3_text` — 人間向けアンカー (補助)

読み取り:

- same-model: 従来の L1→L1.5 コサイン
- cross-model: `CortexMemory.search_graph` (query_vec 不要) → `flash_summary()` で状況をフラッシュ理解 → 必要なら自空間へ soft 再投影

書き込み: `add(..., graph=...)` / `add_graph(mg)`。評議会の AbstractCanvas からも自動生成。

## 実装入口

- `memory_graph.py`: `MemoryGraph` / `search_graphs` / `flash_summary`
- `verantyx_mind.py`: `CortexMemory.add_graph` / `search_graph`
- `verantyx_council.py`: `dist_from_vector` / AbstractLink + 記憶へ graph 刻印
- `abstract_link.py`: `AbstractCanvas` / `LinkChannel.catchball` (記憶は graph 経路)
- `speaker_bridge.py`: `SpeakerBrief`
- `obsidian_ingest.py`: Obsidian vault → Cortex L3 (`/obsidian`)
