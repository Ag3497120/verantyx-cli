#!/usr/bin/env python3
"""
Cross Structure Implementation
Cross構造の実装

Phase 2: Cross構造演算
- 6軸（UP/DOWN/RIGHT/LEFT/FRONT/BACK）の実装
- Cross構造同士の同調計算
- 時間軸での予測
- GPU並列化対応
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import warnings


class CrossStructure:
    """
    Cross構造

    6軸:
    - UP/DOWN: 活性化軸（値の範囲）
    - RIGHT/LEFT: 空間軸（横方向の関係）
    - FRONT/BACK: 時間軸（未来/過去）

    各軸は点の配列として表現される
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None, num_points: int = 260000):
        """
        Initialize

        Args:
            data: .jcrossからパースされたデータ、またはNone
            num_points: 点の総数（デフォルト: 260,000）
        """
        self.num_points = num_points

        if data is None:
            # 空のCross構造を作成
            self.up = np.zeros(num_points, dtype=np.float32)
            self.down = np.zeros(num_points, dtype=np.float32)
            self.right = np.zeros(num_points, dtype=np.float32)
            self.left = np.zeros(num_points, dtype=np.float32)
            self.front = np.zeros(num_points, dtype=np.float32)
            self.back = np.zeros(num_points, dtype=np.float32)
            self.metadata = {}
        else:
            # .jcrossデータから構築
            self._load_from_dict(data)

    def _load_from_dict(self, data: Dict[str, Any]):
        """
        辞書データからCross構造を構築

        Args:
            data: .jcrossからパースされた辞書
        """
        # 各軸のデータを抽出
        up_data = data.get("UP", [])
        down_data = data.get("DOWN", [])
        right_data = data.get("RIGHT", [])
        left_data = data.get("LEFT", [])
        front_data = data.get("FRONT", [])
        back_data = data.get("BACK", [])

        # 最大点数を決定
        max_points = max(
            len(up_data) if up_data else 0,
            len(down_data) if down_data else 0,
            len(right_data) if right_data else 0,
            len(left_data) if left_data else 0,
            len(front_data) if front_data else 0,
            len(back_data) if back_data else 0
        )

        if max_points == 0:
            # データがない場合はデフォルト
            self.num_points = 5
            self.up = np.zeros(5, dtype=np.float32)
            self.down = np.zeros(5, dtype=np.float32)
            self.right = np.zeros(5, dtype=np.float32)
            self.left = np.zeros(5, dtype=np.float32)
            self.front = np.zeros(5, dtype=np.float32)
            self.back = np.zeros(5, dtype=np.float32)
        else:
            self.num_points = max_points
            self.up = self._parse_axis_data(up_data, max_points)
            self.down = self._parse_axis_data(down_data, max_points)
            self.right = self._parse_axis_data(right_data, max_points)
            self.left = self._parse_axis_data(left_data, max_points)
            self.front = self._parse_axis_data(front_data, max_points)
            self.back = self._parse_axis_data(back_data, max_points)

        # メタデータ（元の.jcross構造を全て保存）
        self.metadata = {
            "UP": up_data,
            "DOWN": down_data,
            "RIGHT": right_data,
            "LEFT": left_data,
            "FRONT": front_data,
            "BACK": back_data,
            **data.get("メタデータ", {})
        }

    def _parse_axis_data(self, axis_data: List[Any], target_size: int) -> np.ndarray:
        """
        軸データをNumPy配列にパース

        Args:
            axis_data: 軸データのリスト
            target_size: 目標サイズ

        Returns:
            NumPy配列
        """
        if not axis_data:
            return np.zeros(target_size, dtype=np.float32)

        # 各要素から「値」を抽出
        values = []
        for item in axis_data:
            if isinstance(item, dict):
                # {"点": 0, "値": 35.0, "意味": "..."} 形式
                value = item.get("値", item.get("value", 0.0))
                values.append(float(value))
            elif isinstance(item, (int, float)):
                # 数値の場合はそのまま
                values.append(float(item))
            else:
                # その他の場合は0
                values.append(0.0)

        # NumPy配列に変換
        arr = np.array(values, dtype=np.float32)

        # サイズ調整
        if len(arr) < target_size:
            # パディング
            arr = np.pad(arr, (0, target_size - len(arr)), mode='constant')
        elif len(arr) > target_size:
            # 切り詰め
            arr = arr[:target_size]

        return arr

    def sync_with(self, other: 'CrossStructure') -> float:
        """
        他のCross構造との同調度を計算

        6軸すべてで点同士を比較し、総合的な同調度を返す

        Args:
            other: 比較対象のCross構造

        Returns:
            同調度 (0.0-1.0)
        """
        if self.num_points != other.num_points:
            warnings.warn(f"Point count mismatch: {self.num_points} vs {other.num_points}")
            # サイズを合わせる
            min_points = min(self.num_points, other.num_points)
        else:
            min_points = self.num_points

        # 各軸の同調度を計算
        sync_up = self._axis_sync(self.up[:min_points], other.up[:min_points])
        sync_down = self._axis_sync(self.down[:min_points], other.down[:min_points])
        sync_right = self._axis_sync(self.right[:min_points], other.right[:min_points])
        sync_left = self._axis_sync(self.left[:min_points], other.left[:min_points])
        sync_front = self._axis_sync(self.front[:min_points], other.front[:min_points])
        sync_back = self._axis_sync(self.back[:min_points], other.back[:min_points])

        # 6軸の平均
        total_sync = (sync_up + sync_down + sync_right + sync_left + sync_front + sync_back) / 6.0

        return total_sync

    def _axis_sync(self, axis1: np.ndarray, axis2: np.ndarray, threshold: float = 0.1) -> float:
        """
        単一軸の同調度を計算

        Args:
            axis1: 軸1の点配列
            axis2: 軸2の点配列
            threshold: 一致とみなす閾値

        Returns:
            同調度 (0.0-1.0)
        """
        # 差分の絶対値
        diff = np.abs(axis1 - axis2)

        # 閾値以下の点の割合
        matched = np.sum(diff <= threshold)
        sync_score = matched / len(axis1)

        return sync_score

    def predict_front(self, steps: int = 1) -> 'CrossStructure':
        """
        FRONT軸方向に予測

        現在の状態からFRONT軸方向（未来）に展開

        Args:
            steps: 予測ステップ数

        Returns:
            予測されたCross構造
        """
        # 簡易実装: 現在のFRONT軸の傾向から外挿
        predicted = CrossStructure(num_points=self.num_points)

        # UP軸の予測: 現在値 + FRONT軸の傾向
        if np.any(self.front != 0):
            predicted.up = self.up + self.front * steps
        else:
            predicted.up = self.up.copy()

        # 他の軸も同様
        predicted.down = self.down.copy()
        predicted.right = self.right.copy()
        predicted.left = self.left.copy()
        predicted.front = self.front.copy()
        predicted.back = self.back.copy()

        return predicted

    def record_to_back(self, actual: 'CrossStructure'):
        """
        実際の値をBACK軸に記録

        予測と実際の差分を学習

        Args:
            actual: 実際のCross構造
        """
        # 予測誤差をBACK軸に記録
        self.back = actual.up - self.up

    def apply_resource_allocation(self, allocation: Dict[str, float]):
        """
        リソース配分を適用

        感情による強制割り込み時に呼ばれる

        Args:
            allocation: リソース配分辞書
        """
        # RIGHT軸にリソース配分を記録
        # 簡易実装: リソース名に対応する点に値を設定
        resource_mapping = {
            "探索": 0,
            "学習": 1,
            "予測": 2,
            "記憶": 3,
            "逃走": 4,
            "攻撃": 5,
            "休息": 6
        }

        for resource, value in allocation.items():
            if resource in resource_mapping:
                idx = resource_mapping[resource]
                if idx < self.num_points:
                    self.right[idx] = value

    def get_activation(self) -> float:
        """
        活性化レベルを取得（UP軸の総和）

        Returns:
            活性化レベル
        """
        return float(np.sum(self.up))

    def to_dict(self) -> Dict[str, Any]:
        """
        辞書形式に変換

        Returns:
            辞書
        """
        return {
            "UP": self.up.tolist(),
            "DOWN": self.down.tolist(),
            "RIGHT": self.right.tolist(),
            "LEFT": self.left.tolist(),
            "FRONT": self.front.tolist(),
            "BACK": self.back.tolist(),
            "metadata": self.metadata,
            "num_points": self.num_points
        }

    def __repr__(self) -> str:
        return f"<CrossStructure: {self.num_points} points, activation={self.get_activation():.2f}>"


