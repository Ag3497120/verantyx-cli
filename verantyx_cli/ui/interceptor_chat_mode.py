"""
Interceptor Chat Mode - mitmproxy経由でClaude API監視

完全な傍受アプローチ:
1. Claude Codeを独立して実行（普通に使える）
2. mitmproxyで通信を傍受
3. Verantyxで応答を表示 + Cross構造に記録
"""

import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def start_interceptor_mode(project_path: Path, auto_launch: bool = True):
    """
    Interceptorモード起動

    Args:
        project_path: プロジェクトディレクトリ
        auto_launch: 自動起動モード（True=全て自動、False=手動）
    """
    from .simple_chat_ui import SimpleChatUI
    from ..engine.claude_api_interceptor import ClaudeAPIInterceptor
    from ..engine.auto_launcher import AutoLauncher

    print()
    print("=" * 70)
    print("  Verantyx Interceptor Mode")
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
            logging.FileHandler(verantyx_dir / 'interceptor.log')
        ]
    )

    # Auto Launcher
    launcher = None

    if auto_launch:
        # 自動起動モード
        launcher = AutoLauncher(project_path)

        if not launcher.launch_all():
            print()
            print("❌ 自動起動に失敗しました")
            print()
            print("手動セットアップ手順:")
            from ..engine.network_monitor import MitmproxyMonitor
            mitm = MitmproxyMonitor()
            mitm.start_instructions()
            return

    else:
        # 手動モード
        from ..engine.network_monitor import MitmproxyMonitor
        mitm = MitmproxyMonitor()
        mitm_script = mitm.generate_mitm_script()

        print("📋 セットアップ手順:")
        print()
        print("【ターミナル1】mitmproxy起動:")
        print(f"  mitmproxy -s {mitm_script} -p 8080")
        print()
        print("【ターミナル2】Claude Code起動:")
        print("  HTTPS_PROXY=http://localhost:8080 claude")
        print()
        print("【このターミナル】Verantyx UI（自動的に起動します）")
        print()
        print("=" * 70)
        print()

        # ユーザーに確認
        print("✋ 準備ができたらEnterを押してください...")
        print("   (mitmproxyとClaude Codeを起動してから)")
        input()

    print()
    print("🚀 Starting Verantyx UI...")
    print()

    # UI初期化
    ui = SimpleChatUI(
        llm_name="Claude Code (Intercepted)",
        cross_file=cross_file,
        verantyx_dir=verantyx_dir
    )

    # Interceptor起動
    def on_api_message(msg: dict):
        """API応答をUIに表示"""
        msg_type = msg['type']
        content = msg['content']

        ui.add_message(msg_type, content)

    interceptor = ClaudeAPIInterceptor(
        responses_file="/tmp/claude_responses.jsonl",
        cross_output=cross_file,
        on_message=on_api_message
    )

    interceptor.start()
    logger.info("Interceptor started")

    print("✅ Verantyx Interceptor Mode Started!")
    print()
    print("💡 使い方:")
    print("   - Claude Codeで普通に会話してください")
    print("   - 会話内容が自動的にこのUIに表示されます")
    print("   - Cross構造: {cross_file}")
    print()

    # UIループ
    try:
        ui.run()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    finally:
        interceptor.stop()

        # Auto Launcherのクリーンアップ
        if launcher:
            launcher.cleanup()

        print("✅ Interceptor stopped")
        print(f"   Conversation saved: {cross_file}")


if __name__ == "__main__":
    start_interceptor_mode(Path.cwd())
