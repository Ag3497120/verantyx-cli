#!/usr/bin/env python3
"""
推論抽出パイプラインのテスト

文章 → 推論プログラム変換の検証
"""

import sys
from pathlib import Path

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.reasoning_operator_extractor import ReasoningOperatorExtractor
from verantyx_cli.engine.reasoning_to_jcross import ReasoningToJCrossConverter


def test_deepseek_example():
    """DeepSeekの例でテスト"""
    print("=" * 80)
    print("Test 1: DeepSeek Explanation")
    print("=" * 80)

    user_question = "DeepSeekとは"
    claude_response = """
DeepSeekは中国のAI企業が開発した大規模言語モデル（LLM）です。
GPTやClaudeと比較すると、コスト効率に優れており、特に推論タスクにおいて高い性能を発揮します。
主な特徴として、オープンソースであること、高速な推論速度、そして低い運用コストが挙げられます。
例えば、数学的問題やコーディングタスクで優れた結果を示しています。
    """

    # Step 1: 推論演算子を抽出
    extractor = ReasoningOperatorExtractor()
    operations = extractor.extract(claude_response, user_question)

    print("\n[Step 1] Extracted Reasoning Operators:")
    print("-" * 80)
    for i, op in enumerate(operations, 1):
        print(f"{i}. {op['operator']}")
        for key, value in op.items():
            if key not in ['operator', 'sentence', 'sentence_index']:
                print(f"   {key}: {value}")
        print()

    print(f"\nTotal operators extracted: {len(operations)}")
    print("\nOperator summary:")
    for op_type, count in extractor.get_operator_summary().items():
        print(f"  {op_type}: {count}")

    # Step 2: JCrossプログラムに変換
    converter = ReasoningToJCrossConverter()
    jcross_program = converter.convert(
        operations,
        context={'topic': 'DeepSeek', 'question': user_question}
    )

    print("\n[Step 2] Generated JCross Program:")
    print("-" * 80)
    print(jcross_program)

    # Step 3: 抽象的推論パターンを生成
    abstract_pattern = converter.generate_concept_abstraction(operations)

    print("\n[Step 3] Abstracted Reasoning Pattern:")
    print("-" * 80)
    print(abstract_pattern)

    return operations, jcross_program, abstract_pattern


def test_python_example():
    """Pythonの例でテスト"""
    print("\n\n" + "=" * 80)
    print("Test 2: Python Programming Language")
    print("=" * 80)

    user_question = "Pythonとは"
    claude_response = """
Pythonはプログラミング言語です。
読みやすい文法を持ち、初心者にも学びやすいという特徴があります。
まず、変数を定義します。
次に、関数を作成します。
最後に、プログラムを実行します。
PythonはJavaやC++と比較して、簡潔なコードで記述できます。
例えば、データ分析や機械学習、Web開発などに広く使われています。
    """

    extractor = ReasoningOperatorExtractor()
    operations = extractor.extract(claude_response, user_question)

    print("\n[Step 1] Extracted Reasoning Operators:")
    print("-" * 80)
    print(f"Total: {len(operations)} operators")
    for op_type, count in extractor.get_operator_summary().items():
        print(f"  {op_type}: {count}")

    converter = ReasoningToJCrossConverter()
    jcross_program = converter.convert(
        operations,
        context={'topic': 'Python', 'question': user_question}
    )

    print("\n[Step 2] Generated JCross Program:")
    print("-" * 80)
    print(jcross_program)

    abstract_pattern = converter.generate_concept_abstraction(operations)

    print("\n[Step 3] Abstracted Reasoning Pattern:")
    print("-" * 80)
    print(abstract_pattern)

    return operations, jcross_program, abstract_pattern


def test_comparison():
    """比較の例でテスト"""
    print("\n\n" + "=" * 80)
    print("Test 3: Comparison (DeepSeek vs GPT)")
    print("=" * 80)

    user_question = "DeepSeekとGPTの違いは"
    claude_response = """
DeepSeekとGPTの主な違いは、コストと性能のトレードオフです。
DeepSeekはコスト効率に優れており、GPTと比較して低価格で運用できます。
一方、GPTは汎用性が高く、幅広いタスクに対応しています。
推論速度ではDeepSeekが優れていますが、創造的なタスクではGPTが強みを持ちます。
    """

    extractor = ReasoningOperatorExtractor()
    operations = extractor.extract(claude_response, user_question)

    print("\n[Step 1] Extracted Reasoning Operators:")
    print("-" * 80)
    print(f"Total: {len(operations)} operators")
    for op_type, count in extractor.get_operator_summary().items():
        print(f"  {op_type}: {count}")

    converter = ReasoningToJCrossConverter()
    jcross_program = converter.convert(
        operations,
        context={'topic': 'DeepSeek vs GPT', 'question': user_question}
    )

    print("\n[Step 2] Generated JCross Program:")
    print("-" * 80)
    print(jcross_program)

    return operations, jcross_program


def main():
    print("\n🧠 Reasoning Extraction Pipeline Test\n")
    print("This test demonstrates:")
    print("  1. Extracting reasoning operators from Claude responses")
    print("  2. Converting operators to JCross programs")
    print("  3. Generating abstracted reasoning patterns")
    print("\n" + "=" * 80 + "\n")

    # Test 1: DeepSeek
    test_deepseek_example()

    # Test 2: Python
    test_python_example()

    # Test 3: Comparison
    test_comparison()

    print("\n\n" + "=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)
    print("\nKey Insight:")
    print("  従来: conversation → keywords (単語リスト)")
    print("  新方式: conversation → .jcross programs (推論プログラム)")
    print("\nこれにより、知識ではなく「思考パターン」を学習できます。")


if __name__ == '__main__':
    main()
