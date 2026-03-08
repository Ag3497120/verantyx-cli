# Verantyx - 画像認識ガイド

## 概要

Verantyxでは、2つの画像認識方法を提供しています：

1. **Claude Code Native（デフォルト）** - Claude Codeの高精度な画像認識
2. **Verantyx Vision（オプション）** - Cross Simulationによる独自の画像解析

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

## 対応画像パス形式

### 絶対パス

```
/Users/username/Desktop/image.png
~/Desktop/image.png
```

### 相対パス

```
./image.png
../images/photo.jpg
```

### スペースを含むパス

```
/Users/username/My\ Documents/image.png
~/Desktop/スクリーンショット\ 2026-03-04\ 10.49.12.png
```

## 複数画像の同時処理

複数の画像パスを含めることも可能です：

```
🗣️  You: ~/image1.png と ~/image2.png を比較して auto
```

それぞれの画像が個別にVision処理されます。

## 技術詳細

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

Verantyxの画像認識：

✅ **デフォルト**: Claude Codeのネイティブ機能（高精度・高速）
✅ **オプション**: Verantyx Vision（Cross Simulation）
✅ **柔軟**: 用途に応じて選択可能

```bash
# 通常はこれだけ
verantyx chat
```

画像パスを含めてプロンプトを送信すれば、Claudeが認識します 🖼️✨
