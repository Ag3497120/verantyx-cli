"""
Claude API Interceptor - mitmproxy監視 + Cross構造書き込み

アーキテクチャ:
1. mitmproxy → claude_responses.jsonl に書き込み
2. このモジュール → jsonlファイルを監視（tail -f）
3. 新しい応答を検出 → Cross構造に変換
4. Crossファイルに書き込み + Verantyx UIに通知
"""

import json
import time
import threading
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ClaudeAPIInterceptor:
    """
    Claude API通信を傍受してCross構造に記録

    フロー:
    Claude Code → mitmproxy → responses.jsonl
                                    ↓
                          このクラスが監視
                                    ↓
                            Cross構造に変換
                                    ↓
                  conversation.cross.json + UI通知
    """

    def __init__(
        self,
        responses_file: str = "/tmp/claude_responses.jsonl",
        cross_output: Optional[Path] = None,
        on_message: Optional[Callable[[dict], None]] = None
    ):
        """
        Args:
            responses_file: mitmproxyが書き込むファイル
            cross_output: Cross構造の出力先
            on_message: 新しいメッセージ検出時のコールバック
        """
        self.responses_file = Path(responses_file)
        self.cross_output = cross_output
        self.on_message = on_message

        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_position = 0

        # Cross構造の初期化
        self.cross_structure = {
            "version": "1.0",
            "type": "conversation",
            "created_at": datetime.now().isoformat(),
            "axes": {
                "FRONT": {
                    "current_conversation": [],
                    "active_session": True
                },
                "UP": {
                    "user_inputs": [],
                    "total_messages": 0
                },
                "DOWN": {
                    "claude_responses": [],
                    "total_tokens": 0
                },
                "RIGHT": {
                    "api_metadata": [],
                    "request_count": 0
                },
                "LEFT": {
                    "timestamps": [],
                    "session_duration": 0
                },
                "BACK": {
                    "raw_api_data": []
                }
            }
        }

    def start(self):
        """監視開始"""
        if self._running:
            logger.warning("Interceptor already running")
            return

        # responses_fileが存在しない場合は作成
        if not self.responses_file.exists():
            self.responses_file.touch()
            logger.info(f"Created responses file: {self.responses_file}")

        # 現在のファイル位置を記録
        self._last_position = self.responses_file.stat().st_size

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info(f"Started monitoring: {self.responses_file}")

    def stop(self):
        """監視停止"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)

        # Cross構造を保存
        if self.cross_output:
            self._save_cross_structure()

        logger.info("Stopped interceptor")

    def _monitor_loop(self):
        """ファイル監視ループ"""
        while self._running:
            try:
                current_size = self.responses_file.stat().st_size

                if current_size > self._last_position:
                    # 新しいデータがある
                    with open(self.responses_file, 'r', encoding='utf-8') as f:
                        f.seek(self._last_position)

                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    api_data = json.loads(line)
                                    self._process_api_response(api_data)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse JSON: {e}")

                        self._last_position = f.tell()

                elif current_size < self._last_position:
                    # ファイルが切り詰められた
                    logger.info("Responses file was truncated")
                    self._last_position = 0

                time.sleep(0.1)  # 0.1秒間隔で監視

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(1.0)

    def _process_api_response(self, api_data: Dict[str, Any]):
        """API応答を処理してCross構造に追加"""
        try:
            logger.info(f"Processing API response from {api_data.get('url', 'unknown')}")

            # リクエストとレスポンスを抽出
            request_body = api_data.get('request', '')
            response_body = api_data.get('response', '')

            # JSONとしてパース
            try:
                request_json = json.loads(request_body) if request_body else {}
                response_json = json.loads(response_body) if response_body else {}
            except:
                request_json = {}
                response_json = {}

            # ユーザー入力を抽出（requestから）
            user_message = self._extract_user_message(request_json)

            # Claude応答を抽出（responseから）
            assistant_message = self._extract_assistant_message(response_json)

            # Cross構造に追加
            if user_message:
                self._add_to_cross_structure('user', user_message, api_data)

            if assistant_message:
                self._add_to_cross_structure('assistant', assistant_message, api_data)

            # UIに通知
            if self.on_message:
                if user_message:
                    self.on_message({
                        'type': 'user',
                        'content': user_message,
                        'timestamp': api_data.get('timestamp'),
                        'raw': api_data
                    })

                if assistant_message:
                    self.on_message({
                        'type': 'assistant',
                        'content': assistant_message,
                        'timestamp': api_data.get('timestamp'),
                        'raw': api_data
                    })

            # Cross構造を保存
            if self.cross_output:
                self._save_cross_structure()

        except Exception as e:
            logger.error(f"Error processing API response: {e}")

    def _extract_user_message(self, request_json: dict) -> Optional[str]:
        """リクエストからユーザーメッセージを抽出"""
        # Claude APIの一般的な構造
        # {"messages": [{"role": "user", "content": "..."}]}

        messages = request_json.get('messages', [])
        for msg in reversed(messages):  # 最新のメッセージから
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # マルチモーダルの場合
                    text_parts = [c.get('text', '') for c in content if c.get('type') == 'text']
                    return ' '.join(text_parts)

        return None

    def _extract_assistant_message(self, response_json: dict) -> Optional[str]:
        """レスポンスからClaude応答を抽出"""
        # Claude APIのレスポンス構造
        # Streaming: {"type": "content_block_delta", "delta": {"text": "..."}}
        # Non-streaming: {"content": [{"text": "..."}]}

        # Non-streamingの場合
        content = response_json.get('content', [])
        if content:
            text_parts = []
            for block in content:
                if block.get('type') == 'text':
                    text_parts.append(block.get('text', ''))
            if text_parts:
                return ''.join(text_parts)

        # Streamingの場合（delta）
        delta = response_json.get('delta', {})
        if delta.get('text'):
            return delta['text']

        # message内にある場合
        message = response_json.get('message', {})
        if message:
            return self._extract_assistant_message(message)

        return None

    def _add_to_cross_structure(self, role: str, content: str, api_data: dict):
        """Cross構造にメッセージを追加"""
        timestamp = api_data.get('timestamp', time.time())

        # FRONT軸: 現在の会話
        self.cross_structure['axes']['FRONT']['current_conversation'].append({
            'role': role,
            'content': content,
            'timestamp': timestamp
        })

        # UP軸: ユーザー入力
        if role == 'user':
            self.cross_structure['axes']['UP']['user_inputs'].append({
                'content': content,
                'timestamp': timestamp
            })
            self.cross_structure['axes']['UP']['total_messages'] += 1

        # DOWN軸: Claude応答
        if role == 'assistant':
            self.cross_structure['axes']['DOWN']['claude_responses'].append({
                'content': content,
                'timestamp': timestamp
            })

        # RIGHT軸: APIメタデータ
        self.cross_structure['axes']['RIGHT']['api_metadata'].append({
            'url': api_data.get('url'),
            'method': api_data.get('method'),
            'timestamp': timestamp
        })
        self.cross_structure['axes']['RIGHT']['request_count'] += 1

        # LEFT軸: タイムスタンプ
        self.cross_structure['axes']['LEFT']['timestamps'].append(timestamp)

        # BACK軸: 生のAPIデータ
        self.cross_structure['axes']['BACK']['raw_api_data'].append(api_data)

    def _save_cross_structure(self):
        """Cross構造をファイルに保存"""
        if not self.cross_output:
            return

        try:
            self.cross_output.parent.mkdir(parents=True, exist_ok=True)

            with open(self.cross_output, 'w', encoding='utf-8') as f:
                json.dump(self.cross_structure, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved Cross structure: {self.cross_output}")

        except Exception as e:
            logger.error(f"Failed to save Cross structure: {e}")


def test_interceptor():
    """テスト用"""
    print("🎯 Claude API Interceptor Test")
    print()

    def on_msg(msg: dict):
        print(f"[{msg['type'].upper()}] {msg['content'][:100]}")

    cross_file = Path("/tmp/test_conversation.cross.json")

    interceptor = ClaudeAPIInterceptor(
        responses_file="/tmp/claude_responses.jsonl",
        cross_output=cross_file,
        on_message=on_msg
    )

    try:
        interceptor.start()
        print("✅ Interceptor started")
        print(f"   Monitoring: /tmp/claude_responses.jsonl")
        print(f"   Cross output: {cross_file}")
        print()
        print("📌 セットアップ手順:")
        print("   1. 別ターミナルでmitmproxy起動:")
        print("      mitmproxy -s /tmp/claude_mitm.py -p 8080")
        print()
        print("   2. Claude Codeをプロキシ経由で起動:")
        print("      HTTPS_PROXY=http://localhost:8080 claude")
        print()
        print("   3. Claude Codeで会話する")
        print()
        print("Press Ctrl+C to stop")
        print()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping...")
        interceptor.stop()
        print(f"✅ Cross structure saved: {cross_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_interceptor()
