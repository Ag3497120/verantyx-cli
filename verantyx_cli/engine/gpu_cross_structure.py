#!/usr/bin/env python3
"""
GPU Cross Structure
GPU並列化Cross構造

Phase 7: GPU並列化
- CuPyによるGPU演算
- 260,000点の高速同調計算
- バッチ処理
- 自動的にGPU/CPUを切り替え
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple

# CuPyが利用可能かチェック
try:
    import cupy as cp
    CUPY_AVAILABLE = True
    print("✅ CuPy available - GPU acceleration enabled")
except ImportError:
    cp = None
    CUPY_AVAILABLE = False
    print("⚠️  CuPy not available - using CPU fallback")


class GPUCrossStructure:
    """
    GPU並列化Cross構造

    CuPyが利用可能な場合はGPUで演算、
    そうでない場合はNumPy（CPU）で演算
    """

    def __init__(self, num_points: int = 260100, use_gpu: bool = True):
        """
        Initialize

        Args:
            num_points: 点の総数
            use_gpu: GPUを使用するか
        """
        self.num_points = num_points
        self.use_gpu = use_gpu and CUPY_AVAILABLE

        # 使用するライブラリを決定
        self.xp = cp if self.use_gpu else np

        # 6軸を初期化
        self.up = self.xp.zeros(num_points, dtype=self.xp.float32)
        self.down = self.xp.zeros(num_points, dtype=self.xp.float32)
        self.right = self.xp.zeros(num_points, dtype=self.xp.float32)
        self.left = self.xp.zeros(num_points, dtype=self.xp.float32)
        self.front = self.xp.zeros(num_points, dtype=self.xp.float32)
        self.back = self.xp.zeros(num_points, dtype=self.xp.float32)

    def to_cpu(self):
        """GPUからCPUにデータを転送"""
        if not self.use_gpu:
            return

        self.up = cp.asnumpy(self.up)
        self.down = cp.asnumpy(self.down)
        self.right = cp.asnumpy(self.right)
        self.left = cp.asnumpy(self.left)
        self.front = cp.asnumpy(self.front)
        self.back = cp.asnumpy(self.back)

        self.use_gpu = False
        self.xp = np

    def to_gpu(self):
        """CPUからGPUにデータを転送"""
        if not CUPY_AVAILABLE or self.use_gpu:
            return

        self.up = cp.asarray(self.up)
        self.down = cp.asarray(self.down)
        self.right = cp.asarray(self.right)
        self.left = cp.asarray(self.left)
        self.front = cp.asarray(self.front)
        self.back = cp.asarray(self.back)

        self.use_gpu = True
        self.xp = cp

    def sync_with(self, other: 'GPUCrossStructure', threshold: float = 0.1) -> float:
        """
        他のCross構造との同調度を計算（GPU並列化）

        Args:
            other: 比較対象のCross構造
            threshold: 一致とみなす閾値

        Returns:
            同調度 (0.0-1.0)
        """
        # 各軸の同調度を計算
        axis_syncs = []

        for axis_name in ["up", "down", "right", "left", "front", "back"]:
            axis1 = getattr(self, axis_name)
            axis2 = getattr(other, axis_name)

            # 差分（GPU並列計算）
            diff = self.xp.abs(axis1 - axis2)

            # 閾値以下の点の数
            matched = self.xp.sum(diff <= threshold)

            # 同調度
            sync_score = float(matched) / self.num_points

            axis_syncs.append(sync_score)

        # 6軸の平均
        return float(self.xp.mean(self.xp.array(axis_syncs)))

    def batch_sync(self, others: List['GPUCrossStructure'], threshold: float = 0.1) -> np.ndarray:
        """
        複数のCross構造との同調度を一括計算（GPU並列化）

        Args:
            others: 比較対象のCross構造リスト
            threshold: 閾値

        Returns:
            同調度の配列
        """
        results = []

        for other in others:
            sync = self.sync_with(other, threshold)
            results.append(sync)

        return np.array(results)

    def predict_front(self, steps: int = 1) -> 'GPUCrossStructure':
        """
        FRONT軸方向に予測（GPU並列化）

        Args:
            steps: 予測ステップ数

        Returns:
            予測されたCross構造
        """
        predicted = GPUCrossStructure(self.num_points, self.use_gpu)

        # UP軸の予測（GPU並列計算）
        if self.xp.any(self.front != 0):
            predicted.up = self.up + self.front * steps
        else:
            predicted.up = self.up.copy()

        # 他の軸はコピー
        predicted.down = self.down.copy()
        predicted.right = self.right.copy()
        predicted.left = self.left.copy()
        predicted.front = self.front.copy()
        predicted.back = self.back.copy()

        return predicted

    def apply_resource_allocation(self, allocation: Dict[str, float]):
        """
        リソース配分を適用（GPU並列化）

        Args:
            allocation: リソース配分辞書
        """
        resource_mapping = {
            "explore": 0,
            "learn": 1,
            "predict": 2,
            "memory": 3,
            "flee": 4,
            "attack": 5,
            "rest": 6
        }

        for resource, value in allocation.items():
            if resource in resource_mapping:
                idx = resource_mapping[resource]
                if idx < self.num_points:
                    self.right[idx] = value

    def get_activation(self) -> float:
        """
        活性化レベルを取得（GPU並列化）

        Returns:
            活性化レベル
        """
        return float(self.xp.sum(self.up))

    def get_memory_usage(self) -> Dict[str, Any]:
        """
        メモリ使用量を取得

        Returns:
            メモリ使用量情報
        """
        axes = [self.up, self.down, self.right, self.left, self.front, self.back]

        total_bytes = sum(axis.nbytes for axis in axes)

        return {
            "total_bytes": total_bytes,
            "total_mb": total_bytes / (1024 * 1024),
            "device": "GPU" if self.use_gpu else "CPU"
        }

    def __repr__(self) -> str:
        memory_info = self.get_memory_usage()
        device = "GPU" if self.use_gpu else "CPU"
        return f"<GPUCrossStructure: {self.num_points} points on {device}, {memory_info['total_mb']:.2f} MB>"


def benchmark_sync(num_points: int = 260100, use_gpu: bool = True):
    """
    同調計算のベンチマーク

    Args:
        num_points: 点の数
        use_gpu: GPUを使用するか
    """
    import time

    print(f"\n{'='*80}")
    print(f"ベンチマーク: {num_points}点の同調計算")
    print(f"デバイス: {'GPU' if use_gpu and CUPY_AVAILABLE else 'CPU'}")
    print(f"{'='*80}\n")

    # Cross構造を作成
    cross1 = GPUCrossStructure(num_points, use_gpu)
    cross2 = GPUCrossStructure(num_points, use_gpu)

    # ランダムデータを設定
    if use_gpu and CUPY_AVAILABLE:
        cross1.up = cp.random.rand(num_points).astype(cp.float32)
        cross2.up = cp.random.rand(num_points).astype(cp.float32) * 0.9
    else:
        cross1.up = np.random.rand(num_points).astype(np.float32)
        cross2.up = np.random.rand(num_points).astype(np.float32) * 0.9

    # ウォームアップ
    _ = cross1.sync_with(cross2)

    # ベンチマーク
    num_iterations = 100
    start = time.time()

    for _ in range(num_iterations):
        sync = cross1.sync_with(cross2)

    elapsed = time.time() - start

    print(f"実行時間: {elapsed:.4f}秒 ({num_iterations}回)")
    print(f"1回あたり: {elapsed/num_iterations*1000:.2f}ms")
    print(f"同調度: {sync:.4f}")
    print()


def main():
    """テスト用メイン関数"""
    print("=" * 80)
    print("GPU並列化Cross構造テスト")
    print("=" * 80)

    # GPU版を作成
    print("\n1. GPU版の作成")
    gpu_cross = GPUCrossStructure(num_points=260100, use_gpu=True)
    print(f"   {gpu_cross}")

    # CPU版を作成
    print("\n2. CPU版の作成")
    cpu_cross = GPUCrossStructure(num_points=260100, use_gpu=False)
    print(f"   {cpu_cross}")

    # ベンチマーク（GPU）
    if CUPY_AVAILABLE:
        benchmark_sync(num_points=260100, use_gpu=True)

    # ベンチマーク（CPU）
    benchmark_sync(num_points=260100, use_gpu=False)

    # バッチ同調
    if CUPY_AVAILABLE:
        print("=" * 80)
        print("バッチ同調テスト（GPU）")
        print("=" * 80)

        base_cross = GPUCrossStructure(100, use_gpu=True)
        base_cross.up = cp.random.rand(100).astype(cp.float32)

        # 10個のCross構造を作成
        others = []
        for i in range(10):
            other = GPUCrossStructure(100, use_gpu=True)
            other.up = cp.random.rand(100).astype(cp.float32) * 0.8
            others.append(other)

        # バッチ同調
        import time
        start = time.time()
        syncs = base_cross.batch_sync(others)
        elapsed = time.time() - start

        print(f"\n10個との同調度: {syncs}")
        print(f"実行時間: {elapsed*1000:.2f}ms")


if __name__ == "__main__":
    main()
