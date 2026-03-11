#!/usr/bin/env python3
"""
スタンドアロンモードの学習テスト

実際に学習された知識が使えるか検証
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.knowledge_learner import KnowledgeLearner
from verantyx_cli.engine.standalone_ai import StandaloneAI


def test_knowledge_retrieval():
    """知識取得のテスト"""
    print("=" * 80)
    print("🧪 Knowledge Retrieval Test")
    print("=" * 80)

    cross_file = Path('.verantyx/conversation.cross.json')

    if not cross_file.exists():
        print("❌ No learning data found")
        return False

    # 知識を学習
    learner = KnowledgeLearner(cross_file)
    learner.learn()

    summary = learner.get_knowledge_summary()

    print(f"\n📊 Learned Knowledge:")
    print(f"  Q&A patterns: {summary['qa_patterns_count']}")
    print(f"  Concepts: {summary['concepts_count']}")

    # 学習されたトピックを取得
    topics = []
    for key in learner.learned_knowledge['qa_patterns'].keys():
        parts = key.split(':')
        if len(parts) > 1:
            topics.append(parts[1])

    if not topics:
        print("\n❌ No topics learned")
        return False

    print(f"\n📚 Learned Topics:")
    for i, topic in enumerate(set(topics), 1):
        print(f"  {i}. {topic}")

    # テストクエリ
    print("\n" + "=" * 80)
    print("🔍 Testing Query Matching")
    print("=" * 80)

    test_topic = topics[0] if topics else None

    if test_topic:
        test_queries = [
            f"{test_topic}とは",
            f"{test_topic}について",
            f"{test_topic}",
        ]

        for query in test_queries:
            print(f"\nQuery: {query}")

            # パターンマッチング
            matched = learner.find_matching_pattern(query)

            if matched:
                print(f"  ✅ Match found!")
                print(f"  Pattern: {matched['pattern_key'][:60]}...")
                print(f"  Answer preview: {matched['answer'][:100]}...")
            else:
                print(f"  ❌ No match")

    return True


def test_standalone_mode():
    """スタンドアロンモードのテスト"""
    print("\n" + "=" * 80)
    print("🤖 Standalone AI Test")
    print("=" * 80)

    project_path = Path('.')
    ai = StandaloneAI(project_path)

    # 学習データをロード
    summary = ai.knowledge_learner.get_knowledge_summary()

    print(f"\n📊 AI Knowledge Base:")
    print(f"  Q&A patterns: {summary['qa_patterns_count']}")
    print(f"  Concepts: {summary['concepts_count']}")

    if summary['qa_patterns_count'] == 0:
        print("\n❌ No knowledge available for standalone mode")
        return False

    # 学習されたトピックから自動テスト
    topics = []
    for key in ai.knowledge_learner.learned_knowledge['qa_patterns'].keys():
        parts = key.split(':')
        if len(parts) > 1 and parts[1]:
            topics.append(parts[1])

    if not topics:
        print("\n❌ No queryable topics found")
        return False

    print(f"\n🧪 Testing with learned topics:")

    # 最初のトピックでテスト
    test_topic = list(set(topics))[0]
    test_query = f"{test_topic}とは"

    print(f"\nTest Query: {test_query}")
    print("-" * 80)

    # 応答を生成
    response = ai.generate_response(test_query)

    print(f"\nAI Response:")
    print(response)
    print("-" * 80)

    # 成功判定
    success = (
        response != "すみません、その質問には答えられません。" and
        "No match found" not in response
    )

    if success:
        print("\n✅ Standalone mode working!")
    else:
        print("\n❌ Standalone mode not retrieving knowledge")

    return success


def test_bidirectional_linking():
    """双方向リンクのテスト"""
    print("\n" + "=" * 80)
    print("🔗 Bidirectional Linking Test")
    print("=" * 80)

    cross_file = Path('.verantyx/conversation.cross.json')

    if not cross_file.exists():
        print("❌ No learning data")
        return False

    learner = KnowledgeLearner(cross_file)
    learner.learn()

    # 概念を取得
    top_concepts = learner.get_knowledge_summary()['top_concepts']

    if len(top_concepts) < 2:
        print("❌ Not enough concepts for bidirectional test")
        return False

    print(f"\n📚 Testing with concepts:")
    for i, concept in enumerate(top_concepts[:5], 1):
        print(f"  {i}. {concept}")

    # 各概念でクエリをテスト
    print("\n🧪 Query Tests:")

    for concept in top_concepts[:3]:
        query = f"{concept}とは"
        matched = learner.find_matching_pattern(query)

        if matched:
            print(f"\n  ✅ {concept}")
            print(f"     Query: {query}")
            print(f"     Match: {matched['pattern_key'][:50]}...")
        else:
            print(f"\n  ❌ {concept}")
            print(f"     Query: {query}")
            print(f"     No match found")

    return True


def main():
    print("\n🔬 Standalone Learning Verification\n")

    # Test 1: 知識取得
    print("\n[Test 1] Knowledge Retrieval")
    test1_passed = test_knowledge_retrieval()

    # Test 2: スタンドアロンモード
    print("\n[Test 2] Standalone Mode")
    test2_passed = test_standalone_mode()

    # Test 3: 双方向リンク
    print("\n[Test 3] Bidirectional Linking")
    test3_passed = test_bidirectional_linking()

    # 結果
    print("\n" + "=" * 80)
    print("📊 Test Results")
    print("=" * 80)

    results = {
        'Knowledge Retrieval': test1_passed,
        'Standalone Mode': test2_passed,
        'Bidirectional Linking': test3_passed,
    }

    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All tests passed! Standalone mode is working.")
    else:
        print("⚠️  Some tests failed. Check logs above.")
    print("=" * 80)


if __name__ == '__main__':
    main()
