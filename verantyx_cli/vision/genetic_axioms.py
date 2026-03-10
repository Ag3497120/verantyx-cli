#!/usr/bin/env python3
"""
Genetic Axioms - DNA-Encoded Initial Parameters
遺伝子に刻まれた初期パラメータ

These are the ABSOLUTE axioms encoded in DNA:
- Homeostasis maintenance (temperature, energy, pain thresholds)
- Survival reflexes (breathing, heartbeat, crying)
- Initial "color" as scalar variance/deviation

These run constantly on the Neural Engine and cannot be overridden.
"""

import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class HomeostaticVariable(Enum):
    """恒常性を維持すべき変数"""
    TEMPERATURE = "temperature"
    ENERGY = "energy"
    PAIN = "pain"
    OXYGEN = "oxygen"


@dataclass
class HomeostaticTarget:
    """恒常性の目標値と許容範囲"""
    target: float           # 目標値
    min_threshold: float    # 最小閾値
    max_threshold: float    # 最大閾値
    critical_min: float     # 臨界最小値（死の危険）
    critical_max: float     # 臨界最大値（死の危険）


class GeneticAxioms:
    """
    遺伝子に刻まれた公理

    これらは生まれつき持っているもので、学習では変わらない。
    - 恒常性の維持
    - 生存反射
    - 初期の「色」（不快感の強度）
    """

    def __init__(self):
        """Initialize genetic axioms"""

        # 恒常性の目標値（DNA-encoded）
        self.homeostatic_targets = {
            HomeostaticVariable.TEMPERATURE: HomeostaticTarget(
                target=37.0,        # 37°C
                min_threshold=36.0,
                max_threshold=38.0,
                critical_min=35.0,
                critical_max=40.0
            ),
            HomeostaticVariable.ENERGY: HomeostaticTarget(
                target=100.0,
                min_threshold=30.0,
                max_threshold=100.0,
                critical_min=0.0,
                critical_max=150.0
            ),
            HomeostaticVariable.PAIN: HomeostaticTarget(
                target=0.0,
                min_threshold=0.0,
                max_threshold=10.0,
                critical_min=0.0,
                critical_max=100.0
            ),
            HomeostaticVariable.OXYGEN: HomeostaticTarget(
                target=100.0,
                min_threshold=90.0,
                max_threshold=100.0,
                critical_min=70.0,
                critical_max=100.0
            )
        }

        # 現在の状態
        self.current_state = {
            HomeostaticVariable.TEMPERATURE: 37.0,
            HomeostaticVariable.ENERGY: 100.0,
            HomeostaticVariable.PAIN: 0.0,
            HomeostaticVariable.OXYGEN: 100.0
        }

        # 不快感の履歴（学習用）
        self.discomfort_history = []

    def calculate_discomfort(self, variable: HomeostaticVariable) -> float:
        """
        不快感を計算（スカラー値）

        ΔS = |S_target - S_current|

        Args:
            variable: 恒常性変数

        Returns:
            不快感の強度（0.0 = なし、1.0 = 最大）
        """
        current = self.current_state[variable]
        target_spec = self.homeostatic_targets[variable]

        # 目標値からのズレ
        deviation = abs(target_spec.target - current)

        # 正常範囲内なら不快感なし
        if target_spec.min_threshold <= current <= target_spec.max_threshold:
            return 0.0

        # 臨界値を超えたら最大不快感
        if current <= target_spec.critical_min or current >= target_spec.critical_max:
            return 1.0

        # それ以外は線形に増加
        if current < target_spec.min_threshold:
            # 下限を下回る場合
            range_size = target_spec.min_threshold - target_spec.critical_min
            discomfort = deviation / range_size
        else:
            # 上限を超える場合
            range_size = target_spec.critical_max - target_spec.max_threshold
            discomfort = deviation / range_size

        return np.clip(discomfort, 0.0, 1.0)

    def calculate_total_discomfort(self) -> Dict[str, Any]:
        """
        全体の不快感を計算

        Returns:
            {
                "total": 総不快感,
                "details": 各変数の不快感,
                "critical": 臨界状態か
            }
        """
        discomfort_details = {}
        total_discomfort = 0.0
        critical = False

        for variable in HomeostaticVariable:
            discomfort = self.calculate_discomfort(variable)
            discomfort_details[variable.value] = {
                "current": self.current_state[variable],
                "target": self.homeostatic_targets[variable].target,
                "discomfort": discomfort
            }

            # 重み付けで合計（エネルギーと酸素は特に重要）
            if variable in [HomeostaticVariable.ENERGY, HomeostaticVariable.OXYGEN]:
                total_discomfort += discomfort * 2.0
            else:
                total_discomfort += discomfort

            # 臨界状態チェック
            current = self.current_state[variable]
            target_spec = self.homeostatic_targets[variable]
            if current <= target_spec.critical_min or current >= target_spec.critical_max:
                critical = True

        # 正規化
        total_discomfort = total_discomfort / 6.0  # 4変数、2つは重み2倍

        return {
            "total": total_discomfort,
            "details": discomfort_details,
            "critical": critical
        }

    def update_state(self, variable: HomeostaticVariable, value: float):
        """
        状態を更新

        Args:
            variable: 変数
            value: 新しい値
        """
        self.current_state[variable] = value

        # 不快感を記録
        discomfort = self.calculate_discomfort(variable)
        if discomfort > 0.0:
            self.discomfort_history.append({
                "variable": variable.value,
                "value": value,
                "discomfort": discomfort,
                "timestamp": len(self.discomfort_history)
            })

    def get_survival_reflex(self) -> Optional[str]:
        """
        生存反射を取得

        DNA-encoded reflexes that activate automatically.

        Returns:
            反射の種類（"cry", "breathe", "sleep" など）
        """
        total_discomfort = self.calculate_total_discomfort()

        # 臨界状態 → 泣く
        if total_discomfort["critical"]:
            return "cry_critical"

        # 強い不快感 → 泣く
        if total_discomfort["total"] > 0.7:
            return "cry"

        # エネルギー不足 → 眠る
        if self.current_state[HomeostaticVariable.ENERGY] < 30.0:
            return "sleep"

        # 酸素不足 → 深呼吸
        if self.current_state[HomeostaticVariable.OXYGEN] < 90.0:
            return "breathe_deep"

        # 痛み → 回避
        if self.current_state[HomeostaticVariable.PAIN] > 10.0:
            return "avoid"

        return None

    def is_alive(self) -> bool:
        """
        生存しているか

        Returns:
            True if alive
        """
        # エネルギーまたは酸素が臨界値以下なら死亡
        if self.current_state[HomeostaticVariable.ENERGY] <= 0.0:
            return False
        if self.current_state[HomeostaticVariable.OXYGEN] <= 70.0:
            return False

        return True

    def get_initial_color(self) -> float:
        """
        初期の「色」を取得

        0歳児の「色」は複雑な感情ではなく、単純な不快感の強度。

        Returns:
            色の強度（0.0 = neutral, 1.0 = maximum discomfort）
        """
        total_discomfort = self.calculate_total_discomfort()
        return total_discomfort["total"]

    def reset_to_healthy_state(self):
        """健康な状態にリセット"""
        for variable in HomeostaticVariable:
            self.current_state[variable] = self.homeostatic_targets[variable].target


