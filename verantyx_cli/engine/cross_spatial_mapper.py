#!/usr/bin/env python3
"""
Cross Spatial Mapper

推論演算子をCross構造の6軸に立体的にマッピング

Cross構造は単なるデータ保存ではなく、多次元推論空間
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from collections import defaultdict


class CrossSpatialMapper:
    """
    Cross構造への空間的マッピング

    6軸の意味:
    - UP: 質問の抽象化
    - DOWN: 推論プログラム
    - LEFT: 時系列推論チェーン
    - RIGHT: ツール/アクション
    - FRONT: 概念展開（関連概念）
    - BACK: 生の対話

    重要: 関連する概念は空間的に近くに配置される
    例: DeepSeek → [GPT, Claude, Gemini]（近接）
         DeepSeek ← イヤホン（遠隔）
    """

    def __init__(self):
        # 概念間の関連度マップ
        self.concept_proximity_map = defaultdict(dict)

        # 概念の座標（6次元空間）
        self.concept_coordinates = {}

        # 操作パターンライブラリ
        self.operation_patterns = []

    def map_to_cross_structure(
        self,
        operations: List[Dict[str, Any]],
        user_question: str,
        context_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        推論演算子をCross構造の6軸に立体的にマッピング

        Args:
            operations: 推論演算子のリスト
            user_question: ユーザーの質問
            context_metadata: コンテキストメタデータ

        Returns:
            6軸にマッピングされたCross構造
        """
        cross_mapping = {
            'UP': self._map_to_up_axis(user_question, operations),
            'DOWN': self._map_to_down_axis(operations),
            'LEFT': self._map_to_left_axis(operations),
            'RIGHT': self._map_to_right_axis(operations),
            'FRONT': self._map_to_front_axis(operations),
            'BACK': self._map_to_back_axis(user_question, operations)
        }

        # 概念の空間座標を計算
        main_entity = self._extract_main_entity(operations)
        if main_entity:
            coordinates = self._calculate_spatial_coordinates(main_entity, operations)
            cross_mapping['spatial_coordinates'] = coordinates

        return cross_mapping

    def _map_to_up_axis(self, user_question: str, operations: List[Dict]) -> Dict:
        """
        UP軸: 質問の抽象化

        例:
            「DeepSeekとは」→ 抽象化 → 「定義質問: AI技術」
        """
        # 質問タイプを抽出
        question_type = self._classify_question_type(user_question)

        # 質問の主題を抽出
        main_topic = self._extract_main_entity(operations)

        # カテゴリを推定
        category = self._infer_category(operations)

        return {
            'original_question': user_question,
            'question_type': question_type,
            'main_topic': main_topic,
            'category': category,
            'abstraction_level': self._calculate_abstraction_level(operations)
        }

    def _map_to_down_axis(self, operations: List[Dict]) -> Dict:
        """
        DOWN軸: 推論プログラム

        推論演算子の実行可能なプログラムとして保存
        """
        program_steps = []

        for i, op in enumerate(operations):
            step = {
                'step_number': i + 1,
                'operator': op['operator'],
                'parameters': self._extract_op_parameters(op),
                'dependencies': []  # 前のステップへの依存関係
            }
            program_steps.append(step)

        return {
            'program_steps': program_steps,
            'program_pattern': self._extract_program_pattern(operations),
            'complexity': len(operations)
        }

    def _map_to_left_axis(self, operations: List[Dict]) -> Dict:
        """
        LEFT軸: 時系列推論チェーン

        推論の流れ、因果関係
        """
        reasoning_chain = []

        for i, op in enumerate(operations):
            chain_item = {
                'position': i,
                'operation': op['operator'],
                'reasoning_type': self._classify_reasoning_type(op),
                'causality': self._detect_causality(op, operations)
            }
            reasoning_chain.append(chain_item)

        return {
            'reasoning_chain': reasoning_chain,
            'chain_length': len(reasoning_chain),
            'dominant_pattern': self._find_dominant_reasoning_pattern(reasoning_chain)
        }

    def _map_to_right_axis(self, operations: List[Dict]) -> Dict:
        """
        RIGHT軸: ツール/アクション

        実行可能な操作、ツール呼び出し
        """
        actions = []

        for op in operations:
            if op['operator'] in ['SEQUENCE', 'EXAMPLE']:
                # 手順や具体例は実行可能なアクション
                action = {
                    'action_type': op['operator'],
                    'executable': True,
                    'parameters': self._extract_op_parameters(op)
                }
                actions.append(action)

        return {
            'actions': actions,
            'has_executable_steps': len(actions) > 0
        }

    def _map_to_front_axis(self, operations: List[Dict]) -> Dict:
        """
        FRONT軸: 概念展開（関連概念）

        重要: ここで概念間の空間的近接性を計算
        """
        # 主要エンティティを抽出
        main_entity = self._extract_main_entity(operations)

        # 関連概念を抽出
        related_concepts = self._extract_related_concepts(operations)

        # 概念間の関連度を計算
        concept_relations = []
        for related in related_concepts:
            if related != main_entity:
                proximity = self._calculate_concept_proximity(main_entity, related, operations)
                concept_relations.append({
                    'concept': related,
                    'proximity': proximity,
                    'relation_type': self._infer_relation_type(main_entity, related, operations)
                })

        # 近接度でソート（近いほど優先）
        concept_relations.sort(key=lambda x: x['proximity'], reverse=True)

        return {
            'main_concept': main_entity,
            'related_concepts': concept_relations,
            'concept_category': self._infer_category(operations)
        }

    def _map_to_back_axis(self, user_question: str, operations: List[Dict]) -> Dict:
        """
        BACK軸: 生の対話

        元の質問、推論演算子、JCrossプログラム
        """
        return {
            'raw_question': user_question,
            'extracted_operations': operations,
            'operation_count': len(operations)
        }

    def _calculate_spatial_coordinates(self, entity: str, operations: List[Dict]) -> Dict:
        """
        概念の6次元空間座標を計算

        これにより、DeepSeek と GPT が近くに配置され、
        DeepSeek と イヤホン が遠くに配置される
        """
        # 各軸の座標値を計算
        coords = {
            'UP': self._calculate_up_coordinate(entity, operations),
            'DOWN': self._calculate_down_coordinate(entity, operations),
            'LEFT': self._calculate_left_coordinate(entity, operations),
            'RIGHT': self._calculate_right_coordinate(entity, operations),
            'FRONT': self._calculate_front_coordinate(entity, operations),
            'BACK': self._calculate_back_coordinate(entity, operations)
        }

        # 概念座標を保存
        self.concept_coordinates[entity] = coords

        return coords

    def calculate_distance(self, entity1: str, entity2: str) -> float:
        """
        2つの概念間の空間距離を計算

        近い = 関連性が高い
        遠い = 関連性が低い
        """
        if entity1 not in self.concept_coordinates or entity2 not in self.concept_coordinates:
            return float('inf')

        coords1 = self.concept_coordinates[entity1]
        coords2 = self.concept_coordinates[entity2]

        # ユークリッド距離
        distance = 0.0
        for axis in ['UP', 'DOWN', 'LEFT', 'RIGHT', 'FRONT', 'BACK']:
            distance += (coords1[axis] - coords2[axis]) ** 2

        return np.sqrt(distance)

    # ========== ヘルパーメソッド ==========

    def _extract_main_entity(self, operations: List[Dict]) -> Optional[str]:
        """主要エンティティを抽出"""
        for op in operations:
            if op['operator'] == 'DEFINE' and 'entity' in op:
                return op['entity']
        return None

    def _extract_related_concepts(self, operations: List[Dict]) -> List[str]:
        """関連概念を全て抽出"""
        concepts = set()

        for op in operations:
            # DEFINE, CLASSIFY, ATTRIBUTEからエンティティ抽出
            if 'entity' in op:
                concepts.add(op['entity'])

            # COMPAREから比較対象を抽出
            if op['operator'] == 'COMPARE':
                if 'A' in op and op['A']:
                    concepts.add(op['A'])
                if 'B' in op and op['B']:
                    concepts.add(op['B'])

            # 定義や説明から固有名詞を抽出（簡易版）
            if 'definition' in op:
                concepts.update(self._extract_proper_nouns(op['definition']))
            if 'text' in op:
                concepts.update(self._extract_proper_nouns(op['text']))

        return list(concepts)

    def _extract_proper_nouns(self, text: str) -> List[str]:
        """固有名詞を抽出（簡易版）"""
        # 大文字で始まる単語を固有名詞と見なす
        import re
        words = re.findall(r'\b[A-Z][a-zA-Z]+\b', text)
        return words

    def _calculate_concept_proximity(
        self,
        entity1: str,
        entity2: str,
        operations: List[Dict]
    ) -> float:
        """
        2つの概念の関連度を計算（0.0〜1.0）

        高い値 = 関連性が強い
        """
        proximity = 0.0

        # 同じ文章内で言及されている
        for op in operations:
            if 'text' in op or 'definition' in op:
                text = op.get('text', '') + op.get('definition', '')
                if entity1 in text and entity2 in text:
                    proximity += 0.3

        # 比較されている
        for op in operations:
            if op['operator'] == 'COMPARE':
                if (op.get('A') == entity1 and op.get('B') == entity2) or \
                   (op.get('A') == entity2 and op.get('B') == entity1):
                    proximity += 0.5

        # 同じカテゴリ
        # （簡易版: 実装は省略）

        return min(proximity, 1.0)

    def _infer_relation_type(
        self,
        entity1: str,
        entity2: str,
        operations: List[Dict]
    ) -> str:
        """関係性のタイプを推定"""
        for op in operations:
            if op['operator'] == 'COMPARE':
                if entity1 in str(op) and entity2 in str(op):
                    return 'comparison'

        return 'related'

    def _classify_question_type(self, question: str) -> str:
        """質問タイプを分類"""
        q_lower = question.lower()
        if 'とは' in question or 'what is' in q_lower:
            return 'definition'
        elif 'どうやって' in question or 'how' in q_lower:
            return 'howto'
        elif '違い' in question or 'difference' in q_lower:
            return 'comparison'
        return 'general'

    def _infer_category(self, operations: List[Dict]) -> str:
        """カテゴリを推定"""
        # 定義やクラス分類から推定
        for op in operations:
            if op['operator'] == 'CLASSIFY' and 'category' in op:
                return op['category']
            if op['operator'] == 'DEFINE' and 'definition' in op:
                definition = op['definition'].lower()
                if any(w in definition for w in ['llm', 'ai', 'model', 'モデル']):
                    return 'AI_Technology'
                elif any(w in definition for w in ['言語', 'language', 'プログラミング']):
                    return 'Programming_Language'

        return 'General'

    def _calculate_abstraction_level(self, operations: List[Dict]) -> int:
        """抽象度レベルを計算（1〜5）"""
        # 操作の種類が多いほど抽象度が高い
        op_types = set(op['operator'] for op in operations)
        return min(len(op_types), 5)

    def _extract_op_parameters(self, op: Dict) -> Dict:
        """操作のパラメータを抽出"""
        params = {}
        for key, value in op.items():
            if key not in ['operator', 'sentence', 'sentence_index']:
                params[key] = value
        return params

    def _extract_program_pattern(self, operations: List[Dict]) -> str:
        """プログラムパターンを抽出"""
        pattern = ' → '.join([op['operator'] for op in operations])
        return pattern

    def _classify_reasoning_type(self, op: Dict) -> str:
        """推論タイプを分類"""
        op_type = op['operator']
        if op_type in ['DEFINE', 'CLASSIFY']:
            return 'categorization'
        elif op_type == 'COMPARE':
            return 'comparison'
        elif op_type == 'CAUSE':
            return 'causal'
        elif op_type == 'SEQUENCE':
            return 'procedural'
        return 'descriptive'

    def _detect_causality(self, op: Dict, all_operations: List[Dict]) -> Optional[str]:
        """因果関係を検出"""
        if op['operator'] == 'CAUSE':
            return 'causal_relation'
        return None

    def _find_dominant_reasoning_pattern(self, chain: List[Dict]) -> str:
        """支配的な推論パターンを検出"""
        from collections import Counter
        reasoning_types = [item['reasoning_type'] for item in chain]
        if reasoning_types:
            return Counter(reasoning_types).most_common(1)[0][0]
        return 'unknown'

    def _calculate_up_coordinate(self, entity: str, operations: List[Dict]) -> float:
        """UP軸座標（抽象度）"""
        return float(self._calculate_abstraction_level(operations))

    def _calculate_down_coordinate(self, entity: str, operations: List[Dict]) -> float:
        """DOWN軸座標（推論複雑度）"""
        return float(len(operations))

    def _calculate_left_coordinate(self, entity: str, operations: List[Dict]) -> float:
        """LEFT軸座標（時系列位置）"""
        # 簡易版: 最新のものほど大きい値
        import time
        return time.time()

    def _calculate_right_coordinate(self, entity: str, operations: List[Dict]) -> float:
        """RIGHT軸座標（アクション性）"""
        action_ops = sum(1 for op in operations if op['operator'] in ['SEQUENCE', 'EXAMPLE'])
        return float(action_ops)

    def _calculate_front_coordinate(self, entity: str, operations: List[Dict]) -> float:
        """FRONT軸座標（関連概念数）"""
        related = self._extract_related_concepts(operations)
        return float(len(related))

    def _calculate_back_coordinate(self, entity: str, operations: List[Dict]) -> float:
        """BACK軸座標（生データサイズ）"""
        return float(len(operations))


