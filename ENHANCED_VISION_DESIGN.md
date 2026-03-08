# Enhanced Vision Design - ARC-AGI2統合によるCross視覚認識

## 概要

現在のCross Vision実装は空間的特徴（明暗、色分布）のみを捉えていますが、
動画・画像の**実際の内容**（テキスト、UI要素、オブジェクト）を分析できるように拡張します。

## 問題点

現在の`video_to_llm_context()`の出力：
```
この分析は空間的な特徴（明暗、構成）は捉えていますが、
実際に何が表示されているか（テキスト、UI要素など）を知りたい場合は、
元の動画ファイルまたは代表的なフレームを直接見る必要があります。
```

## 目標

1. **形状・輪郭の検出** - エッジ検出でオブジェクトの境界をCross構造に格納
2. **テキスト認識（OCR）** - 画面内のテキストを抽出して内容を理解
3. **オブジェクト検出** - 何が描画されているか（ボタン、ウィンドウ、アイコン等）
4. **ARC-AGI2風パターン表現** - グリッドベースの抽象化で視覚パターンを表現

## ARC-AGI2とは

ARC-AGI (Abstraction and Reasoning Corpus) は視覚的なパターン認識と推論のベンチマーク：

- **グリッド表現**: 画像を色付きグリッドとして抽象化
- **パターン抽出**: 形状、対称性、繰り返しパターンを認識
- **抽象的推論**: 視覚パターンから規則を学習

### Verantyxへの応用

画像・動画フレームを：
1. グリッド化（例: 32x32、64x64）
2. 色をカテゴリ化（10色程度に削減）
3. 形状パターンを検出
4. Cross構造のPATTERN軸に格納

## 拡張されたCross構造

### 現在の構造（6軸）

```json
{
  "axes": {
    "FRONT": { "points": [...], "features": "前方特徴" },
    "BACK": { "points": [...], "features": "後方特徴" },
    "UP": { "points": [...], "features": "上方特徴" },
    "DOWN": { "points": [...], "features": "下方特徴" },
    "RIGHT": { "points": [...], "features": "右方特徴" },
    "LEFT": { "points": [...], "features": "左方特徴" }
  }
}
```

### 拡張後の構造（10軸）

```json
{
  "version": "2.0",
  "type": "image_enhanced",
  "axes": {
    "FRONT": { "points": [...] },
    "BACK": { "points": [...] },
    "UP": { "points": [...] },
    "DOWN": { "points": [...] },
    "RIGHT": { "points": [...] },
    "LEFT": { "points": [...] },

    // 新規追加
    "PATTERN": {
      "arc_grid": {
        "size": [32, 32],
        "colors": [...],
        "shapes": [
          { "type": "rectangle", "position": [x, y], "size": [w, h] },
          { "type": "circle", "center": [x, y], "radius": r }
        ]
      }
    },

    "CONTOUR": {
      "edges": [
        { "points": [[x1, y1], [x2, y2], ...], "hierarchy": 0 }
      ],
      "bounding_boxes": [
        { "x": 10, "y": 20, "w": 100, "h": 50, "label": "button" }
      ]
    },

    "TEXT": {
      "ocr_results": [
        {
          "text": "Click here",
          "position": [x, y, w, h],
          "confidence": 0.95,
          "language": "en"
        }
      ]
    },

    "SEMANTIC": {
      "objects": [
        { "label": "button", "confidence": 0.9, "bbox": [x, y, w, h] },
        { "label": "window", "confidence": 0.85, "bbox": [x, y, w, h] }
      ],
      "scene_type": "desktop_ui"
    }
  }
}
```

## 実装アーキテクチャ

### 1. 形状検出モジュール (`shape_detector.py`)

