#!/usr/bin/env python3
"""
Cross操作コマンドシミュレータ

機能:
1. JCrossプログラムの操作コマンドを実際に実行
2. 操作自体の位置をCross空間上に記録
3. 推論の流れ（操作の連鎖）を位置として学習
4. 操作の実行履歴から推論パターンを抽出
"""

import re
import math
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path


class CrossCommandSimulator:
    """
    Cross操作コマンドを実際に実行してCross空間をシミュレート

    原則:
    - 操作コマンド自体もCross空間上の位置を持つ
    - 連続する操作は近い位置に配置される（推論の流れ）
    - 同じパターンの推論は位置が近づく
    """

    def __init__(self, cross_space_manager):
        """
        Args:
            cross_space_manager: CrossSpaceManagerインスタンス
        """
        self.cross_space = cross_space_manager

        # 操作の位置を記録
        self.operation_positions = {}  # {operation_id: position}

        # 推論フローを記録
        self.reasoning_flows = []  # 推論の流れ（操作の連鎖）

        # 現在実行中のフロー
        self.current_flow = None

        # 操作ハンドラー
        self.operation_handlers = {
            '分類設定': self._handle_classify,
            '属性設定': self._handle_attribute,
            '概念定義': self._handle_define,
            '比較実行': self._handle_compare,
            '特徴列挙': self._handle_list_features,
        }

    def execute_program(
        self,
        jcross_program: str,
        context_id: str,
        initial_position: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        JCrossプログラム全体を実行

        Args:
            jcross_program: JCrossプログラム文字列
            context_id: コンテキストID
            initial_position: 初期位置（Noneの場合はランダム）

        Returns:
            実行結果
        """
        # 新しい推論フローを開始
        self.current_flow = {
            'context_id': context_id,
            'operations': [],
            'start_position': initial_position or self._generate_random_position(),
            'current_position': initial_position or self._generate_random_position(),
            'started_at': datetime.now().isoformat()
        }

        # プログラムを行ごとに解析
        lines = jcross_program.split('\n')

        for line in lines:
            line = line.strip()

            # コメント行はスキップ
            if line.startswith('#') or not line:
                continue

            # 操作コマンドを実行
            self._execute_command(line, context_id)

        # フローを保存
        self.reasoning_flows.append(self.current_flow)

        result = {
            'flow_id': len(self.reasoning_flows) - 1,
            'operations_count': len(self.current_flow['operations']),
            'start_position': self.current_flow['start_position'],
            'end_position': self.current_flow['current_position'],
            'flow_distance': self._calculate_flow_distance()
        }

        self.current_flow = None

        return result

    def _execute_command(self, command: str, context_id: str):
        """
        単一の操作コマンドを実行

        例: "分類設定 実体=りんご カテゴリ=バラ科"
        """
        # コマンドをパース
        parsed = self._parse_command(command)

        if not parsed:
            return

        operation_type = parsed['operation']
        params = parsed['params']

        # ハンドラーを取得
        handler = self.operation_handlers.get(operation_type)

        if not handler:
            print(f"⚠️  Unknown operation: {operation_type}")
            return

        # 操作を実行
        handler(params, context_id)

        # 操作の位置を記録
        operation_id = f"{operation_type}_{len(self.current_flow['operations'])}"
        operation_position = self.current_flow['current_position'].copy()

        self.operation_positions[operation_id] = operation_position

        # フローに追加
        self.current_flow['operations'].append({
            'id': operation_id,
            'type': operation_type,
            'params': params,
            'position': operation_position,
            'timestamp': datetime.now().isoformat()
        })

        # 次の操作位置を調整（推論の流れに沿って移動）
        self._move_to_next_operation_position(operation_type)

    def _parse_command(self, command: str) -> Optional[Dict]:
        """
        操作コマンドをパース

        例:
        Input: "分類設定 実体=りんご カテゴリ=バラ科"
        Output: {
            'operation': '分類設定',
            'params': {'実体': 'りんご', 'カテゴリ': 'バラ科'}
        }
        """
        # 操作タイプを抽出
        parts = command.split(maxsplit=1)

        if len(parts) < 2:
            return None

        operation = parts[0]
        params_str = parts[1]

        # パラメータを抽出
        params = {}
        param_pattern = r'(\S+)=(\S+)'
        matches = re.findall(param_pattern, params_str)

        for key, value in matches:
            params[key] = value

        return {
            'operation': operation,
            'params': params
        }

    def _handle_classify(self, params: Dict, context_id: str):
        """
        分類設定を実行

        例: 分類設定 実体=りんご カテゴリ=バラ科
        """
        entity = params.get('実体')
        category = params.get('カテゴリ')

        if not entity or not category:
            return

        # Cross空間のインデックスに追加
        self.cross_space.category_index[category].add(entity)

        # 実体とカテゴリを単語層に追加（位置は現在のフロー位置）
        timestamp = datetime.now().isoformat()

        # 実体の位置 = 現在のフロー位置
        if entity not in self.cross_space.word_layer:
            self.cross_space.word_layer[entity] = {
                'position': self.current_flow['current_position'].copy(),
                'frequency': 1,
                'contexts': [context_id],
                'neighbors': {},
                'operations': ['CLASSIFY'],
                'first_seen': timestamp,
                'last_updated': timestamp
            }

        # カテゴリの位置 = 実体の近く
        category_position = self._generate_position_near(
            self.current_flow['current_position'],
            radius=0.1
        )

        if category not in self.cross_space.word_layer:
            self.cross_space.word_layer[category] = {
                'position': category_position,
                'frequency': 1,
                'contexts': [context_id],
                'neighbors': {},
                'operations': [],
                'first_seen': timestamp,
                'last_updated': timestamp
            }

        # 関係を記録
        self.cross_space._add_relation(entity, category, 'is_a', context_id)

    def _handle_attribute(self, params: Dict, context_id: str):
        """
        属性設定を実行

        例: 属性設定 実体=りんご 属性=学名 値=Malus_domestica
        """
        entity = params.get('実体')
        attr = params.get('属性')
        value = params.get('値')

        if not entity or not attr or not value:
            return

        # Cross空間のインデックスに追加
        if attr not in self.cross_space.attribute_index:
            self.cross_space.attribute_index[attr] = {}

        self.cross_space.attribute_index[attr][value] = entity

        # 実体と値を単語層に追加
        timestamp = datetime.now().isoformat()

        if entity not in self.cross_space.word_layer:
            self.cross_space.word_layer[entity] = {
                'position': self.current_flow['current_position'].copy(),
                'frequency': 1,
                'contexts': [context_id],
                'neighbors': {},
                'operations': ['ATTRIBUTE'],
                'first_seen': timestamp,
                'last_updated': timestamp
            }

        # 値の位置 = 実体の近く
        value_position = self._generate_position_near(
            self.current_flow['current_position'],
            radius=0.05  # 属性値は実体にさらに近い
        )

        if value not in self.cross_space.word_layer:
            self.cross_space.word_layer[value] = {
                'position': value_position,
                'frequency': 1,
                'contexts': [context_id],
                'neighbors': {},
                'operations': [],
                'first_seen': timestamp,
                'last_updated': timestamp
            }

        # 関係を記録
        self.cross_space._add_relation(entity, value, 'has_attr', context_id)

    def _handle_define(self, params: Dict, context_id: str):
        """概念定義を実行"""
        entity = params.get('実体')
        value = params.get('値')

        if not entity or not value:
            return

        timestamp = datetime.now().isoformat()

        if entity not in self.cross_space.word_layer:
            self.cross_space.word_layer[entity] = {
                'position': self.current_flow['current_position'].copy(),
                'frequency': 1,
                'contexts': [context_id],
                'neighbors': {},
                'operations': ['DEFINE'],
                'first_seen': timestamp,
                'last_updated': timestamp,
                'definition': value
            }

    def _handle_compare(self, params: Dict, context_id: str):
        """比較実行"""
        a = params.get('対象A')
        b = params.get('対象B')

        if not a or not b:
            return

        # 比較対象同士を関連付ける
        self.cross_space._add_relation(a, b, 'compared_with', context_id)

    def _handle_list_features(self, params: Dict, context_id: str):
        """特徴列挙"""
        entity = params.get('実体')
        features = params.get('特徴', '').split(',')

        if not entity:
            return

        timestamp = datetime.now().isoformat()

        if entity not in self.cross_space.word_layer:
            self.cross_space.word_layer[entity] = {
                'position': self.current_flow['current_position'].copy(),
                'frequency': 1,
                'contexts': [context_id],
                'neighbors': {},
                'operations': ['LIST_FEATURES'],
                'first_seen': timestamp,
                'last_updated': timestamp,
                'features': features
            }

    def _move_to_next_operation_position(self, operation_type: str):
        """
        次の操作位置に移動（推論の流れを表現）

        連続する操作は近い位置に配置される
        """
        # 推論の流れに沿ってわずかに移動
        # 操作タイプに応じて移動方向を変える

        movement = {
            '分類設定': [0.02, 0.01, 0.0, 0.0, 0.0, 0.0],    # UP-DOWN軸に移動
            '属性設定': [0.0, 0.0, 0.02, 0.01, 0.0, 0.0],    # LEFT-RIGHT軸に移動
            '概念定義': [0.01, 0.0, 0.0, 0.0, 0.02, 0.0],    # UP-FRONT軸に移動
            '比較実行': [0.0, 0.02, 0.0, 0.0, 0.0, 0.01],    # DOWN-BACK軸に移動
            '特徴列挙': [0.0, 0.0, 0.01, 0.0, 0.01, 0.0],    # LEFT-FRONT軸に移動
        }

        move_vector = movement.get(operation_type, [0.01] * 6)

        # 現在位置を更新
        for i in range(6):
            self.current_flow['current_position'][i] = max(
                0.0,
                min(1.0, self.current_flow['current_position'][i] + move_vector[i])
            )

    def _calculate_flow_distance(self) -> float:
        """推論フロー全体の距離を計算"""
        start = self.current_flow['start_position']
        end = self.current_flow['current_position']

        return math.sqrt(sum((s - e) ** 2 for s, e in zip(start, end)))

    def _generate_random_position(self) -> List[float]:
        """ランダムな6次元位置を生成"""
        import random
        return [random.random() for _ in range(6)]

    def _generate_position_near(
        self,
        center: List[float],
        radius: float = 0.1
    ) -> List[float]:
        """中心位置の近くにランダムな位置を生成"""
        import random
        return [
            max(0.0, min(1.0, c + random.uniform(-radius, radius)))
            for c in center
        ]

    def find_similar_flows(
        self,
        current_operations: List[str],
        similarity_threshold: float = 0.7
    ) -> List[Dict]:
        """
        類似する推論フローを検索

        Args:
            current_operations: 現在の操作列 ['CLASSIFY', 'ATTRIBUTE', ...]
            similarity_threshold: 類似度閾値

        Returns:
            類似フローのリスト
        """
        similar_flows = []

        for flow in self.reasoning_flows:
            flow_ops = [op['type'] for op in flow['operations']]

            # 操作列の類似度を計算（Jaccard類似度）
            set_current = set(current_operations)
            set_flow = set(flow_ops)

            intersection = len(set_current & set_flow)
            union = len(set_current | set_flow)

            if union > 0:
                similarity = intersection / union

                if similarity >= similarity_threshold:
                    similar_flows.append({
                        'flow': flow,
                        'similarity': similarity,
                        'operations_match': list(set_current & set_flow)
                    })

        # 類似度でソート
        similar_flows.sort(key=lambda x: x['similarity'], reverse=True)

        return similar_flows

    def get_operation_statistics(self) -> Dict[str, Any]:
        """操作統計を取得"""
        operation_counts = {}

        for flow in self.reasoning_flows:
            for op in flow['operations']:
                op_type = op['type']
                operation_counts[op_type] = operation_counts.get(op_type, 0) + 1

        return {
            'total_flows': len(self.reasoning_flows),
            'total_operations': sum(len(f['operations']) for f in self.reasoning_flows),
            'operation_types': operation_counts,
            'average_flow_length': sum(len(f['operations']) for f in self.reasoning_flows) / max(len(self.reasoning_flows), 1)
        }
