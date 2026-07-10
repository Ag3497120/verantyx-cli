# Verantyx

**思考と発話を分離した、ローカル常駐マルチエージェント推論システム**

Verantyx は、モデルの重みを独自形式 (JGEN) に変換して自前の Rust エンジンで動かし、常駐する 0.5B の「ルーター」が複数のモデル (jgen ワーカー / HuggingFace 直ロードの大型モデル / Ollama・LM Studio 上の外部モデル) をベクトル空間上の「評議会」として束ねる CLI システムです。回答はトークン列の連鎖 (CoT のテキスト生成) ではなく、参加者間で隠れ状態ベクトルと確率分布を交換する議論によって収束させ、最後に一度だけ発話役がテキスト化します。

会話・作業の記録は「永遠の記憶」(多解像度ベクトルメモリ) に刻印され、コンテキストウィンドウに依存せずに再起動をまたいで参照されます。エージェント (web検索 / ファイル編集 / シェル / macOS アプリ操作) も同じ記憶を共有します。

> 📖 **The Verantyx Chronicles (開発年代記)**
> このシステムは AI との数十時間の対話と、無数のクラッシュ (M1 Max の MPS メモリ衝突、自己回帰ループでのエントロピー爆発、Qwen の謎の哲学モード等) の末に構築されました。どのような仮説と検証を経てここへ来たのか、記録を公開しています。
> - [Vol 1: The Genesis & MPS Trap](docs/chronicles/Vol1_The_Genesis_and_MPS_Trap.md)
> - [Vol 2: Zero-RAM Inference](docs/chronicles/Vol2_Zero_RAM_Inference.md)
> - [Vol 3: Multilingual Madness & JCross](docs/chronicles/Vol3_Multilingual_Madness_and_JCross.md)
> - [Vol 4: The Philosophical Drift](docs/chronicles/Vol4_The_Philosophical_Drift.md)

---

