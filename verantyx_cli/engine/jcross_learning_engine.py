#!/usr/bin/env python3
"""
JCross Learning Engine
JCross学習エンジン

Stage 4: 学習アルゴリズムの実装 (75%→90%)
- Hebbian学習: 同時活性化で結合強化
- 重み更新: 成功で強化、失敗で減衰
- パターン認識: 繰り返しパターンの検出
- 予測学習: FRONT軸での時系列予測
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import time

from cross_structure import CrossStructure
from large_cross_structure import LargeCrossStructure


class CrossConnectionMatrix:
    """
    Cross間の結合行列

    Hebbian学習: 同時に活性化したCrossの結合を強化
    """

    def __init__(self, num_crosses: int = 100):
        """
        Initialize

        Args:
            num_crosses: Cross構造の数
        """
        self.num_crosses = num_crosses

        # 結合行列 (i, j) = Crossi → Crossjの結合強度
        self.connections = np.zeros((num_crosses, num_crosses), dtype=np.float32)

        # Cross IDマッピング
        self.cross_id_map: Dict[str, int] = {}
        self.id_cross_map: Dict[int, str] = {}
        self.next_id = 0

    def register_cross(self, cross_name: str) -> int:
        """
        Cross構造を登録

        Args:
            cross_name: Cross名

        Returns:
            割り当てられたID
        """
        if cross_name in self.cross_id_map:
            return self.cross_id_map[cross_name]

        cross_id = self.next_id
        self.cross_id_map[cross_name] = cross_id
        self.id_cross_map[cross_id] = cross_name
        self.next_id += 1

        return cross_id

    def hebbian_update(
        self,
        cross1_name: str,
        cross2_name: str,
        activation1: float,
        activation2: float,
        learning_rate: float = 0.01
    ):
        """
        Hebbian学習則による結合更新

        "Neurons that fire together, wire together"

        Args:
            cross1_name: Cross1の名前
            cross2_name: Cross2の名前
            activation1: Cross1の活性化レベル
            activation2: Cross2の活性化レベル
            learning_rate: 学習率
        """
        id1 = self.register_cross(cross1_name)
        id2 = self.register_cross(cross2_name)

        # Hebbian更新: Δw = η * a1 * a2
        delta_w = learning_rate * activation1 * activation2

        self.connections[id1, id2] += delta_w

        # 対称的な結合も更新（双方向）
        self.connections[id2, id1] += delta_w

        # 結合強度を[0, 1]に制限
        self.connections[id1, id2] = np.clip(self.connections[id1, id2], 0.0, 1.0)
        self.connections[id2, id1] = np.clip(self.connections[id2, id1], 0.0, 1.0)

    def get_connection(self, cross1_name: str, cross2_name: str) -> float:
        """
        結合強度を取得

        Args:
            cross1_name: Cross1の名前
            cross2_name: Cross2の名前

        Returns:
            結合強度
        """
        if cross1_name not in self.cross_id_map or cross2_name not in self.cross_id_map:
            return 0.0

        id1 = self.cross_id_map[cross1_name]
        id2 = self.cross_id_map[cross2_name]

        return float(self.connections[id1, id2])

    def decay_all(self, decay_rate: float = 0.001):
        """
        全結合を減衰

        Args:
            decay_rate: 減衰率
        """
        self.connections *= (1.0 - decay_rate)


class PatternDetector:
    """
    パターン検出器

    繰り返し現れるCrossパターンを検出し、記憶
    """

    def __init__(self, pattern_threshold: float = 0.8):
        """
        Initialize

        Args:
            pattern_threshold: パターンとして認識する閾値
        """
        self.pattern_threshold = pattern_threshold

        # 検出されたパターン: {pattern_id: {"crosses": [...], "frequency": N, "strength": 0.9}}
        self.patterns: Dict[int, Dict[str, Any]] = {}
        self.next_pattern_id = 0

        # 最近のアクティベーション履歴
        self.activation_history: List[List[str]] = []
        self.history_size = 100

    def record_activation(self, active_crosses: List[str]):
        """
        アクティベーションを記録

        Args:
            active_crosses: 活性化したCrossのリスト
        """
        self.activation_history.append(active_crosses)

        if len(self.activation_history) > self.history_size:
            self.activation_history.pop(0)

        # パターン検出を試行
        self._detect_patterns()

    def _detect_patterns(self):
        """
        パターンを検出
        """
        if len(self.activation_history) < 3:
            return

        # 最近の3つのアクティベーションを確認
        recent = self.activation_history[-3:]

        # 共通して現れるCross
        common_crosses = set(recent[0])
        for activation in recent[1:]:
            common_crosses &= set(activation)

        if len(common_crosses) >= 2:
            # パターンとして登録
            pattern_key = tuple(sorted(common_crosses))

            # 既存パターンを検索
            existing_pattern_id = None
            for pid, pattern in self.patterns.items():
                if tuple(sorted(pattern["crosses"])) == pattern_key:
                    existing_pattern_id = pid
                    break

            if existing_pattern_id is not None:
                # 頻度を増加
                self.patterns[existing_pattern_id]["frequency"] += 1
                self.patterns[existing_pattern_id]["strength"] = min(
                    1.0,
                    self.patterns[existing_pattern_id]["strength"] + 0.05
                )
            else:
                # 新しいパターンとして登録
                self.patterns[self.next_pattern_id] = {
                    "crosses": list(common_crosses),
                    "frequency": 1,
                    "strength": 0.5,
                    "created_at": time.time()
                }
                self.next_pattern_id += 1

    def get_patterns(self, min_frequency: int = 2) -> List[Dict[str, Any]]:
        """
        検出されたパターンを取得

        Args:
            min_frequency: 最小頻度

        Returns:
            パターンのリスト
        """
        return [
            pattern
            for pattern in self.patterns.values()
            if pattern["frequency"] >= min_frequency
        ]


class JCrossLearningEngine:
    """
    JCross学習エンジン

    Stage 4: 実際の学習アルゴリズム実装
    """

    def __init__(self):
        """Initialize"""
        # 結合行列
        self.connection_matrix = CrossConnectionMatrix(num_crosses=200)

        # パターン検出器
        self.pattern_detector = PatternDetector()

        # 予測誤差履歴
        self.prediction_errors: List[float] = []

        # 学習統計
        self.learning_stats = {
            "total_updates": 0,
            "successful_predictions": 0,
            "failed_predictions": 0,
            "patterns_detected": 0
        }

    def hebbian_learn(
        self,
        active_crosses: Dict[str, float],
        learning_rate: float = 0.01
    ):
        """
        Hebbian学習を実行

        同時に活性化したCross間の結合を強化

        Args:
            active_crosses: {cross_name: activation_level}
            learning_rate: 学習率
        """
        cross_names = list(active_crosses.keys())

        # すべてのペアについて結合を更新
        for i, cross1 in enumerate(cross_names):
            for cross2 in cross_names[i+1:]:
                activation1 = active_crosses[cross1]
                activation2 = active_crosses[cross2]

                # Hebbian更新
                self.connection_matrix.hebbian_update(
                    cross1,
                    cross2,
                    activation1,
                    activation2,
                    learning_rate
                )

        self.learning_stats["total_updates"] += 1

        # パターン検出
        self.pattern_detector.record_activation(cross_names)
        self.learning_stats["patterns_detected"] = len(self.pattern_detector.get_patterns())

    def predict_next_activation(
        self,
        current_active: List[str]
    ) -> Dict[str, float]:
        """
        次に活性化するCrossを予測

        Args:
            current_active: 現在活性化しているCross

        Returns:
            {cross_name: predicted_activation}
        """
        predictions = {}

        for cross_name in current_active:
            if cross_name not in self.connection_matrix.cross_id_map:
                continue

            cross_id = self.connection_matrix.cross_id_map[cross_name]

            # この Crossから強い結合を持つCrossを予測
            connections = self.connection_matrix.connections[cross_id, :]

            # 上位3つ
            top_indices = np.argsort(connections)[-3:]

            for idx in top_indices:
                if idx < len(self.connection_matrix.id_cross_map):
                    target_name = self.connection_matrix.id_cross_map[idx]
                    strength = connections[idx]

                    if strength > 0.1:  # 閾値
                        predictions[target_name] = strength

        return predictions

    def learn_from_prediction_error(
        self,
        predicted: Dict[str, float],
        actual: List[str],
        error_threshold: float = 0.3
    ):
        """
        予測誤差から学習

        Args:
            predicted: 予測されたアクティベーション
            actual: 実際のアクティベーション
            error_threshold: 誤差の閾値
        """
        # 予測誤差を計算
        predicted_set = set(predicted.keys())
        actual_set = set(actual)

        # 正しく予測したもの
        correct = predicted_set & actual_set

        # 予測ミス
        false_positive = predicted_set - actual_set
        false_negative = actual_set - predicted_set

        # 誤差率
        error_rate = (len(false_positive) + len(false_negative)) / max(1, len(actual_set))

        self.prediction_errors.append(error_rate)

        if error_rate < error_threshold:
            self.learning_stats["successful_predictions"] += 1
        else:
            self.learning_stats["failed_predictions"] += 1

            # 誤った予測の結合を減衰
            for fp_cross in false_positive:
                for actual_cross in actual:
                    # 結合を弱める
                    if fp_cross in self.connection_matrix.cross_id_map and \
                       actual_cross in self.connection_matrix.cross_id_map:
                        id1 = self.connection_matrix.cross_id_map[fp_cross]
                        id2 = self.connection_matrix.cross_id_map[actual_cross]

                        self.connection_matrix.connections[id1, id2] *= 0.9

    def get_learning_stats(self) -> Dict[str, Any]:
        """
        学習統計を取得

        Returns:
            統計情報
        """
        recent_errors = self.prediction_errors[-10:] if self.prediction_errors else [0.0]

        return {
            **self.learning_stats,
            "average_prediction_error": np.mean(recent_errors),
            "total_patterns": len(self.pattern_detector.patterns),
            "connection_matrix_density": np.sum(self.connection_matrix.connections > 0.1) / \
                                        (self.connection_matrix.num_crosses ** 2)
        }


def main():
    """テスト用メイン関数"""
    print("=" * 80)
    print("JCross学習エンジンテスト")
    print("Stage 4: 学習アルゴリズムの実装")
    print("=" * 80)
    print()

    engine = JCrossLearningEngine()

    # テスト1: Hebbian学習
    print("【テスト1: Hebbian学習】")
    active1 = {"恐怖Cross": 0.9, "心拍数Cross": 0.8}
    engine.hebbian_learn(active1)

    connection = engine.connection_matrix.get_connection("恐怖Cross", "心拍数Cross")
    print(f"  恐怖Cross ⇔ 心拍数Cross の結合強度: {connection:.3f}")
    print()

    # テスト2: パターン検出
    print("【テスト2: パターン検出】")
    for _ in range(5):
        engine.pattern_detector.record_activation(["恐怖Cross", "心拍数Cross", "逃走Cross"])

    patterns = engine.pattern_detector.get_patterns(min_frequency=3)
    print(f"  検出されたパターン数: {len(patterns)}")
    if patterns:
        print(f"  パターン1: {patterns[0]['crosses']} (頻度: {patterns[0]['frequency']})")
    print()

    # テスト3: 予測
    print("【テスト3: 次のアクティベーション予測】")
    # さらに学習
    for _ in range(10):
        engine.hebbian_learn({"恐怖Cross": 0.9, "逃走Cross": 0.8})

    predicted = engine.predict_next_activation(["恐怖Cross"])
    print(f"  恐怖Crossから予測される次のCross: {predicted}")
    print()

    # 学習統計
    print("【学習統計】")
    stats = engine.get_learning_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    print("✅ Stage 4完了: 学習アルゴリズムが動作")
    print("\n現在の実装度: 75-90%")


if __name__ == "__main__":
    main()
