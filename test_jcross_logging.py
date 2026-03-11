#!/usr/bin/env python3
"""
JCrossベースのCross構造記録のテスト
"""

import json
from pathlib import Path
from verantyx_cli.engine.cross_conversation_logger import CrossConversationLogger


def test_jcross_logging():
    """JCrossベースのCross記録をテスト"""
    print()
    print("=" * 70)
    print("  🧪 Testing JCross-Based Cross Structure Logging")
    print("=" * 70)
    print()

    # テストファイル
    test_file = Path(".verantyx/test_conversation.cross.json")
    test_file.parent.mkdir(parents=True, exist_ok=True)

    # 既存ファイルを削除
    if test_file.exists():
        test_file.unlink()
        print("✅ Cleared old test file")

    # CrossConversationLoggerを初期化
    logger = CrossConversationLogger(test_file)
    print("✅ Initialized CrossConversationLogger")
    print()

    # テスト会話1: chatgptとは
    print("📝 Logging conversation 1: 'chatgptとは'")
    logger.log_user_input("chatgptとは")
    logger.log_claude_response(
        "ChatGPTは、OpenAIが開発した大規模言語モデルベースの対話型AIアシスタントです。\n\n"
        "主な特徴：\n"
        "1. GPT-3.5/GPT-4アーキテクチャをベース\n"
        "2. 自然な会話形式で質問に回答\n"
        "3. コード生成、文章作成、翻訳など多様なタスクに対応\n\n"
        "Claudeとの比較：\n"
        "- Claude: Anthropic社開発、Constitutional AI\n"
        "- ChatGPT: OpenAI開発、RLHF\n"
        "- 両者とも高度な言語理解能力を持つ"
    )
    logger.save()
    print("✅ Saved conversation 1")
    print()

    # テスト会話2: claudeとは
    print("📝 Logging conversation 2: 'claudeとは'")
    logger.log_user_input("claudeとは")
    logger.log_claude_response(
        "Claudeは、Anthropic社が開発した大規模言語モデルベースのAIアシスタントです。\n\n"
        "主な特徴：\n"
        "1. Constitutional AI（安全性重視の設計）\n"
        "2. 長文コンテキスト対応（100K+ tokens）\n"
        "3. 高度な推論能力と安全性\n\n"
        "バージョン：\n"
        "- Claude 3 Opus: 最高性能\n"
        "- Claude 3 Sonnet: バランス型\n"
        "- Claude 3 Haiku: 高速・軽量"
    )
    logger.save()
    print("✅ Saved conversation 2")
    print()

    # 統計確認
    stats = logger.get_statistics()
    print("📊 Statistics:")
    print(f"   - Total inputs: {stats['total_inputs']}")
    print(f"   - Total responses: {stats['total_responses']}")
    print(f"   - Conversation length: {stats['conversation_length']}")
    print()

    # Cross構造の内容を確認
    cross_structure = logger.get_cross_structure()
    axes = cross_structure.get('axes', {})

    print("📦 Cross Structure Contents:")
    print()

    # UP軸
    user_inputs = axes.get('UP', {}).get('user_inputs', [])
    print(f"UP Axis (user_inputs): {len(user_inputs)} items")
    for i, inp in enumerate(user_inputs, 1):
        print(f"  {i}. {inp[:50]}...")
    print()

    # DOWN軸
    claude_responses = axes.get('DOWN', {}).get('claude_responses', [])
    print(f"DOWN Axis (claude_responses): {len(claude_responses)} items")
    for i, resp in enumerate(claude_responses, 1):
        preview = resp[:100].replace('\n', ' ')
        print(f"  {i}. {preview}...")
    print()

    # FRONT軸
    conversation = axes.get('FRONT', {}).get('current_conversation', [])
    print(f"FRONT Axis (current_conversation): {len(conversation)} items")
    for i, item in enumerate(conversation, 1):
        role = item.get('role', 'unknown')
        content_preview = item.get('content', '')[:50].replace('\n', ' ')
        print(f"  {i}. [{role}] {content_preview}...")
    print()

    # データ形式の検証
    print("✅ Validation:")
    print(f"   - user_inputs are strings: {all(isinstance(inp, str) for inp in user_inputs)}")
    print(f"   - claude_responses are strings: {all(isinstance(resp, str) for resp in claude_responses)}")
    print()

    print("=" * 70)
    print("  ✅ JCross-Based Cross Logging Test Complete!")
    print("=" * 70)
    print()

    return test_file


if __name__ == "__main__":
    test_file = test_jcross_logging()
    print(f"Test file saved at: {test_file}")
    print()
    print("Next step: Test knowledge extraction with knowledge_learner.py")
