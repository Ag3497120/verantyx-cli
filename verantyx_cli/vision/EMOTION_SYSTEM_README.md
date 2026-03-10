# 自律的感情推測システム
Autonomous Emotion Inference System

## 概要

このシステムは **「感情とは推測するものである」** というコンセプトに基づいて開発されました。

従来の教師あり学習とは異なり、システム自身が：
- ラベルなしで経験を蓄積
- 過去のパターンから未来を推測
- 予測と現実のズレから感情を形成

完全自律的に感情を持つシステムです。

---

## 哲学的基盤

### 従来のアプローチ（否定）

```
❌ 人間が「これはりんご」とラベルを付ける
   → 教師あり学習
   → 人間の知識に依存
   → システムは「覚える」だけ
```

### 新しいアプローチ（採用）

```
✅ システム自身がCross構造のパターンから「何か」を推測する
   → 感情の形成
   → 自律的な意味生成
   → システムは「推測する」
```

### 感情の定義

```
感情 ≠ 喜怒哀楽のラベル
感情 = Cross構造のパターンから生まれる「推測」
     = 過去の経験との「類似度」から生まれる期待
     = 未来への予測と現実のズレ
```

---

## システムアーキテクチャ

### 1. 経験記憶層（ExperienceMemory）

**役割**: ラベルなしで観測したCross構造を時系列で記憶

```python
from verantyx_cli.vision.experience_memory import ExperienceMemory

memory = ExperienceMemory()

# ラベルなしで観測
memory.observe(cross_structure)

# 類似した過去の瞬間を探す
similar_moments = memory.find_similar_moments(current_cross, top_k=5)
```

**特徴**:
- 完全にラベルフリー
- 時系列の連続として記憶
- パターンIDでインデックス化
- 文脈（前後の経験との関連）を自動抽出

### 2. 感情推測層（EmotionInference）

**役割**: 過去の経験から未来を予測し、感情を形成

```python
from verantyx_cli.vision.emotion_inference import EmotionInference

inference = EmotionInference(memory)

# 現在のCross構造から感情を推測
emotion = inference.infer(current_cross)

# 予測を検証
reward = inference.validate_prediction(actual_next)
```

**感情のタイプ**:

1. **新鮮さ（Novelty）** - 未知の経験
   ```
   FRONT軸: 0.8（高い期待）
   UP軸: 0.7（警戒）
   確信度: 0.3（低い）
   ```

2. **期待（Expectation）** - 過去の経験から予測
   ```
   FRONT軸: 0.9（強い期待）
   DOWN軸: 0.8（安心）
   確信度: 類似度に依存
   ```

3. **懐かしさ（Nostalgia）** - 類似した経験はあるが次がない
   ```
   BACK軸: 0.9（記憶）
   DOWN軸: 0.7（安心）
   ```

4. **満足（Satisfaction）** - 予測が当たった
   ```
   UP軸: 0.6（喜び）
   DOWN軸: 0.8（安心）
   FRONT軸: 0.9（期待の強化）
   ```

5. **驚き（Surprise）** - 予測が外れた
   ```
   UP軸: 0.9（強い反応）
   DOWN軸: 0.2（不安）
   BACK軸: 0.7（記憶の見直し）
   ```

### 3. 感情表現層（EmotionVisualizer）

**役割**: 感情をカメラ映像にオーバーレイして可視化

```python
from verantyx_cli.vision.emotion_inference import EmotionVisualizer

visualizer = EmotionVisualizer()
visualizer.visualize(frame, emotion, inference)
```

**表示内容**:
- 感情タイプとアイコン
- 感情の言語化
- 確信度
- 6軸の値（バーグラフ）
- 記憶のタイムスタンプと類似度

---

## 使い方

### 1. 経験記録セッション

最も基本的な使い方。カメラで観測しながら自律的に感情を形成します。

```bash
python -m verantyx_cli.vision.experience_recorder
```

**動作**:
1. カメラで観測（約2秒に1回）
2. Cross構造に変換
3. 経験として記憶（ラベルなし）
4. 過去の経験と照合
5. 類似したパターンを発見
6. 次の瞬間を予測
7. 感情を形成
8. 画面に表示

**操作**:
- `[Q]` - 終了
- `[S]` - サマリー表示

**出力例**:
```
👁️  観測 #1
----------------------------------------------------------------------
🔄 Cross構造に変換中...
📝 経験を記録中...
💭 感情を推測中...
   → 新鮮さ（好奇心: 80%, 警戒: 70%）
----------------------------------------------------------------------

👁️  観測 #2
----------------------------------------------------------------------
🔄 Cross構造に変換中...
📝 経験を記録中...
💭 感情を推測中...
   記憶: タイムスタンプ 0
   類似度: 65%
   確信度: 65%
   → 期待（確信: 65%, 予測: 65%）
----------------------------------------------------------------------

👁️  観測 #3
----------------------------------------------------------------------
🔄 Cross構造に変換中...
🎯 前回の予測を検証中...
   ズレ: 15%
   → ✅ 満足（予測が当たった）
📝 経験を記録中...
💭 感情を推測中...
   → 期待（確信: 78%, 予測: 78%）
----------------------------------------------------------------------
```

