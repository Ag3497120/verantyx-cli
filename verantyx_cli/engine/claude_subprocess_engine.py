#!/usr/bin/env python3
"""
Claude Subprocess Engine - Claude Codeをサブプロセスとして完全制御

アーキテクチャ:
1. Claude Codeをsubprocessで起動（PTY経由）
2. 標準入出力を完全にキャプチャ
3. JCross動的プロンプト生成機能
4. Cross構造への自動記録
5. ユーザーにはVerantyx CLIとして見せる

目的:
- Claude Codeのエージェント機能をそのまま活用
- Cross構造で個人ごとに進化する記憶
- 使用感を損なわない設計
"""

import os
import sys
import pty
import select
import subprocess
import threading
import time
import re
import json
import logging
import termios
import tty
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from queue import Queue

logger = logging.getLogger(__name__)


class ClaudeSubprocessEngine:
    """
    Claude Codeをサブプロセスとして制御するエンジン

    Features:
    - PTYベースの双方向通信
    - リアルタイム出力パース
    - Cross構造への記憶書き込み
    - JCross動的プロンプト生成
    """

    def __init__(
        self,
        project_path: Path,
        cross_file: Path,
        on_output: Optional[Callable[[str], None]] = None,
        on_claude_response: Optional[Callable[[str], None]] = None
    ):
        """
        Args:
            project_path: プロジェクトディレクトリ
            cross_file: Cross構造ファイル
            on_output: 生出力のコールバック
            on_claude_response: Claude応答のコールバック
        """
        self.project_path = project_path
        self.cross_file = cross_file
        self.on_output = on_output
        self.on_claude_response = on_claude_response

        # PTY
        self.master_fd: Optional[int] = None
        self.claude_pid: Optional[int] = None

        # 状態管理
        self.running = False
        self.ready = False
        self.waiting_for_input = False  # Claude が入力待ち状態か
        self.processing_response = False  # 応答処理中か
        self.auto_respond_enabled = False  # 自動応答が有効か（ユーザートリガー）

        # 出力バッファ
        self.output_buffer = ""
        self.current_response = ""
        self.last_output_time = time.time()
        self.pending_choice = None  # 保留中の選択肢

        # Cross構造
        self.cross_memory = self._load_cross_memory()

        # 出力パーサースレッド
        self.parser_thread: Optional[threading.Thread] = None

    def _load_cross_memory(self) -> dict:
        """Cross記憶を読み込む"""
        # 初期構造のテンプレート
        initial_structure = {
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
                    "tool_calls": [],
                    "actions_taken": []
                },
                "LEFT": {
                    "timestamps": [],
                    "session_duration": 0
                },
                "BACK": {
                    "raw_interactions": [],
                    "jcross_prompts": []
                }
            }
        }

        if self.cross_file.exists():
            try:
                with open(self.cross_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 構造を検証（必要なキーがあるか）
                if 'axes' in data:
                    # 各軸が存在するか確認し、なければ追加
                    for axis_name, axis_data in initial_structure['axes'].items():
                        if axis_name not in data['axes']:
                            logger.warning(f"Missing axis {axis_name}, adding...")
                            data['axes'][axis_name] = axis_data

                    return data
                else:
                    logger.warning("Invalid Cross structure, creating new one")
                    return initial_structure

            except Exception as e:
                logger.error(f"Failed to load Cross memory: {e}")
                return initial_structure

        # 新規作成
        return initial_structure

    def _save_cross_memory(self):
        """Cross記憶を保存"""
        try:
            self.cross_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cross_file, 'w', encoding='utf-8') as f:
                json.dump(self.cross_memory, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved Cross memory: {self.cross_file}")
        except Exception as e:
            logger.error(f"Failed to save Cross memory: {e}")

    def start(self) -> bool:
        """Claude Codeを起動"""
        try:
            logger.info("Starting Claude Code subprocess...")

            # 作業ディレクトリに移動
            os.chdir(self.project_path)

            # PTYでClaudeを起動
            self.claude_pid, self.master_fd = pty.fork()

            if self.claude_pid == 0:
                # 子プロセス - Claude実行
                os.environ['TERM'] = 'xterm-256color'
                os.environ['COLUMNS'] = '120'
                os.environ['LINES'] = '40'

                os.execvp("claude", ["claude"])
                # ここには到達しない

            else:
                # 親プロセス - I/O監視
                logger.info(f"Claude started (PID: {self.claude_pid})")

                # PTYの設定を調整（raw mode）
                try:
                    # 現在の設定を取得
                    old_settings = termios.tcgetattr(self.master_fd)
                    new_settings = termios.tcgetattr(self.master_fd)

                    # Raw modeに設定（エコーバックなし、行バッファリングなし）
                    new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON)
                    termios.tcsetattr(self.master_fd, termios.TCSANOW, new_settings)

                    logger.info("PTY configured to raw mode")
                except Exception as e:
                    logger.warning(f"Could not configure PTY: {e}")

                # 起動確認
                time.sleep(1.0)
                try:
                    os.kill(self.claude_pid, 0)
                    logger.info("Claude process confirmed running")
                except OSError:
                    logger.error("Claude process died immediately")
                    return False

                self.running = True

                # 出力パーサー開始
                self.parser_thread = threading.Thread(
                    target=self._output_parser_loop,
                    daemon=True
                )
                self.parser_thread.start()

                # Claude が入力待ち状態になるまで待機
                logger.info("Waiting for Claude to be ready for input...")
                max_wait = 10  # 最大10秒
                for i in range(max_wait * 10):
                    if self.waiting_for_input:
                        logger.info("Claude is ready for input")
                        break
                    time.sleep(0.1)

                self.ready = True
                return True

        except Exception as e:
            logger.error(f"Failed to start Claude: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _output_parser_loop(self):
        """出力パーサーループ（専用スレッド）"""
        logger.info("Output parser started")

        while self.running:
            try:
                # 出力待機
                readable, _, _ = select.select([self.master_fd], [], [], 0.1)

                if self.master_fd in readable:
                    try:
                        data = os.read(self.master_fd, 4096)

                        if data:
                            # デコード
                            text = data.decode('utf-8', errors='replace')

                            # デバッグ: 受信データをログ
                            logger.debug(f"Received {len(data)} bytes from Claude")

                            # 最後の出力時刻を更新
                            self.last_output_time = time.time()

                            # 応答処理中フラグ
                            if not self.processing_response and not self.waiting_for_input:
                                self.processing_response = True
                                logger.debug("Started processing Claude response")

                            # 生出力コールバック
                            if self.on_output:
                                self.on_output(text)

                            # バッファに追加
                            self.output_buffer += text

                            # Claude応答を抽出
                            self._parse_claude_response(text)

                        else:
                            # Claude終了
                            logger.info("Claude closed")
                            self.running = False
                            break

                    except OSError as e:
                        logger.error(f"Error reading from Claude: {e}")
                        break

            except Exception as e:
                logger.error(f"Error in parser loop: {e}")
                time.sleep(1.0)

    def _parse_claude_response(self, text: str):
        """Claude応答をパース"""
        # ANSIエスケープシーケンスを除去
        clean_text = self._strip_ansi(text)

        # Claude の選択肢プロンプトを検出
        # 例: "❯ 1. Yes" や "Do you want to proceed?"
        if self.auto_respond_enabled and self.pending_choice is None:
            if "Do you want to proceed?" in clean_text or \
               "❯" in clean_text and ("Yes" in clean_text or "Allow" in clean_text):
                # 選択肢を検出
                logger.info("Detected choice prompt, will auto-respond")
                self.pending_choice = "detected"

                # 少し待ってから "1" (Yes) を送信
                time.sleep(0.5)
                try:
                    os.write(self.master_fd, b'1')  # "1" を選択
                    time.sleep(0.1)
                    os.write(self.master_fd, b'\x0d')  # Enter
                    logger.info("Auto-responded with '1' (Yes)")
                    self.pending_choice = "responded"
                except Exception as e:
                    logger.error(f"Auto-response failed: {e}")
                    self.pending_choice = None

        # Claude が入力待ち状態かチェック
        # プロンプト行を検出（例: "────> " や ">" で終わる行）
        lines = clean_text.split('\n')
        for line in lines:
            stripped = line.strip()
            # 入力待ちプロンプトを検出
            if (stripped.endswith('>') and len(stripped) < 100) or \
               ('──>' in stripped) or \
               ('Try "' in stripped and '..."' in stripped):
                self.waiting_for_input = True
                logger.debug("Detected Claude waiting for input")
                # 選択肢応答後はリセット
                if self.pending_choice == "responded":
                    self.pending_choice = None
                break

        # 応答バッファに追加
        self.current_response += clean_text

        # 応答完了の検出
        # Claude が新しい入力を待っている状態になったら応答完了
        if self.waiting_for_input and self.current_response.strip():
            # 初回の起動メッセージは無視
            if "Welcome back!" not in self.current_response and \
               "Tips for getting started" not in self.current_response:
                # コールバック
                if self.on_claude_response:
                    self.on_claude_response(self.current_response)

                # Cross構造に記録
                self._record_to_cross('assistant', self.current_response)

            # リセット
            self.current_response = ""

    def _strip_ansi(self, text: str) -> str:
        """ANSIエスケープシーケンスを除去"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def enable_auto_respond(self):
        """自動応答を有効化（ユーザートリガー）"""
        self.auto_respond_enabled = True
        self.pending_choice = None
        logger.info("Auto-respond enabled")

    def disable_auto_respond(self):
        """自動応答を無効化"""
        self.auto_respond_enabled = False
        self.pending_choice = None
        logger.info("Auto-respond disabled")

    def send_prompt(self, prompt: str, use_jcross: bool = True, auto_respond: bool = False) -> bool:
        """
        プロンプトをClaudeに送信

        Args:
            prompt: ユーザープロンプト
            use_jcross: JCross動的生成を使用するか
            auto_respond: 自動応答を有効にするか（ユーザートリガー）

        Returns:
            成功したかどうか
        """
        if not self.ready:
            logger.warning("Claude not ready yet")
            return False

        # 自動応答の有効/無効を設定
        if auto_respond:
            self.enable_auto_respond()
        else:
            # プロンプトにトリガーワードがあるかチェック
            trigger_words = ['auto', 'yes', 'allow', '自動', '許可', 'はい']
            if any(word in prompt.lower() for word in trigger_words):
                logger.info("Auto-respond trigger detected in prompt")
                self.enable_auto_respond()

        # Claude が入力待ち状態になるまで待機
        max_wait = 5  # 最大5秒
        for i in range(max_wait * 10):
            if self.waiting_for_input:
                break
            time.sleep(0.1)

        if not self.waiting_for_input:
            logger.warning("Claude not waiting for input, sending anyway...")

        try:
            # JCross動的プロンプト生成
            if use_jcross:
                final_prompt = self._generate_jcross_prompt(prompt)
            else:
                final_prompt = prompt

            # Cross構造に記録
            self._record_to_cross('user', prompt, jcross_prompt=final_prompt if use_jcross else None)

            # 入力待ち状態をリセット
            self.waiting_for_input = False
            self.processing_response = False  # リセット

            # Claudeに送信
            encoded = final_prompt.encode('utf-8')
            logger.info(f"Sending to Claude: {final_prompt[:200]}")

            # プロンプトを送信
            written = os.write(self.master_fd, encoded)
            logger.info(f"Wrote {written} bytes")

            time.sleep(0.1)

            # Enterキー送信 - Ctrl+Mと同じ
            os.write(self.master_fd, b'\x0d')  # Ctrl+M (Enter)
            logger.info("Sent Enter key (Ctrl+M)")

            time.sleep(0.1)

            logger.info(f"Prompt sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send prompt: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _generate_jcross_prompt(self, user_prompt: str) -> str:
        """
        JCross動的プロンプト生成

        Cross記憶から関連情報を抽出して、プロンプトを拡張
        """
        try:
            # 安全に軸データを取得
            axes = self.cross_memory.get('axes', {})

            # 関連する過去の会話を取得
            front_axis = axes.get('FRONT', {})
            past_conversations = front_axis.get('current_conversation', [])
            recent_context = past_conversations[-5:] if len(past_conversations) > 5 else past_conversations

            # ツール使用履歴
            right_axis = axes.get('RIGHT', {})
            tool_history = right_axis.get('tool_calls', [])
            recent_tools = tool_history[-3:] if len(tool_history) > 3 else tool_history

            # JCross拡張プロンプト生成
            jcross_additions = []

            if recent_context:
                jcross_additions.append("[Context from Cross Memory]")
                for msg in recent_context:
                    role = msg.get('role', 'unknown')
                    content_preview = msg.get('content', '')[:50]
                    jcross_additions.append(f"- {role}: {content_preview}...")

            if recent_tools:
                jcross_additions.append("\n[Recent Actions]")
                for tool in recent_tools:
                    jcross_additions.append(f"- {tool.get('name', 'unknown')}")

            # 最終プロンプト
            if jcross_additions:
                context_block = "\n".join(jcross_additions)
                final_prompt = f"{user_prompt}\n\n<!-- Cross Context:\n{context_block}\n-->"
            else:
                final_prompt = user_prompt

            return final_prompt

        except Exception as e:
            logger.error(f"Error in JCross generation: {e}")
            # エラー時は元のプロンプトをそのまま返す
            return user_prompt

    def _record_to_cross(self, role: str, content: str, jcross_prompt: Optional[str] = None):
        """Cross構造に記録"""
        try:
            timestamp = time.time()

            # 安全に軸データを取得
            axes = self.cross_memory.get('axes', {})

            # FRONT軸: 会話履歴
            if 'FRONT' in axes:
                axes['FRONT']['current_conversation'].append({
                    'role': role,
                    'content': content,
                    'timestamp': timestamp
                })

            # UP軸: ユーザー入力
            if role == 'user' and 'UP' in axes:
                axes['UP']['user_inputs'].append({
                    'content': content,
                    'timestamp': timestamp
                })
                axes['UP']['total_messages'] += 1

            # DOWN軸: Claude応答
            if role == 'assistant' and 'DOWN' in axes:
                axes['DOWN']['claude_responses'].append({
                    'content': content,
                    'timestamp': timestamp
                })

            # LEFT軸: タイムスタンプ
            if 'LEFT' in axes:
                axes['LEFT']['timestamps'].append(timestamp)

            # BACK軸: JCrossプロンプト
            if jcross_prompt and 'BACK' in axes:
                axes['BACK']['jcross_prompts'].append({
                    'original': content,
                    'jcross_enhanced': jcross_prompt,
                    'timestamp': timestamp
                })

            # 保存
            self._save_cross_memory()

        except Exception as e:
            logger.error(f"Error recording to Cross: {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        """停止"""
        logger.info("Stopping Claude subprocess...")
        self.running = False

        if self.parser_thread:
            self.parser_thread.join(timeout=2.0)

        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass

        if self.claude_pid:
            try:
                import signal
                os.kill(self.claude_pid, signal.SIGTERM)
                time.sleep(0.5)
            except:
                pass

        # 最終保存
        self._save_cross_memory()

        logger.info("Claude subprocess stopped")

    def is_ready(self) -> bool:
        """準備完了しているか"""
        return self.ready and self.running


def test_subprocess_engine():
    """テスト用"""
    print("🧪 Claude Subprocess Engine Test")
    print()

    project_path = Path.cwd()
    cross_file = project_path / '.verantyx' / 'conversation.cross.json'

    def on_output(text: str):
        print(text, end='', flush=True)

    def on_response(text: str):
        print(f"\n[📝 Response captured: {len(text)} chars]")

    engine = ClaudeSubprocessEngine(
        project_path=project_path,
        cross_file=cross_file,
        on_output=on_output,
        on_claude_response=on_response
    )

    try:
        if not engine.start():
            print("❌ Failed to start engine")
            return

        print("✅ Engine started")
        print()

        # 待機
        time.sleep(3)

        # テストプロンプト
        print("\n📤 Sending test prompt...")
        engine.send_prompt("Hello! What's your name?")

        print("\n⏳ Waiting for response...")
        time.sleep(10)

        print("\n📤 Sending another prompt...")
        engine.send_prompt("What can you help me with?")

        time.sleep(10)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted")

    finally:
        engine.stop()
        print(f"✅ Cross memory saved: {cross_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_subprocess_engine()
