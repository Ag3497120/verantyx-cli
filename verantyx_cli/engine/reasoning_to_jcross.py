#!/usr/bin/env python3
"""
Reasoning-to-JCross Converter

推論演算子 → JCrossプログラム変換

文章 → 推論プログラム
"""

from typing import List, Dict, Any, Optional


class ReasoningToJCrossConverter:
    """
    推論演算子をJCrossプログラムに変換

    Input:
        [
            {'operator': 'DEFINE', 'entity': 'DeepSeek', 'definition': 'LLM'},
            {'operator': 'ATTRIBUTE', 'entity': 'DeepSeek', 'attribute': 'コスト効率'},
            {'operator': 'COMPARE', 'A': 'DeepSeek', 'B': 'GPT'}
        ]

    Output (JCross):
        概念定義 実体=DeepSeek 値=LLM
        属性設定 実体=DeepSeek 属性=コスト効率
        比較実行 対象A=DeepSeek 対象B=GPT
    """

    def __init__(self):
        # JCross命令マッピング
        self.jcross_commands = {
            'DEFINE': self._define_to_jcross,
            'COMPARE': self._compare_to_jcross,
            'CLASSIFY': self._classify_to_jcross,
            'ATTRIBUTE': self._attribute_to_jcross,
            'LIST_FEATURES': self._features_to_jcross,
            'EXAMPLE': self._example_to_jcross,
            'SEQUENCE': self._sequence_to_jcross,
            'EXPLAIN': self._explain_to_jcross,
            'ANALYZE': self._analyze_to_jcross,
            'CAUSE': self._cause_to_jcross,
        }

    def convert(self, operations: List[Dict[str, Any]], context: Optional[Dict] = None) -> str:
        """
        推論演算子列をJCrossコードに変換

        Args:
            operations: 推論演算子のリスト
            context: 追加コンテキスト（質問、トピックなど）

        Returns:
            JCrossプログラム文字列
        """
        jcross_lines = []

        # ヘッダー（コンテキスト情報）
        if context:
            jcross_lines.append(f"# Context: {context.get('topic', 'unknown')}")
            jcross_lines.append(f"# Question: {context.get('question', 'unknown')}")
            jcross_lines.append("")

        # 推論操作を順次変換
        for i, op in enumerate(operations):
            jcross_cmd = self._convert_single_operation(op)

            if jcross_cmd:
                # コメント付きで追加
                jcross_lines.append(f"# Operation {i+1}: {op['operator']}")
                jcross_lines.append(jcross_cmd)
                jcross_lines.append("")

        return '\n'.join(jcross_lines)

    def _convert_single_operation(self, op: Dict[str, Any]) -> Optional[str]:
        """個別の推論操作をJCrossコマンドに変換"""
        op_type = op['operator']

        converter_func = self.jcross_commands.get(op_type)

        if converter_func:
            return converter_func(op)

        # 未定義の操作はコメントとして保存
        return f"# Unknown operation: {op_type}"

    def _define_to_jcross(self, op: Dict) -> str:
        """
        DEFINE → 概念定義

        例:
            {'operator': 'DEFINE', 'entity': 'DeepSeek', 'definition': 'LLM'}
            → 概念定義 実体=DeepSeek 値=LLM
        """
        entity = op.get('entity', 'unknown')
        definition = op.get('definition', '')

        # 定義を簡潔化（最初の主要部分のみ）
        if definition:
            # 句読点で区切って最初の部分を取得
            definition_short = definition.split('。')[0].split(',')[0].strip()
        else:
            definition_short = 'unknown'

        return f"概念定義 実体={self._sanitize(entity)} 値={self._sanitize(definition_short)}"

    def _classify_to_jcross(self, op: Dict) -> str:
        """
        CLASSIFY → 分類設定

        例:
            {'operator': 'CLASSIFY', 'entity': 'りんご', 'category': 'バラ科リンゴ属'}
            → 分類設定 実体=りんご カテゴリ=バラ科 + 分類設定 実体=りんご カテゴリ=リンゴ属
        """
        entity = op.get('entity', 'unknown')
        category = op.get('category', 'unknown')

        # 生物分類の場合、科と属を分離
        # 「バラ科リンゴ属」→「バラ科」「リンゴ属」
        import re
        taxonomic_match = re.search(r'(.+科)(.+属)', category)
        if taxonomic_match:
            family = taxonomic_match.group(1)  # バラ科
            genus = taxonomic_match.group(2)   # リンゴ属
            # 2つの分類設定を生成
            result = f"分類設定 実体={self._sanitize(entity)} カテゴリ={self._sanitize(family)}\n"
            result += f"# Operation (sub): CLASSIFY\n"
            result += f"分類設定 実体={self._sanitize(entity)} カテゴリ={self._sanitize(genus)}"
            return result

        return f"分類設定 実体={self._sanitize(entity)} カテゴリ={self._sanitize(category)}"

    def _attribute_to_jcross(self, op: Dict) -> str:
        """
        ATTRIBUTE → 属性設定

        例:
            {'operator': 'ATTRIBUTE', 'entity': 'りんご', 'attr': '学名', 'value': 'Malus domestica'}
            → 属性設定 実体=りんご 属性=学名 値=Malus_domestica
        """
        entity = op.get('entity', 'unknown')

        # 新形式（attr + value）を優先
        if 'attr' in op and 'value' in op:
            attr = op.get('attr', 'unknown')
            value = op.get('value', 'unknown')
            return f"属性設定 実体={self._sanitize(entity)} 属性={self._sanitize(attr)} 値={self._sanitize(value)}"

        # 旧形式（attribute）にフォールバック
        attribute = op.get('attribute', 'unknown')
        # 属性を簡潔化
        attribute_short = attribute.split('。')[0].split(',')[0].strip()
        return f"属性設定 実体={self._sanitize(entity)} 属性={self._sanitize(attribute_short)}"

    def _compare_to_jcross(self, op: Dict) -> str:
        """
        COMPARE → 比較実行

        例:
            {'operator': 'COMPARE', 'A': 'DeepSeek', 'B': 'GPT', 'text': '...'}
            → 比較実行 対象A=DeepSeek 対象B=GPT 軸=general
        """
        A = op.get('A', 'unknown')
        B = op.get('B', 'unknown')
        text = op.get('text', '')

        # 比較軸を抽出（簡易版）
        axis = 'general'
        if 'コスト' in text or 'cost' in text.lower():
            axis = 'cost'
        elif '性能' in text or 'performance' in text.lower():
            axis = 'performance'
        elif '速度' in text or 'speed' in text.lower():
            axis = 'speed'

        return f"比較実行 対象A={self._sanitize(A)} 対象B={self._sanitize(B)} 軸={axis}"

    def _features_to_jcross(self, op: Dict) -> str:
        """
        LIST_FEATURES → 特徴列挙

        例:
            {'operator': 'LIST_FEATURES', 'entity': 'DeepSeek', 'features': ['高性能', 'コスト効率']}
            → 特徴列挙 実体=DeepSeek 特徴=高性能,コスト効率
        """
        entity = op.get('entity', 'unknown')
        features = op.get('features', [])

        if isinstance(features, list):
            features_str = ','.join([self._sanitize(f) for f in features[:3]])  # 最大3つ
        else:
            features_str = self._sanitize(str(features))

        return f"特徴列挙 実体={self._sanitize(entity)} 特徴={features_str}"

    def _example_to_jcross(self, op: Dict) -> str:
        """
        EXAMPLE → 具体例追加

        例:
            {'operator': 'EXAMPLE', 'entity': 'DeepSeek', 'example': '数学的問題'}
            → 具体例追加 実体=DeepSeek 例=数学的問題
        """
        entity = op.get('entity', 'unknown')
        example = op.get('example', 'unknown')

        return f"具体例追加 実体={self._sanitize(entity)} 例={self._sanitize(example)}"

    def _sequence_to_jcross(self, op: Dict) -> str:
        """
        SEQUENCE → 手順追加

        例:
            {'operator': 'SEQUENCE', 'step': 1, 'instruction': '変数を定義'}
            → 手順追加 ステップ=1 内容=変数を定義
        """
        step = op.get('step', 0)
        instruction = op.get('instruction', 'unknown')

        return f"手順追加 ステップ={step} 内容={self._sanitize(instruction)}"

    def _explain_to_jcross(self, op: Dict) -> str:
        """
        EXPLAIN → 説明追加

        例:
            {'operator': 'EXPLAIN', 'text': 'つまり、高性能である'}
            → 説明追加 内容=つまり、高性能である
        """
        text = op.get('text', 'unknown')

        return f"説明追加 内容={self._sanitize(text)}"

    def _analyze_to_jcross(self, op: Dict) -> str:
        """
        ANALYZE → 分析実行

        例:
            {'operator': 'ANALYZE', 'text': 'パフォーマンスを分析すると...'}
            → 分析実行 内容=パフォーマンスを分析すると...
        """
        text = op.get('text', 'unknown')

        return f"分析実行 内容={self._sanitize(text)}"

    def _cause_to_jcross(self, op: Dict) -> str:
        """
        CAUSE → 因果関係設定

        例:
            {'operator': 'CAUSE', 'text': '高性能なのはアーキテクチャが優れているため'}
            → 因果関係設定 内容=高性能なのはアーキテクチャが優れているため
        """
        text = op.get('text', 'unknown')

        return f"因果関係設定 内容={self._sanitize(text)}"

    def _sanitize(self, text: str) -> str:
        """
        JCross用にテキストをサニタイズ

        - 改行を削除
        - 余分な空白を削除
        - 特殊文字をエスケープ
        """
        if not text:
            return 'unknown'

        # 文字列に変換
        text = str(text)

        # 改行を削除
        text = text.replace('\n', ' ').replace('\r', '')

        # 連続する空白を1つに
        text = ' '.join(text.split())

        # 長すぎる場合は切り詰め
        if len(text) > 100:
            text = text[:97] + '...'

        return text

    def generate_concept_abstraction(self, operations: List[Dict[str, Any]]) -> str:
        """
        操作列から抽象的な推論パターンを生成

        例:
            DEFINE → ATTRIBUTE → COMPARE
            → パターン: "定義+属性付与+比較"

        これをConcept Engineが学習
        """
        pattern_sequence = [op['operator'] for op in operations]
        pattern_str = ' → '.join(pattern_sequence)

        jcross_lines = [
            "# Abstracted Reasoning Pattern",
            f"推論パターン パターン={'+'.join(pattern_sequence)}",
            f"# Sequence: {pattern_str}",
            ""
        ]

        return '\n'.join(jcross_lines)


