# 🖼️ 画像変換機能 - クイックテストガイド

## ✅ 動作確認

画像変換機能は正常に動作しています！

### テスト結果

```bash
python3 test_image_handler.py
```

**結果:**
- ✅ DNG形式の検出: 成功
- ✅ パスからの自動検出: 成功
- ✅ `/image`コマンド: 成功
- ✅ 品質指定: 成功
- ✅ Cross構造生成: 成功 (5領域、1,000-5,000ポイント)

## 🚀 使い方

### 1. Verantyx-CLIを起動

```bash
cd /Users/motonishikoudai/verantyx_v6/verantyx-cli
verantyx chat
```

### 2. 画像を変換

チャット画面で以下のいずれかを入力：

#### 方法A: `/image`コマンド（推奨）
```
> /image /Users/motonishikoudai/Downloads/IMG_9278.DNG high
```

#### 方法B: パスを直接ペースト
```
> /Users/motonishikoudai/Downloads/IMG_9278.DNG
```

### 3. 変換結果を確認

```bash
# 生成されたCross構造を確認
cat ~/.verantyx/vision/IMG_9278.cross.json | python3 -m json.tool | head -50

# 説明を確認
cat ~/.verantyx/vision/IMG_9278.cross.json | python3 -c "import sys, json; print(json.load(sys.stdin)['description'])"
```

## 📊 期待される出力

### 変換成功時

```
🔄 Converting image: IMG_9278.DNG (quality: high)...

✅ Image converted to Cross structure!
📸 Image: IMG_9278.DNG
📊 Points: 5,000
🗺️  Regions: 5
💾 Saved: ~/.verantyx/vision/IMG_9278.cross.json

**Description:**
Image: IMG_9278.DNG
Detected 5 regions:
  - mid_region in top_left (intensity: 0.44, 348 points)
  - mid_region in top_right (intensity: 0.39, 317 points)
  - mid_region in bottom_left (intensity: 0.66, 2646 points)
  - mid_region in bottom_right (intensity: 0.53, 1549 points)
  - dark_region in center (intensity: 0.29, 140 points)

**Regions detected:**
1. **mid_region** - Position: top_left, Intensity: 0.44, Points: 348
2. **mid_region** - Position: top_right, Intensity: 0.39, Points: 317
3. **mid_region** - Position: bottom_left, Intensity: 0.66, Points: 2646
4. **mid_region** - Position: bottom_right, Intensity: 0.53, Points: 1549
5. **dark_region** - Position: center, Intensity: 0.29, Points: 140

**Spatial relationships:**
  • mid_region is right_of mid_region
  • mid_region is below mid_region
  ...
```

## 🎨 品質レベル

| レベル | ポイント数 | テスト結果 |
|--------|-----------|-----------|
| `low` | 500 | ✅ 動作確認 |
| `medium` | 1,000 | ✅ 動作確認（デフォルト） |
| `high` | 5,000 | ✅ 動作確認 |
| `ultra` | 10,000 | - |
| `maximum` | 50,000 | - |

## 📂 生成されるファイル

```
~/.verantyx/vision/
└── IMG_9278.cross.json
```

## 🔧 トラブルシューティング

### チャットUIで変換結果が表示されない場合

1. **ログを確認**:
   ```bash
   tail -f ~/.verantyx/debug.log
   ```

2. **手動でテスト**:
   ```bash
   python3 test_image_handler.py
   ```

3. **ライブラリを確認**:
   ```bash
   pip list | grep -i pillow
   pip list | grep -i numpy
   ```

### エラー: "Vision support not available"

```bash
pip install pillow numpy
```

### パスが認識されない場合

- 絶対パスを使用してください: `/Users/name/...`
- `~` は自動展開されます
- スペースを含むパスは引用符で囲む必要があります（現在は未対応）

## 🎯 次のステップ

1. **Claudeに質問**:
   ```
   > この写真の明るい部分はどこですか？
   ```

2. **複数画像を比較**:
   ```
   > /image photo1.jpg
   > /image photo2.jpg
   > 2つの違いを説明して
   ```

3. **品質を変えて比較**:
   ```
   > /image test.jpg low
   > /image test.jpg high
   > 検出結果の違いは？
   ```

---

**✅ 実装完了！GitHubにプッシュ済み**

リポジトリ: https://github.com/Ag3497120/verantyx-cli
