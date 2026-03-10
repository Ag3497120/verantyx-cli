#!/usr/bin/env python3
"""
Large Cross Structure (260,000 points)
大規模Cross構造（260,000点）

Phase 6: 大規模Cross構造の実装
- 260,000点の6軸Cross構造
- 疎行列による効率的なメモリ管理
- 階層的な点の意味付け
- 高速同調計算
"""

import numpy as np
from scipy import sparse
from typing import Dict, Any, List, Optional, Tuple
import warnings


class LargeCrossStructure:
    """
    大規模Cross構造（260,000点）

    メモリ効率を考慮した実装:
    - 疎行列（sparse matrix）を使用
    - 非ゼロ要素のみ保存
    - 階層的な構造（Layer 0-4）
    """

    # 各層の点数
    LAYER_SIZES = {
        0: 200000,  # Pixel Layer
        1: 50000,   # Feature Layer
        2: 10000,   # Pattern Layer
        3: 1000,    # Semantic Layer
        4: 100      # Concept Layer
    }

    TOTAL_POINTS = sum(LAYER_SIZES.values())  # 260,100点

    def __init__(self, use_sparse: bool = True):
        """
        Initialize

        Args:
            use_sparse: 疎行列を使用するか
        """
        self.use_sparse = use_sparse
        self.num_points = self.TOTAL_POINTS

        if use_sparse:
            # 疎行列で初期化
            self.up = sparse.lil_matrix((self.num_points, 1), dtype=np.float32)
            self.down = sparse.lil_matrix((self.num_points, 1), dtype=np.float32)
            self.right = sparse.lil_matrix((self.num_points, 1), dtype=np.float32)
            self.left = sparse.lil_matrix((self.num_points, 1), dtype=np.float32)
            self.front = sparse.lil_matrix((self.num_points, 1), dtype=np.float32)
            self.back = sparse.lil_matrix((self.num_points, 1), dtype=np.float32)
        else:
            # 密行列で初期化
            self.up = np.zeros(self.num_points, dtype=np.float32)
            self.down = np.zeros(self.num_points, dtype=np.float32)
            self.right = np.zeros(self.num_points, dtype=np.float32)
            self.left = np.zeros(self.num_points, dtype=np.float32)
            self.front = np.zeros(self.num_points, dtype=np.float32)
            self.back = np.zeros(self.num_points, dtype=np.float32)

        # 層のオフセット
        self.layer_offsets = {}
        offset = 0
        for layer, size in self.LAYER_SIZES.items():
            self.layer_offsets[layer] = offset
            offset += size

        # メタデータ
        self.metadata = {
            "total_points": self.num_points,
            "use_sparse": use_sparse,
            "layers": self.LAYER_SIZES.copy()
        }

    def set_layer_data(self, layer: int, axis: str, data: np.ndarray):
        """
        特定の層のデータを設定

        Args:
            layer: 層番号（0-4）
            axis: 軸名（"up"/"down"/"right"/"left"/"front"/"back"）
            data: データ配列
        """
        if layer not in self.layer_offsets:
            raise ValueError(f"Invalid layer: {layer}")

        offset = self.layer_offsets[layer]
        size = self.LAYER_SIZES[layer]

        # データサイズをチェック
        if len(data) > size:
            data = data[:size]
        elif len(data) < size:
            # パディング
            data = np.pad(data, (0, size - len(data)), mode='constant')

        # 軸を取得
        axis_attr = getattr(self, axis.lower())

        if self.use_sparse:
            # 疎行列の場合
            axis_attr[offset:offset + size, 0] = data.reshape(-1, 1)
        else:
            # 密行列の場合
            axis_attr[offset:offset + size] = data

    def get_layer_data(self, layer: int, axis: str) -> np.ndarray:
        """
        特定の層のデータを取得

        Args:
            layer: 層番号（0-4）
            axis: 軸名

        Returns:
            データ配列
        """
        if layer not in self.layer_offsets:
            raise ValueError(f"Invalid layer: {layer}")

        offset = self.layer_offsets[layer]
        size = self.LAYER_SIZES[layer]

        axis_attr = getattr(self, axis.lower())

        if self.use_sparse:
            return axis_attr[offset:offset + size, 0].toarray().flatten()
        else:
            return axis_attr[offset:offset + size]

    def sync_with(
        self,
        other: 'LargeCrossStructure',
        layer: Optional[int] = None,
        threshold: float = 0.1
    ) -> float:
        """
        他のCross構造との同調度を計算

        Args:
            other: 比較対象のCross構造
            layer: 特定の層のみ比較（Noneの場合は全層）
            threshold: 一致とみなす閾値

        Returns:
            同調度 (0.0-1.0)
        """
        if layer is not None:
            # 特定の層のみ
            return self._layer_sync(other, layer, threshold)
        else:
            # 全層の平均
            layer_syncs = []
            for layer_num in self.LAYER_SIZES.keys():
                sync = self._layer_sync(other, layer_num, threshold)
                layer_syncs.append(sync)

            return np.mean(layer_syncs)

    def _layer_sync(
        self,
        other: 'LargeCrossStructure',
        layer: int,
        threshold: float
    ) -> float:
        """
        特定の層の同調度を計算

        Args:
            other: 比較対象
            layer: 層番号
            threshold: 閾値

        Returns:
            同調度
        """
        # 各軸の同調度
        axis_syncs = []

        for axis in ["up", "down", "right", "left", "front", "back"]:
            data1 = self.get_layer_data(layer, axis)
            data2 = other.get_layer_data(layer, axis)

            # 差分
            diff = np.abs(data1 - data2)

            # 閾値以下の割合
            matched = np.sum(diff <= threshold)
            sync_score = matched / len(data1)

            axis_syncs.append(sync_score)

        # 6軸の平均
        return np.mean(axis_syncs)

    def predict_front(self, layer: Optional[int] = None) -> 'LargeCrossStructure':
        """
        FRONT軸方向に予測

        Args:
            layer: 特定の層のみ予測（Noneの場合は全層）

        Returns:
            予測されたCross構造
        """
        predicted = LargeCrossStructure(use_sparse=self.use_sparse)

        if layer is not None:
            layers_to_predict = [layer]
        else:
            layers_to_predict = list(self.LAYER_SIZES.keys())

        for layer_num in layers_to_predict:
            # UP軸のデータ
            up_data = self.get_layer_data(layer_num, "up")
            front_data = self.get_layer_data(layer_num, "front")

            # 予測: 現在値 + FRONT軸の傾向
            if np.any(front_data != 0):
                predicted_up = up_data + front_data
            else:
                predicted_up = up_data.copy()

            predicted.set_layer_data(layer_num, "up", predicted_up)

            # 他の軸はコピー
            for axis in ["down", "right", "left", "front", "back"]:
                data = self.get_layer_data(layer_num, axis)
                predicted.set_layer_data(layer_num, axis, data.copy())

        return predicted

    def get_memory_usage(self) -> Dict[str, Any]:
        """
        メモリ使用量を取得

        Returns:
            メモリ使用量情報
        """
        if self.use_sparse:
            # 疎行列のメモリ使用量
            axes = [self.up, self.down, self.right, self.left, self.front, self.back]

            total_bytes = 0
            non_zero_counts = []

            for axis in axes:
                # CSR形式に変換してサイズを計算
                axis_csr = axis.tocsr()
                bytes_used = axis_csr.data.nbytes + axis_csr.indices.nbytes + axis_csr.indptr.nbytes
                total_bytes += bytes_used
                non_zero_counts.append(axis.nnz)

            return {
                "total_bytes": total_bytes,
                "total_mb": total_bytes / (1024 * 1024),
                "non_zero_elements": {
                    "up": non_zero_counts[0],
                    "down": non_zero_counts[1],
                    "right": non_zero_counts[2],
                    "left": non_zero_counts[3],
                    "front": non_zero_counts[4],
                    "back": non_zero_counts[5]
                },
                "sparsity": sum(non_zero_counts) / (self.num_points * 6)
            }
        else:
            # 密行列のメモリ使用量
            total_bytes = (
                self.up.nbytes +
                self.down.nbytes +
                self.right.nbytes +
                self.left.nbytes +
                self.front.nbytes +
                self.back.nbytes
            )

            return {
                "total_bytes": total_bytes,
                "total_mb": total_bytes / (1024 * 1024),
                "density": 1.0
            }

    def __repr__(self) -> str:
        memory_info = self.get_memory_usage()
        if self.use_sparse:
            return f"<LargeCrossStructure: {self.num_points} points (sparse), {memory_info['total_mb']:.2f} MB, sparsity={memory_info['sparsity']:.4f}>"
        else:
            return f"<LargeCrossStructure: {self.num_points} points (dense), {memory_info['total_mb']:.2f} MB>"


