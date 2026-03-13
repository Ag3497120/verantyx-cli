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
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def detect_media_paths(text: str) -> tuple[list[str], list[str]]:
    """
    テキストから画像・動画パスを検出

    Returns:
        (画像パスのリスト, 動画パスのリスト)
    """
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff']
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv']

    detected_images = []
    detected_videos = []

    # 単語で分割してパスを探す
    words = text.split()

    for i, word in enumerate(words):
        # エスケープされたスペースを処理
        # 連続する単語を結合してパスを構築
        path_str = word
        j = i + 1

        # バックスラッシュで終わっている場合、次の単語と結合
        while path_str.endswith('\\') and j < len(words):
            path_str = path_str[:-1] + ' ' + words[j]
            j += 1

        # パスとして検証
        try:
            # チルダ展開
            if path_str.startswith('~'):
                path = Path(path_str).expanduser()
            else:
                path = Path(path_str)

            # 画像・動画ファイルかチェック
            if path.suffix.lower() in image_extensions:
                if path.exists():
                    detected_images.append(str(path.absolute()))
                    print(f"   🔍 検出（画像）: {path.name}")
                    logger.info(f"Detected image path: {path}")
            elif path.suffix.lower() in video_extensions:
                if path.exists():
                    detected_videos.append(str(path.absolute()))
                    print(f"   🔍 検出（動画）: {path.name}")
                    logger.info(f"Detected video path: {path}")
        except Exception as e:
            # パースエラーは無視
            pass

    return detected_images, detected_videos


def process_image_with_vision(image_path: str) -> str:
    """
    Verantyx Vision機能で画像を処理してLLMコンテキストを生成

    Returns:
        LLMが理解できる画像の説明文
    """
    try:
        from ..vision import image_to_llm_context

        print(f"\n🖼️  画像を解析中: {Path(image_path).name}")
        print("   Verantyx Vision (Cross Simulation) で処理...")

        context = image_to_llm_context(Path(image_path))

        print("   ✅ 解析完了\n")
        return context

    except ImportError:
        logger.error("Vision module not available")
        return f"[画像: {image_path}]"
    except Exception as e:
        logger.error(f"Vision processing failed: {e}")
        return f"[画像処理エラー: {image_path}]"


def process_video_with_vision(video_path: str, max_frames: int = 10, use_shape_recognition: bool = True) -> str:
    """
    Verantyx Vision機能で動画を処理してLLMコンテキストを生成

    動画は常に最高品質（maximum）で処理される

    Args:
        video_path: 動画ファイルパス
        max_frames: 解析する最大フレーム数
        use_shape_recognition: JCross形状認識を使用するか

    Returns:
        LLMが理解できる動画の説明文
    """
    try:
        # Cross形状認識を使用
        if use_shape_recognition:
            from ..vision import enhanced_video_to_llm_context

            print(f"\n🎥 動画を解析中: {Path(video_path).name}")
            print(f"   Verantyx Vision (Cross Simulation) で処理...")
            print(f"   品質: MAXIMUM（最高品質）")
            print(f"   🧠 Cross形状認識: 有効（JCross）")
            print(f"   フレームサンプリング: 最大{max_frames}フレーム")

            context = enhanced_video_to_llm_context(
                Path(video_path),
                max_frames=max_frames,
                use_shape_recognition=True
            )

            print("   ✅ 解析完了（形状認識結果を含む）\n")
            return context

        # 基本のVision処理（形状認識なし）
        else:
            from ..vision import video_to_llm_context

            print(f"\n🎥 動画を解析中: {Path(video_path).name}")
            print(f"   Verantyx Vision (Cross Simulation) で処理...")
            print(f"   品質: MAXIMUM（最高品質）")
            print(f"   フレームサンプリング: 最大{max_frames}フレーム")

            context = video_to_llm_context(Path(video_path), max_frames=max_frames)

            print("   ✅ 解析完了\n")
            return context

    except ImportError as e:
        logger.error(f"Video processing not available: {e}")
        return f"[動画処理にはOpenCVが必要です。pip install opencv-python を実行してください: {video_path}]"
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        import traceback
        traceback.print_exc()
        return f"[動画処理エラー: {video_path}]"


