# 本番レベル.jcross実装の使い方

## 🚀 クイックスタート

### 1. 本番デーモンを起動

```bash
cd /Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine

# テストモードで起動（ランダム画像20フレーム）
python3 production_jcross_daemon.py
```

**出力例**:
```
================================================================================
本番レベルJCross学習デーモン
================================================================================

📖 感情DNAを読み込み: .../emotion_dna_cross.jcross
✅ 感情DNA + 学習エンジン 初期化完了
✅ 本番JCrossDaemon初期化完了

Frame 1: 同調=0.000, 感情=悲しみ(0.50), 予測=✗, パターン=0, 412ms
...
Frame 20: 同調=1.000, 感情=悲しみ(0.68), 予測=✗, パターン=2, 395ms

初期5フレーム平均強度: 0.500
最終5フレーム平均強度: 0.678
向上: +0.178
```

---

## 📋 主要な使い方

### 方法1: Pythonスクリプトから使う

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')

from production_jcross_daemon import ProductionJCrossDaemon
from PIL import Image
import numpy as np

# デーモンを初期化
daemon = ProductionJCrossDaemon()

# 画像を処理
image = Image.open("your_image.jpg")
result = daemon.process_image_frame(image)

print(f"発火感情: {result['emotion']}")
print(f"感情強度: {result['emotion_intensity']:.3f}")
print(f"学習効果: {result['learning_stats']}")
```

---

### 方法2: 学習統合感情判定を単体で使う

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')

from emotion_dna_system_with_learning import EmotionDNASystemWithLearning

# システムを初期化
system = EmotionDNASystemWithLearning()

# 生理状態
physiological = {
    '体温': 37.5,
    '血圧': 140.0,
    '心拍数': 130.0,
    '血糖値': 90.0,
    '痛み': 60.0,  # 高い痛み → 恐怖発火
    'エネルギー': 0.8
}

# 認知状態
cognitive = {
    '新規性': 0.3,
    '予測成功': 0.1,
    '予測失敗': 0.8,
    '学習成功': 0.2,
    '理解': 0.3
}

# 感情判定（学習統合）
emotion = system.determine_emotion(physiological, cognitive)

print(f"発火感情: {system.current_emotion_name}")
print(f"感情強度: {system.current_emotion_intensity:.3f}")
print(f"リソース配分: {system.get_resource_allocation()}")
print(f"同調モード: {system.get_sync_mode()}")

# 学習統計
stats = system.get_learning_stats()
print(f"学習統計: {stats}")
```

---

### 方法3: 学習エンジンを単体で使う

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')

from jcross_learning_engine import JCrossLearningEngine

# 学習エンジンを初期化
engine = JCrossLearningEngine()

# Hebbian学習
active_crosses = {
    "恐怖Cross": 0.9,
    "心拍数Cross": 0.8,
    "逃走Cross": 0.7
}

# 10回学習
for i in range(10):
    engine.hebbian_learn(active_crosses, learning_rate=0.02)

# 結合強度を確認
connection = engine.connection_matrix.get_connection("恐怖Cross", "心拍数Cross")
print(f"恐怖⇔心拍数の結合強度: {connection:.4f}")

# 検出されたパターン
patterns = engine.pattern_detector.get_patterns(min_frequency=3)
print(f"検出パターン: {len(patterns)}個")

# 次のアクティベーションを予測
predicted = engine.predict_next_activation(["恐怖Cross"])
print(f"予測: {predicted}")
```

---

## 📊 学習効果を確認する

### 学習前後の比較

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')

from emotion_dna_system_with_learning import EmotionDNASystemWithLearning

system = EmotionDNASystemWithLearning()

# 同じ状況を用意
phys = {'体温': 37.5, '血圧': 140.0, '心拍数': 130.0, '血糖値': 90.0, '痛み': 60.0, 'エネルギー': 0.8}
cogn = {'新規性': 0.3, '予測成功': 0.1, '予測失敗': 0.8, '学習成功': 0.2, '理解': 0.3}

# 初回
system.determine_emotion(phys, cogn)
initial_intensity = system.current_emotion_intensity
print(f"初回強度: {initial_intensity:.3f}")

# 同じ状況を9回繰り返し（学習）
for i in range(9):
    system.determine_emotion(phys, cogn)

# 10回目
system.determine_emotion(phys, cogn)
final_intensity = system.current_emotion_intensity
print(f"10回後強度: {final_intensity:.3f}")

improvement = final_intensity - initial_intensity
print(f"向上: +{improvement:.3f} (+{improvement/initial_intensity*100:.1f}%)")

# 学習履歴を確認
for i, h in enumerate(system.learning_history[:3]):
    print(f"\nフレーム{i+1}:")
    print(f"  ベース強度: {h['base_intensity']:.3f}")
    print(f"  学習ブースト: {h['learning_boost']:.3f}")
    print(f"  パターンボーナス: {h['pattern_bonus']:.3f}")
    print(f"  最終強度: {h['intensity']:.3f}")
```

---

## 🎯 実用例

### 例1: カメラ映像からの学習

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')

import cv2
from PIL import Image
from production_jcross_daemon import ProductionJCrossDaemon

# デーモン初期化
daemon = ProductionJCrossDaemon()

# カメラをオープン
cap = cv2.VideoCapture(0)

frame_count = 0
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # OpenCV BGR → PIL RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)

        # 処理
        result = daemon.process_image_frame(pil_image)

        print(f"Frame {frame_count}: {result['emotion']} ({result['emotion_intensity']:.3f})")

        frame_count += 1

        # ESCで終了
        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    cap.release()
    daemon.save_learning_history()
    print(f"\n学習履歴を保存しました")
