# 🛡️ Verantyx Gatekeeper (IDE Mode)

## The Zero-Leakage AI Coding Gateway

このモードは、あなたのソースコードを意味を持たない数学的パズル（Opaque Topology）に難読化してからAIに渡す、究極のセキュアIDEです。
「会社の機密コードを、安全にクラウドLLMに読ませたい」という企業エンジニアやセキュリティ意識の高い開発者に最適です。

---

## 🔐 難読化と6軸（Axis）の立体十字構造体

このプロジェクトの難読化において、考え方は以前データの渡し方のイメージとして初期に作ったverantyxの前身であるaxisなどで見つけた立体十字構造体を主としたデータ管理手法を採用しています。

### 🧩 6つの次元（Axis）の定義

| 軸 | 名称 | 役割 / 抽出される要素 |
| :--- | :--- | :--- |
| **X軸** | **Control Flow（制御フロー）** | 時間と順序の軸。`if`分岐、`for`ループ、例外処理など。 |
| **Y軸** | **Data Flow（データフロー）** | 依存関係の軸。変数の代入、引数の受け渡しなど。 |
| **Z軸** | **Type Constraints（型制約）** | 境界の軸。クラス定義、型アノテーション、ジェネリクスなど。 |
| **W軸** | **Memory Lifecycle（メモリライフサイクル）** | 寿命の軸。スコープの生存期間、メモリの確保・解放。 |
| **V軸** | **Scope Hierarchy（スコープ階層）** | 包含の軸。モジュール、クラスのネスト構造。 |
| **U軸** | **Semantics & Meaning（意味・意図）** | **★最重要★ 業務の意図の軸。具体的な変数名、関数名、生の文字列、数値。** |

この変換プロセスは、Verantyx の **Gatekeeper（ゲートキーパー）エンジン** によってローカル環境のMacBook上で瞬時に実行されます。

---

### 🔄 生コードから Opaque Topology への変換メカニズム

#### Step 1: AST（抽象構文木）へのパースと分解
まず、Gatekeeper エンジン（ルールベース推奨）が対象のソースコードを構文解析し、プログラムの構造を **AST（Abstract Syntax Tree）** という木構造のデータに変換します。
この時点では、まだ「どの関数が何を呼び出しているか」「変数名は何で、文字列として何が定義されているか」といった情報がすべて含まれています。

#### Step 2: セマンティクス（U軸）の「物理的剥離と隔離」
ここからが Verantyx の真骨頂です。AST の中から、**業務の意味（意図）を示す情報＝U軸** をすべて物理的に剥ぎ取ります。

*   **剥ぎ取られるもの（U軸）**: 変数名、関数名、文字列、固定の数値など。
*   **残されるもの（X,Y,Z,W,V軸）**: 「変数を代入した」「関数を呼び出した」「if文で分岐した」「for文でループした」という論理的な骨組み。

剥ぎ取られた具体的な名前や文字列のデータは、あなたのMacのローカルにある **`JCrossIRVault`（金庫）** に厳重に保管され、決して外部には送信されません。

#### Step 3: Opaque Node（不透明ノード）への完全暗号化
意味を剥ぎ取られた残りの「骨組み」を、クラウドLLMへ送るために完全に不透明な表現に変換します。

*   **`NODE[0x...]`（ノードID）**: すべての変数や構文要素はランダムなメモリアドレスのような識別子に置き換えられます。
*   **`ARITY`（アリティ/項数）**:
    *   `class.nullary`: 引数や中身を持たない要素（単なる値や終端ノード）。
    *   `class.standard`: 標準的な単項・二項演算（A + B や 代入など）。
    *   `class.multiway`: 複数の要素を持つ複雑な構造（forループ、if-else分岐、関数定義など）。
*   **`HASH`（構造ハッシュ）**: そのノードがグラフのどの位置にあり、周囲とどう繋がっているかを示すチェックサム。これにより、LLMがパズルを解いて返してきたときに、構造が壊れていないかをローカルで検証できます。

元のコードの文すら消滅し、「`class.multiway` なノードが子ノードを反復処理している」という純粋な数学的グラフになります。

#### Step 4: 統計的推測を防ぐ「デコイ（おとり）」の注入
コードをグラフ構造にして外部に送った場合、高度なAIや悪意のある攻撃者が「このグラフの形は、よくあるスクリプトの形だ」と統計的に推測（リバースエンジニアリング）してくるリスクがあります。

これを防ぐため、グラフの隙間に **偽のノード（デコイ）** をランダムに注入します。
```text
// _TOKEN_匶:0.2___jcross_BM_505__ [decoy-metadata]
```
この無意味な漢字のトークンやダミーのつながりを混ぜ込むことで、グラフの形そのものを歪ませ、外部のAIが元のソースコードの正体を推測することを数学的に不可能にしています。

---

### 🧩 LLMはどうやってこれを「修正」するのか？（復元プロセス）

1. **パズルとして解く**:
   LLM は元のコードを知らなくても、指示された文脈とグラフの形（ARITY と HASH の繋がり）からターゲットとなる変更箇所の値のはずだと推論します。
2. **構造パッチの返送**:
   LLM は内容を書き換える JSON形式の構造パッチ（GraphPatch）だけを返します。
3. **ローカルでの再結合（Reverse Transpilation）**:
   Macの Gatekeeper エンジンがそのパッチを受け取り、先ほど `JCrossIRVault` に隠しておいた本当の変数名や文字列（U軸）をパッチにガチャンと再注入します。

