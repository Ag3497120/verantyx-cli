# 🖼️ 画像変換機能 - 使い方のコツ

## ✅ 正しい使用方法

### パターン1: 画像を変換してから質問（推奨）

**手順:**
1. まず画像を変換
2. 次のメッセージで質問

```bash
# メッセージ1: 画像を変換
> /Users/motonishikoudai/Downloads/IMG_9278.DNG high

🔄 Converting image: IMG_9278.DNG (quality: high)...
✅ Image converted!
📊 Points: 5,000
...

# メッセージ2: 質問を入力（Enterを押して新しいメッセージ）
> この写真の内容を教えて

🤖 Claude: Cross構造の分析によると、この画像は5つの領域で構成されています...
```

### パターン2: 画像パスと質問を同じ行に

```bash
# 1行で画像パス + 質問
> /Users/motonishikoudai/Downloads/IMG_9278.DNG high この写真の内容を教えて

🔄 Converting image: IMG_9278.DNG (quality: high)...
✅ Image converted!
...

**Your message:** この写真の内容を教えて

🤖 Claude: Cross構造の分析によると...
```

### パターン3: `/image`コマンド

```bash
# /imageコマンドで変換
> /image /Users/motonishikoudai/Downloads/IMG_9278.DNG high

✅ Image converted!
...

# 次のメッセージで質問
> この写真の明るい部分はどこですか？

🤖 Claude: Cross構造によると、最も明るい領域（intensity: 0.66）は...
```

## 🎯 使い方の例

### 例1: 写真の分析

```bash
# ステップ1: 画像変換
> ~/Desktop/photo.jpg high
✅ Converted!

# ステップ2: 質問
> この写真の主な被写体は何ですか？
🤖 Claude: ...

# ステップ3: 追加質問
> 明るい部分と暗い部分の割合は？
🤖 Claude: ...
```

### 例2: 複数画像の比較

```bash
# 画像1を変換
> ~/photos/before.jpg high
✅ Converted!

# 画像2を変換
> ~/photos/after.jpg high
✅ Converted!

# 比較を依頼
> この2つの画像の違いを説明して
🤖 Claude: before.jpgとafter.jpgのCross構造を比較すると...
```

### 例3: 品質による違いの確認

```bash
# 低品質で変換
> ~/test.jpg low
✅ Converted! Points: 500

# 高品質で変換
> ~/test.jpg high
✅ Converted! Points: 5,000

# 違いを確認
> 検出結果の違いは？
🤖 Claude: 高品質版では5,000ポイントで、より詳細な...
```

## ❌ よくある間違い

### 間違い1: 質問が届かない

```bash
# ❌ 間違い: Enterを押さずに質問を続けてタイプしている
> /Users/.../IMG_9278.DNG high
  （ここでEnterを押す）
> この写真の内容を教えて
  （ここでEnterを押す）
```

**解決策**: 各メッセージの後にEnterを押して送信する

### 間違い2: パスが認識されない

```bash
# ❌ 間違い: 相対パスやスペースを含むパス
> ./image.jpg
> ~/My Photos/photo.jpg  # スペースあり

# ✅ 正しい: 絶対パスまたは ~ 展開
> ~/Desktop/image.jpg
> /Users/name/Desktop/image.jpg
```

**解決策**: 絶対パスを使用する。スペースは現在未対応。

### 間違い3: 品質指定の位置

```bash
# ❌ 間違い: パスの前に品質
> high ~/image.jpg

# ✅ 正しい: パスの後に品質
> ~/image.jpg high
```

## 💡 プロのヒント

### ヒント1: エイリアスを使う

```bash
# ~/.zshrc または ~/.bashrc に追加
alias convert-img='verantyx chat'
```

### ヒント2: 複数画像を一括変換

```bash
# まとめて変換
> ~/photos/img1.jpg high
> ~/photos/img2.jpg high
> ~/photos/img3.jpg high

# 一括で質問
> これら3つの画像の共通点は？
```

### ヒント3: Cross構造を直接確認

```bash
# ターミナルで確認
cat ~/.verantyx/vision/IMG_9278.cross.json | jq '.description'

# 領域を確認
cat ~/.verantyx/vision/IMG_9278.cross.json | jq '.regions'
```

## 🔧 トラブルシューティング

### 問題: Claudeに質問が届かない

**原因**: 画像変換メッセージの直後に質問をタイプし、変換メッセージが表示される前にEnterを押している

**解決策**:
1. 画像変換が完了するまで待つ（"✅ Image converted!"が表示される）
2. 新しいメッセージとして質問を入力
3. Enterを押して送信

### 問題: "Waiting for Claude response..."が消えない

**原因**: Claudeへの接続に問題がある、またはClaudeが応答を生成中

**解決策**:
1. Escキーを押して待機をキャンセル
2. もう一度質問を送信
3. それでもダメならVerantyxを再起動

### 問題: 画像が変換されない

**原因**: ファイルパスが間違っている、またはサポートされていない形式

**確認事項**:
```bash
# ファイルが存在するか確認
ls -lh /Users/motonishikoudai/Downloads/IMG_9278.DNG

# サポート形式を確認
# JPG, PNG, GIF, BMP, WebP, TIFF, DNG, RAW, CR2, NEF, ARW, ORF
```

## 📊 品質レベルの使い分け

| 用途 | 推奨品質 | 理由 |
|------|---------|------|
| プレビュー・確認 | `low` | 高速で十分 |
| 通常の分析 | `medium` | バランスが良い |
| 詳細な分析 | `high` | より精密な検出 |
| 研究・アーカイブ | `ultra` または `maximum` | 最高品質 |

## 🎓 学習用チュートリアル

### チュートリアル1: 初めての画像変換

```bash
1. Verantyx起動
   $ verantyx chat

2. 画像変換（まずは medium で）
   > ~/Desktop/test.jpg

3. 結果を確認
   ✅ Image converted!
   📊 Points: 1,000
   🗺️  Regions: 5

4. Claudeに質問
   > この画像の明るい部分はどこですか？

5. Cross構造を直接確認
   $ cat ~/.verantyx/vision/test.cross.json | jq '.description'
```

### チュートリアル2: 品質の違いを体験

```bash
1. 同じ画像を異なる品質で変換
   > ~/test.jpg low
   > ~/test.jpg medium
   > ~/test.jpg high

2. 違いを質問
   > 3つの品質レベルで検出された領域数の違いは？

3. 結果を比較
   🤖 Claude: lowでは500ポイント、mediumでは1,000ポイント、
   highでは5,000ポイントで構成されています...
```

---

**🎯 基本ルール: 画像変換完了を待ってから質問する！**

これを守れば、スムーズに使えます。
