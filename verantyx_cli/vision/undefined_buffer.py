#!/usr/bin/env python3
"""
Undefined Buffer Layer
未定義バッファ層

Stores raw Cross structures without interpretation.
This is pre-semantic memory - experiences stored before language/meaning.

Key concept:
- Cross structures are stored as-is (260,000 points)
- No labels, no interpretation, no meaning
- "Color" (discomfort signal) is attached at storage time
- Later, when abilities develop, these memories gain meaning

記憶は能力発達後に意味を知るために重要
(Memory is important for knowing meaning after ability development)
"""

import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import time


@dataclass
class RawExperience:
    """
    未解釈の生経験

    Cross構造 + 不快感信号 + タイムスタンプ
    意味はまだない。
    """
    experience_id: int
    timestamp: float
    cross_structure: Dict[str, Any]  # MultiLayerCross structure
    discomfort_signal: float         # 0.0-1.0 (from genetic axioms)
    sensory_context: Dict[str, Any]  # Additional sensory data
    resolution: Optional[str] = None  # What happened after (set later)
    meaning: Optional[str] = None     # Assigned when language develops


@dataclass
class ExperienceCluster:
    """
    経験のクラスタ（パターン発見前）

    Similar experiences group together automatically
    through Cross structure similarity.
    """
    cluster_id: int
    experiences: List[int] = field(default_factory=list)  # Experience IDs
    average_discomfort: float = 0.0
    pattern_detected: bool = False
    pattern_signature: Optional[np.ndarray] = None


