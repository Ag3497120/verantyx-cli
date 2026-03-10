#!/usr/bin/env python3
"""
Cognitive Discomfort Processors
認知的不快感システムのPythonプロセッサ
"""

from typing import Dict, Any, List
import math


class CognitiveDiscomfortSystem:
    """
    認知的不快感システム

    「分からない」「予測が外れた」は不快
    「分かった」「予測が当たった」は快
    """

    def __init__(self):
        """Initialize"""
        self.discomfort = {
            "prediction_error_discomfort": 0.0,
            "novelty_discomfort": 0.0,
            "complexity_discomfort": 0.0,
            "sync_failure_discomfort": 0.0,
            "total_cognitive_discomfort": 0.0
        }

        self.pleasure = {
            "prediction_success_pleasure": 0.0,
            "understanding_pleasure": 0.0,
            "synchronization_pleasure": 0.0,
            "compression_pleasure": 0.0,
            "total_cognitive_pleasure": 0.0
        }

    def calculate_prediction_error_discomfort(self, prediction_error: float) -> float:
        """
        予測誤差不快感

        Args:
            prediction_error: 予測誤差 (0.0-1.0)

        Returns:
            不快感 (0.0-1.0)
        """
        if prediction_error < 0.05:
            # ほぼ予測通り
            return 0.0

        if prediction_error > 0.5:
            # 大きく外れた
            return 1.0

        # 線形
        discomfort = prediction_error * 2.0
        return max(0.0, min(1.0, discomfort))

    def calculate_novelty_discomfort(self, similar_experiences_count: int) -> float:
        """
        未知性不快感

        Args:
            similar_experiences_count: 類似経験の数

        Returns:
            不快感 (0.0-1.0)
        """
        if similar_experiences_count == 0:
            # 全く未知
            return 1.0

        if similar_experiences_count >= 10:
            # 十分な経験
            return 0.0

        # 逆比例
        discomfort = 1.0 - (similar_experiences_count / 10.0)
        return max(0.0, min(1.0, discomfort))

    def calculate_complexity_discomfort(self, total_points: int) -> float:
        """
        複雑性不快感

        Args:
            total_points: Cross構造の総点数

        Returns:
            不快感 (0.0-1.0)
        """
        if total_points < 3000:
            # シンプル
            return 0.0

        if total_points > 10000:
            # 超複雑
            return 1.0

        # 線形
        complexity = (total_points - 3000) / 7000.0
        return max(0.0, min(1.0, complexity))

    def calculate_sync_failure_discomfort(self, sync_failure: float) -> float:
        """
        同調失敗不快感

        Args:
            sync_failure: 同調失敗度 (0.0-1.0)

        Returns:
            不快感 (0.0-1.0)
        """
        if sync_failure < 0.3:
            # ある程度同調できた
            return 0.0

        if sync_failure > 0.8:
            # 全く同調できない
            return 1.0

        # 線形
        discomfort = (sync_failure - 0.3) / 0.5
        return max(0.0, min(1.0, discomfort))

    def calculate_total_cognitive_discomfort(
        self,
        cross_structure: Dict[str, Any],
        prediction_error: float,
        similar_experiences_count: int,
        sync_failure: float
    ) -> float:
        """
        総認知不快感を計算

        Args:
            cross_structure: Cross構造
            prediction_error: 予測誤差
            similar_experiences_count: 類似経験数
            sync_failure: 同調失敗度

        Returns:
            総認知不快感 (0.0-1.0)
        """
        # 各不快感を計算
        pred_discomfort = self.calculate_prediction_error_discomfort(prediction_error)
        novelty_discomfort = self.calculate_novelty_discomfort(similar_experiences_count)
        complexity_discomfort = self.calculate_complexity_discomfort(
            cross_structure['metadata']['total_points']
        )
        sync_discomfort = self.calculate_sync_failure_discomfort(sync_failure)

        # 重み付け平均
        total_discomfort = (
            pred_discomfort * 0.4 +
            novelty_discomfort * 0.3 +
            complexity_discomfort * 0.2 +
            sync_discomfort * 0.1
        )

        # 状態を更新
        self.discomfort["prediction_error_discomfort"] = pred_discomfort
        self.discomfort["novelty_discomfort"] = novelty_discomfort
        self.discomfort["complexity_discomfort"] = complexity_discomfort
        self.discomfort["sync_failure_discomfort"] = sync_discomfort
        self.discomfort["total_cognitive_discomfort"] = total_discomfort

        return total_discomfort

    def calculate_prediction_success_pleasure(self, prediction_error: float) -> float:
        """予測成功快感"""
        if prediction_error < 0.05:
            return 1.0

        if prediction_error > 0.3:
            return 0.0

        pleasure = 1.0 - (prediction_error / 0.3)
        return max(0.0, min(1.0, pleasure))

    def calculate_understanding_pleasure(self, similar_experiences_count: int) -> float:
        """理解快感"""
        if similar_experiences_count >= 5:
            return 1.0

        if similar_experiences_count == 0:
            return 0.0

        pleasure = similar_experiences_count / 5.0
        return max(0.0, min(1.0, pleasure))

    def calculate_synchronization_pleasure(self, sync_degree: float) -> float:
        """同調快感"""
        if sync_degree > 0.8:
            return 1.0

        if sync_degree < 0.3:
            return 0.0

        pleasure = (sync_degree - 0.3) / 0.5
        return max(0.0, min(1.0, pleasure))

    def calculate_total_cognitive_pleasure(
        self,
        prediction_error: float,
        similar_experiences_count: int,
        sync_degree: float
    ) -> float:
        """
        総認知快感を計算

        Args:
            prediction_error: 予測誤差
            similar_experiences_count: 類似経験数
            sync_degree: 同調度

        Returns:
            総認知快感 (0.0-1.0)
        """
        pred_pleasure = self.calculate_prediction_success_pleasure(prediction_error)
        understanding_pleasure = self.calculate_understanding_pleasure(similar_experiences_count)
        sync_pleasure = self.calculate_synchronization_pleasure(sync_degree)

        total_pleasure = (
            pred_pleasure * 0.5 +
            understanding_pleasure * 0.3 +
            sync_pleasure * 0.2
        )

        self.pleasure["prediction_success_pleasure"] = pred_pleasure
        self.pleasure["understanding_pleasure"] = understanding_pleasure
        self.pleasure["synchronization_pleasure"] = sync_pleasure
        self.pleasure["total_cognitive_pleasure"] = total_pleasure

        return total_pleasure

    def calculate_total_discomfort(
        self,
        physiological_discomfort: float,
        cognitive_discomfort: float,
        developmental_stage: str
    ) -> float:
        """
        総合不快感（生理的 + 認知的）

        Args:
            physiological_discomfort: 生理的不快感
            cognitive_discomfort: 認知的不快感
            developmental_stage: 発達段階

        Returns:
            総合不快感 (0.0-1.0)
        """
        # 発達段階に応じて重み付け
        if developmental_stage == "0歳_新生児":
            # 0歳: 認知的不快が強い
            total = (physiological_discomfort * 0.3) + (cognitive_discomfort * 0.7)
        elif developmental_stage == "1歳_立位":
            # 1歳: まだ認知的不快が強い
            total = (physiological_discomfort * 0.4) + (cognitive_discomfort * 0.6)
        elif developmental_stage == "3歳_歩行":
            # 3歳: バランス
            total = (physiological_discomfort * 0.5) + (cognitive_discomfort * 0.5)
        else:
            # 7歳以降: 生理的不快がより重要
            total = (physiological_discomfort * 0.6) + (cognitive_discomfort * 0.4)

        return max(0.0, min(1.0, total))

    def determine_discomfort_resolution_action(self) -> Dict[str, Any]:
        """
        不快感解消アクションを決定

        Returns:
            アクション情報
        """
        # 最も不快な要素を特定
        max_discomfort = 0.0
        max_type = "none"

        if self.discomfort["prediction_error_discomfort"] > max_discomfort:
            max_discomfort = self.discomfort["prediction_error_discomfort"]
            max_type = "prediction_error"

        if self.discomfort["novelty_discomfort"] > max_discomfort:
            max_discomfort = self.discomfort["novelty_discomfort"]
            max_type = "novelty"

        if self.discomfort["complexity_discomfort"] > max_discomfort:
            max_discomfort = self.discomfort["complexity_discomfort"]
            max_type = "complexity"

        if self.discomfort["sync_failure_discomfort"] > max_discomfort:
            max_discomfort = self.discomfort["sync_failure_discomfort"]
            max_type = "sync_failure"

        # アクション決定
        actions = {
            "prediction_error": {
                "action": "予測モデルを更新",
                "reason": "予測が外れて不快",
                "priority": max_discomfort
            },
            "novelty": {
                "action": "類似経験を探す",
                "reason": "未知で不安",
                "priority": max_discomfort
            },
            "complexity": {
                "action": "単純化・分解",
                "reason": "複雑すぎて理解できない",
                "priority": max_discomfort
            },
            "sync_failure": {
                "action": "新しいパターンとして記憶",
                "reason": "既存パターンに当てはまらない",
                "priority": max_discomfort
            },
            "none": {
                "action": "なし",
                "reason": "不快なし",
                "priority": 0.0
            }
        }

        return actions[max_type]

    def get_status(self) -> Dict[str, Any]:
        """状態を取得"""
        return {
            "不快感": {
                "予測誤差不快": self.discomfort["prediction_error_discomfort"],
                "未知性不快": self.discomfort["novelty_discomfort"],
                "複雑性不快": self.discomfort["complexity_discomfort"],
                "同調失敗不快": self.discomfort["sync_failure_discomfort"],
                "総認知不快": self.discomfort["total_cognitive_discomfort"]
            },
            "快感": {
                "予測成功快": self.pleasure["prediction_success_pleasure"],
                "理解快": self.pleasure["understanding_pleasure"],
                "同調快": self.pleasure["synchronization_pleasure"],
                "総認知快": self.pleasure["total_cognitive_pleasure"]
            }
        }
