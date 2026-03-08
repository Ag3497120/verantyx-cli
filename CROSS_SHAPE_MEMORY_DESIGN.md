# Cross形状記憶層 - 点配置パターンから形を認識する設計

## 本質的な理解の修正

### 誤った理解（訂正前）
- OCRやエッジ検出などの外部ツールで形状を認識
- 画像処理の結果をCross構造に「変換」

### 正しい理解
- **Cross構造の点の位置関係そのものが世界モデル**
- 点の配置パターンをCross 6軸で計測 → 立体的に脳内再構成
- 色もCross構造でマッピング → 色の空間的位置関係を6軸で表現
- **断片記憶に形のパターンを保存** → 何の形かを認識する層を強化

## Cross Simulatorの世界モデル

### 点による世界の再構成

画像の各ピクセル → 3D空間の点 → Cross 6軸で位置を計測

```
例: 文字「A」の場合

元の画像:
  *
 * *
*****
*   *

Cross構造での点配置:
点1: (x=0.5, y=0.9, z=0) → FRONT=high, UP=high, RIGHT=center
点2: (x=0.3, y=0.7, z=0) → FRONT=mid, UP=mid, LEFT=slight
点3: (x=0.7, y=0.7, z=0) → FRONT=mid, UP=mid, RIGHT=slight
点4-8: (y=0.5の横線) → UP=mid, RIGHT/LEFT=wide_distribution
点9: (x=0.2, y=0.3, z=0) → FRONT=low, DOWN=low, LEFT=strong
点10: (x=0.8, y=0.3, z=0) → FRONT=low, DOWN=low, RIGHT=strong
```

### Cross 6軸による位置計測

各点の位置を6つの軸で数値化：

```python
point = {
    "position": [x, y, z],  # 3D座標
    "cross_metrics": {
        "FRONT": 0.8,   # 前方への投影強度
        "BACK": 0.2,    # 後方への投影強度
        "UP": 0.9,      # 上方への投影強度
        "DOWN": 0.1,    # 下方への投影強度
        "RIGHT": 0.7,   # 右方への投影強度
        "LEFT": 0.3     # 左方への投影強度
    },
    "color": {
        "rgb": [255, 255, 255],
        "cross_position": {
            # 色空間もCrossでマッピング
            "R_axis": 1.0,
            "G_axis": 1.0,
            "B_axis": 1.0
        }
    }
}
```

## 形状認識のための断片記憶層

### 記憶の構造

形のパターンを**Crossの点配置パターン**として記憶：

```json
{
  "shape_memory": {
    "letter_A": {
      "pattern_signature": {
        "point_count": 10,
        "cross_distribution": {
          "UP_concentration": [0.7, 0.8, 0.9],  // 上部に点が集中
          "CENTER_horizontal_line": [0.4, 0.5, 0.6],  // 中央に横線
          "DOWN_split": ["LEFT", "RIGHT"]  // 下部が左右に分離
        },
        "spatial_relations": [
          {
            "region": "top",
            "cross_pattern": "FRONT=high, UP=high, convergent"
          },
          {
            "region": "middle",
            "cross_pattern": "UP=mid, RIGHT/LEFT=distributed"
          },
          {
            "region": "bottom",
            "cross_pattern": "DOWN=high, bifurcated"
          }
        ]
      },
      "recognition_weight": 0.95
    },

    "rectangle": {
      "pattern_signature": {
        "point_count": "variable",
        "cross_distribution": {
          "edge_concentration": true,  // 点が縁に集中
          "interior_sparse": true      // 内部は疎
        },
        "spatial_relations": [
          {
            "region": "edges",
            "cross_pattern": "RIGHT/LEFT=symmetric, UP/DOWN=symmetric"
          }
        ]
      }
    },

    "circle": {
      "pattern_signature": {
        "cross_distribution": {
          "radial_symmetry": true,  // 放射状対称性
          "CENTER_convergence": true  // 中心への収束
        },
        "spatial_relations": [
          {
            "region": "boundary",
            "cross_pattern": "equal_distribution_all_axes"
          }
        ]
      }
    }
  }
}
```

### 認識プロセス

入力された点群 → Cross計測 → 断片記憶との照合

```
1. 点群をCross 6軸で計測
   → 各点の FRONT/BACK/UP/DOWN/RIGHT/LEFT 値を算出

2. 点の分布パターンを抽出
   → "UP側に点が多い"、"中央に横線"、"下部が二分"

3. 断片記憶と照合
   → letter_A の pattern_signature と類似度計算

4. 最も類似度が高いパターンを返す
   → "この点配置は文字'A'である" (confidence: 0.87)
```

## 実装アーキテクチャ

### 1. Cross Point Mapper (`cross_point_mapper.py`)