def start_verantyx_chat_mode(project_path: Path, show_cross: bool = False, use_vision: bool = False, open_viewer: bool = False):
    """
    Verantyx Chat Mode起動

    Args:
        project_path: プロジェクトディレクトリ
        show_cross: Cross構造の成長を表示するか
        use_vision: Verantyx Vision（Cross Simulation）を使用するか
                    False（デフォルト）の場合、Claude Codeの画像認識に任せる
        open_viewer: Cross構造のリアルタイムビューアーを起動するか
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

    # 背景学習モードの設定チェック
    from ..engine.background_learning_config import BackgroundLearningConfig
    bg_config = BackgroundLearningConfig(config_dir=verantyx_dir)

    # 初回起動時: 背景学習モードの設定を行う
    preferences = bg_config.load_preferences()
    if preferences is None:
        print("🔧 初回起動を検出しました\n")
        preferences = bg_config.setup_user_preferences()

        if preferences.get("enabled", False):
            # ファイル活動分析
            analysis = bg_config.analyze_file_activity(lookback_days=30)

            # デーモン起動の提案
            print("\n背景学習デーモンを起動しますか？")
            print("  デーモンを起動すると、非アクティブ時間帯に自動的に学習を行います。")
            print("  後で手動で起動する場合: ./start_learning_daemon.sh")
            print()

            start_daemon = input("デーモンを起動しますか？ (y/n): ").strip().lower()
            if start_daemon in ["y", "yes"]:
                import subprocess
                try:
                    subprocess.Popen(
                        ["./start_learning_daemon.sh"],
                        cwd=str(project_path),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    print("✅ 背景学習デーモンを起動しました\n")
                except Exception as e:
                    print(f"⚠️  デーモン起動に失敗しました: {e}")
                    print("   手動で起動してください: ./start_learning_daemon.sh\n")

    elif preferences.get("enabled", False):
        # 既に設定済み: デーモンの状態をチェック
        daemon_status = bg_config.load_daemon_status()
        if daemon_status and daemon_status.get("running", False):
            import os
            # プロセスが実際に動いているか確認
            try:
                os.kill(daemon_status["pid"], 0)
                # プロセス存在
                pass
            except OSError:
                # プロセス不在
                print("⚠️  背景学習デーモンが停止しています")
                print("   起動するには: ./start_learning_daemon.sh\n")

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

    # Cross構造ビューアーを起動
    if open_viewer:
        from .cross_realtime_viewer import start_viewer_server
        import webbrowser

        print("🌐 Starting Cross Structure Realtime Viewer...")
        viewer_port = 8765
        start_viewer_server(cross_file, viewer_port)
        time.sleep(1)
        webbrowser.open(f"http://localhost:{viewer_port}")
        print(f"✅ Viewer opened at http://localhost:{viewer_port}")
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
    # Thinking状態の管理
    thinking_active = {'value': False, 'last_shown': 0}
    # 現在のユーザー入力を保持
    current_user_input = {'value': ''}

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

        # Thinkingインジケーターを検出してフィルタ
        if "Thinking…" in clean or "Thundering…" in clean:
            # Thinking開始
            if not thinking_active['value']:
                thinking_active['value'] = True
                thinking_active['last_shown'] = time.time()
                print("\n💭 Thinking...", end='', flush=True)
            else:
                # 既にThinking中 - 1秒ごとにドットを追加
                current_time = time.time()
                if current_time - thinking_active['last_shown'] >= 1.0:
                    print(".", end='', flush=True)
                    thinking_active['last_shown'] = current_time
            return

        # Thinking終了を検出
        if thinking_active['value']:
            # 実際の応答が始まった
            if clean.strip() and not any(marker in clean for marker in ['────', '? for shortcuts', 'Thinking off']):
                thinking_active['value'] = False
                print("\n", flush=True)  # 改行

        # 起動後は、すべての出力を表示（フィルタあり）
        if clean.strip():
            # フィルタするパターン
            skip_patterns = [
                '────',  # セパレーター
                '? for shortcuts',  # ヒント
                'Thinking off',  # Thinkingトグル
                'ctrl-g to edit',  # エディタヒント
                '(esc to interrupt)',  # 中断ヒント
            ]

            # スピナー文字（Thinking中のアニメーション）
            spinner_chars = ['✻', '✽', '✶', '✳', '✢', '·', '⏺']

            lines = clean.split('\n')
            for line in lines:
                stripped = line.strip()

                # スキップパターンをチェック
                should_skip = False
                for pattern in skip_patterns:
                    if pattern in stripped:
                        should_skip = True
                        break

                # スピナー文字だけの行もスキップ
                if stripped in spinner_chars:
                    should_skip = True

                # プロンプト行もスキップ
                if stripped == '>' or stripped.startswith('────>'):
                    should_skip = True

                # 表示するか判断
                if stripped and not should_skip:
                    print(line, flush=True)

    def on_claude_response(response: str):
        """Claude応答完了"""
        # UIに追加（簡易版なのでスキップ）
        # ui.add_message('assistant', response)

        # Cross構造の成長を表示（engineが自動記録）
        if show_cross:
            # エンジンのCross構造から統計を取得
            try:
                import json
                if cross_file.exists():
                    with open(cross_file, 'r', encoding='utf-8') as f:
                        cross_data = json.load(f)
                    axes = cross_data.get('axes', {})
                    total_inputs = len(axes.get('UP', {}).get('user_inputs', []))
                    total_responses = len(axes.get('DOWN', {}).get('claude_responses', []))
                    print(f"\n\n  💾 Cross Memory: {total_inputs} inputs, {total_responses} responses")
            except Exception as e:
                pass  # 統計表示失敗は無視

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

    # 自動応答を有効化（Claude Codeの選択肢に自動で "1" を送信）
    engine.enable_auto_respond()

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
    if use_vision:
        print("   - Image paths are auto-detected and processed with Verantyx Vision")
    else:
        print("   - Image recognition: Claude Code native support (high quality)")
    print("   - All conversations are saved to Cross structure")
    print("   - Press Ctrl+C to exit")
    print()
    print("📂 Cross Memory: ", cross_file)
    if use_vision:
        print("🖼️  Verantyx Vision: Enabled (Cross Simulation)")
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

            # 画像・動画パスを検出
            print("\n🔍 メディアファイルを検出中...")
            detected_images, detected_videos = detect_media_paths(user_input)

            enhanced_prompt = user_input

            # 動画は常にVerantyx Visionで処理（Claude Codeは動画非対応）
            if detected_videos:
                print(f"\n🎥 {len(detected_videos)}個の動画を検出しました")
                print("   ℹ️  動画はVerantyx Vision（最高品質 + Cross形状認識）で処理されます\n")

                for video_path in detected_videos:
                    # 動画をVisionで処理（最高品質 + JCross形状認識）
                    vision_context = process_video_with_vision(
                        video_path,
                        max_frames=10,
                        use_shape_recognition=True  # JCross形状認識を有効化
                    )

                    # プロンプトに動画コンテキストを追加
                    original_path = video_path
                    escaped_path = video_path.replace(' ', '\\ ')

                    if original_path in user_input:
                        enhanced_prompt = enhanced_prompt.replace(
                            original_path,
                            f"\n\n[Verantyx Vision Analysis of {Path(video_path).name}]\n{vision_context}\n"
                        )
                    elif escaped_path in user_input:
                        enhanced_prompt = enhanced_prompt.replace(
                            escaped_path,
                            f"\n\n[Verantyx Vision Analysis of {Path(video_path).name}]\n{vision_context}\n"
                        )
                    else:
                        enhanced_prompt += f"\n\n[Verantyx Vision Analysis of {Path(video_path).name}]\n{vision_context}\n"

            # 画像はuse_visionフラグに従う
            if use_vision and detected_images:
                print(f"\n🖼️  {len(detected_images)}個の画像を検出しました")
                print("   ℹ️  Verantyx Vision（Cross Simulation）で処理されます\n")

                for img_path in detected_images:
                    # Visionで処理
                    vision_context = process_image_with_vision(img_path)

                    # プロンプトに画像コンテキストを追加
                    original_path = img_path
                    escaped_path = img_path.replace(' ', '\\ ')

                    if original_path in user_input:
                        enhanced_prompt = enhanced_prompt.replace(
                            original_path,
                            f"\n\n[Verantyx Vision Analysis of {Path(img_path).name}]\n{vision_context}\n"
                        )
                    elif escaped_path in user_input:
                        enhanced_prompt = enhanced_prompt.replace(
                            escaped_path,
                            f"\n\n[Verantyx Vision Analysis of {Path(img_path).name}]\n{vision_context}\n"
                        )
                    else:
                        enhanced_prompt += f"\n\n[Verantyx Vision Analysis of {Path(img_path).name}]\n{vision_context}\n"
            elif detected_images and not use_vision:
                print(f"   🖼️  {len(detected_images)}個の画像を検出（Claude Code nativeで処理）")

            if not detected_images and not detected_videos:
                print("   メディアファイルは検出されませんでした")

            # UIに追加（簡易版なのでスキップ）
            # ui.add_message('user', user_input)

            # Claudeに送信（JCross拡張 + 画像コンテキスト）
            print("\n📤 Sending to Claude...", flush=True)

            # トリガーワードチェック
            trigger_words = ['auto', 'yes', 'allow', 'high', '自動', '許可', 'はい']
            has_trigger = any(word in user_input.lower() for word in trigger_words)
            if has_trigger:
                print("   ✅ 自動応答トリガー検出（Claudeの選択肢に自動で応答します）")

            # ユーザー入力を保持（応答記録用）
            current_user_input['value'] = user_input

            print("🤖 Verantyx Agent: ", end='', flush=True)

            success = engine.send_prompt(enhanced_prompt, use_jcross=True, auto_respond=True)

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
