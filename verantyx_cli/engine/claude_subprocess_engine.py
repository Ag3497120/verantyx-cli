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

        # シンプル方式: PTYのみ + パズル推論
        #
        # - PTY: リアルタイム出力、ユーザー体験
        # - パズル推論: Cross シミュレータによる穴埋め式の文章組み立て
        # - 応答完了検出: パズル推論のスコアが閾値を超えたら完成
        # - データ保存: 完成検出時にCross構造に保存
        print(f"[DEBUG INIT] Simple mode: PTY + Puzzle reasoning only")

        # Cross構造
        self.cross_memory = self._load_cross_memory()

        # Cross会話記録（JCrossベース） - インスタンスを保持
        # .jcrossストレージエンジンを使用
        from .jcross_storage_processors import JCrossStorageEngine
        # .jcross拡張子に変更
        jcross_file = Path(str(cross_file).replace('.json', '.jcross'))
        self.cross_logger = JCrossStorageEngine(jcross_file)

        # コンテキスト分離
        from .context_separator import ConversationContext
        self.context_separator = ConversationContext()
        self.last_user_input = None  # 前回のユーザー入力

        # 推論抽出パイプライン（新規）
        from .reasoning_operator_extractor import ReasoningOperatorExtractor
        from .reasoning_to_jcross import ReasoningToJCrossConverter
        self.reasoning_extractor = ReasoningOperatorExtractor()
        self.reasoning_converter = ReasoningToJCrossConverter()

        # Cross空間位置管理（新規）
        from .cross_space_manager import CrossSpaceManager
        space_file = Path(str(self.cross_file).replace('.jcross', '.space.jcross'))
        self.cross_space = CrossSpaceManager(space_file)

        # 応答完成予測器（Cross構造ベース）
        # .jcrossベースのパズル推論を使用
        from .response_completion_processors import ResponseCompletionDetector
        # Cross構造ベースのパズル推論器
        self.completion_predictor = ResponseCompletionDetector()

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
        """
        Cross記憶を保存

        【重要】この関数は無効化されています。
        JCrossStorageEngineが自動的に.jcrossファイルに保存するため、
        ここで古い.json形式で上書きしないようにします。
        """
        # 無効化: JCrossStorageEngineが.jcrossファイルに自動保存するため不要
        # 古い.jsonファイルへの保存を防止
        pass

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
                            # 【ハイブリッド方式】Enterキー検出は不要
                            # - 保存: API傍受が担当（正確、重複なし）
                            # - UI: PTYが担当（リアルタイム表示）

                            # デコード
                            text = data.decode('utf-8', errors='replace')

                            # デバッグ: 受信データをログ
                            logger.debug(f"Received {len(data)} bytes from Claude")
                            print(f"[PTY] Received {len(data)} bytes", flush=True)

                            # 最後の出力時刻を更新
                            self.last_output_time = time.time()

                            # 応答処理中フラグ
                            if not self.processing_response and not self.waiting_for_input:
                                self.processing_response = True
                                logger.debug("Started processing Claude response")
                                print(f"[PTY] Started processing response", flush=True)

                            # 生出力コールバック
                            if self.on_output:
                                self.on_output(text)

                            # バッファに追加
                            self.output_buffer += text

                            # Claude応答を抽出（チャンク蓄積のみ）
                            self._parse_claude_response(text)

                        else:
                            # Claude終了
                            logger.info("Claude closed")
                            self.running = False
                            break

                    except OSError as e:
                        logger.error(f"Error reading from Claude: {e}")
                        break

                # タイムアウトチェック: 出力が途絶えたら保存
                self._check_response_timeout()

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

        # 【旧方式 - 廃止】'>' プロンプト検出による保存
        # 新方式: Enterキー検出に統一
        #
        # 理由:
        # - '>' は複数の文脈で出現（応答内、学習モードメッセージ、実際のプロンプト）
        # - 検出が不安定で重複が発生しやすい
        # - Enterキーの方が明確で確実

        # 応答バッファに追加
        self.current_response += clean_text

        # チャンクを受信したら時刻を更新
        if clean_text.strip():
            self.last_chunk_time = time.time()

        # 【ハイブリッド方式】パズル推論による応答完了検出
        #
        # 役割: UI表示のみ（🗣️ You: プロンプトを即座に表示）
        # 保存: API傍受に任せる（正確な境界検出、重複なし）
        if clean_text.strip():
            # チャンクを予測器に追加
            prediction = self.completion_predictor.add_chunk(clean_text)

            # デバッグ: 予測スコアを表示
            print(f"[PUZZLE] score={prediction['completion_score']:.2%} complete={prediction['is_complete']} waiting={self.waiting_for_next_enter}")

            logger.debug(f"Response prediction | completion={prediction['completion_score']:.2%} | missing={prediction['missing_pieces']}")

            # 完成判定（パズル推論）- UI表示 + データ保存
            if prediction['is_complete'] and not self.waiting_for_next_enter:
                logger.info(f"[PUZZLE] Response complete | score={prediction['completion_score']:.2%}")
                print(f"\n[PUZZLE] Response COMPLETE detected!")

                # 組み立て済みの応答を取得
                assembled = self.completion_predictor.current_assembly.get('chunks', [])
                full_text = ''.join(assembled)

                print(f"[PUZZLE] Assembled text: {len(full_text)} chars")

                # Cross構造に保存
                if len(full_text.strip()) >= 20:
                    # 起動メッセージは無視
                    if "Welcome back!" not in full_text and "Tips for getting started" not in full_text:
                        logger.info(f"[PUZZLE] Saving to Cross structure: {len(full_text)} chars")

                        # コールバック
                        if self.on_claude_response:
                            self.on_claude_response(full_text)

                        # Cross構造に記録
                        stats = self._record_to_cross('assistant', full_text)

                        # 💾 保存案内を表示
                        if stats:
                            print(f"\n💾 Cross Memory: {stats['total_inputs']} inputs, {stats['total_responses']} responses")

                # フラグをセット（UI層で待機ループを解除）
                self.waiting_for_next_enter = True
                self.waiting_for_input = True  # verantyx_chat_mode.py が待機しているフラグ
                print(f"[PUZZLE] Set waiting_for_input=True")

                # 予測器をリセット
                self.completion_predictor.reset()

                # 🗣️ You: プロンプトを即座に表示（ユーザー体験向上）
                print(f"\n🗣️  You: ", end='', flush=True)

    def _strip_ansi(self, text: str) -> str:
        """ANSIエスケープシーケンスを除去"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _clean_response_text(self, text: str) -> str:
        """
        応答テキストから制御文字と装飾文字を除去

        除去対象:
        - \\r\\n などの制御文字
        - ─ ✳ ⏺ などのターミナル装飾文字
        - 重複する空白
        - Claude Code UIの装飾テキスト
        """
        # Remove \r\n line breaks
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '')

        # Remove terminal decoration characters
        decorations = ['─', '✳', '✻', '✽', '✶', '✢', '⏺', '·', '⎿', '╭', '╰', '│', '├', '└', '┌', '┐', '┘', '━', '┃', '┏', '┓', '┗', '┛']
        for char in decorations:
            text = text.replace(char, '')

        # Remove "... (esc to interrupt)" patterns
        text = re.sub(r'…?\s*\(esc to interrupt\)', '', text)
        text = re.sub(r'Tip:.*?Press.*?to enable\.', '', text, flags=re.DOTALL)

        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    # 【ハイブリッド方式】旧保存メソッドは削除
    # - Enterキー検出: 不要（API傍受で保存）
    # - プロンプト検出: 不要（API傍受で保存）
    # - PTYは UI表示のみに専念

    # 【ハイブリッド方式】旧タイムアウトチェックは削除
    # API傍受が保存を担当するため不要

        # 既に保存済みならスキップ
        if self.response_saved:
            return

        # 最後のチャンクからの経過時間
        elapsed = time.time() - self.last_chunk_time

        # タイムアウト判定
        if elapsed >= self.response_timeout_seconds:
            # 組み立て済みの応答を取得
            assembled = self.completion_predictor.current_assembly.get('chunks', [])
            if assembled:
                full_text = ''.join(assembled)

                # 十分な長さがあるか（50文字以上）
                if len(full_text.strip()) >= 50:
                    logger.info(f"Response COMPLETE (timeout: {elapsed:.1f}s) | length={len(full_text)}")

                    # 初回の起動メッセージは無視
                    if "Welcome back!" not in full_text and \
                       "Tips for getting started" not in full_text:

                        # 重複記録防止: フラグをセット
                        # self.response_saved = True  # 無効化
                        self.processing_response = False

                        # コールバック
                        if self.on_claude_response:
                            self.on_claude_response(full_text)

                        # Cross構造に記録（1回のみ）
                        logger.info(f"Recording response to Cross (timeout trigger) | length={len(full_text)}")
                        stats = self._record_to_cross('assistant', full_text)

                        # 💾 保存案内を表示（統計情報付き）
                        if stats:
                            print(f"\n💾 Cross Memory: {stats['total_inputs']} inputs, {stats['total_responses']} responses")
                        else:
                            print(f"\n💾 Saved to Cross Memory")

                    # 予測器をリセット
                    self.completion_predictor.reset()

                    # リセット
                    self.current_response = ""
                    self.waiting_for_input = False

                    # タイマーリセット
                    self.last_chunk_time = time.time()

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

    def send_prompt(self, prompt: str, use_jcross: bool = True, auto_respond: bool = False, use_cross_optimization: bool = True) -> bool:
        """
        プロンプトをClaudeに送信

        Args:
            prompt: ユーザープロンプト
            use_jcross: JCross動的生成を使用するか
            auto_respond: 自動応答を有効にするか（ユーザートリガー）
            use_cross_optimization: Cross構造最適化プレプロンプトを使用するか

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
            trigger_words = ['auto', 'yes', 'allow', 'high', '自動', '許可', 'はい']
            if any(word in prompt.lower() for word in trigger_words):
                logger.info(f"Auto-respond trigger detected in prompt: {prompt[:100]}")
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
            # コンテキスト分離を適用
            from .context_separator import enhance_message_with_context

            context_enhanced_prompt, context_metadata = enhance_message_with_context(
                prompt,
                self.context_separator,
                self.last_user_input
            )

            # 【デバッグ】一時的に全ての拡張を無効化
            # Cross最適化とJCrossを無効化してシンプルなプロンプトのみ送信
            enhanced_prompt = context_enhanced_prompt
            final_prompt = prompt  # 元のユーザープロンプトをそのまま使用

            print(f"[DEBUG] Simplified prompt: {final_prompt[:100]}")

            # # Cross構造最適化プレプロンプトを追加（透明、ユーザーには見えない）
            # if use_cross_optimization:
            #     from .cross_optimized_prompt import generate_cross_optimized_preprompt, should_inject_preprompt
            #
            #     if should_inject_preprompt(prompt):
            #         cross_preprompt = generate_cross_optimized_preprompt(prompt)
            #         # プレプロンプト + コンテキスト情報 + ユーザーメッセージ
            #         enhanced_prompt = cross_preprompt + context_enhanced_prompt
            #         logger.info(f"Cross-optimized preprompt injected | Context: {context_metadata.get('topic', 'N/A')}")
            #     else:
            #         enhanced_prompt = context_enhanced_prompt
            # else:
            #     enhanced_prompt = context_enhanced_prompt
            #
            # # JCross動的プロンプト生成
            # if use_jcross:
            #     final_prompt = self._generate_jcross_prompt(enhanced_prompt)
            # else:
            #     final_prompt = enhanced_prompt

            # Cross構造に記録（元のユーザープロンプト + コンテキストメタデータ）
            self._record_to_cross(
                'user',
                prompt,
                jcross_prompt=final_prompt if use_jcross else None,
                context_metadata=context_metadata
            )

            # 最後のユーザー入力を保存
            self.last_user_input = prompt

            # 入力待ち状態をリセット
            print(f"[DEBUG] Resetting waiting_for_input=False (new prompt sent)")
            self.waiting_for_input = False
            self.processing_response = False  # リセット
            self.waiting_for_next_enter = False  # 次の応答完了を待つ

            # 応答完成予測器をリセット
            self.completion_predictor.reset()

            # タイムアウトタイマーをリセット
            self.last_chunk_time = time.time()

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

    def _record_to_cross(self, role: str, content: str, jcross_prompt: Optional[str] = None, context_metadata: Dict[str, Any] = None):
        """
        Cross構造に記録（JCrossベース）

        JCross conversation_logger.jcrossを使用してCross構造に記録

        Args:
            role: 'user' or 'assistant'
            content: メッセージ内容
            jcross_prompt: JCross拡張プロンプト（オプション）
            context_metadata: コンテキストメタデータ（トピック、キーワードなど）
        """
        try:
            # Cross構造の健全性チェック
            if not hasattr(self.cross_logger, 'memory') or not self.cross_logger.memory:
                logger.error("Cross structure not initialized, re-initializing...")
                from .jcross_storage_processors import JCrossStorageEngine
                from pathlib import Path
                jcross_file = Path(str(self.cross_file).replace('.json', '.jcross'))
                self.cross_logger = JCrossStorageEngine(jcross_file)

            # インスタンスを再利用（FIX: 毎回作成しない）
            # self.cross_loggerは__init__で作成済み

            # コンテキストメタデータをメッセージに付与
            if context_metadata and role == 'user':
                # メタデータを特殊形式で保存（学習時に活用）
                context_marker = f"[CTX:{context_metadata.get('context_id', 'unknown')}|TOPIC:{context_metadata.get('topic', 'unknown')}]"
                enhanced_content = f"{context_marker} {content}"
            else:
                enhanced_content = content

            # ロールに応じて記録
            if role == 'user':
                # ユーザー入力はそのまま記録
                self.cross_logger.log_user_input(enhanced_content)
                # コンテキスト分離器にも記録
                if context_metadata:
                    self.context_separator.add_message_to_context('user', content, context_metadata.get('context_id'))

            elif role == 'assistant':
                # Claude応答はANSIエスケープシーケンスを除去してから保存
                cleaned_content = self._strip_ansi(content)
                # さらに制御文字(\r\n, \x1B等)も除去
                cleaned_content = self._clean_response_text(cleaned_content)

                self.cross_logger.log_claude_response(cleaned_content)
                # コンテキスト分離器にも記録
                if self.context_separator.current_context_id:
                    self.context_separator.add_message_to_context('assistant', cleaned_content)

                # 【新機能】Claude応答から推論演算子を抽出してJCrossプログラムに変換
                self._extract_and_convert_reasoning(cleaned_content, context_metadata)

            # JCrossプロンプトがある場合は記録
            if jcross_prompt:
                self.cross_logger.log_jcross_prompt(jcross_prompt)

            # 保存
            self.cross_logger.save()
            logger.info(f"Cross structure saved | role={role}")

            # メモリ内のCross構造も更新
            self.cross_memory = self.cross_logger.get_cross_structure()

            # 統計情報を返す（表示用）
            return self.cross_logger.get_statistics()

        except Exception as e:
            logger.error(f"Error recording to Cross: {e}")
            logger.error(f"  Role: {role}")
            logger.error(f"  Content length: {len(content) if content else 0}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_and_convert_reasoning(self, claude_response: str, context_metadata: Optional[Dict] = None):
        """
        Claude応答から推論演算子を抽出してJCrossプログラムに変換

        これが「文章 → 推論プログラム」変換の核心

        Args:
            claude_response: Claudeの応答文
            context_metadata: コンテキストメタデータ
        """
        try:
            # ユーザーの質問を取得
            user_question = self.last_user_input if self.last_user_input else None

            # Step 1: 推論演算子を抽出
            operations = self.reasoning_extractor.extract(claude_response, user_question)

            if not operations:
                logger.debug("No reasoning operators extracted")
                return

            logger.info(f"Extracted {len(operations)} reasoning operators")

            # Step 2: JCrossプログラムに変換
            context = {
                'question': user_question,
                'topic': context_metadata.get('topic') if context_metadata else 'unknown'
            }

            jcross_program = self.reasoning_converter.convert(operations, context)

            # Step 3: Cross構造のBACK軸に保存（推論プログラム）
            # BACK軸 = 生の対話 + 推論プログラム
            self.cross_logger.cross_structure['axes']['BACK']['jcross_programs'] = \
                self.cross_logger.cross_structure['axes']['BACK'].get('jcross_programs', [])

            self.cross_logger.cross_structure['axes']['BACK']['jcross_programs'].append({
                'user_question': user_question,
                'claude_response': claude_response[:200],  # 最初の200文字のみ
                'jcross_program': jcross_program,
                'operations_count': len(operations),
                'timestamp': self.cross_logger._get_timestamp()
            })

            # Step 4: 抽象的推論パターンを生成
            abstract_pattern = self.reasoning_converter.generate_concept_abstraction(operations)

            # FRONT軸 = 概念拡張 + 推論パターン
            self.cross_logger.cross_structure['axes']['FRONT']['reasoning_patterns'] = \
                self.cross_logger.cross_structure['axes']['FRONT'].get('reasoning_patterns', [])

            self.cross_logger.cross_structure['axes']['FRONT']['reasoning_patterns'].append({
                'pattern': abstract_pattern,
                'topic': context.get('topic'),
                'timestamp': self.cross_logger._get_timestamp()
            })

            # Step 5: 【新機能】Cross空間に単語を追加（位置ベース学習）
            context_id = context_metadata.get('context_id') if context_metadata else 'unknown'
            timestamp = self.cross_logger._get_timestamp()

            # コンテキストを作成（初回のみ）
            topic = context_metadata.get('topic') if context_metadata else 'unknown'
            if context_id not in self.cross_space.context_layer:
                self.cross_space.create_context(context_id, topic, [])

            # 各操作から単語を抽出してCross空間に追加
            for operation in operations:
                self.cross_space.add_word_from_operation(operation, context_id, timestamp)

            # Cross空間を保存
            self.cross_space.save()

            logger.info(f"Reasoning extraction successful | Operators: {len(operations)}")
            logger.info(f"Cross space updated | Words: {len(self.cross_space.word_layer)}")

        except Exception as e:
            logger.error(f"Error in reasoning extraction: {e}")
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
