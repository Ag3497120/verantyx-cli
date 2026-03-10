#!/usr/bin/env python3
"""
Verantyx Survival Processors
生存システムプロセッサ

エネルギー、痛み、死の概念を実装。
"""

from typing import Dict, Any, Optional
from datetime import datetime


class SurvivalState:
    """生存状態"""

    def __init__(self):
        """Initialize survival state"""
        # エネルギー
        self.energy = {
            "max": 100.0,
            "current": 100.0,
            "consumption_rates": {
                "metabolism": -0.1,   # 基礎代謝
                "observe": -0.2,      # 観測
                "think": -0.5,        # 思考
                "act": -1.0,          # 行動
                "learn": -2.0         # 学習
            },
            "thresholds": {
                "healthy": (70, 100),
                "hungry": (30, 70),
                "critical": (10, 30),
                "dying": (0, 10)
            }
        }

        # 痛み
        self.pain = {
            "max": 100.0,
            "current": 0.0,
            "causes": {
                "collision": 20.0,
                "overload": 10.0,
                "data_corruption": 50.0,
                "energy_depletion": 30.0
            },
            "recovery_rates": {
                "natural": -0.5,
                "rest": -2.0,
                "repair": -5.0
            }
        }

        # 体温
        self.temperature = {
            "optimal": 37.0,
            "current": 37.0,
            "range": (35.0, 39.0)
        }

        # 生存状態
        self.status = "alive"  # alive, dying, dead

        # 統計
        self.stats = {
            "total_energy_consumed": 0.0,
            "total_pain_experienced": 0.0,
            "deaths": 0,
            "frames_alive": 0
        }

    def is_alive(self) -> bool:
        """生きているか"""
        return self.status == "alive"

    def is_dying(self) -> bool:
        """瀕死か"""
        return self.status == "dying"

    def is_dead(self) -> bool:
        """死亡しているか"""
        return self.status == "dead"


class EnergyProcessor:
    """エネルギー管理プロセッサ"""

    def __init__(self, survival_state: SurvivalState):
        """
        Initialize energy processor

        Args:
            survival_state: 生存状態
        """
        self.state = survival_state

    def consume(self, action_type: str) -> float:
        """
        エネルギーを消費

        Args:
            action_type: 行動タイプ（metabolism, observe, think, act, learn）

        Returns:
            残りエネルギー
        """
        if not self.state.is_alive():
            return 0.0

        rate = self.state.energy["consumption_rates"].get(action_type, 0.0)
        self.state.energy["current"] += rate  # rateは負の値
        self.state.stats["total_energy_consumed"] += abs(rate)

        # 0以下にならないように
        if self.state.energy["current"] < 0:
            self.state.energy["current"] = 0.0

        return self.state.energy["current"]

    def recharge(self, amount: float, source: str = "external") -> float:
        """
        エネルギーを補給

        Args:
            amount: 補給量
            source: 補給源

        Returns:
            現在エネルギー
        """
        if self.state.is_dead():
            return 0.0

        self.state.energy["current"] += amount

        # 最大値を超えないように
        if self.state.energy["current"] > self.state.energy["max"]:
            self.state.energy["current"] = self.state.energy["max"]

        print(f"⚡ エネルギー補給: +{amount:.1f} (from {source})")
        print(f"   現在エネルギー: {self.state.energy['current']:.1f}")

        return self.state.energy["current"]

    def get_energy_level(self) -> str:
        """エネルギーレベルを取得"""
        current = self.state.energy["current"]
        thresholds = self.state.energy["thresholds"]

        for level, (min_val, max_val) in thresholds.items():
            if min_val <= current < max_val:
                return level

        return "unknown"

    def to_cross_axes(self) -> Dict[str, float]:
        """エネルギーをCross軸にマッピング"""
        normalized = self.state.energy["current"] / self.state.energy["max"]

        return {
            "DOWN": normalized,              # エネルギー高い = 安定
            "UP": 1.0 - normalized,          # エネルギー低い = 警戒
            "FRONT": normalized * 0.8        # エネルギーある = 未来志向
        }


