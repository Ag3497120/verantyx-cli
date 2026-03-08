"""
Vision Processors for JCross
Cross形状認識のためのプロセッサ群
"""

import numpy as np
from typing import Dict, Any, List, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CrossPointMapper:
    """
    画像をCross点群にマッピング
    """

    def __init__(self):
        pass

    def map_to_points(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        画像データ → Cross点群

        Args:
            args: {
                "image_data": ndarray or PIL Image,
                "threshold": int (default: 50)
            }

        Returns:
            {
                "points": List[Dict],  # 各点の情報
                "point_count": int
            }
        """
        try:
            image_data = args.get("image_data")
            threshold = args.get("threshold", 50)

            # PIL ImageをNumPy配列に変換
            if hasattr(image_data, "mode"):  # PIL Image
                image_array = np.array(image_data)
            else:
                image_array = image_data

            height, width = image_array.shape[:2]
            points = []

            # 各ピクセルを点として処理
            for y in range(height):
                for x in range(width):
                    pixel = image_array[y, x]

                    # 輝度が閾値以上なら点として記録
                    intensity = np.mean(pixel[:3]) if len(pixel.shape) > 1 else pixel

                    if intensity > threshold:
                        # 正規化座標 (0-1)
                        norm_x = x / width
                        norm_y = 1 - (y / height)  # Y軸反転
                        norm_z = 0  # 2D画像

                        # Cross 6軸計測は後で行う
                        points.append({
                            "position": [norm_x, norm_y, norm_z],
                            "color": pixel.tolist() if hasattr(pixel, "tolist") else [int(pixel)] * 3,
                            "original_xy": [x, y]
                        })

            return {
                "points": points,
                "point_count": len(points)
            }

        except Exception as e:
            logger.error(f"map_to_points failed: {e}")
            return {"points": [], "point_count": 0}


class CrossMetricsCalculator:
    """
    点のCross 6軸座標を計測
    """

    def __init__(self):
        pass

    def calculate_metrics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        3D座標 → Cross 6軸計測値

        Args:
            args: {
                "point": Dict with "position": [x, y, z]
            }

        Returns:
            {
                "FRONT": float,
                "BACK": float,
                "UP": float,
                "DOWN": float,
                "RIGHT": float,
                "LEFT": float
            }
        """
        try:
            # VM変数から点を取得
            vm_vars = args.get("__vm_vars__", {})
            point = vm_vars.get("point", args.get("point", {}))

            position = point.get("position", [0.5, 0.5, 0])
            x, y, z = position

            # Cross 6軸計測
            cross_metrics = {
                "FRONT": max(0.0, min(1.0, z + 0.5)),   # Z軸前方
                "BACK": max(0.0, min(1.0, 0.5 - z)),    # Z軸後方
                "UP": float(y),                          # Y軸上方
                "DOWN": float(1 - y),                    # Y軸下方
                "RIGHT": float(x),                       # X軸右方
                "LEFT": float(1 - x)                     # X軸左方
            }

            return cross_metrics

        except Exception as e:
            logger.error(f"calculate_metrics failed: {e}")
            return {
                "FRONT": 0.0, "BACK": 0.0,
                "UP": 0.0, "DOWN": 0.0,
                "RIGHT": 0.0, "LEFT": 0.0
            }


class CrossDistributionAnalyzer:
    """
    点群のCross軸分布を解析
    """

    def __init__(self):
        pass

    def measure_axis_distribution(self, args: Dict[str, Any], axis: str) -> Dict[str, Any]:
        """
        指定軸の分布を計測

        Args:
            args: {"points": List[Dict]}
            axis: "UP" | "DOWN" | "RIGHT" | "LEFT"

        Returns:
            {
                "mean": float,
                "std": float,
                "concentration": str
            }
        """
        try:
            vm_vars = args.get("__vm_vars__", {})
            points = vm_vars.get("points", args.get("points", []))

            if not points:
                return {"mean": 0.0, "std": 0.0, "concentration": "none"}

            # 各点の指定軸値を取得
            axis_values = []
            for point in points:
                cross = point.get("cross", {})
                value = cross.get(axis, 0.0)
                axis_values.append(value)

            # 統計計算
            mean = np.mean(axis_values)
            std = np.std(axis_values)

            # 集中度判定
            if std < 0.1:
                concentration = "highly_concentrated"
            elif std < 0.3:
                concentration = "concentrated"
            else:
                concentration = "distributed"

            return {
                "mean": float(mean),
                "std": float(std),
                "concentration": concentration
            }

        except Exception as e:
            logger.error(f"measure_axis_distribution failed: {e}")
            return {"mean": 0.0, "std": 0.0, "concentration": "error"}

    def measure_up_axis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.measure_axis_distribution(args, "UP")

    def measure_down_axis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.measure_axis_distribution(args, "DOWN")

    def measure_right_axis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.measure_axis_distribution(args, "RIGHT")

    def measure_left_axis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.measure_axis_distribution(args, "LEFT")

    def check_symmetry(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross軸での対称性チェック

        Returns:
            {
                "left_right": bool,
                "up_down": bool
            }
        """
        try:
            vm_vars = args.get("__vm_vars__", {})
            points = vm_vars.get("points", args.get("points", []))

            if not points:
                return {"left_right": False, "up_down": False}

            # 左右対称性
            left_points = [p for p in points if p.get("cross", {}).get("LEFT", 0) > 0.5]
            right_points = [p for p in points if p.get("cross", {}).get("RIGHT", 0) > 0.5]
            lr_symmetric = abs(len(left_points) - len(right_points)) < len(points) * 0.1

            # 上下対称性
            up_points = [p for p in points if p.get("cross", {}).get("UP", 0) > 0.5]
            down_points = [p for p in points if p.get("cross", {}).get("DOWN", 0) > 0.5]
            ud_symmetric = abs(len(up_points) - len(down_points)) < len(points) * 0.1

            return {
                "left_right": lr_symmetric,
                "up_down": ud_symmetric
            }

        except Exception as e:
            logger.error(f"check_symmetry failed: {e}")
            return {"left_right": False, "up_down": False}


class ShapeMemoryBank:
    """
    形状の断片記憶
    """

    def __init__(self):
        self.memory = {}
        self.initialize_basic_shapes()

    def initialize_basic_shapes(self):
        """基本形状を登録"""
        self.memory = {
            "horizontal_line": {
                "signature": {
                    "UP": {"concentration": "highly_concentrated"},
                    "RIGHT": {"concentration": "distributed"},
                    "symmetry": {"left_right": True}
                },
                "label": "horizontal_line"
            },
            "vertical_line": {
                "signature": {
                    "RIGHT": {"concentration": "highly_concentrated"},
                    "UP": {"concentration": "distributed"},
                    "symmetry": {"up_down": True}
                },
                "label": "vertical_line"
            },
            "rectangle": {
                "signature": {
                    "symmetry": {"left_right": True, "up_down": True},
                    "UP": {"concentration": "concentrated"},
                    "RIGHT": {"concentration": "concentrated"}
                },
                "label": "rectangle"
            },
            "circle": {
                "signature": {
                    "symmetry": {"left_right": True, "up_down": True},
                    "UP": {"concentration": "concentrated"},
                    "RIGHT": {"concentration": "concentrated"},
                    "DOWN": {"concentration": "concentrated"},
                    "LEFT": {"concentration": "concentrated"}
                },
                "label": "circle"
            }
        }

    def init_basic_shapes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """JCrossから呼び出される初期化"""
        self.initialize_basic_shapes()
        return {"shapes_loaded": len(self.memory)}

    def recognize(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross分布パターンから形状を認識

        Args:
            args: {"cross_pattern": Dict}

        Returns:
            {"shape": str, "confidence": float}
        """
        try:
            vm_vars = args.get("__vm_vars__", {})
            cross_pattern = vm_vars.get("cross_pattern", args.get("cross_pattern", {}))

            best_match = "unknown"
            best_score = 0.0

            for shape_name, shape_data in self.memory.items():
                score = self._calculate_similarity(cross_pattern, shape_data["signature"])

                if score > best_score:
                    best_score = score
                    best_match = shape_data["label"]

            return {
                "shape": best_match,
                "confidence": best_score
            }

        except Exception as e:
            logger.error(f"recognize failed: {e}")
            return {"shape": "unknown", "confidence": 0.0}

    def _calculate_similarity(self, pattern: Dict, signature: Dict) -> float:
        """パターンとシグネチャの類似度"""
        score = 0.0
        total_checks = 0

        # 対称性チェック
        pattern_sym = pattern.get("symmetry", {})
        sig_sym = signature.get("symmetry", {})

        if "left_right" in sig_sym:
            if pattern_sym.get("left_right") == sig_sym["left_right"]:
                score += 1
            total_checks += 1

        if "up_down" in sig_sym:
            if pattern_sym.get("up_down") == sig_sym["up_down"]:
                score += 1
            total_checks += 1

        # 各軸の分布チェック
        for axis in ["UP", "DOWN", "RIGHT", "LEFT"]:
            if axis in signature:
                pattern_dist = pattern.get(axis.lower(), {})
                sig_dist = signature[axis]

                pattern_conc = pattern_dist.get("concentration", "")
                sig_conc = sig_dist.get("concentration", "")

                if pattern_conc == sig_conc:
                    score += 1
                total_checks += 1

        return score / total_checks if total_checks > 0 else 0.0


def create_vision_processors() -> Dict[str, callable]:
    """
    視覚認識用プロセッサを作成

    Returns:
        プロセッサ辞書 {name: function}
    """
    point_mapper = CrossPointMapper()
    metrics_calc = CrossMetricsCalculator()
    dist_analyzer = CrossDistributionAnalyzer()
    shape_memory = ShapeMemoryBank()

    return {
        # 点マッピング
        "vision.map_to_points": point_mapper.map_to_points,

        # Cross計測
        "cross.calculate_metrics": metrics_calc.calculate_metrics,

        # 分布解析
        "cross.measure_up_axis": dist_analyzer.measure_up_axis,
        "cross.measure_down_axis": dist_analyzer.measure_down_axis,
        "cross.measure_right_axis": dist_analyzer.measure_right_axis,
        "cross.measure_left_axis": dist_analyzer.measure_left_axis,
        "cross.check_symmetry": dist_analyzer.check_symmetry,

        # 形状記憶
        "shape_memory.init_basic_shapes": shape_memory.init_basic_shapes,
        "shape_memory.recognize": shape_memory.recognize,
    }
