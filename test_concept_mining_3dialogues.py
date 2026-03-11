#!/usr/bin/env python3
"""
Concept Mining Test - 3 dialogues
Verifies new concept creation + strengthening
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.concept_mining_complete import RealConceptMiner


def test_multiple_concepts():
    """Test multiple concept extraction"""
    print("=" * 80)
    print("Concept Mining Test - 3 Dialogues")
    print("=" * 80)
    print()

    miner = RealConceptMiner()

    # 3 test dialogues
    dialogues = [
        {
            "user": "docker build でエラーが出ました",
            "claude": "Dockerfileを確認してください。まず、COPY命令のパスが正しいかチェックしましょう。次に、ベースイメージが存在するか確認します。最後に、docker buildを再実行してください。"
        },
        {
            "user": "git merge でコンフリクトが発生しました",
            "claude": "git statusでコンフリクトファイルを確認してください。該当ファイルを編集してマーカーを解決します。その後、git add して git commit してください。"
        },
        {
            "user": "また docker build がエラーになりました",
            "claude": "Dockerfileをチェックしてください。イメージ名が正しいか確認します。修正したら docker build を実行します。"
        }
    ]

    concepts_created = 0
    concepts_strengthened = 0

    for i, dialogue in enumerate(dialogues, 1):
        print(f"--- Dialogue {i} ---")
        print(f"User: {dialogue['user']}")
        print()

        concept, is_new = miner.mine(dialogue['user'], dialogue['claude'])

        if is_new:
            concepts_created += 1
            print(f"✅ New concept: {concept['name']}")
        else:
            concepts_strengthened += 1
            print(f"🔄 Strengthened: {concept['name']}")

        print(f"   Domain: {concept['domain']}")
        print(f"   Rule: {concept['rule']}")
        print(f"   Confidence: {concept['confidence']:.2f}")
        print(f"   Use Count: {concept['use_count']}")
        print()

    # Statistics
    print("=" * 80)
    print("Statistics")
    print("=" * 80)
    print()

    stats = miner.get_statistics()
    print(f"Total Concepts: {stats['total_concepts']}")
    print(f"New Created: {concepts_created}")
    print(f"Strengthened: {concepts_strengthened}")
    print(f"Average Confidence: {stats['avg_confidence']:.2f}")
    print()

    print("By Domain:")
    for domain, count in stats['by_domain'].items():
        print(f"  {domain}: {count}")
    print()

    # Verify
    print("=" * 80)
    print("Verification")
    print("=" * 80)
    print()

    success_criteria = {
        "Total concepts >= 2": stats['total_concepts'] >= 2,
        "New created >= 2": concepts_created >= 2,
        "Strengthened >= 1": concepts_strengthened >= 1,
        "Average confidence > 0": stats['avg_confidence'] > 0
    }

    all_passed = all(success_criteria.values())

    for criterion, passed in success_criteria.items():
        status = "✅" if passed else "❌"
        print(f"{status} {criterion}")

    print()

    if all_passed:
        print("🎉 SUCCESS: Real Concept Mining works!")
        print()
        print(f"  ✓ {concepts_created} concepts created")
        print(f"  ✓ {concepts_strengthened} concepts strengthened")
        print(f"  ✓ {stats['total_concepts']} total concepts in database")
        print()
        print("  → Foundation ready to learn from Claude logs!")
        return 0
    else:
        print("⚠️  Some criteria not met")
        return 1


if __name__ == "__main__":
    exit(test_multiple_concepts())