```python
class ShapeDetector:
    """OpenCVでエッジ・輪郭を検出"""

    def detect_edges(self, image: np.ndarray) -> np.ndarray:
        """Cannyエッジ検出"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, threshold1=50, threshold2=150)
        return edges

    def detect_contours(self, image: np.ndarray) -> list:
        """輪郭検出と階層構造"""
        edges = self.detect_edges(image)
        contours, hierarchy = cv2.findContours(
            edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )
        return contours, hierarchy

    def detect_shapes(self, contours: list) -> list:
        """形状分類（矩形、円、多角形）"""
        shapes = []
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)

            if len(approx) == 4:
                shapes.append({"type": "rectangle", "contour": approx})
            elif len(approx) > 4:
                # 円に近いか判定
                area = cv2.contourArea(contour)
                perimeter = cv2.arcLength(contour, True)
                circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0

                if circularity > 0.8:
                    shapes.append({"type": "circle", "contour": contour})
                else:
                    shapes.append({"type": "polygon", "contour": approx})

        return shapes
```

### 2. OCRモジュール (`text_recognizer.py`)

```python
class TextRecognizer:
    """Tesseract OCRでテキスト抽出"""

    def __init__(self):
        try:
            import pytesseract
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("pytesseract not available. Install with: pip install pytesseract")

    def extract_text(self, image: np.ndarray, lang: str = "eng+jpn") -> list:
        """画像からテキストを抽出"""
        if not self.available:
            return []

        import pytesseract

        # OCR実行
        data = pytesseract.image_to_data(
            image, lang=lang, output_type=pytesseract.Output.DICT
        )

        # 信頼度の高いテキストのみ抽出
        texts = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            conf = int(data['conf'][i])

            if text and conf > 60:  # 60%以上の信頼度
                texts.append({
                    "text": text,
                    "confidence": conf / 100.0,
                    "position": [
                        data['left'][i],
                        data['top'][i],
                        data['width'][i],
                        data['height'][i]
                    ]
                })

        return texts
```

### 3. ARC-AGI2パターン抽出 (`arc_pattern_extractor.py`)

```python
class ARCPatternExtractor:
    """ARC-AGI2風のグリッドパターン抽出"""

    def __init__(self, grid_size: int = 32):
        self.grid_size = grid_size
        self.color_palette = self._create_palette()

    def _create_palette(self) -> list:
        """ARC-AGI2の10色パレット"""
        return [
            (0, 0, 0),         # 0: Black
            (0, 116, 217),     # 1: Blue
            (255, 65, 54),     # 2: Red
            (46, 204, 64),     # 3: Green
            (255, 220, 0),     # 4: Yellow
            (170, 170, 170),   # 5: Grey
            (240, 18, 190),    # 6: Magenta
            (255, 133, 27),    # 7: Orange
            (127, 219, 255),   # 8: Azure
            (135, 12, 37)      # 9: Maroon
        ]

    def image_to_grid(self, image: np.ndarray) -> np.ndarray:
        """画像をグリッドに変換"""
        from PIL import Image

        # リサイズ
        pil_image = Image.fromarray(image)
        pil_image = pil_image.resize((self.grid_size, self.grid_size), Image.Resampling.LANCZOS)
        grid_array = np.array(pil_image)

        # 色を10色パレットに量子化
        grid = np.zeros((self.grid_size, self.grid_size), dtype=int)

        for i in range(self.grid_size):
            for j in range(self.grid_size):
                pixel = grid_array[i, j]
                grid[i, j] = self._nearest_color(pixel)

        return grid

    def _nearest_color(self, pixel: np.ndarray) -> int:
        """最も近いパレット色を返す"""
        min_dist = float('inf')
        nearest_idx = 0

        for idx, color in enumerate(self.color_palette):
            dist = np.linalg.norm(pixel[:3] - np.array(color))
            if dist < min_dist:
                min_dist = dist
                nearest_idx = idx

        return nearest_idx

    def extract_patterns(self, grid: np.ndarray) -> dict:
        """グリッドからパターンを抽出"""
        patterns = {
            "symmetry": self._check_symmetry(grid),
            "repetitions": self._find_repetitions(grid),
            "shapes": self._detect_grid_shapes(grid)
        }
        return patterns

    def _check_symmetry(self, grid: np.ndarray) -> dict:
        """対称性をチェック"""
        return {
            "horizontal": np.array_equal(grid, np.flipud(grid)),
            "vertical": np.array_equal(grid, np.fliplr(grid)),
            "diagonal": np.array_equal(grid, grid.T)
        }

    def _find_repetitions(self, grid: np.ndarray) -> list:
        """繰り返しパターンを検出"""
        # 簡易実装: 2x2, 3x3のブロックで繰り返しを検出
        repetitions = []
        # TODO: 実装
        return repetitions

    def _detect_grid_shapes(self, grid: np.ndarray) -> list:
        """グリッド上の形状を検出"""
        shapes = []
        # 連結成分分析
        for color_idx in range(10):
            mask = (grid == color_idx).astype(np.uint8)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if len(contour) >= 4:
                    x, y, w, h = cv2.boundingRect(contour)
                    shapes.append({
                        "color": color_idx,
                        "bbox": [x, y, w, h],
                        "area": cv2.contourArea(contour)
                    })

        return shapes
```

