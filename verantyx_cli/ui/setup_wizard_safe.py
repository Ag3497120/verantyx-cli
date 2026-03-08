"""
Safe Setup Wizard - Zero-dependency, bulletproof implementation

Uses only standard input() - no raw mode, no escape sequences, no TUI.
Works perfectly with Japanese IME and all terminal environments.
"""

from pathlib import Path
from typing import Optional, Dict, Any


def print_separator():
    """Print separator line"""
    print("\n" + "=" * 70 + "\n")


def print_menu(title: str, options: list) -> int:
    """
    Print menu and get user selection

    Args:
        title: Menu title
        options: List of option strings

    Returns:
        Selected index (0-based)
    """
    print_separator()
    print(f"  {title}")
    print_separator()

    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")

    print()

    while True:
        try:
            choice = input("  Select (1-{}): ".format(len(options)))
            choice_num = int(choice)

            if 1 <= choice_num <= len(options):
                return choice_num - 1
            else:
                print(f"  ❌ Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("  ❌ Please enter a valid number")
        except KeyboardInterrupt:
            print("\n\n  Setup cancelled.")
            return -1


def get_input(prompt: str, default: str = "", password: bool = False) -> str:
    """
    Get text input from user

    Args:
        prompt: Prompt message
        default: Default value
        password: Hide input if True

    Returns:
        User input string
    """
    print_separator()
    print(f"  {prompt}")
    print_separator()

    if default:
        print(f"  💡 Default: {default}")
        print()

    try:
        if password:
            import getpass
            print("  🔒 API key will be hidden while typing")
            print()
            value = getpass.getpass("  Enter API key: ")
        else:
            if default:
                print(f"  📝 Type your value and press Enter")
                print(f"  💡 Or just press Enter to use default: '{default}'")
                print()
                value = input("  > ")
            else:
                print("  📝 Type your value and press Enter")
                print("  💡 Japanese IME: Preview will appear below, then Enter to confirm")
                print()
                value = input("  > ")

        return value.strip() or default

    except KeyboardInterrupt:
        print("\n\n  Setup cancelled.")
        return ""


def run_setup_wizard(project_path: Path) -> Dict[str, Any]:
    """
    Run safe setup wizard using only standard input()

    Returns:
        Configuration dict
    """
    print("\n\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "🚀 Verantyx-CLI Setup" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝")

    # Step 1: LLM Selection
    llm_options = [
        "Claude (Anthropic) - Subscription",
        "Gemini (Google) - Subscription",
        "Codex (OpenAI) - Subscription",
        "Claude API (requires API key)",
        "Gemini API (requires API key)",
        "OpenAI API (requires API key)",
    ]

    llm_mapping = {
        0: ("claude", "subscription"),
        1: ("gemini", "subscription"),
        2: ("codex", "subscription"),
        3: ("claude", "api"),
        4: ("gemini", "api"),
        5: ("openai", "api"),
    }

    selected = print_menu("Select your LLM provider", llm_options)

    if selected == -1:
        return {
            "llm_type": "claude",
            "llm_mode": "subscription",
            "launch_command": "claude",
            "api_key": None,
            "multi_agent": False,
            "num_agents": 1
        }

    llm_name, llm_mode = llm_mapping[selected]

    # Step 1.5: Multi-Agent Mode Selection
    print_separator()
    print("  🤖 Agent Mode Selection")
    print_separator()
    print()

    agent_mode_options = [
        "Single Agent - Standard mode with one Claude instance",
        "Multi-Agent - Control multiple agents with personality awareness"
    ]

    agent_mode_selected = print_menu("Select agent mode", agent_mode_options)
    multi_agent = (agent_mode_selected == 1)

    # Step 1.5: Select execution architecture
    arch_options = [
        "VM (von Neumann) - Recommended for Claude wrapper (I/O-dependent)",
        "Neural Engine (Experimental) - For static state graphs only"
    ]

    arch_selected = print_menu("Select execution architecture", arch_options)
    use_neural_engine = (arch_selected == 1)

    if use_neural_engine:
        print()
        print("  ⚠️  Neural Engine selected (Experimental)")
        print("     - Best for: Static state graphs, data pipelines")
        print("     - NOT suitable for: I/O-dependent control flow")
        print("     - Claude wrapper will loop infinitely with this option")
        print("     - Uses Apple Neural Engine (ANE)")
        print()
        print("  ℹ️  For Claude wrapper, VM is recommended")
        print()
    else:
        print()
        print("  ✅ VM selected (Recommended)")
        print("     - von Neumann architecture")
        print("     - Perfect for I/O-dependent programs")
        print("     - Works correctly with Claude wrapper")
        print()

    num_agents = 1
    if multi_agent:
        print()
        num_agents_str = get_input(
            "🔢 Number of agents to launch (2-5)",
            default="2"
        )
        try:
            num_agents = int(num_agents_str)
            if num_agents < 2:
                num_agents = 2
            elif num_agents > 5:
                num_agents = 5
        except ValueError:
            num_agents = 2

        print(f"  ✅ Will launch {num_agents} agents")
        print()

    # Step 2: Configuration Input
    if llm_mode == "api":
        # API mode - get API key
        api_key = get_input(
            f"🔑 Enter your {llm_name.upper()} API Key",
            password=True
        )

        if not api_key:
            print("\n  ❌ Setup cancelled - no API key provided")
            return {
                "llm_type": "claude",
                "llm_mode": "subscription",
                "launch_command": "claude",
                "api_key": None
            }

        # Success message
        print_separator()
        print("  ✅ Setup Complete!")
        print_separator()
        print(f"  LLM: {llm_name.upper()}")
        print(f"  Mode: API")
        print(f"  API Key: {'*' * min(20, len(api_key))}")
        print()

        return {
            "llm_type": llm_name,
            "llm_mode": "api",
            "launch_command": None,
            "api_key": api_key,
            "multi_agent": multi_agent,
            "num_agents": num_agents,
            "use_neural_engine": use_neural_engine
        }

    else:
        # Subscription mode - get launch command
        launch_command = get_input(
            f"🚀 Enter command to launch {llm_name.capitalize()}",
            default=llm_name
        )

        if not launch_command:
            print("\n  ❌ Setup cancelled")
            return {
                "llm_type": "claude",
                "llm_mode": "subscription",
                "launch_command": "claude",
                "api_key": None,
                "multi_agent": False,
                "num_agents": 1,
                "use_neural_engine": False
            }

        # Success message
        print_separator()
        print("  ✅ Setup Complete!")
        print_separator()
        print(f"  LLM: {llm_name.upper()}")
        print(f"  Mode: Subscription (separate terminal)")
        print(f"  Launch command: {launch_command}")
        print_separator()

        # Show installation status
        import subprocess
        check_result = subprocess.run(
            ["which", launch_command],
            capture_output=True,
            text=True
        )

        if check_result.returncode == 0:
            print(f"  ✅ '{launch_command}' is installed and ready")
        else:
            print(f"  ⚠️  '{launch_command}' command not found!")
            print()
            print("  Installation guides:")

            if llm_name == 'claude':
                print("  • Claude: npm install -g @anthropic-ai/claude-code")
            elif llm_name == 'gemini':
                print("  • Gemini: Install Google AI CLI")
                print("    https://ai.google.dev/gemini-api/docs/cli")
            elif llm_name == 'codex':
                print("  • Codex: npm install -g openai-codex-cli")

            print()
            print("  💡 Install the CLI and run 'verantyx chat' again")

        print_separator()

        return {
            "llm_type": llm_name,
            "llm_mode": "subscription",
            "launch_command": launch_command,
            "api_key": None,
            "multi_agent": multi_agent,
            "num_agents": num_agents,
            "use_neural_engine": use_neural_engine
        }


if __name__ == "__main__":
    # Test
    config = run_setup_wizard(Path.cwd())
    print("\nFinal config:", config)
