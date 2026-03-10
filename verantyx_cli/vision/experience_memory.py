#!/usr/bin/env python3
"""
Experience Memory
経験記憶システム

ラベルなしで観測したCross構造を時系列で記憶する。
人間の介入なし。システムが自律的に経験を蓄積。
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
import hashlib

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class ExperienceMemory:
    """経験記憶（ラベルなし）"""

    def __init__(self, memory_path: Optional[Path] = None):
        """
        Initialize experience memory

        Args:
            memory_path: 記憶ファイルのパス
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required")

        if memory_path is None:
            memory_path = Path.home() / ".verantyx" / "experience_memory.json"

        self.memory_path = memory_path
        self.timeline = []  # 時系列の経験
        self.patterns = {}  # パターンID -> タイムスタンプリスト

        # 既存の記憶を読み込み
        if self.memory_path.exists():
            self.load()

    def observe(self, cross_structure: Dict[str, Any], metadata: Optional[Dict] = None):
        """
        観測して記憶（ラベルなし）

        Args:
            cross_structure: Cross構造
            metadata: メタデータ（オプション）
        """
        timestamp = len(self.timeline)

        # 文脈を抽出
        context = self._extract_context(cross_structure)

        # パターンを抽出
        pattern = self._extract_pattern(cross_structure)
        pattern_id = self._hash_pattern(pattern)

        # 経験を記録
        experience = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "cross_structure": cross_structure,
            "pattern_id": pattern_id,
            "context": context,
            "metadata": metadata or {}
        }

        self.timeline.append(experience)

        # パターンインデックスを更新
        if pattern_id not in self.patterns:
            self.patterns[pattern_id] = []
        self.patterns[pattern_id].append(timestamp)

        print(f"📝 経験記録: タイムスタンプ {timestamp}, パターンID {pattern_id[:8]}")

        # 自動保存（100経験ごと）
        if len(self.timeline) % 100 == 0:
            self.save()
            print(f"💾 自動保存: {len(self.timeline)} 経験")

    def _extract_context(self, cross_structure: Dict[str, Any]) -> Dict[str, Any]:
        """文脈を抽出"""
        context = {}

        if len(self.timeline) == 0:
            # 最初の経験
            context["is_first"] = True
            context["delta"] = None
            context["trend"] = None
        else:
            # 直前の経験との関連
            prev_experience = self.timeline[-1]
            prev_cross = prev_experience["cross_structure"]

            # 差分を計算
            delta = self._calculate_delta(prev_cross, cross_structure)
            context["delta"] = delta
            context["is_first"] = False

            # トレンドを検出
            context["trend"] = self._detect_trend(delta)

        return context

    def _calculate_delta(
        self,
        cross1: Dict[str, Any],
        cross2: Dict[str, Any]
    ) -> Dict[str, float]:
        """2つのCross構造の差分を計算"""
        delta = {}

        # 単層の場合
        if "axes" in cross1 and "axes" in cross2:
            axes1 = cross1.get("axes", {})
            axes2 = cross2.get("axes", {})

            for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
                mean1 = axes1.get(axis_name, {}).get("mean", 0.5)
                mean2 = axes2.get(axis_name, {}).get("mean", 0.5)
                delta[axis_name] = mean2 - mean1

        # 多層の場合
        elif "layers" in cross1 and "layers" in cross2:
            layers1 = cross1.get("layers", [])
            layers2 = cross2.get("layers", [])

            for i, (layer1, layer2) in enumerate(zip(layers1, layers2)):
                stats1 = layer1.get("axis_statistics", {})
                stats2 = layer2.get("axis_statistics", {})

                for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
                    mean1 = stats1.get(axis_name, {}).get("mean", 0.5)
                    mean2 = stats2.get(axis_name, {}).get("mean", 0.5)
                    delta[f"L{i}_{axis_name}"] = mean2 - mean1

        return delta

    def _detect_trend(self, delta: Dict[str, float]) -> str:
        """トレンドを検出"""
        if not delta:
            return "stable"

        # 平均変化量
        avg_change = np.mean(list(delta.values()))

        if abs(avg_change) < 0.01:
            return "stable"
        elif avg_change > 0.1:
            return "increasing"
        elif avg_change < -0.1:
            return "decreasing"
        else:
            return "fluctuating"

    def _extract_pattern(self, cross_structure: Dict[str, Any]) -> Dict[str, Any]:
        """パターンを抽出（簡易版）"""
        pattern = {}

        # 単層の場合
        if "axes" in cross_structure:
            axes = cross_structure.get("axes", {})
            for axis_name, axis_data in axes.items():
                mean_val = axis_data.get("mean", 0.5)
                # 0.1刻みで量子化（パターン認識用）
                pattern[axis_name] = round(mean_val, 1)

        # 多層の場合
        elif "layers" in cross_structure:
            layers = cross_structure.get("layers", [])
            for layer in layers:
                layer_id = layer.get("id")
                stats = layer.get("axis_statistics", {})
                for axis_name, axis_stats in stats.items():
                    mean_val = axis_stats.get("mean", 0.5)
                    pattern[f"L{layer_id}_{axis_name}"] = round(mean_val, 1)

        return pattern

    def _hash_pattern(self, pattern: Dict[str, Any]) -> str:
        """パターンをハッシュ化"""
        pattern_str = json.dumps(pattern, sort_keys=True)
        return hashlib.sha256(pattern_str.encode()).hexdigest()

    def find_similar_moments(
        self,
        current_cross: Dict[str, Any],
        top_k: int = 10,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        類似した過去の瞬間を探す

        Args:
            current_cross: 現在のCross構造
            top_k: 上位k個
            min_similarity: 最小類似度

        Returns:
            類似した経験のリスト
        """
        if not self.timeline:
            return []

        similarities = []

        for experience in self.timeline:
            similarity = self._calculate_similarity(
                current_cross,
                experience["cross_structure"]
            )

            if similarity >= min_similarity:
                similarities.append({
                    "timestamp": experience["timestamp"],
                    "similarity": similarity,
                    "experience": experience
                })

        # 類似度順にソート
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        return similarities[:top_k]

    def _calculate_similarity(
        self,
        cross1: Dict[str, Any],
        cross2: Dict[str, Any]
    ) -> float:
        """Cross構造の類似度を計算"""
        # 単層の場合
        if "axes" in cross1 and "axes" in cross2:
            axes1 = cross1.get("axes", {})
            axes2 = cross2.get("axes", {})

            similarities = []
            for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
                mean1 = axes1.get(axis_name, {}).get("mean", 0.5)
                mean2 = axes2.get(axis_name, {}).get("mean", 0.5)
                diff = abs(mean1 - mean2)
                similarity = 1.0 - min(1.0, diff)
                similarities.append(similarity)

            return float(np.mean(similarities))

        # 多層の場合
        elif "layers" in cross1 and "layers" in cross2:
            layers1 = cross1.get("layers", [])
            layers2 = cross2.get("layers", [])

            if not layers1 or not layers2:
                return 0.0

            layer_similarities = []
            for layer1, layer2 in zip(layers1, layers2):
                stats1 = layer1.get("axis_statistics", {})
                stats2 = layer2.get("axis_statistics", {})

                axis_similarities = []
                for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
                    mean1 = stats1.get(axis_name, {}).get("mean", 0.5)
                    mean2 = stats2.get(axis_name, {}).get("mean", 0.5)
                    diff = abs(mean1 - mean2)
                    similarity = 1.0 - min(1.0, diff)
                    axis_similarities.append(similarity)

                if axis_similarities:
                    layer_similarities.append(np.mean(axis_similarities))

            return float(np.mean(layer_similarities)) if layer_similarities else 0.0

        return 0.0

    def get_next_moment(self, timestamp: int) -> Optional[Dict[str, Any]]:
        """
        指定したタイムスタンプの次の瞬間を取得

        Args:
            timestamp: タイムスタンプ

        Returns:
            次の経験（なければNone）
        """
        next_timestamp = timestamp + 1
        if next_timestamp < len(self.timeline):
            return self.timeline[next_timestamp]
        return None

    def save(self):
        """記憶を保存"""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "experience_count": len(self.timeline),
            "pattern_count": len(self.patterns),
            "timeline": self.timeline,
            "patterns": self.patterns
        }

        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self):
        """記憶を読み込み"""
        if not self.memory_path.exists():
            return

        with open(self.memory_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.timeline = data.get("timeline", [])
        self.patterns = data.get("patterns", {})

        print(f"📂 記憶を読み込みました:")
        print(f"   経験数: {len(self.timeline)}")
        print(f"   パターン数: {len(self.patterns)}")

    def print_summary(self):
        """サマリーを表示"""
        print()
        print("=" * 60)
        print("経験記憶 サマリー")
        print("=" * 60)
        print(f"記憶パス: {self.memory_path}")
        print(f"経験数: {len(self.timeline)}")
        print(f"パターン数: {len(self.patterns)}")
        print()

        if self.timeline:
            first_exp = self.timeline[0]
            last_exp = self.timeline[-1]
            print(f"最初の経験: {first_exp['datetime'][:19]}")
            print(f"最新の経験: {last_exp['datetime'][:19]}")

            # 最頻パターン
            if self.patterns:
                pattern_counts = {
                    pid: len(timestamps)
                    for pid, timestamps in self.patterns.items()
                }
                most_common = sorted(
                    pattern_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]

                print()
                print("最頻パターン:")
                for pid, count in most_common:
                    print(f"  - {pid[:8]}... ({count} 回)")

        print("=" * 60)
        print()