### 4. 統合拡張コンバーター (`enhanced_image_to_cross.py`)

```python
class EnhancedImageToCross:
    """拡張された画像→Cross変換"""

    def __init__(self):
        self.base_converter = ImageToCross()
        self.shape_detector = ShapeDetector()
        self.text_recognizer = TextRecognizer()
        self.arc_extractor = ARCPatternExtractor(grid_size=32)

    def convert_image_enhanced(
        self,
        image: Image.Image,
        quality: str = "maximum"
    ) -> dict:
        """拡張された画像変換"""

        # 1. 基本のCross構造（既存の6軸）
        base_cross = self.base_converter.convert_image(image, quality=quality)

        # 2. NumPy配列に変換
        image_array = np.array(image)

        # 3. 形状検出
        contours, hierarchy = self.shape_detector.detect_contours(image_array)
        shapes = self.shape_detector.detect_shapes(contours)

        # 4. テキスト認識
        texts = self.text_recognizer.extract_text(image_array)

        # 5. ARC-AGI2パターン抽出
        arc_grid = self.arc_extractor.image_to_grid(image_array)
        patterns = self.arc_extractor.extract_patterns(arc_grid)

        # 6. Cross構造を拡張
        enhanced_cross = {
            **base_cross,
            "version": "2.0",
            "axes": {
                **base_cross.get("axes", {}),

                "PATTERN": {
                    "arc_grid": {
                        "size": list(arc_grid.shape),
                        "grid": arc_grid.tolist(),
                        "patterns": patterns
                    }
                },

                "CONTOUR": {
                    "shapes": [
                        {
                            "type": shape["type"],
                            "points": shape["contour"].tolist()
                        }
                        for shape in shapes
                    ],
                    "total_contours": len(contours)
                },

                "TEXT": {
                    "ocr_results": texts,
                    "total_text_regions": len(texts)
                }
            }
        }

        return enhanced_cross
```

### 5. 詳細なLLMコンテキスト生成 (`enhanced_llm_context.py`)

