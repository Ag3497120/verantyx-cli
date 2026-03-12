#!/usr/bin/env python3
"""
Reasoning Operator Extractor

Claudeの応答からLayer3（思考操作）を抽出

知識ではなく「思考パターン」を学ぶ
"""

from typing import List, Dict, Any, Optional
import re


class ReasoningOperatorExtractor:
    """
    Claude応答から推論演算子（Reasoning Operators）を抽出

    Layer1（文章） → Layer2（構造） → Layer3（思考操作）

    例:
        Input: "DeepSeekは中国のAI企業が開発したLLMです。GPTと比較すると..."

        Output: [
            {'operator': 'DEFINE', 'entity': 'DeepSeek'},
            {'operator': 'ATTRIBUTE', 'entity': 'DeepSeek', 'attr': 'developer', 'value': '中国のAI企業'},
            {'operator': 'CLASSIFY', 'entity': 'DeepSeek', 'category': 'LLM'},
            {'operator': 'COMPARE', 'A': 'DeepSeek', 'B': 'GPT'}
        ]
    """

    # 推論演算子パターン辞書
    OPERATOR_PATTERNS = {
        'DEFINE': {
            'markers': ['とは', 'は', 'です', 'is', 'means', 'refers to'],
            'description': '定義'
        },
        'COMPARE': {
            'markers': ['比較', '違い', 'compared to', 'vs', 'versus', 'より', 'に対して'],
            'description': '比較'
        },
        'LIST_FEATURES': {
            'markers': ['特徴', '特性', 'features', '主な', 'characteristics', '含む', 'include'],
            'description': '特徴列挙'
        },
        'CLASSIFY': {
            'markers': ['種類', 'タイプ', 'type', 'category', '分類', 'belongs to', '科', '属', '門', '綱', '目', '種'],
            'description': '分類'
        },
        'ATTRIBUTE': {
            'markers': ['持つ', '持っている', 'has', 'with', '備える', '提供', '学名:', '英名:', '原産地:', '旬:', '見た目:', '味:'],
            'description': '属性設定'
        },
        'CAUSE': {
            'markers': ['原因', 'なぜなら', 'because', '理由', 'due to', 'caused by'],
            'description': '因果関係'
        },
        'EXAMPLE': {
            'markers': ['例えば', '例として', 'for example', 'such as', 'like', 'たとえば'],
            'description': '具体例'
        },
        'SEQUENCE': {
            'markers': ['まず', '次に', 'first', 'then', 'next', 'finally', 'ステップ'],
            'description': '手順'
        },
        'EXPLAIN': {
            'markers': ['説明', 'つまり', 'in other words', 'specifically', '具体的には'],
            'description': '説明'
        },
        'ANALYZE': {
            'markers': ['分析', '考えると', 'analyzing', 'breakdown', '見ると'],
            'description': '分析'
        }
    }

    def __init__(self):
        self.extracted_operators = []

    def extract(self, claude_response: str, user_question: str = None) -> List[Dict[str, Any]]:
        """
        Claude応答から推論演算子を抽出

        Args:
            claude_response: Claudeの応答文
            user_question: ユーザーの質問（オプション、文脈理解に使用）

        Returns:
            推論演算子のリスト
        """
        operations = []

        # 文章を文単位に分割
        sentences = self._split_sentences(claude_response)

        # 質問から主エンティティを抽出
        main_entity = self._extract_main_entity(user_question) if user_question else None

        for i, sentence in enumerate(sentences):
            # 各文から操作を検出
            detected_ops = self._detect_operators(sentence)

            for op_type in detected_ops:
                # 操作に応じたパラメータ抽出
                params = self._extract_parameters(sentence, op_type, main_entity)

                if params:  # パラメータが抽出できた場合のみ追加
                    operations.append({
                        'operator': op_type,
                        'sentence': sentence,
                        'sentence_index': i,
                        **params
                    })

        self.extracted_operators = operations
        return operations

    def _split_sentences(self, text: str) -> List[str]:
        """文章を文単位に分割"""
        # 日本語と英語の文末を考慮
        sentences = re.split(r'[。！？\n]|(?<=[.!?])\s+', text)
        # 空文字列を除去
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _detect_operators(self, sentence: str) -> List[str]:
        """文から操作タイプを検出"""
        detected = []

        sentence_lower = sentence.lower()

        for op_type, config in self.OPERATOR_PATTERNS.items():
            for marker in config['markers']:
                if marker.lower() in sentence_lower:
                    detected.append(op_type)
                    break  # 1つの操作タイプにつき1回だけ

        return detected

    def _extract_main_entity(self, question: str) -> Optional[str]:
        """質問から主エンティティを抽出"""
        if not question:
            return None

        # 「〜とは」パターン
        match = re.search(r'(.+?)とは', question)
        if match:
            return match.group(1).strip()

        # 「What is X」パターン
        match = re.search(r'what is (.+?)[?\s]', question.lower())
        if match:
            return match.group(1).strip()

        # 最初の名詞句を抽出（簡易版）
        words = question.split()
        if words:
            return words[0]

        return None

    def _extract_parameters(self, sentence: str, op_type: str, main_entity: Optional[str]) -> Dict[str, Any]:
        """操作タイプに応じてパラメータを抽出"""

        if op_type == 'DEFINE':
            return self._extract_define_params(sentence, main_entity)

        elif op_type == 'COMPARE':
            return self._extract_compare_params(sentence, main_entity)

        elif op_type == 'CLASSIFY':
            return self._extract_classify_params(sentence, main_entity)

        elif op_type == 'ATTRIBUTE':
            return self._extract_attribute_params(sentence, main_entity)

        elif op_type == 'LIST_FEATURES':
            return self._extract_features_params(sentence, main_entity)

        elif op_type == 'EXAMPLE':
            return self._extract_example_params(sentence, main_entity)

        elif op_type == 'SEQUENCE':
            return self._extract_sequence_params(sentence)

        else:
            # その他の操作はテキストのみ保存
            return {'text': sentence}

    def _extract_define_params(self, sentence: str, main_entity: Optional[str]) -> Dict:
        """定義操作のパラメータ抽出"""
        # 「AはBです」パターン
        match = re.search(r'(.+?)は(.+?)(?:です|だ)', sentence)
        if match:
            entity = match.group(1).strip()
            definition = match.group(2).strip()
            return {
                'entity': entity if not main_entity else main_entity,
                'definition': definition
            }

        # "A is B" パターン
        match = re.search(r'(.+?)\s+is\s+(.+)', sentence, re.IGNORECASE)
        if match:
            entity = match.group(1).strip()
            definition = match.group(2).strip()
            return {
                'entity': entity if not main_entity else main_entity,
                'definition': definition
            }

        return {'entity': main_entity, 'definition': sentence}

    def _extract_compare_params(self, sentence: str, main_entity: Optional[str]) -> Dict:
        """比較操作のパラメータ抽出"""
        # 「AとBを比較」「AとBの違い」パターン
        match = re.search(r'(.+?)と(.+?)(?:を比較|の違い|比べ|に対して)', sentence)
        if match:
            return {
                'A': match.group(1).strip(),
                'B': match.group(2).strip(),
                'text': sentence
            }

        # "compared to B" パターン
        match = re.search(r'compared to (.+)', sentence, re.IGNORECASE)
        if match:
            return {
                'A': main_entity,
                'B': match.group(1).strip(),
                'text': sentence
            }

        return {'A': main_entity, 'text': sentence}

    def _extract_classify_params(self, sentence: str, main_entity: Optional[str]) -> Dict:
        """分類操作のパラメータ抽出"""
        # 「AはBの一種」「AはBに分類」パターン
        match = re.search(r'(.+?)は(.+?)(?:の一種|に分類|というタイプ)', sentence)
        if match:
            return {
                'entity': match.group(1).strip(),
                'category': match.group(2).strip()
            }

        # 「AはBです」で名詞が続く場合
        match = re.search(r'(.+?)は[、,]?(.+?)(?:です|だ)', sentence)
        if match:
            entity = match.group(1).strip()
            category = match.group(2).strip()
            # カテゴリっぽい単語か判定（拡張版）
            # 分類キーワード: 科、属、種、類、系、型、LLM、AI、システム、ツール、企業、組織など
            if any(w in category for w in ['科', '属', '種', '類', '系', '型', '門', '綱', '目',
                                            'タイプ', 'type', 'LLM', 'AI', 'システム', 'ツール',
                                            '企業', '組織', '団体', 'family', 'genus', 'species',
                                            '木', '草', '植物', '動物', '生物']):
                return {
                    'entity': entity if not main_entity else main_entity,
                    'category': category
                }

        return {'entity': main_entity, 'category': sentence}

    def _extract_attribute_params(self, sentence: str, main_entity: Optional[str]) -> Dict:
        """属性操作のパラメータ抽出"""
        # 「- 学名: Malus domestica」のようなKey-Valueペアパターン
        match = re.search(r'[-・]\s*(.+?)\s*[:：]\s*(.+)', sentence)
        if match:
            attr_name = match.group(1).strip()
            attr_value = match.group(2).strip()
            return {
                'entity': main_entity,
                'attr': attr_name,
                'value': attr_value
            }

        # 「Aは〜を持つ」「Aには〜がある」パターン
        match = re.search(r'(.+?)(?:は|には)(.+?)(?:を持つ|がある|備える|提供)', sentence)
        if match:
            return {
                'entity': match.group(1).strip() if not main_entity else main_entity,
                'attribute': match.group(2).strip()
            }

        # "has X" パターン
        match = re.search(r'has (.+)', sentence, re.IGNORECASE)
        if match:
            return {
                'entity': main_entity,
                'attribute': match.group(1).strip()
            }

        return {'entity': main_entity, 'attribute': sentence}

    def _extract_features_params(self, sentence: str, main_entity: Optional[str]) -> Dict:
        """特徴列挙のパラメータ抽出"""
        # 箇条書きや列挙を検出
        features = []

        # 「、」や「、」で区切られたリスト
        if '、' in sentence or ',' in sentence:
            parts = re.split(r'[、,]', sentence)
            features = [p.strip() for p in parts if p.strip()]
        else:
            features = [sentence]

        return {
            'entity': main_entity,
            'features': features
        }

    def _extract_example_params(self, sentence: str, main_entity: Optional[str]) -> Dict:
        """具体例のパラメータ抽出"""
        # 「例えば〜」以降を抽出
        match = re.search(r'(?:例えば|for example|such as|like)(.+)', sentence, re.IGNORECASE)
        if match:
            example = match.group(1).strip()
            return {
                'entity': main_entity,
                'example': example
            }

        return {'entity': main_entity, 'example': sentence}

    def _extract_sequence_params(self, sentence: str) -> Dict:
        """手順のパラメータ抽出"""
        # ステップ番号を検出
        match = re.search(r'(?:まず|first|ステップ\s*(\d+)|(\d+)\.)', sentence, re.IGNORECASE)
        if match:
            step_num = match.group(1) or match.group(2)
            return {
                'step': int(step_num) if step_num and step_num.isdigit() else 1,
                'instruction': sentence
            }

        return {'instruction': sentence}

    def get_operator_summary(self) -> Dict[str, int]:
        """抽出された操作の統計"""
        summary = {}
        for op in self.extracted_operators:
            op_type = op['operator']
            summary[op_type] = summary.get(op_type, 0) + 1
        return summary

    def to_readable_format(self) -> str:
        """人間が読みやすい形式で出力"""
        lines = []
        lines.append("=" * 60)
        lines.append("Extracted Reasoning Operators")
        lines.append("=" * 60)

        for i, op in enumerate(self.extracted_operators, 1):
            lines.append(f"\n[{i}] {op['operator']}")
            lines.append(f"    Sentence: {op['sentence'][:80]}...")

            # パラメータを表示
            for key, value in op.items():
                if key not in ['operator', 'sentence', 'sentence_index']:
                    lines.append(f"    {key}: {value}")

        lines.append("\n" + "=" * 60)
        lines.append("Summary")
        lines.append("=" * 60)
        summary = self.get_operator_summary()
        for op_type, count in sorted(summary.items()):
            lines.append(f"{op_type}: {count}")

        return '\n'.join(lines)


# テスト用
if __name__ == '__main__':
    extractor = ReasoningOperatorExtractor()

    # テストケース1: DeepSeekについての説明
    test_response_1 = """
    DeepSeekは中国のAI企業が開発したLLMです。
    GPTやClaudeと比較すると、コスト効率に優れています。
    特に推論タスクにおいて高い性能を発揮します。
    例えば、数学的問題やコーディングタスクで優れた結果を示しています。
    """

    print("Test 1: DeepSeek explanation")
    print("-" * 60)
    ops = extractor.extract(test_response_1, user_question="DeepSeekとは")
    print(extractor.to_readable_format())

    # テストケース2: Pythonについての説明
    test_response_2 = """
    Pythonはプログラミング言語です。
    まず、変数を定義します。
    次に、関数を作成します。
    Pythonは読みやすい文法を持っています。
    """

    print("\n\nTest 2: Python explanation")
    print("-" * 60)
    extractor2 = ReasoningOperatorExtractor()
    ops2 = extractor2.extract(test_response_2, user_question="Pythonとは")
    print(extractor2.to_readable_format())