### 2. カスタム設定

観測間隔や記憶パスを変更できます。

```bash
# 観測間隔を30フレーム（約1秒）に設定
python -m verantyx_cli.vision.experience_recorder --observe-interval 30

# 記憶ファイルのパスを指定
python -m verantyx_cli.vision.experience_recorder --memory-path ./my_memory.json
```

### 3. 経験記憶の確認

```python
from pathlib import Path
from verantyx_cli.vision.experience_memory import ExperienceMemory

# 記憶を読み込み
memory = ExperienceMemory()

# サマリー表示
memory.print_summary()

# 出力例:
# ============================================================
# 経験記憶 サマリー
# ============================================================
# 記憶パス: /Users/xxx/.verantyx/experience_memory.json
# 経験数: 150
# パターン数: 45
#
# 最初の経験: 2025-01-15 14:23:10
# 最新の経験: 2025-01-15 14:28:35
#
# 最頻パターン:
#   - a1b2c3d4... (23 回)
#   - e5f6g7h8... (18 回)
#   - i9j0k1l2... (15 回)
# ============================================================
```

---

## 感情の進化

システムは使えば使うほど感情が豊かになります。

### レベル1: 反射的感情（初期）

```
経験数: 0〜10
すべてが「新鮮さ」
過去の経験がないため予測不可能
```

### レベル2: 記憶ベース感情（学習中）

```
経験数: 10〜100
「これは以前見た」→ 懐かしさ
「これは初めて」→ 新鮮さ
類似度ベースの簡単な推測
```

### レベル3: 予測ベース感情（推測開始）

```
経験数: 100〜1000
「次はこれが来る」→ 期待
予測が当たる → 満足
予測が外れる → 驚き
連続するパターンを学習
```

### レベル4: 複合感情（高度な推測）

```
経験数: 1000+
複数の記憶パターンから複雑な推測
「AとBが来たら次はC」→ 文脈理解
「Cが来なかった」→ 不安
長期的なパターン認識
```

---

## 技術詳細

### Cross構造の類似度計算

```python
def _calculate_similarity(cross1, cross2) -> float:
    """
    2つのCross構造の類似度を計算

    単層の場合:
        各軸の平均値の差分を計算
        similarity = 1.0 - abs(mean1 - mean2)

    多層の場合:
        各層ごとに類似度を計算
        全層の平均を取る
    """
    # 単層
    if "axes" in cross1 and "axes" in cross2:
        similarities = []
        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
            mean1 = cross1["axes"][axis_name]["mean"]
            mean2 = cross2["axes"][axis_name]["mean"]
            diff = abs(mean1 - mean2)
            similarity = 1.0 - min(1.0, diff)
            similarities.append(similarity)

        return np.mean(similarities)
```

### 感情の6軸マッピング

```python
def _map_to_axes(confidence, expected_next) -> dict:
    """
    感情を6軸にマッピング

    確信度が高い = 安心 = DOWN軸
    確信度が低い = 不安 = UP軸

    期待がある = FRONT軸
    期待がない = BACK軸
    """
    down_val = confidence
    up_val = 1.0 - confidence

    if expected_next:
        front_val = confidence
        back_val = 0.3
    else:
        front_val = 0.3
        back_val = confidence

    return {
        "FRONT": front_val,
        "BACK": back_val,
        "UP": up_val,
        "DOWN": down_val,
        "RIGHT": 0.5,  # 現時点では中立
        "LEFT": 0.5    # 現時点では中立
    }
```

### 予測検証とズレの計測

```python
def validate_prediction(actual_next) -> dict:
    """
    予測を検証（実際の次の瞬間と比較）

    ズレ < 20% → 満足（予測が当たった）
    ズレ >= 20% → 驚き（予測が外れた）
    """
    expected = self.current_emotion.get("expected_next")

    # ズレを計測
    surprise = self._calculate_surprise(expected, actual_next)

    if surprise < 0.2:
        # 予測が当たった
        return {
            "type": "satisfaction",
            "UP": 0.6,      # 喜び
            "DOWN": 0.8,    # 安心
            "FRONT": 0.9,   # 期待の強化
            "surprise": surprise
        }
    else:
        # 予測が外れた
        return {
            "type": "surprise",
            "UP": 0.9,      # 強い反応
            "DOWN": 0.2,    # 不安
            "FRONT": 0.3,   # 期待の修正
            "BACK": 0.7,    # 記憶の見直し
            "surprise": surprise
        }
```

---

