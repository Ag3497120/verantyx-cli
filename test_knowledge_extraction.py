#!/usr/bin/env python3
"""
Knowledge Learnerのテスト - JCross記録からの知識抽出
"""

from pathlib import Path
from verantyx_cli.engine.knowledge_learner import KnowledgeLearner


def test_knowledge_extraction():
    """JCrossで記録されたCross構造から知識を抽出"""
    print()
    print("=" * 70)
    print("  🧠 Testing Knowledge Extraction from JCross-Logged Data")
    print("=" * 70)
    print()

    # テストファイルを使用
    test_file = Path(".verantyx/test_conversation.cross.json")

    if not test_file.exists():
        print("❌ Test file not found. Run test_jcross_logging.py first.")
        return

    print(f"📂 Loading Cross structure from: {test_file}")
    print()

    # KnowledgeLearnerを初期化
    learner = KnowledgeLearner(test_file)
    print("✅ Initialized KnowledgeLearner")
    print()

    # 知識サマリーを取得
    summary = learner.get_knowledge_summary()

    print("📊 Knowledge Summary:")
    print(f"   - Q&A patterns: {summary['qa_patterns_count']}")
    print(f"   - Concepts: {summary['concepts_count']}")
    print(f"   - Technical knowledge: {summary['technical_knowledge_count']}")
    print(f"   - Reasoning patterns: {summary['reasoning_patterns_count']}")
    print(f"   - Advice patterns: {summary['advice_patterns_count']}")
    print()

    # Q&Aパターンの詳細
    if summary['qa_patterns_count'] > 0:
        print("🔍 Q&A Patterns by Type:")
        if 'qa_by_type' in summary:
            for qa_type, count in summary['qa_by_type'].items():
                print(f"   - {qa_type}: {count}")
        else:
            print(f"   Total: {summary['qa_patterns_count']}")
        print()

    # コンセプトの詳細
    if summary['concepts_count'] > 0:
        print("📚 Top Concepts:")
        for concept in summary['top_concepts'][:5]:
            print(f"   • {concept}")
        print()

    # 実際のQ&A検索をテスト
    print("=" * 70)
    print("  🔎 Testing Q&A Pattern Matching")
    print("=" * 70)
    print()

    test_questions = [
        "claudeとは",
        "chatgptとは",
        "Claudeって何？",
        "ChatGPTについて教えて",
    ]

    for question in test_questions:
        print(f"Q: {question}")
        answer = learner.find_similar_qa(question)
        if answer:
            preview = answer[:150].replace('\n', ' ')
            print(f"✅ Found: {preview}...")
        else:
            print("❌ No matching Q&A found")
        print()

    # コンセプト検索をテスト
    print("=" * 70)
    print("  📖 Testing Concept Lookup")
    print("=" * 70)
    print()

    test_concepts = [
        "claude",
        "chatgpt",
        "constitutional ai",
        "gpt-4"
    ]

    for concept in test_concepts:
        print(f"Concept: {concept}")
        explanation = learner.get_concept_explanation(concept)
        if explanation:
            preview = explanation[:100].replace('\n', ' ')
            print(f"  ✅ {preview}...")
        else:
            print("  ❌ No explanation found")
        print()

    print("=" * 70)
    print("  ✅ Knowledge Extraction Test Complete!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    test_knowledge_extraction()
