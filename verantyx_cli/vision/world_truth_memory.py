#!/usr/bin/env python3
"""
World Truth Memory Bank
世界の真理記憶バンク

物理シミュレーションから抽出した世界の法則（真理）を記憶し、
実際の動画と照合して物理的な振る舞いを認識する。

真理の例:
- falling: 物体が落下する
- horizontal_motion: 物体が水平に移動する
- projectile: 物体が放物運動する
- rotation: 物体が回転する
- collision: 物体が衝突する
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from dataclasses import dataclass
from datetime import datetime

try:
    import numpy as np
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    import numpy as np


@dataclass
class WorldTruth:
    """世界の真理"""
    name: str
    temporal_pattern: Dict[str, List[float]]  # 時系列パターン（各軸）
    axis_changes: Dict[str, Dict[str, Any]]  # 軸の変化特性
    duration: float
    num_frames: int
    learned_at: str


class WorldTruthMemoryBank:
    """世界の真理を記憶・認識するバンク"""

    def __init__(self, memory_path: Optional[Path] = None):
        """
        Initialize world truth memory bank

        Args:
            memory_path: 記憶バンクの保存先
        """
        self.memory_path = memory_path
        self.truths: Dict[str, WorldTruth] = {}

        # 保存先があれば読み込み
        if memory_path and memory_path.exists():
            self.load()

    def learn_truth(
        self,
        truth_name: str,
        simulation_timeline: List[Dict[str, Any]]
    ) -> WorldTruth:
        """
        シミュレーションから真理を学習

        Args:
            truth_name: 真理の名前（例: "falling"）
            simulation_timeline: シミュレーション時系列

        Returns:
            学習した真理
        """
        print(f"\n📚 世界の真理を学習中: {truth_name}")
        print("=" * 60)

        if not simulation_timeline:
            raise ValueError("Timeline is empty")

        # 時系列パターンを抽出
        print("  ⚙️  時系列パターンを抽出中...")
        temporal_pattern = self._extract_temporal_pattern(simulation_timeline)

        # 軸の変化特性を抽出
        print("  ⚙️  軸の変化特性を抽出中...")
        axis_changes = self._extract_axis_changes(simulation_timeline)

        # 真理を作成
        truth = WorldTruth(
            name=truth_name,
            temporal_pattern=temporal_pattern,
            axis_changes=axis_changes,
            duration=simulation_timeline[-1]["time"],
            num_frames=len(simulation_timeline),
            learned_at=datetime.now().isoformat()
        )

        # 記憶バンクに保存
        self.truths[truth_name] = truth

        print(f"  ✅ 真理 '{truth_name}' を記憶しました")
        print(f"     期間: {truth.duration:.2f}秒")
        print(f"     フレーム数: {truth.num_frames}")
        print()

        self._print_truth_summary(truth)

        print("=" * 60)
        print()

        # ファイルに保存
        if self.memory_path:
            self.save()

        return truth

    def _extract_temporal_pattern(
        self,
        timeline: List[Dict[str, Any]]
    ) -> Dict[str, List[float]]:
        """時系列パターンを抽出"""
        pattern = {
            "UP": [],
            "DOWN": [],
            "RIGHT": [],
            "LEFT": [],
            "FRONT": [],
            "BACK": []
        }

        for snapshot in timeline:
            cross_structure = snapshot.get("cross_structure", {})
            axes = cross_structure.get("axes", {})

            for axis_name in pattern.keys():
                axis_data = axes.get(axis_name, {})
                mean_value = axis_data.get("mean", 0.5)
                pattern[axis_name].append(mean_value)

        return pattern

    def _extract_axis_changes(
        self,
        timeline: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """軸の変化特性を抽出"""
        changes = {}

        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
            values = []

            for snapshot in timeline:
                cross_structure = snapshot.get("cross_structure", {})
                axes = cross_structure.get("axes", {})
                axis_data = axes.get(axis_name, {})
                mean_value = axis_data.get("mean", 0.5)
                values.append(mean_value)

            if not values:
                continue

            # 変化特性を計算
            changes[axis_name] = {
                "trend": self._detect_trend(values),
                "rate": self._calculate_change_rate(values),
                "pattern_type": self._classify_pattern(values),
                "variance": float(np.var(values)),
                "range": float(np.max(values) - np.min(values))
            }

        return changes

    def _detect_trend(self, values: List[float]) -> str:
        """トレンドを検出"""
        if len(values) < 2:
            return "constant"

        # 線形回帰の傾き
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]

        if slope > 0.01:
            return "increasing"
        elif slope < -0.01:
            return "decreasing"
        else:
            return "constant"

    def _calculate_change_rate(self, values: List[float]) -> float:
        """変化率を計算"""
        if len(values) < 2:
            return 0.0

        # 平均変化率
        diffs = np.diff(values)
        return float(np.mean(np.abs(diffs)))

    def _classify_pattern(self, values: List[float]) -> str:
        """パターンタイプを分類"""
        if len(values) < 3:
            return "unknown"

        # 1次微分（速度）
        first_diff = np.diff(values)

        # 2次微分（加速度）
        second_diff = np.diff(first_diff)

        # 加速度の平均
        avg_accel = np.mean(np.abs(second_diff))

        if avg_accel > 0.001:
            # 加速度がある → 加速または減速
            if np.mean(second_diff) > 0:
                return "accelerating"
            else:
                return "decelerating"
        else:
            # 加速度が小さい → 等速
            return "linear"

    def _print_truth_summary(self, truth: WorldTruth):
        """真理のサマリーを表示"""
        print("  📊 真理の特性:")
        print()

        for axis_name, changes in truth.axis_changes.items():
            trend = changes.get("trend", "unknown")
            pattern = changes.get("pattern_type", "unknown")
            rate = changes.get("rate", 0.0)

            if trend != "constant" or rate > 0.01:
                print(f"     {axis_name}軸:")
                print(f"       トレンド: {trend}")
                print(f"       パターン: {pattern}")
                print(f"       変化率: {rate:.4f}")

        print()

    def recognize_truth(
        self,
        video_timeline: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        動画のCross構造時系列から真理を認識

        Args:
            video_timeline: 動画のCross構造時系列
            top_k: 上位k個の真理を返す

        Returns:
            認識された真理のリスト
        """
        if not self.truths:
            print("⚠️  学習済みの真理がありません")
            return []

        print("\n🔍 世界の真理を認識中...")
        print("=" * 60)

        scores = {}

        for truth_name, truth in self.truths.items():
            score = self._match_truth(video_timeline, truth)
            scores[truth_name] = score

            print(f"  {truth_name}: {score:.4f}")

        print("=" * 60)

        # スコアでソート
        sorted_truths = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 上位k個を返す
        results = []

        for truth_name, score in sorted_truths[:top_k]:
            results.append({
                "truth": truth_name,
                "score": score,
                "confidence": score * 100
            })

        if results:
            print(f"\n✅ 最も類似: {results[0]['truth']} ({results[0]['confidence']:.1f}%)")
        print()

        return results

    def _match_truth(
        self,
        video_timeline: List[Dict[str, Any]],
        truth: WorldTruth
    ) -> float:
        """
        動画時系列と真理をマッチング

        Args:
            video_timeline: 動画時系列
            truth: 真理

        Returns:
            類似度スコア [0.0, 1.0]
        """
        # 動画から時系列パターンを抽出
        video_pattern = self._extract_temporal_pattern(video_timeline)

        # 各軸のパターンマッチングスコアを計算
        axis_scores = []

        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
            video_values = video_pattern.get(axis_name, [])
            truth_values = truth.temporal_pattern.get(axis_name, [])

            if not video_values or not truth_values:
                continue

            # パターンマッチング
            score = self._match_temporal_pattern(video_values, truth_values)
            axis_scores.append(score)

        if not axis_scores:
            return 0.0

        # 平均スコア
        return float(np.mean(axis_scores))

    def _match_temporal_pattern(
        self,
        video_values: List[float],
        truth_values: List[float]
    ) -> float:
        """
        時系列パターンをマッチング

        Args:
            video_values: 動画の値
            truth_values: 真理の値

        Returns:
            類似度スコア [0.0, 1.0]
        """
        if not video_values or not truth_values:
            return 0.0

        # 長さを揃える（リサンプリング）
        target_len = min(len(video_values), len(truth_values), 100)

        video_resampled = self._resample(video_values, target_len)
        truth_resampled = self._resample(truth_values, target_len)

        # 正規化
        video_norm = self._normalize(video_resampled)
        truth_norm = self._normalize(truth_resampled)

        # 相関係数を計算
        if len(video_norm) > 1 and len(truth_norm) > 1:
            correlation = np.corrcoef(video_norm, truth_norm)[0, 1]

            # NaNチェック
            if np.isnan(correlation):
                correlation = 0.0

            # [0, 1] にマッピング
            score = (correlation + 1.0) / 2.0

            return float(score)

        return 0.0

    def _resample(self, values: List[float], target_len: int) -> np.ndarray:
        """値をリサンプリング"""
        if len(values) == target_len:
            return np.array(values)

        x_old = np.linspace(0, 1, len(values))
        x_new = np.linspace(0, 1, target_len)

        resampled = np.interp(x_new, x_old, values)

        return resampled

    def _normalize(self, values: np.ndarray) -> np.ndarray:
        """値を正規化"""
        min_val = np.min(values)
        max_val = np.max(values)

        if max_val - min_val < 1e-6:
            return values - np.mean(values)

        normalized = (values - min_val) / (max_val - min_val)

        return normalized

    def save(self):
        """記憶バンクをファイルに保存"""
        if not self.memory_path:
            return

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "num_truths": len(self.truths),
            "truths": {}
        }

        for truth_name, truth in self.truths.items():
            data["truths"][truth_name] = {
                "name": truth.name,
                "temporal_pattern": truth.temporal_pattern,
                "axis_changes": truth.axis_changes,
                "duration": truth.duration,
                "num_frames": truth.num_frames,
                "learned_at": truth.learned_at
            }

        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"💾 世界の真理記憶バンクを保存: {self.memory_path}")

    def load(self):
        """記憶バンクをファイルから読み込み"""
        if not self.memory_path or not self.memory_path.exists():
            return

        with open(self.memory_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.truths.clear()

        for truth_name, truth_data in data.get("truths", {}).items():
            truth = WorldTruth(
                name=truth_data.get("name", truth_name),
                temporal_pattern=truth_data.get("temporal_pattern", {}),
                axis_changes=truth_data.get("axis_changes", {}),
                duration=truth_data.get("duration", 0.0),
                num_frames=truth_data.get("num_frames", 0),
                learned_at=truth_data.get("learned_at", "")
            )

            self.truths[truth_name] = truth

        print(f"📂 世界の真理記憶バンクを読み込み: {len(self.truths)} 真理")

    def list_truths(self) -> List[Dict[str, Any]]:
        """学習済み真理の一覧を返す"""
        truths = []

        for truth_name, truth in self.truths.items():
            truths.append({
                "name": truth_name,
                "duration": truth.duration,
                "num_frames": truth.num_frames,
                "learned_at": truth.learned_at
            })

        return truths

    def get_truth_info(self, truth_name: str) -> Optional[Dict[str, Any]]:
        """特定真理の詳細情報を取得"""
        if truth_name not in self.truths:
            return None

        truth = self.truths[truth_name]

        return {
            "name": truth.name,
            "duration": truth.duration,
            "num_frames": truth.num_frames,
            "learned_at": truth.learned_at,
            "axis_changes": truth.axis_changes
        }
