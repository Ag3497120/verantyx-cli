#!/usr/bin/env python3
"""
Adaptive Resolution Controller
適応的解像度コントローラ

動画の状態遷移を検出し、解像度を動的に調整する。
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TransitionInfo:
    """状態遷移情報"""
    is_transition: bool
    transition_magnitude: float  # 0.0 〜 1.0
    transition_type: str  # "sudden", "moderate", "gradual", "none"
    axis_changes: Dict[str, float]
    affected_regions: list = None


class AdaptiveResolutionController:
    """適応的解像度コントローラ"""

    # 解像度レベルと最大点数のマッピング
    RESOLUTION_LEVELS = {
        "very_low": 10000,
        "low": 50000,
        "medium": 100000,
        "high": 200000,
        "very_high": 500000,
        "ultra": 1000000
    }

    def __init__(self, initial_level: str = "low"):
        """
        Initialize controller

        Args:
            initial_level: 初期解像度レベル
        """
        self.current_level = initial_level
        self.transition_active = False
        self.transition_start_frame = None
        self.history = []

    def detect_transition(
        self,
        prev_frame_cross: Dict[str, Any],
        curr_frame_cross: Dict[str, Any]
    ) -> TransitionInfo:
        """
        フレーム間の状態遷移を検出

        Args:
            prev_frame_cross: 前フレームのCross構造
            curr_frame_cross: 現在フレームのCross構造

        Returns:
            遷移情報
        """
        if not prev_frame_cross or not curr_frame_cross:
            return TransitionInfo(
                is_transition=False,
                transition_magnitude=0.0,
                transition_type="none",
                axis_changes={}
            )

        # 各軸の変化を計算
        prev_axes = prev_frame_cross.get("axes", {})
        curr_axes = curr_frame_cross.get("axes", {})

        axis_changes = {}

        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
            prev_data = prev_axes.get(axis_name, {})
            curr_data = curr_axes.get(axis_name, {})

            prev_mean = prev_data.get("mean", 0.5)
            curr_mean = curr_data.get("mean", 0.5)

            change = abs(curr_mean - prev_mean)
            axis_changes[axis_name] = change

        # 総変化量を計算
        total_change = sum(axis_changes.values())

        # 遷移タイプを判定
        if total_change > 0.5:
            transition_type = "sudden"
            is_transition = True
        elif total_change > 0.3:
            transition_type = "moderate"
            is_transition = True
        elif total_change > 0.1:
            transition_type = "gradual"
            is_transition = True
        else:
            transition_type = "none"
            is_transition = False

        return TransitionInfo(
            is_transition=is_transition,
            transition_magnitude=total_change,
            transition_type=transition_type,
            axis_changes=axis_changes
        )

    def update(
        self,
        transition_info: TransitionInfo,
        frame_number: int
    ) -> str:
        """
        遷移情報に基づいて解像度レベルを更新

        Args:
            transition_info: 遷移情報
            frame_number: 現在のフレーム番号

        Returns:
            新しい解像度レベル
        """
        previous_level = self.current_level

        if not transition_info.is_transition:
            # 遷移なし
            if self.transition_active:
                # 遷移が終了 → 解像度を下げる
                self.current_level = self._decrease_level()
                self.transition_active = False
                self.transition_start_frame = None

            # 変化なし
            return self.current_level

        # 遷移あり
        if not self.transition_active:
            self.transition_active = True
            self.transition_start_frame = frame_number

        magnitude = transition_info.transition_magnitude

        # 変化の大きさに応じて解像度を決定
        if magnitude > 0.5:
            self.current_level = "ultra"  # 1,000,000点
        elif magnitude > 0.3:
            self.current_level = "very_high"  # 500,000点
        elif magnitude > 0.2:
            self.current_level = "high"  # 200,000点
        else:
            self.current_level = "medium"  # 100,000点

        # 履歴に記録
        self.history.append({
            "frame": frame_number,
            "prev_level": previous_level,
            "new_level": self.current_level,
            "transition_type": transition_info.transition_type,
            "magnitude": transition_info.transition_magnitude
        })

        return self.current_level

    def _decrease_level(self) -> str:
        """解像度レベルを1段階下げる"""
        level_order = ["ultra", "very_high", "high", "medium", "low", "very_low"]

        try:
            current_index = level_order.index(self.current_level)
            if current_index < len(level_order) - 1:
                return level_order[current_index + 1]
        except ValueError:
            pass

        return "low"

    def get_max_points(self, level: Optional[str] = None) -> int:
        """
        解像度レベルの最大点数を取得

        Args:
            level: 解像度レベル（Noneの場合は現在のレベル）

        Returns:
            最大点数
        """
        if level is None:
            level = self.current_level

        return self.RESOLUTION_LEVELS.get(level, 50000)

    def get_state(self) -> Dict[str, Any]:
        """
        現在の状態を取得

        Returns:
            状態情報
        """
        return {
            "resolution_level": self.current_level,
            "max_points": self.get_max_points(),
            "transition_active": self.transition_active,
            "transition_start_frame": self.transition_start_frame,
            "history_count": len(self.history)
        }

    def print_summary(self):
        """サマリーを表示"""
        print("\n" + "=" * 60)
        print("適応的解像度コントローラ サマリー")
        print("=" * 60)
        print(f"現在のレベル: {self.current_level}")
        print(f"最大点数: {self.get_max_points():,}")
        print(f"遷移アクティブ: {self.transition_active}")
        print(f"解像度変更回数: {len(self.history)}")

        if self.history:
            print("\n最近の解像度変更:")
            for entry in self.history[-5:]:
                print(f"  フレーム {entry['frame']}: "
                      f"{entry['prev_level']} → {entry['new_level']} "
                      f"({entry['transition_type']}, {entry['magnitude']:.3f})")

        print("=" * 60 + "\n")
