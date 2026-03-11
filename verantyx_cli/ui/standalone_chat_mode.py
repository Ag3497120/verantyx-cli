#!/usr/bin/env python3
"""
Verantyx Standalone Chat Mode - 学習済みAIとの対話

Claude Codeなしで、学習済みCross構造だけで動作
"""

import time
from pathlib import Path
from typing import Optional

from ..engine.standalone_ai import VerantyxStandaloneAI


def start_standalone_chat_mode(project_path: Path):
    """
    スタンドアロンチャットモード起動

    Args:
        project_path: プロジェクトディレクトリ
    """
    print()
    print("=" * 70)
    print("  🤖 Verantyx Standalone Mode - Learned AI")
    print("=" * 70)
    print()
    print("  Testing what Verantyx learned from Claude Code interactions")
    print("  This mode runs WITHOUT Claude Code connection")
    print()
    print("=" * 70)
    print()

    # Cross構造ファイル
    verantyx_dir = project_path / '.verantyx'
    cross_file = verantyx_dir / "conversation.cross.json"

    # 学習データの存在確認
    if not cross_file.exists():
        print("⚠️  No learning data found!")
        print()
        print("Verantyx needs to learn from interactions first.")
        print()
        print("To train Verantyx, run:")
        print("  python3 -m verantyx_cli chat")
        print()
        print("Have at least a few conversations, then come back to test")
        print("standalone mode with:")
        print("  python3 -m verantyx_cli standalone")
        print()
        return

    # AIエンジン初期化（スキル学習を有効化）
    print("🚀 Initializing Verantyx Standalone AI with Skill Learning...")
    ai = VerantyxStandaloneAI(cross_file, project_path=project_path, enable_skills=True)
    print()

    # 学習統計を表示
    stats = ai.get_learning_stats()

    print("📊 Learning Status:")
    print(f"   - Learned from: {stats['total_inputs']} interactions")
    print(f"   - Response patterns: {stats['total_responses']}")
    print(f"   - JCross patterns: {stats['learned_patterns']}")
    print(f"   - Cross memory size: {stats['cross_size_kb']:.1f} KB")
    print()

    if stats['tool_usage']:
        print("🔧 Learned Tool Patterns:")
        for tool, count in sorted(stats['tool_usage'].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   - {tool}: {count} uses")
        print()

    # スキル学習統計を表示
    if 'skills' in stats:
        skills = stats['skills']
        print("🎓 Learned Skills:")
        print(f"   - Tool patterns: {skills['tool_patterns_count']}")
        print(f"   - Workflows: {skills['workflows_count']}")
        print(f"   - Code templates: {skills['code_templates_count']}")
        print(f"   - Error solutions: {skills['error_solutions_count']}")
        print()

        if skills['top_patterns']:
            print("   Top tool patterns:")
            for pattern, count in skills['top_patterns'][:3]:
                print(f"      • {pattern}: {count}x")
            print()

    # 学習レベル評価
    learning_level = "Beginner"
    if stats['total_inputs'] >= 100:
        learning_level = "Expert"
    elif stats['total_inputs'] >= 50:
        learning_level = "Advanced"
    elif stats['total_inputs'] >= 20:
        learning_level = "Intermediate"

    print(f"🎓 Learning Level: {learning_level}")
    print()

    print("=" * 70)
    print()
    print("💡 Usage:")
    print("   - Type your message and press Enter")
    print("   - Verantyx will respond based on learned patterns")
    print("   - Type 'exit', 'quit', or 'bye' to quit")
    print("   - Type 'stats' to see learning statistics")
    print("   - Type 'skills' to see learned operational skills")
    print("   - Type 'train' to see training recommendations")
    print()
    print("⚠️  Note: Standalone mode runs learned skills in dry-run mode")
    print("   For actual execution, use: python3 -m verantyx_cli chat")
    print()
    print("=" * 70)
    print()

    # チャットループ
    conversation_count = 0

    try:
        while True:
            # ユーザー入力
            try:
                user_input = input("\n🗣️  You: ")
            except EOFError:
                break

            if not user_input.strip():
                continue

            # 終了コマンド
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\n👋 Goodbye!")
                print()
                print(f"📊 This session: {conversation_count} interactions")
                print()
                print("To continue learning and improve my responses:")
                print("  python3 -m verantyx_cli chat")
                print()
                break

            # 統計表示
            if user_input.lower() == 'stats':
                print()
                print("📊 Current Learning Statistics:")
                print()
                current_stats = ai.get_learning_stats()
                print(f"   Total interactions learned: {current_stats['total_inputs']}")
                print(f"   Response patterns: {current_stats['total_responses']}")
                print(f"   JCross patterns: {current_stats['learned_patterns']}")
                print(f"   Cross file size: {current_stats['cross_size_kb']:.1f} KB")
                print()
                print(f"   Learning level: {learning_level}")
                print()
                if current_stats['tool_usage']:
                    print("   Tool usage patterns:")
                    for tool, count in sorted(current_stats['tool_usage'].items(), key=lambda x: x[1], reverse=True):
                        print(f"      - {tool}: {count} times")
                    print()
                continue

            # スキル表示
            if user_input.lower() == 'skills':
                print()
                skills_summary = ai.get_learned_skills_summary()
                print(skills_summary)
                continue

            # トレーニング推奨
            if user_input.lower() == 'train':
                print()
                print("🎓 Training Recommendations:")
                print()

                if stats['total_inputs'] < 10:
                    print("   📚 Status: Just getting started")
                    print()
                    print("   Next steps:")
                    print("   1. Use full mode for more conversations")
                    print("      python3 -m verantyx_cli chat")
                    print()
                    print("   2. Try diverse topics:")
                    print("      - File operations")
                    print("      - Code writing")
                    print("      - Search and analysis")
                    print("      - Testing and execution")
                    print()
                    print("   Goal: 10+ interactions for basic patterns")

                elif stats['total_inputs'] < 50:
                    print("   📈 Status: Building knowledge base")
                    print()
                    print("   You're making good progress!")
                    print()
                    print("   To improve further:")
                    print("   - Continue varied conversations")
                    print("   - Try complex multi-step tasks")
                    print("   - Use different programming languages")
                    print()
                    print("   Goal: 50+ interactions for solid patterns")

                else:
                    print("   ✨ Status: Well trained!")
                    print()
                    print("   Great job! I've learned from {stats['total_inputs']} interactions.")
                    print()
                    print("   I can now recognize:")
                    print("   - Common question patterns")
                    print("   - Tool usage scenarios")
                    print("   - Task workflows")
                    print()
                    print("   Keep using me to maintain and expand my knowledge!")

                print()
                continue

            # 応答生成
            print("\n🤖 Verantyx: ", end='', flush=True)
            print("[Analyzing learned patterns...]", flush=True)

            # 処理中を表現（学習済みパターンの検索）
            time.sleep(0.5)

            # 応答生成
            response = ai.generate_response(user_input)

            print("\r" + " " * 50 + "\r", end='')  # クリア
            print(f"🤖 Verantyx:\n\n{response}")

            conversation_count += 1

            # 会話カウントの節目でメッセージ
            if conversation_count % 5 == 0:
                print()
                print(f"💬 Session interactions: {conversation_count}")
                print()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
        print()

    # 終了メッセージ
    print()
    print("=" * 70)
    print()
    print("Thank you for testing Verantyx Standalone Mode!")
    print()
    print("🌱 To help me learn more:")
    print("   python3 -m verantyx_cli chat")
    print()
    print("🌐 To see learning visualization:")
    print("   python3 -m verantyx_cli chat --viewer")
    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    from pathlib import Path
    start_standalone_chat_mode(Path("."))
