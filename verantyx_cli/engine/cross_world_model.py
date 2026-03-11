#!/usr/bin/env python3
"""
Cross World Model - Verantyxの核となる世界モデル

思想:
- LLMの推論ではなく、構造化された世界モデル
- object, region, topology, relationを明示的に表現
- .jcrossプログラムで操作可能
- シミュレーション・検証が可能

設計原則:
1. 全ての知識はCross構造で表現される
2. 操作は.jcrossプログラムで記述される
3. 結果は検証可能である
4. ユーザーごとに進化する

ARC-AGI的アプローチ:
- 問題を構造として理解
- プログラムとして解決
- 検証によって確認
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from datetime import datetime
import json


class ObjectType(Enum):
    """オブジェクトの種類"""
    CONCEPT = "concept"      # 抽象概念
    TASK = "task"           # タスク
    TOOL = "tool"           # ツール
    PATTERN = "pattern"     # パターン
    SOLUTION = "solution"   # 解決策
    DOMAIN = "domain"       # ドメイン知識


class RelationType(Enum):
    """関係の種類"""
    CAUSES = "causes"           # 因果関係
    REQUIRES = "requires"       # 依存関係
    SIMILAR_TO = "similar_to"   # 類似関係
    PART_OF = "part_of"         # 部分-全体関係
    FOLLOWS = "follows"         # 順序関係
    CONFLICTS = "conflicts"     # 競合関係


@dataclass
class CrossObject:
    """Cross世界のオブジェクト"""
    id: str
    type: ObjectType
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None  # 意味埋め込み
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 0.5  # 確信度

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "properties": self.properties,
            "created_at": self.created_at,
            "confidence": self.confidence
        }


@dataclass
class CrossRegion:
    """Cross世界の領域（複数のオブジェクトのグループ）"""
    id: str
    name: str
    objects: Set[str] = field(default_factory=set)  # オブジェクトIDのセット
    properties: Dict[str, Any] = field(default_factory=dict)
    parent_region: Optional[str] = None  # 親領域

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "name": self.name,
            "objects": list(self.objects),
            "properties": self.properties,
            "parent_region": self.parent_region
        }


@dataclass
class CrossRelation:
    """Cross世界の関係"""
    source_id: str
    target_id: str
    relation_type: RelationType
    strength: float = 1.0  # 関係の強さ
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relation_type.value,
            "strength": self.strength,
            "properties": self.properties
        }


class CrossWorldModel:
    """
    Cross World Model - Verantyxの世界モデル

    構造:
    - Objects: 概念・タスク・ツール・パターン
    - Regions: オブジェクトのグループ（ドメイン等）
    - Relations: オブジェクト間の関係
    - Topology: 構造的配置

    機能:
    - オブジェクトの追加・検索
    - 関係の構築・推論
    - 領域の形成・階層化
    - トポロジカル推論
    """

    def __init__(self):
        # オブジェクト管理
        self.objects: Dict[str, CrossObject] = {}

        # 領域管理
        self.regions: Dict[str, CrossRegion] = {}

        # 関係管理
        self.relations: List[CrossRelation] = []

        # インデックス（高速検索用）
        self.type_index: Dict[ObjectType, Set[str]] = {
            t: set() for t in ObjectType
        }
        self.relation_index: Dict[str, List[CrossRelation]] = {}

        # 統計
        self.stats = {
            "objects_created": 0,
            "relations_created": 0,
            "regions_created": 0,
            "simulations_run": 0
        }

    # ========================================
    # Object Operations
    # ========================================

    def add_object(
        self,
        obj_type: ObjectType,
        name: str,
        properties: Optional[Dict] = None,
        confidence: float = 0.5
    ) -> CrossObject:
        """
        オブジェクトを追加

        Args:
            obj_type: オブジェクトの種類
            name: オブジェクト名
            properties: プロパティ
            confidence: 確信度

        Returns:
            作成されたオブジェクト
        """
        obj_id = f"{obj_type.value}_{len(self.objects)}"

        obj = CrossObject(
            id=obj_id,
            type=obj_type,
            name=name,
            properties=properties or {},
            confidence=confidence
        )

        self.objects[obj_id] = obj
        self.type_index[obj_type].add(obj_id)
        self.stats["objects_created"] += 1

        return obj

    def get_object(self, obj_id: str) -> Optional[CrossObject]:
        """オブジェクトを取得"""
        return self.objects.get(obj_id)

    def find_objects_by_type(self, obj_type: ObjectType) -> List[CrossObject]:
        """タイプでオブジェクトを検索"""
        obj_ids = self.type_index.get(obj_type, set())
        return [self.objects[oid] for oid in obj_ids if oid in self.objects]

    def find_objects_by_property(
        self,
        property_name: str,
        property_value: Any
    ) -> List[CrossObject]:
        """プロパティでオブジェクトを検索"""
        results = []
        for obj in self.objects.values():
            if obj.properties.get(property_name) == property_value:
                results.append(obj)
        return results

    # ========================================
    # Relation Operations
    # ========================================

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        strength: float = 1.0,
        properties: Optional[Dict] = None
    ) -> CrossRelation:
        """
        関係を追加

        Args:
            source_id: ソースオブジェクトID
            target_id: ターゲットオブジェクトID
            relation_type: 関係の種類
            strength: 関係の強さ
            properties: プロパティ

        Returns:
            作成された関係
        """
        relation = CrossRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            strength=strength,
            properties=properties or {}
        )

        self.relations.append(relation)

        # インデックス更新
        if source_id not in self.relation_index:
            self.relation_index[source_id] = []
        self.relation_index[source_id].append(relation)

        self.stats["relations_created"] += 1

        return relation

    def get_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[RelationType] = None
    ) -> List[CrossRelation]:
        """関係を検索"""
        results = self.relations.copy()

        if source_id:
            results = [r for r in results if r.source_id == source_id]

        if target_id:
            results = [r for r in results if r.target_id == target_id]

        if relation_type:
            results = [r for r in results if r.relation_type == relation_type]

        return results

    def find_related_objects(
        self,
        obj_id: str,
        relation_type: Optional[RelationType] = None,
        max_depth: int = 1
    ) -> List[Tuple[CrossObject, float]]:
        """
        関連オブジェクトを検索（トポロジカル探索）

        Args:
            obj_id: 起点オブジェクトID
            relation_type: 関係の種類（Noneなら全種類）
            max_depth: 探索深さ

        Returns:
            (オブジェクト, 関連度)のリスト
        """
        visited = set()
        results = []

        def dfs(current_id: str, depth: int, cumulative_strength: float):
            if depth > max_depth or current_id in visited:
                return

            visited.add(current_id)

            relations = self.relation_index.get(current_id, [])

            for rel in relations:
                if relation_type and rel.relation_type != relation_type:
                    continue

                target = self.get_object(rel.target_id)
                if target:
                    strength = cumulative_strength * rel.strength
                    results.append((target, strength))
                    dfs(rel.target_id, depth + 1, strength)

        dfs(obj_id, 0, 1.0)

        # 関連度でソート
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    # ========================================
    # Region Operations
    # ========================================

    def create_region(
        self,
        name: str,
        objects: Optional[Set[str]] = None,
        parent_region: Optional[str] = None
    ) -> CrossRegion:
        """
        領域を作成

        Args:
            name: 領域名
            objects: オブジェクトIDのセット
            parent_region: 親領域ID

        Returns:
            作成された領域
        """
        region_id = f"region_{len(self.regions)}"

        region = CrossRegion(
            id=region_id,
            name=name,
            objects=objects or set(),
            parent_region=parent_region
        )

        self.regions[region_id] = region
        self.stats["regions_created"] += 1

        return region

    def add_to_region(self, region_id: str, obj_id: str):
        """領域にオブジェクトを追加"""
        region = self.regions.get(region_id)
        if region:
            region.objects.add(obj_id)

    def get_region_objects(self, region_id: str) -> List[CrossObject]:
        """領域内のオブジェクトを取得"""
        region = self.regions.get(region_id)
        if not region:
            return []

        return [
            self.objects[oid]
            for oid in region.objects
            if oid in self.objects
        ]

    # ========================================
    # Topology & Reasoning
    # ========================================

    def infer_causal_chain(
        self,
        start_obj_id: str,
        end_obj_id: str,
        max_steps: int = 10
    ) -> Optional[List[str]]:
        """
        因果チェーンを推論

        Args:
            start_obj_id: 開始オブジェクト
            end_obj_id: 終了オブジェクト
            max_steps: 最大ステップ数

        Returns:
            因果チェーン（オブジェクトIDのリスト）
        """
        # BFS for causal path
        from collections import deque

        queue = deque([(start_obj_id, [start_obj_id])])
        visited = set()

        while queue:
            current_id, path = queue.popleft()

            if current_id == end_obj_id:
                return path

            if len(path) > max_steps or current_id in visited:
                continue

            visited.add(current_id)

            # CAUSESリレーションを辿る
            relations = self.get_relations(
                source_id=current_id,
                relation_type=RelationType.CAUSES
            )

            for rel in relations:
                if rel.target_id not in visited:
                    queue.append((rel.target_id, path + [rel.target_id]))

        return None

    def find_similar_patterns(
        self,
        pattern_obj_id: str,
        threshold: float = 0.5
    ) -> List[Tuple[CrossObject, float]]:
        """
        類似パターンを検索

        Args:
            pattern_obj_id: パターンオブジェクトID
            threshold: 類似度閾値

        Returns:
            (類似オブジェクト, 類似度)のリスト
        """
        pattern_obj = self.get_object(pattern_obj_id)
        if not pattern_obj:
            return []

        # SIMILAR_TO関係を検索
        similar_rels = self.get_relations(
            source_id=pattern_obj_id,
            relation_type=RelationType.SIMILAR_TO
        )

        results = []
        for rel in similar_rels:
            if rel.strength >= threshold:
                target = self.get_object(rel.target_id)
                if target:
                    results.append((target, rel.strength))

        results.sort(key=lambda x: x[1], reverse=True)

        return results

    # ========================================
    # Serialization
    # ========================================

    def to_cross_structure(self) -> Dict:
        """
        Cross構造形式でエクスポート

        Returns:
            6軸Cross構造
        """
        cross = {
            "UP": [],      # 抽象概念
            "DOWN": [],    # 具体実装
            "LEFT": [],    # 原因・入力
            "RIGHT": [],   # 結果・出力
            "FRONT": [],   # 未来・予測
            "BACK": [],    # 過去・履歴
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "stats": self.stats
            }
        }

        # Objects by type
        for obj in self.objects.values():
            if obj.type == ObjectType.CONCEPT:
                cross["UP"].append(obj.to_dict())
            elif obj.type == ObjectType.TASK:
                cross["LEFT"].append(obj.to_dict())
            elif obj.type == ObjectType.SOLUTION:
                cross["RIGHT"].append(obj.to_dict())
            elif obj.type == ObjectType.PATTERN:
                cross["FRONT"].append(obj.to_dict())
            else:
                cross["DOWN"].append(obj.to_dict())

        # Relations
        cross["relations"] = [r.to_dict() for r in self.relations]

        # Regions
        cross["regions"] = [r.to_dict() for r in self.regions.values()]

        return cross

    def save_to_file(self, filepath: str):
        """ファイルに保存"""
        cross_data = self.to_cross_structure()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cross_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> 'CrossWorldModel':
        """ファイルから読み込み"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        model = cls()

        # Objects
        for axis in ["UP", "DOWN", "LEFT", "RIGHT", "FRONT", "BACK"]:
            for obj_data in data.get(axis, []):
                obj = CrossObject(
                    id=obj_data["id"],
                    type=ObjectType(obj_data["type"]),
                    name=obj_data["name"],
                    properties=obj_data.get("properties", {}),
                    created_at=obj_data.get("created_at", ""),
                    confidence=obj_data.get("confidence", 0.5)
                )
                model.objects[obj.id] = obj
                model.type_index[obj.type].add(obj.id)

        # Relations
        for rel_data in data.get("relations", []):
            rel = CrossRelation(
                source_id=rel_data["source"],
                target_id=rel_data["target"],
                relation_type=RelationType(rel_data["type"]),
                strength=rel_data.get("strength", 1.0),
                properties=rel_data.get("properties", {})
            )
            model.relations.append(rel)

            if rel.source_id not in model.relation_index:
                model.relation_index[rel.source_id] = []
            model.relation_index[rel.source_id].append(rel)

        # Regions
        for reg_data in data.get("regions", []):
            region = CrossRegion(
                id=reg_data["id"],
                name=reg_data["name"],
                objects=set(reg_data.get("objects", [])),
                properties=reg_data.get("properties", {}),
                parent_region=reg_data.get("parent_region")
            )
            model.regions[region.id] = region

        return model

    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        return {
            "total_objects": len(self.objects),
            "total_relations": len(self.relations),
            "total_regions": len(self.regions),
            "objects_by_type": {
                t.value: len(self.type_index[t])
                for t in ObjectType
            },
            "relations_by_type": {
                t.value: len([r for r in self.relations if r.relation_type == t])
                for t in RelationType
            },
            **self.stats
        }
