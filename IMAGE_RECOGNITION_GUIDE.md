# Verantyx - 画像・動画認識ガイド

## 概要

Verantyxでは、画像と動画の認識方法を提供しています：

### 画像認識
1. **Claude Code Native（デフォルト）** - Claude Codeの高精度な画像認識
2. **Verantyx Vision（オプション）** - Cross Simulationによる独自の画像解析

### 動画認識
- **Verantyx Vision（自動）** - Claude Codeは動画非対応のため、常にCross Simulationで処理（最高品質）
- **Cross形状認識（JCross）** - 点配置パターンから形状を認識し、動画内の「何が描画されているか」を理解
- **動的JCross解析（実験的）** - フレーム間変化をJCrossコードの動的変更として表現・観察

## Claude Code Native（推奨）

### デフォルトの動作

Native Chatモードでは、Claude Codeの画像認識機能を使用します：

```bash
verantyx chat
```

**使い方:**
```
🗣️  You: /Users/username/Desktop/screenshot.png について教えて
```

Claude Codeが直接画像を読み取って応答します：
```
🤖 Verantyx Agent: 💭 Thinking.....

⏺ この画像は、GitHubのリポジトリページを表示しています...
```

**メリット:**
- ✅ 高精度（Anthropic API使用）
- ✅ 処理が速い
- ✅ ネイティブサポート
- ✅ 追加設定不要

## Verantyx Vision（オプション）

Cross Simulationによる独自の画像解析を使いたい場合：

```bash
verantyx chat --use-vision
```

### 何が起きるか

1. **画像パス自動検出**
   - プロンプトから画像パスを自動検出
   - 対応形式: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.tiff`

2. **Verantyx Vision処理**
   ```
   🔍 画像パスを検出中...
      🔍 検出: screenshot.png

   🖼️  1個の画像を検出しました

   🖼️  画像を解析中: screenshot.png
      Verantyx Vision (Cross Simulation) で処理...
      ✅ 解析完了
   ```

3. **Cross構造に変換**
   - 画像をCross 6軸構造に変換
   - 視覚情報を立体的に表現

4. **Claudeに送信**
   - 画像の詳細な説明をClaudeに提供
   - Claudeが画像の内容を理解して応答

### いつ使うか

- Cross構造で画像を記録したい場合
- 独自の視覚処理パイプラインが必要な場合
- 他のLLM（Gemini、Ollama等）と統合する場合

## 動画認識（Verantyx Vision）

### 自動処理

Claude Codeは動画に対応していないため、動画は**常にVerantyx Vision（最高品質）で自動処理**されます：

```bash
verantyx chat
```

**使い方:**
```
🗣️  You: /Users/username/Desktop/demo.mp4 について教えて auto
```

動画が自動的に検出され、Verantyx Visionで処理されます：
```
🔍 メディアファイルを検出中...
   🔍 検出（動画）: demo.mp4

🎥 1個の動画を検出しました
   ℹ️  動画はVerantyx Vision（最高品質）で処理されます

🎥 動画を解析中: demo.mp4
   品質: MAXIMUM（最高品質）
   フレームサンプリング: 最大10フレーム
   ✅ 解析完了

📤 Sending to Claude...
🤖 Verantyx Agent: 💭 Thinking.....

⏺ この動画は、...
```

### 処理内容

1. **フレーム抽出**
   - OpenCVで動画をフレームに分割
   - 均等サンプリング（デフォルト10フレーム）
   - 動画の長さに応じて自動調整

2. **各フレームをCross構造に変換**
   - 各フレームを最高品質（maximum）で処理
   - 50,000ポイントのポイントクラウド
   - Cross 6軸構造化

3. **Cross形状認識（JCross）**
   - 画像のピクセル → 3D空間の点群にマッピング
   - 各点の位置をCross 6軸（FRONT/BACK/UP/DOWN/RIGHT/LEFT）で計測
   - 点の分布パターンを抽出
   - 断片記憶（形状パターンの記憶層）と照合
   - **点配置パターンから形状を認識**（矩形、円、線等）

4. **TIME軸を追加**
   - 各フレームにタイムスタンプを付与
   - 時間軸を含む4次元（3D空間+時間）の視覚情報として表現

5. **LLMコンテキスト生成**
   - フレームごとの詳細な説明を生成
   - **認識された形状を含む**
   - Claudeが動画の**実際の内容**を理解して応答

### 対応動画形式

- `.mp4` - MP4（推奨）
- `.mov` - QuickTime
- `.avi` - AVI
- `.mkv` - Matroska
- `.webm` - WebM
- `.flv` - Flash Video

### メリット

- ✅ 最高品質（maximum quality）で処理
- ✅ 自動検出・自動処理
- ✅ フレームごとの詳細な分析
- ✅ Cross構造で時間情報も記録
- ✅ **JCross形状認識で「何が描画されているか」を理解**
- ✅ 点配置パターンから形状を認識（OCR等の外部ツール不要）
- ✅ 断片記憶に基づく認識（新しい形状パターンを学習可能）

## 自動応答機能

### トリガーワード

プロンプトに以下のキーワードが含まれている場合、Claudeの選択肢（Yes/No等）に自動で"Yes"を選択します：

- **英語**: `auto`, `yes`, `allow`
- **日本語**: `自動`, `許可`, `はい`

### 使用例

```
🗣️  You: /Users/username/Desktop/screenshot.png について教えて auto