# テスト用
if __name__ == '__main__':
    from reasoning_operator_extractor import ReasoningOperatorExtractor

    # テスト: DeepSeekについての説明
    test_response = """
    DeepSeekは中国のAI企業が開発したLLMです。
    GPTやClaudeと比較すると、コスト効率に優れています。
    特に推論タスクにおいて高い性能を発揮します。
    """

    # Step 1: 推論演算子を抽出
    extractor = ReasoningOperatorExtractor()
    operations = extractor.extract(test_response, user_question="DeepSeekとは")

    print("=" * 60)
    print("Extracted Reasoning Operators")
    print("=" * 60)
    for op in operations:
        print(f"{op['operator']}: {op}")
    print()

    # Step 2: JCrossプログラムに変換
    converter = ReasoningToJCrossConverter()
    jcross_program = converter.convert(
        operations,
        context={'topic': 'DeepSeek', 'question': 'DeepSeekとは'}
    )

    print("=" * 60)
    print("Generated JCross Program")
    print("=" * 60)
    print(jcross_program)
    print()

    # Step 3: 抽象パターン生成
    abstract_pattern = converter.generate_concept_abstraction(operations)
    print("=" * 60)
    print("Abstracted Reasoning Pattern")
    print("=" * 60)
    print(abstract_pattern)
