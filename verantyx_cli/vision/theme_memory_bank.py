#!/usr/bin/env python3
"""
Theme Memory Bank
テーマ別Cross構造記憶バンク

空・花・人間などのテーマ別にCross構造パターンを学習・記憶し、
新しい画像の認識に活用する。

テーマごとに5層×6軸の特徴署名を持つ。
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from dataclasses import dataclass, field
from datetime import datetime

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


@dataclass
class ThemeSignature:
    """テーマの特徴署名"""
    theme_name: str
    layer_signatures: Dict[int, Dict[str, Dict[str, float]]]  # layer_id -> axis -> stats
    sample_count: int
    learned_at: str


@dataclass
class ThemePattern:
    """テーマのCross構造パターン"""
    theme_name: str
    common_patterns: Dict[int, Dict[str, Any]]  # layer_id -> axis patterns
    signature: ThemeSignature


class ThemeMemoryBank:
    """
    テーマ別Cross構造記憶バンク

    複数のサンプル画像から共通パターンを学習し、
    新しい画像の認識に活用する。
    """

    def __init__(self, memory_path: Optional[Path] = None):
        """
        Initialize theme memory bank

        Args:
            memory_path: 記憶バンクの保存先（Noneの場合はメモリのみ）
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required. Install with: pip install numpy")

        self.memory_path = memory_path
        self.themes: Dict[str, ThemePattern] = {}

        # 保存先があれば読み込み
        if memory_path and memory_path.exists():
            self.load()

    def learn_theme(
        self,
        theme_name: str,
        cross_structures: List[Dict[str, Any]]
    ) -> ThemePattern:
        """
        テーマを学習

        Args:
            theme_name: テーマ名（例: "sky", "flower", "human"）
            cross_structures: 多層Cross構造のリスト

        Returns:
            学習したテーマパターン
        """
        print(f"\n📚 テーマ学習中: {theme_name}")
        print(f"サンプル数: {len(cross_structures)}")
        print("=" * 60)

        if not cross_structures:
            raise ValueError("At least one cross structure is required")

        # 各層で共通パターンを抽出
        common_patterns = {}
        layer_signatures = {}

        num_layers = len(cross_structures[0].get("layers", []))

        for layer_id in range(num_layers):
            print(f"\nLayer {layer_id}: パターン抽出中...")

            # この層のデータを全サンプルから収集
            layer_data_list = []

            for cs in cross_structures:
                layers = cs.get("layers", [])
                if layer_id < len(layers):
                    layer_data_list.append(layers[layer_id])

            if not layer_data_list:
                continue

            # 共通パターンを抽出
            common_pattern = self._extract_common_pattern(layer_data_list)
            common_patterns[layer_id] = common_pattern

            # 特徴署名を生成
            signature = self._generate_layer_signature(common_pattern)
            layer_signatures[layer_id] = signature

            print(f"  ✅ Layer {layer_id} パターン抽出完了")

        # テーマ署名を作成
        theme_signature = ThemeSignature(
            theme_name=theme_name,
            layer_signatures=layer_signatures,
            sample_count=len(cross_structures),
            learned_at=datetime.now().isoformat()
        )

        # テーマパターンを作成
        theme_pattern = ThemePattern(
            theme_name=theme_name,
            common_patterns=common_patterns,
            signature=theme_signature
        )

        # 記憶バンクに保存
        self.themes[theme_name] = theme_pattern

        print()
        print("=" * 60)
        print(f"✅ テーマ '{theme_name}' の学習が完了しました")
        print(f"   - サンプル数: {len(cross_structures)}")
        print(f"   - 層数: {len(common_patterns)}")
        print()

        # ファイルに保存
        if self.memory_path:
            self.save()

        return theme_pattern

    def _extract_common_pattern(
        self,
        layer_data_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        複数のCross層から共通パターンを抽出

        Args:
            layer_data_list: 層データのリスト

        Returns:
            共通パターン（各軸の統計を統合）
        """
        # 各軸の統計を収集
        axis_names = ["FRONT", "BACK", "UP", "DOWN", "RIGHT", "LEFT"]

        common_pattern = {}

        for axis_name in axis_names:
            # この軸の統計を全サンプルから収集
            axis_stats_list = []

            for layer_data in layer_data_list:
                axis_stats = layer_data.get("axis_statistics", {}).get(axis_name, {})
                if axis_stats:
                    axis_stats_list.append(axis_stats)

            if not axis_stats_list:
                continue

            # 統計を統合
            merged_stats = self._merge_axis_statistics(axis_stats_list)
            common_pattern[axis_name] = merged_stats

        return common_pattern

    def _merge_axis_statistics(
        self,
        stats_list: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        複数の軸統計を統合

        Args:
            stats_list: 統計情報のリスト

        Returns:
            統合された統計
        """
        if not stats_list:
            return {}

        # 各統計量の平均を取る
        merged = {}

        stat_keys = ["mean", "std", "min", "max", "median"]

        for key in stat_keys:
            values = [s.get(key, 0.0) for s in stats_list if key in s]
            if values:
                merged[key] = float(np.mean(values))

        # 分布タイプを判定（stdから）
        if "std" in merged:
            if merged["std"] > 0.5:
                merged["distribution"] = "uniform"
            elif merged["std"] < 0.2:
                merged["distribution"] = "highly_concentrated"
            else:
                merged["distribution"] = "concentrated"

        # ピーク位置を推定（meanから）
        if "mean" in merged:
            merged["peak_position"] = merged["mean"]

        # 集中度
        if "std" in merged:
            merged["concentration"] = 1.0 - min(1.0, merged["std"])

        return merged

    def _generate_layer_signature(
        self,
        common_pattern: Dict[str, Any]
    ) -> Dict[str, Dict[str, float]]:
        """
        層の特徴署名を生成

        Args:
            common_pattern: 共通パターン

        Returns:
            特徴署名（軸 -> 特徴）
        """
        signature = {}

        for axis_name, axis_data in common_pattern.items():
            signature[axis_name] = {
                "mean": axis_data.get("mean", 0.0),
                "std": axis_data.get("std", 0.0),
                "distribution_type": axis_data.get("distribution", "unknown"),
                "peak_position": axis_data.get("peak_position", 0.0),
                "concentration": axis_data.get("concentration", 0.5)
            }

        return signature

    def recognize_theme(
        self,
        cross_structure: Dict[str, Any],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Cross構造からテーマを認識

        Args:
            cross_structure: 多層Cross構造
            top_k: 上位k個のテーマを返す

        Returns:
            テーマと類似度スコアのリスト
        """
        if not self.themes:
            return []

        print("\n🔍 テーマ認識中...")
        print("=" * 60)

        scores = {}

        for theme_name, theme_pattern in self.themes.items():
            score = self._calculate_similarity(
                cross_structure,
                theme_pattern
            )

            scores[theme_name] = score

            print(f"  {theme_name}: {score:.4f}")

        print("=" * 60)

        # スコアでソート
        sorted_themes = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 上位k個を返す
        results = []

        for theme_name, score in sorted_themes[:top_k]:
            results.append({
                "theme": theme_name,
                "score": score,
                "confidence": score * 100
            })

        print(f"\n✅ 最も類似: {results[0]['theme']} ({results[0]['confidence']:.1f}%)")
        print()

        return results

    def _calculate_similarity(
        self,
        cross_structure: Dict[str, Any],
        theme_pattern: ThemePattern
    ) -> float:
        """
        Cross構造とテーマパターンの類似度を計算

        Args:
            cross_structure: 多層Cross構造
            theme_pattern: テーマパターン

        Returns:
            類似度スコア [0.0, 1.0]
        """
        layers = cross_structure.get("layers", [])

        if not layers:
            return 0.0

        layer_scores = []
        layer_weights = [0.1, 0.15, 0.2, 0.25, 0.3]  # 上位層ほど重要

        for layer_id, layer_data in enumerate(layers):
            if layer_id >= len(layer_weights):
                break

            # テーマパターンの該当層と比較
            theme_layer_pattern = theme_pattern.common_patterns.get(layer_id)

            if not theme_layer_pattern:
                continue

            # 層のマッチングスコアを計算
            layer_score = self._match_layer(
                layer_data,
                theme_layer_pattern
            )

            layer_scores.append((layer_score, layer_weights[layer_id]))

        if not layer_scores:
            return 0.0

        # 重み付き平均
        weighted_sum = sum(score * weight for score, weight in layer_scores)
        weight_sum = sum(weight for _, weight in layer_scores)

        return weighted_sum / weight_sum if weight_sum > 0 else 0.0

    def _match_layer(
        self,
        layer_data: Dict[str, Any],
        theme_layer_pattern: Dict[str, Any]
    ) -> float:
        """
        層のマッチングスコアを計算

        Args:
            layer_data: 入力層データ
            theme_layer_pattern: テーマ層パターン

        Returns:
            マッチングスコア [0.0, 1.0]
        """
        axis_stats = layer_data.get("axis_statistics", {})

        if not axis_stats:
            return 0.0

        axis_scores = []

        for axis_name in ["FRONT", "BACK", "UP", "DOWN", "RIGHT", "LEFT"]:
            input_stats = axis_stats.get(axis_name, {})
            theme_stats = theme_layer_pattern.get(axis_name, {})

            if not input_stats or not theme_stats:
                continue

            # 軸のマッチングスコアを計算
            axis_score = self._match_axis(input_stats, theme_stats)
            axis_scores.append(axis_score)

        if not axis_scores:
            return 0.0

        return float(np.mean(axis_scores))

    def _match_axis(
        self,
        input_stats: Dict[str, float],
        theme_stats: Dict[str, float]
    ) -> float:
        """
        軸のマッチングスコアを計算

        Args:
            input_stats: 入力統計
            theme_stats: テーマ統計

        Returns:
            マッチングスコア [0.0, 1.0]
        """
        scores = []

        # 平均値の類似度
        if "mean" in input_stats and "mean" in theme_stats:
            diff = abs(input_stats["mean"] - theme_stats["mean"])
            similarity = 1.0 - min(1.0, diff)
            scores.append(similarity)

        # 標準偏差の類似度
        if "std" in input_stats and "std" in theme_stats:
            diff = abs(input_stats["std"] - theme_stats["std"])
            similarity = 1.0 - min(1.0, diff)
            scores.append(similarity)

        # 中央値の類似度
        if "median" in input_stats and "median" in theme_stats:
            diff = abs(input_stats["median"] - theme_stats["median"])
            similarity = 1.0 - min(1.0, diff)
            scores.append(similarity)

        if not scores:
            return 0.5

        return float(np.mean(scores))

    def save(self):
        """記憶バンクをファイルに保存"""
        if not self.memory_path:
            return

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "num_themes": len(self.themes),
            "themes": {}
        }

        for theme_name, theme_pattern in self.themes.items():
            data["themes"][theme_name] = {
                "theme_name": theme_pattern.theme_name,
                "common_patterns": theme_pattern.common_patterns,
                "signature": {
                    "theme_name": theme_pattern.signature.theme_name,
                    "layer_signatures": theme_pattern.signature.layer_signatures,
                    "sample_count": theme_pattern.signature.sample_count,
                    "learned_at": theme_pattern.signature.learned_at
                }
            }

        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"💾 テーマ記憶バンクを保存: {self.memory_path}")

    def load(self):
        """記憶バンクをファイルから読み込み"""
        if not self.memory_path or not self.memory_path.exists():
            return

        with open(self.memory_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.themes.clear()

        for theme_name, theme_data in data.get("themes", {}).items():
            # 署名を復元
            signature_data = theme_data.get("signature", {})
            signature = ThemeSignature(
                theme_name=signature_data.get("theme_name", theme_name),
                layer_signatures=signature_data.get("layer_signatures", {}),
                sample_count=signature_data.get("sample_count", 0),
                learned_at=signature_data.get("learned_at", "")
            )

            # パターンを復元
            pattern = ThemePattern(
                theme_name=theme_data.get("theme_name", theme_name),
                common_patterns=theme_data.get("common_patterns", {}),
                signature=signature
            )

            self.themes[theme_name] = pattern

        print(f"📂 テーマ記憶バンクを読み込み: {len(self.themes)} テーマ")

    def list_themes(self) -> List[Dict[str, Any]]:
        """学習済みテーマの一覧を返す"""
        themes = []

        for theme_name, theme_pattern in self.themes.items():
            themes.append({
                "name": theme_name,
                "sample_count": theme_pattern.signature.sample_count,
                "learned_at": theme_pattern.signature.learned_at,
                "num_layers": len(theme_pattern.common_patterns)
            })

        return themes

    def get_theme_info(self, theme_name: str) -> Optional[Dict[str, Any]]:
        """特定テーマの詳細情報を取得"""
        if theme_name not in self.themes:
            return None

        theme_pattern = self.themes[theme_name]

        return {
            "name": theme_pattern.theme_name,
            "sample_count": theme_pattern.signature.sample_count,
            "learned_at": theme_pattern.signature.learned_at,
            "num_layers": len(theme_pattern.common_patterns),
            "layer_signatures": theme_pattern.signature.layer_signatures
        }