class MultiCrossStructure:
    """
    複数のCross構造を管理

    感情DNA全体など、複数のCross構造をまとめて扱う
    """

    def __init__(self, jcross_data: Dict[str, Any]):
        """
        Initialize

        Args:
            jcross_data: .jcrossから読み込んだ全データ
        """
        self.crosses = {}

        # 各変数をCrossStructureとして構築
        for name, data in jcross_data.items():
            if isinstance(data, dict) and any(axis in data for axis in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]):
                # Cross構造の場合
                self.crosses[name] = CrossStructure(data)
            elif isinstance(data, dict):
                # ネストした辞書の場合は再帰的に処理
                for sub_name, sub_data in data.items():
                    if isinstance(sub_data, dict) and any(axis in sub_data for axis in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]):
                        full_name = f"{name}.{sub_name}"
                        self.crosses[full_name] = CrossStructure(sub_data)

    def get(self, name: str) -> Optional[CrossStructure]:
        """
        Cross構造を取得

        Args:
            name: Cross構造の名前

        Returns:
            CrossStructure、または None
        """
        return self.crosses.get(name)

    def sync_all(self, other: 'MultiCrossStructure') -> Dict[str, float]:
        """
        すべてのCross構造の同調度を計算

        Args:
            other: 比較対象のMultiCrossStructure

        Returns:
            各Cross構造の同調度辞書
        """
        results = {}

        for name, cross in self.crosses.items():
            if name in other.crosses:
                sync = cross.sync_with(other.crosses[name])
                results[name] = sync

        return results

    def __repr__(self) -> str:
        return f"<MultiCrossStructure: {len(self.crosses)} crosses>"


def main():
    """テスト用メイン関数"""
    from jcross_interpreter import JCrossInterpreter

    print("=" * 80)
    print("Cross構造テスト")
    print("=" * 80)
    print()

    # .jcrossファイルを読み込み
    interpreter = JCrossInterpreter()
    jcross_data = interpreter.load_file("../vision/emotion_dna_cross.jcross")

    # MultiCrossStructureに変換
    multi_cross = MultiCrossStructure(jcross_data)

    print(f"読み込んだCross構造数: {len(multi_cross.crosses)}")
    print()

    # 個別のCross構造を確認
    for name in list(multi_cross.crosses.keys())[:5]:
        cross = multi_cross.crosses[name]
        print(f"{name}: {cross}")

    print()

    # 体温Crossを取得
    body_temp_cross = multi_cross.get("体温Cross")
    if body_temp_cross:
        print("体温Cross:")
        print(f"  点数: {body_temp_cross.num_points}")
        print(f"  UP軸: {body_temp_cross.up}")
        print(f"  DOWN軸: {body_temp_cross.down}")
        print(f"  活性化: {body_temp_cross.get_activation()}")


if __name__ == "__main__":
    main()
