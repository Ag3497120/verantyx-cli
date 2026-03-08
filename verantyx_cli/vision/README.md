# Verantyx Vision Module

Cross Simulationによる画像・動画認識

## 機能

### 1. 基本的なCross変換
- `image_to_cross.py`: 画像 → Cross構造
- `video_to_cross.py`: 動画 → Cross構造（フレームごと）
- `cross_simulator.py`: Cross Simulation（世界モデル）

### 2. Cross形状認識（JCross実装）
- `shape_recognition.jcross`: 形状認識プログラム
- `vision_processors.py`: 形状認識用プロセッサ
- `run_shape_recognition.py`: スタンドアロンランナー

**特徴:**
- Cross構造の点配置パターンから形状を認識
- 断片記憶（形状パターンの記憶層）
- OCR等の外部ツール不要

### 3. 動的JCross動画解析（NEW）

#### 3-1. 基本版
- `dynamic_video_analysis.jcross`: 基本実装
- `run_dynamic_video_analysis.py`: 基本版ランナー

**機能:**
- フレーム抽出（30fps）
- ARC-AGI2グリッド変換（32x32、10色）
- フレーム間差分検出
- 基本レポート生成

#### 3-2. フル実装版（★推奨）
- `dynamic_video_analysis_full.jcross`: フル実装
- `run_dynamic_full.py`: フル実装ランナー

**機能:**
1. **JCrossコード動的生成**
   - フレーム間の変化をJCrossコードの動的変更として表現
   - 点追加・削除・移動・色変更の命令を自動生成

2. **Cross層マッピング**
   - FRONT軸: 追加命令
   - BACK軸: 削除命令
   - UP/DOWN軸: 属性変化
   - RIGHT/LEFT軸: 移動
   - TIME軸: 時系列情報

3. **コード変容観察**
   - 各軸のパターン解析
   - 変化頻度の計測
   - コードの進化を追跡

4. **詳細レポート生成**
   - 全体統計
   - Cross軸別パターン
   - JCrossコード変更詳細
   - Cross層マッピング結果

### 4. 多層Cross構造（★NEW - 超高密度認識）

#### 4-1. 多層Cross変換
- `multi_layer_cross.py`: 画像を5層のCross構造に変換
- `theme_memory_bank.py`: テーマ別学習・認識システム
- `multi_layer_processors.py`: 多層Cross用プロセッサ（25個）

**特徴:**
- **5層構造**: Pixel → Feature → Pattern → Semantic → Concept
- **超高密度**: 総計26万点（従来の5倍以上）
- **6軸相互接続**: 層間・層内で6軸方向に接続
- **情報密度**: 約3,760万次元（従来の125倍）

**層構成:**
```
Layer 0: Pixel Layer     (200,000点) - 超高密度画素レベル
Layer 1: Feature Layer   ( 50,000点) - エッジ・テクスチャ
Layer 2: Pattern Layer   ( 10,000点) - 基本形状・パターン
Layer 3: Semantic Layer  (  1,000点) - 意味・オブジェクト
Layer 4: Concept Layer   (    100点) - 抽象概念・シーン
```

#### 4-2. テーマ別学習
- `learn_themes.jcross`: テーマ学習プログラム
- `run_theme_learning.py`: テーマ学習ランナー

**テーマ:**
- 自然要素: sky (空), cloud (雲), flower (花), tree (木), water (水)
- 人工物: building (建物), road (道路), car (車), text (テキスト)
- 生物: human (人間), face (顔), animal (動物)

**学習フロー:**
```
ユーザーの写真
  ↓
【1】テーマごとに5枚ずつ検索
  ↓
【2】各写真を5層×6軸のCross構造に変換（26万点）
  ↓
【3】共通パターンを抽出（5層×6軸）
  ↓
【4】テーマ特徴署名を生成
  ↓
【5】テーマ記憶バンクに保存
```

### 5. 世界の真理システム（★NEW - 物理法則の学習）

#### 5-1. Cross物理シミュレータ
- `cross_physics_simulator.py`: Cross構造上での物理シミュレーション
- `world_truth_memory.py`: 世界の真理記憶バンク
- `physics_processors.py`: 物理シミュレーション用プロセッサ（25個）

**特徴:**
- **物理法則**: 重力、慣性、衝突、摩擦、境界
- **世界の真理**: falling (落下), horizontal_motion (水平移動), projectile (放物運動)
- **時系列シミュレーション**: 60 FPS で物理演算
- **真理認識**: 動画から物理的振る舞いを自動検出