```python
def enhanced_image_to_llm_context(image_path: Path, quality: str = "maximum") -> str:
    """拡張された画像分析をLLM可読テキストに変換"""

    converter = EnhancedImageToCross()

    # 画像読み込み
    from PIL import Image
    image = Image.open(image_path).convert('RGB')

    # 拡張変換
    cross_structure = converter.convert_image_enhanced(image, quality=quality)

    # LLMコンテキスト構築
    context_parts = []

    # 1. 基本情報
    context_parts.append(f"# Image Analysis: {image_path.name}")
    context_parts.append(f"Resolution: {image.width}x{image.height}")

    # 2. テキスト内容
    texts = cross_structure["axes"].get("TEXT", {}).get("ocr_results", [])
    if texts:
        context_parts.append("\n## Detected Text:")
        for text_item in texts:
            context_parts.append(
                f"- \"{text_item['text']}\" "
                f"(confidence: {text_item['confidence']:.2f}, "
                f"position: {text_item['position']})"
            )

    # 3. 形状と構造
    shapes = cross_structure["axes"].get("CONTOUR", {}).get("shapes", [])
    if shapes:
        context_parts.append("\n## Detected Shapes:")
        shape_counts = {}
        for shape in shapes:
            shape_type = shape["type"]
            shape_counts[shape_type] = shape_counts.get(shape_type, 0) + 1

        for shape_type, count in shape_counts.items():
            context_parts.append(f"- {count} {shape_type}(s)")

    # 4. ARCパターン
    pattern_data = cross_structure["axes"].get("PATTERN", {}).get("arc_grid", {})
    if pattern_data:
        patterns = pattern_data.get("patterns", {})
        context_parts.append("\n## Visual Patterns (ARC-AGI2):")

        symmetry = patterns.get("symmetry", {})
        if any(symmetry.values()):
            sym_types = [k for k, v in symmetry.items() if v]
            context_parts.append(f"- Symmetry detected: {', '.join(sym_types)}")

        grid = np.array(pattern_data.get("grid", []))
        if grid.size > 0:
            unique_colors = len(np.unique(grid))
            context_parts.append(f"- Color complexity: {unique_colors} distinct colors")
            context_parts.append(f"- Grid size: {grid.shape[0]}x{grid.shape[1]}")

    # 5. 空間的特徴（既存のCross分析）
    context_parts.append("\n## Spatial Features (Cross 6-Axis):")
    for axis in ["FRONT", "BACK", "UP", "DOWN", "RIGHT", "LEFT"]:
        axis_data = cross_structure["axes"].get(axis, {})
        if "features" in axis_data:
            context_parts.append(f"- {axis}: {axis_data['features']}")

    return "\n".join(context_parts)
```

## 動画への適用

### `enhanced_video_to_cross.py`

```python
def enhanced_video_to_llm_context(video_path: Path, max_frames: int = 10) -> str:
    """拡張された動画分析"""

    import cv2
    converter = EnhancedImageToCross()

    cap = cv2.VideoCapture(str(video_path))
    # ... (フレーム抽出は既存と同じ)

    frame_analyses = []

    for frame_data in sampled_frames:
        frame_rgb = frame_data["frame"]
        timestamp = frame_data["timestamp"]

        # PIL Imageに変換
        from PIL import Image
        pil_image = Image.fromarray(frame_rgb)

        # 拡張分析
        cross = converter.convert_image_enhanced(pil_image, quality="maximum")

        # テキスト抽出
        texts = cross["axes"].get("TEXT", {}).get("ocr_results", [])
        text_content = [t["text"] for t in texts]

        # 形状
        shapes = cross["axes"].get("CONTOUR", {}).get("shapes", [])
        shape_summary = f"{len(shapes)} shapes detected"

        frame_analyses.append({
            "timestamp": timestamp,
            "texts": text_content,
            "shapes": shape_summary,
            "cross": cross
        })

    # LLMコンテキスト構築
    context = f"""# Enhanced Video Analysis: {video_path.name}

## Frame-by-Frame Analysis

"""

    for analysis in frame_analyses:
        context += f"\n### Frame at {analysis['timestamp']:.2f}s\n"

        if analysis['texts']:
            context += f"**Text detected:** {', '.join(analysis['texts'])}\n"

        context += f"**Visual elements:** {analysis['shapes']}\n"

    return context
```

## 依存関係

```bash
# 必須
pip install opencv-python numpy pillow

# OCR（オプション）
pip install pytesseract
brew install tesseract  # macOS

# より高度な分析（将来的）
pip install torch torchvision  # 物体検出用
```

## 実装の優先順位

1. **Phase 1（即座に実装）**:
   - エッジ検出と輪郭抽出
   - ARC-AGI2グリッド表現
   - 基本的な形状検出

2. **Phase 2（OCR追加）**:
   - Tesseract統合
   - テキスト位置とコンテキスト

3. **Phase 3（高度な分析）**:
   - YOLOv8等で物体検出
   - UIコンポーネント識別（ボタン、ウィンドウ等）

## まとめ

この設計により、Verantyx Visionは：

✅ **空間的特徴**（現在）+ **実際の内容**（新規）を分析
✅ ARC-AGI2のパターン認識でグリッド表現
✅ OCRでテキスト内容を抽出
✅ 輪郭検出で形状を識別
✅ LLMが理解できる詳細な説明を生成

動画内の「何が描画されているか」を正確に把握できるようになります。
