# Point-Based Visual Recognition Design
点配置ベースの視覚認識設計

## 新しいアプローチ

### 従来の問題

```
従来: 言葉で理解しようとする
画像 → "これは四角です" → "四角の中にテキストがあります"

問題:
- 言葉による抽象化が先に来る
- Cross構造の点配置が活かせていない
- シミュレーションによる学習がない
```

### 新しいアプローチ

```
新方式: 点配置として見る → シミュレーションで覚える

【1】画像を見る
   ↓
【2】点の配置パターンを検出
   "この領域に点が密集している"
   "この領域は点が少ない（空白）"
   ↓
【3】点の境界を検出（バウンディングボックス）
   "点群A: (x1, y1) 〜 (x2, y2) の四角形領域"
   "点群B: (x3, y3) 〜 (x4, y4) の四角形領域"
   ↓
【4】出力（視覚的記述）
   "四角い領域(100, 50)〜(200, 150)に何かが表示されている"
   "四角い領域(50, 200)〜(400, 250)に何かが表示されている"
   ↓
【5】Cross構造でシミュレーション
   その領域の点配置を時系列でシミュレート
   ↓
【6】シミュレーション結果を記憶
   「この点配置パターン」として記憶
   （言葉のラベルは後で学習）
```

## 認識フロー詳細

### Step 1: 点の密度マップ作成

```python
画像（1920x1080）
  ↓
多層Cross変換（200,000点）
  ↓
グリッド分割（例: 32x32グリッド）
  ↓
各グリッドセルの点密度を計算
  ↓
密度マップ
  [
    [0, 0, 5, 12, 8, ...],  # 行1
    [0, 0, 3, 15, 9, ...],  # 行2
    ...
  ]
```

### Step 2: 領域検出（密度ベース）

```python
密度マップ
  ↓
閾値処理（密度 > threshold）
  ↓
連結領域検出
  ↓
各領域のバウンディングボックス計算
  ↓
検出結果
  [
    {
      "bbox": (100, 50, 200, 150),  # (x1, y1, x2, y2)
      "point_count": 1523,
      "density": 0.85,
      "region_id": 0
    },
    {
      "bbox": (50, 200, 400, 250),
      "point_count": 892,
      "density": 0.62,
      "region_id": 1
    },
    ...
  ]
```

### Step 3: 視覚的出力生成

```
検出された領域を視覚的に記述:

フレーム 0 (0.00秒):
  ┌─────────────────────────────────────┐
  │ 領域 #0                             │
  │   位置: (100, 50) 〜 (200, 150)     │
  │   サイズ: 100 x 100 ピクセル        │
  │   点数: 1,523 点                    │
  │   密度: 85%                         │
  │   配置: 中央上部                    │
  └─────────────────────────────────────┘

  ┌─────────────────────────────────────┐
  │ 領域 #1                             │
  │   位置: (50, 200) 〜 (400, 250)     │
  │   サイズ: 350 x 50 ピクセル         │
  │   点数: 892 点                      │
  │   密度: 62%                         │
  │   配置: 左下                        │
  │   形状: 横長の矩形                  │
  └─────────────────────────────────────┘
```

### Step 4: Cross構造シミュレーション

```python
各領域について:
  ↓
【1】領域内の点群を抽出
  points_in_region = filter_points_by_bbox(all_points, bbox)

  ↓
【2】点群のCross構造を計算
  cross_structure = calculate_cross_structure(points_in_region)

  ↓
【3】点群を物理シミュレーションで動かす
  # 例: 重力をかけてみる
  timeline = simulate_with_gravity(points_in_region, duration=1.0)

  ↓
【4】シミュレーション結果を観察
  - この点配置は重力で下に落ちる？
  - この点配置は形を保つ？（剛体）
  - この点配置はバラバラになる？（粒子）

  ↓
【5】振る舞いパターンとして記憶
  behavior_pattern = {
    "original_bbox": bbox,
    "point_count": len(points_in_region),
    "simulation_result": timeline,
    "behavior_type": "rigid_body" | "particles" | "static"
  }
```

### Step 5: 時系列での変化観察

