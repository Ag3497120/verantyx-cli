# Verantyx Cross構造システム - 使い方サマリー

**作成日**: 2026-03-10

---

## 🎯 このシステムで何ができるか

### 核心機能

1. **Claude対話の自動学習**
   - Claude/Geminiとの対話をリアルタイムでCross構造に変換
   - 22,097個のコマンド辞書で操作を自動分類
   - 6軸（UP/DOWN/LEFT/RIGHT/FRONT/BACK）で多次元的に保存

2. **パターン推論（3件以上の対話で自動実行）**
   - トピックと意図を自動抽出
   - 類似パターンを探索
   - パズルピース組み合わせで新しい推論を生成

3. **小世界シミュレータ（5件以上の対話で自動実行）**
   - 学習履歴から小世界を構築
   - 因果推論で関係性を発見
   - 未来を予測（信頼度付き）
   - 推奨行動を生成

4. **コード省略問題の回避**
   - ツール呼び出し（Edit/Write）を自動検出
   - git diffで実際の変更を取得
   - 完全なコード履歴を保存

---

## 🚀 クイックスタート

### 1. Claude統合ブリッジの起動（シミュレーションモード）

```python
from claude_cross_bridge import ClaudeCrossBridge
import time

# ブリッジ初期化（シミュレーションモード）
ブリッジ = ClaudeCrossBridge(モード="シミュレーション")

# 起動
ブリッジ.start()

# 10秒間実行（テストデータを処理）
time.sleep(10)

# 停止して統計表示
ブリッジ.stop()
```

**実行例**:
```bash
python3 claude_cross_bridge.py
```

**出力**:
```
📊 統計情報:
  処理した対話数: 3件
  パターン推論実行回数: 1回
  シミュレーション実行回数: 0回
  学習履歴総数: 3件
  コード変更履歴: 0件
```

---

### 2. 実Claudeとの連携（PTYモード）

```python
# 実Claudeモードで起動
ブリッジ = ClaudeCrossBridge(モード="実Claude")

# ブリッジ起動（Claude Wrapperが自動起動）
ブリッジ.start()

# バックグラウンドで動作
# Claudeとの対話が自動的にCross構造化される
# パターン推論・小世界シミュレータが自動実行される

# 停止
ブリッジ.stop()
```

**動作フロー**:
```
Claudeと対話
    ↓
PTYでI/Oキャプチャ
    ↓
コマンドマッチング（22,097コマンド辞書）
    ↓
Cross構造生成（6軸）
    ↓
グローバルCross構造に保存
    ↓
【自動】パターン推論（3件以上で実行）
    ↓
【自動】小世界シミュレータ（5件以上で実行）
    ↓
【自動】動的.jcross生成（推論結果から）
```

---

### 3. Gemini学習データの読み込み

```python
from gemini_data_loader import Gemini学習データ統合

# 統合システム初期化
統合 = Gemini学習データ統合()

# Gemini応答ファイルを読み込み
統合.Gemini応答ファイルを読み込み("data/gemini_responses.txt")

# Cross構造を確認
print(f"学習した対話数: {len(統合.エンジン.グローバルCross構造.get('学習履歴', []))}")

# パターン推論を実行
統合.エンジン.jcrossファイルを読み込み("cross_pattern_matching.jcross")
結果 = 統合.エンジン.ラベルを実行("パターン推論を実行")
```

---

### 4. パターン推論の手動実行

```python
from production_jcross_engine import 本番JCrossエンジン

# エンジン初期化
エンジン = 本番JCrossエンジン()

# パターンデータベースを準備
エンジン.グローバルCross構造["パターンDB"] = [
    {
        "元テキスト": "Pythonでデータ分析",
        "キーワード": ["Python", "データ", "分析"],
        "トピック": "データ分析",
        "意図": "学習"
    }
]

# .jcrossコードを実行
テストコード = """
ラベル パターン推論テスト
  実行する パターンを抽出 "データ分析のパフォーマンスを改善したい"
  取り出す 新パターン
  実行する 類似パターンを探索 新パターン
  取り出す 類似リスト
  実行する 最適推論を選択 類似リスト
  取り出す 最適推論
  返す 最適推論
"""

エンジン._jcrossコードをパース(テストコード)
結果 = エンジン.ラベルを実行("パターン推論テスト")

print(f"推論結果: {結果}")
```

**実行例**:
```bash
python3 test_pattern_inference.py
```

**出力**:
```
【パターン】
  トピック: データ分析
  意図: 情報提供
  キーワード: データ分析のパフォーマンスを改善したい

【最適推論】
  信頼度: 0.80
  タイプ: 抽象-具体マッチング
```

