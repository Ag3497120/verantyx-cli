"""
Dynamic JCross Processors for Video Analysis
動画解析用の動的JCrossプロセッサ群（Pythonは入出力のみ）
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def extract_frames(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    動画からフレームを抽出（OpenCV使用）

    Args:
        args: {
            "path": str,
            "fps": int (default: 30),
            "max_frames": int (default: 900)
        }

    Returns:
        {
            "frames": List[ndarray],
            "frame_count": int,
            "original_fps": float,
            "duration": float
        }
    """
    try:
        # VM変数から取得
        vm_vars = args.get("__vm_vars__", {})
        path = vm_vars.get("video_path", args.get("path"))
        fps = args.get("fps", 30)
        max_frames = args.get("max_frames", 900)

        cap = cv2.VideoCapture(str(path))

        if not cap.isOpened():
            return {"frames": [], "frame_count": 0, "error": "Failed to open video"}

        # 動画情報
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / original_fps if original_fps > 0 else 0

        # フレーム抽出間隔
        frame_interval = max(1, int(original_fps / fps))

        frames = []
        frame_count = 0

        while len(frames) < max_frames:
            ret, frame = cap.read()

            if not ret:
                break

            if frame_count % frame_interval == 0:
                # BGR → RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)

            frame_count += 1

        cap.release()

        logger.info(f"Extracted {len(frames)} frames from {path}")

        return {
            "frames": frames,
            "frame_count": len(frames),
            "original_fps": original_fps,
            "duration": duration
        }

    except Exception as e:
        logger.error(f"extract_frames failed: {e}")
        return {"frames": [], "frame_count": 0, "error": str(e)}