```
動画の場合:

フレーム t=0:
  領域 #0: (100, 50) 〜 (200, 150)
  領域 #1: (50, 200) 〜 (400, 250)
  ↓
フレーム t=1:
  領域 #0: (102, 55) 〜 (202, 155)  ← 移動した！
  領域 #1: (50, 200) 〜 (400, 250)  ← 静止
  ↓
フレーム t=2:
  領域 #0: (105, 65) 〜 (205, 165)  ← さらに移動
  領域 #1: (50, 200) 〜 (400, 250)  ← 静止
  ↓
観察結果:
  領域 #0: 下方向に移動している（落下？）
  領域 #1: 静止している（背景？地面？）
```

## 実装方針

### 1. 点密度ベース領域検出

```python
class PointDensityRegionDetector:
    """点密度ベースの領域検出器"""

    def __init__(self, grid_size: int = 32):
        self.grid_size = grid_size

    def detect_regions(
        self,
        points: List[CrossPoint],
        image_size: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        """
        点群から領域を検出

        Returns:
            領域のリスト（バウンディングボックス付き）
        """
        # 1. 密度マップ作成
        density_map = self._create_density_map(points, image_size)

        # 2. 閾値処理
        binary_map = density_map > threshold

        # 3. 連結領域検出
        labeled_map = label_connected_components(binary_map)

        # 4. 各領域のバウンディングボックス計算
        regions = []
        for region_id in unique_labels:
            bbox = self._calculate_bbox(labeled_map, region_id)
            points_in_region = self._get_points_in_bbox(points, bbox)

            regions.append({
                "region_id": region_id,
                "bbox": bbox,
                "point_count": len(points_in_region),
                "density": self._calculate_density(points_in_region, bbox),
                "points": points_in_region
            })

        return regions
```

### 2. 視覚的出力生成器

```python
class VisualOutputFormatter:
    """視覚的出力フォーマッター"""

    def format_frame_regions(
        self,
        frame_number: int,
        timestamp: float,
        regions: List[Dict[str, Any]],
        image_size: Tuple[int, int]
    ) -> str:
        """
        フレームの領域を視覚的にフォーマット
        """
        output = []

        output.append(f"\n{'='*60}")
        output.append(f"フレーム {frame_number} ({timestamp:.2f}秒)")
        output.append(f"画像サイズ: {image_size[0]} x {image_size[1]}")
        output.append(f"検出領域数: {len(regions)}")
        output.append(f"{'='*60}\n")

        for region in regions:
            bbox = region["bbox"]
            point_count = region["point_count"]
            density = region["density"]

            # バウンディングボックス情報
            x1, y1, x2, y2 = bbox
            width = x2 - x1
            height = y2 - y1

            # 配置位置を判定
            position = self._describe_position(bbox, image_size)

            # 形状を判定
            shape = self._describe_shape(width, height)

            output.append(f"  ┌{'─'*50}┐")
            output.append(f"  │ 領域 #{region['region_id']:02d}")
            output.append(f"  │   位置: ({x1}, {y1}) 〜 ({x2}, {y2})")
            output.append(f"  │   サイズ: {width} x {height} ピクセル")
            output.append(f"  │   点数: {point_count:,} 点")
            output.append(f"  │   密度: {density*100:.1f}%")
            output.append(f"  │   配置: {position}")
            output.append(f"  │   形状: {shape}")
            output.append(f"  └{'─'*50}┘")
            output.append("")

        return "\n".join(output)

    def _describe_position(
        self,
        bbox: Tuple[int, int, int, int],
        image_size: Tuple[int, int]
    ) -> str:
        """位置を記述"""
        x1, y1, x2, y2 = bbox
        width, height = image_size

        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        # 横方向
        if center_x < width / 3:
            h_pos = "左"
        elif center_x > width * 2 / 3:
            h_pos = "右"
        else:
            h_pos = "中央"

        # 縦方向
        if center_y < height / 3:
            v_pos = "上部"
        elif center_y > height * 2 / 3:
            v_pos = "下部"
        else:
            v_pos = "中部"

        return f"{h_pos}{v_pos}"

    def _describe_shape(self, width: int, height: int) -> str:
        """形状を記述"""
        aspect_ratio = width / height

        if aspect_ratio > 3:
            return "横長の矩形"
        elif aspect_ratio < 0.33:
            return "縦長の矩形"
        elif 0.9 < aspect_ratio < 1.1:
            return "正方形に近い矩形"
        else:
            return "矩形"
```