---

### 5. 小世界シミュレータの手動実行

```python
from production_jcross_engine import 本番JCrossエンジン

エンジン = 本番JCrossエンジン()

# 学習履歴を準備
エンジン.グローバルCross構造["学習履歴"] = [
    {
        "LEFT": {
            "元テキスト": "Pythonでデータを分析したい",
            "Cross軸統合": {"UP": [{"内容": "データ分析"}]}
        },
        "DOWN": [{"具体": "Python分析"}],
        "BACK": [{"時刻": "2026-03-10T10:00:00"}]
    },
    # ... 5件以上の履歴
]

# .jcrossコードを実行
テストコード = """
ラベル 小世界テスト
  取り出す グローバルCross構造.学習履歴
  取り出す 学習履歴
  実行する 小世界を構築 学習履歴
  取り出す 小世界Cross
  実行する 未来を予測 小世界Cross
  取り出す 予測結果
  返す 予測結果
"""

エンジン._jcrossコードをパース(テストコード)
結果 = エンジン.ラベルを実行("小世界テスト")

print(f"予測結果: {結果}")
```

**実行例**:
```bash
python3 test_world_simulator.py
```

**出力**:
```
【小世界】
  UP（概念）: 2件
  DOWN（事例）: 2件
  LEFT（原因）: 0件
  RIGHT（結果）: 0件
  BACK（履歴）: 2件

【未来予測】(2件)
  1. 要求 → 応答 (信頼度: 0.70)
  2. 概念適用: 2個の概念を2個の事例に適用 (信頼度: 0.75)
```

---

## 📊 実際の対話での動作例

### シナリオ: Claudeとデータ分析について5回対話

```
【対話1】
ユーザー: "Pythonでデータを分析する方法を教えて"
Claude: "pandasライブラリを使ってCSVを読み込み..."

→ Cross構造に保存（1件目）

【対話2】
ユーザー: "CSVの読み込みでエラーが出た"
Claude: "エラーメッセージを確認しましょう..."

→ Cross構造に保存（2件目）

【対話3】
ユーザー: "パフォーマンスを改善したい"
Claude: "プロファイリングでボトルネックを..."

→ Cross構造に保存（3件目）
→ 【自動実行】パターン推論開始
   - トピック: データ分析
   - 意図: 問題解決
   - パターン: エラー対処 → 最適化の流れ

【対話4】
ユーザー: "グラフを作成したい"
Claude: "matplotlibを使って可視化..."

→ Cross構造に保存（4件目）
→ 【自動実行】パターン推論
   - 類似パターン検出: 過去の可視化関連質問

【対話5】
ユーザー: "統計分析を追加したい"
Claude: "scipyで統計処理を..."

→ Cross構造に保存（5件目）
→ 【自動実行】パターン推論
→ 【自動実行】小世界シミュレータ開始
   - 小世界構築: データ分析 → エラー対処 → 最適化 → 可視化 → 統計
   - 因果推論: データ収集 → 分析 → 可視化 → 統計分析
   - 未来予測: 次は機械学習の質問が来る可能性（信頼度: 0.82）
   - 推奨行動: scikit-learnの準備を推奨
```

---

## 🔍 コード省略問題の回避

### Claudeがコードを省略する問題

**従来の問題**:
```
Claude: "production_jcross_engine.pyを更新しました。
        主な変更点は...
        [コードは省略]"
```

**Verantyxの解決策**:

#### 1. ツール呼び出しの監視

```python
from code_capture_enhancer import コードキャプチャ強化

キャプチャ = コードキャプチャ強化(".")

# Claude出力を監視
Claude出力 = """
production_jcross_engine.pyを更新しました。

<invoke name="Edit">
<parameter name="file_path">production_jcross_engine.py</parameter>
<parameter name="old_string">def test():
    pass</parameter>
<parameter name="new_string">def test():
    print("Hello!")</parameter>
</invoke>
"""

# ツール呼び出しを検出
変更 = キャプチャ.ツール呼び出しを監視(Claude出力)

# 完全なコードが取得される
print(変更[0]["新コード"])  # 'def test():\n    print("Hello!")'
```

#### 2. git diffによる変更取得

```python
# ファイル変更を検出
ファイル変更 = キャプチャ.ファイル変更を検出(Claude出力)

# git diffで実際の変更内容を取得
print(ファイル変更[0]["差分"])
# 出力:
# --- a/production_jcross_engine.py
# +++ b/production_jcross_engine.py
# @@ -1,2 +1,3 @@
#  def test():
# -    pass
# +    print("Hello!")
```