# または

🗣️  You: この画像を自動で解析して ~/Desktop/photo.jpg
```

Claudeが「Do you want to proceed?」と聞いてきたら、自動的に"Yes"を選択します。

### トリガーなしの場合

トリガーワードがない場合は、通常通り手動で選択できます（ただし、PTY経由のため選択は困難）。

## 対応メディアパス形式

### 絶対パス

```
/Users/username/Desktop/image.png
/Users/username/Videos/demo.mp4
~/Desktop/image.png
~/Videos/demo.mp4
```

### 相対パス

```
./image.png
./video.mp4
../images/photo.jpg
../videos/demo.mov
```

### スペースを含むパス

```
/Users/username/My\ Documents/image.png
/Users/username/My\ Videos/demo\ video.mp4
~/Desktop/スクリーンショット\ 2026-03-04\ 10.49.12.png
```

## 複数メディアの同時処理

複数の画像・動画パスを含めることも可能です：

```
🗣️  You: ~/image1.png と ~/image2.png を比較して auto
```

それぞれの画像が個別に処理されます。

```
🗣️  You: ~/video1.mp4 と ~/video2.mp4 の違いを説明して auto
```

それぞれの動画が個別にVision処理されます（最高品質）。

```
🗣️  You: ~/photo.png と ~/demo.mp4 を分析して auto
```

画像と動画を混在させることも可能です。

## 技術詳細

### Cross形状認識（JCross実装）

動画・画像の**実際の内容**を理解するため、Cross構造の点配置パターンから形状を認識します：

#### 1. 画像 → Cross点群

```
各ピクセル → 3D空間の点

例: 100x100の画像
→ 最大10,000個の点（輝度が閾値以上のピクセルのみ）

各点の情報:
- position: [x, y, z]  # 正規化座標 (0-1)
- color: [R, G, B]
- cross: {FRONT, BACK, UP, DOWN, RIGHT, LEFT}  # 6軸計測値
```

#### 2. Cross 6軸計測

各点の位置を6つの軸で数値化：

```python
cross_metrics = {
    "FRONT": z + 0.5,      # Z軸前方投影
    "BACK": 0.5 - z,       # Z軸後方投影
    "UP": y,               # Y軸上方投影
    "DOWN": 1 - y,         # Y軸下方投影
    "RIGHT": x,            # X軸右方投影
    "LEFT": 1 - x          # X軸左方投影
}
```

#### 3. Cross分布パターン抽出

点群から各軸の分布パターンを抽出：

```
UP軸分布:
  - mean: 0.7 (上部に点が集中)
  - std: 0.15 (concentrated)

RIGHT軸分布:
  - mean: 0.5 (中央)
  - std: 0.35 (distributed - 横に広がり)

対称性:
  - left_right: True
  - up_down: False
```

#### 4. 断片記憶との照合

抽出されたパターンを断片記憶（形状パターンの記憶層）と照合：

```
断片記憶の例:

"triangle" パターン:
  - UP軸: concentrated (上部に点)
  - DOWN軸: distributed (下部に底辺)
  - 対称性: left_right=True

"rectangle" パターン:
  - 対称性: left_right=True, up_down=True
  - UP軸: concentrated
  - RIGHT軸: concentrated
```

#### 5. 形状認識結果

最も類似度が高いパターンを返す：

```json
{
  "shape": "triangle",
  "confidence": 0.87,
  "point_count": 152,
  "cross_pattern": { ... }
}
```

#### JCross実装

形状認識は`.jcross`言語で実装されています：

- `verantyx_cli/vision/shape_recognition.jcross` - メインプログラム
- `verantyx_cli/vision/vision_processors.py` - Pythonプロセッサ
- `verantyx_cli/engine/jcross_operation_commands.py` - Cross操作コマンド

**特徴:**
- ✅ OCR等の外部ツール不要
- ✅ Cross構造の点配置パターンそのものから認識
- ✅ 新しい形状パターンを学習可能
- ✅ 色もCross構造でマッピング

### Verantyx Vision (Cross Simulation)

画像認識は以下のプロセスで行われます：

1. **ピクセル → Point Cloud**
   - 画像をポイントクラウドに変換
   - 各ピクセルが3D空間の点として表現

2. **Cross 6軸構造化**
   - UP/DOWN: 色情報の階層
   - FRONT/BACK: 空間的な奥行き
   - RIGHT/LEFT: 特徴の関連性

3. **LLMコンテキスト生成**
   - Cross構造からLLMが理解できるテキストを生成
   - 視覚情報を言語化

### プロンプト拡張

元のプロンプト：
```
/Users/username/screenshot.png について教えて
```

拡張後（Claudeに送信されるもの）：
```
[Verantyx Vision Analysis of screenshot.png]
<詳細な画像の説明>
- 色分布: ...
- 主要な特徴: ...
- 空間構造: ...
</詳細な画像の説明>
について教えて
```

## トラブルシューティング

### 画像が検出されない

- パスが正しいか確認
- スペースがある場合は`\`でエスケープ
- 絶対パスを使用してみる

### Vision処理が失敗する

依存関係を確認：
```bash
pip install pillow numpy
```

### 動画処理が失敗する

OpenCVが必要です：
```bash
pip install opencv-python
```

動画が開けない場合：
- ファイルが破損していないか確認
- 対応形式か確認（`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.flv`）
- ffmpegがインストールされているか確認（一部の形式で必要）

### 自動応答が動作しない

- トリガーワード（`auto`, `yes`, `allow`, `自動`, `許可`, `はい`）を含める
- ログを確認: `.verantyx/verantyx.log`

## 例

### スクリーンショット分析

```
🗣️  You: ~/Desktop/スクリーンショット\ 2026-03-04\ 10.49.12.png について教えて auto

