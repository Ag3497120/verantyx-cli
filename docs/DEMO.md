# 実機デモ手順（Honest demo）

偽の GIF や無関係な画面録画は置きません。ここでは **いまのリポジトリで実際に動く短い経路**だけを書きます。

## いまの製品面

現在の公開入口は **Omni / council / memory**（`python3 verantyx.py`）です。古いタグや Claude-Code 時代の CLI 表記とは一致しないことがあります → [`docs/RELEASES.md`](RELEASES.md)。

## A. モデルなし（推奨・最短）

ルーター分類のキーワード安全網だけを走らせます（大きな重みのダウンロード不要）:

```bash
cd verantyx-cli
source .venv/bin/activate   # 任意
python3 scripts/smoke_router_classify.py --no-model
```

期待: 数件のプロンプトに `task` / `chat?` ラベルが付いて表示される。

録画ヘルパー:

```bash
./scripts/record_demo.sh --no-model
```

## B. 重みがあるとき（Omni スモーク）

ルーター用 `.jgen` などが手元にある場合のみ:

```bash
python3 verantyx.py
# メニュー → Omni（推奨）→ 短い質問を1つ投げる → 終了
```

または分類スモーク（モデル読込あり）:

```bash
python3 scripts/smoke_router_classify.py
```

## C. ターミナル録画（GIF がまだ無いとき）

この環境では本物の短い GIF を保証できません。手元で撮る例:

```bash
# asciinema（例）
asciinema rec /tmp/verantyx-demo.cast
./scripts/record_demo.sh --no-model
exit
# 任意: agg / asciinema-gif 等で GIF 化 → assets/ へ（本物の出力のみ）

# または script(1)
script -q /tmp/verantyx-demo.txt ./scripts/record_demo.sh --no-model
```

README 上部は、GIF が無い間は本ページへのリンクを正とします。

## やらないこと

- 無関係な製品画面の流用 GIF
- ベンチ数値の捏造
- 「デモは準備中」だけの放置（手順はここに書く）