class DiscomfortSignalMonitor:
    """
    不快感信号モニター（Neural Engineで常時実行）

    ハードウェア接続された監視層として機能。
    恒常性のズレを常にチェックし、システム全体に割り込み信号を送る。
    """

    def __init__(self, genetic_axioms: GeneticAxioms):
        """
        Initialize monitor

        Args:
            genetic_axioms: 遺伝子公理
        """
        self.axioms = genetic_axioms
        self.monitoring = True
        self.interrupt_threshold = 0.3  # この値を超えたら割り込み

    def check_and_interrupt(self) -> Optional[Dict[str, Any]]:
        """
        チェックして必要なら割り込み信号を送る

        Returns:
            割り込み信号（Noneなら正常）
        """
        if not self.monitoring:
            return None

        # 生存チェック
        if not self.axioms.is_alive():
            return {
                "type": "death",
                "message": "Critical homeostatic failure"
            }

        # 不快感チェック
        discomfort = self.axioms.calculate_total_discomfort()

        if discomfort["total"] > self.interrupt_threshold:
            # 生存反射を取得
            reflex = self.axioms.get_survival_reflex()

            return {
                "type": "discomfort_interrupt",
                "discomfort": discomfort["total"],
                "details": discomfort["details"],
                "reflex": reflex,
                "color": self.axioms.get_initial_color()
            }

        return None

    def simulate_step(self, time_delta: float = 1.0):
        """
        シミュレーションの1ステップ

        Args:
            time_delta: 時間経過（秒）
        """
        # エネルギー消費（基礎代謝）
        current_energy = self.axioms.current_state[HomeostaticVariable.ENERGY]
        new_energy = current_energy - 0.1 * time_delta
        self.axioms.update_state(HomeostaticVariable.ENERGY, new_energy)

        # 酸素消費（呼吸）
        current_oxygen = self.axioms.current_state[HomeostaticVariable.OXYGEN]
        new_oxygen = current_oxygen - 0.05 * time_delta
        self.axioms.update_state(HomeostaticVariable.OXYGEN, new_oxygen)

        # 痛みは自然治癒
        current_pain = self.axioms.current_state[HomeostaticVariable.PAIN]
        new_pain = max(0.0, current_pain - 0.5 * time_delta)
        self.axioms.update_state(HomeostaticVariable.PAIN, new_pain)
