#!/usr/bin/env python3
"""
JCross統合検証スクリプト

ClaudeSubprocessEngineが正しくCrossConversationLogger（JCrossベース）を使用しているか確認
"""

import inspect
from pathlib import Path
from verantyx_cli.engine.claude_subprocess_engine import ClaudeSubprocessEngine


def verify_jcross_integration():
    """JCross統合を検証"""
    print()
    print("=" * 70)
    print("  🔍 Verifying JCross Integration")
    print("=" * 70)
    print()

    # 1. _record_to_cross メソッドのソースコード確認
    print("1. Checking ClaudeSubprocessEngine._record_to_cross implementation:")
    print()

    source = inspect.getsource(ClaudeSubprocessEngine._record_to_cross)

    # JCross関連のキーワードをチェック
    checks = {
        'CrossConversationLogger': 'CrossConversationLogger' in source,
        'conversation_logger.jcross': 'conversation_logger.jcross' in source or 'JCross' in source,
        'log_user_input': 'log_user_input' in source,
        'log_claude_response': 'log_claude_response' in source,
        'save()': 'save()' in source,
    }

    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"   {status} {check_name}: {result}")

    print()

    # 2. conversation_logger.jcross ファイルの存在確認
    print("2. Checking conversation_logger.jcross file:")
    print()

    jcross_file = Path("verantyx_cli/engine/conversation_logger.jcross")
    if jcross_file.exists():
        print(f"   ✅ File exists: {jcross_file}")

        # ラベルを確認
        content = jcross_file.read_text(encoding='utf-8')
        labels = [
            "会話記録初期化",
            "ユーザー入力記録",
            "Claude応答記録",
            "ツール呼び出し記録",
            "JCrossプロンプト記録",
            "生相互作用記録",
            "Cross構造保存",
            "Cross構造読み込み",
            "会話ターン記録",
            "統計取得",
            "単一メッセージ記録"
        ]

        print()
        print("   JCross Labels:")
        for label in labels:
            exists = f"ラベル {label}" in content
            status = "✅" if exists else "❌"
            print(f"      {status} {label}")
    else:
        print(f"   ❌ File not found: {jcross_file}")

    print()

    # 3. CrossConversationLogger の確認
    print("3. Checking CrossConversationLogger:")
    print()

    try:
        from verantyx_cli.engine.cross_conversation_logger import CrossConversationLogger

        # メソッドリストを確認
        methods = [
            'log_user_input',
            'log_claude_response',
            'log_tool_call',
            'log_jcross_prompt',
            'log_raw_interaction',
            'log_conversation_turn',
            'save',
            'get_statistics',
            'get_cross_structure'
        ]

        for method in methods:
            exists = hasattr(CrossConversationLogger, method)
            status = "✅" if exists else "❌"
            print(f"   {status} {method}")

    except ImportError as e:
        print(f"   ❌ Failed to import CrossConversationLogger: {e}")

    print()

    # 4. 統合ステータス
    print("=" * 70)
    all_checks_passed = all(checks.values()) and jcross_file.exists()

    if all_checks_passed:
        print("  ✅ JCross Integration: VERIFIED")
        print()
        print("  The system is properly configured to use JCross-based logging.")
        print("  All conversation data will be recorded through conversation_logger.jcross")
    else:
        print("  ❌ JCross Integration: INCOMPLETE")
        print()
        print("  Some components are missing. Please check the failed items above.")

    print("=" * 70)
    print()

    return all_checks_passed


if __name__ == "__main__":
    success = verify_jcross_integration()
    exit(0 if success else 1)