**物理法則:**
```
GravityLaw: 重力（DOWN軸方向に加速）
InertiaLaw: 慣性（等速運動）
CollisionLaw: 衝突（地面との反発）
FrictionLaw: 摩擦（速度減衰）
BoundaryLaw: 境界（空間の端で反射）
```

#### 5-2. 世界真理学習
- `learn_world_truths.jcross`: 世界真理学習プログラム
- `run_truth_learning.py`: 世界真理学習ランナー

**学習フロー:**
```
【1】物理シミュレーション実行（2秒間、60 FPS）
  ↓
【2】時系列Cross構造を生成（120フレーム）
  ↓
【3】6軸の時系列パターンを抽出
  ↓
【4】軸の変化特性を解析（トレンド、変化率、パターンタイプ）
  ↓
【5】真理として記憶バンクに保存
```

**動画認識への適用:**
```
動画のCross構造時系列
  ↓
【1】各軸の時系列パターンを抽出
  ↓
【2】学習済み真理と照合（パターンマッチング）
  ↓
【3】最も類似度の高い真理を検出
  ↓
【4】物理的文脈を考慮した形状認識
  - 落下中 → 「物体」である可能性が高い
  - 静止 → 「背景」の可能性
```

### 6. 適応的解像度システム（★NEW - 自己変容型JCross）

#### 6-1. 適応的解像度制御
- `adaptive_resolution_controller.py`: 解像度動的調整コントローラ
- `self_modifying_jcross.py`: JCross自己変容生成器
- `adaptive_processors.py`: 適応的解析用プロセッサ（20個）

**特徴:**
- **状態遷移検出**: フレーム間差分から自動検出
- **動的解像度調整**: 50K → 1M点まで自動切り替え
- **JCross自己変容**: コード自体が状態に応じて書き換わる
- **効率的処理**: 通常時は低解像度、重要シーンで高解像度

**解像度レベル:**
```
very_low:   10,000点 - 最低解像度
low:        50,000点 - 通常時（デフォルト）
medium:    100,000点 - 小変化検出時
high:      200,000点 - 中変化検出時
very_high: 500,000点 - 大変化検出時
ultra:   1,000,000点 - 急激な変化検出時
```

**状態遷移タイプ:**
```
sudden:   変化量 > 0.5 → ultra (1M点)
moderate: 変化量 > 0.3 → very_high (500K点)
gradual:  変化量 > 0.1 → high (200K点)
none:     変化量 < 0.1 → low (50K点)
```

#### 6-2. 自己変容型JCross
- `adaptive_video_analysis.jcross`: 適応的動画解析プログラム
- `run_adaptive_analysis.py`: 適応的解析ランナー

**自己変容の仕組み:**
```jcross
# 通常時のコード
実行する convert.frame = {"max_points": 50000}

↓ 状態遷移検出！

# 自動的に書き換わる
実行する convert.frame = {"max_points": 1000000}
実行する analyze.detail = {"precision": "ultra"}
実行する track.objects = {"method": "dense"}
```

### 7. カメラ学習（★NEW - リアルタイム物体学習）

#### 7-1. カメラベースの物体学習
- `learn_from_camera.py`: MacBookカメラで物体を学習
- `object_cross_database.py`: 物体Cross構造データベース

#### 7-2. 学習リファレンス資料
- `CROSS_HOUSEHOLD_OBJECT_REFERENCE.md`: 20,000+家庭内物体のCross構造リファレンス
- `CROSS_3D_VISUAL_GUIDE.md`: Cross構造の3D視覚表現ガイド
- `cross_transformation_examples.jcross`: JCross変換実例集

**特徴:**
- **インタラクティブ学習**: カメラに物を見せてラベル付け
- **リアルタイム認識**: 学習した物体をリアルタイムで認識
- **Cross構造記憶**: 多層Cross構造で物体を記憶
- **認識精度向上**: 複数サンプルで精度向上

**学習フロー:**
```
【1】カメラ起動
  ↓
【2】物をカメラに見せる
  ↓
【3】スペースキーでキャプチャ
  ↓
【4】Cross構造に変換（26万点）
  ↓
【5】「これは何ですか？」と質問
  ↓
【6】ユーザーがラベル入力（例: "りんご"）
  ↓
【7】データベースに保存
  ↓
【8】次の物を学習 or 認識モード
```

**認識モード:**
```
【1】[r]キーで認識モードに切り替え
  ↓
【2】カメラで物を見る
  ↓
【3】リアルタイムCross変換
  ↓
【4】データベースと照合
  ↓
【5】「りんご: 89%」と画面に表示
```

