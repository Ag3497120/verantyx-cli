#!/usr/bin/env python3
"""
Simple Concept Mining Test - 1 dialogue only
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.concept_mining_complete import RealConceptMiner


def test_single_concept():
    """Test single concept extraction"""
    print("=" * 60)
    print("Simple Concept Mining Test - 1 Dialogue")
    print("=" * 60)
    print()

    miner = RealConceptMiner()

    # Single test dialogue
    user_input = "docker build でエラーが出ました"
    claude_response = "Dockerfileを確認してください。まず、COPY命令のパスが正しいかチェックしましょう。次に、ベースイメージが存在するか確認します。最後に、docker buildを再実行してください。"

    print(f"User: {user_input}")
    print(f"Claude: {claude_response[:80]}...")
    print()

    # Mine concept
    print("Mining concept...")
    concept, is_new = miner.mine(user_input, claude_response)

    print()
    print("=" * 60)
    print("Result:")
    print("=" * 60)
    print(f"Is New: {is_new}")
    print(f"Name: {concept['name']}")
    print(f"Domain: {concept['domain']}")
    print(f"Problem Type: {concept['problem_type']}")
    print(f"Rule: {concept['rule']}")
    print(f"Confidence: {concept['confidence']:.2f}")
    print(f"Use Count: {concept['use_count']}")
    print(f"Inputs: {concept['inputs']}")
    print(f"Outputs: {concept['outputs']}")
    print()

    # Verify
    if concept['domain'] == 'docker' and is_new:
        print("✅ SUCCESS: Concept extracted correctly!")
        return 0
    else:
        print("❌ FAILED: Concept not extracted properly")
        return 1


if __name__ == "__main__":
    exit(test_single_concept())
