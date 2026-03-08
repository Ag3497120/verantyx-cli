"""
Simple Setup Wizard - Terminal-safe implementation

Uses standard input/print instead of Textual TUI to avoid:
- ANSI escape sequence leakage
- IME buffer conflicts
- Raw mode input issues
"""

from pathlib import Path
from typing import Optional, Dict, Any
import sys


def clear_screen():
    """Clear terminal screen"""
    print("\033[2J\033[H", end="")


def print_header(title: str):
    """Print header"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def print_menu(options: list, selected: int):
    """Print menu with selection"""
    for i, option in enumerate(options):
        if i == selected:
            print(f"  → {option}")
        else:
            print(f"    {option}")


def get_arrow_selection(options: list, prompt: str = "") -> int:
    """
    Get user selection with arrow keys

    Returns index of selected option
    """
    import termios
    import tty

    selected = 0

    # Save terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        while True:
            clear_screen()
            print_header(prompt)
            print_menu(options, selected)
            print()
            print("  ↑↓: Navigate  Enter: Select  q: Quit")

            # Get single character
            tty.setraw(fd)
            ch = sys.stdin.read(1)

            # Restore for potential multi-byte read
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            if ch == '\x1b':  # ESC sequence
                # Read next two characters for arrow keys
                tty.setraw(fd)
                ch2 = sys.stdin.read(2)
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

                if ch2 == '[A':  # Up arrow
                    selected = (selected - 1) % len(options)
                elif ch2 == '[B':  # Down arrow
                    selected = (selected + 1) % len(options)

            elif ch == '\r' or ch == '\n':  # Enter
                return selected
            elif ch == 'q' or ch == 'Q':
                return -1

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def get_text_input(prompt: str, default: str = "", password: bool = False) -> str:
    """
    Get text input from user

    Args:
        prompt: Prompt message
        default: Default value
        password: Hide input if True

    Returns:
        User input string
    """
    clear_screen()
    print_header(prompt)

    if default:
        print(f"  Default: {default}")
        print()

    if password:
        import getpass
        value = getpass.getpass("  Enter value (hidden): ")
    else:
        value = input("  Enter value: ")

    return value.strip() or default


def run_setup_wizard(project_path: Path) -> Dict[str, Any]:
    """
    Run simple setup wizard

    Returns:
        Configuration dict
    """
    clear_screen()

    # Step 1: LLM Selection
    llm_options = [
        "Claude (Anthropic)",
        "Gemini (Google)",
        "Codex (OpenAI)",
        "──────────────────",
        "Claude API (API key required)",
        "Gemini API (API key required)",
        "OpenAI API (API key required)",
    ]

    llm_mapping = {
        0: ("claude", False),
        1: ("gemini", False),
        2: ("codex", False),
        4: ("claude", True),
        5: ("gemini", True),
        6: ("openai", True),
    }

    selected = get_arrow_selection(
        llm_options,
        "🚀 Verantyx-CLI Setup - Select LLM Provider"
    )

    if selected == -1 or selected == 3:  # Quit or separator
        print("\nSetup cancelled.")
        return {
            "llm_type": "claude",
            "llm_mode": "subscription",
            "launch_command": "claude",
            "api_key": None
        }

    llm_name, is_api = llm_mapping[selected]

    # Step 2: Mode Selection (if not API)
    if not is_api:
        mode_options = [
            f"🚀 Launch {llm_name} CLI (subscription required)",
            f"🔑 Use {llm_name} API (API key required)",
        ]

        mode_selected = get_arrow_selection(
            mode_options,
            f"🤖 {llm_name.upper()} Configuration - Select Mode"
        )

        if mode_selected == -1:
            print("\nSetup cancelled.")
            return {
                "llm_type": "claude",
                "llm_mode": "subscription",
                "launch_command": "claude",
                "api_key": None
            }

        is_api = (mode_selected == 1)

    # Step 3: Configuration Input
    if is_api:
        # API mode - get API key
        api_key = get_text_input(
            f"🔑 Enter {llm_name.upper()} API Key",
            password=True
        )

        clear_screen()
        print_header("✅ Setup Complete!")
        print(f"  LLM: {llm_name.upper()}")
        print(f"  Mode: API")
        print(f"  API Key: {'*' * 20}")
        print()

        return {
            "llm_type": llm_name,
            "llm_mode": "api",
            "launch_command": None,
            "api_key": api_key
        }
    else:
        # Subscription mode - get launch command
        launch_command = get_text_input(
            f"🚀 Enter {llm_name.capitalize()} Launch Command",
            default=llm_name
        )

        clear_screen()
        print_header("✅ Setup Complete!")
        print(f"  LLM: {llm_name.upper()}")
        print(f"  Mode: Subscription (separate terminal)")
        print(f"  Launch command: {launch_command}")
        print()

        return {
            "llm_type": llm_name,
            "llm_mode": "subscription",
            "launch_command": launch_command,
            "api_key": None
        }
