"""
Verantyx Chat Mode - 独自UIでClaudeエンジンを制御

ユーザー体験:
- `verantyx chat` で起動
- 完全に独自のUI
- 裏でClaude Codeが動いている
- Cross構造で記憶が進化
- 使用感はシームレス
"""

import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def start_verantyx_chat_mode(project_path: Path, show_cross: bool = False):
    """
    Verantyx Chat Mode起動

    Args:
        project_path: プロジェクトディレクトリ
        show_cross: Cross構造の成長を表示するか
    """
    from ..engine.claude_subprocess_engine import ClaudeSubprocessEngine
    from .simple_chat_ui import SimpleChatUI

    print()
    print("=" * 70)
    print("  🌟 Verantyx-CLI - Autonomous AI with Cross Memory")
    print("=" * 70)
    print()
    print("  Powered by Claude Code + Cross Structure")
    print("  Your personal AI that evolves with every conversation")
    print()
    print("=" * 70)
    print()

    # .verantyxディレクトリ
    verantyx_dir = project_path / '.verantyx'
    verantyx_dir.mkdir(exist_ok=True)

    # Crossファイル
    cross_file = verantyx_dir / "conversation.cross.json"

    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(verantyx_dir / 'verantyx.log')
        ]
    )

    print("🚀 Initializing Verantyx Engine...")
    print()

    # UI初期化
    ui = SimpleChatUI(
        llm_name="Verantyx Agent",
        cross_file=cross_file,
        verantyx_dir=verantyx_dir
    )

    # Claudeエンジン起動
    engine: Optional[ClaudeSubprocessEngine] = None

    # 起動画面を表示するかのフラグ
    welcome_shown = {'value': False}

    def on_claude_output(text: str):
        """Claude生出力（リアルタイム表示）"""
        # デバッグログ: トラブルシューティング用（本番でも有用）
        with open(verantyx_dir / 'debug_output.log', 'a', encoding='utf-8') as f:
            f.write(f"[{time.time()}] {repr(text)}\n")

        # ANSIエスケープシーケンスを除去
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean = ansi_escape.sub('', text)

        # クリーンな出力もログ（デバッグ用）
        if clean.strip():
            with open(verantyx_dir / 'debug_clean.log', 'a', encoding='utf-8') as f:
                f.write(f"[{time.time()}] {clean}\n")

        # 起動画面は一度だけ表示
        if not welcome_shown['value']:
            if "Welcome back!" in text or "Claude Code" in text:
                # 起動画面を表示
                print(text, end='', flush=True)
                if "Try \"" in text:
                    # 起動完了
                    welcome_shown['value'] = True
                    print()  # 改行
                return

        # 起動後は、すべての出力を表示（フィルタなし）
        # ただし、繰り返しのプロンプト行は除外
        if clean.strip():
            # プロンプト行（">" で始まる短い行）は除外
            lines = clean.split('\n')
            for line in lines:
                stripped = line.strip()
                # プロンプト以外を表示
                if stripped and not (stripped == '>' or stripped.startswith('────>')):
                    print(line, flush=True)

    def on_claude_response(response: str):
        """Claude応答完了"""
        # UIに追加（簡易版なのでスキップ）
        # ui.add_message('assistant', response)

        # Cross構造の成長を表示
        if show_cross:
            cross_stats = engine.cross_memory['axes']
            total_msgs = cross_stats['UP']['total_messages']
            total_responses = len(cross_stats['DOWN']['claude_responses'])
            print(f"\n\n  💾 Cross Memory: {total_msgs} inputs, {total_responses} responses")

    engine = ClaudeSubprocessEngine(
        project_path=project_path,
        cross_file=cross_file,
        on_output=on_claude_output,
        on_claude_response=on_claude_response
    )

    # エンジン起動
    if not engine.start():
        print()
        print("❌ Failed to start Verantyx Engine")
        print()
        print("Make sure Claude Code is installed:")
        print("  npm install -g @anthropic-ai/claude-code")
        print()
        return

    print("✅ Verantyx Engine Started!")
    print()

    # 準備待機（エンジン内で待機するので短縮）
    time.sleep(1.0)

    if not engine.is_ready():
        print("⚠️  Engine not ready, waiting...")
        time.sleep(2.0)

    print()
    print("=" * 70)
    print()
    print("💡 Usage:")
    print("   - Type your message and press Enter")
    print("   - JCross will automatically enhance prompts with Cross memory")
    print("   - All conversations are saved to Cross structure")
    print("   - Press Ctrl+C to exit")
    print()
    print("📂 Cross Memory: ", cross_file)
    print()
    print("=" * 70)
    print()

    # チャットループ
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
                break

            # UIに追加（簡易版なのでスキップ）
            # ui.add_message('user', user_input)

            # Claudeに送信（JCross拡張あり）
            print("\n📤 Sending to Claude...", flush=True)
            print("🤖 Verantyx Agent: ", end='', flush=True)

            success = engine.send_prompt(user_input, use_jcross=True)

            if not success:
                print("\n❌ Failed to send prompt")
                continue

            print("[Waiting for response...]", flush=True)

            # 応答待機（応答が完了するまで）
            # Claude が次の入力待ち状態になるまで待つ
            max_wait = 30  # 最大30秒
            for i in range(max_wait * 10):
                if engine.waiting_for_input:
                    print("\n[Response complete]", flush=True)
                    break
                time.sleep(0.1)
            else:
                print("\n⚠️ Timeout waiting for response", flush=True)

    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")

    finally:
        # エンジン停止
        if engine:
            engine.stop()

        print()
        print("=" * 70)
        print()
        print("✅ Session ended")
        print(f"   Cross Memory saved: {cross_file}")
        print()
        print("   Your Verantyx Agent has learned from this conversation.")
        print("   Next time, it will remember what you discussed!")
        print()
        print("=" * 70)


def start_verantyx_chat_simple(project_path: Path):
    """
    シンプル版（Cross表示なし）
    """
    start_verantyx_chat_mode(project_path, show_cross=False)


def start_verantyx_chat_verbose(project_path: Path):
    """
    詳細版（Cross構造の成長を表示）
    """
    start_verantyx_chat_mode(project_path, show_cross=True)


if __name__ == "__main__":
    start_verantyx_chat_mode(Path.cwd())
