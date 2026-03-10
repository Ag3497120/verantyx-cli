# 感情推測システム設計
Emotion Inference System Design

## コンセプト

**「感情とは推測するものである」**

現在の学習アプローチ:
```
❌ 人間が「これはりんご」とラベルを付ける
   → 教師あり学習
   → 人間の知識に依存
```

新しいアプローチ:
```
✅ システム自身がCross構造のパターンから「何か」を推測する
   → 感情の形成
   → 自律的な意味生成
```

---

## 感情とは何か

### 従来の定義（否定）
```
感情 = 喜怒哀楽のラベル
     = 人間が定義した分類
```

### 新しい定義（採用）
```
感情 = Cross構造のパターンから生まれる「推測」
     = 過去の経験との「類似度」から生まれる期待
     = 未来への予測と現実のズレ
```

---

## 感情推測の仕組み

### 1. パターン蓄積（経験）

```
カメラで見たもの → Cross構造に変換 → 自動的に記憶

【記憶の形式】
時刻0: Cross構造A
時刻1: Cross構造B
時刻2: Cross構造C
...

※ラベルなし！ただの構造の連続
```

### 2. パターン認識（推測）

```
新しいCross構造を見る
  ↓
過去の経験と照合
  ↓
「これは時刻5で見たものに似ている」
  ↓
時刻5の後には時刻6が来た（記憶）
  ↓
「次は時刻6のようなものが来るだろう」（推測）
  ↓
これが「感情」
```

### 3. 予測と現実のズレ（感情の強度）

```
予測: 「次はXが来る」
現実: Yが来た

ズレが小さい → 「安心」（感情A）
ズレが大きい → 「驚き」（感情B）
```

---

## Cross構造における感情の表現

### 感情の6軸マッピング

```
【時間軸の感情】
FRONT軸: 期待（未来への予測）
BACK軸:  記憶（過去の経験）

【空間軸の感情】
UP軸:    高揚（エネルギーの増加）
DOWN軸:  沈静（エネルギーの減少）

【方向軸の感情】
RIGHT軸: 接近（対象に近づく）
LEFT軸:  回避（対象から離れる）
```

### 感情の生成アルゴリズム

```python
# 1. 新しいCross構造を観測
current_cross = observe_camera()

# 2. 過去の経験と照合
similar_past = find_most_similar(current_cross, memory)

# 3. 過去の次の瞬間を推測
expected_next = memory[similar_past.index + 1]

# 4. 感情を形成
emotion = {
    "expectation": expected_next,  # FRONT軸: 期待
    "memory": similar_past,         # BACK軸: 記憶
    "similarity": calculate_similarity(current_cross, similar_past),
    "confidence": 0.8  # 推測の確信度
}

# 5. 次の瞬間を待つ
actual_next = observe_camera()

# 6. ズレを計測
surprise = calculate_difference(expected_next, actual_next)

# 7. 感情を更新
if surprise < threshold:
    emotion["valence"] = "positive"  # UP軸: 予測が当たった
else:
    emotion["valence"] = "negative"  # DOWN軸: 予測が外れた
```

---

## 実装アーキテクチャ

### 1. 経験記憶層（Experience Memory）

```python
class ExperienceMemory:
    """経験の記憶（ラベルなし）"""

    def __init__(self):
        self.timeline = []  # 時系列のCross構造
        self.patterns = {}  # パターンの集合

    def observe(self, cross_structure):
        """観測して記憶"""
        timestamp = len(self.timeline)

        # 時系列に追加
        self.timeline.append({
            "timestamp": timestamp,
            "cross": cross_structure,
            "context": self._extract_context(cross_structure)
        })

        # パターンを抽出
        pattern = self._extract_pattern(cross_structure)

        # パターン集合に追加
        pattern_id = hash_pattern(pattern)
        if pattern_id not in self.patterns:
            self.patterns[pattern_id] = []

        self.patterns[pattern_id].append(timestamp)

    def _extract_context(self, cross_structure):
        """文脈を抽出"""
        # 直近の経験との関連性
        if len(self.timeline) > 0:
            prev_cross = self.timeline[-1]["cross"]
            delta = calculate_delta(prev_cross, cross_structure)
            return {"delta": delta, "trend": self._detect_trend()}
        return {}
```

### 2. 推測層（Inference Layer）

