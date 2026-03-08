# Multi-Layer Cross Structure Design
多層Cross構造による高密度画像認識設計

## 概要

現在のCross構造は1層のみで情報密度が低い。これを多層化し、6軸で情報を相互接続することで、より精密で豊かな認識を実現する。

## 問題点（現状）

### 1. 単層構造の限界
```
現在: 1層のCross構造
画像 → [Cross Layer 0] → 認識結果

問題:
- 情報密度が薄い
- 抽象化レベルが1つしかない
- 階層的な特徴表現ができない
```

### 2. 粒度の粗さ
```
現在の最大品質:
- max_points: 50,000点
- downsample_factor: 1

問題:
- 高解像度画像で細部が失われる
- テキストや細かいパターンの認識が困難
```

### 3. テーマ別学習の欠如
```
問題:
- 汎用的な点群表現のみ
- 「空」「花」「人間」などの概念が事前学習されていない
- 認識のたびに一から解析が必要
```

## 解決策: 多層Cross構造

### アーキテクチャ

```
画像
  ↓
【Layer 0: Pixel Layer】超高密度点群（200,000点）
  ├─ FRONT/BACK軸: 色情報（RGB）
  ├─ UP/DOWN軸: 空間位置（Y軸）
  ├─ RIGHT/LEFT軸: 空間位置（X軸）
  └─ TIME軸: 画素単位の変化（動画用）
  ↓ 6軸接続
【Layer 1: Feature Layer】特徴点層（50,000点）
  ├─ FRONT軸: エッジ特徴
  ├─ BACK軸: テクスチャ特徴
  ├─ UP軸: 明度勾配（上方向）
  ├─ DOWN軸: 明度勾配（下方向）
  ├─ RIGHT軸: 水平パターン
  └─ LEFT軸: 垂直パターン
  ↓ 6軸接続
【Layer 2: Pattern Layer】パターン層（10,000点）
  ├─ FRONT軸: 基本形状（線、円、矩形）
  ├─ BACK軸: 断片記憶パターン
  ├─ UP軸: 上下構造（空/地面など）
  ├─ DOWN軸: 重力方向特徴
  ├─ RIGHT軸: 左右対称性
  └─ LEFT軸: 水平配置パターン
  ↓ 6軸接続
【Layer 3: Semantic Layer】意味層（1,000点）
  ├─ FRONT軸: オブジェクト認識
  ├─ BACK軸: テーマ記憶（空/花/人/物）
  ├─ UP軸: 空間関係（上）
  ├─ DOWN軸: 空間関係（下）
  ├─ RIGHT軸: 意味的右側関係
  └─ LEFT軸: 意味的左側関係
  ↓ 6軸接続
【Layer 4: Concept Layer】概念層（100点）
  ├─ FRONT軸: シーン分類
  ├─ BACK軸: 記憶想起
  ├─ UP軸: 抽象概念
  ├─ DOWN軸: 具体要素
  ├─ RIGHT軸: 関連概念
  └─ LEFT軸: 対比概念
```

## 6軸相互接続の仕組み

### 1. 層間接続（Vertical Connections）

各層の点は、下位層の複数点と6軸で接続される:

```python
class CrossLayerConnection:
    """層間の6軸接続"""

    def __init__(self, from_layer: int, to_layer: int):
        self.from_layer = from_layer
        self.to_layer = to_layer

    def connect_point(self, upper_point: CrossPoint, lower_points: List[CrossPoint]):
        """
        上位層の1点を下位層の複数点に接続

        FRONT軸: 前方に位置する下位点との接続
        BACK軸: 後方に位置する下位点との接続
        UP軸: 上方向の特徴を持つ下位点との接続
        DOWN軸: 下方向の特徴を持つ下位点との接続
        RIGHT軸: 右側の下位点との接続
        LEFT軸: 左側の下位点との接続
        """
        connections = {
            "FRONT": [],  # Z > 0の点
            "BACK": [],   # Z < 0の点
            "UP": [],     # Y > threshold の点
            "DOWN": [],   # Y < threshold の点
            "RIGHT": [],  # X > threshold の点
            "LEFT": []    # X < threshold の点
        }

        for lower_point in lower_points:
            # 相対位置を計算
            dx = lower_point.x - upper_point.x
            dy = lower_point.y - upper_point.y
            dz = lower_point.z - upper_point.z

            # 各軸に割り当て
            if dz > 0:
                connections["FRONT"].append(lower_point)
            else:
                connections["BACK"].append(lower_point)

            if dy > 0.1:
                connections["UP"].append(lower_point)
            elif dy < -0.1:
                connections["DOWN"].append(lower_point)

            if dx > 0.1:
                connections["RIGHT"].append(lower_point)
            elif dx < -0.1:
                connections["LEFT"].append(lower_point)

        return connections
```