def main():
    """テスト用メイン関数"""
    print("=" * 80)
    print("大規模Cross構造テスト（260,000点）")
    print("=" * 80)
    print()

    # 疎行列版を作成
    print("1. 疎行列版の作成")
    sparse_cross = LargeCrossStructure(use_sparse=True)
    print(f"   {sparse_cross}")
    print()

    # Layer 4（Concept Layer）にデータを設定
    print("2. Layer 4（Concept Layer）にデータを設定")
    concept_data = np.random.rand(100) * 0.5  # 100点
    sparse_cross.set_layer_data(4, "up", concept_data)
    print(f"   Layer 4 UP軸: {sparse_cross.get_layer_data(4, 'up')[:10]}")
    print()

    # メモリ使用量
    print("3. メモリ使用量")
    memory_info = sparse_cross.get_memory_usage()
    print(f"   総メモリ: {memory_info['total_mb']:.2f} MB")
    print(f"   疎密度: {memory_info['sparsity']:.6f}")
    print(f"   非ゼロ要素数: {memory_info['non_zero_elements']}")
    print()

    # 同調度計算（Layer 4のみ）
    print("4. 同調度計算")
    another_cross = LargeCrossStructure(use_sparse=True)
    another_cross.set_layer_data(4, "up", concept_data * 0.9)  # 90%一致

    sync_layer4 = sparse_cross.sync_with(another_cross, layer=4)
    print(f"   Layer 4の同調度: {sync_layer4:.4f}")
    print()

    # 予測
    print("5. FRONT軸予測")
    front_data = np.ones(100) * 0.1  # 傾向: +0.1
    sparse_cross.set_layer_data(4, "front", front_data)

    predicted = sparse_cross.predict_front(layer=4)
    print(f"   元のLayer 4: {sparse_cross.get_layer_data(4, 'up')[:5]}")
    print(f"   予測Layer 4: {predicted.get_layer_data(4, 'up')[:5]}")
    print()

    # 密行列版との比較
    print("6. 密行列版との比較")
    dense_cross = LargeCrossStructure(use_sparse=False)
    dense_memory = dense_cross.get_memory_usage()
    print(f"   密行列メモリ: {dense_memory['total_mb']:.2f} MB")
    print(f"   疎行列メモリ: {memory_info['total_mb']:.2f} MB")
    print(f"   削減率: {(1 - memory_info['total_mb'] / dense_memory['total_mb']) * 100:.2f}%")


if __name__ == "__main__":
    main()