```python
class CrossPointMapper:
    """
    画像の各ピクセルを3D空間の点に変換し、
    Cross 6軸で位置を計測する
    """

    def map_image_to_cross_points(self, image: np.ndarray) -> list:
        """
        画像 → Cross点群

        Returns:
            各点の3D座標とCross計測値
        """
        height, width = image.shape[:2]
        points = []

        for y in range(height):
            for x in range(width):
                pixel = image[y, x]

                # ピクセル輝度が閾値以上なら点として記録
                if np.mean(pixel[:3]) > 50:  # 暗すぎる点は除外
                    # 正規化座標 (0-1)
                    norm_x = x / width
                    norm_y = 1 - (y / height)  # Y軸反転
                    norm_z = 0  # 2D画像なのでZ=0

                    # Cross 6軸計測
                    cross_metrics = self._calculate_cross_metrics(
                        norm_x, norm_y, norm_z
                    )

                    # 色のCrossマッピング
                    color_cross = self._map_color_to_cross(pixel)

                    points.append({
                        "position": [norm_x, norm_y, norm_z],
                        "cross": cross_metrics,
                        "color": pixel.tolist(),
                        "color_cross": color_cross
                    })

        return points

    def _calculate_cross_metrics(self, x: float, y: float, z: float) -> dict:
        """
        3D座標 → Cross 6軸計測値

        FRONT/BACK: Z軸方向の投影
        UP/DOWN: Y軸方向の投影
        RIGHT/LEFT: X軸方向の投影
        """
        return {
            "FRONT": max(0, z + 0.5),      # Z軸前方
            "BACK": max(0, 0.5 - z),       # Z軸後方
            "UP": y,                        # Y軸上方
            "DOWN": 1 - y,                  # Y軸下方
            "RIGHT": x,                     # X軸右方
            "LEFT": 1 - x                   # X軸左方
        }

    def _map_color_to_cross(self, pixel: np.ndarray) -> dict:
        """
        色をCross構造でマッピング

        RGB各成分を空間的位置として表現
        """
        r, g, b = pixel[:3] / 255.0  # 正規化

        return {
            "R_axis": r,     # 赤成分 → R軸
            "G_axis": g,     # 緑成分 → G軸
            "B_axis": b,     # B軸
            "intensity": (r + g + b) / 3.0,  # 明度
            "cross_color_position": {
                # 色空間での6軸表現
                "BRIGHT": (r + g + b) / 3.0,
                "DARK": 1 - (r + g + b) / 3.0,
                "WARM": (r + g) / 2.0,    # 赤・黄系
                "COOL": b,                 # 青系
                "SATURATED": max(r, g, b) - min(r, g, b),
                "NEUTRAL": 1 - (max(r, g, b) - min(r, g, b))
            }
        }
```

### 2. Cross Pattern Extractor (`cross_pattern_extractor.py`)

```python
class CrossPatternExtractor:
    """
    Cross点群から分布パターンを抽出
    """

    def extract_pattern(self, points: list) -> dict:
        """
        点群 → Cross分布パターン
        """
        if not points:
            return {}

        # 各軸への点の分布を計算
        up_values = [p["cross"]["UP"] for p in points]
        down_values = [p["cross"]["DOWN"] for p in points]
        right_values = [p["cross"]["RIGHT"] for p in points]
        left_values = [p["cross"]["LEFT"] for p in points]

        pattern = {
            "point_count": len(points),

            # 軸ごとの分布統計
            "UP_distribution": {
                "mean": np.mean(up_values),
                "std": np.std(up_values),
                "concentration": self._calculate_concentration(up_values)
            },
            "DOWN_distribution": {
                "mean": np.mean(down_values),
                "std": np.std(down_values),
                "concentration": self._calculate_concentration(down_values)
            },
            "RIGHT_distribution": {
                "mean": np.mean(right_values),
                "std": np.std(right_values),
                "concentration": self._calculate_concentration(right_values)
            },
            "LEFT_distribution": {
                "mean": np.mean(left_values),
                "std": np.std(left_values),
                "concentration": self._calculate_concentration(left_values)
            },

            # 空間的特徴
            "symmetry": self._check_symmetry(points),
            "clustering": self._detect_clusters(points),
            "connectivity": self._analyze_connectivity(points)
        }

        return pattern

    def _calculate_concentration(self, values: list) -> str:
        """
        値の集中度を判定
        """
        std = np.std(values)

        if std < 0.1:
            return "highly_concentrated"
        elif std < 0.3:
            return "concentrated"
        else:
            return "distributed"

    def _check_symmetry(self, points: list) -> dict:
        """
        Cross軸での対称性をチェック
        """
        # 左右対称性
        left_points = [p for p in points if p["cross"]["LEFT"] > 0.5]
        right_points = [p for p in points if p["cross"]["RIGHT"] > 0.5]

        lr_symmetric = abs(len(left_points) - len(right_points)) < len(points) * 0.1

        # 上下対称性
        up_points = [p for p in points if p["cross"]["UP"] > 0.5]
        down_points = [p for p in points if p["cross"]["DOWN"] > 0.5]

        ud_symmetric = abs(len(up_points) - len(down_points)) < len(points) * 0.1

        return {
            "left_right": lr_symmetric,
            "up_down": ud_symmetric
        }

    def _detect_clusters(self, points: list) -> list:
        """
        点のクラスタを検出（Cross距離ベース）
        """
        # Cross空間での距離でクラスタリング
        clusters = []

        # 簡易実装: UP/DOWN/RIGHT/LEFTの値でグルーピング
        # TODO: より高度なクラスタリング

        return clusters

    def _analyze_connectivity(self, points: list) -> dict:
        """
        点の連結性を分析
        """
        # 近接点のつながりを解析
        # TODO: 実装

        return {
            "connected_components": 0,
            "has_loops": False,
            "has_branches": False
        }
```