### 2. 層内接続（Horizontal Connections）

同一層内でも6軸で近傍点を接続:

```python
class IntraLayerConnection:
    """層内の6軸接続"""

    def connect_neighbors(self, point: CrossPoint, all_points: List[CrossPoint], k: int = 6):
        """
        各軸方向に最も近いk個の点を接続

        これにより、層内で情報が6軸方向に伝播する
        """
        neighbors = {
            "FRONT": self._find_k_nearest(point, all_points, axis='z', direction=1, k=k),
            "BACK": self._find_k_nearest(point, all_points, axis='z', direction=-1, k=k),
            "UP": self._find_k_nearest(point, all_points, axis='y', direction=1, k=k),
            "DOWN": self._find_k_nearest(point, all_points, axis='y', direction=-1, k=k),
            "RIGHT": self._find_k_nearest(point, all_points, axis='x', direction=1, k=k),
            "LEFT": self._find_k_nearest(point, all_points, axis='x', direction=-1, k=k),
        }
        return neighbors
```

## 超高密度点群（粒度の向上）

### Layer 0の仕様

```python
LAYER_0_CONFIG = {
    "name": "Pixel Layer",
    "max_points": 200000,  # 20万点（従来の4倍）
    "downsample_factor": 1,  # ダウンサンプリングなし
    "point_extraction": "dense_grid",  # 密なグリッドサンプリング

    # 各点の属性
    "point_attributes": {
        "position": (x, y, z),  # 3D位置
        "color": (r, g, b),     # RGB色
        "intensity": float,      # 明度
        "gradient_x": float,     # X方向勾配
        "gradient_y": float,     # Y方向勾配
        "local_variance": float, # 局所分散（テクスチャ）
    },

    # 6軸マッピング
    "axis_mapping": {
        "FRONT": "r",  # 赤成分
        "BACK": "b",   # 青成分
        "UP": "y",     # Y位置
        "DOWN": "1-y", # 下方向距離
        "RIGHT": "x",  # X位置
        "LEFT": "1-x"  # 左方向距離
    }
}
```

### 粒度の段階的削減

各層で点数を1/4〜1/5に削減し、抽象度を上げる:

```
Layer 0: 200,000点（全画素レベル）
Layer 1:  50,000点（特徴点）
Layer 2:  10,000点（パターン）
Layer 3:   1,000点（意味）
Layer 4:     100点（概念）
```

## テーマ別学習システム

### 学習対象テーマ

1. **自然要素**
   - 空（sky）
   - 雲（cloud）
   - 花（flower）
   - 木（tree）
   - 水（water）

2. **人工物**
   - 建物（building）
   - 道路（road）
   - 車（car）
   - テキスト（text）

3. **生物**
   - 人間（human）
   - 顔（face）
   - 動物（animal）

### テーマ記憶の構造