## ⚡ セットアップ (ワンコマンド)

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
./setup.sh --model     # venv + 依存 + Rustエンジンビルド + 0.5Bルーター自動変換
```

起動:

```bash
source .venv/bin/activate
python verantyx.py     # 対話メニュー → Omni (全機能内包チャット)
```

`--model` を付けない場合は環境構築のみ行います。手持ちの GGUF / safetensors / LM Studio / Ollama のモデルは後述の Forge で発見・変換できます。

### 前提

| 必要なもの | 備考 |
|---|---|
| Python 3.10+ | `python3 -m venv` が使えること |
| Rust (cargo) | 推論エンジンのビルドに必要 ([rustup.rs](https://rustup.rs)) |
| RAM 16GB 以上推奨 | 0.5B ルーターのみなら 8GB でも可 |
| macOS / Linux / Windows | GPU は macOS=Metal、Windows/Linux=CUDA (無ければ CPU に自動フォールバック) |
| (任意) LM Studio / Ollama | 稼働していれば大型モデルを議論・エージェントの頭脳として自動招集 |

macOS では画面 OCR とアプリ操作のために `pyobjc` を setup.sh が追加します (他 OS ではその機能だけ無効)。

---

## 🧭 開発の軌跡 (Chronicles → 現在)

このリポジトリは一直線に書かれたものではなく、失敗の記録の上に立っています。

1. **Vol 1 — Genesis & MPS Trap**: M1 Max 上で複数モデルを同時常駐させようとして MPS のメモリ衝突で崩壊。ここで「全員を常時ロードしない。軽いルーターだけ常駐させ、必要なときに招集する」という現在のエスカレーション設計の原型ができました。
2. **Vol 2 — Zero-RAM Inference**: モデル重みを mmap で読み、必要なテンソルだけ触る方式へ。これが後の JGEN 形式 (追記型バイナリ + サイドカー meta) と、重みを発火させずに検索する「静的辞書 (WeightLexicon)」につながります。
3. **Vol 3 — Multilingual Madness & JCross**: トークナイザが違うモデル同士は本来会話できません。語彙 ID ではなく「トークン文字列 + 確率」の分布を交換する中間言語 (interlingua) 方式でこれを回避し、異種モデルの議論が可能になりました。
4. **Vol 4 — The Philosophical Drift**: ベクトルだけで思考を回すと、意味が潜在空間の重心 (Qwen では抽象的な中国語の哲学) に流されていく現象に直面。6軸アンカー (Logic / Syntax / Factual / Temporal / Creativity / Consensus) による意味の係留と、ドリフトの定量監視を導入して解決しました。ドリフトは今では敵ではなく、「合意の脆さを測る摂動テスト」として意図的に注入する道具になっています。
5. **現在**: 上記の要素を統合した Omni モード (評議会 + エージェント + 静的辞書 + 永遠の記憶 + 視覚層 + ファイル資産層)、GGUF/safetensors → JGEN の汎用変換器 (MoE・QK-norm 対応)、フィードバックからのスキル獲得とルーターの反射学習、が動いています。

---

## 🏗️ アーキテクチャ

```
あなた
 └─ Omni チャット (verantyx.py)
     ├─ 意図ルーティング: 質問 → 評議会 / 作業依頼 → エージェント (自動判定)
     ├─ 評議会 (verantyx_council.py)
     │    ├─ 常駐ルーター 0.5B (jgen / Rustエンジン) — Commander・Scout・Worker の多役割
     │    ├─ エスカレーション: jgenワーカー → HF大型 (賢者) → 外部 (Ollama/LM Studio)
     │    └─ ベクトル議論: 隠れ状態と分布の交換で合意形成 → 最強参加者が一度だけ発話
     ├─ エージェント (verantyx_agent.py)
     │    └─ web検索(実ブラウザ経由) / ファイル / シェル / macOSアプリ操作 — 危険操作は確認つき
     ├─ 永遠の記憶 (CortexMemory): L1 6軸署名 → L1.5 全次元ベクトル → L3 原文 のカスケード
     │    ├─ 視覚層 (画面OCR + 多解像度圧縮) / 資産層 (パソコン内ファイルの意味検索)
     │    └─ 反射層 (ルーティング経験) / スキル層 (フィードバックから獲得した手順)
     ├─ 静的辞書 (weight_lexicon.py): 大型モデルの重みを推論なしで mmap 連想検索
     └─ Forge (jgen_forge.py): GGUF / safetensors / LM Studio / Ollama → JGEN 変換