def frame_to_grid(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    フレーム → ARC-AGI2グリッド（32x32、10色）

    Args:
        args: {
            "frame": ndarray,
            "size": int (default: 32)
        }

    Returns:
        {
            "grid": List[List[int]],  # 32x32の2D配列、各要素0-9
            "size": int
        }
    """
    try:
        # VM変数から取得
        vm_vars = args.get("__vm_vars__", {})
        frame = vm_vars.get("current_frame", args.get("frame"))
        size = args.get("size", 32)

        # ARC-AGI2の10色パレット
        palette = np.array([
            [0, 0, 0],         # 0: Black
            [0, 116, 217],     # 1: Blue
            [255, 65, 54],     # 2: Red
            [46, 204, 64],     # 3: Green
            [255, 220, 0],     # 4: Yellow
            [170, 170, 170],   # 5: Grey
            [240, 18, 190],    # 6: Magenta
            [255, 133, 27],    # 7: Orange
            [127, 219, 255],   # 8: Azure
            [135, 12, 37]      # 9: Maroon
        ])

        # リサイズ
        from PIL import Image
        pil_image = Image.fromarray(frame)
        pil_image = pil_image.resize((size, size), Image.Resampling.LANCZOS)
        resized = np.array(pil_image)

        # 10色に量子化
        grid = np.zeros((size, size), dtype=int)

        for i in range(size):
            for j in range(size):
                pixel = resized[i, j]

                # 最も近い色を見つける
                min_dist = float('inf')
                nearest_idx = 0

                for idx, color in enumerate(palette):
                    dist = np.linalg.norm(pixel - color)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_idx = idx

                grid[i, j] = nearest_idx

        return {
            "grid": grid.tolist(),
            "size": size
        }

    except Exception as e:
        logger.error(f"frame_to_grid failed: {e}")
        return {"grid": [], "size": 0, "error": str(e)}


def grid_to_cross(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    ARC-AGI2グリッド → Cross構造

    Args:
        args: {"grid": List[List[int]]}

    Returns:
        Cross構造辞書
    """
    try:
        vm_vars = args.get("__vm_vars__", {})
        grid = vm_vars.get("grid", args.get("grid"))

        if not grid:
            return {"error": "Empty grid"}

        grid_array = np.array(grid)
        size = grid_array.shape[0]

        # Cross構造を構築
        cross_structure = {
            "type": "arc_grid",
            "size": size,
            "grid": grid,
            "axes": {}
        }

        # 各軸の点分布を計算
        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT"]:
            cross_structure["axes"][axis_name] = {
                "points": [],
                "colors": []
            }

        # グリッドの各セルをCross軸にマッピング
        for i in range(size):
            for j in range(size):
                color = grid_array[i, j]

                if color > 0:  # 黒以外
                    # 正規化座標
                    norm_x = j / size
                    norm_y = 1 - (i / size)

                    # UP軸: 上部のピクセル
                    if norm_y > 0.5:
                        cross_structure["axes"]["UP"]["points"].append([norm_x, norm_y])
                        cross_structure["axes"]["UP"]["colors"].append(int(color))

                    # DOWN軸: 下部のピクセル
                    if norm_y <= 0.5:
                        cross_structure["axes"]["DOWN"]["points"].append([norm_x, norm_y])
                        cross_structure["axes"]["DOWN"]["colors"].append(int(color))

                    # RIGHT軸: 右部のピクセル
                    if norm_x > 0.5:
                        cross_structure["axes"]["RIGHT"]["points"].append([norm_x, norm_y])
                        cross_structure["axes"]["RIGHT"]["colors"].append(int(color))

                    # LEFT軸: 左部のピクセル
                    if norm_x <= 0.5:
                        cross_structure["axes"]["LEFT"]["points"].append([norm_x, norm_y])
                        cross_structure["axes"]["LEFT"]["colors"].append(int(color))

        return cross_structure

    except Exception as e:
        logger.error(f"grid_to_cross failed: {e}")
        return {"error": str(e)}


def calculate_diff(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    2つのCross構造の差分を計算

    Args:
        args: {
            "prev_frame": Dict (Cross構造),
            "current_frame": Dict (Cross構造)
        }

    Returns:
        {
            "has_changes": bool,
            "added_points": List,
            "removed_points": List,
            "moved_points": List,
            "color_changes": List
        }
    """
    try:
        vm_vars = args.get("__vm_vars__", {})
        prev = vm_vars.get("prev_frame", {})
        current = vm_vars.get("current_frame", {})

        # グリッドを比較
        prev_grid = np.array(prev.get("grid", []))
        current_grid = np.array(current.get("grid", []))

        if prev_grid.size == 0 or current_grid.size == 0:
            return {"has_changes": False}

        # 差分を検出
        diff_mask = (prev_grid != current_grid)
        has_changes = np.any(diff_mask)

        if not has_changes:
            return {"has_changes": False}

        # 変更箇所を分類
        added_points = []
        removed_points = []
        color_changes = []

        size = prev_grid.shape[0]

        for i in range(size):
            for j in range(size):
                if diff_mask[i, j]:
                    prev_color = int(prev_grid[i, j])
                    current_color = int(current_grid[i, j])

                    norm_x = j / size
                    norm_y = 1 - (i / size)

                    if prev_color == 0 and current_color > 0:
                        # 点追加
                        added_points.append({
                            "position": [norm_x, norm_y],
                            "color": current_color
                        })
                    elif prev_color > 0 and current_color == 0:
                        # 点削除
                        removed_points.append({
                            "position": [norm_x, norm_y],
                            "color": prev_color
                        })
                    else:
                        # 色変化
                        color_changes.append({
                            "position": [norm_x, norm_y],
                            "from_color": prev_color,
                            "to_color": current_color
                        })

        return {
            "has_changes": True,
            "added_points": added_points,
            "removed_points": removed_points,
            "moved_points": [],  # TODO: 移動検出
            "color_changes": color_changes
        }

    except Exception as e:
        logger.error(f"calculate_diff failed: {e}")
        return {"has_changes": False, "error": str(e)}


def create_dynamic_jcross_processors() -> Dict[str, callable]:
    """
    動的JCross用プロセッサを作成

    Returns:
        プロセッサ辞書
    """
    return {
        # 動画処理
        "video.extract_frames": extract_frames,

        # ARC-AGI2グリッド
        "arc.frame_to_grid": frame_to_grid,

        # Cross変換
        "cross.grid_to_cross": grid_to_cross,

        # 差分計算
        "cross.calculate_diff": calculate_diff,
    }