```python
class ThemeMemoryBank:
    """テーマ別Cross構造記憶バンク"""

    def __init__(self):
        self.themes = {}

    def learn_theme(self, theme_name: str, sample_images: List[Path]):
        """
        テーマの学習

        複数のサンプル画像から共通のCross構造パターンを抽出
        """
        # 1. 各サンプルを多層Cross構造に変換
        cross_structures = []
        for img_path in sample_images:
            cross_structure = multi_layer_convert(img_path)
            cross_structures.append(cross_structure)

        # 2. 各層でパターンを統合
        theme_pattern = {
            "layer_0": self._extract_common_pattern(
                [cs["layers"][0] for cs in cross_structures]
            ),
            "layer_1": self._extract_common_pattern(
                [cs["layers"][1] for cs in cross_structures]
            ),
            "layer_2": self._extract_common_pattern(
                [cs["layers"][2] for cs in cross_structures]
            ),
            "layer_3": self._extract_common_pattern(
                [cs["layers"][3] for cs in cross_structures]
            ),
            "layer_4": self._extract_common_pattern(
                [cs["layers"][4] for cs in cross_structures]
            ),
        }

        # 3. 6軸ごとの特徴署名を生成
        theme_signature = self._generate_theme_signature(theme_pattern)

        # 4. 記憶バンクに保存
        self.themes[theme_name] = {
            "pattern": theme_pattern,
            "signature": theme_signature,
            "sample_count": len(sample_images)
        }

    def _extract_common_pattern(self, layer_data_list: List[Dict]) -> Dict:
        """複数のCross層から共通パターンを抽出"""
        # 各軸の分布統計を統合
        common_pattern = {
            "FRONT": self._merge_axis_statistics([ld["FRONT"] for ld in layer_data_list]),
            "BACK": self._merge_axis_statistics([ld["BACK"] for ld in layer_data_list]),
            "UP": self._merge_axis_statistics([ld["UP"] for ld in layer_data_list]),
            "DOWN": self._merge_axis_statistics([ld["DOWN"] for ld in layer_data_list]),
            "RIGHT": self._merge_axis_statistics([ld["RIGHT"] for ld in layer_data_list]),
            "LEFT": self._merge_axis_statistics([ld["LEFT"] for ld in layer_data_list]),
        }
        return common_pattern

    def _generate_theme_signature(self, theme_pattern: Dict) -> Dict:
        """テーマの6軸特徴署名を生成"""
        signature = {}

        # 各層・各軸の特徴を数値化
        for layer_name, layer_data in theme_pattern.items():
            signature[layer_name] = {}
            for axis_name, axis_data in layer_data.items():
                # 軸ごとの特徴ベクトル
                signature[layer_name][axis_name] = {
                    "mean": axis_data["mean"],
                    "std": axis_data["std"],
                    "distribution_type": axis_data["distribution"],
                    "peak_positions": axis_data.get("peaks", []),
                    "concentration": axis_data.get("concentration", 0.5)
                }

        return signature

    def recognize_theme(self, cross_structure: Dict) -> Dict[str, float]:
        """
        Cross構造からテーマを認識

        Returns:
            各テーマとの類似度スコア
        """
        scores = {}

        for theme_name, theme_data in self.themes.items():
            # 各層でのマッチングスコアを計算
            layer_scores = []

            for layer_idx in range(5):
                layer_score = self._match_layer(
                    cross_structure["layers"][layer_idx],
                    theme_data["pattern"][f"layer_{layer_idx}"]
                )
                layer_scores.append(layer_score)

            # 重み付き平均（上位層ほど重要）
            weights = [0.1, 0.15, 0.2, 0.25, 0.3]  # Layer 4が最重要
            weighted_score = sum(s * w for s, w in zip(layer_scores, weights))

            scores[theme_name] = weighted_score

        return scores
```

## 実装ファイル構成

### 新規作成ファイル

1. **`multi_layer_cross.py`**
   - 多層Cross構造への変換
   - 5層のCross構造生成
   - 層間・層内6軸接続

2. **`theme_memory_bank.py`**
   - テーマ別記憶バンク
   - 学習・認識機能
   - 6軸特徴署名

3. **`learn_themes.jcross`**
   - テーマ学習用JCrossプログラム
   - ユーザーの写真から自動学習

4. **`multi_layer_processors.py`**
   - 多層Cross用プロセッサ（25個以上）
   - 層間接続プロセッサ
   - テーマ認識プロセッサ

5. **`run_theme_learning.py`**
   - テーマ学習ランナー
   - コンピュータから写真を読み込み
   - 自動学習実行

## JCross実装（learn_themes.jcross）

