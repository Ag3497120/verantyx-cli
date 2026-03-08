# 🖼️ 画像変換機能ガイド - Verantyx-CLI

Verantyx-CLIのチャット画面から、画像を自動的にCross構造に変換できます。

## 📦 インストール

画像変換機能を使うには、画像処理ライブラリが必要です：

```bash
pip install pillow numpy
```

## 🎯 使い方

### 方法1: `/image`コマンド（推奨）

チャット画面で `/image` コマンドを使用します：

```
> /image /Users/name/Desktop/photo.jpg

🖼️  Image Conversion:
✅ Image converted to Cross structure!
📸 Image: photo.jpg
📊 Points: 5,000
🗺️  Regions: 5
💾 Saved: .verantyx/vision/photo.cross.json

**Description:**
Image: photo.jpg
Detected 5 regions:
  1. edge in top_left (intensity: 0.65, 1200 points)
  2. bright_region in top_right (intensity: 0.85, 900 points)
  ...

**Spatial relationships:**
  • edge is right_of bright_region
  • dark_region is below edge
```

### 方法2: 画像パスを直接ペースト（ドラッグ&ドロップ風）

ファイルマネージャーから画像ファイルのパスをコピーして、チャットにペーストするだけ：

```
> /Users/name/Documents/screenshot.png

🖼️  Image Conversion:
✅ Image converted to Cross structure!
...
```

### 方法3: 品質を指定

`/image` コマンドの後に品質レベルを指定できます：

```
> /image ~/photos/important.jpg high

> /image /path/to/image.png maximum
```

## 🎨 品質レベル

| レベル | ポイント数 | 用途 | 処理時間 |
|--------|-----------|------|---------|
| `low` | 500 | 高速プレビュー | 最速 |
| `medium` | 1,000 | 標準（デフォルト） | 速い |
| `high` | 5,000 | 高品質 | 普通 |
| `ultra` | 10,000 | 非常に高品質 | やや遅い |
| `maximum` | 50,000 | 最高品質 | 遅い |

**例：**
```bash
# 高速プレビュー
> /image image.jpg low

# 標準品質（デフォルト）
> /image image.jpg
> /image image.jpg medium

# 高品質
> /image image.jpg high

# 最高品質
> /image image.jpg maximum
```

## 🧠 Cross構造とは？

画像は以下の6軸Cross構造に変換されます：

### 6軸マッピング

- **RIGHT/LEFT軸**: 水平位置（画像のX座標）
- **UP/DOWN軸**: 垂直位置（画像のY座標）
- **FRONT/BACK軸**: 明度（明るい = 前、暗い = 後ろ）

### 領域検出

画像は5つの領域に自動分割されます：

1. **center** - 中央領域
2. **top_left** - 左上
3. **top_right** - 右上
4. **bottom_left** - 左下
5. **bottom_right** - 右下

### パターン認識

各領域のパターンを自動検出：

- **edge** - エッジ（境界線）が多い
- **bright_region** - 明るい領域
- **dark_region** - 暗い領域
- **mid_region** - 中間的な明度

## 📊 生成されるファイル

変換された画像は `.verantyx/vision/` に保存されます：

```
.verantyx/
└── vision/
    ├── photo.cross.json          # 変換されたCross構造
    ├── screenshot.cross.json
    └── image.cross.json
```

### Cross構造の例

```json
{
  "type": "vision_cross",
  "source": "/Users/name/photo.jpg",
  "timestamp": "2026-03-08T14:00:00",
  "metadata": {
    "original_size": {"width": 1920, "height": 1080},
    "num_points": 5000,
    "num_regions": 5
  },
  "axes": {
    "RIGHT_LEFT": {
      "axis": "RIGHT_LEFT",
      "mean": 0.05,
      "std": 0.65,
      "distribution": "uniform"
    },
    "UP_DOWN": {...},
    "FRONT_BACK": {...}
  },
  "regions": [
    {
      "center": {"x": -0.5, "y": 0.5, "z": 0.3, "intensity": 0.65},
      "pattern": "edge",
      "relations": ["top_left"],
      "num_points": 1200
    }
  ],
  "spatial_relations": [
    {
      "from": "edge",
      "to": "bright_region",
      "relation": "right_of",
      "distance": 0.85
    }
  ]
}
```

## 💬 Claudeとの統合

変換されたCross構造は自動的にClaudeに送信されます。Claudeは：

1. **画像の内容を理解**できます（Cross構造を通じて）
2. **領域と関係を分析**できます
3. **空間的な質問に答える**ことができます

**例：**
```
> /image diagram.png high

> この図の左上には何がありますか？

🤖 Claude: Cross構造によると、左上領域（top_left）には「edge」パターンが
検出されています。これは明度0.65の境界線が多い領域で、1200ポイントで
構成されています。この領域は右側の明るい領域（bright_region）と隣接
しています。
```

## 🎯 実用例

### 例1: スクリーンショットの分析

```
> /image ~/Desktop/screenshot.png medium

> このスクリーンショットの構造を説明して

🤖 Claude: このスクリーンショットは5つの主要領域で構成されています...
```

### 例2: 写真の説明

```
> /image ~/photos/vacation.jpg high

> この写真の明るい部分はどこですか？

🤖 Claude: Cross構造の分析によると、最も明るい領域（intensity: 0.85）は
右上（top_right）に位置しています...
```

### 例3: 図表の理解

```
> /image diagram.png ultra

> この図の要素の位置関係を教えて

🤖 Claude: 空間関係の分析結果：
- エッジパターンが明るい領域の左側にあります
- 暗い領域は中央より下部に位置しています
...
```

## 🔧 トラブルシューティング

### エラー: "Vision support not available"

```bash
# 解決策: 画像処理ライブラリをインストール
pip install pillow numpy
```

### エラー: "Image not found"

- ファイルパスが正しいか確認
- 絶対パス（`/Users/...`）を使用してください
- `~` は自動的に展開されます

### エラー: "Unsupported image format"

サポートされている形式：
- ✅ JPG/JPEG
- ✅ PNG
- ✅ GIF
- ✅ BMP
- ✅ WebP
- ✅ TIFF

### 変換が遅い

- 品質レベルを下げる（`high` → `medium` → `low`）
- 大きな画像は自動的にダウンサンプリングされますが、`low`や`medium`を使うとより高速

## 📚 ヘルプコマンド

チャット内でヘルプを表示：

```
> /help image

🖼️  Image Support

Methods to convert images:

1. Command: /image <path> [quality]
   Example: /image ~/photos/sunset.jpg high

2. Drag & Drop (paste path): Just paste the image file path
   Example: /Users/name/Desktop/image.png

Quality levels: low, medium (default), high, ultra, maximum

Supported formats: JPG, PNG, GIF, BMP, WebP, TIFF
...
```

## 🌟 高度な使い方

### 複数画像の比較

```
> /image photo1.jpg medium

> /image photo2.jpg medium

> この2つの画像の違いを説明して
```

### 品質による違い

```
> /image test.jpg low
> /image test.jpg high

> lowとhighで検出結果はどう変わりましたか？
```

## 💡 ベストプラクティス

1. **通常使用**: `medium`で十分
2. **詳細分析**: `high`または`ultra`を使用
3. **プレビュー**: `low`で高速確認
4. **重要な画像**: `maximum`で最高品質

---

**Made with 🧠 Cross-Native Architecture**
