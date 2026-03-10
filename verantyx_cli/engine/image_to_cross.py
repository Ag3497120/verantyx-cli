#!/usr/bin/env python3
"""
Image to Cross Structure Converter
画像→Cross構造変換器

Phase 8: 実画像処理との統合
- 画像を260,000点のCross構造に変換
- 5層構造（Pixel/Feature/Pattern/Semantic/Concept）
- GPU並列化対応
"""

import numpy as np
from PIL import Image
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from large_cross_structure import LargeCrossStructure
from gpu_cross_structure import GPUCrossStructure


class ImageToCrossConverter:
    """
    画像→Cross構造変換器

    画像を260,000点の大規模Cross構造に変換
    """

    def __init__(self, use_gpu: bool = False, target_size: Tuple[int, int] = (64, 64)):
        """
        Initialize

        Args:
            use_gpu: GPUを使用するか
            target_size: 画像のリサイズサイズ
        """
        self.use_gpu = use_gpu
        self.target_size = target_size

    def convert(self, image: Image.Image) -> LargeCrossStructure:
        """
        画像をCross構造に変換

        Args:
            image: PIL Image

        Returns:
            LargeCrossStructure
        """
        # 画像をリサイズ
        image = image.resize(self.target_size)

        # RGB配列に変換
        img_array = np.array(image, dtype=np.float32) / 255.0  # 0-1に正規化

        # Cross構造を作成
        cross = LargeCrossStructure(use_sparse=True)

        # Layer 0: Pixel Layer
        self._process_pixel_layer(cross, img_array)

        # Layer 1: Feature Layer
        self._process_feature_layer(cross, img_array)

        # Layer 2: Pattern Layer
        self._process_pattern_layer(cross, img_array)

        # Layer 3: Semantic Layer
        self._process_semantic_layer(cross, img_array)

        # Layer 4: Concept Layer
        self._process_concept_layer(cross, img_array)

        return cross

    def _process_pixel_layer(self, cross: LargeCrossStructure, img_array: np.ndarray):
        """
        Layer 0: Pixel Layerを処理

        各ピクセルの輝度をUP軸に、色相をRIGHT軸に配置

        Args:
            cross: LargeCrossStructure
            img_array: 画像配列
        """
        h, w = img_array.shape[:2]

        # グレースケールに変換（輝度）
        if len(img_array.shape) == 3:
            luminance = np.mean(img_array, axis=2)
        else:
            luminance = img_array

        # フラット化
        flat_luminance = luminance.flatten()

        # Layer 0のサイズ: 200,000点
        # 画像サイズ: 64x64 = 4,096点
        # 残りは0で埋める

        cross.set_layer_data(0, "up", flat_luminance)

        # 色相をRIGHT軸に
        if len(img_array.shape) == 3:
            # 簡易的な色相計算
            r = img_array[:, :, 0]
            g = img_array[:, :, 1]
            b = img_array[:, :, 2]

            # R-G差分を色相の代わりに使用
            hue_approx = (r - g).flatten()
            cross.set_layer_data(0, "right", hue_approx)

    def _process_feature_layer(self, cross: LargeCrossStructure, img_array: np.ndarray):
        """
        Layer 1: Feature Layerを処理

        エッジ、テクスチャなどの特徴を抽出

        Args:
            cross: LargeCrossStructure
            img_array: 画像配列
        """
        # グレースケール化
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array

        # 簡易的なエッジ検出（Sobelフィルタの簡易版）
        # 水平方向の差分
        dx = np.diff(gray, axis=1, prepend=gray[:, :1])
        # 垂直方向の差分
        dy = np.diff(gray, axis=0, prepend=gray[:1, :])

        # エッジ強度
        edge_strength = np.sqrt(dx**2 + dy**2)

        # フラット化
        flat_edges = edge_strength.flatten()

        # Layer 1に設定
        cross.set_layer_data(1, "up", flat_edges)

        # エッジの方向をRIGHT軸に
        edge_direction = np.arctan2(dy, dx).flatten()
        cross.set_layer_data(1, "right", edge_direction)

    def _process_pattern_layer(self, cross: LargeCrossStructure, img_array: np.ndarray):
        """
        Layer 2: Pattern Layerを処理

        局所的なパターン（コーナー、ブロブなど）を検出

        Args:
            cross: LargeCrossStructure
            img_array: 画像配列
        """
        # グレースケール化
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array

        # 簡易的なコーナー検出（Harris corner風）
        # 2次微分を計算
        dxx = np.diff(gray, n=2, axis=1, prepend=gray[:, :2])
        dyy = np.diff(gray, n=2, axis=0, prepend=gray[:2, :])

        # コーナー強度
        corner_strength = np.abs(dxx) + np.abs(dyy)

        # ダウンサンプリング（8x8ブロックの平均）
        h, w = corner_strength.shape
        block_size = 8
        downsampled = []

        for i in range(0, h, block_size):
            for j in range(0, w, block_size):
                block = corner_strength[i:i+block_size, j:j+block_size]
                downsampled.append(np.mean(block))

        pattern_features = np.array(downsampled, dtype=np.float32)

        # Layer 2に設定
        cross.set_layer_data(2, "up", pattern_features)

    def _process_semantic_layer(self, cross: LargeCrossStructure, img_array: np.ndarray):
        """
        Layer 3: Semantic Layerを処理

        意味的な特徴（顔らしさ、物体らしさなど）を抽出

        Args:
            cross: LargeCrossStructure
            img_array: 画像配列
        """
        # 簡易実装: 画像全体の統計量を使用

        # 平均輝度
        mean_brightness = np.mean(img_array)

        # 標準偏差（コントラスト）
        std_brightness = np.std(img_array)

        # 色の偏り
        if len(img_array.shape) == 3:
            r_mean = np.mean(img_array[:, :, 0])
            g_mean = np.mean(img_array[:, :, 1])
            b_mean = np.mean(img_array[:, :, 2])

            color_features = [r_mean, g_mean, b_mean]
        else:
            color_features = [mean_brightness, mean_brightness, mean_brightness]

        # その他の特徴
        semantic_features = [
            mean_brightness,
            std_brightness,
            *color_features,
            # さらに特徴を追加可能
        ]

        # Layer 3に設定（少数の特徴）
        semantic_array = np.array(semantic_features * 200, dtype=np.float32)  # 1000点分
        cross.set_layer_data(3, "up", semantic_array)

    def _process_concept_layer(self, cross: LargeCrossStructure, img_array: np.ndarray):
        """
        Layer 4: Concept Layerを処理

        高レベルの概念（カテゴリ、抽象的な属性など）

        Args:
            cross: LargeCrossStructure
            img_array: 画像配列
        """
        # 簡易実装: 画像の大域的な特徴

        # 全体の明るさ
        overall_brightness = np.mean(img_array)

        # 複雑さ（エッジの総量）
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array

        dx = np.diff(gray, axis=1)
        dy = np.diff(gray, axis=0)
        complexity = np.mean(np.abs(dx)) + np.mean(np.abs(dy))

        # 色の種類（RGB各チャンネルの多様性）
        if len(img_array.shape) == 3:
            r_diversity = np.std(img_array[:, :, 0])
            g_diversity = np.std(img_array[:, :, 1])
            b_diversity = np.std(img_array[:, :, 2])
            color_diversity = (r_diversity + g_diversity + b_diversity) / 3
        else:
            color_diversity = np.std(gray)

        # 概念レベルの特徴
        concept_features = [
            overall_brightness,
            complexity,
            color_diversity,
            # さらに特徴を追加可能
        ]

        # Layer 4に設定（100点）
        concept_array = np.array(concept_features * 34, dtype=np.float32)[:100]
        cross.set_layer_data(4, "up", concept_array)


