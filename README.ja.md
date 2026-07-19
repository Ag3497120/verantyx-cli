# Verantyx

**Languages:** [English](README.md) · [日本語](README.ja.md) · [简体中文](README-zh-CN.md) · [繁體中文](README-zh-TW.md) · [한국어](README-ko.md) · [Español](README-es.md) · [Português](README-pt-BR.md) · [Deutsch](README-de.md) · [Français](README-fr.md) · [Русский](README-ru.md) · [Українська](README-uk.md) · [Türkçe](README-tr.md) · [العربية](README-ar.md)

> **常駐は小さいルーターだけ。大きなモデルは必要なときだけ。記憶は再起動をまたぐ。**

ノートPCで強いローカルAIを回したいのに、大きいモデルを一日中VRAMに置きたくない——そのための **運用ハーネス** です。  
約0.5Bのルーターだけを常温で置き、Ollama / HF / LM Studio などの発話役は **必要なとき一度だけ** 呼び、会話は **永遠の記憶** に書いてプロセス終了後も残します。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Demo](https://img.shields.io/badge/demo-60s-brightgreen.svg)](docs/DEMO.md)
[![Docker](https://img.shields.io/badge/docker-one%20command-blue.svg)](#60秒で入れる)

---

## これ一件のためにあります

**ローカルAIのRAM税を下げる。**

| Verantyx なし | Verantyx あり |
|---|---|
| 大型モデルが一日中VRAMを占有 | 常駐は小さいルーターだけ |
| 再起動で文脈が消える | 永遠の記憶が残る |
| 誰が話すか・何を覚えるかがクラウド側 | 端末の外に明け渡さない |

「もっと賢いモデル」競争ではありません。  
**誰を呼ぶか・いつ覚えるか・合意をどう運ぶか** を制御するCLIです（テキスト往復の多役エージェントより壊れにくいベクトル媒体）。

---

## 60秒デモ

偽GIFは置きません。手順の正本 → [`docs/DEMO.md`](docs/DEMO.md)

```bash
# A) 重みなし（安全・最短）
docker build -t verantyx:demo .
docker run --rm -it verantyx:demo
# または:
python3 scripts/smoke_router_classify.py --no-model

# B) ルーター重みがあるとき
python3 verantyx.py          # メニュー → Omni → 一言聞く → 終了 → 再起動しても記憶
```

**一分で感じること:** 小さい脳が常駐 → 大きい脳が一度だけ話す → 再起動しても消えない。

---

## 60秒で入れる

### 1) Docker（いちばん速い）

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
docker build -t verantyx:demo .
docker run --rm -it verantyx:demo
```

### 2) Python venv（重みは任意）

```bash
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/smoke_router_classify.py --no-model
```

### 3) フルセットアップ（変換 + Rust）

```bash
git checkout stable
./setup.sh --model
source .venv/bin/activate
python3 verantyx.py
```

詳細: [`docs/QUICKSTART.md`](docs/QUICKSTART.md) · [`docs/OMNI_PROFILES.md`](docs/OMNI_PROFILES.md)

---

## 仕組み（30秒）

```text
  あなた ──► 0.5B ルーター（常駐）
                │  分類 / 招集 / 記憶
                ▼
           ベクトル合議（任意）
                │
                ▼
           発話役を一度だけ（Ollama / HF / …）
                │
                ▼
           永遠の記憶 ──► 終了・再起動後も残る
```

| 平たい言い方 | コード上の名前 |
|---|---|
| 常駐の小さい脳 | ルーター |
| 内部合意の運び方 | ベクトル評議会 / company |
| 口を開くモデル | 発話役 |
| 再起動をまたぐ記憶 | 永遠の記憶 |

---

## 共有用コピー（Show HN / SNS）

> **Verantyx** — 常駐は小さいルーターだけ。大きなモデルは必要なときだけ。記憶は再起動をまたぐ。  
> ローカルCLI: 約0.5Bを常駐させ、大型発話役を一度だけ呼び、文脈窓の外に記憶する。  
> Demo: `docker build -t verantyx:demo . && docker run --rm -it verantyx:demo`  
> https://github.com/Ag3497120/verantyx-cli

長文ピッチ: [`docs/PITCH.md`](docs/PITCH.md)

---

## 正直な限界（盛らない）

- **精度 ≈ 誰が話すか。** 同じ0.5B話者なら合議 ≈ ルーター単独（公平ベンチ）。  
- **媒体としてのベクトル**は NL 合議より速く・壊れにくい（当方85問でおおよそ +15pt・半分の時間）。IQブースターではない。  
- 数値の正本: [`benchmarks/README.md`](benchmarks/README.md)

---

## コントリビュート

60秒経路を、速く・正直なまま保ちたいです。

- [good first issue](https://github.com/Ag3497120/verantyx-cli/labels/good%20first%20issue)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- 評価するだけなら `stable` を先に。開発は `main`。

---

## License

コードは [MIT](LICENSE)。**重みは別物** — Ollama / HF / ローカル変換で持ってきてください。

偽メトリクスなし。60秒で欲しくなったらスターをお願いします。
