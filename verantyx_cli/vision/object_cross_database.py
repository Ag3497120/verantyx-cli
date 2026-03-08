#!/usr/bin/env python3
"""
Object Cross Structure Database
オブジェクトCross構造データベース

カメラで学習したオブジェクトのCross構造を保存・認識する。
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class ObjectCrossDatabase:
    """オブジェクトCross構造データベース"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database

        Args:
            db_path: データベースファイルパス（Noneの場合はデフォルト）
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required. Install with: pip install numpy")

        if db_path is None:
            db_path = Path.home() / ".verantyx" / "object_database.json"

        self.db_path = db_path
        self.objects = {}  # object_name -> [samples]

        # 既存のデータベースを読み込み
        if self.db_path.exists():
            self.load()

    def add_object(
        self,
        object_name: str,
        cross_structure: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        オブジェクトをデータベースに追加

        Args:
            object_name: オブジェクト名（例: "りんご"）
            cross_structure: Cross構造
            metadata: メタデータ（オプション）
        """
        if object_name not in self.objects:
            self.objects[object_name] = []

        sample = {
            "cross_structure": cross_structure,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        self.objects[object_name].append(sample)

        print(f"✅ '{object_name}' をデータベースに追加しました")
        print(f"   総サンプル数: {len(self.objects[object_name])}")

        # 自動保存
        self.save()

    def recognize(
        self,
        cross_structure: Dict[str, Any],
        top_k: int = 3,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Cross構造からオブジェクトを認識

        Args:
            cross_structure: 認識対象のCross構造
            top_k: 上位k個を返す
            min_confidence: 最小信頼度

        Returns:
            認識結果のリスト
        """
        if not self.objects:
            return []

        scores = {}

        for object_name, samples in self.objects.items():
            # 各サンプルとの類似度を計算
            sample_scores = []

            for sample in samples:
                similarity = self._calculate_similarity(
                    cross_structure,
                    sample["cross_structure"]
                )
                sample_scores.append(similarity)

            # 最高スコアを採用
            if sample_scores:
                scores[object_name] = max(sample_scores)

        # 最小信頼度でフィルタ
        filtered_scores = {
            name: score
            for name, score in scores.items()
            if score >= min_confidence
        }

        if not filtered_scores:
            return []

        # スコアでソート
        sorted_objects = sorted(
            filtered_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 上位k個を返す
        results = []

        for object_name, score in sorted_objects[:top_k]:
            results.append({
                "object": object_name,
                "score": score,
                "confidence": score * 100,
                "sample_count": len(self.objects[object_name])
            })

        return results

    def _calculate_similarity(
        self,
        cross1: Dict[str, Any],
        cross2: Dict[str, Any]
    ) -> float:
        """
        2つのCross構造の類似度を計算

        Args:
            cross1: Cross構造1
            cross2: Cross構造2

        Returns:
            類似度スコア [0.0, 1.0]
        """
        # 単層の場合
        if "axes" in cross1 and "axes" in cross2:
            return self._compare_single_layer(cross1, cross2)

        # 多層の場合
        if "layers" in cross1 and "layers" in cross2:
            return self._compare_multi_layer(cross1, cross2)

        return 0.0

    def _compare_single_layer(
        self,
        cross1: Dict[str, Any],
        cross2: Dict[str, Any]
    ) -> float:
        """単層Cross構造の比較"""
        axes1 = cross1.get("axes", {})
        axes2 = cross2.get("axes", {})

        similarities = []

        for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
            axis_data1 = axes1.get(axis_name, {})
            axis_data2 = axes2.get(axis_name, {})

            mean1 = axis_data1.get("mean", 0.5)
            mean2 = axis_data2.get("mean", 0.5)

            # 平均値の差
            diff = abs(mean1 - mean2)
            similarity = 1.0 - min(1.0, diff)

            similarities.append(similarity)

        if not similarities:
            return 0.0

        return float(np.mean(similarities))

    def _compare_multi_layer(
        self,
        cross1: Dict[str, Any],
        cross2: Dict[str, Any]
    ) -> float:
        """多層Cross構造の比較"""
        layers1 = cross1.get("layers", [])
        layers2 = cross2.get("layers", [])

        if not layers1 or not layers2:
            return 0.0

        # 各層の類似度を計算
        layer_similarities = []
        layer_weights = [0.1, 0.15, 0.2, 0.25, 0.3]  # 上位層ほど重要

        for i, (layer1, layer2) in enumerate(zip(layers1, layers2)):
            if i >= len(layer_weights):
                break

            # 層の軸統計を比較
            axes1 = layer1.get("axis_statistics", {})
            axes2 = layer2.get("axis_statistics", {})

            axis_similarities = []

            for axis_name in ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]:
                stats1 = axes1.get(axis_name, {})
                stats2 = axes2.get(axis_name, {})

                mean1 = stats1.get("mean", 0.5)
                mean2 = stats2.get("mean", 0.5)

                diff = abs(mean1 - mean2)
                similarity = 1.0 - min(1.0, diff)

                axis_similarities.append(similarity)

            if axis_similarities:
                layer_similarity = float(np.mean(axis_similarities))
                layer_similarities.append((layer_similarity, layer_weights[i]))

        if not layer_similarities:
            return 0.0

        # 重み付き平均
        weighted_sum = sum(sim * weight for sim, weight in layer_similarities)
        weight_sum = sum(weight for _, weight in layer_similarities)

        return weighted_sum / weight_sum if weight_sum > 0 else 0.0

    def save(self):
        """データベースをファイルに保存"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "num_objects": len(self.objects),
            "total_samples": sum(len(samples) for samples in self.objects.values()),
            "objects": self.objects
        }

        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self):
        """データベースをファイルから読み込み"""
        if not self.db_path.exists():
            return

        with open(self.db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.objects = data.get("objects", {})

        print(f"📂 データベースを読み込みました:")
        print(f"   オブジェクト数: {len(self.objects)}")
        print(f"   総サンプル数: {sum(len(s) for s in self.objects.values())}")

    def list_objects(self) -> List[Dict[str, Any]]:
        """学習済みオブジェクトの一覧を取得"""
        objects = []

        for name, samples in self.objects.items():
            objects.append({
                "name": name,
                "sample_count": len(samples),
                "latest_timestamp": samples[-1]["timestamp"] if samples else None
            })

        return sorted(objects, key=lambda x: x["name"])

    def delete_object(self, object_name: str) -> bool:
        """
        オブジェクトを削除

        Args:
            object_name: 削除するオブジェクト名

        Returns:
            削除成功したかどうか
        """
        if object_name in self.objects:
            del self.objects[object_name]
            self.save()
            print(f"🗑️  '{object_name}' を削除しました")
            return True

        return False

    def clear_all(self):
        """すべてのオブジェクトを削除"""
        self.objects.clear()
        self.save()
        print("🗑️  すべてのオブジェクトを削除しました")

    def get_object_info(self, object_name: str) -> Optional[Dict[str, Any]]:
        """
        オブジェクトの詳細情報を取得

        Args:
            object_name: オブジェクト名

        Returns:
            オブジェクト情報
        """
        if object_name not in self.objects:
            return None

        samples = self.objects[object_name]

        return {
            "name": object_name,
            "sample_count": len(samples),
            "first_learned": samples[0]["timestamp"],
            "last_learned": samples[-1]["timestamp"],
            "samples": samples
        }

    def print_summary(self):
        """データベースのサマリーを表示"""
        print("\n" + "=" * 60)
        print("オブジェクトデータベース サマリー")
        print("=" * 60)
        print(f"データベースパス: {self.db_path}")
        print(f"オブジェクト数: {len(self.objects)}")
        print(f"総サンプル数: {sum(len(s) for s in self.objects.values())}")
        print()

        if self.objects:
            print("学習済みオブジェクト:")
            for obj_info in self.list_objects():
                print(f"  - {obj_info['name']}: {obj_info['sample_count']} サンプル")

        print("=" * 60 + "\n")
