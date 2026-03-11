#!/usr/bin/env python3
"""
Standalone AIのテスト - 学習した知識からの応答生成
"""

from pathlib import Path
from verantyx_cli.engine.standalone_ai import VerantyxStandaloneAI


def test_standalone_knowledge():
    """Standaloneモードで学習した知識を使って応答生成"""
    print()
    print("=" * 70)
    print("  🤖 Testing Standalone AI with Learned Knowledge")
    print("=" * 70)
    print()

    # Cross構造ファイル
    cross_file = Path(".verantyx/conversation.cross.json")

    if not cross_file.exists():
        print("❌ Cross structure file not found")
        return

    # StandaloneAIを初期化
    ai = VerantyxStandaloneAI(
        cross_file=cross_file,
        enable_skills=True
    )

    print("✅ Standalone AI initialized")
    print()

    # 学習統計を表示
    print("📊 Learning Statistics:")
    print()

    # スキル統計
    if ai.skill_learner:
        skill_summary = ai.skill_learner.get_skill_summary()
        print(f"  📋 Operational Skills:")
        print(f"     - Tool patterns: {skill_summary['tool_patterns_count']}")
        print(f"     - Workflows: {skill_summary['workflows_count']}")
        print(f"     - Code templates: {skill_summary['code_templates_count']}")
        print(f"     - Error solutions: {skill_summary['error_solutions_count']}")
        print()

    # 知識統計
    if ai.knowledge_learner:
        knowledge_summary = ai.knowledge_learner.get_knowledge_summary()
        print(f"  📚 General Knowledge:")
        print(f"     - Q&A patterns: {knowledge_summary['qa_patterns_count']}")
        print(f"     - Concepts: {knowledge_summary['concepts_count']}")
        print(f"     - Technical knowledge: {knowledge_summary['technical_knowledge_count']}")
        print()
        if knowledge_summary['top_concepts']:
            print(f"     Top concepts:")
            for concept in knowledge_summary['top_concepts'][:5]:
                print(f"       • {concept}")
        print()

    # テスト質問
    test_questions = [
        "claudeとは",
        "chatgptとは",
        "Claudeについて教えて",
        "Constitutional AIって何？",
    ]

    print("=" * 70)
    print("  💬 Testing Question Responses")
    print("=" * 70)
    print()

    for question in test_questions:
        print(f"Q: {question}")
        print()

        response = ai.generate_response(question)

        # 応答を表示（最初の500文字）
        if len(response) > 500:
            print(response[:500] + "...")
        else:
            print(response)

        print()
        print("-" * 70)
        print()

    print("=" * 70)
    print("  ✅ Standalone Knowledge Test Complete!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    test_standalone_knowledge()
