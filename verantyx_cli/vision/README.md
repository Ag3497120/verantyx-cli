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

### 5. プロセッサ群
- `dynamic_jcross_processors.py`: 動的JCross用プロセッサ（17個）
- `multi_layer_processors.py`: 多層Cross用プロセッサ（25個）

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
- `MULTI_LAYER_CROSS_DESIGN.md`: 多層Cross構造の完全設計（★NEW）

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