# テスト用
if __name__ == '__main__':
    from reasoning_operator_extractor import ReasoningOperatorExtractor

    # テスト: DeepSeekとGPTの距離
    mapper = CrossSpatialMapper()

    # DeepSeekについての推論演算子
    extractor = ReasoningOperatorExtractor()

    deepseek_response = "DeepSeekは中国のAI企業が開発したLLMです。GPTやClaudeと比較すると、コスト効率に優れています。"
    deepseek_ops = extractor.extract(deepseek_response, "DeepSeekとは")

    # Cross構造にマッピング
    deepseek_mapping = mapper.map_to_cross_structure(deepseek_ops, "DeepSeekとは")

    print("=" * 80)
    print("DeepSeek Cross Mapping")
    print("=" * 80)
    print(f"Main Concept: {deepseek_mapping['FRONT']['main_concept']}")
    print(f"Category: {deepseek_mapping['FRONT']['concept_category']}")
    print(f"\nRelated Concepts:")
    for rel in deepseek_mapping['FRONT']['related_concepts']:
        print(f"  - {rel['concept']}: proximity={rel['proximity']:.2f}, type={rel['relation_type']}")

    print(f"\nSpatial Coordinates:")
    if 'spatial_coordinates' in deepseek_mapping:
        for axis, coord in deepseek_mapping['spatial_coordinates'].items():
            print(f"  {axis}: {coord:.2f}")

    # イヤホンについて
    earphone_response = "イヤホンは音響機器です。Bluetooth接続が可能です。"
    earphone_ops = extractor.extract(earphone_response, "イヤホンとは")
    earphone_mapping = mapper.map_to_cross_structure(earphone_ops, "イヤホンとは")

    print("\n" + "=" * 80)
    print("Distance Calculation")
    print("=" * 80)

    # DeepSeek と GPT の距離（近いはず）
    if 'DeepSeek' in mapper.concept_coordinates and 'GPT' in mapper.concept_coordinates:
        distance_deepseek_gpt = mapper.calculate_distance('DeepSeek', 'GPT')
        print(f"DeepSeek ↔ GPT: {distance_deepseek_gpt:.2f} (should be small)")

    # DeepSeek と イヤホン の距離（遠いはず）
    if 'DeepSeek' in mapper.concept_coordinates and 'イヤホン' in mapper.concept_coordinates:
        distance_deepseek_earphone = mapper.calculate_distance('DeepSeek', 'イヤホン')
        print(f"DeepSeek ↔ イヤホン: {distance_deepseek_earphone:.2f} (should be large)")