**データベース構造:**
```json
{
  "りんご": [
    {"cross_structure": {...}, "timestamp": "2024-..."},
    {"cross_structure": {...}, "timestamp": "2024-..."}
  ],
  "ペン": [
    {"cross_structure": {...}, "timestamp": "2024-..."}
  ]
}
```

**学習リファレンスの使い方:**
```bash
# 1. リファレンスを開く
open verantyx_cli/vision/CROSS_HOUSEHOLD_OBJECT_REFERENCE.md
open verantyx_cli/vision/CROSS_3D_VISUAL_GUIDE.md

# 2. カメラ学習起動
python -m verantyx_cli.vision.learn_from_camera

# 3. 物体をカメラに見せる（例: りんご）
[スペース] キャプチャ

# 4. リファレンスを確認:
#    - FRONT視点: 円形、中心密度高い
#    - UP軸: 0.45-0.55（対称）
#    - FRONT軸: 0.60-0.80（赤色）

# 5. ラベル入力
これは何ですか？ > りんご

# 6. JCross変換例で検証
python -m verantyx_cli.engine.run_jcross_interpreter \
  verantyx_cli/vision/cross_transformation_examples.jcross
```

### 8. プロセッサ群
- `dynamic_jcross_processors.py`: 動的JCross用プロセッサ（17個）
- `multi_layer_processors.py`: 多層Cross用プロセッサ（25個）
- `physics_processors.py`: 物理シミュレーション用プロセッサ（25個）
- `adaptive_processors.py`: 適応的解析用プロセッサ（20個）

## 使い方

### 形状認識（単一画像）
```bash
python -m verantyx_cli.vision.run_shape_recognition image.png
```

### 動的JCross解析（基本版）
```bash
python -m verantyx_cli.vision.run_dynamic_video_analysis video.mp4
```

### 動的JCross解析（フル実装版）★推奨
```bash
python -m verantyx_cli.vision.run_dynamic_full video.mp4 --save-report report.json
```

### 多層Crossテーマ学習（★NEW）
```bash
# 自動学習（sky, flower, humanを学習）
python -m verantyx_cli.vision.run_theme_learning

# 特定のテーマのみ学習
python -m verantyx_cli.vision.run_theme_learning --theme sky

# カスタムディレクトリから学習
python -m verantyx_cli.vision.run_theme_learning --directory ~/Photos --max-samples 10
```

### 多層Cross変換と認識
```python
from verantyx_cli.vision.multi_layer_cross import convert_image_to_multi_layer_cross
from verantyx_cli.vision.theme_memory_bank import ThemeMemoryBank

# 画像を多層Cross構造に変換（26万点）
cross_structure = convert_image_to_multi_layer_cross(
    image_path=Path("photo.jpg"),
    quality="ultra_high"
)

# テーマを認識
bank = ThemeMemoryBank(memory_path=Path("~/.verantyx/theme_memory.json"))
results = bank.recognize_theme(cross_structure, top_k=3)

# 結果: [{"theme": "sky", "score": 0.89, "confidence": 89.0}, ...]
```

### 世界真理学習（★NEW）
```bash
# 全ての基本真理を学習
python -m verantyx_cli.vision.run_truth_learning

# 特定の真理のみ学習
python -m verantyx_cli.vision.run_truth_learning --truth falling
```

### 物理シミュレーションと真理認識
```python
from verantyx_cli.vision.cross_physics_simulator import create_falling_ball_simulation
from verantyx_cli.vision.world_truth_memory import WorldTruthMemoryBank

# 落下シミュレーションを実行
timeline = create_falling_ball_simulation(
    duration=2.0,
    initial_height=1.0,
    gravity=9.8
)

# 真理として学習
bank = WorldTruthMemoryBank(memory_path=Path("~/.verantyx/world_truth_memory.json"))
bank.learn_truth("falling", timeline)

# 動画から真理を認識
video_timeline = convert_video_to_cross_timeline(video_path)
recognized = bank.recognize_truth(video_timeline, top_k=3)

# 結果: [{"truth": "falling", "score": 0.92, "confidence": 92.0}, ...]
```

### 適応的動画解析（★NEW）
```bash
# 状態遷移を検出して解像度を自動調整
python -m verantyx_cli.vision.run_adaptive_analysis video.mp4

# レポート保存
python -m verantyx_cli.vision.run_adaptive_analysis video.mp4 --save-report report.json

# 最大フレーム数指定
python -m verantyx_cli.vision.run_adaptive_analysis video.mp4 --max-frames 200
```