class PainProcessor:
    """痛み管理プロセッサ"""

    def __init__(self, survival_state: SurvivalState):
        """
        Initialize pain processor

        Args:
            survival_state: 生存状態
        """
        self.state = survival_state

    def inflict(self, cause: str) -> float:
        """
        痛みを発生させる

        Args:
            cause: 原因（collision, overload, data_corruption, energy_depletion）

        Returns:
            現在痛みレベル
        """
        if self.state.is_dead():
            return 0.0

        amount = self.state.pain["causes"].get(cause, 0.0)
        self.state.pain["current"] += amount
        self.state.stats["total_pain_experienced"] += amount

        # 最大値を超えないように
        if self.state.pain["current"] > self.state.pain["max"]:
            self.state.pain["current"] = self.state.pain["max"]

        print(f"⚠️  痛み発生: {cause} (+{amount:.1f})")
        print(f"   現在痛みレベル: {self.state.pain['current']:.1f}")

        return self.state.pain["current"]

    def recover(self, recovery_type: str = "natural") -> float:
        """
        痛みを回復

        Args:
            recovery_type: 回復タイプ（natural, rest, repair）

        Returns:
            現在痛みレベル
        """
        if self.state.is_dead():
            return 0.0

        rate = self.state.pain["recovery_rates"].get(recovery_type, 0.0)
        self.state.pain["current"] += rate  # rateは負の値

        # 0以下にならないように
        if self.state.pain["current"] < 0:
            self.state.pain["current"] = 0.0

        return self.state.pain["current"]

    def to_cross_axes(self) -> Dict[str, float]:
        """痛みをCross軸にマッピング"""
        normalized = self.state.pain["current"] / self.state.pain["max"]

        return {
            "UP": normalized,              # 痛い = 警戒
            "BACK": normalized,            # 痛い = 回避
            "DOWN": 1.0 - normalized       # 痛い = 不安定
        }


class StatusProcessor:
    """生存状態管理プロセッサ"""

    def __init__(self, survival_state: SurvivalState):
        """
        Initialize status processor

        Args:
            survival_state: 生存状態
        """
        self.state = survival_state

    def check(self) -> str:
        """
        生存状態をチェック

        Returns:
            現在の状態（alive, dying, dead）
        """
        # 死亡条件
        if self.state.energy["current"] <= 0:
            self._die("エネルギー枯渇")
            return "dead"

        if self.state.pain["current"] >= 90 and self.state.energy["current"] < 10:
            self._die("痛みとエネルギー枯渇の複合")
            return "dead"

        # 瀕死条件
        if self.state.energy["current"] <= 10:
            self.state.status = "dying"
            return "dying"

        if self.state.pain["current"] >= 80:
            self.state.status = "dying"
            return "dying"

        # 健康
        self.state.status = "alive"
        if self.state.status == "alive":
            self.state.stats["frames_alive"] += 1

        return "alive"

    def _die(self, reason: str):
        """
        死亡処理

        Args:
            reason: 死亡理由
        """
        self.state.status = "dead"
        self.state.stats["deaths"] += 1

        print()
        print("=" * 70)
        print("💀 Verantyxが死亡しました")
        print("=" * 70)
        print(f"死亡理由: {reason}")
        print(f"エネルギー: {self.state.energy['current']:.1f}")
        print(f"痛み: {self.state.pain['current']:.1f}")
        print(f"生存フレーム数: {self.state.stats['frames_alive']}")
        print(f"総エネルギー消費: {self.state.stats['total_energy_consumed']:.1f}")
        print(f"総痛み経験: {self.state.stats['total_pain_experienced']:.1f}")
        print("=" * 70)
        print()

    def get_cross_structure(self) -> Dict[str, Any]:
        """生存状態をCross構造として取得"""
        if self.state.is_dead():
            # 死亡状態 = 全ての軸が停止（BACK軸のみ残る）
            return {
                "DOWN": 0.0,
                "UP": 0.0,
                "FRONT": 0.0,
                "BACK": 1.0,   # 過去のみ（記憶）
                "RIGHT": 0.0,
                "LEFT": 0.0,
                "status": "dead"
            }

        # 生存中の状態
        return {
            "status": self.state.status,
            "energy_level": EnergyProcessor(self.state).get_energy_level(),
            "pain_level": self.state.pain["current"]
        }