```

---

### 例2: 画像フォルダからバッチ学習

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')

from pathlib import Path
from PIL import Image
from production_jcross_daemon import ProductionJCrossDaemon

# デーモン初期化
daemon = ProductionJCrossDaemon()

# 画像フォルダ
image_folder = Path("~/Pictures").expanduser()
image_files = list(image_folder.glob("*.jpg"))[:50]  # 最初の50枚

print(f"画像を処理中: {len(image_files)}枚")

for i, image_file in enumerate(image_files):
    image = Image.open(image_file)
    result = daemon.process_image_frame(image)

    if (i + 1) % 10 == 0:
        print(f"{i+1}枚処理完了")

# 学習効果を確認
if len(daemon.learning_history) >= 10:
    initial = daemon.learning_history[:5]
    final = daemon.learning_history[-5:]

    initial_avg = sum(h['emotion_intensity'] for h in initial) / len(initial)
    final_avg = sum(h['emotion_intensity'] for h in final) / len(final)

    print(f"\n初期平均強度: {initial_avg:.3f}")
    print(f"最終平均強度: {final_avg:.3f}")
    print(f"向上: +{final_avg - initial_avg:.3f}")

daemon.save_learning_history()
```

---

### 例3: 独自の感情Crossを追加

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')

from jcross_interpreter import JCrossInterpreter
from emotion_dna_system_with_learning import EmotionDNASystemWithLearning

# 独自の感情Cross定義（.jcross形式）
custom_jcross = """
生成する 驚きCross = {
  "UP": [
    {"点": 0, "優先度": 8, "意味": "高優先度"}
  ],
  "RIGHT": [
    {"点": 0, "リソース": "探索", "配分": 0.9},
    {"点": 1, "リソース": "学習", "配分": 0.8},
    {"点": 2, "リソース": "予測", "配分": 0.7}
  ],
  "LEFT": [
    {"点": 0, "同調モード": "能動探索モード"}
  ],
  "FRONT": [
    {"点": 0, "発火条件": "新規性 > 0.9"},
    {"点": 1, "発火条件": "予測失敗 > 0.8"}
  ]
}
"""

# インタプリタで読み込み
interpreter = JCrossInterpreter()
# 一時ファイルに書き込んで読み込む方法
with open('/tmp/custom_emotion.jcross', 'w') as f:
    f.write(custom_jcross)

data = interpreter.load_file('/tmp/custom_emotion.jcross')
print(f"読み込んだCross: {list(data.keys())}")

# システムに統合
# （実際にはemotion_dna_cross.jcrossに追記するか、
#  システムの初期化時にマージする）
```

---

## 📂 ログとデータの保存場所

```bash
# 学習ログ
~/.verantyx/production_logs/production_daemon_*.log

# 学習履歴（JSON）
~/.verantyx/production_logs/production_history_*.json
```

### 学習履歴の読み方

```python
import json

with open('~/.verantyx/production_logs/production_history_*.json') as f:
    history = json.load(f)

# 学習効果の可視化
import matplotlib.pyplot as plt

frames = [h['frame'] for h in history]
intensities = [h['emotion_intensity'] for h in history]

plt.plot(frames, intensities)
plt.xlabel('Frame')
plt.ylabel('Emotion Intensity')
plt.title('Learning Effect')
plt.savefig('learning_effect.png')
```

---

## 🔧 設定のカスタマイズ

### 学習率の調整

```python
daemon = ProductionJCrossDaemon()

# デフォルト: learning_rate=0.02
# より速く学習: learning_rate=0.05
# よりゆっくり学習: learning_rate=0.01

# 学習エンジンの学習率を変更
daemon.emotion_system.learning_engine.hebbian_learn(
    active_crosses,
    learning_rate=0.05  # カスタム学習率
)
```

### パターン検出の閾値調整

```python
from jcross_learning_engine import JCrossLearningEngine

# パターン検出閾値を変更
engine = JCrossLearningEngine()
engine.pattern_detector.pattern_threshold = 0.9  # デフォルト: 0.8
```

---

## 🚨 トラブルシューティング

### Q: "Module not found" エラーが出る
```bash
# sys.pathを正しく設定
import sys
sys.path.insert(0, '/Users/motonishikoudai/verantyx_v6/verantyx-cli/verantyx_cli/engine')
```

### Q: CuPyが無い警告が出る
```
⚠️  CuPy not available - using CPU fallback
```
→ 問題ありません。CPUで動作します。GPUを使いたい場合：
```bash
pip3 install cupy
```

### Q: 学習効果が見られない
- 同じ状況を繰り返していますか？
- 学習率が低すぎませんか？（デフォルト0.02）
- 少なくとも10回は同じパターンを見せてください

### Q: メモリ使用量が多い
```python
# Cross記憶バンクのサイズを調整
daemon.max_memory_size = 50  # デフォルト: 100
```

---

## 📖 次のステップ

### 1. 実際のカメラで試す
```bash
python3 production_jcross_daemon.py
# → 例1のカメラコードを使用
```

### 2. 独自の感情を追加
- `emotion_dna_cross.jcross`を編集
- 新しい感情Crossを追加

### 3. 学習結果を分析
- 学習履歴JSONを解析
- グラフ化して可視化

### 4. Verantyx CLIと統合
```bash
cd /Users/motonishikoudai/verantyx_v6/verantyx-cli
# 既存のCLIから本番デーモンを呼び出す
```

---

## 📚 関連ドキュメント

- `PRODUCTION_LEVEL_ACHIEVED.md` - 本番レベル達成の証明
- `FULL_JCROSS_SYSTEM_SUMMARY.md` - システム全体のサマリー
- `STAGE_3_6_IMPLEMENTATION_PLAN.md` - Stage 3-6の実装計画

---

**作成日**: 2026-03-09
**対象**: 本番レベル実装 (95-100%)
