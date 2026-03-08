"""
Network Monitor - Claude CodeのAPI通信を監視

macOSのネットワークトラフィックを監視して、Claude APIの通信をキャプチャ
"""

import subprocess
import json
import re
import threading
import logging
from typing import Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ClaudeNetworkMonitor:
    """
    Claude CodeのAPI通信を監視

    アプローチ:
    1. Claude CodeのプロセスIDを取得
    2. そのプロセスのネットワーク接続を監視
    3. Claude API (api.anthropic.com) への通信を検出
    4. Request/Responseをキャプチャ

    注意: macOSではroot権限が必要な場合があります
    """

    def __init__(self, on_message: Optional[Callable[[dict], None]] = None):
        """
        Args:
            on_message: メッセージ検出時のコールバック
                       {'type': 'user'/'assistant', 'content': str}
        """
        self.on_message = on_message
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Claude APIのホスト
        self.claude_api_hosts = [
            'api.anthropic.com',
            'claude.ai',
            'api.claude.ai'
        ]

    def start(self):
        """監視開始"""
        if self._running:
            logger.warning("Monitor already running")
            return

        logger.info("Starting network monitor...")

        # Claude Codeのプロセスを探す
        claude_pid = self._find_claude_process()
        if not claude_pid:
            logger.error("Claude Code process not found")
            raise RuntimeError("Claude Code is not running. Please start Claude Code first.")

        logger.info(f"Found Claude Code process: PID {claude_pid}")

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_connections,
            args=(claude_pid,),
            daemon=True
        )
        self._monitor_thread.start()

        logger.info("Network monitor started")

    def stop(self):
        """監視停止"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Network monitor stopped")

    def _find_claude_process(self) -> Optional[int]:
        """Claude Codeのプロセスを探す"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'claude'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                # 最初のPIDを返す
                return int(pids[0])

            return None
        except Exception as e:
            logger.error(f"Error finding Claude process: {e}")
            return None

    def _monitor_connections(self, pid: int):
        """
        ネットワーク接続を監視

        Note: これは簡易実装です。実際のパケットキャプチャには
              より高度な方法（mitmproxy、Wireshark等）が必要です。
        """
        logger.info(f"Monitoring network connections for PID {pid}")

        while self._running:
            try:
                # lsofでプロセスのネットワーク接続を取得
                result = subprocess.run(
                    ['lsof', '-p', str(pid), '-a', '-i', 'TCP'],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    # Claude APIへの接続をチェック
                    for line in result.stdout.split('\n'):
                        for host in self.claude_api_hosts:
                            if host in line and 'ESTABLISHED' in line:
                                logger.info(f"Active connection to Claude API: {line.strip()}")

                # TODO: 実際のパケット内容の取得
                # これには以下のいずれかが必要:
                # 1. mitmproxy経由でClaude Codeを実行
                # 2. macOSのNetwork Extension使用
                # 3. tcpdumpでパケットキャプチャ（root権限必要）

                import time
                time.sleep(1.0)

            except Exception as e:
                logger.error(f"Error monitoring connections: {e}")
                import time
                time.sleep(5.0)


class MitmproxyMonitor:
    """
    mitmproxyを使用したより高度な監視

    使用方法:
    1. mitmproxyをインストール: pip install mitmproxy
    2. mitmproxyスクリプトを作成（このクラスが生成）
    3. mitmproxy起動
    4. Claude CodeにHTTPS_PROXY環境変数を設定
    """

    def __init__(self, on_message: Optional[Callable[[dict], None]] = None):
        self.on_message = on_message
        self.proxy_port = 8080

    def generate_mitm_script(self, output_path: str = "/tmp/claude_mitm.py"):
        """mitmproxy用のスクリプトを生成"""
        script = '''"""
mitmproxy script for Claude Code monitoring
"""

import json
from mitmproxy import http

def response(flow: http.HTTPFlow) -> None:
    """Intercept Claude API responses"""

    # Claude APIのみを対象
    if "anthropic.com" in flow.request.pretty_host or "claude.ai" in flow.request.pretty_host:

        # リクエスト情報
        if flow.request.method == "POST":
            try:
                req_body = flow.request.content.decode('utf-8', errors='ignore')
                print(f"[REQUEST] {flow.request.pretty_url}")
                print(f"Body: {req_body[:200]}")
            except:
                pass

        # レスポンス情報
        if flow.response:
            try:
                resp_body = flow.response.content.decode('utf-8', errors='ignore')
                print(f"[RESPONSE] {flow.request.pretty_url}")
                print(f"Body: {resp_body[:200]}")

                # JSONファイルに保存
                with open("/tmp/claude_responses.jsonl", "a") as f:
                    data = {
                        "url": flow.request.pretty_url,
                        "method": flow.request.method,
                        "request": req_body if 'req_body' in locals() else "",
                        "response": resp_body,
                        "timestamp": flow.response.timestamp_start
                    }
                    f.write(json.dumps(data) + "\\n")

            except Exception as e:
                print(f"Error: {e}")
'''

        with open(output_path, 'w') as f:
            f.write(script)

        logger.info(f"Generated mitmproxy script: {output_path}")
        return output_path

    def start_instructions(self):
        """mitmproxy起動手順を表示"""
        script_path = self.generate_mitm_script()

        print()
        print("=" * 70)
        print("  Claude Network Monitor - mitmproxy Setup")
        print("=" * 70)
        print()
        print("1. mitmproxyをインストール:")
        print("   pip install mitmproxy")
        print()
        print("2. mitmproxyを起動:")
        print(f"   mitmproxy -s {script_path} -p {self.proxy_port}")
        print()
        print("3. 別のターミナルでClaude Codeを起動:")
        print(f"   HTTPS_PROXY=http://localhost:{self.proxy_port} claude")
        print()
        print("4. Claude Codeで会話すると、応答が /tmp/claude_responses.jsonl に保存されます")
        print()
        print("=" * 70)
        print()


def test_network_monitor():
    """テスト用"""
    print("🌐 Network Monitor Test")
    print()

    # mitmproxyアプローチを推奨
    print("Option 1: mitmproxy (推奨)")
    mitm = MitmproxyMonitor()
    mitm.start_instructions()

    print()
    print("Option 2: Simple connection monitor")

    def on_msg(msg):
        print(f"[{msg['type']}] {msg['content']}")

    try:
        monitor = ClaudeNetworkMonitor(on_message=on_msg)
        monitor.start()
        print("✅ Monitoring connections...")
        print("   Press Ctrl+C to stop")
        print()

        import time
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping...")
        monitor.stop()
        print("✅ Stopped")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_network_monitor()
