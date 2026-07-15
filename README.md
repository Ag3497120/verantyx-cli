# Verantyx

**Languages:** [日本語](README.md) · [English](README-en.md) · [简体中文](README-zh-CN.md) · [繁體中文](README-zh-TW.md) · [한국어](README-ko.md) · [Español](README-es.md) · [Português](README-pt-BR.md) · [Deutsch](README-de.md) · [Français](README-fr.md) · [Русский](README-ru.md) · [Українська](README-uk.md) · [Türkçe](README-tr.md) · [العربية](README-ar.md)

> **0.5Bだけを常駐させ、必要な瞬間だけ大型ローカルモデルを起動する、再起動をまたぐ記憶付きAIランタイム。**

![demo](demo.gif)

Verantyx は「もっと賢いモデル」を競う製品ではありません。あなたのマシン上で、**どのモデルを呼ぶか・いつ記憶するか・どう合意を運ぶか**を制御する CLI ランタイムです。

常駐は 0.5B 級のルーターだけ。必要なときだけワーカー / HuggingFace / Ollama / LM Studio 上の大型モデルを起動して**一度だけ発話**させ、会話・作業・画面は「永遠の記憶」に残します（コンテキスト窓に依存せず再起動をまたぐ）。

| 平たい言い方 | 内部で使う名前 |
|---|---|
| 交通整理役（常駐の小モデル） | ルーター / classify-only |
| 内部合意の運び方 | ベクトル評議会（council） |
| 答えを口にするモデル | 発話役 / speaker |
| 再起動をまたぐ記憶 | 永遠の記憶（eternal memory） |

> **ベンチで確認したこと (誇張なし)**  
> 発話役を同じ 0.5B に揃えると、評議会の正答率はルーター単独と**ほぼ同じ** (501問で差1問)。精度の伸びは熟議ではなく**誰が話すか**で決まる。  
> 一方、同じ 0.5B で「自然言語の合議」と「ベクトル合議」を比べると、ベクトル側が **+15pt・約半分の時間**で勝つ。合議の価値は精度ブースターではなく、**テキスト往復より壊れにくい媒体と制御**にある。

> 📖 **The Verantyx Chronicles** — 失敗から設計が生まれた記録  
> - [Vol 1: The Genesis & MPS Trap](docs/chronicles/Vol1_The_Genesis_and_MPS_Trap.md)  
> - [Vol 2: Zero-RAM Inference](docs/chronicles/Vol2_Zero_RAM_Inference.md)  
> - [Vol 3: Multilingual Madness & JCross](docs/chronicles/Vol3_Multilingual_Madness_and_JCross.md)  
> - [Vol 4: The Philosophical Drift](docs/chronicles/Vol4_The_Philosophical_Drift.md)

---

## これは何で、何ではないか

| 出すもの | 出さないもの |
|---|---|
| ローカル常駐のルーター + モデル招集 | 「合議で単独より大幅に正解する」という主張 |
| ベクトル熟議 (NL合議より安く・壊れにくい内部合意) | 業界最先端モデルとの精度競争 |
| 発話役の差し替え (精度は話者選択に依存) | ブラックボックスのクラウド専用エージェント |
| 永遠の記憶・反射・スキル・Omni/Agent/Demo | 「重みを焼く」ための学習基盤 |

一言で:

> **0.5Bだけを常駐させ、必要な瞬間だけ大型ローカルモデルを起動する、再起動をまたぐ記憶付きAIランタイム。**

---