```jcross
# テーマ別写真学習プログラム
# ユーザーのコンピュータから写真を読み込み、Cross構造に変換して学習

# ============================================================
# 1. 写真ファイルの検索と読み込み
# ============================================================

# テーマディレクトリから写真を収集
実行する theme.find_photos = {
  "theme": "sky",
  "directory": "~/Pictures",
  "max_samples": 5
}
入れる sky_photos

実行する theme.find_photos = {
  "theme": "flower",
  "directory": "~/Pictures",
  "max_samples": 5
}
入れる flower_photos

実行する theme.find_photos = {
  "theme": "human",
  "directory": "~/Pictures",
  "max_samples": 5
}
入れる human_photos

# ============================================================
# 2. 各写真を多層Cross構造に変換
# ============================================================

# 空の写真を変換
ラベル CONVERT_SKY
  実行する multi_layer.convert = {
    "quality": "ultra_high",
    "layers": 5,
    "max_points_layer0": 200000
  }
  実行する array.append
  実行する counter.increment
  実行する counter.check
  条件ジャンプ CONVERT_SKY  # まだサンプルが残っている場合
入れる sky_cross_structures

# 花の写真を変換
ラベル CONVERT_FLOWER
  実行する multi_layer.convert = {
    "quality": "ultra_high",
    "layers": 5,
    "max_points_layer0": 200000
  }
  実行する array.append
  実行する counter.increment
  実行する counter.check
  条件ジャンプ CONVERT_FLOWER
入れる flower_cross_structures

# 人間の写真を変換
ラベル CONVERT_HUMAN
  実行する multi_layer.convert = {
    "quality": "ultra_high",
    "layers": 5,
    "max_points_layer0": 200000
  }
  実行する array.append
  実行する counter.increment
  実行する counter.check
  条件ジャンプ CONVERT_HUMAN
入れる human_cross_structures

# ============================================================
# 3. 各層で共通パターンを抽出（6軸ごと）
# ============================================================

# Layer 0: Pixel Layer
実行する pattern.extract_common = {
  "layer": 0,
  "axis": "FRONT"
}
実行する pattern.extract_common = {"layer": 0, "axis": "BACK"}
実行する pattern.extract_common = {"layer": 0, "axis": "UP"}
実行する pattern.extract_common = {"layer": 0, "axis": "DOWN"}
実行する pattern.extract_common = {"layer": 0, "axis": "RIGHT"}
実行する pattern.extract_common = {"layer": 0, "axis": "LEFT"}

# Layer 1: Feature Layer
実行する pattern.extract_common = {"layer": 1, "axis": "FRONT"}
実行する pattern.extract_common = {"layer": 1, "axis": "BACK"}
実行する pattern.extract_common = {"layer": 1, "axis": "UP"}
実行する pattern.extract_common = {"layer": 1, "axis": "DOWN"}
実行する pattern.extract_common = {"layer": 1, "axis": "RIGHT"}
実行する pattern.extract_common = {"layer": 1, "axis": "LEFT"}

# Layer 2〜4も同様...

# ============================================================
# 4. 6軸特徴署名を生成
# ============================================================

実行する theme.generate_signature = {
  "theme": "sky",
  "layers": 5,
  "axes": 6
}
入れる sky_signature

実行する theme.generate_signature = {
  "theme": "flower",
  "layers": 5,
  "axes": 6
}
入れる flower_signature

実行する theme.generate_signature = {
  "theme": "human",
  "layers": 5,
  "axes": 6
}
入れる human_signature

# ============================================================
# 5. テーマ記憶バンクに保存
# ============================================================

実行する theme.save_to_memory = {
  "theme": "sky",
  "layer_count": 5,
  "axis_count": 6
}

実行する theme.save_to_memory = {
  "theme": "flower",
  "layer_count": 5,
  "axis_count": 6
}

実行する theme.save_to_memory = {
  "theme": "human",
  "layer_count": 5,
  "axis_count": 6
}

# ============================================================
# 6. 学習結果レポート生成
# ============================================================

実行する report.generate = {
  "themes": ["sky", "flower", "human"],
  "layers": 5,
  "axes": 6,
  "total_photos": 15
}

実行する report.save
```

## 認識フロー（新しい画像の解析）

```
新しい画像
  ↓
【1】多層Cross変換（5層、20万点）
  ↓
【2】各層で6軸特徴抽出
  ↓
【3】テーマ記憶バンクとマッチング
  ↓
【4】各テーマとの類似度スコア計算
  ↓
【5】最も類似度の高いテーマを認識
  ↓
【6】そのテーマの詳細パターンを適用
  ↓
【7】より精密な解析結果を生成
```

## 情報密度の比較

### 従来（単層）
```
総点数: 50,000点
層数: 1層
軸数: 6軸
情報量: 50,000 × 6 = 300,000 次元
```

### 新方式（多層）
```
総点数: 200,000 + 50,000 + 10,000 + 1,000 + 100 = 261,100点
層数: 5層
軸数: 6軸/層
層間接続: 各点が平均10点と接続
層内接続: 各点が6軸×6点と接続

情報量推定:
- 点属性: 261,100 × 6軸 × 8属性 = 12,532,800 次元
- 層間接続: 261,100 × 10接続 × 6軸 = 15,666,000 エッジ
- 層内接続: 261,100 × 36接続 = 9,399,600 エッジ

総情報量: 約3,760万次元（従来の125倍）
```

## 次のステップ

1. `multi_layer_cross.py` の実装
2. `theme_memory_bank.py` の実装
3. `multi_layer_processors.py` の実装（25個以上）
4. `learn_themes.jcross` の完全実装
5. `run_theme_learning.py` の実装
6. サンプル写真での学習テスト
7. 認識精度の検証