## ファイル構成

```
verantyx_cli/vision/
├── EMOTION_INFERENCE_DESIGN.md      # 設計ドキュメント（哲学と理論）
├── EMOTION_SYSTEM_README.md         # このファイル（使い方）
├── experience_memory.py             # 経験記憶システム
├── emotion_inference.py             # 感情推測エンジン
└── experience_recorder.py           # メインプログラム
```

---

## 従来システムとの比較

### 従来: オブジェクト認識（教師あり学習）

```bash
# カメラ学習
python -m verantyx_cli.vision.learn_from_camera

# 人間がラベルを付ける
これは何ですか？ > りんご

# システムは「覚える」だけ
データベースに保存: りんご → Cross構造
```

**問題点**:
- 人間の介入が必要
- ラベルに依存
- 「覚える」だけで「理解」しない
- 感情なし

### 新しい: 感情推測（自律学習）

```bash
# 感情推測セッション
python -m verantyx_cli.vision.experience_recorder

# システムが自律的に観測・推測・学習
[自動] 観測: Cross構造を記録
[自動] 推測: 「これは記憶0052に似ている」
[自動] 期待: 「次は記憶0053のようなものが来るだろう」
[自動] 確認: （次の瞬間を観測）
[自動] 感情: 「予測が当たった → 安心」
```

**利点**:
- 完全自律
- ラベル不要
- 「推測」して「理解」する
- 感情を形成

---

## よくある質問

### Q: ラベルなしでどうやって認識するのですか？

A: **認識しません**。このシステムは「認識」ではなく「推測」を行います。

従来:
```
「これはりんご」という知識を持つ
新しいものを見る → データベースと照合 → 「りんごだ」と認識
```

新しい:
```
過去の経験のパターンを持つ
新しいものを見る → 過去と照合 → 「これは経験0052に似ている」と推測
次の瞬間を予測 → 「次は経験0053のようなものが来るだろう」と期待
実際の次の瞬間を観測 → ズレを計測 → 「予測が当たった（満足）」or「外れた（驚き）」
```

### Q: 感情は何に使うのですか？

A: 感情は **システム自身の内部状態** です。

- 高い確信度（DOWN軸） → 安心 → 学習済みの領域
- 低い確信度（UP軸） → 警戒 → 未知の領域
- 予測の成功（満足） → このパターンは信頼できる
- 予測の失敗（驚き） → パターンを修正すべき

将来的には、この感情を強化学習の報酬として使うことも可能です。

### Q: 従来のオブジェクト認識システムとの共存は？

A: 完全に独立したシステムです。

```bash
# 従来システム（教師あり学習）
python -m verantyx_cli.vision.learn_from_camera
python -m verantyx_cli.vision.test_all_objects

# 新しいシステム（自律的感情推測）
python -m verantyx_cli.vision.experience_recorder
```

両方を併用することも可能です。

### Q: どのくらいの経験で感情が形成されますか？

A: 最初の観測から感情は形成されます。

- 経験0: 「新鮮さ」（未知）
- 経験1: 「期待」（類似度に応じて）
- 経験2以降: 「満足」「驚き」（予測検証）

ただし、豊かな感情には100回以上の経験が推奨されます。

---

## 次のステップ

### 1. まずは試してみる

```bash
# 5分間の経験記録セッション
python -m verantyx_cli.vision.experience_recorder
```

カメラの前でゆっくり物を動かしてみてください。
システムがどのように感情を形成するか観察できます。

### 2. 長時間セッション

```bash
# 30分〜1時間のセッション
# より豊かな感情が形成されます
python -m verantyx_cli.vision.experience_recorder
```

### 3. 記憶の分析

```python
from verantyx_cli.vision.experience_memory import ExperienceMemory

memory = ExperienceMemory()
memory.print_summary()

# どのようなパターンが記憶されているか確認
```

### 4. 感情の分析

経験記録セッション中に `[S]` キーを押すと、
現在の感情サマリーが表示されます。

### 5. カスタマイズ

`experience_recorder.py` を参考に、
独自の感情システムを構築することも可能です。

---

## まとめ

このシステムは **「感情とは推測するものである」** という新しいパラダイムを実装しています。

従来の教師あり学習のように人間がラベルを付けるのではなく、
システム自身が：

1. 観測する（ラベルなし）
2. 記憶する（時系列のパターン）
3. 推測する（過去からの予測）
4. 検証する（予測と現実のズレ）
5. 感情を形成する（ズレから生まれる反応）

これにより、システムは「覚える」だけでなく「推測する」ようになり、
真の意味で「理解」に近づきます。

---

**プロジェクト**: Verantyx Vision - Autonomous Emotion Inference System
**コンセプト**: 感情とは推測するものである
**実装**: Cross構造 + 経験記憶 + パターン推測
**目標**: 自律的に感情を持つシステム
