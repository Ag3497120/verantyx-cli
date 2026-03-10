#!/usr/bin/env python3
"""
Experiential Learning System
経験的学習システム

Automatic weight updates when discomfort signal and resolution co-occur.
This is how a 0-year-old learns without supervision:

1. High discomfort signal (from genetic axioms)
2. Specific sensory input (sound, visual, etc.)
3. Discomfort reduces → positive association
4. Cross structure weights automatically update

This is NOT supervised learning.
This is experience-driven, emotion-colored learning.
"""

import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from verantyx_cli.vision.genetic_axioms import GeneticAxioms, HomeostaticVariable
from verantyx_cli.vision.undefined_buffer import UndefinedBuffer, RawExperience
from verantyx_cli.vision.cross_neural_network import CrossNeuralNetwork


@dataclass
class LearningEvent:
    """学習イベント（不快感-解決の共起）"""
    discomfort_before: float
    discomfort_after: float
    experience_id: int
    resolution_type: str
    weight_delta: float
    timestamp: float


class ExperientialLearner:
    """
    経験的学習器

    0歳児の学習メカニズム:
    - 教師信号なし
    - 不快感の変化が唯一の信号
    - Cross構造の重みが自動更新
    """

    def __init__(
        self,
        genetic_axioms: GeneticAxioms,
        undefined_buffer: UndefinedBuffer,
        cross_network: Optional[CrossNeuralNetwork] = None
    ):
        """
        Initialize experiential learner

        Args:
            genetic_axioms: 遺伝子公理
            undefined_buffer: 未定義バッファ
            cross_network: Cross neural network（オプション）
        """
        self.axioms = genetic_axioms
        self.buffer = undefined_buffer
        self.network = cross_network

        # 学習履歴
        self.learning_events: List[LearningEvent] = []

        # 現在の不快感（学習判定用）
        self.current_discomfort = 0.0
        self.previous_experience_id: Optional[int] = None

        # 学習パラメータ
        self.learning_rate = 0.01
        self.discomfort_threshold = 0.3  # これ以上の不快感で学習開始
        self.resolution_threshold = 0.5  # これ以上の改善で強化

        print("🎓 Experiential Learner initialized")
        print(f"   Learning rate: {self.learning_rate}")
        print(f"   Discomfort threshold: {self.discomfort_threshold}")

    def observe_and_learn(
        self,
        cross_structure: Dict[str, Any],
        sensory_context: Optional[Dict[str, Any]] = None
    ) -> Optional[LearningEvent]:
        """
        観察して学習

        1. 現在の不快感を取得
        2. 経験をバッファに保存
        3. 前回から改善があれば学習

        Args:
            cross_structure: Cross構造
            sensory_context: 感覚コンテキスト

        Returns:
            学習イベント（学習が発生した場合）
        """
        # 現在の不快感
        discomfort_info = self.axioms.calculate_total_discomfort()
        current_discomfort = discomfort_info["total"]

        # 経験を保存
        experience_id = self.buffer.store_experience(
            cross_structure=cross_structure,
            discomfort_signal=current_discomfort,
            sensory_context=sensory_context
        )

        learning_event = None

        # 前回の経験があり、不快感が高かった場合
        if self.previous_experience_id is not None and self.current_discomfort > self.discomfort_threshold:
            # 不快感の変化をチェック
            discomfort_change = self.current_discomfort - current_discomfort

            # 改善があった場合（不快感が減少）
            if discomfort_change > self.resolution_threshold:
                # 学習イベント発生
                learning_event = self._create_learning_event(
                    discomfort_before=self.current_discomfort,
                    discomfort_after=current_discomfort,
                    experience_id=experience_id,
                    resolution_type="discomfort_reduction"
                )

                # 前回の経験に「解決」を記録
                self.buffer.mark_resolution(
                    experience_id=self.previous_experience_id,
                    resolution="reduced_by_current_input"
                )

                # Cross構造の重みを更新
                if self.network is not None:
                    self._update_weights(
                        experience_id=experience_id,
                        discomfort_change=discomfort_change
                    )

                self.learning_events.append(learning_event)

        # 状態を更新
        self.current_discomfort = current_discomfort
        self.previous_experience_id = experience_id

        return learning_event

    def detect_pattern_and_learn(
        self,
        pattern_name: str,
        experience_ids: List[int]
    ) -> bool:
        """
        パターンを検出して学習

        複数の経験から共通パターンを発見し、
        それに基づいて重みを調整。

        Args:
            pattern_name: パターン名
            experience_ids: 経験IDリスト

        Returns:
            学習成功したか
        """
        if not experience_ids or self.network is None:
            return False

        # 経験を取得
        experiences = [
            self.buffer.experiences[exp_id]
            for exp_id in experience_ids
            if exp_id in self.buffer.experiences
        ]

        if not experiences:
            return False

        # 平均的な不快感変化を計算
        discomfort_changes = []
        for exp in experiences:
            if exp.resolution is not None:
                # 解決があった経験のみ
                discomfort_changes.append(1.0 - exp.discomfort_signal)

        if not discomfort_changes:
            return False

        avg_improvement = np.mean(discomfort_changes)

        # パターンの特徴署名を抽出
        signatures = [
            self.buffer._extract_signature(exp.cross_structure)
            for exp in experiences
        ]
        pattern_signature = np.mean(signatures, axis=0)

        # 重みを更新（パターンに基づく）
        self._update_weights_by_pattern(
            pattern_signature=pattern_signature,
            reinforcement=avg_improvement
        )

        # バッファに意味を付与
        self.buffer.assign_meaning(
            experience_ids=experience_ids,
            meaning=pattern_name
        )

        return True

    def _create_learning_event(
        self,
        discomfort_before: float,
        discomfort_after: float,
        experience_id: int,
        resolution_type: str
    ) -> LearningEvent:
        """学習イベントを作成"""
        import time

        # 不快感の改善度 = 重みの変化量
        improvement = discomfort_before - discomfort_after
        weight_delta = self.learning_rate * improvement

        return LearningEvent(
            discomfort_before=discomfort_before,
            discomfort_after=discomfort_after,
            experience_id=experience_id,
            resolution_type=resolution_type,
            weight_delta=weight_delta,
            timestamp=time.time()
        )

    def _update_weights(
        self,
        experience_id: int,
        discomfort_change: float
    ):
        """
        重みを更新

        不快感の改善度に基づいて、Cross構造の重みを強化。

        Args:
            experience_id: 経験ID
            discomfort_change: 不快感の変化（正なら改善）
        """
        if experience_id not in self.buffer.experiences:
            return

        experience = self.buffer.experiences[experience_id]

        # Cross構造から特徴を抽出
        signature = self.buffer._extract_signature(experience.cross_structure)

        # 改善度に基づく強化量
        reinforcement = self.learning_rate * discomfort_change

        # Cross Neural Networkの出力層の重みを調整
        # （簡略版: Layer4の活性化を強化）
        if hasattr(self.network, 'layers') and len(self.network.layers) > 0:
            output_layer = self.network.layers[-1]

            # 各点の重みを調整
            for point in output_layer.points[:min(10, len(output_layer.points))]:
                for connection in point.connections:
                    # 正の強化
                    connection.weight += reinforcement * 0.1

                    # クリップ
                    connection.weight = np.clip(connection.weight, -5.0, 5.0)

    def _update_weights_by_pattern(
        self,
        pattern_signature: np.ndarray,
        reinforcement: float
    ):
        """
        パターンに基づいて重みを更新

        Args:
            pattern_signature: パターン特徴
            reinforcement: 強化量
        """
        if self.network is None:
            return

        # 出力層の重みを調整
        if hasattr(self.network, 'layers') and len(self.network.layers) > 0:
            output_layer = self.network.layers[-1]

            for point in output_layer.points[:min(20, len(output_layer.points))]:
                for connection in point.connections:
                    # パターンに基づく重み更新
                    connection.weight += self.learning_rate * reinforcement * 0.05
                    connection.weight = np.clip(connection.weight, -5.0, 5.0)

    def get_learning_summary(self) -> Dict[str, Any]:
        """学習の要約を取得"""
        if not self.learning_events:
            return {
                "total_learning_events": 0,
                "average_improvement": 0.0,
                "total_weight_change": 0.0
            }

        total_events = len(self.learning_events)
        improvements = [
            event.discomfort_before - event.discomfort_after
            for event in self.learning_events
        ]
        avg_improvement = np.mean(improvements)

        total_weight_change = sum(event.weight_delta for event in self.learning_events)

        return {
            "total_learning_events": total_events,
            "average_improvement": avg_improvement,
            "total_weight_change": total_weight_change,
            "recent_events": self.learning_events[-5:]  # 最新5件
        }