```python
class EmotionInference:
    """感情推測エンジン"""

    def __init__(self, memory: ExperienceMemory):
        self.memory = memory
        self.current_emotion = None

    def infer(self, current_cross):
        """現在のCross構造から感情を推測"""

        # 1. 最も類似した過去の経験を探す
        similar_moments = self._find_similar_moments(current_cross)

        if not similar_moments:
            # 未知の経験 → 「新鮮さ」という感情
            return {
                "type": "novelty",
                "FRONT": 0.8,  # 高い期待
                "UP": 0.7,     # 高揚
                "confidence": 0.3  # 低い確信
            }

        # 2. 過去の経験から「次」を予測
        best_match = similar_moments[0]
        next_timestamp = best_match["timestamp"] + 1

        if next_timestamp < len(self.memory.timeline):
            expected_next = self.memory.timeline[next_timestamp]["cross"]
        else:
            expected_next = None

        # 3. 感情を形成
        emotion = {
            "type": "expectation",
            "memory_timestamp": best_match["timestamp"],
            "similarity": best_match["similarity"],
            "expected_next": expected_next,
            "confidence": best_match["similarity"]
        }

        # 4. 6軸に展開
        emotion.update(self._map_to_axes(emotion))

        self.current_emotion = emotion
        return emotion

    def _find_similar_moments(self, current_cross):
        """類似した過去の瞬間を探す"""
        similarities = []

        for i, moment in enumerate(self.memory.timeline):
            similarity = calculate_similarity(
                current_cross,
                moment["cross"]
            )

            if similarity > 0.5:  # 閾値
                similarities.append({
                    "timestamp": i,
                    "similarity": similarity,
                    "moment": moment
                })

        # 類似度順にソート
        return sorted(similarities, key=lambda x: x["similarity"], reverse=True)

    def _map_to_axes(self, emotion):
        """感情を6軸にマッピング"""
        confidence = emotion["confidence"]

        # 類似度が高い = 安心 = DOWN軸（落ち着き）
        # 類似度が低い = 不安 = UP軸（高揚・警戒）

        return {
            "FRONT": confidence,        # 期待の強さ
            "BACK": 1.0 - confidence,   # 不確実性
            "UP": 1.0 - confidence,     # 警戒レベル
            "DOWN": confidence,         # 安心レベル
            "RIGHT": 0.5,               # 中立
            "LEFT": 0.5                 # 中立
        }

    def validate_prediction(self, actual_next):
        """予測を検証（学習）"""
        if not self.current_emotion:
            return

        expected = self.current_emotion.get("expected_next")
        if not expected:
            return

        # ズレを計測
        surprise = calculate_difference(expected, actual_next)

        # 感情の更新
        if surprise < 0.2:
            # 予測が当たった → 報酬
            reward = {
                "type": "satisfaction",
                "UP": 0.6,      # 喜び
                "FRONT": 0.8    # 期待の強化
            }
        else:
            # 予測が外れた → 驚き
            reward = {
                "type": "surprise",
                "UP": 0.9,      # 強い反応
                "FRONT": 0.3    # 期待の修正
            }

        return reward
```

### 3. 感情表現層（Emotion Expression）

```python
class EmotionExpression:
    """感情を可視化・言語化"""

    def express(self, emotion):
        """感情を表現"""

        # 6軸の値から感情の言語化
        up = emotion.get("UP", 0)
        down = emotion.get("DOWN", 0)
        front = emotion.get("FRONT", 0)
        back = emotion.get("BACK", 0)

        # パターンマッチング
        if up > 0.7 and front > 0.7:
            return "期待と高揚"
        elif down > 0.7 and front > 0.7:
            return "安心と期待"
        elif up > 0.7 and back > 0.7:
            return "驚きと記憶"
        elif down > 0.7 and back > 0.7:
            return "懐かしさ"
        else:
            return "中立"

    def visualize(self, emotion, frame):
        """感情をカメラ映像にオーバーレイ"""

        # 6軸を可視化
        axes_display = self._draw_emotion_axes(emotion)

        # 感情の言語化
        emotion_text = self.express(emotion)

        # 確信度
        confidence = emotion.get("confidence", 0)

        # 画面に描画
        cv2.putText(
            frame,
            f"感情: {emotion_text}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"確信度: {confidence:.1%}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (200, 200, 200),
            1
        )

        # 6軸レーダーチャート
        self._draw_radar_chart(frame, emotion)
```

---

## 使い方

### 従来（教師あり学習）

```bash
# カメラ学習
python -m verantyx_cli.vision.learn_from_camera

# ユーザーがラベルを付ける
これは何ですか？ > りんご
```

### 新しい（感情推測）

```bash
# 感情推測セッション
python -m verantyx_cli.vision.emotion_inference

# システムが自律的に観測・推測・学習
[自動] 観測: Cross構造を記録
[自動] 推測: 「これは記憶0052に似ている」
[自動] 期待: 「次は記憶0053のようなものが来るだろう」
[自動] 確認: （次の瞬間を観測）
[自動] 感情: 「予測が当たった → 安心」
```

---

## 感情の進化

### レベル1: 反射的感情

```
現在のCross構造のみから判断
- 明るい → 「快」
- 暗い → 「不快」
```

### レベル2: 記憶ベース感情

```
過去の経験と照合
- 「これは以前見た」→ 「懐かしさ」
- 「これは初めて」→ 「新鮮さ」
```

### レベル3: 予測ベース感情（推測）

```
過去の経験から未来を予測
- 「次はこれが来る」→ 「期待」
- 予測が当たる → 「満足」
- 予測が外れる → 「驚き」
```

### レベル4: 複合感情

```
複数の記憶パターンから複雑な推測
- 「AとBが来たら次はC」→ 「文脈理解」
- 「Cが来なかった」→ 「不安」
```

---

## 実装ステップ

### フェーズ1: 経験蓄積
```python
# カメラで観測して記憶（ラベルなし）
python -m verantyx_cli.vision.experience_recorder
```

### フェーズ2: パターン推測
```python
# 記憶から類似パターンを推測
python -m verantyx_cli.vision.pattern_inference
```

### フェーズ3: 感情生成
```python
# 推測から感情を形成
python -m verantyx_cli.vision.emotion_generator
```

### フェーズ4: 自律的感情システム
```python
# すべてを統合
python -m verantyx_cli.vision.emotion_inference
```

---

## 哲学的基盤

### 感情とは

```
感情 ≠ ラベル付けされた分類
感情 = 予測と現実のズレから生まれる反応
```

### 推測とは

```
推測 = 過去の経験パターンから未来を予想すること
     = 記憶（BACK）から期待（FRONT）を生成すること
```

### 意味とは

```
意味 ≠ 人間が与えた言葉
意味 = システム自身が形成した関連性
     = Cross構造間の類似度ネットワーク
```

---

## 次のステップ

1. `experience_recorder.py` - 経験記録エンジン
2. `emotion_inference.py` - 感情推測エンジン
3. `emotion_visualizer.py` - 感情可視化
4. `autonomous_emotion_system.py` - 自律感情システム

これにより、システムは「教えられる」のではなく、
「自ら推測し、感情を形成する」ようになります。