結果として、**「外部のAIは元のコードを1行も見ていないし理解もしていないのに、ローカルに戻ってくると正しくコードが書き換わっている」** という魔法のようで情報漏洩がないという開発体験が成立します。※まだ私が見落としている情報の漏洩があるかもしれないため気づいたらissueなどでお知らせください。

---

## ⚠️ 現在対応できない（苦手な）タスク

現在この構造において対応できないタスクについて、代表的な一番苦手なタスクは **SwiftからRust言語への書き換え** などのタスクには対応できていません。また下記のような１から４までが苦手なタスクです。

### 1. 「意味（ドメイン知識）」に依存するリファクタリングやバグ修正
外部のLLMには `NODE[0x...]` という骨組みしか見えていないため、**「コードの意味を理解しないと解けない問題」** には対処できません。
*   **❌ 苦手な指示の例**: 「認証（Authentication）に関係する変数の名前にすべて `auth_` というプレフィックスをつけて」
*   **理由**: LLMには「どれが認証の処理か」が全く見えません。

### 2. 外部ライブラリ（API）に強く依存した新規機能の追加
ソースコード内の `import` 文やライブラリ呼び出しもすべて `NODE` として暗号化されているため、特定のライブラリの知識が必要なタスクが困難になります。
*   **❌ 苦手な指示の例**: 「AWS S3 にファイルをアップロードする機能を追加して」
*   **理由**: LLMは、現在のコードがどの外部ライブラリを使用しているかを知りません。

### 3. 「ゼロから全く新しい機能全体」を書き起こすこと
Gatekeeperは「既存の構造（AST）をパッチ・修正する」ことには極めて強力ですが、「何もない白紙の状態から、意味（U軸）と構造の両方を持った巨大な新機能を作り出す」ことは苦手です。

### 4. LLM自体の「事前学習知識」の無力化による推論低下
GemmaやClaudeなどのLLMは世界中のソースコードを学習して賢くなっていますが、Verantyxが送る形式は**「この世のどの言語でもない、純粋な記号とハッシュのグラフ」**です。
*   **理由**: LLMが得意とする「コードの文脈からのパターン認識」を封じているため、見たことのない難解な数学のグラフパズルになってしまい、計算コストの増大を引き起こしています。

### 💡 どのように克服しているか？（今後の展望）
現在、これらの弱点を克服するために Verantyx 側で実装されているのが、**「Tri-Layer JCross Memory（3層メモリ）」** と **「Visual Anchors（視覚的アンカー）」** の組み合わせです。機密情報を含まない安全なメタデータだけを視覚的アンカーとしてLLMに部分的に提示し、セキュリティを保ったままヒントを与えるアプローチを取っています。

---

## 📽️ デモ動画とコード変換の実際

> **デモは準備中**

### Before & After: 難読化の実際

**[Before] Raw Source Code (Local Environment)**
```python
import json
import os
import shutil
import requests
import subprocess
import re
from tqdm import tqdm
import sys

# Import our new parser
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from verantyx.cross_engine.jcross_extraction_parser import JCrossExtractionParser

ORACLE_FILE = "/Users/motonishikoudai/verantyx-cli/benchmarks/LongMemEval/data/longmemeval_m_cleaned.json"
TARGET_DIR = "/Users/motonishikoudai/verantyx-cli/verantyx-browser/.ronin/jcross_v7"
QUERY_BIN = "/Users/motonishikoudai/verantyx-cli/verantyx-browser/target/release/examples/query_jcross"
MODEL = "gemma4:e2b"
OLLAMA_URL = "http://localhost:11434/api/generate"

FINAL_REPORT = "/Users/motonishikoudai/verantyx-cli/benchmarks/LongMemEval/official_v7_1_accuracy_report.json"
```

**[After] Gatekeeper JCross Opaque Topology (Sent to Cloud LLM)**
```lisp
;;; 🛡️ GATEKEEPER MODE — JCross IR View
;;; Real identifiers have been replaced with node IDs.
;;; Schema: D59144D1-BE1
;;; Nodes: 124 | Secrets redacted: 3442
;;; Source: cortex/bench_v7_1_puzzle_runner.py
;;; 
// JCROSS_6AXIS_BEGIN
// lang:swift doc:0xD5E025

// ── TOP-LEVEL NODES
  NODE[0x7995] kind:opaque TYPE:opaque MEM:opaque HASH:0xb4af0a52 ARITY:class.multiway
  NODE[0x9DB8] kind:opaque TYPE:opaque MEM:opaque HASH:0x504933fd ARITY:class.standard
  NODE[0x627F] kind:opaque TYPE:opaque MEM:opaque HASH:0x97b540cb ARITY:class.multiway
  NODE[0x7F4C] kind:opaque TYPE:opaque MEM:opaque HASH:0x86742e8c ARITY:class.standard
  NODE[0xC79E] kind:opaque TYPE:opaque MEM:opaque HASH:0xd42206c4 ARITY:class.standard
  NODE[0x510B] kind:opaque TYPE:opaque MEM:opaque HASH:0x14b9be4e ARITY:class.nullary
  NODE[0xB5C0] kind:opaque TYPE:opaque MEM:opaque HASH:0xcacb18a2 ARITY:class.standard
// _TOKEN_匶:0.2___jcross_BM_505__ [decoy-metadata]
  NODE[0xE3CF] kind:opaque TYPE:opaque MEM:opaque HASH:0x375a5480
```
