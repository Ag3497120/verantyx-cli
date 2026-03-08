"""
Verantyx-CLI entry point
"""

import sys
import argparse
from pathlib import Path


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="verantyx",
        description="Verantyx-CLI: Autonomous AI Assistant with Cross Memory",
        epilog="Built with human-like thinking • Learn more at https://github.com/verantyx/verantyx-cli"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Chat mode (default)
    chat_parser = subparsers.add_parser(
        "chat",
        help="Start interactive chat mode"
    )
    chat_parser.add_argument(
        "--project",
        type=str,
        default=".",
        help="Project directory (default: current directory)"
    )
    chat_parser.add_argument(
        "--llm",
        type=str,
        choices=["claude", "gemini", "ollama", "gpt4"],
        default="claude",
        help="LLM to use (default: claude)"
    )

    # Auto mode (autonomous execution)
    auto_parser = subparsers.add_parser(
        "auto",
        help="Start autonomous mode"
    )
    auto_parser.add_argument(
        "--project",
        type=str,
        default=".",
        help="Project directory"
    )
    auto_parser.add_argument(
        "--goal",
        type=str,
        help="Goal to achieve (if not provided, will ask interactively)"
    )

    # Browse mode (file browser with chat)
    browse_parser = subparsers.add_parser(
        "browse",
        help="Start file browser mode"
    )
    browse_parser.add_argument(
        "--project",
        type=str,
        default=".",
        help="Project directory"
    )

    # Cross viewer
    cross_parser = subparsers.add_parser(
        "cross",
        help="View Cross structure in real-time"
    )
    cross_parser.add_argument(
        "--project",
        type=str,
        default=".",
        help="Project directory"
    )

    # Vision commands (image to Cross)
    vision_parser = subparsers.add_parser(
        "vision",
        help="Image recognition via Cross simulation"
    )
    vision_parser.add_argument(
        "image",
        type=str,
        help="Path to image file"
    )
    vision_parser.add_argument(
        "--output",
        type=str,
        help="Output path for Cross structure JSON (optional)"
    )
    vision_parser.add_argument(
        "--llm-context",
        action="store_true",
        help="Generate LLM-readable context (for feeding to Claude/Gemini)"
    )
    vision_parser.add_argument(
        "--quality",
        type=str,
        choices=["low", "medium", "high", "ultra", "maximum"],
        default="medium",
        help="Quality preset: low(500pts), medium(1000pts), high(5000pts), ultra(10000pts), maximum(50000pts)"
    )
    vision_parser.add_argument(
        "--max-points",
        type=int,
        help="Custom maximum points (overrides --quality)"
    )

    # Memory commands
    memory_parser = subparsers.add_parser(
        "memory",
        help="Cross Memory management"
    )
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command")

    memory_subparsers.add_parser("show", help="Show Cross Memory contents")
    memory_subparsers.add_parser("stats", help="Show memory statistics")
    memory_subparsers.add_parser("clear", help="Clear Cross Memory")

    # Config commands
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration management"
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    config_subparsers.add_parser("init", help="Initialize configuration")
    config_subparsers.add_parser("show", help="Show current configuration")
    config_subparsers.add_parser("edit", help="Edit configuration file")

    # Version
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}"
    )

    args = parser.parse_args()

    # Default to chat mode if no command specified
    if not args.command:
        args.command = "chat"
        args.project = "."
        args.llm = "claude"

    # Route to appropriate handler
    try:
        if args.command == "chat":
            from .ui.terminal_ui import start_chat_mode
            start_chat_mode(
                project_path=Path(args.project),
                llm_provider=args.llm
            )
        elif args.command == "auto":
            from .ui.terminal_ui import start_auto_mode
            start_auto_mode(
                project_path=Path(args.project),
                goal=getattr(args, "goal", None)
            )
        elif args.command == "browse":
            from .ui.terminal_ui import start_browse_mode
            start_browse_mode(
                project_path=Path(args.project)
            )
        elif args.command == "cross":
            from .ui.cross_viewer import view_cross_structure
            view_cross_structure(
                project_path=Path(args.project)
            )
        elif args.command == "vision":
            from .cli_commands import handle_vision_command
            handle_vision_command(
                image_path=args.image,
                output_path=getattr(args, "output", None),
                llm_context=getattr(args, "llm_context", False),
                quality=getattr(args, "quality", "medium"),
                max_points=getattr(args, "max_points", None)
            )
        elif args.command == "memory":
            from .cli_commands import handle_memory_command
            handle_memory_command(args.memory_command)
        elif args.command == "config":
            from .cli_commands import handle_config_command
            handle_config_command(args.config_command)
        else:
            parser.print_help()
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if "--debug" in sys.argv:
            raise
        return 1


def get_version() -> str:
    """Get version from __init__.py"""
    from . import __version__
    return __version__


if __name__ == "__main__":
    sys.exit(main())