### 3. シミュレーションベース記憶

```python
class SimulationBasedMemory:
    """シミュレーションベースの記憶システム"""

    def __init__(self):
        self.memory_bank = []

    def learn_from_simulation(
        self,
        region: Dict[str, Any],
        simulation_timeline: List[Dict[str, Any]]
    ):
        """
        シミュレーションから学習

        言葉ではなく、点配置とその振る舞いを記憶
        """
        points = region["points"]
        bbox = region["bbox"]

        # 1. 点配置パターンを抽出
        point_pattern = self._extract_point_pattern(points, bbox)

        # 2. シミュレーション振る舞いを抽出
        behavior = self._extract_behavior(simulation_timeline)

        # 3. 記憶として保存（言葉のラベルなし）
        memory_entry = {
            "id": len(self.memory_bank),
            "point_pattern": point_pattern,
            "behavior": behavior,
            "original_bbox": bbox,
            "point_count": len(points),
            "timestamp": datetime.now().isoformat()
        }

        self.memory_bank.append(memory_entry)

    def recognize_by_simulation(
        self,
        new_region: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        新しい領域を、過去のシミュレーション記憶と照合

        言葉を使わず、点配置の類似性で認識
        """
        # 新しい領域をシミュレート
        new_points = new_region["points"]
        new_timeline = simulate_physics(new_points, duration=1.0)
        new_behavior = self._extract_behavior(new_timeline)

        # 記憶と照合
        matches = []

        for memory_entry in self.memory_bank:
            similarity = self._calculate_similarity(
                new_behavior,
                memory_entry["behavior"]
            )

            if similarity > 0.7:
                matches.append({
                    "memory_id": memory_entry["id"],
                    "similarity": similarity
                })

        return sorted(matches, key=lambda x: x["similarity"], reverse=True)
```

## 動画解析の新しい出力フォーマット

```
=============================================================
動画解析結果
=============================================================
ファイル: screen_recording.mp4
解像度: 1920 x 1080
フレーム数: 24,319
解析フレーム数: 100

=============================================================
フレーム 0 (0.00秒)
=============================================================
検出領域数: 3

  ┌──────────────────────────────────────────────┐
  │ 領域 #00                                     │
  │   位置: (50, 30) 〜 (1870, 80)               │
  │   サイズ: 1820 x 50 ピクセル                 │
  │   点数: 2,341 点                             │
  │   密度: 82%                                  │
  │   配置: 中央上部                             │
  │   形状: 横長の矩形                           │
  └──────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────┐
  │ 領域 #01                                     │
  │   位置: (100, 150) 〜 (800, 600)             │
  │   サイズ: 700 x 450 ピクセル                 │
  │   点数: 15,823 点                            │
  │   密度: 91%                                  │
  │   配置: 左中部                               │
  │   形状: 矩形                                 │
  └──────────────────────────────────────────────┘

=============================================================
フレーム 30 (1.00秒)
=============================================================
検出領域数: 3

領域の変化:
  領域 #00: 位置変化なし（静止）
  領域 #01: (100, 150) → (100, 155) [↓ 5px]
  領域 #02: 新規出現 (900, 400)

=============================================================
シミュレーション記憶
=============================================================
3個の領域パターンをシミュレーションで記憶しました

記憶 #0:
  点配置: 横長矩形パターン
  振る舞い: 静止

記憶 #1:
  点配置: 矩形パターン
  振る舞い: 緩やかな下方移動

記憶 #2:
  点配置: 矩形パターン
  振る舞い: 出現
```

## 次のステップ

1. `point_density_detector.py` - 点密度ベース領域検出
2. `visual_output_formatter.py` - 視覚的出力フォーマッター
3. `simulation_memory.py` - シミュレーションベース記憶
4. `point_recognition_processors.py` - 点認識用プロセッサ
5. `run_point_recognition.py` - 点ベース認識ランナー
6. 動画解析との統合