class ZeroYearOldModel:
    """
    0歳児モデル

    統合されたシステム:
    - 遺伝子公理（恒常性維持）
    - 未定義バッファ（生の記憶）
    - 経験的学習（自動重み更新）
    - Cross Neural Network（情報処理）
    """

    def __init__(self):
        """Initialize 0-year-old model"""
        print()
        print("=" * 70)
        print("👶 0歳児モデル初期化中...")
        print("=" * 70)
        print()

        # 遺伝子公理
        self.axioms = GeneticAxioms()
        print("✅ 遺伝子公理: 恒常性維持システム起動")

        # 未定義バッファ
        self.buffer = UndefinedBuffer(max_buffer_size=10000)
        print("✅ 未定義バッファ: 記憶システム起動")

        # 経験的学習器
        self.learner = ExperientialLearner(
            genetic_axioms=self.axioms,
            undefined_buffer=self.buffer,
            cross_network=None  # 後でセット
        )
        print("✅ 経験的学習器: 学習システム起動")

        # Cross Neural Network（オプション）
        self.network: Optional[CrossNeuralNetwork] = None

        print()
        print("=" * 70)
        print("👶 0歳児モデル起動完了")
        print("=" * 70)
        print()
        print("【機能】")
        print("  1. 遺伝子に刻まれた恒常性維持")
        print("  2. 未解釈の生経験を記憶")
        print("  3. 不快感-解決の共起で自動学習")
        print("  4. 後から意味が付与される")
        print()

    def set_cross_network(self, network: CrossNeuralNetwork):
        """Cross Neural Networkをセット"""
        self.network = network
        self.learner.network = network
        print(f"✅ Cross Neural Network connected: {len(network.all_points):,} neurons")

    def experience(
        self,
        cross_structure: Dict[str, Any],
        sensory_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        経験する

        Args:
            cross_structure: Cross構造
            sensory_context: 感覚コンテキスト

        Returns:
            経験結果
        """
        # 観察して学習
        learning_event = self.learner.observe_and_learn(
            cross_structure=cross_structure,
            sensory_context=sensory_context
        )

        # 不快感チェック
        discomfort_info = self.axioms.calculate_total_discomfort()

        # 生存反射
        reflex = self.axioms.get_survival_reflex()

        return {
            "discomfort": discomfort_info,
            "reflex": reflex,
            "learning_event": learning_event,
            "alive": self.axioms.is_alive()
        }

    def simulate_homeostatic_change(
        self,
        variable: str,
        new_value: float
    ):
        """
        恒常性変数を変更（シミュレーション用）

        Args:
            variable: 変数名
            new_value: 新しい値
        """
        from verantyx_cli.vision.genetic_axioms import HomeostaticVariable

        var_map = {
            "temperature": HomeostaticVariable.TEMPERATURE,
            "energy": HomeostaticVariable.ENERGY,
            "pain": HomeostaticVariable.PAIN,
            "oxygen": HomeostaticVariable.OXYGEN
        }

        if variable in var_map:
            self.axioms.update_state(var_map[variable], new_value)

    def get_status(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        return {
            "axioms": {
                "alive": self.axioms.is_alive(),
                "discomfort": self.axioms.calculate_total_discomfort(),
                "state": self.axioms.current_state
            },
            "buffer": self.buffer.get_statistics(),
            "learning": self.learner.get_learning_summary()
        }