def main():
    """テスト用メイン関数"""
    import sys

    print("=" * 80)
    print("画像→Cross構造変換テスト")
    print("=" * 80)
    print()

    # テスト画像を作成
    print("1. テスト画像を作成")

    # ランダムな画像
    test_img = Image.new('RGB', (64, 64))
    pixels = np.random.rand(64, 64, 3) * 255
    test_img = Image.fromarray(pixels.astype(np.uint8))

    print(f"   画像サイズ: {test_img.size}")
    print()

    # 変換器を作成
    print("2. 変換器を作成")
    converter = ImageToCrossConverter(use_gpu=False, target_size=(64, 64))
    print("   ✅ 完了")
    print()

    # 画像をCross構造に変換
    print("3. 画像をCross構造に変換")
    cross = converter.convert(test_img)
    print(f"   {cross}")
    print()

    # 各層の状態を確認
    print("4. 各層の状態")
    for layer in range(5):
        up_data = cross.get_layer_data(layer, "up")
        non_zero = np.count_nonzero(up_data)
        mean_val = np.mean(up_data[up_data != 0]) if non_zero > 0 else 0

        print(f"   Layer {layer}: 非ゼロ要素={non_zero}, 平均値={mean_val:.4f}")

    print()

    # メモリ使用量
    print("5. メモリ使用量")
    memory_info = cross.get_memory_usage()
    print(f"   総メモリ: {memory_info['total_mb']:.2f} MB")
    print(f"   疎密度: {memory_info['sparsity']:.6f}")


if __name__ == "__main__":
    main()