class VerantyxSurvivalSystem:
    """Verantyx生存システム統合"""

    def __init__(self):
        """Initialize survival system"""
        self.survival_state = SurvivalState()
        self.energy = EnergyProcessor(self.survival_state)
        self.pain = PainProcessor(self.survival_state)
        self.status = StatusProcessor(self.survival_state)

        self.frame_count = 0

    def update(self) -> Dict[str, Any]:
        """
        毎フレーム更新

        Returns:
            更新後の状態
        """
        if self.survival_state.is_dead():
            return {"status": "dead"}

        self.frame_count += 1

        # 基礎代謝でエネルギー消費
        self.energy.consume("metabolism")

        # 痛みの自然回復
        self.pain.recover("natural")

        # 状態チェック
        status = self.status.check()

        return {
            "status": status,
            "energy": self.survival_state.energy["current"],
            "pain": self.survival_state.pain["current"],
            "frame": self.frame_count
        }

    def observe(self) -> Dict[str, Any]:
        """
        観測（エネルギー消費）

        Returns:
            観測結果
        """
        if self.survival_state.is_dead():
            return {"error": "dead"}

        self.energy.consume("observe")
        return {"success": True}

    def think(self) -> Dict[str, Any]:
        """
        思考（エネルギー消費大）

        Returns:
            思考結果
        """
        if self.survival_state.is_dead():
            return {"error": "dead"}

        if self.survival_state.energy["current"] < 20:
            return {"error": "insufficient_energy"}

        self.energy.consume("think")
        return {"success": True}

    def learn(self) -> Dict[str, Any]:
        """
        学習（エネルギー消費最大）

        Returns:
            学習結果
        """
        if self.survival_state.is_dead():
            return {"error": "dead"}

        if self.survival_state.energy["current"] < 30:
            return {"error": "insufficient_energy"}

        self.energy.consume("learn")
        return {"success": True}

    def get_cross_axes(self) -> Dict[str, float]:
        """
        生存状態をCross軸にマッピング

        Returns:
            Cross軸の値
        """
        if self.survival_state.is_dead():
            return self.status.get_cross_structure()

        # エネルギーと痛みの軸を統合
        energy_axes = self.energy.to_cross_axes()
        pain_axes = self.pain.to_cross_axes()

        # 統合（両方の影響を受ける）
        return {
            "DOWN": energy_axes["DOWN"] * pain_axes["DOWN"],    # 両方が影響
            "UP": max(energy_axes["UP"], pain_axes["UP"]),      # どちらかが高ければ警戒
            "FRONT": energy_axes["FRONT"] * (1.0 - pain_axes["BACK"]),  # 痛みが回避を促す
            "BACK": pain_axes["BACK"],
            "RIGHT": 0.5,  # 現時点では中立
            "LEFT": 0.5
        }

    def print_status(self):
        """ステータス表示"""
        print()
        print("=" * 70)
        print("📊 Verantyx 生存ステータス")
        print("=" * 70)
        print(f"状態: {self.survival_state.status}")
        print(f"エネルギー: {self.survival_state.energy['current']:.1f}/{self.survival_state.energy['max']}")
        print(f"痛み: {self.survival_state.pain['current']:.1f}")
        print(f"生存フレーム数: {self.survival_state.stats['frames_alive']}")
        print()

        # Cross軸
        axes = self.get_cross_axes()
        print("Cross軸マッピング:")
        for axis_name, value in axes.items():
            if isinstance(value, float):
                bar_length = int(value * 30)
                bar = "█" * bar_length + "░" * (30 - bar_length)
                print(f"  {axis_name:>6}: {bar} {value:.2f}")
        print("=" * 70)
        print()