Rust エンジン (jcross_engine_glm): JGEN v3 ロード、Metal/CUDA、MoE、QK-norm、SVD/Dense両対応
```

---

## 🔬 技術的な要点 (誇張なしの現状)

**できていること:**

- **思考と発話の分離**: 議論フェーズではテキストを生成しません。各参加者は質問の隠れ状態に自分の意見ベクトルを混ぜ、上位トークン分布を交換します。合意 (コサイン類似度とエントロピーで判定) に達してから、最も強い参加者が一度だけテキスト化します。小さいモデルに長文を書かせないので、0.5B 級でもトークン天井による途切れが起きにくい構造です。
- **異種モデル間のベクトル通信**: トークナイザが違っても「トークン文字列+確率」の分布交換で議論に参加できます。jgen 同士なら隠れ状態そのものを注入できます (次元が違う場合は lm_head 経由で分布に落として橋渡し)。
- **JGEN 変換器**: `gguf` パッケージによる全量子化タイプの逆量子化、ストリーミング書き出し (大型モデルでも RAM に載せない)、MoE エキスパートの分割展開、QK-norm・共有エキスパート・ルーター重みの命名マップ。LM Studio / Ollama の隠しフォルダと HF キャッシュを自動発見します。
- **エンジン**: JGEN v3 (SVD 分解 or Dense 2D)、meta.json 駆動の MoE 設定 (top-k / softmax / 開始層)、QK-norm、Metal GPU (CUDA はビルドフラグ)、GPU 非対応レイヤーの CPU フォールバック。
- **永遠の記憶**: 3層構造 (6次元署名 → 1024次元 → 原文) のカスケード検索に文字バイグラムの字句一致を混ぜたハイブリッド。古い記憶は消えず「重力」で沈むだけ。会話・タスク・画面・ファイル資産が同じ空間に刻印されます。
- **自己改善ループ**: ユーザーの改善フィードバックからツール手順 (スキル) を抽出し、ペルソナに対する予行演習で満足度を予測してから採用します。ルーターも過去のルーティング結果 (エスカレーション要否・合意の脆さ) を反射として蓄積します。
- **静的辞書**: 9B〜数十B の重みを発火させず、埋め込み行列の mmap 検索だけで連想・類推を引きます。

**限界・正直な注意点:**

- 0.5B ルーター単体の言語能力は低く、複雑な回答の品質は招集される大型モデル (jgen ワーカー / HF / 外部サーバー) に依存します。ルーターの役割はあくまで交通整理・記憶・ベクトル操作です。
- ベクトル議論の「合意」は幾何的な収束であって正しさの証明ではありません。摂動テストとエスカレーションで脆い合意を検出しますが、間違った合意もありえます。
- MoE モデルの GPU バッチ経路は未実装で、MoE 層を含むモデルは全パス CPU にフォールバックします (正しさ優先)。
- SSM / ハイブリッド線形注意のモデル (Qwen3.5 系など) は変換はできますがエンジンでの推論は未対応で、静的辞書 (lexicon) としてのみ使えます。
- スキル獲得の「予行演習」は LLM によるシミュレーションであり、実行結果の保証ではありません。
- 6軸の意味づけはアンカー学習の質に依存し、厳密な解釈可能性を主張できる段階ではありません。

---

## ⚙️ 設定: モデルの割り当てを自由に固定する

既定では **auto** — マシンの RAM とローカル資産 (LM Studio / Ollama / HF キャッシュ / 変換済み jgen) をスキャンして各ロールを自動評価します。`verantyx.config.json` を作ると各ロールを明示的に固定できます。

```bash
cp verantyx.config.example.json verantyx.config.json
```

またはチャット内から (即座に保存されます):

```
/config                                # 現在の設定を表示
/config set models.worker ornith9b_full
/config set models.sage none
/config set models.agent_backend ollama:qwen3:8b
/config set models.bridges ["lmstudio:ornith-1.0-35b"]
/config reset
```

CLI からも同じ操作ができます: `python verantyx_config.py show | set <key> <value> | reset`

| キー | 値 | 意味 |
|---|---|---|
| `models.router` | `auto` / `.jgen`パス | 常駐ルーター。auto は環境変数 `JGEN_MODEL` → 既知パス → レジストリの順で解決 |
| `models.router_tokenizer` | HF repo id / パス | ルーターのトークナイザ |
| `models.worker` | `auto` / `none` / レジストリ名 / `.jgen`パス | 発話ワーカー。auto は RAM に収まる最大の ready モデル |
| `models.sage` | `auto` / `none` / HFモデルdir | 大型賢者 (HF直ロード)。`none` で禁止し外部サーバーへ委譲 |
| `models.lexicon` | `auto` / `none` / 名前 / パス | 静的辞書。auto はローカル最大の対応モデル |
| `models.agent_backend` | `auto` / `lmstudio[:model]` / `ollama[:model]` / `sage` | エージェントの頭脳 |
| `models.bridges` | `auto` / `["lmstudio:...", ...]` | 評議会への常時参加。auto はエスカレーション時のみ招集 |
| `generation.speak_tokens` | `auto` / 整数 | 発話長。auto は EOS 終了 + 安全天井 |
| `generation.language` | `null` / `"Japanese"` 等 | 応答言語の強制 |
| `escalation.enabled` | true / false | 自動エスカレーション |
| `escalation.ram_fraction` | 0.0–1.0 | ワーカー自動選択に使う RAM 割合 (既定 0.45) |
| `memory.enabled` | true / false | false で常時シークレット (記憶を参照も刻印もしない) |

設定は次のモデルロードから反映されます。ロード済みモデルの入れ替えは `/council` (解任) → `/model` (再選択) で。

---

## 🕹️ 使い方 (Omni モード)

`python verantyx.py` → `1. Omni`。そのまま話しかけるだけで、質問は評議会・作業依頼はエージェントに自動で振り分けられます。主なコマンド:

```
/model      発話役の選択 (jgen / Ollama / LM Studio / HF 9B)
/council    議論メンバーの表示・追加・解任
/scout      ローカルモデルの自動探索と役割割り当て
/convert X  LM Studio / Ollama / HF キャッシュのモデルを jgen へ変換
/lang, /think, /tokens, /rounds, /fast   言語・思考許可・発話長・議論数
/agent TASK 手動でエージェント実行  /ask Q  強制的に評議会へ
/dict WORD  静的辞書の連想検索      /analogy a b c  ベクトル類推
/recall Q   記憶検索  /vault ファイル資産化  /persona  ペルソナ表示
/screen /see  画面の刻印と検索 (macOS)
/secret     記憶バイアスの遮断/再開      /config  設定
/reflex /skills  ルーターの反射・獲得スキルの一覧
```

### モデルの追加 (Forge)

```bash
python jgen_forge.py sources            # LM Studio / Ollama / HF キャッシュを発見
python jgen_forge.py pull <名前の一部>   # 発見したモデルを jgen に変換
python jgen_forge.py pull <名前> --parts lexicon   # 静的辞書のみ (軽量・高速)
python jgen_forge.py list               # 変換済みレジストリ
```

MoE (Qwen3-MoE 系など) はエキスパート分割つきで変換され、そのままエンジンで動きます。エンジン未対応アーキテクチャ (SSM 系) も lexicon 変換で辞書として使えます。

---

## 📂 リポジトリ構成 (現行システムの中核)

| ファイル | 役割 |
|---|---|
| `verantyx.py` | 対話ランチャー + Omni モード |
| `verantyx_mind.py` | Rust エンジンの FFI、埋め込み、永遠の記憶 (CortexMemory) |
| `verantyx_council.py` | 評議会: 多役割ベクトル議論・エスカレーション・発話 |
| `verantyx_agent.py` | ReAct エージェント (確認つきツール実行) |
| `verantyx_bridges.py` | Ollama / LM Studio 連携 (分布交換 + reasoning 制御) |
| `verantyx_browser.py` | 実ブラウザエンジン経由のボットガード耐性 web 取得 |
| `verantyx_config.py` | ロール割り当て・動作設定 (`verantyx.config.json`) |
| `jgen_forge.py` | GGUF / safetensors → JGEN 変換器 + モデルレジストリ |
| `weight_lexicon.py` | 静的辞書 (重みの mmap 連想検索) |
| `model_scout.py` | ローカルモデルの発見と役割の自動割り当て |
| `memory_guard.py` | RAM 監視と OOM 回避 (ロード可否判定・身代わり招集) |
| `cognitive_anchors.py` / `skill_memory.py` / `router_reflex.py` | 認知アンカー / スキル獲得 / ルーター反射 |
| `file_vault.py` / `vision_memory.py` / `computer_control.py` | 資産層 / 視覚層 / macOS 操作 |
| `session_log.py` | セッション履歴 (「さっきの」を再起動をまたいで解決) |
| `jcross_engine_glm/` | Rust 推論エンジン (JGEN v3 / Metal / MoE / QK-norm) |
| `verantyx_mcp.py` | MCP サーバー (記憶・議論を JSON-RPC ツールとして公開) |

モデル本体 (`*.jgen`, `*.gguf`, `*.safetensors` など) と個人の記憶 (`.verantyx_chrono/`) はリポジトリに含まれません。

---

## License

このリポジトリのコードは研究・実験目的で公開しています。変換対象の各モデルのライセンスはそれぞれの配布元に従ってください。
