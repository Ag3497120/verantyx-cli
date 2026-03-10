#!/usr/bin/env python3
"""
Cross Neural Network
本物のCross AI実装

Cross構造 = ニューラルネットワーク
26万点の情報を全て使う
6軸の相互作用で意味を生成
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CrossConnection:
    """Cross点間の接続"""
    source_id: int      # 接続元の点ID
    target_id: int      # 接続先の点ID
    weight: float       # 重み
    axis_type: str      # 接続の種類（inter_layer, intra_layer, axis_direction）


class CrossPoint:
    """
    Cross構造の点 = ニューロン

    26万点の各点がニューロンとして機能する。
    """

    def __init__(
        self,
        point_id: int,
        layer_id: int,
        position_3d: np.ndarray,
        rgb: np.ndarray,
        axis_values: Dict[str, float]
    ):
        """
        Initialize Cross point (neuron)

        Args:
            point_id: 点のID
            layer_id: 所属する層のID
            position_3d: 3次元位置 (x, y, z)
            rgb: RGB値 (r, g, b)
            axis_values: 6軸の値
        """
        self.id = point_id
        self.layer_id = layer_id
        self.position = position_3d  # (x, y, z)
        self.rgb = rgb              # (r, g, b)

        # 6軸の値（これが活性化を変調する）
        self.axes = axis_values

        # 接続リスト
        self.connections = []  # List[CrossConnection]

        # 現在の活性化状態
        self.activation = 0.0
        self.prev_activation = 0.0

        # 学習用の勾配
        self.gradient = 0.0

    def add_connection(self, connection: CrossConnection):
        """接続を追加"""
        self.connections.append(connection)

    def calculate_input(self, all_points: Dict[int, 'CrossPoint']) -> float:
        """
        入力を計算（接続された点からの入力の合計）

        Args:
            all_points: 全ての点の辞書 {point_id: CrossPoint}

        Returns:
            入力値
        """
        total_input = 0.0

        for conn in self.connections:
            source_point = all_points.get(conn.source_id)
            if source_point:
                # 重み × 接続元の活性化
                total_input += conn.weight * source_point.activation

        return total_input

    def activate(self, total_input: float):
        """
        活性化関数を適用

        Args:
            total_input: 入力値
        """
        # 前回の活性化を保存
        self.prev_activation = self.activation

        # 6軸による変調
        axis_modulation = self._calculate_axis_modulation()

        # シグモイド活性化（6軸で変調）
        modulated_input = total_input * axis_modulation
        self.activation = self._sigmoid(modulated_input)

    def _calculate_axis_modulation(self) -> float:
        """
        6軸による変調を計算

        Returns:
            変調係数
        """
        # UP/DOWN: 活性度の制御
        vertical = self.axes["UP"] - self.axes["DOWN"]

        # FRONT/BACK: 時間的な影響
        temporal = self.axes["FRONT"] - self.axes["BACK"]

        # RIGHT/LEFT: 空間的な影響
        spatial = self.axes["RIGHT"] - self.axes["LEFT"]

        # 3つの軸を統合（0.5-1.5の範囲）
        modulation = 1.0 + (vertical + temporal + spatial) / 6.0

        return np.clip(modulation, 0.1, 2.0)

    def _sigmoid(self, x: float) -> float:
        """シグモイド関数"""
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

    def update_weights(self, learning_rate: float, all_points: Dict[int, 'CrossPoint']):
        """
        重みを更新（学習）

        Args:
            learning_rate: 学習率
            all_points: 全ての点の辞書
        """
        for conn in self.connections:
            source_point = all_points.get(conn.source_id)
            if source_point:
                # 勾配降下法
                delta_weight = learning_rate * self.gradient * source_point.activation
                conn.weight -= delta_weight

                # 重みをクリップ
                conn.weight = np.clip(conn.weight, -5.0, 5.0)


class CrossLayer:
    """
    Cross構造の層 = ニューラル層

    Layer0: 100,000点（入力層）
    Layer1: 50,000点（特徴抽出）
    Layer2: 10,000点（パターン認識）
    Layer3: 1,000点（意味理解）
    Layer4: 100点（概念形成）
    """

    def __init__(self, layer_id: int, name: str, points: List[CrossPoint]):
        """
        Initialize Cross layer

        Args:
            layer_id: 層のID
            name: 層の名前
            points: この層に属する点のリスト
        """
        self.id = layer_id
        self.name = name
        self.points = points
        self.num_points = len(points)

    def forward_propagate(self, all_points: Dict[int, CrossPoint]):
        """
        順伝播（下層 → この層）

        Args:
            all_points: 全ての点の辞書
        """
        for point in self.points:
            # 入力を計算
            total_input = point.calculate_input(all_points)

            # 活性化
            point.activate(total_input)

    def get_activation_vector(self) -> np.ndarray:
        """
        この層の活性化ベクトルを取得

        Returns:
            活性化ベクトル（shape: (num_points,)）
        """
        return np.array([point.activation for point in self.points])

    def set_activation_vector(self, activations: np.ndarray):
        """
        この層の活性化ベクトルを設定（入力層用）

        Args:
            activations: 活性化ベクトル
        """
        for i, point in enumerate(self.points):
            if i < len(activations):
                point.activation = activations[i]


class CrossNeuralNetwork:
    """
    Cross構造全体 = 深層ニューラルネットワーク

    本物のCross AI:
    - 26万点全てがニューロン
    - 層間接続 = 重み
    - 6軸 = 変調係数
    - 情報が層を通って流れる
    """

    def __init__(self, layers: List[CrossLayer], all_points: Dict[int, CrossPoint]):
        """
        Initialize Cross neural network

        Args:
            layers: Cross層のリスト（Layer0 → Layer4）
            all_points: 全ての点の辞書
        """
        self.layers = layers
        self.all_points = all_points
        self.num_layers = len(layers)

        print(f"🧠 Cross Neural Network initialized:")
        print(f"   総点数: {len(all_points):,}")
        print(f"   層数: {self.num_layers}")
        for layer in layers:
            print(f"   - {layer.name}: {layer.num_points:,} points")

    def forward(self):
        """
        順伝播（Layer0 → Layer4）

        情報が層を通って流れる。
        """
        # Layer0（入力層）はスキップ（既にセット済み）
        # Layer1から順に活性化
        for layer in self.layers[1:]:
            layer.forward_propagate(self.all_points)

    def backward(self, target_output: np.ndarray, learning_rate: float = 0.01):
        """
        逆伝播（学習）

        Args:
            target_output: 目標出力（Layer4の正解）
            learning_rate: 学習率
        """
        # 1. 出力層（Layer4）の誤差を計算
        output_layer = self.layers[-1]
        current_output = output_layer.get_activation_vector()

        # 二乗誤差
        error = target_output - current_output

        # 出力層の勾配
        for i, point in enumerate(output_layer.points):
            if i < len(error):
                # シグモイドの微分
                sigmoid_derivative = point.activation * (1 - point.activation)
                point.gradient = error[i] * sigmoid_derivative

        # 2. 逆向きに誤差を伝播
        for layer_idx in range(self.num_layers - 2, -1, -1):
            current_layer = self.layers[layer_idx]

            for point in current_layer.points:
                # この点から出ていく接続を探す
                gradient = 0.0

                for conn in point.connections:
                    target_point = self.all_points.get(conn.target_id)
                    if target_point and target_point.layer_id > point.layer_id:
                        # 上位層からの勾配を逆伝播
                        gradient += conn.weight * target_point.gradient

                # シグモイドの微分
                sigmoid_derivative = point.activation * (1 - point.activation)
                point.gradient = gradient * sigmoid_derivative

        # 3. 全ての重みを更新
        for point in self.all_points.values():
            point.update_weights(learning_rate, self.all_points)

    def set_input(self, input_activations: np.ndarray):
        """
        入力層（Layer0）に入力をセット

        Args:
            input_activations: 入力ベクトル（shape: (100000,)）
        """
        input_layer = self.layers[0]
        input_layer.set_activation_vector(input_activations)

    def get_output(self) -> np.ndarray:
        """
        出力層（Layer4）の出力を取得

        Returns:
            出力ベクトル（shape: (100,)）
        """
        output_layer = self.layers[-1]
        return output_layer.get_activation_vector()

    def predict(self, input_activations: np.ndarray) -> np.ndarray:
        """
        予測

        Args:
            input_activations: 入力

        Returns:
            出力
        """
        # 入力をセット
        self.set_input(input_activations)

        # 順伝播
        self.forward()

        # 出力を取得
        return self.get_output()

    def train_step(
        self,
        input_activations: np.ndarray,
        target_output: np.ndarray,
        learning_rate: float = 0.01
    ) -> float:
        """
        1ステップの学習

        Args:
            input_activations: 入力
            target_output: 目標出力
            learning_rate: 学習率

        Returns:
            誤差（MSE）
        """
        # 順伝播
        output = self.predict(input_activations)

        # 誤差を計算
        error = np.mean((target_output - output) ** 2)

        # 逆伝播
        self.backward(target_output, learning_rate)

        return error

    def get_layer_activations(self, layer_id: int) -> np.ndarray:
        """
        特定の層の活性化を取得

        Args:
            layer_id: 層のID

        Returns:
            活性化ベクトル
        """
        if 0 <= layer_id < self.num_layers:
            return self.layers[layer_id].get_activation_vector()
        return np.array([])


class CrossNeuralNetworkBuilder:
    """Cross Neural Networkを構築するビルダー"""

    @staticmethod
    def from_multi_layer_cross(multi_layer_cross: Dict[str, Any]) -> CrossNeuralNetwork:
        """
        MultiLayerCrossConverter の出力からCross Neural Networkを構築

        Args:
            multi_layer_cross: MultiLayerCrossConverterの出力

        Returns:
            CrossNeuralNetwork
        """
        print()
        print("=" * 70)
        print("🏗️  Cross Neural Network 構築中...")
        print("=" * 70)
        print()

        all_points = {}
        layers = []

        # 各層を処理
        for layer_data in multi_layer_cross["layers"]:
            layer_id = layer_data["id"]
            layer_name = layer_data["name"]

            print(f"Layer {layer_id} ({layer_name}) 構築中...")

            # この層の点を作成
            layer_points = []

            for i, point_data in enumerate(layer_data["points"]):
                point_id = len(all_points)  # グローバルID

                # CrossPointを作成
                cross_point = CrossPoint(
                    point_id=point_id,
                    layer_id=layer_id,
                    position_3d=np.array(point_data["position"]),
                    rgb=np.array(point_data["rgb"]),
                    axis_values=point_data["axis_values"]
                )

                all_points[point_id] = cross_point
                layer_points.append(cross_point)

            # CrossLayerを作成
            cross_layer = CrossLayer(layer_id, layer_name, layer_points)
            layers.append(cross_layer)

            print(f"   → {len(layer_points):,} 点を作成")

        print()
        print("接続を構築中...")

        # 接続を構築（層間接続）
        total_connections = 0

        for layer_data in multi_layer_cross["layers"]:
            if "inter_layer_connections" in layer_data:
                for conn_data in layer_data["inter_layer_connections"]:
                    # 接続元と接続先の点IDを特定
                    source_layer_id = layer_data["id"]
                    source_idx = conn_data["source_idx"]
                    target_idx = conn_data["target_idx"]

                    # グローバルIDに変換
                    source_id = CrossNeuralNetworkBuilder._get_global_id(
                        all_points, source_layer_id, source_idx
                    )
                    target_id = CrossNeuralNetworkBuilder._get_global_id(
                        all_points, source_layer_id + 1, target_idx
                    )

                    if source_id is not None and target_id is not None:
                        # 接続を作成（初期重みはランダム）
                        connection = CrossConnection(
                            source_id=source_id,
                            target_id=target_id,
                            weight=np.random.randn() * 0.1,
                            axis_type="inter_layer"
                        )

                        # 接続先の点に接続を追加
                        all_points[target_id].add_connection(connection)
                        total_connections += 1

        print(f"   → {total_connections:,} 個の接続を作成")
        print()

        # CrossNeuralNetworkを構築
        network = CrossNeuralNetwork(layers, all_points)

        print("=" * 70)
        print("✅ Cross Neural Network 構築完了")
        print("=" * 70)
        print()

        return network

    @staticmethod
    def _get_global_id(
        all_points: Dict[int, CrossPoint],
        layer_id: int,
        local_idx: int
    ) -> Optional[int]:
        """ローカルインデックスからグローバルIDを取得"""
        for point_id, point in all_points.items():
            if point.layer_id == layer_id:
                # この層の何番目の点か
                layer_points = [
                    p for p in all_points.values()
                    if p.layer_id == layer_id
                ]
                layer_points.sort(key=lambda p: p.id)

                if local_idx < len(layer_points):
                    return layer_points[local_idx].id

        return None