🖼️  1個の画像を検出しました
🖼️  画像を解析中: スクリーンショット 2026-03-04 10.49.12.png
   Verantyx Vision (Cross Simulation) で処理...
   ✅ 解析完了

📤 Sending to Claude...
🤖 Verantyx Agent: 💭 Thinking.....

⏺ このスクリーンショットは、ターミナルウィンドウを表示しています...
```

### 複数画像比較

```
🗣️  You: ~/before.png と ~/after.png の違いを説明して yes

🖼️  2個の画像を検出しました
🖼️  画像を解析中: before.png
   ✅ 解析完了
🖼️  画像を解析中: after.png
   ✅ 解析完了

🤖 Verantyx Agent: 2つの画像を比較すると...
```

### 動画分析

```
🗣️  You: ~/Desktop/demo.mp4 の内容を要約して auto

🎥 1個の動画を検出しました
   ℹ️  動画はVerantyx Vision（最高品質）で処理されます

🎥 動画を解析中: demo.mp4
   品質: MAXIMUM（最高品質）
   フレームサンプリング: 最大10フレーム
   Video info: 300 frames, 30.00 fps, 1920x1080, 10.00s
   Processed frame 0/300 (sample 1/10)
   Processed frame 30/300 (sample 2/10)
   ...
   ✅ 解析完了

📤 Sending to Claude...
🤖 Verantyx Agent: 💭 Thinking.....

⏺ この動画は10秒間の映像で、...
   - 0.00秒: ...
   - 1.00秒: ...
   - 2.00秒: ...
   ...
```

### 画像と動画の混在

```
🗣️  You: ~/photo.png のスクリーンショットと ~/demo.mp4 の動画を比較して auto

🔍 メディアファイルを検出中...
   🔍 検出（画像）: photo.png
   🔍 検出（動画）: demo.mp4

🎥 1個の動画を検出しました
   ℹ️  動画はVerantyx Vision（最高品質）で処理されます

🖼️  1個の画像を検出しました
   ℹ️  画像はClaude Code nativeで処理されます

🤖 Verantyx Agent: スクリーンショットと動画を比較すると...
```

## スタンドアロンでの使用

Native Chatを使わない場合、Verantyx Visionをスタンドアロンで使用できます：

### LLMコンテキスト生成
```bash
verantyx vision image.png --llm-context
```

画像の詳細な説明を生成します。

### Cross構造に保存
```bash
verantyx vision image.png --output image.cross.json
```

画像をCross 6軸構造に変換して保存します。

### 品質設定
```bash
verantyx vision image.png --quality high
verantyx vision image.png --max-points 10000
```

## 使い分け

### Claude Code Native（デフォルト）
```bash
verantyx chat
```
- ✅ 高精度・高速
- ✅ ネイティブサポート
- ✅ ほとんどのユースケース

### Verantyx Vision（--use-vision）
```bash
verantyx chat --use-vision
```
- ✅ Cross構造で記録
- ✅ 独自の視覚処理
- ✅ 他のLLMとの統合

### スタンドアロン
```bash
verantyx vision image.png
```
- ✅ Claude Code不要
- ✅ Cross構造の研究
- ✅ バッチ処理

## まとめ

Verantyxのメディア認識：

### 画像認識
✅ **デフォルト**: Claude Codeのネイティブ機能（高精度・高速）
✅ **オプション**: Verantyx Vision（Cross Simulation）で `--use-vision`
✅ **柔軟**: 用途に応じて選択可能

### 動画認識
✅ **自動**: Claude Code非対応のため、Verantyx Vision（最高品質）で自動処理
✅ **高品質**: 常にmaximum品質（50,000ポイント）
✅ **時間軸**: Cross構造のTIME軸で時間情報も記録

```bash
# 通常はこれだけ
verantyx chat
```

画像・動画パスを含めてプロンプトを送信すれば、自動的に認識・処理されます 🖼️🎥✨