## ⚡ セットアップ

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
./setup.sh --model     # venv + 依存 + Rustエンジン + 0.5Bルーター変換
```

```bash
source .venv/bin/activate
python verantyx.py     # メニュー → Omni (推奨) / Demo / Mind / Agent …
```

| 前提 | 備考 |
|---|---|
| Python 3.10+ / Rust (cargo) | エンジンビルドに必要 ([rustup.rs](https://rustup.rs)) |
| RAM 16GB 推奨 (0.5Bのみなら 8GB 可) | |
| macOS / Linux / Windows | Metal / CUDA / 無ければ CPU |
| (任意) LM Studio / Ollama | 大型の発話・エージェント頭脳として招集可 |

---

## 🏗️ アーキテクチャ (運用ハーネス)

```
あなた
 └─ Omni (verantyx.py)
     ├─ 意図ルーティング …… 質問→評議会 / 作業→エージェント
     ├─ ルーター 0.5B …… 常駐。交通整理・記憶・ベクトル操作
     ├─ ベクトル評議会 …… 隠れ状態・分布の交換で合意 (テキスト合議ではない)
     ├─ 発話役の差し替え …… sage / worker / Ollama / LM Studio (精度の本体)
     ├─ エージェント …… web(実WebKit) / ファイル / シェル / macOS操作
     ├─ 永遠の記憶 …… 多解像度ベクトル + 原文 (窓に依存しない)
     ├─ 静的辞書 …… 大型重みを発火させず mmap 連想検索
     └─ Forge …… GGUF / safetensors → JGEN
