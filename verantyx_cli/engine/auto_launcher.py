"""
Auto Launcher - mitmproxy と Claude Code を自動起動

ユーザーは `verantyx intercept` 一発で全て起動
"""

import subprocess
import time
import os
import signal
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class AutoLauncher:
    """
    mitmproxy と Claude Code を自動起動・管理

    起動順序:
    1. mitmproxy（バックグラウンド）
    2. Claude Code（新しいターミナルタブ、HTTPS_PROXY設定）
    3. Verantyx UI（このプロセス）
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.mitm_process: Optional[subprocess.Popen] = None
        self.mitm_script = "/tmp/claude_mitm.py"
        self.proxy_port = 8080
        self.claude_pid: Optional[int] = None

    def launch_all(self) -> bool:
        """すべてのコンポーネントを起動"""
        print()
        print("=" * 70)
        print("  🚀 Verantyx Auto Launcher")
        print("=" * 70)
        print()

        # 1. mitmproxy起動
        if not self.launch_mitmproxy():
            return False

        # 2. Claude Code起動（プロキシ経由）
        if not self.launch_claude_with_proxy():
            return False

        print()
        print("✅ すべてのコンポーネントが起動しました！")
        print()
        print("💡 使い方:")
        print("   - Claudeタブで普通に会話してください")
        print("   - 会話内容が自動的にこのUIに表示されます")
        print("   - Ctrl+Cで全てのプロセスを停止します")
        print()
        print("=" * 70)
        print()

        return True

    def launch_mitmproxy(self) -> bool:
        """mitmproxyをバックグラウンドで起動"""
        print("📡 mitmproxy起動中...")

        # mitmproxyがインストールされているか確認
        try:
            result = subprocess.run(
                ['which', 'mitmproxy'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print()
                print("❌ mitmproxyがインストールされていません")
                print()
                print("インストール方法:")
                print("  pip3 install mitmproxy")
                print()
                return False

        except Exception as e:
            logger.error(f"Failed to check mitmproxy: {e}")
            return False

        # mitmproxyスクリプトを生成
        from .network_monitor import MitmproxyMonitor
        mitm = MitmproxyMonitor()
        self.mitm_script = mitm.generate_mitm_script()

        # ログファイル
        verantyx_dir = self.project_path / '.verantyx'
        verantyx_dir.mkdir(exist_ok=True)
        mitm_log = verantyx_dir / 'mitmproxy.log'

        # mitmproxy起動
        try:
            log_file = open(mitm_log, 'w')

            self.mitm_process = subprocess.Popen(
                [
                    'mitmproxy',
                    '-s', self.mitm_script,
                    '-p', str(self.proxy_port),
                    '--set', 'confdir=' + str(verantyx_dir / 'mitmproxy_config'),
                    '--set', 'flow_detail=0',  # 詳細ログを抑制
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True  # 独立したプロセスグループ
            )

            # 起動確認（ポートが開くまで待機）
            max_wait = 10
            for i in range(max_wait):
                time.sleep(0.5)

                # ポートが開いているか確認
                result = subprocess.run(
                    ['lsof', '-i', f':{self.proxy_port}', '-sTCP:LISTEN'],
                    capture_output=True
                )

                if result.returncode == 0:
                    print(f"✅ mitmproxy起動完了 (port {self.proxy_port})")
                    print(f"   ログ: {mitm_log}")
                    return True

            print("⚠️  mitmproxyの起動確認ができませんでした")
            print(f"   ログを確認してください: {mitm_log}")
            return True  # 一応継続

        except Exception as e:
            print(f"❌ mitmproxy起動失敗: {e}")
            return False

    def launch_claude_with_proxy(self) -> bool:
        """Claude Codeをプロキシ経由で新しいタブに起動"""
        print()
        print("🤖 Claude Code起動中...")

        # Claudeコマンドの存在確認
        try:
            result = subprocess.run(
                ['which', 'claude'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print()
                print("❌ Claude Codeがインストールされていません")
                print()
                print("インストール方法:")
                print("  npm install -g @anthropic-ai/claude-code")
                print()
                return False

        except Exception as e:
            logger.error(f"Failed to check claude: {e}")
            return False

        # ターミナルの種類を検出
        terminal_type = self._detect_terminal()

        if terminal_type == "Terminal.app":
            success = self._launch_claude_terminal_app()
        elif terminal_type == "iTerm":
            success = self._launch_claude_iterm()
        else:
            print(f"❌ サポートされていないターミナル: {terminal_type}")
            print("   Terminal.app または iTerm2 を使用してください")
            return False

        if success:
            print(f"✅ Claude Code起動完了")
            print(f"   新しいタブでClaude Codeが実行されています")

            # Claude起動を少し待つ
            time.sleep(2)

            # PIDを取得
            self.claude_pid = self._get_claude_pid()
            if self.claude_pid:
                print(f"   Process ID: {self.claude_pid}")

        return success

    def _detect_terminal(self) -> str:
        """使用中のターミナルを検出"""
        term_program = os.environ.get('TERM_PROGRAM', '')

        if 'iTerm' in term_program:
            return 'iTerm'
        elif 'Apple_Terminal' in term_program or term_program == '':
            return 'Terminal.app'
        else:
            return 'Unknown'

    def _launch_claude_terminal_app(self) -> bool:
        """Terminal.appで新しいタブに起動"""
        try:
            # プロキシ設定を含むコマンド
            claude_cmd = f"cd '{self.project_path}' && HTTPS_PROXY=http://localhost:{self.proxy_port} claude"

            applescript = f'''
            tell application "Terminal"
                activate
                tell application "System Events"
                    keystroke "t" using command down
                end tell
                delay 0.5
                do script "{claude_cmd}" in front window
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True
            )

            return result.returncode == 0

        except Exception as e:
            logger.error(f"Failed to launch Claude in Terminal.app: {e}")
            return False

    def _launch_claude_iterm(self) -> bool:
        """iTerm2で新しいタブに起動"""
        try:
            claude_cmd = f"cd '{self.project_path}' && HTTPS_PROXY=http://localhost:{self.proxy_port} claude"

            applescript = f'''
            tell application "iTerm"
                activate
                tell current window
                    create tab with default profile
                    tell current session
                        write text "{claude_cmd}"
                    end tell
                end tell
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True
            )

            return result.returncode == 0

        except Exception as e:
            logger.error(f"Failed to launch Claude in iTerm: {e}")
            return False

    def _get_claude_pid(self) -> Optional[int]:
        """Claude CodeのPIDを取得"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'claude'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                # 最新のPID（最後のもの）を返す
                return int(pids[-1])

            return None

        except Exception as e:
            logger.error(f"Failed to get Claude PID: {e}")
            return None

    def cleanup(self):
        """すべてのプロセスをクリーンアップ"""
        print()
        print("🛑 プロセスを停止中...")

        # mitmproxy停止
        if self.mitm_process:
            try:
                logger.info(f"Stopping mitmproxy (PID: {self.mitm_process.pid})")
                self.mitm_process.terminate()
                self.mitm_process.wait(timeout=5)
                print("   ✅ mitmproxy停止")
            except Exception as e:
                logger.error(f"Failed to stop mitmproxy: {e}")
                try:
                    self.mitm_process.kill()
                except:
                    pass

        # Claude Code停止
        if self.claude_pid:
            try:
                logger.info(f"Stopping Claude Code (PID: {self.claude_pid})")
                os.kill(self.claude_pid, signal.SIGTERM)
                time.sleep(1)
                print("   ✅ Claude Code停止")
            except ProcessLookupError:
                pass  # 既に停止している
            except Exception as e:
                logger.error(f"Failed to stop Claude: {e}")

        print()
        print("✅ クリーンアップ完了")


def test_auto_launcher():
    """テスト用"""
    print("🚀 Auto Launcher Test")
    print()

    launcher = AutoLauncher(Path.cwd())

    try:
        if launcher.launch_all():
            print("✅ Launch successful!")
            print("   Press Ctrl+C to stop all processes")
            print()

            # 待機
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    finally:
        launcher.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_auto_launcher()