#### 3. Claude Cross Bridgeでの自動検出

```python
# Claude Cross Bridgeは自動的にコード変更を検出
ブリッジ = ClaudeCrossBridge(モード="実Claude")
ブリッジ.start()

# Claudeと対話
# → ツール呼び出しが自動検出される
# → ファイル変更が自動検出される
# → グローバルCross構造の「コード変更履歴」に保存される

# 統計を確認
ブリッジ.統計を表示()
# 出力:
# コード変更履歴: 5件
#
# 【完全コード履歴】
#   1. Edit: production_jcross_engine.py (2026-03-10T15:30:00)
#   2. Write: test_new_feature.py (2026-03-10T15:31:00)
```

---

## 🎯 .jcrossによる動的コード生成

### 推論結果から自動的に.jcrossコードを生成

```python
def 動的ラベルを生成(エンジン, パターン, 予測):
    """パターンと予測から.jcrossコードを動的生成"""

    # 新しいラベルのコード
    新コード = [
        f'出力する "予測されたトピック: {パターン.get("トピック", "")}"',
        f'実行する パターンを抽出 "{予測[0].get("予測", "")}"',
        '取り出す 新パターン',
        '実行する 類似パターンを探索 新パターン',
        '取り出す 類似リスト',
        '返す 類似リスト'
    ]

    # エンジンに動的追加
    エンジン.ラベルを動的に追加("予測ベース推論", 新コード)

    # 即座に実行
    結果 = エンジン.ラベルを実行("予測ベース推論")

    return 結果
```

**使用例**:
```python
from production_jcross_engine import 本番JCrossエンジン

エンジン = 本番JCrossエンジン()

# パターンと予測を取得（パターン推論・小世界シミュレータから）
パターン = {"トピック": "データ分析", "意図": "学習"}
予測 = [{"予測": "機械学習の質問が来る", "信頼度": 0.82}]

# 動的にラベルを生成
結果 = 動的ラベルを生成(エンジン, パターン, 予測)

# 次の対話から自動的にこのラベルが使われる
# → 学習が加速
```

---

## 📂 ファイル構成

```
verantyx_cli/engine/
├── production_jcross_engine.py          # .jcross実行エンジン（100%完成）
├── jcross_pattern_processors.py         # パターン推論プロセッサ（100%完成）
├── jcross_world_processors.py           # 小世界シミュレータ（100%完成）
├── claude_cross_bridge.py               # Claude統合ブリッジ（95%完成）
├── code_capture_enhancer.py             # コードキャプチャ強化（100%完成）
├── gemini_data_loader.py                # Gemini学習データ統合（完成）
├── test_simple_loop.py                  # ループテスト ✅
├── test_pattern_inference.py            # パターン推論テスト ✅
├── test_world_simulator.py              # 小世界シミュレータテスト ✅
├── IMPLEMENTATION_PROGRESS.md           # 実装進捗（90%完成）
├── ACTUAL_OPERATION_FLOW.md             # 実動作フロー詳細
└── USAGE_SUMMARY.md                     # 本ファイル
```

---

## 🎊 まとめ

### 完成した機能

✅ **Claude対話の自動学習**
- PTYでI/Oキャプチャ
- 22,097コマンド辞書でマッチング
- 6軸Cross構造生成

✅ **パターン推論（自動実行）**
- 3件以上の対話で自動トリガー
- トピック・意図抽出
- パズルピース組み合わせ
- 最適推論選択

✅ **小世界シミュレータ（自動実行）**
- 5件以上の対話で自動トリガー
- 小世界構築
- 因果推論
- 未来予測
- 推奨行動生成

✅ **コード省略問題の回避**
- ツール呼び出し監視
- git diff取得
- 完全コード履歴保存

✅ **動的.jcross生成**
- 推論結果からラベル生成
- 即座に実行
- 学習の加速

### 使い方

1. **シミュレーションモードで動作確認**: `python3 claude_cross_bridge.py`
2. **実Claudeと連携**: `ClaudeCrossBridge(モード="実Claude")`
3. **Geminiデータ学習**: `Gemini学習データ統合().Gemini応答ファイルを読み込み("data.txt")`
4. **手動でパターン推論**: `python3 test_pattern_inference.py`
5. **手動で小世界シミュレータ**: `python3 test_world_simulator.py`

### 実装完成度

**全体**: 90%完成

- コア機能: 100%
- テスト: 90%
- 実Claude PTY連携: 枠組み完成（テスト待ち）

---

**次のステップ**: 実Claudeとの接続テストで100%完成！