### カメラ学習（★NEW）
```bash
# カメラ学習を起動
python -m verantyx_cli.vision.learn_from_camera

# カスタムデータベースパス指定
python -m verantyx_cli.vision.learn_from_camera --db-path ~/my_objects.json

# 別のカメラを使用
python -m verantyx_cli.vision.learn_from_camera --camera 1

# 操作:
# [スペース] キャプチャ＆学習
# [r] 認識モード切り替え
# [l] 学習済みオブジェクト一覧
# [q] 終了
```

### 適応的解像度制御
```python
from verantyx_cli.vision.adaptive_resolution_controller import AdaptiveResolutionController

# コントローラを初期化
controller = AdaptiveResolutionController(initial_level="low")

# フレーム間の遷移を検出
transition_info = controller.detect_transition(prev_frame, curr_frame)

# 解像度を更新
new_level = controller.update(transition_info, frame_number)

# 結果:
# 通常時: "low" (50,000点)
# 遷移時: "ultra" (1,000,000点) - 20倍の解像度！
```

### カメラ学習と認識
```python
from verantyx_cli.vision.object_cross_database import ObjectCrossDatabase
from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter
from pathlib import Path

# データベースとコンバータを初期化
db = ObjectCrossDatabase()
converter = MultiLayerCrossConverter(quality="high")

# 画像をCross構造に変換
cross_structure = converter.convert(Path("apple.jpg"))

# データベースに追加
db.add_object("りんご", cross_structure)

# 認識
test_cross = converter.convert(Path("test.jpg"))
results = db.recognize(test_cross, top_k=3, min_confidence=0.5)

# 結果: [{"object": "りんご", "score": 0.89, "confidence": 89.0}, ...]
```

## ARC-AGI2資産の活用

- **グリッド表現**: 32x32グリッド
- **10色パレット**: ARC-AGI2の標準10色
- **パターン変換**: 入力 → 変換規則 → 出力
- **人間の脳のアプローチ**: 差分記憶

## アーキテクチャ

```
動画 (video.mp4)
  ↓
【1】30fpsでフレーム分解（OpenCV）
  ↓
【2】各フレーム → ARC-AGI2グリッド (32x32, 10色)
  ↓
【3】グリッド → Cross構造
  ↓
【4】フレーム間差分検出
  ↓
【5】差分 → JCrossコード動的変更
  ↓
【6】変更履歴 → Cross層マッピング
  ↓
【7】JCrossコード変容観察
  ↓
【8】詳細レポート生成
```

**重要**: ステップ2以降は全て`.jcross`で実装。Pythonは入出力のみ。

## 設計ドキュメント

- `CROSS_SHAPE_MEMORY_DESIGN.md`: 形状認識の詳細設計
- `DYNAMIC_JCROSS_VIDEO_ANALYSIS.md`: 動的JCross解析の完全設計
- `MULTI_LAYER_CROSS_DESIGN.md`: 多層Cross構造の完全設計
- `CROSS_WORLD_TRUTH_DESIGN.md`: 世界の真理システム完全設計
- `ADAPTIVE_RESOLUTION_DESIGN.md`: 適応的解像度システム完全設計
- `POINT_BASED_RECOGNITION_DESIGN.md`: 点ベース認識システム設計
- `CAMERA_LEARNING_DESIGN.md`: カメラ学習システム設計

## 学習リファレンス資料（★NEW）

- `CROSS_HOUSEHOLD_OBJECT_REFERENCE.md`: 20,000+家庭内物体のCross構造リファレンス
  - 7カテゴリ、20,000+物体の詳細なCross構造データ
  - 6軸方向の期待値
  - JCrossコードでの動的変化パターン

- `CROSS_3D_VISUAL_GUIDE.md`: Cross構造の3D視覚表現ガイド
  - 6視点（FRONT/BACK/UP/DOWN/RIGHT/LEFT）からの点配置図
  - 20,000点がどう見えるかの視覚的説明
  - 回転・移動・変形の視覚的パターン

- `cross_transformation_examples.jcross`: JCross変換実例集（実行可能）
  - りんご、バナナ、マグカップ、本、PC、ペン、ペットボトルの実例
  - 30以上の変換パターン
  - カメラ学習時の検証用コード

## 依存関係

```bash
pip install opencv-python numpy pillow
```

## Native Chatとの統合

Native Chatモードでは自動的に使用されます：

```bash
verantyx chat
🗣️  You: ~/video.mp4 を分析して auto
```

- 画像: Claude Code native（デフォルト）or Verantyx Vision（--use-vision）
- 動画: Verantyx Vision（Cross形状認識付き、自動）
