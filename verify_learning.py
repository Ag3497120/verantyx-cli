#!/usr/bin/env python3
"""
学習内容の検証スクリプト

Cross構造に何が記録されているか、どう学習されているかを確認
"""

import json
from pathlib import Path
import sys


def verify_cross_structure():
    """Cross構造の内容を検証"""
    cross_file = Path('.verantyx/conversation.cross.json')

    if not cross_file.exists():
        print("❌ Cross structure file not found")
        print(f"   Expected: {cross_file}")
        return False

    print("=" * 80)
    print("📊 Cross Structure Verification")
    print("=" * 80)

    data = json.load(open(cross_file, encoding='utf-8'))

    # 6軸の確認
    axes = data.get('axes', {})

    print("\n[1] 6-Axis Structure:")
    for axis_name in ['UP', 'DOWN', 'LEFT', 'RIGHT', 'FRONT', 'BACK']:
        if axis_name in axes:
            print(f"  ✅ {axis_name} axis exists")
        else:
            print(f"  ❌ {axis_name} axis missing")

    # UP軸（ユーザー入力）
    print("\n[2] UP Axis (User Inputs):")
    user_inputs = axes.get('UP', {}).get('user_inputs', [])
    print(f"  Total inputs: {len(user_inputs)}")

    if user_inputs:
        print("\n  Latest inputs:")
        for i, inp in enumerate(user_inputs[-3:], 1):
            # コンテキストマーカーを抽出
            if '[CTX:' in inp:
                import re
                match = re.search(r'\[CTX:([^\|]+)\|TOPIC:([^\]]+)\]\s*(.+)', inp)
                if match:
                    ctx_id = match.group(1)
                    topic = match.group(2)
                    question = match.group(3)
                    print(f"    {i}. Topic: {topic}")
                    print(f"       Question: {question[:60]}...")
                    print(f"       Context ID: {ctx_id}")
                else:
                    print(f"    {i}. {inp[:60]}...")
            else:
                print(f"    {i}. {inp[:60]}...")

    # DOWN軸（Claude応答）
    print("\n[3] DOWN Axis (Claude Responses):")
    responses = axes.get('DOWN', {}).get('claude_responses', [])
    print(f"  Total responses: {len(responses)}")

    if responses:
        print(f"\n  Latest response preview:")
        latest = responses[-1]
        print(f"    Length: {len(latest)} chars")
        print(f"    Preview: {latest[:150]}...")

    # BACK軸（JCrossプログラム）
    print("\n[4] BACK Axis (JCross Programs):")
    jcross_programs = axes.get('BACK', {}).get('jcross_programs', [])
    print(f"  Total programs: {len(jcross_programs)}")

    if jcross_programs:
        print("\n  Latest JCross program:")
        latest_prog = jcross_programs[-1]
        print(f"    Question: {latest_prog.get('user_question', 'N/A')[:60]}...")
        print(f"    Operations count: {latest_prog.get('operations_count', 0)}")
        print(f"\n    Program preview:")
        program = latest_prog.get('jcross_program', '')
        for line in program.split('\n')[:5]:
            if line.strip():
                print(f"      {line}")

    # FRONT軸（推論パターン）
    print("\n[5] FRONT Axis (Reasoning Patterns):")
    patterns = axes.get('FRONT', {}).get('reasoning_patterns', [])
    print(f"  Total patterns: {len(patterns)}")

    if patterns:
        print("\n  Latest reasoning pattern:")
        latest_pattern = patterns[-1]
        print(f"    Topic: {latest_pattern.get('topic', 'N/A')}")
        pattern_text = latest_pattern.get('pattern', '')
        for line in pattern_text.split('\n')[:3]:
            if line.strip():
                print(f"      {line}")

    return len(user_inputs) > 0 and len(responses) > 0


def verify_knowledge_extraction():
    """知識抽出の検証"""
    cross_file = Path('.verantyx/conversation.cross.json')

    if not cross_file.exists():
        return

    print("\n" + "=" * 80)
    print("🧠 Knowledge Extraction Verification")
    print("=" * 80)

    from verantyx_cli.engine.knowledge_learner import KnowledgeLearner

    learner = KnowledgeLearner(cross_file)

    # 知識を抽出
    print("\n[1] Extracting knowledge from Cross structure...")
    learner.learn()

    # サマリーを取得
    summary = learner.get_knowledge_summary()

    print(f"\n[2] Extracted Knowledge Summary:")
    print(f"  Q&A Patterns: {summary['qa_patterns_count']}")
    print(f"  Concepts: {summary['concepts_count']}")
    print(f"  Skills: {summary['skills_count']}")

    # 概念を表示
    if summary['top_concepts']:
        print(f"\n[3] Top Concepts (first 10):")
        for i, concept in enumerate(summary['top_concepts'][:10], 1):
            print(f"    {i}. {concept}")

    # Q&Aパターンを表示
    print(f"\n[4] Q&A Pattern Keys:")
    for key in list(learner.learned_knowledge['qa_patterns'].keys())[:5]:
        print(f"    - {key}")

    return summary['qa_patterns_count'] > 0


def verify_standalone_readiness():
    """スタンドアロンモードの準備状態を確認"""
    print("\n" + "=" * 80)
    print("🤖 Standalone Mode Readiness")
    print("=" * 80)

    cross_file = Path('.verantyx/conversation.cross.json')

    if not cross_file.exists():
        print("  ❌ No learning data (Cross structure missing)")
        return False

    from verantyx_cli.engine.knowledge_learner import KnowledgeLearner

    learner = KnowledgeLearner(cross_file)
    learner.learn()

    summary = learner.get_knowledge_summary()

    # 準備状態チェック
    checks = {
        'Q&A patterns exist': summary['qa_patterns_count'] > 0,
        'Concepts extracted': summary['concepts_count'] > 0,
        'Multiple inputs': len(learner.learned_knowledge.get('qa_patterns', {})) > 1,
    }

    print("\n[1] Readiness Checks:")
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")

    all_passed = all(checks.values())

    if all_passed:
        print("\n[2] Status: ✅ Ready for standalone mode")
        print("\n[3] Test Query Suggestions:")

        # 学習したトピックから提案
        topics = set()
        for key in learner.learned_knowledge['qa_patterns'].keys():
            # keyの形式: "question_type:topic:keywords"
            parts = key.split(':')
            if len(parts) > 1:
                topics.add(parts[1])

        if topics:
            print("    Based on learned topics, try:")
            for topic in list(topics)[:3]:
                print(f"      - {topic}とは")
                print(f"      - {topic}について教えて")
    else:
        print("\n[2] Status: ❌ Not ready yet")
        print("    Need more conversation data for learning")

    return all_passed


def main():
    print("\n🔍 Verantyx Learning Verification\n")

    # Step 1: Cross構造の確認
    has_data = verify_cross_structure()

    if not has_data:
        print("\n⚠️  No learning data found. Please run chat mode first:")
        print("    python3 -m verantyx_cli chat")
        return

    # Step 2: 知識抽出の確認
    has_knowledge = verify_knowledge_extraction()

    # Step 3: スタンドアロンモードの準備確認
    is_ready = verify_standalone_readiness()

    # 最終結果
    print("\n" + "=" * 80)
    print("📋 Summary")
    print("=" * 80)

    if is_ready:
        print("\n✅ Learning successful!")
        print("\nNext step: Test standalone mode")
        print("  python3 -m verantyx_cli standalone")
    else:
        print("\n⚠️  Learning incomplete")
        print("\nSuggestion: Add more conversations in chat mode")
        print("  python3 -m verantyx_cli chat")


if __name__ == '__main__':
    main()