```

**設計の芯:** 思考 (ベクトル) と発話 (テキスト) を分離する。小さいモデルに長文 CoT を書かせない。精度が要る局面だけ強い話者を呼ぶ。

---

## 🔬 実測から言えること (`benchmarks/` で再現可)

### 1. 同一話者では合議の正答率ゲインはほぼ無い

501問・エスカレーション off・**発話役を 0.5B router に固定**:

| モード | 正解率 (95% CI) |
|--------|-----------------|
| router | 52.5% [48.1–56.8] |
| council (ベクトル) | 52.3% [47.9–56.6] |

差は1問。CI は完全に重なる。時間だけ +2.5s/問。  
→ **精度を上げたいなら熟議の往復ではなく、より大きな発話モデルを使う。**

> 以前公開していた「評議会 +22.7pt」は不公平でした。`--no-escalate` 下でも発話役が別ワーカーへ自動昇格しており、話者の差を測っていました。訂正済み (`force_router_speaker`)。

### 2. 媒体としては、自然言語合議よりベクトル合議が強い

85問・同じ 0.5B・2ラウンド固定:

| モード | 正解率 | 平均時間 | コスト感 |
|--------|--------|----------|----------|
| router | 60.0% | 7.0s | 生成1回 |
| **council (ベクトル)** | **63.5%** | 8.8s | 隠れ状態交換 |
| nl_council (自然言語) | 48.2% | 19.7s | 平均13回生成 |

vector − NL = **+15.3pt**、時間は約半分。  
→ 合議をやるならテキスト往復よりベクトル。ただし「router を大きく超える精度装置」ではない。

### 3. その他

| 項目 | 結果 |
|---|---|
| JGEN (SVD) 重み再構成 | 相対誤差 0.036%、出力コサイン 1.000 |
| 意図ルーティング (task/chat) | 95.0% (40件) |
| エスカレーション on | 難問で 150〜400s+/問 (bridge待ちが支配的。1呼び出し90sキャップあり／全体締切は未実装) |

詳細・カテゴリ内訳・再現コマンド: [`benchmarks/README.md`](benchmarks/README.md)

---

## 🧭 開発の軌跡 (なぜこの形か)

1. **MPS Trap** — 全員常駐は崩れる → 軽いルーター常駐 + 招集  
2. **Zero-RAM / JGEN** — mmap と追記型バイナリで重みを扱う  
3. **JCross** — 異トークナイザ間は「文字列+確率」分布で交信  
4. **Philosophical Drift** — ベクトル思考の重心ドリフトを係留し、摂動テストに転用  
5. **現在** — Omni + 記憶 + エージェント + Forge。主張はベンチで矯正済み

---

## ⚙️ 設定 (モデル割り当て)

既定は **auto** (RAM とローカル資産を見て役割を選ぶ)。固定するなら:

```bash
cp verantyx.config.example.json verantyx.config.json
# または Omni 内: /config set models.worker ornith9b_full
```

| キー | 意味 |
|---|---|
| `models.router` | 常駐ルーター (`.jgen` / auto) |
| `models.worker` / `models.sage` | 発話・賢者 (精度の本体。`none` 可) |
| `models.agent_backend` | エージェント頭脳 (`ollama:…` / `lmstudio:…` / sage) |
| `models.bridges` | 評議会への外部参加 |
| `escalation.enabled` / `bridge_timeout_s` | 自動招集と外部呼び出し上限 (既定90s) |
| `memory.enabled` | false でシークレット (刻印も参照もしない) |

CLI: `python verantyx_config.py show | set <key> <value> | reset`

---

## 🕹️ 使い方

`python verantyx.py` → **Omni** (日常) / **Demo** (映像壁の可視化・使い勝手は意図的に低下)

```
/model /council /scout     発話役・議論メンバー・探索
/convert X                 ローカルモデルを jgen へ
/agent TASK  /ask Q        エージェント強制 / 評議会強制
/dict /analogy             静的辞書
/recall /vault /persona    記憶・資産・ペルソナ
/screen /see               画面の刻印 (macOS)
/secret /config /reflex /skills
```

```bash
python jgen_forge.py sources
python jgen_forge.py pull <名前の一部>
python jgen_forge.py list
```

---

## 📂 中核ファイル

| ファイル | 役割 |
|---|---|
| `verantyx.py` | ランチャー + Omni / Demo |
| `verantyx_council.py` | ベクトル評議会・発話・`ask_nl` (媒体比較用) |
| `verantyx_mind.py` | Rust FFI・永遠の記憶 |
| `verantyx_agent.py` / `verantyx_browser.py` | エージェント・実WebKit取得 |
| `verantyx_bridges.py` / `jgen_forge.py` | 外部モデル・JGEN変換 |
| `weight_lexicon.py` / `memory_guard.py` | 静的辞書・RAMガード |
| `demo_stage.py` / `demo_pane.py` | デモ映像壁 |
| `benchmarks/` | 再現可能な測定 (公平条件・媒体比較含む) |
| `jcross_engine_glm/` | Rust 推論エンジン |
| `verantyx_mcp.py` | MCP (記憶・議論) |

モデル本体と個人記憶 (`.verantyx_chrono/`) はリポジトリに含みません。

---

## 限界 (リリース時に隠さないこと)

- 0.5B ルーターの言語能力は低い。複雑な答えの質は**招集した発話モデル**次第。  
- ベクトル合意は幾何的収束であり、正しさの証明ではない。  
- MoE の GPU バッチ未実装 / SSM・ハイブリッド線形注意は推論未対応 (lexicon 可)。  
- 評議会全体の経過時間デッドラインは未実装 (低速 bridge では `--no-escalate` 推奨)。  
- 長期タスクの忘れ・情報劣化ベンチはこれから (次の主戦場)。

---

## Releases / tags

Prefer **`main`** and the docs in this tree. Older GitHub tags may describe a **legacy Claude-Code-era CLI** and can disagree with current Omni / council behavior. We are not cutting a new `v3` release from this packaging pass unless maintainers explicitly approve.

## Trust & contributing

- [`LICENSE`](LICENSE) — code license  
- [`SECURITY.md`](SECURITY.md) — shell / files / web / memory wipe  
- [`PRIVACY.md`](PRIVACY.md) — local vs outbound data  
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

## License

**Repository code** is released under the [MIT License](LICENSE).

**Model weights and tokenizers are not MIT.** They keep each upstream distributor’s terms. Converting or downloading a model does **not** relicense those weights as MIT.

| Component | License posture |
|---|---|
| Verantyx CLI / harness source in this repo | **MIT** ([`LICENSE`](LICENSE)) |
| Router / speaker weights (e.g. Qwen, GLM, Ornith, …) | **Upstream model license** — see each Hugging Face / vendor card |
| Optional Ollama / LM Studio blobs you install | Their upstream + host app terms |

研究・実験用途を想定しています。配布・商用利用の可否は **コードの MIT** と **各モデルのライセンス** の両方を確認してください。