class UndefinedBuffer:
    """
    未定義バッファ層

    0歳児の記憶システム:
    - 全ての経験をCross構造として保存
    - 解釈なし、意味なし
    - 「色」（不快感）だけが付いている
    - 後から意味が付与される
    """

    def __init__(self, max_buffer_size: int = 10000):
        """
        Initialize undefined buffer

        Args:
            max_buffer_size: 最大保存数
        """
        self.max_buffer_size = max_buffer_size
        self.experiences: Dict[int, RawExperience] = {}
        self.next_id = 0

        # クラスタリング（自動パターン発見）
        self.clusters: Dict[int, ExperienceCluster] = {}
        self.next_cluster_id = 0

        # 不快感-解決の共起記録
        self.discomfort_resolution_pairs: List[Dict[str, Any]] = []

        print("🧠 Undefined Buffer initialized")
        print(f"   Max capacity: {max_buffer_size:,} experiences")

    def store_experience(
        self,
        cross_structure: Dict[str, Any],
        discomfort_signal: float,
        sensory_context: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        経験を保存（未解釈のまま）

        Args:
            cross_structure: Cross構造
            discomfort_signal: 不快感の強度
            sensory_context: 感覚的コンテキスト

        Returns:
            Experience ID
        """
        # バッファが満杯なら古いものを削除
        if len(self.experiences) >= self.max_buffer_size:
            self._remove_oldest()

        experience_id = self.next_id
        self.next_id += 1

        experience = RawExperience(
            experience_id=experience_id,
            timestamp=time.time(),
            cross_structure=cross_structure,
            discomfort_signal=discomfort_signal,
            sensory_context=sensory_context or {}
        )

        self.experiences[experience_id] = experience

        # 自動的にクラスタに追加
        self._add_to_cluster(experience)

        return experience_id

    def mark_resolution(
        self,
        experience_id: int,
        resolution: str
    ):
        """
        経験の「解決」を記録

        Example:
        - Experience: 不快感が高い + 特定の音
        - Resolution: "母親が来た" → 不快感が減少

        これが繰り返されると、その音に「意味」が付く。

        Args:
            experience_id: 経験ID
            resolution: 解決方法
        """
        if experience_id not in self.experiences:
            return

        experience = self.experiences[experience_id]
        experience.resolution = resolution

        # 不快感-解決ペアとして記録
        if experience.discomfort_signal > 0.3:
            self.discomfort_resolution_pairs.append({
                "experience_id": experience_id,
                "discomfort": experience.discomfort_signal,
                "resolution": resolution,
                "timestamp": experience.timestamp
            })

    def find_similar_experiences(
        self,
        cross_structure: Dict[str, Any],
        threshold: float = 0.8,
        max_results: int = 10
    ) -> List[int]:
        """
        類似の経験を検索

        Cross構造の類似度で検索。
        まだ「意味」はわからないが、「似ている」ことはわかる。

        Args:
            cross_structure: Cross構造
            threshold: 類似度閾値
            max_results: 最大結果数

        Returns:
            類似経験のIDリスト
        """
        similarities = []

        # 入力のLayer4特徴を抽出
        input_signature = self._extract_signature(cross_structure)

        for exp_id, experience in self.experiences.items():
            # 保存された経験のLayer4特徴を抽出
            exp_signature = self._extract_signature(experience.cross_structure)

            # コサイン類似度
            similarity = self._cosine_similarity(input_signature, exp_signature)

            if similarity >= threshold:
                similarities.append((exp_id, similarity))

        # 類似度でソート
        similarities.sort(key=lambda x: x[1], reverse=True)

        return [exp_id for exp_id, _ in similarities[:max_results]]

    def get_discomfort_pattern(
        self,
        resolution: str
    ) -> Optional[Dict[str, Any]]:
        """
        特定の解決方法に関連する不快感パターンを取得

        Example:
        resolution="母親の声" → どんな不快感の時に有効だったか

        Args:
            resolution: 解決方法

        Returns:
            パターン情報
        """
        relevant_pairs = [
            pair for pair in self.discomfort_resolution_pairs
            if pair["resolution"] == resolution
        ]

        if not relevant_pairs:
            return None

        # 平均不快感レベル
        avg_discomfort = np.mean([pair["discomfort"] for pair in relevant_pairs])

        # 共通のCross構造パターン
        experience_ids = [pair["experience_id"] for pair in relevant_pairs]
        signatures = [
            self._extract_signature(self.experiences[exp_id].cross_structure)
            for exp_id in experience_ids
            if exp_id in self.experiences
        ]

        if signatures:
            pattern_signature = np.mean(signatures, axis=0)
        else:
            pattern_signature = None

        return {
            "resolution": resolution,
            "occurrence_count": len(relevant_pairs),
            "average_discomfort": avg_discomfort,
            "pattern_signature": pattern_signature,
            "experience_ids": experience_ids
        }

    def assign_meaning(
        self,
        experience_ids: List[int],
        meaning: str
    ):
        """
        経験に意味を付与（言語獲得後）

        Args:
            experience_ids: 経験IDリスト
            meaning: 意味（言語ラベル）
        """
        for exp_id in experience_ids:
            if exp_id in self.experiences:
                self.experiences[exp_id].meaning = meaning

    def _add_to_cluster(self, experience: RawExperience):
        """経験をクラスタに追加"""
        signature = self._extract_signature(experience.cross_structure)

        # 既存クラスタとの類似度をチェック
        best_cluster = None
        best_similarity = 0.0

        for cluster_id, cluster in self.clusters.items():
            if cluster.pattern_signature is not None:
                similarity = self._cosine_similarity(signature, cluster.pattern_signature)
                if similarity > best_similarity and similarity > 0.7:
                    best_similarity = similarity
                    best_cluster = cluster_id

        if best_cluster is not None:
            # 既存クラスタに追加
            cluster = self.clusters[best_cluster]
            cluster.experiences.append(experience.experience_id)

            # 平均不快感を更新
            cluster.average_discomfort = np.mean([
                self.experiences[exp_id].discomfort_signal
                for exp_id in cluster.experiences
                if exp_id in self.experiences
            ])

            # パターン署名を更新
            signatures = [
                self._extract_signature(self.experiences[exp_id].cross_structure)
                for exp_id in cluster.experiences
                if exp_id in self.experiences
            ]
            cluster.pattern_signature = np.mean(signatures, axis=0)

        else:
            # 新しいクラスタを作成
            cluster_id = self.next_cluster_id
            self.next_cluster_id += 1

            self.clusters[cluster_id] = ExperienceCluster(
                cluster_id=cluster_id,
                experiences=[experience.experience_id],
                average_discomfort=experience.discomfort_signal,
                pattern_signature=signature
            )

    def _extract_signature(self, cross_structure: Dict[str, Any]) -> np.ndarray:
        """
        Cross構造から特徴署名を抽出（Layer4を使用）

        Args:
            cross_structure: Cross構造

        Returns:
            特徴ベクトル
        """
        # Layer4の点を抽出
        layers = cross_structure.get("layers", [])
        if len(layers) >= 5:
            layer4 = layers[4]
            points = layer4.get("points", [])

            # RGBと軸値を結合
            features = []
            for point in points[:100]:  # 最大100点
                rgb = point.get("rgb", [0, 0, 0])
                axes = point.get("axis_values", {})
                axis_vector = [
                    axes.get("UP", 0),
                    axes.get("DOWN", 0),
                    axes.get("RIGHT", 0),
                    axes.get("LEFT", 0),
                    axes.get("FRONT", 0),
                    axes.get("BACK", 0)
                ]
                features.extend(rgb)
                features.extend(axis_vector)

            return np.array(features)

        # Fallbackとして空ベクトル
        return np.zeros(900)  # 100点 × 9次元

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """コサイン類似度"""
        if len(a) != len(b):
            return 0.0

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return np.dot(a, b) / (norm_a * norm_b)

    def _remove_oldest(self):
        """最も古い経験を削除"""
        if not self.experiences:
            return

        oldest_id = min(self.experiences.keys(), key=lambda k: self.experiences[k].timestamp)
        del self.experiences[oldest_id]

    def get_statistics(self) -> Dict[str, Any]:
        """バッファの統計情報を取得"""
        if not self.experiences:
            return {
                "total_experiences": 0,
                "total_clusters": 0,
                "average_discomfort": 0.0,
                "experiences_with_resolution": 0,
                "experiences_with_meaning": 0
            }

        total_experiences = len(self.experiences)
        experiences_with_resolution = sum(
            1 for exp in self.experiences.values() if exp.resolution is not None
        )
        experiences_with_meaning = sum(
            1 for exp in self.experiences.values() if exp.meaning is not None
        )
        average_discomfort = np.mean([
            exp.discomfort_signal for exp in self.experiences.values()
        ])

        return {
            "total_experiences": total_experiences,
            "total_clusters": len(self.clusters),
            "average_discomfort": average_discomfort,
            "experiences_with_resolution": experiences_with_resolution,
            "experiences_with_meaning": experiences_with_meaning,
            "discomfort_resolution_pairs": len(self.discomfort_resolution_pairs)
        }
