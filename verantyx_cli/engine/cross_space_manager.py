#!/usr/bin/env python3
"""
Cross空間位置管理エンジン

機能:
1. 単語のCross空間上の位置管理
2. 重複単語の統合（情報洗練）
3. 文法層と単語層の分離
4. 位置の動的調整
5. 逆引きクエリサポート
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from datetime import datetime
from collections import defaultdict


class CrossSpaceManager:
    """
    Cross空間での位置ベース学習を管理

    原則:
    - 同じ会話内の単語は近い位置に配置
    - 共起頻度が高い単語は距離が縮まる
    - 重複する情報は統合される
    - 単語層と文法層は分離される
    """

    def __init__(self, space_file: Path):
        """
        Args:
            space_file: Cross空間データベースファイル (.jcross)
        """
        self.space_file = space_file
        self.dimensions = 6  # UP, DOWN, LEFT, RIGHT, FRONT, BACK

        # LAYER 1: 単語層
        self.word_layer = {}  # {word: {position, frequency, contexts, neighbors}}

        # LAYER 2: 文法層
        self.grammar_layer = {}  # {operation: {template, usage_count}}

        # LAYER 3: 関係層
        self.relation_layer = {}  # {word_pair: {distance, relation_type}}

        # LAYER 4: コンテキスト層
        self.context_layer = {}  # {context_id: {center_position, words}}

        # LAYER 5: 統合層
        self.integration_layer = []  # 統合履歴

        # LAYER 6: 推論層（逆引きインデックス）
        self.category_index = defaultdict(set)  # {category: {entities}}
        self.attribute_index = defaultdict(dict)  # {attr: {value: entity}}

        # メタ情報
        self.meta = {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'total_words': 0,
            'total_operations': 0,
            'space_dimensions': self.dimensions
        }

        # ロード
        self._load()

    def _load(self):
        """Cross空間データベースを読み込む"""
        if not self.space_file.exists():
            return

        try:
            # .jcrossファイルから読み込む（簡易パーサー）
            with open(self.space_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # JSONデータを抽出（簡易実装）
            # 実際にはJCrossパーサーを使う
            # ここでは一旦スキップ
            pass
        except Exception as e:
            print(f"⚠️  Failed to load Cross space: {e}")

    def add_word_from_operation(
        self,
        operation: Dict[str, Any],
        context_id: str,
        timestamp: str
    ):
        """
        操作コマンドから単語を抽出してCross空間に追加

        重要: 重複する単語は統合される

        Args:
            operation: 推論操作 {'operator': 'CLASSIFY', 'entity': 'りんご', ...}
            context_id: コンテキストID
            timestamp: タイムスタンプ
        """
        operator = operation.get('operator')

        # LAYER 2: 文法層に操作を記録
        self._record_operation(operator, operation)

        # LAYER 1: 単語層に実体を追加
        if operator == 'CLASSIFY':
            entity = operation.get('entity')
            category = operation.get('category')

            # 実体を追加
            if entity:
                self._add_word(entity, context_id, timestamp)

            # カテゴリを追加
            if category:
                self._add_word(category, context_id, timestamp)

            # LAYER 6: 推論層にインデックス追加
            if entity and category:
                self.category_index[category].add(entity)

                # LAYER 3: 関係層に関係を記録
                self._add_relation(entity, category, 'is_a', context_id)

        elif operator == 'ATTRIBUTE':
            entity = operation.get('entity')
            attr = operation.get('attr')
            value = operation.get('value')

            # 実体を追加
            if entity:
                self._add_word(entity, context_id, timestamp)

            # 属性値を追加
            if value:
                self._add_word(value, context_id, timestamp)

            # LAYER 6: 推論層にインデックス追加
            if entity and attr and value:
                if attr not in self.attribute_index:
                    self.attribute_index[attr] = {}
                self.attribute_index[attr][value] = entity

                # LAYER 3: 関係層に関係を記録
                self._add_relation(entity, value, 'has_attr', context_id)

        elif operator == 'DEFINE':
            entity = operation.get('entity')

            if entity:
                self._add_word(entity, context_id, timestamp)

    def _add_word(self, word: str, context_id: str, timestamp: str):
        """
        単語をCross空間に追加（重複チェック付き）

        統合ロジック:
        1. 完全一致: そのまま頻度を増やす
        2. 表記ゆれ: 統合する（りんご/リンゴ/林檎）
        3. 同義語: 近い位置に配置
        """
        # 正規化
        normalized = self._normalize_word(word)

        # 既存単語との類似度チェック
        canonical = self._find_canonical_form(normalized)

        if canonical:
            # 既存単語が見つかった → 統合
            self._merge_word(canonical, word, context_id, timestamp)
        else:
            # 新規単語 → 追加
            self._create_new_word(normalized, context_id, timestamp)

    def _normalize_word(self, word: str) -> str:
        """単語を正規化"""
        # 前後の空白除去
        word = word.strip()

        # 記号除去（必要に応じて）
        word = re.sub(r'[「」『』（）()]', '', word)

        return word

    def _find_canonical_form(self, word: str) -> Optional[str]:
        """
        既存単語との類似度をチェックして、統合すべき正規形を返す

        統合基準:
        - 完全一致
        - ひらがな/カタカナ変換一致（りんご/リンゴ）
        - 漢字/ひらがな変換一致（林檎/りんご）
        """
        if word in self.word_layer:
            return word

        # ひらがな変換
        hiragana = self._to_hiragana(word)
        if hiragana in self.word_layer:
            return hiragana

        # カタカナ変換
        katakana = self._to_katakana(word)
        if katakana in self.word_layer:
            return katakana

        # 既存単語をひらがな変換して比較
        for existing in self.word_layer.keys():
            if self._to_hiragana(existing) == hiragana:
                return existing

        return None

    def _to_hiragana(self, text: str) -> str:
        """カタカナをひらがなに変換（簡易版）"""
        result = []
        for char in text:
            code = ord(char)
            # カタカナ範囲: 0x30A0-0x30FF
            if 0x30A0 <= code <= 0x30FF:
                result.append(chr(code - 0x60))  # ひらがなに変換
            else:
                result.append(char)
        return ''.join(result)

    def _to_katakana(self, text: str) -> str:
        """ひらがなをカタカナに変換（簡易版）"""
        result = []
        for char in text:
            code = ord(char)
            # ひらがな範囲: 0x3040-0x309F
            if 0x3040 <= code <= 0x309F:
                result.append(chr(code + 0x60))  # カタカナに変換
            else:
                result.append(char)
        return ''.join(result)

    def _merge_word(
        self,
        canonical: str,
        variant: str,
        context_id: str,
        timestamp: str
    ):
        """
        既存単語と統合（情報洗練）

        統合時の処理:
        1. 頻度を増やす
        2. コンテキストを追加
        3. 位置を調整（新しいコンテキストに近づける）
        """
        if canonical not in self.word_layer:
            return

        word_data = self.word_layer[canonical]

        # 頻度を増やす
        word_data['frequency'] += 1

        # コンテキストを追加（重複チェック）
        if context_id not in word_data['contexts']:
            word_data['contexts'].append(context_id)

        # 位置を調整
        if context_id in self.context_layer:
            context_center = self.context_layer[context_id]['center_position']
            self._adjust_position(canonical, context_center)

        # 更新日時
        word_data['last_updated'] = timestamp

        # 統合記録
        if canonical != variant:
            self.integration_layer.append({
                'original': variant,
                'canonical': canonical,
                'reason': '表記ゆれ統合',
                'merged_at': timestamp
            })

    def _create_new_word(self, word: str, context_id: str, timestamp: str):
        """新規単語を作成"""
        # コンテキストの中心位置を取得（または初期位置を生成）
        if context_id in self.context_layer:
            position = self._generate_position_near(
                self.context_layer[context_id]['center_position']
            )
        else:
            # 新規コンテキスト → ランダム位置
            position = self._generate_random_position()

        self.word_layer[word] = {
            'position': position,
            'frequency': 1,
            'contexts': [context_id],
            'neighbors': {},
            'operations': [],
            'first_seen': timestamp,
            'last_updated': timestamp
        }

        self.meta['total_words'] += 1

    def _generate_random_position(self) -> List[float]:
        """ランダムな6次元位置を生成"""
        import random
        return [random.random() for _ in range(self.dimensions)]

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

    def _adjust_position(
        self,
        word: str,
        target_position: List[float],
        learning_rate: float = 0.1
    ):
        """
        単語の位置を目標位置に近づける

        学習率: 0.1 = 10%ずつ移動
        """
        if word not in self.word_layer:
            return

        current = self.word_layer[word]['position']

        # 各次元で目標に近づく
        new_position = [
            current[i] + learning_rate * (target_position[i] - current[i])
            for i in range(self.dimensions)
        ]

        self.word_layer[word]['position'] = new_position

    def _record_operation(self, operator: str, operation: Dict):
        """文法層に操作を記録"""
        if operator not in self.grammar_layer:
            self.grammar_layer[operator] = {
                'template': self._infer_template(operator, operation),
                'usage_count': 0,
                'parameters': list(operation.keys()),
                'examples': []
            }

        self.grammar_layer[operator]['usage_count'] += 1
        self.grammar_layer[operator]['examples'].append(operation)

        # 例は最大10件まで保存
        if len(self.grammar_layer[operator]['examples']) > 10:
            self.grammar_layer[operator]['examples'].pop(0)

    def _infer_template(self, operator: str, operation: Dict) -> str:
        """操作からテンプレートを推測"""
        if operator == 'CLASSIFY':
            return "分類設定 実体={entity} カテゴリ={category}"
        elif operator == 'ATTRIBUTE':
            return "属性設定 実体={entity} 属性={attr} 値={value}"
        elif operator == 'DEFINE':
            return "概念定義 実体={entity} 値={definition}"
        elif operator == 'COMPARE':
            return "比較実行 対象A={A} 対象B={B}"
        else:
            return f"{operator} " + " ".join([f"{k}={{{k}}}" for k in operation.keys()])

    def _add_relation(
        self,
        word1: str,
        word2: str,
        relation_type: str,
        context_id: str
    ):
        """関係層に単語間の関係を記録"""
        # 正規化
        word1 = self._normalize_word(word1)
        word2 = self._normalize_word(word2)

        # ペアキー（順序を固定）
        pair_key = f"{min(word1, word2)}<->{max(word1, word2)}"

        if pair_key not in self.relation_layer:
            # 距離を計算
            distance = self._calculate_distance(word1, word2)

            self.relation_layer[pair_key] = {
                'distance': distance,
                'relation_type': relation_type,
                'confidence': 0.8,
                'co_occurrence': 1,
                'contexts': [context_id]
            }
        else:
            # 共起回数を増やす
            self.relation_layer[pair_key]['co_occurrence'] += 1

            # 距離を更新（近づける）
            current_distance = self.relation_layer[pair_key]['distance']
            self.relation_layer[pair_key]['distance'] = current_distance * 0.9

            # コンテキスト追加
            if context_id not in self.relation_layer[pair_key]['contexts']:
                self.relation_layer[pair_key]['contexts'].append(context_id)

    def _calculate_distance(self, word1: str, word2: str) -> float:
        """2つの単語間の距離を計算"""
        # 正規化
        word1 = self._find_canonical_form(word1) or word1
        word2 = self._find_canonical_form(word2) or word2

        if word1 not in self.word_layer or word2 not in self.word_layer:
            return 1.0  # デフォルト距離

        pos1 = self.word_layer[word1]['position']
        pos2 = self.word_layer[word2]['position']

        # ユークリッド距離
        return math.sqrt(sum((p1 - p2) ** 2 for p1, p2 in zip(pos1, pos2)))

    def create_context(
        self,
        context_id: str,
        topic: str,
        initial_words: List[str]
    ):
        """
        新しいコンテキスト（会話）を作成

        同じ会話内の単語は近い位置に配置される
        """
        # 中心位置を生成
        center_position = self._generate_random_position()

        self.context_layer[context_id] = {
            'center_position': center_position,
            'words': initial_words,
            'topic': topic,
            'radius': 0.3,
            'created_at': datetime.now().isoformat()
        }

    def query_by_category(self, category: str) -> Set[str]:
        """
        カテゴリから実体を逆引き

        例: "バラ科" → {"りんご", "さくら", "いちご"}
        """
        # 正規化
        category = self._normalize_word(category)

        # 完全一致
        if category in self.category_index:
            return self.category_index[category]

        # 部分一致（"バラ科*"など）
        results = set()
        for cat, entities in self.category_index.items():
            if category in cat or cat in category:
                results.update(entities)

        return results

    def query_by_attribute(self, attr: str, value: str) -> Optional[str]:
        """
        属性値から実体を逆引き

        例: attr="学名", value="Malus domestica" → "りんご"
        """
        attr = self._normalize_word(attr)
        value = self._normalize_word(value)

        if attr in self.attribute_index:
            return self.attribute_index[attr].get(value)

        return None

    def get_neighbors(self, word: str, max_distance: float = 0.5) -> List[Tuple[str, float]]:
        """
        単語の近傍を取得

        Returns:
            [(word, distance), ...] 距離が近い順
        """
        word = self._normalize_word(word)
        canonical = self._find_canonical_form(word) or word

        if canonical not in self.word_layer:
            return []

        neighbors = []
        for other_word in self.word_layer.keys():
            if other_word == canonical:
                continue

            distance = self._calculate_distance(canonical, other_word)
            if distance <= max_distance:
                neighbors.append((other_word, distance))

        # 距離でソート
        neighbors.sort(key=lambda x: x[1])

        return neighbors

    def save(self):
        """Cross空間を.jcross形式で保存"""
        output = self._generate_jcross_output()

        with open(self.space_file, 'w', encoding='utf-8') as f:
            f.write(output)

    def _generate_jcross_output(self) -> str:
        """Cross空間データを.jcross形式で出力"""
        lines = []

        lines.append('"""')
        lines.append('Cross空間位置データベース - 動的生成')
        lines.append('')
        lines.append(f'生成日時: {datetime.now().isoformat()}')
        lines.append(f'総単語数: {self.meta["total_words"]}')
        lines.append(f'総操作数: {self.meta["total_operations"]}')
        lines.append('"""')
        lines.append('')
        lines.append('CROSS cross_space_db {')
        lines.append('')

        # LAYER 1: 単語層
        lines.append('    // LAYER 1: 単語層')
        lines.append('    AXIS WORD_LAYER {')
        lines.append('        words: {')
        for word, data in self.word_layer.items():
            lines.append(f'            "{word}": {{')
            lines.append(f'                position: {data["position"]},')
            lines.append(f'                frequency: {data["frequency"]},')
            lines.append(f'                contexts: {data["contexts"]},')
            lines.append(f'                neighbors: {dict(list(data.get("neighbors", {}).items())[:5])},')
            lines.append(f'                first_seen: "{data["first_seen"]}",')
            lines.append(f'                last_updated: "{data["last_updated"]}"')
            lines.append('            },')
        lines.append('        }')
        lines.append('    }')
        lines.append('')

        # LAYER 2: 文法層
        lines.append('    // LAYER 2: 文法層')
        lines.append('    AXIS GRAMMAR_LAYER {')
        lines.append('        operations: {')
        for op, data in self.grammar_layer.items():
            lines.append(f'            "{op}": {{')
            lines.append(f'                template: "{data["template"]}",')
            lines.append(f'                usage_count: {data["usage_count"]}')
            lines.append('            },')
        lines.append('        }')
        lines.append('    }')
        lines.append('')

        # LAYER 6: 推論層
        lines.append('    // LAYER 6: 推論層（逆引きインデックス）')
        lines.append('    AXIS INFERENCE_LAYER {')
        lines.append('        category_index: {')
        for category, entities in self.category_index.items():
            lines.append(f'            "{category}": {sorted(list(entities))},')
        lines.append('        },')
        lines.append('        attribute_index: {')
        for attr, value_map in self.attribute_index.items():
            lines.append(f'            "{attr}": {{')
            for value, entity in value_map.items():
                lines.append(f'                "{value}": "{entity}",')
            lines.append('            },')
        lines.append('        }')
        lines.append('    }')
        lines.append('')

        lines.append('}')

        return '\n'.join(lines)

    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'total_words': len(self.word_layer),
            'total_operations': len(self.grammar_layer),
            'total_contexts': len(self.context_layer),
            'total_relations': len(self.relation_layer),
            'total_integrations': len(self.integration_layer),
            'category_count': len(self.category_index),
            'attribute_count': len(self.attribute_index)
        }
