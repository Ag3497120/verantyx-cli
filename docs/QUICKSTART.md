# 最短クイックスタート (初心者向け)

このページは「すでにルーター用の重み (`.jgen` など) がマシンにある」場合の最短経路です。  
Rust ビルドや初回モデル変換は **後回し (発展)** にして構いません。

## これは何 / 何ではないか (30秒)

- **何か:** ローカル常駐の AI **運用ハーネス** (どのモデルを呼ぶか・いつ記憶するか・どう合意を運ぶか)。
- **何かではない:** 世界知識を増やす学習基盤でも、合議による**精度ブースター**でもありません。  
  構造 (ルーティング・ベクトル合議・記憶) ≠ 正答率そのもの。数値は [`../benchmarks/README.md`](../benchmarks/README.md) を正とします。

## 前提

- Python 3.10+
- リポジトリを clone 済み
- ルーター用重みが既にある (例: `setup.sh --model` 済み、または手元の `.jgen`)

venv がまだなら:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt   # プロジェクトに合わせて調整
```

## 起動 (最短)

```bash
cd verantyx-cli
source .venv/bin/activate
python3 verantyx.py
```

メニューから **Omni** (日常) を選びます。Demo は可視化寄りで使い勝手は意図的に低下しています。

### Omni で最初に触るもの

| コマンド | 用途 |
|----------|------|
| `/settings` / `/setup` | クイック設定 |
| `/guide` / `/features` | 機能解説 |
| `/model` | 発話役の選択 (精度の本体) |
| `/config` | 設定キー |

プロファイルの説明: [`OMNI_PROFILES.md`](OMNI_PROFILES.md)

## 1分デモ (コマンドだけ · 指標は出さない)

誇張メトリクスなし。動くことだけ確認します。

```bash
source .venv/bin/activate
python3 verantyx.py
# → Omni
# → /guide          # 機能の地図
# → /settings       # 動作モードを確認 (既定 auto で可)
# → 短い質問を1つ投げる (例: 今日の日付を聞かない・ローカルで答えられる簡単な問い)
# → /model          # 発話役が何かを確認 (精度はここに依存)
# → exit / quit
```

任意: ルーター分類のスモーク

```bash
python3 scripts/smoke_router_classify.py
```

## 重みが無い場合 (発展)

初回だけセットアップが必要です。時間とディスクを使います。

```bash
./setup.sh --model     # venv + 依存 + Rustエンジン + 0.5Bルーター変換
source .venv/bin/activate
python3 verantyx.py
```

| 発展トピック | メモ |
|--------------|------|
| Rust (`cargo`) | エンジンビルド ([rustup.rs](https://rustup.rs)) |
| Forge | `python jgen_forge.py sources` / `pull` / `list` |
| Ollama / LM Studio | 大型の発話・エージェント頭脳として招集可 |
| 設定ファイル | `cp verantyx.config.example.json verantyx.config.json` |

## 困ったら

- 正直な測定と限界: [`../benchmarks/README.md`](../benchmarks/README.md)
- 貢献の仕方: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- メイン README: [`../README.md`](../README.md)
