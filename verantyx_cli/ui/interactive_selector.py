#!/usr/bin/env python3
"""
Interactive Selector - 矢印キーで選択できるUI

使い方:
    from verantyx_cli.ui.interactive_selector import select_option

    options = ["Option 1", "Option 2", "Option 3"]
    selected = select_option("Choose an option:", options)
"""

import sys
import tty
import termios
from typing import List, Optional


def select_option(prompt: str, options: List[str], descriptions: Optional[List[str]] = None) -> Optional[str]:
    """
    矢印キーで選択できるインタラクティブセレクター

    Args:
        prompt: プロンプトメッセージ
        options: 選択肢のリスト
        descriptions: 各選択肢の説明（オプション）

    Returns:
        選択されたオプション、キャンセル時はNone
    """
    if not options:
        return None

    # 現在の選択インデックス
    selected_idx = 0

    # ターミナル設定を保存
    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except termios.error:
        # TTYが利用できない場合はフォールバック（最初の選択肢を返す）
        print(f"{prompt}\n")
        for i, option in enumerate(options):
            print(f"  {i+1}. {option}")
            if descriptions and i < len(descriptions) and descriptions[i]:
                print(f"     {descriptions[i]}")
        print("\n⚠️  Interactive mode not available, selecting first option")
        return options[0] if options else None

    try:
        # Raw モードに設定
        tty.setraw(fd)

        while True:
            # 画面クリア（カーソルを上に移動）
            if selected_idx > 0:
                print(f"\033[{len(options) + 2}A", end='')

            # プロンプト表示
            print(f"\r\033[K{prompt}")
            print("\r\033[K")

            # 選択肢を表示
            for i, option in enumerate(options):
                if i == selected_idx:
                    # 選択中（緑色 + 矢印）
                    print(f"\r\033[K\033[32m❯ {option}\033[0m")
                else:
                    # 未選択
                    print(f"\r\033[K  {option}")

                # 説明があれば表示
                if descriptions and i < len(descriptions) and descriptions[i]:
                    desc = descriptions[i]
                    if i == selected_idx:
                        print(f"\r\033[K    \033[90m{desc}\033[0m")
                    else:
                        print(f"\r\033[K    \033[90m{desc}\033[0m")

            print("\r\033[K")
            print("\r\033[K\033[90m↑/↓: 選択  Enter: 決定  Ctrl+C: キャンセル\033[0m", end='', flush=True)

            # キー入力待機
            ch = sys.stdin.read(1)

            if ch == '\x03':  # Ctrl+C
                print("\n")
                return None
            elif ch == '\r' or ch == '\n':  # Enter
                print("\n")
                return options[selected_idx]
            elif ch == '\x1b':  # エスケープシーケンス（矢印キー）
                next1 = sys.stdin.read(1)
                if next1 == '[':
                    next2 = sys.stdin.read(1)
                    if next2 == 'A':  # 上矢印
                        selected_idx = (selected_idx - 1) % len(options)
                    elif next2 == 'B':  # 下矢印
                        selected_idx = (selected_idx + 1) % len(options)

    finally:
        # ターミナル設定を復元
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def select_with_index(prompt: str, options: List[str], descriptions: Optional[List[str]] = None) -> Optional[int]:
    """
    矢印キーで選択し、インデックスを返す

    Returns:
        選択されたインデックス、キャンセル時はNone
    """
    if not options:
        return None

    selected_idx = 0
    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except termios.error:
        # TTYが利用できない場合はフォールバック
        print(f"{prompt}\n")
        for i, option in enumerate(options):
            print(f"  {i+1}. {option}")
            if descriptions and i < len(descriptions) and descriptions[i]:
                print(f"     {descriptions[i]}")
        print("\n⚠️  Interactive mode not available, selecting first option")
        return 0

    try:
        tty.setraw(fd)

        while True:
            # 画面更新
            if selected_idx > 0:
                lines = len(options) + 3
                if descriptions:
                    lines += len([d for d in descriptions if d])
                print(f"\033[{lines}A", end='')

            print(f"\r\033[K{prompt}")
            print("\r\033[K")

            for i, option in enumerate(options):
                if i == selected_idx:
                    print(f"\r\033[K\033[32m❯ {option}\033[0m")
                else:
                    print(f"\r\033[K  {option}")

                if descriptions and i < len(descriptions) and descriptions[i]:
                    print(f"\r\033[K    \033[90m{descriptions[i]}\033[0m")

            print("\r\033[K")
            print("\r\033[K\033[90m↑/↓: 選択  Enter: 決定  Ctrl+C: キャンセル\033[0m", end='', flush=True)

            ch = sys.stdin.read(1)

            if ch == '\x03':
                print("\n")
                return None
            elif ch == '\r' or ch == '\n':
                print("\n")
                return selected_idx
            elif ch == '\x1b':
                next1 = sys.stdin.read(1)
                if next1 == '[':
                    next2 = sys.stdin.read(1)
                    if next2 == 'A':
                        selected_idx = (selected_idx - 1) % len(options)
                    elif next2 == 'B':
                        selected_idx = (selected_idx + 1) % len(options)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    # テスト
    test_options = [
        "Start new conversation",
        "Resume previous conversation",
        "View Cross memory",
        "Exit"
    ]

    test_descriptions = [
        "Begin a fresh chat session",
        "Continue from where you left off",
        "Browse your conversation history",
        "Quit Verantyx"
    ]

    print("🧪 Interactive Selector Test\n")

    result = select_option("What would you like to do?", test_options, test_descriptions)

    if result:
        print(f"✅ You selected: {result}")
    else:
        print("❌ Selection cancelled")
