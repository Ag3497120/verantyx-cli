# Verantyx JGEN Converter (Ornith 1.0 9B)

このフォルダは、`deepreinforce-ai/Ornith-1.0-9B` モデルを Verantyx の JGEN フォーマット（ロスレスフルランク SVD 適用済みの空間ベクトル形式）に変換するための自己完結型ツールパックです。

## 動作要件 (Prerequisites)

- **OS**: macOS / Linux
- **Python**: Python 3.9 以上
- **Memory (RAM)**: 32GB 以上の物理メモリを推奨（SVDの行列計算に多大なメモリを使用します）
- **Disk Space**: 50GB 以上の空き容量（Hugging Faceからのダウンロードキャッシュ ＋ 変換後の `.jgen` ファイル出力用）

## 実行手順

### 1. ターミナルを開き、このフォルダに移動します。

```bash
cd /path/to/jgen_converter_pack
```

### 2. （任意・推奨）仮想環境の作成と有効化

システム全体にライブラリをインストールしたくない場合は、仮想環境を作成します。

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 必要なライブラリのインストール

```bash
pip install -r requirements.txt
```

### 4. 変換スクリプトの実行

```bash
python3 build_ornith_jgen.py
```

## 処理のフローと完了目安時間

スクリプトを実行すると以下の順序で処理が進行します。

1. **ダウンロードフェーズ**: 
   Hugging Face (`deepreinforce-ai/Ornith-1.0-9B`) から `safetensors` ファイル群を自動ダウンロードします。ネットワーク回線に依存しますが、数分〜数十分かかります。
2. **行列分解 (SVD) フェーズ**:
   ダウンロード完了後、モデルのすべてのLinear層（自己注意機構やMLPなど）に対して、フルランクの特異値分解（SVD）を計算します。
   **⚠️ 注意**: この処理はCPUの全コアを使用して極めて重い計算を行うため、Macのスペックに依存しますが **数時間 (2時間〜4時間程度)** かかります。
3. **完了**:
   処理が完了すると、同じディレクトリ内に `ornith_9b_full.jgen` という名前のバイナリファイルが出力されます。これがVerantyxエンジンでそのまま読み込める形式のモデルファイルになります。
