#!/usr/bin/env python3
"""
Multi-Layer Cross Structure Conversion
多層Cross構造による高密度画像認識

画像を5層のCross構造に変換し、6軸で相互接続することで
情報密度を飛躍的に向上させる。

Layer 0: Pixel Layer (200,000点) - 超高密度画素レベル
Layer 1: Feature Layer (50,000点) - エッジ・テクスチャ特徴
Layer 2: Pattern Layer (10,000点) - 基本形状・パターン
Layer 3: Semantic Layer (1,000点) - 意味・オブジェクト
Layer 4: Concept Layer (100点) - 抽象概念・シーン
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import json
from datetime import datetime

try:
    from PIL import Image
    import numpy as np
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


@dataclass
class MultiLayerCrossPoint:
    """多層Cross構造の点"""
    x: float  # RIGHT/LEFT axis
    y: float  # UP/DOWN axis
    z: float  # FRONT/BACK axis
    layer: int  # どの層に属するか

    # 各軸の値
    front: float = 0.0
    back: float = 0.0
    up: float = 0.0
    down: float = 0.0
    right: float = 0.0
    left: float = 0.0

    # 追加属性
    intensity: float = 0.0
    color: Optional[Tuple[int, int, int]] = None
    gradient_x: float = 0.0
    gradient_y: float = 0.0
    local_variance: float = 0.0

    # 接続情報
    layer_connections: Dict[str, List[int]] = field(default_factory=dict)  # 層間接続
    intra_connections: Dict[str, List[int]] = field(default_factory=dict)  # 層内接続


@dataclass
class CrossLayer:
    """Cross構造の1層"""
    layer_id: int
    name: str
    points: List[MultiLayerCrossPoint]
    axis_statistics: Dict[str, Dict[str, float]]  # 各軸の統計情報
    description: str


class MultiLayerCrossConverter:
    """
    画像を多層Cross構造に変換

    5層のCross構造を生成し、6軸で相互接続する
    """

    # 各層の設定
    LAYER_CONFIGS = [
        {
            "id": 0,
            "name": "Pixel Layer",
            "max_points": 200000,
            "extraction_method": "dense_grid",
            "description": "超高密度画素レベル（全画素）"
        },
        {
            "id": 1,
            "name": "Feature Layer",
            "max_points": 50000,
            "extraction_method": "edge_and_texture",
            "description": "エッジ・テクスチャ特徴"
        },
        {
            "id": 2,
            "name": "Pattern Layer",
            "max_points": 10000,
            "extraction_method": "shape_patterns",
            "description": "基本形状・パターン"
        },
        {
            "id": 3,
            "name": "Semantic Layer",
            "max_points": 1000,
            "extraction_method": "semantic_regions",
            "description": "意味・オブジェクト"
        },
        {
            "id": 4,
            "name": "Concept Layer",
            "max_points": 100,
            "extraction_method": "concept_clustering",
            "description": "抽象概念・シーン"
        }
    ]

    def __init__(self, quality: str = "ultra_high"):
        """
        Initialize multi-layer converter

        Args:
            quality: Quality preset
                - 'standard': 通常品質
                - 'high': 高品質
                - 'ultra_high': 超高品質（デフォルト）
        """
        if not VISION_AVAILABLE:
            raise ImportError(
                "Vision support not available. Install with: pip install pillow numpy"
            )

        self.quality = quality

        # 品質に応じて最大点数を調整
        if quality == "standard":
            self._scale_layer_configs(0.5)
        elif quality == "high":
            self._scale_layer_configs(0.75)
        # ultra_highはそのまま

    def _scale_layer_configs(self, scale: float):
        """層設定をスケーリング"""
        for config in self.LAYER_CONFIGS:
            config["max_points"] = int(config["max_points"] * scale)

    def convert(self, image_input) -> Dict[str, Any]:
        """
        画像を多層Cross構造に変換

        Args:
            image_input: 画像ファイルパス（Path）またはPIL Image

        Returns:
            多層Cross構造
        """
        # 入力がPathかImageかを判定
        if isinstance(image_input, Path):
            print(f"\n🎨 画像を多層Cross構造に変換中: {image_input.name}")
            print("=" * 60)
            img = Image.open(image_input)
        else:
            # PIL Imageとして扱う
            print(f"\n🎨 画像を多層Cross構造に変換中")
            print("=" * 60)
            img = image_input

        if img.mode != 'RGB':
            img = img.convert('RGB')

        img_array = np.array(img)
        height, width = img_array.shape[:2]

        print(f"画像サイズ: {width}x{height}")
        print(f"品質設定: {self.quality}")
        print()

        # 各層を生成
        layers = []

        for layer_config in self.LAYER_CONFIGS:
            print(f"Layer {layer_config['id']}: {layer_config['name']}")
            print(f"  最大点数: {layer_config['max_points']:,}")

            layer = self._create_layer(
                layer_config=layer_config,
                img_array=img_array,
                previous_layer=layers[-1] if layers else None
            )

            layers.append(layer)
            print(f"  ✅ {len(layer.points):,} 点を生成")
            print()

        # 層間接続を確立（軽量版：上位2層のみ）
        print("🔗 層間接続を確立中（上位層のみ）...")
        self._establish_inter_layer_connections_fast(layers)
        print("  ✅ 層間接続完了")
        print()

        # 層内接続はスキップ（大幅な高速化のため）
        # print("🔗 層内接続を確立中...")
        # self._establish_intra_layer_connections(layers)
        # print("  ✅ 層内接続完了")
        # print()

        # 多層Cross構造を生成
        # image_pathが文字列の場合の処理
        if isinstance(image_input, Path):
            image_name = image_input.name
        else:
            image_name = "camera_frame"

        multi_layer_structure = self._generate_structure(
            image_path=image_name,
            image_size=(width, height),
            layers=layers
        )

        print("=" * 60)
        total_points = sum(len(layer.points) for layer in layers)
        print(f"✅ 変換完了: 総点数 {total_points:,} 点、5層")
        print()

        return multi_layer_structure

    def _create_layer(
        self,
        layer_config: Dict[str, Any],
        img_array: np.ndarray,
        previous_layer: Optional[CrossLayer]
    ) -> CrossLayer:
        """層を作成"""
        layer_id = layer_config["id"]
        method = layer_config["extraction_method"]
        max_points = layer_config["max_points"]

        # 抽出方法に応じて点を生成
        if method == "dense_grid":
            points = self._extract_dense_grid(img_array, max_points, layer_id)
        elif method == "edge_and_texture":
            points = self._extract_features(img_array, max_points, layer_id)
        elif method == "shape_patterns":
            points = self._extract_patterns(img_array, previous_layer, max_points, layer_id)
        elif method == "semantic_regions":
            points = self._extract_semantic(img_array, previous_layer, max_points, layer_id)
        elif method == "concept_clustering":
            points = self._extract_concepts(img_array, previous_layer, max_points, layer_id)
        else:
            points = []

        # 各軸の統計を計算
        axis_stats = self._calculate_axis_statistics(points)

        return CrossLayer(
            layer_id=layer_id,
            name=layer_config["name"],
            points=points,
            axis_statistics=axis_stats,
            description=layer_config["description"]
        )

    def _extract_dense_grid(
        self,
        img_array: np.ndarray,
        max_points: int,
        layer_id: int
    ) -> List[MultiLayerCrossPoint]:
        """Layer 0: 超高密度グリッドサンプリング"""
        height, width = img_array.shape[:2]
        gray = np.mean(img_array, axis=2).astype(np.uint8)

        # 勾配計算
        gradient_y = np.abs(np.diff(gray, axis=0, prepend=0))
        gradient_x = np.abs(np.diff(gray, axis=1, prepend=0))

        # グリッドステップを計算
        total_pixels = height * width
        if total_pixels <= max_points:
            step = 1
        else:
            step = int(np.sqrt(total_pixels / max_points))

        points = []

        for y in range(0, height, step):
            for x in range(0, width, step):
                if len(points) >= max_points:
                    break

                # 正規化座標 [-1, 1]
                norm_x = (x / width) * 2 - 1
                norm_y = (y / height) * 2 - 1

                # 明度 → Z軸
                intensity = gray[y, x] / 255.0
                norm_z = intensity * 2 - 1

                # 色情報
                color = tuple(img_array[y, x])
                r, g, b = [c / 255.0 for c in color]

                # 局所分散（テクスチャ）
                window_size = 3
                y1 = max(0, y - window_size)
                y2 = min(height, y + window_size + 1)
                x1 = max(0, x - window_size)
                x2 = min(width, x + window_size + 1)
                local_variance = float(np.var(gray[y1:y2, x1:x2]))

                # 6軸の値を計算
                point = MultiLayerCrossPoint(
                    x=norm_x,
                    y=norm_y,
                    z=norm_z,
                    layer=layer_id,
                    front=r,  # 赤成分
                    back=b,   # 青成分
                    up=norm_y if norm_y > 0 else 0,
                    down=-norm_y if norm_y < 0 else 0,
                    right=norm_x if norm_x > 0 else 0,
                    left=-norm_x if norm_x < 0 else 0,
                    intensity=intensity,
                    color=color,
                    gradient_x=float(gradient_x[y, x]) / 255.0,
                    gradient_y=float(gradient_y[y, x]) / 255.0,
                    local_variance=local_variance / 255.0
                )

                points.append(point)

            if len(points) >= max_points:
                break

        return points[:max_points]

    def _extract_features(
        self,
        img_array: np.ndarray,
        max_points: int,
        layer_id: int
    ) -> List[MultiLayerCrossPoint]:
        """Layer 1: エッジ・テクスチャ特徴抽出"""
        height, width = img_array.shape[:2]
        gray = np.mean(img_array, axis=2).astype(np.uint8)

        # エッジ検出
        edges_y = np.abs(np.diff(gray, axis=0, prepend=0))
        edges_x = np.abs(np.diff(gray, axis=1, prepend=0))
        edge_magnitude = np.sqrt(edges_x**2 + edges_y**2)

        # 高エッジ点を抽出（70%）
        edge_threshold = np.percentile(edge_magnitude, 85)
        edge_points_coords = np.argwhere(edge_magnitude > edge_threshold)

        # ランダムサンプリング（エッジ点が多すぎる場合）
        num_edge_points = min(int(max_points * 0.7), len(edge_points_coords))
        if len(edge_points_coords) > num_edge_points:
            indices = np.random.choice(len(edge_points_coords), num_edge_points, replace=False)
            edge_points_coords = edge_points_coords[indices]

        points = []

        # エッジ点を追加
        for y, x in edge_points_coords:
            norm_x = (x / width) * 2 - 1
            norm_y = (y / height) * 2 - 1
            intensity = gray[y, x] / 255.0
            norm_z = intensity * 2 - 1

            color = tuple(img_array[y, x])
            edge_strength = edge_magnitude[y, x] / 255.0

            point = MultiLayerCrossPoint(
                x=norm_x,
                y=norm_y,
                z=norm_z,
                layer=layer_id,
                front=edge_strength,  # エッジ強度
                back=1.0 - edge_strength,
                up=float(edges_y[y, x]) / 255.0,  # 垂直エッジ
                down=1.0 - float(edges_y[y, x]) / 255.0,
                right=float(edges_x[y, x]) / 255.0,  # 水平エッジ
                left=1.0 - float(edges_x[y, x]) / 255.0,
                intensity=intensity,
                color=color,
                gradient_x=float(edges_x[y, x]) / 255.0,
                gradient_y=float(edges_y[y, x]) / 255.0
            )

            points.append(point)

        # テクスチャ点を追加（30%）
        remaining = max_points - len(points)
        if remaining > 0:
            # テクスチャ分散が高い領域をサンプリング
            texture_map = np.zeros_like(gray, dtype=float)
            window = 5

            for y in range(window, height - window, 3):
                for x in range(window, width - window, 3):
                    variance = np.var(gray[y-window:y+window+1, x-window:x+window+1])
                    texture_map[y, x] = variance

            # Check if there's any texture
            texture_values = texture_map[texture_map > 0]
            if len(texture_values) > 0:
                texture_threshold = np.percentile(texture_values, 70)
                texture_coords = np.argwhere(texture_map > texture_threshold)
            else:
                # No texture - use regular grid
                texture_coords = np.array([])

            num_texture = min(remaining, len(texture_coords))
            if len(texture_coords) > num_texture:
                indices = np.random.choice(len(texture_coords), num_texture, replace=False)
                texture_coords = texture_coords[indices]

            for y, x in texture_coords:
                norm_x = (x / width) * 2 - 1
                norm_y = (y / height) * 2 - 1
                intensity = gray[y, x] / 255.0
                norm_z = intensity * 2 - 1

                color = tuple(img_array[y, x])
                texture_strength = texture_map[y, x] / 255.0

                point = MultiLayerCrossPoint(
                    x=norm_x,
                    y=norm_y,
                    z=norm_z,
                    layer=layer_id,
                    front=texture_strength,
                    back=1.0 - texture_strength,
                    up=norm_y if norm_y > 0 else 0,
                    down=-norm_y if norm_y < 0 else 0,
                    right=norm_x if norm_x > 0 else 0,
                    left=-norm_x if norm_x < 0 else 0,
                    intensity=intensity,
                    color=color,
                    local_variance=texture_strength
                )

                points.append(point)

        return points[:max_points]

    def _extract_patterns(
        self,
        img_array: np.ndarray,
        previous_layer: Optional[CrossLayer],
        max_points: int,
        layer_id: int
    ) -> List[MultiLayerCrossPoint]:
        """Layer 2: パターン抽出（下位層からクラスタリング）"""
        if not previous_layer or not previous_layer.points:
            # フォールバック: 均等サンプリング
            return self._uniform_sampling(img_array, max_points, layer_id)

        # 下位層の点をクラスタリング
        prev_points = previous_layer.points

        # 空間的クラスタリング（グリッドベース）
        grid_size = int(np.sqrt(max_points))
        grid_width = 2.0 / grid_size  # [-1, 1] を分割
        grid_height = 2.0 / grid_size

        clusters = {}

        for point in prev_points:
            grid_x = int((point.x + 1) / grid_width)
            grid_y = int((point.y + 1) / grid_height)
            grid_key = (grid_x, grid_y)

            if grid_key not in clusters:
                clusters[grid_key] = []
            clusters[grid_key].append(point)

        # 各クラスタの代表点を作成
        pattern_points = []

        for grid_key, cluster in clusters.items():
            if not cluster:
                continue

            # クラスタ中心を計算
            center_x = np.mean([p.x for p in cluster])
            center_y = np.mean([p.y for p in cluster])
            center_z = np.mean([p.z for p in cluster])

            # 6軸の平均
            avg_front = np.mean([p.front for p in cluster])
            avg_back = np.mean([p.back for p in cluster])
            avg_up = np.mean([p.up for p in cluster])
            avg_down = np.mean([p.down for p in cluster])
            avg_right = np.mean([p.right for p in cluster])
            avg_left = np.mean([p.left for p in cluster])

            avg_intensity = np.mean([p.intensity for p in cluster])

            # パターン点を作成
            pattern_point = MultiLayerCrossPoint(
                x=center_x,
                y=center_y,
                z=center_z,
                layer=layer_id,
                front=avg_front,
                back=avg_back,
                up=avg_up,
                down=avg_down,
                right=avg_right,
                left=avg_left,
                intensity=avg_intensity
            )

            pattern_points.append(pattern_point)

        return pattern_points[:max_points]

    def _extract_semantic(
        self,
        img_array: np.ndarray,
        previous_layer: Optional[CrossLayer],
        max_points: int,
        layer_id: int
    ) -> List[MultiLayerCrossPoint]:
        """Layer 3: 意味的領域抽出（さらに抽象化）"""
        if not previous_layer or not previous_layer.points:
            return self._uniform_sampling(img_array, max_points, layer_id)

        # Layer 2から更に集約
        prev_points = previous_layer.points

        # より大きなグリッドでクラスタリング
        grid_size = int(np.sqrt(max_points * 2))
        grid_width = 2.0 / grid_size
        grid_height = 2.0 / grid_size

        clusters = {}

        for point in prev_points:
            grid_x = int((point.x + 1) / grid_width)
            grid_y = int((point.y + 1) / grid_height)
            grid_key = (grid_x, grid_y)

            if grid_key not in clusters:
                clusters[grid_key] = []
            clusters[grid_key].append(point)

        # 意味的領域点を作成
        semantic_points = []

        for cluster in clusters.values():
            if not cluster or len(cluster) < 2:
                continue

            center_x = np.mean([p.x for p in cluster])
            center_y = np.mean([p.y for p in cluster])
            center_z = np.mean([p.z for p in cluster])

            # 6軸の統計
            avg_front = np.mean([p.front for p in cluster])
            avg_back = np.mean([p.back for p in cluster])
            avg_up = np.mean([p.up for p in cluster])
            avg_down = np.mean([p.down for p in cluster])
            avg_right = np.mean([p.right for p in cluster])
            avg_left = np.mean([p.left for p in cluster])

            avg_intensity = np.mean([p.intensity for p in cluster])

            point = MultiLayerCrossPoint(
                x=center_x,
                y=center_y,
                z=center_z,
                layer=layer_id,
                front=avg_front,
                back=avg_back,
                up=avg_up,
                down=avg_down,
                right=avg_right,
                left=avg_left,
                intensity=avg_intensity
            )

            semantic_points.append(point)

        return semantic_points[:max_points]

    def _extract_concepts(
        self,
        img_array: np.ndarray,
        previous_layer: Optional[CrossLayer],
        max_points: int,
        layer_id: int
    ) -> List[MultiLayerCrossPoint]:
        """Layer 4: 概念抽出（最高レベルの抽象化）"""
        if not previous_layer or not previous_layer.points:
            return self._uniform_sampling(img_array, max_points, layer_id)

        prev_points = previous_layer.points

        # 最も粗いグリッドでクラスタリング
        grid_size = int(np.sqrt(max_points * 3))
        grid_width = 2.0 / grid_size
        grid_height = 2.0 / grid_size

        clusters = {}

        for point in prev_points:
            grid_x = int((point.x + 1) / grid_width)
            grid_y = int((point.y + 1) / grid_height)
            grid_key = (grid_x, grid_y)

            if grid_key not in clusters:
                clusters[grid_key] = []
            clusters[grid_key].append(point)

        # 概念点を作成
        concept_points = []

        for cluster in clusters.values():
            if not cluster or len(cluster) < 3:
                continue

            center_x = np.mean([p.x for p in cluster])
            center_y = np.mean([p.y for p in cluster])
            center_z = np.mean([p.z for p in cluster])

            avg_front = np.mean([p.front for p in cluster])
            avg_back = np.mean([p.back for p in cluster])
            avg_up = np.mean([p.up for p in cluster])
            avg_down = np.mean([p.down for p in cluster])
            avg_right = np.mean([p.right for p in cluster])
            avg_left = np.mean([p.left for p in cluster])

            avg_intensity = np.mean([p.intensity for p in cluster])

            point = MultiLayerCrossPoint(
                x=center_x,
                y=center_y,
                z=center_z,
                layer=layer_id,
                front=avg_front,
                back=avg_back,
                up=avg_up,
                down=avg_down,
                right=avg_right,
                left=avg_left,
                intensity=avg_intensity
            )

            concept_points.append(point)

        return concept_points[:max_points]

    def _uniform_sampling(
        self,
        img_array: np.ndarray,
        max_points: int,
        layer_id: int
    ) -> List[MultiLayerCrossPoint]:
        """フォールバック: 均等サンプリング"""
        height, width = img_array.shape[:2]
        gray = np.mean(img_array, axis=2)

        step = int(np.sqrt(height * width / max_points))
        points = []

        for y in range(0, height, step):
            for x in range(0, width, step):
                if len(points) >= max_points:
                    break

                norm_x = (x / width) * 2 - 1
                norm_y = (y / height) * 2 - 1
                intensity = gray[y, x] / 255.0
                norm_z = intensity * 2 - 1

                point = MultiLayerCrossPoint(
                    x=norm_x,
                    y=norm_y,
                    z=norm_z,
                    layer=layer_id,
                    intensity=intensity
                )

                points.append(point)

            if len(points) >= max_points:
                break

        return points[:max_points]

    def _establish_inter_layer_connections_fast(self, layers: List[CrossLayer]):
        """層間接続を確立（高速版：上位2層のみ）"""
        # Layer 0とLayer 1は点数が多すぎるのでスキップ
        # Layer 2, 3, 4のみ接続を確立
        for i in range(2, len(layers) - 1):
            upper_layer = layers[i + 1]
            lower_layer = layers[i]

            print(f"  Layer {upper_layer.layer_id} → Layer {lower_layer.layer_id}")

            # 上位層の各点を下位層の点に接続（k=5に削減）
            for upper_point in upper_layer.points:
                connections = self._find_layer_connections_fast(
                    upper_point,
                    lower_layer.points,
                    k=5
                )
                upper_point.layer_connections = connections

    def _find_layer_connections_fast(
        self,
        point: MultiLayerCrossPoint,
        lower_points: List[MultiLayerCrossPoint],
        k: int
    ) -> Dict[str, List[int]]:
        """層間の6軸接続を探索（高速版）"""
        connections = {
            "FRONT": [],
            "BACK": [],
            "UP": [],
            "DOWN": [],
            "RIGHT": [],
            "LEFT": []
        }

        # サンプリング：点数が多い場合は間引く
        if len(lower_points) > 1000:
            step = len(lower_points) // 1000
            sampled_points = [(i, lower_points[i]) for i in range(0, len(lower_points), step)]
        else:
            sampled_points = [(i, p) for i, p in enumerate(lower_points)]

        # 距離を計算（サンプリング済み）
        distances = []
        for i, lp in sampled_points:
            dist = np.sqrt(
                (lp.x - point.x)**2 +
                (lp.y - point.y)**2 +
                (lp.z - point.z)**2
            )
            distances.append((i, dist, lp))

        # 近い順にソート
        distances.sort(key=lambda x: x[1])

        # 上位k個を6軸に分類
        for i, dist, lp in distances[:k]:
            dx = lp.x - point.x
            dy = lp.y - point.y
            dz = lp.z - point.z

            # Z軸（FRONT/BACK）
            if dz > 0:
                connections["FRONT"].append(i)
            else:
                connections["BACK"].append(i)

            # Y軸（UP/DOWN）
            if dy > 0.05:
                connections["UP"].append(i)
            elif dy < -0.05:
                connections["DOWN"].append(i)

            # X軸（RIGHT/LEFT）
            if dx > 0.05:
                connections["RIGHT"].append(i)
            elif dx < -0.05:
                connections["LEFT"].append(i)

        return connections

    def _establish_inter_layer_connections(self, layers: List[CrossLayer]):
        """層間接続を確立（旧版・非推奨）"""
        for i in range(len(layers) - 1):
            upper_layer = layers[i + 1]
            lower_layer = layers[i]

            # 上位層の各点を下位層の点に接続
            for upper_point in upper_layer.points:
                # 空間的に近い下位層の点を探索（k=10）
                connections = self._find_layer_connections(
                    upper_point,
                    lower_layer.points,
                    k=10
                )

                upper_point.layer_connections = connections

    def _find_layer_connections(
        self,
        point: MultiLayerCrossPoint,
        lower_points: List[MultiLayerCrossPoint],
        k: int
    ) -> Dict[str, List[int]]:
        """層間の6軸接続を探索"""
        connections = {
            "FRONT": [],
            "BACK": [],
            "UP": [],
            "DOWN": [],
            "RIGHT": [],
            "LEFT": []
        }

        # 距離を計算
        distances = []
        for i, lp in enumerate(lower_points):
            dist = np.sqrt(
                (lp.x - point.x)**2 +
                (lp.y - point.y)**2 +
                (lp.z - point.z)**2
            )
            distances.append((i, dist, lp))

        # 近い順にソート
        distances.sort(key=lambda x: x[1])

        # 上位k個を6軸に分類
        for i, dist, lp in distances[:k]:
            dx = lp.x - point.x
            dy = lp.y - point.y
            dz = lp.z - point.z

            # Z軸（FRONT/BACK）
            if dz > 0:
                connections["FRONT"].append(i)
            else:
                connections["BACK"].append(i)

            # Y軸（UP/DOWN）
            if dy > 0.05:
                connections["UP"].append(i)
            elif dy < -0.05:
                connections["DOWN"].append(i)

            # X軸（RIGHT/LEFT）
            if dx > 0.05:
                connections["RIGHT"].append(i)
            elif dx < -0.05:
                connections["LEFT"].append(i)

        return connections

    def _establish_intra_layer_connections(self, layers: List[CrossLayer]):
        """層内接続を確立"""
        for layer in layers:
            for point in layer.points:
                # 同一層内の近傍点を6軸方向に探索
                connections = self._find_intra_connections(
                    point,
                    layer.points,
                    k=6
                )

                point.intra_connections = connections

    def _find_intra_connections(
        self,
        point: MultiLayerCrossPoint,
        all_points: List[MultiLayerCrossPoint],
        k: int
    ) -> Dict[str, List[int]]:
        """層内の6軸接続を探索"""
        connections = {
            "FRONT": [],
            "BACK": [],
            "UP": [],
            "DOWN": [],
            "RIGHT": [],
            "LEFT": []
        }

        # 各軸方向でk個の最近傍を探索
        for axis_name in connections.keys():
            nearest = self._find_k_nearest_in_axis(
                point, all_points, axis_name, k
            )
            connections[axis_name] = nearest

        return connections

    def _find_k_nearest_in_axis(
        self,
        point: MultiLayerCrossPoint,
        all_points: List[MultiLayerCrossPoint],
        axis: str,
        k: int
    ) -> List[int]:
        """特定軸方向のk最近傍を探索"""
        candidates = []

        for i, other in enumerate(all_points):
            if other is point:
                continue

            dx = other.x - point.x
            dy = other.y - point.y
            dz = other.z - point.z

            # 軸方向のチェック
            is_in_direction = False

            if axis == "FRONT" and dz > 0:
                is_in_direction = True
            elif axis == "BACK" and dz < 0:
                is_in_direction = True
            elif axis == "UP" and dy > 0:
                is_in_direction = True
            elif axis == "DOWN" and dy < 0:
                is_in_direction = True
            elif axis == "RIGHT" and dx > 0:
                is_in_direction = True
            elif axis == "LEFT" and dx < 0:
                is_in_direction = True

            if is_in_direction:
                dist = np.sqrt(dx**2 + dy**2 + dz**2)
                candidates.append((i, dist))

        # 距離でソート
        candidates.sort(key=lambda x: x[1])

        return [i for i, _ in candidates[:k]]

    def _calculate_axis_statistics(
        self,
        points: List[MultiLayerCrossPoint]
    ) -> Dict[str, Dict[str, float]]:
        """各軸の統計を計算"""
        if not points:
            return {}

        stats = {}

        for axis_name in ["FRONT", "BACK", "UP", "DOWN", "RIGHT", "LEFT"]:
            values = [getattr(p, axis_name.lower()) for p in points]

            stats[axis_name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "median": float(np.median(values))
            }

        return stats

    def _generate_structure(
        self,
        image_path: Path,
        image_size: Tuple[int, int],
        layers: List[CrossLayer]
    ) -> Dict[str, Any]:
        """多層Cross構造を生成"""
        width, height = image_size

        total_points = sum(len(layer.points) for layer in layers)
        total_connections = sum(
            sum(len(conns) for conns in point.layer_connections.values())
            for layer in layers
            for point in layer.points
        )

        structure = {
            "type": "multi_layer_cross",
            "source": str(image_path),
            "timestamp": datetime.now().isoformat(),

            "metadata": {
                "original_size": {"width": width, "height": height},
                "num_layers": len(layers),
                "total_points": total_points,
                "total_connections": total_connections,
                "quality": self.quality
            },

            "layers": [
                {
                    "id": layer.layer_id,
                    "name": layer.name,
                    "description": layer.description,
                    "num_points": len(layer.points),
                    "axis_statistics": layer.axis_statistics
                }
                for layer in layers
            ],

            "summary": self._generate_summary(layers, total_points)
        }

        return structure

    def _generate_summary(self, layers: List[CrossLayer], total_points: int) -> str:
        """サマリーを生成"""
        summary_lines = [
            f"Multi-Layer Cross Structure",
            f"Total Points: {total_points:,}",
            f"Layers: {len(layers)}",
            ""
        ]

        for layer in layers:
            summary_lines.append(
                f"  Layer {layer.layer_id} ({layer.name}): "
                f"{len(layer.points):,} points"
            )

        return "\n".join(summary_lines)


def convert_image_to_multi_layer_cross(
    image_path: Path,
    output_path: Optional[Path] = None,
    quality: str = "ultra_high"
) -> Dict[str, Any]:
    """
    便利関数: 画像を多層Cross構造に変換

    Args:
        image_path: 画像ファイルパス
        output_path: 出力パス（オプション）
        quality: 品質（'standard', 'high', 'ultra_high'）

    Returns:
        多層Cross構造
    """
    converter = MultiLayerCrossConverter(quality=quality)
    structure = converter.convert(image_path)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(structure, f, indent=2, ensure_ascii=False)

    return structure
