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


def detect_image_paths(text: str) -> list[str]:
    """
    テキストから画像パスを検出

    Returns:
        検出された画像パスのリスト
    """
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff']
    detected_paths = []

    # パターン1: 絶対パス（/で始まる、または~/で始まる）
    abs_pattern = r'[/~][^\s]+'

    # パターン2: 相対パス（./で始まる、または../で始まる）
    rel_pattern = r'\.[/\.][\S]+'

    # すべてのパスパターンを検出
    all_patterns = abs_pattern + '|' + rel_pattern
    potential_paths = re.findall(all_patterns, text)

    for path_str in potential_paths:
        # エスケープされたスペースを処理
        path_str = path_str.replace('\\ ', ' ')

        # パスとして検証
        try:
            path = Path(path_str).expanduser()

            # 画像ファイルかチェック
            if path.suffix.lower() in image_extensions:
                if path.exists():
                    detected_paths.append(str(path.absolute()))
                    logger.info(f"Detected image path: {path}")
        except:
            continue

    return detected_paths


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
    # Thinking状態の管理
    thinking_active = {'value': False, 'last_shown': 0}

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
    print("   - Image paths are auto-detected and processed with Verantyx Vision")
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

            # 画像パスを検出
            detected_images = detect_image_paths(user_input)

            # 画像が検出された場合、Verantyx Visionで処理
            enhanced_prompt = user_input
            if detected_images:
                print(f"\n🖼️  {len(detected_images)}個の画像を検出しました")

                for img_path in detected_images:
                    # Visionで処理
                    vision_context = process_image_with_vision(img_path)

                    # プロンプトに画像コンテキストを追加
                    enhanced_prompt = enhanced_prompt.replace(
                        img_path,
                        f"\n\n[Verantyx Vision Analysis of {Path(img_path).name}]\n{vision_context}\n"
                    )

            # UIに追加（簡易版なのでスキップ）
            # ui.add_message('user', user_input)

            # Claudeに送信（JCross拡張 + 画像コンテキスト）
            print("\n📤 Sending to Claude...", flush=True)
            print("🤖 Verantyx Agent: ", end='', flush=True)

            success = engine.send_prompt(enhanced_prompt, use_jcross=True)

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