### 3. Shape Memory Bank (`shape_memory_bank.py`)

```python
class ShapeMemoryBank:
    """
    形状の断片記憶を管理
    """

    def __init__(self):
        self.memory = self._initialize_memory()

    def _initialize_memory(self) -> dict:
        """
        基本的な形状パターンを初期化
        """
        return {
            "horizontal_line": {
                "signature": {
                    "UP_distribution": {"concentration": "highly_concentrated"},
                    "RIGHT_distribution": {"concentration": "distributed"},
                    "symmetry": {"left_right": True}
                },
                "label": "horizontal_line"
            },

            "vertical_line": {
                "signature": {
                    "RIGHT_distribution": {"concentration": "highly_concentrated"},
                    "UP_distribution": {"concentration": "distributed"},
                    "symmetry": {"up_down": True}
                },
                "label": "vertical_line"
            },

            "rectangle": {
                "signature": {
                    "symmetry": {"left_right": True, "up_down": True},
                    "clustering": "four_corners",
                    "connectivity": {"has_loops": True}
                },
                "label": "rectangle"
            },

            "circle": {
                "signature": {
                    "symmetry": {"left_right": True, "up_down": True},
                    "UP_distribution": {"concentration": "concentrated"},
                    "RIGHT_distribution": {"concentration": "concentrated"},
                    "connectivity": {"has_loops": True}
                },
                "label": "circle"
            },

            "triangle": {
                "signature": {
                    "UP_distribution": {"mean": ">0.6"},  # 上部に点
                    "DOWN_distribution": {"concentration": "distributed"},  # 下部に底辺
                    "connectivity": {"has_loops": True}
                },
                "label": "triangle"
            }
        }

    def recognize_shape(self, pattern: dict) -> dict:
        """
        Cross分布パターン → 形状認識

        Args:
            pattern: CrossPatternExtractorから抽出されたパターン

        Returns:
            認識結果 {"shape": "rectangle", "confidence": 0.85}
        """
        best_match = None
        best_score = 0

        for shape_name, shape_data in self.memory.items():
            score = self._calculate_similarity(pattern, shape_data["signature"])

            if score > best_score:
                best_score = score
                best_match = shape_data["label"]

        return {
            "shape": best_match,
            "confidence": best_score
        }

    def _calculate_similarity(self, pattern: dict, signature: dict) -> float:
        """
        パターンとシグネチャの類似度を計算
        """
        score = 0.0
        total_checks = 0

        # 対称性のチェック
        if "symmetry" in signature:
            if pattern.get("symmetry", {}).get("left_right") == signature["symmetry"].get("left_right"):
                score += 1
            total_checks += 1

            if pattern.get("symmetry", {}).get("up_down") == signature["symmetry"].get("up_down"):
                score += 1
            total_checks += 1

        # 分布のチェック
        for axis in ["UP", "DOWN", "RIGHT", "LEFT"]:
            dist_key = f"{axis}_distribution"
            if dist_key in signature:
                pattern_conc = pattern.get(dist_key, {}).get("concentration")
                sig_conc = signature[dist_key].get("concentration")

                if pattern_conc == sig_conc:
                    score += 1
                total_checks += 1

        return score / total_checks if total_checks > 0 else 0

    def learn_new_shape(self, pattern: dict, label: str):
        """
        新しい形状パターンを学習
        """
        self.memory[label] = {
            "signature": pattern,
            "label": label,
            "learned": True
        }

        logger.info(f"Learned new shape: {label}")
```

### 4. Enhanced Image Converter (統合)

