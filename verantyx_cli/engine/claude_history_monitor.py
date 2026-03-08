"""
Claude History Monitor - ~/.claude/history.jsonl を監視

Claude Codeの内部通信を傍受するハック的アプローチ
"""

import json
import time
import threading
from pathlib import Path
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


class ClaudeHistoryMonitor:
    """
    Claude Codeのhistory.jsonlを監視して新しい会話を検出

    アーキテクチャ:
    - Claude Code → history.jsonl に会話を記録
    - Monitor → ファイルを監視（tail -f相当）
    - 新しい行が追加されたら → コールバック呼び出し
    """

    def __init__(self, on_new_message: Optional[Callable[[dict], None]] = None):
        """
        Args:
            on_new_message: 新しいメッセージが検出されたときのコールバック
        """
        self.history_file = Path.home() / ".claude" / "history.jsonl"
        self.on_new_message = on_new_message

        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_position = 0
        self._session_start_time = time.time() * 1000  # ミリ秒

    def start(self):
        """監視開始"""
        if self._running:
            logger.warning("Monitor already running")
            return

        if not self.history_file.exists():
            logger.error(f"History file not found: {self.history_file}")
            raise FileNotFoundError(f"Claude history file not found: {self.history_file}")

        # 現在のファイル位置を記録（これ以降の追加分のみ監視）
        self._last_position = self.history_file.stat().st_size

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info(f"Started monitoring: {self.history_file}")
        logger.info(f"Session start time: {self._session_start_time}")

    def stop(self):
        """監視停止"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Stopped monitoring")

    def _monitor_loop(self):
        """ファイル監視ループ（tail -f相当）"""
        while self._running:
            try:
                # ファイルサイズチェック
                current_size = self.history_file.stat().st_size

                if current_size > self._last_position:
                    # 新しいデータがある
                    with open(self.history_file, 'r', encoding='utf-8') as f:
                        # 最後に読んだ位置にシーク
                        f.seek(self._last_position)

                        # 新しい行を読み取り
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    message = json.loads(line)

                                    # このセッション開始後のメッセージのみ処理
                                    msg_timestamp = message.get('timestamp', 0)
                                    if msg_timestamp >= self._session_start_time:
                                        self._process_message(message)

                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse JSON: {e}")

                        # 現在位置を更新
                        self._last_position = f.tell()

                elif current_size < self._last_position:
                    # ファイルが切り詰められた（ログローテーション等）
                    logger.info("History file was truncated, resetting position")
                    self._last_position = 0

                # 短い間隔で監視（0.1秒）
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(1.0)

    def _process_message(self, message: dict):
        """メッセージ処理"""
        try:
            # メッセージの種類を判定
            msg_type = self._detect_message_type(message)

            logger.info(f"New message detected: type={msg_type}, display={message.get('display', '')[:50]}")

            # コールバック呼び出し
            if self.on_new_message:
                self.on_new_message({
                    'type': msg_type,
                    'content': message.get('display', ''),
                    'timestamp': message.get('timestamp'),
                    'project': message.get('project'),
                    'session_id': message.get('sessionId'),
                    'raw': message
                })

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _detect_message_type(self, message: dict) -> str:
        """
        メッセージの種類を判定

        Returns:
            'user' - ユーザー入力
            'assistant' - Claude応答
            'system' - システムメッセージ
        """
        # history.jsonlの構造から判定
        # "display"フィールドがある場合は通常ユーザー入力
        # ただし、より詳細な判定が必要な場合は追加のロジックを実装

        # 簡易判定：とりあえずユーザー入力として扱う
        # （Claude応答は別のフィールドにある可能性があるため、
        #  実際のデータ構造を見て調整が必要）

        return 'user'  # TODO: より詳細な判定ロジック


def test_monitor():
    """テスト用関数"""
    print("🔍 Claude History Monitor - Test")
    print()

    def on_message(msg: dict):
        print(f"[{msg['type']}] {msg['content'][:100]}")

    monitor = ClaudeHistoryMonitor(on_new_message=on_message)

    try:
        monitor.start()
        print("✅ Monitoring started")
        print("   Waiting for new messages in Claude Code...")
        print("   Press Ctrl+C to stop")
        print()

        # 監視継続
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping monitor...")
        monitor.stop()
        print("✅ Stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_monitor()
