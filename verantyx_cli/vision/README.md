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

### 4. プロセッサ群
- `dynamic_jcross_processors.py`: 動的JCross用プロセッサ（17個）

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