```python
class EnhancedImageToCross:
    """
    画像 → Cross点群 → パターン抽出 → 形状認識
    """

    def __init__(self):
        self.point_mapper = CrossPointMapper()
        self.pattern_extractor = CrossPatternExtractor()
        self.shape_memory = ShapeMemoryBank()

    def convert_with_recognition(self, image: Image.Image) -> dict:
        """
        画像を解析してCross構造 + 形状認識結果を返す
        """
        # 1. 画像 → Cross点群
        image_array = np.array(image)
        points = self.point_mapper.map_image_to_cross_points(image_array)

        # 2. Cross分布パターン抽出
        pattern = self.pattern_extractor.extract_pattern(points)

        # 3. 形状認識
        recognition = self.shape_memory.recognize_shape(pattern)

        # 4. Cross構造を構築
        cross_structure = {
            "version": "2.0_shape_recognition",
            "type": "image_with_shape_memory",

            "points": points,
            "point_count": len(points),

            "cross_pattern": pattern,

            "recognized_shapes": [recognition],

            "axes": {
                "FRONT": {"points": [p for p in points if p["cross"]["FRONT"] > 0.5]},
                "BACK": {"points": [p for p in points if p["cross"]["BACK"] > 0.5]},
                "UP": {"points": [p for p in points if p["cross"]["UP"] > 0.5]},
                "DOWN": {"points": [p for p in points if p["cross"]["DOWN"] > 0.5]},
                "RIGHT": {"points": [p for p in points if p["cross"]["RIGHT"] > 0.5]},
                "LEFT": {"points": [p for p in points if p["cross"]["LEFT"] > 0.5]}
            }
        }

        return cross_structure
```

### 5. LLMコンテキスト生成

```python
def cross_shape_to_llm_context(image_path: Path) -> str:
    """
    Cross形状認識の結果をLLM可読テキストに
    """
    from PIL import Image

    converter = EnhancedImageToCross()
    image = Image.open(image_path).convert('RGB')

    cross_structure = converter.convert_with_recognition(image)

    # コンテキスト構築
    context = f"""# Cross Shape Recognition: {image_path.name}

## Recognized Shapes
"""

    for shape_data in cross_structure["recognized_shapes"]:
        context += f"- {shape_data['shape']} (confidence: {shape_data['confidence']:.2f})\n"

    context += f"\n## Cross Point Distribution\n"
    context += f"Total points: {cross_structure['point_count']}\n\n"

    pattern = cross_structure["cross_pattern"]

    context += f"### Spatial Distribution\n"
    for axis in ["UP", "DOWN", "RIGHT", "LEFT"]:
        dist = pattern.get(f"{axis}_distribution", {})
        context += f"- {axis}: {dist.get('concentration', 'unknown')}\n"

    context += f"\n### Symmetry\n"
    sym = pattern.get("symmetry", {})
    context += f"- Left-Right: {'Yes' if sym.get('left_right') else 'No'}\n"
    context += f"- Up-Down: {'Yes' if sym.get('up_down') else 'No'}\n"

    return context
```

## 動画への適用

```python
def enhanced_video_with_shape_memory(video_path: Path, max_frames: int = 10) -> str:
    """
    動画の各フレームで形状認識を実行
    """
    import cv2
    converter = EnhancedImageToCross()

    cap = cv2.VideoCapture(str(video_path))
    # ... フレーム抽出

    frame_analyses = []

    for frame_data in sampled_frames:
        pil_image = Image.fromarray(frame_data["frame"])

        # Cross形状認識
        cross_structure = converter.convert_with_recognition(pil_image)

        shapes = [s["shape"] for s in cross_structure["recognized_shapes"]]

        frame_analyses.append({
            "timestamp": frame_data["timestamp"],
            "shapes": shapes,
            "point_count": cross_structure["point_count"]
        })

    # LLMコンテキスト
    context = f"""# Video Shape Recognition: {video_path.name}

## Frame-by-Frame Shape Analysis

"""

    for analysis in frame_analyses:
        context += f"\n### Frame at {analysis['timestamp']:.2f}s\n"
        context += f"Detected shapes: {', '.join(analysis['shapes'])}\n"
        context += f"Cross points: {analysis['point_count']}\n"

    return context
```

## まとめ

この設計により：

✅ **Cross構造の点配置パターンそのものから形を認識**
✅ 外部ツール（OCR、エッジ検出）に依存しない
✅ 点の位置関係をCross 6軸で計測 → 世界モデルを脳内再構成
✅ 色もCross構造でマッピング → 色の空間的位置関係を表現
✅ 断片記憶に形のパターンを保存 → 認識層を強化
✅ 新しい形状を学習可能（learn_new_shape）

動画内の「何が描画されているか」をCross点配置パターンから理解できるようになります。
