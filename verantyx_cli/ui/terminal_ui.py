"""
Verantyx Terminal UI - Main TUI using Textual

Provides rich, interactive terminal interface with:
- Chat panel
- File browser
- Task progress
- Real-time logs
"""

import logging
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult

logger = logging.getLogger(__name__)
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input
from textual.binding import Binding
from rich.console import RenderableType
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text


class ChatPanel(Static):
    """Chat interface panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages = []

    def add_message(self, role: str, content: str):
        """Add a message to chat history"""
        self.messages.append({"role": role, "content": content})
        self.update_display()

    def update_display(self):
        """Update the display with current messages"""
        lines = []
        for msg in self.messages[-20:]:  # Show last 20 messages
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                lines.append(f"[bold cyan]> {content}[/bold cyan]")
            elif role == "assistant":
                lines.append(f"[bold green]🤖 {content}[/bold green]")
            elif role == "system":
                lines.append(f"[dim]{content}[/dim]")

            lines.append("")  # Blank line between messages

        text = "\n".join(lines)
        self.update(Markdown(text))


class FileBrowserPanel(Static):
    """File browser panel"""

    def __init__(self, project_path: Path, **kwargs):
        super().__init__(**kwargs)
        self.project_path = project_path
        self.update_tree()

    def update_tree(self):
        """Update file tree display"""
        tree_lines = [
            f"[bold]📁 {self.project_path.name}/[/bold]",
            ""
        ]

        # Simple file tree (can be enhanced with tree view widget)
        for item in sorted(self.project_path.iterdir()):
            if item.name.startswith('.'):
                continue

            if item.is_dir():
                tree_lines.append(f"  📁 {item.name}/")
            else:
                tree_lines.append(f"  📄 {item.name}")

        self.update("\n".join(tree_lines))


class TaskPanel(Static):
    """Task progress panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks = []

    def add_task(self, task_name: str, status: str = "pending"):
        """Add a task"""
        self.tasks.append({"name": task_name, "status": status})
        self.update_display()

    def update_task(self, index: int, status: str):
        """Update task status"""
        if 0 <= index < len(self.tasks):
            self.tasks[index]["status"] = status
            self.update_display()

    def update_display(self):
        """Update task display"""
        lines = ["[bold]📋 Tasks:[/bold]", ""]

        for task in self.tasks:
            status = task["status"]
            name = task["name"]

            if status == "completed":
                icon = "✓"
                color = "green"
            elif status == "in_progress":
                icon = "⏳"
                color = "yellow"
            elif status == "failed":
                icon = "✗"
                color = "red"
            else:
                icon = "⏸"
                color = "dim"

            lines.append(f"[{color}]{icon} {name}[/{color}]")

        self.update("\n".join(lines))


class LogPanel(Static):
    """Real-time log panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logs = []

    def add_log(self, message: str, level: str = "info"):
        """Add a log entry"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        if level == "error":
            color = "red"
            icon = "❌"
        elif level == "warning":
            color = "yellow"
            icon = "⚠️"
        elif level == "success":
            color = "green"
            icon = "✅"
        else:
            color = "white"
            icon = "ℹ️"

        self.logs.append(f"[{color}][{timestamp}] {icon} {message}[/{color}]")
        self.update_display()

    def update_display(self):
        """Update log display"""
        # Show last 50 logs
        text = "\n".join(self.logs[-50:])
        self.update(text)


class VerantyxTerminalApp(App):
    """Main Verantyx Terminal Application"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 3;
        grid-rows: auto 1fr auto;
    }

    Header {
        column-span: 2;
    }

    Footer {
        column-span: 2;
    }

    #file_browser {
        width: 30%;
        border: solid $primary;
        padding: 1;
    }

    #chat_panel {
        width: 70%;
        border: solid $primary;
        padding: 1;
    }

    #task_panel {
        width: 30%;
        border: solid $primary;
        padding: 1;
        height: 40%;
    }

    #log_panel {
        width: 70%;
        border: solid $primary;
        padding: 1;
        height: 40%;
    }

    #input_box {
        column-span: 2;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+r", "refresh", "Refresh"),
        ("?", "help", "Help"),
    ]

    def __init__(
        self,
        project_path: Path,
        llm_provider: str = "claude",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.project_path = project_path
        self.llm_provider = llm_provider

        # Will be initialized in compose
        self.chat_panel = None
        self.file_browser = None
        self.task_panel = None
        self.log_panel = None
        self.input_box = None

    def compose(self) -> ComposeResult:
        """Compose the UI layout"""
        yield Header(show_clock=True)

        # Top row: File Browser + Chat
        yield FileBrowserPanel(self.project_path, id="file_browser")
        yield ChatPanel(id="chat_panel")

        # Bottom row: Tasks + Logs
        yield TaskPanel(id="task_panel")
        yield LogPanel(id="log_panel")

        # Input box at bottom
        yield Input(placeholder="Type your message... (Ctrl+C to quit)", id="input_box")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted"""
        self.title = f"Verantyx-CLI | {self.project_path.name} | {self.llm_provider.upper()}"

        # Get widget references
        self.chat_panel = self.query_one("#chat_panel", ChatPanel)
        self.file_browser = self.query_one("#file_browser", FileBrowserPanel)
        self.task_panel = self.query_one("#task_panel", TaskPanel)
        self.log_panel = self.query_one("#log_panel", LogPanel)
        self.input_box = self.query_one("#input_box", Input)

        # Welcome message
        self.chat_panel.add_message("system", "Welcome to Verantyx-CLI!")
        self.chat_panel.add_message("system", f"Project: {self.project_path}")
        self.chat_panel.add_message("system", f"LLM: {self.llm_provider}")
        self.chat_panel.add_message("assistant", "How can I help you today?")

        self.log_panel.add_log("Verantyx-CLI started", "success")
        self.log_panel.add_log(f"Using {self.llm_provider} LLM", "info")

        # Focus input
        self.input_box.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission"""
        user_input = event.value.strip()

        if not user_input:
            return

        # Clear input
        self.input_box.value = ""

        # Add to chat
        self.chat_panel.add_message("user", user_input)
        self.log_panel.add_log(f"User: {user_input[:50]}...", "info")

        # Process input (placeholder - will be replaced with actual LLM integration)
        self.process_user_input(user_input)

    def process_user_input(self, user_input: str):
        """Process user input and generate response"""
        # Placeholder implementation
        # TODO: Integrate with VerantyxCore and LLM Router

        self.log_panel.add_log("Processing input...", "info")

        # Simulate response
        response = f"I received: {user_input}\n\n(LLM integration coming soon...)"
        self.chat_panel.add_message("assistant", response)

        self.log_panel.add_log("Response generated", "success")

    def action_clear_chat(self) -> None:
        """Clear chat panel"""
        self.chat_panel.messages = []
        self.chat_panel.update_display()
        self.log_panel.add_log("Chat cleared", "info")

    def action_refresh(self) -> None:
        """Refresh file browser"""
        self.file_browser.update_tree()
        self.log_panel.add_log("File browser refreshed", "info")

    def action_help(self) -> None:
        """Show help"""
        help_text = """
## Verantyx-CLI Help

**Keybindings:**
- `Ctrl+C` - Quit
- `Ctrl+L` - Clear chat
- `Ctrl+R` - Refresh file browser
- `?` - This help

**Commands:**
- `help` - Show this help
- `exit` or `quit` - Exit the application
- `clear` - Clear chat
- `/auto` - Enter autonomous mode
- `/browse` - Focus file browser

**Features:**
- Cross Memory learning
- Multi-LLM support
- Autonomous task execution
- Real-time file monitoring
        """
        self.chat_panel.add_message("system", help_text)


# Entry point functions

def start_chat_mode(project_path: Path, llm_provider: str = "claude"):
    """Start chat mode with setup wizard"""
    from .setup_wizard_safe import run_setup_wizard
    from .simple_chat_ui import SimpleChatUI
    from ..engine.claude_tab_launcher import ClaudeTabLauncher
    from ..engine.claude_socket_server import ClaudeSocketServer
    from ..engine.cross_generator import CrossGenerator
    import threading
    import time

    # Enable debug logging (file only - don't interfere with UI)
    verantyx_dir = project_path / '.verantyx'
    verantyx_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(verantyx_dir / 'debug.log')
        ]
    )
    logger.info("=== Verantyx Chat Mode Starting ===")

    # Step 1: Run setup wizard (100% safe, uses only standard input())
    config = run_setup_wizard(project_path)

    # Check if multi-agent mode
    multi_agent = config.get('multi_agent', False)
    num_agents = config.get('num_agents', 1)

    if multi_agent:
        # Launch multi-agent mode
        return start_multi_agent_mode(project_path, config)

    # Step 2: Launch LLM in separate terminal TAB (single agent mode)
    llm_name = config['llm_type'].capitalize()
    launch_cmd = config['launch_command']

    if not launch_cmd:
        print("❌ API mode not yet implemented")
        print("   Please use subscription mode for now")
        return

    print()
    print("=" * 70)
    print(f"  Launching {llm_name} with Socket Communication")
    print("=" * 70)
    print()
    print(f"📍 Command: {launch_cmd}")
    print(f"📂 Directory: {project_path}")
    print()

    # Step 2a: Create socket server
    print("🔧 Setting up socket server...")
    socket_server = ClaudeSocketServer()

    host, port = socket_server.start()
    print(f"✅ Socket server ready on {host}:{port}")
    print()

    # Step 2b: Launch in new tab with socket info
    print(f"🚀 Launching {llm_name} wrapper in new tab...")

    # Create launcher instance (keep reference for cleanup)
    launcher = ClaudeTabLauncher(project_path, launch_cmd, host, port)

    if not launcher.launch():
        print()
        print("   Installation guides:")

        if config['llm_type'] == 'claude':
            print("   • Claude: npm install -g @anthropic-ai/claude-code")
        elif config['llm_type'] == 'gemini':
            print("   • Gemini CLI: Install Google Cloud SDK and enable Gemini API")
            print("     https://cloud.google.com/sdk/docs/install")
        elif config['llm_type'] == 'codex':
            print("   • Codex: npm install -g openai-codex-cli")

        print()
        socket_server.stop()
        return

    print(f"✅ Wrapper launched in new tab")
    print()

    # Step 2c: Wait for connection
    print("📡 Waiting for wrapper to connect...")
    print("   (This may take a few seconds)")
    print()

    # Wait up to 30 seconds for connection
    wait_start = time.time()
    while not socket_server.is_connected() and (time.time() - wait_start) < 30:
        time.sleep(0.5)

    if not socket_server.is_connected():
        print("❌ Wrapper did not connect in time")
        print("   Please check the new tab for error messages")
        print()
        socket_server.stop()
        return

    print()
    print("=" * 70)
    print(f"  ✅ {llm_name} Connected!")
    print("=" * 70)
    print()
    time.sleep(1)

    # Step 3a: Start Cross structure generator
    cross_file = verantyx_dir / "conversation.cross.json"
    cross_gen = CrossGenerator(output_file=cross_file, update_interval=3.0)
    cross_gen.start()
    logger.info(f"Cross generator started: {cross_file}")

    # Step 3b: Create input callback with Cross recording
    def on_user_input(text: str):
        """Handle user input - send to Claude and record in Cross"""
        socket_server.send_input(text)
        cross_gen.add_user_message(text)

    # Step 3c: Start simple chat UI with socket connection
    print("🎨 Starting Verantyx Chat UI...")
    print()

    ui = SimpleChatUI(
        llm_name=llm_name,
        on_user_input=on_user_input,
        cross_file=cross_file,
        verantyx_dir=verantyx_dir
    )

    # Set up output relay with buffering, response detection, and Cross recording
    def output_relay():
        """Relay socket outputs to UI with buffering"""
        displayed_count = 0
        output_buffer = ""
        last_output_time = time.time()
        response_detected = False

        while ui.running and socket_server.is_connected():
            current_count = len(socket_server.outputs)

            # Accumulate new outputs
            if current_count > displayed_count:
                for i in range(displayed_count, current_count):
                    output = socket_server.outputs[i]
                    output_buffer += output

                    # Detect actual response (contains emoji circle or meaningful text)
                    if '⏺' in output or (len(output.strip()) > 20 and any(c.isalpha() for c in output)):
                        response_detected = True

                displayed_count = current_count
                last_output_time = time.time()

            # Send buffered output if:
            # 1. Response detected AND no new data for 1 second, OR
            # 2. No new data for 3 seconds (timeout)
            time_since_last = time.time() - last_output_time

            if output_buffer:
                if (response_detected and time_since_last > 1.0) or (time_since_last > 3.0):
                    # Add to UI
                    ui.add_remote_output(output_buffer)

                    # Record in Cross structure
                    cross_gen.add_assistant_message(output_buffer)

                    output_buffer = ""
                    response_detected = False

            time.sleep(0.1)

    relay_thread = threading.Thread(target=output_relay, daemon=True)
    relay_thread.start()

    # Welcome messages
    ui.add_message('system', f'✅ {llm_name} is connected via socket')
    ui.add_message('system', f'📋 Messages you type here will be sent to {llm_name}')
    ui.add_message('system', f'🔄 Responses will appear automatically')
    ui.add_message('system', f'🧠 Cross structure: {cross_file}')

    # Run UI
    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\n🛑 Shutting down...")
        cross_gen.stop()
        socket_server.stop()

        # Close Claude tab
        print("📌 Closing Claude tab...")
        launcher.cleanup()

        print("\nGoodbye! 👋\n")
        print(f"📌 Cross structure saved to: {cross_file}")
        print(f"📌 Don't forget to close the {llm_name} tab if needed")


def start_multi_agent_mode(project_path: Path, config: dict):
    """Start multi-agent mode"""
    from ..engine.multi_agent_controller import MultiAgentController
    from .multi_agent_ui import MultiAgentUI

    num_agents = config.get('num_agents', 2)
    llm_name = config['llm_type'].capitalize()
    launch_cmd = config['launch_command']

    # Enable debug logging
    verantyx_dir = project_path / '.verantyx'
    verantyx_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(verantyx_dir / 'multi_agent.log')
        ]
    )
    logger.info(f"=== Verantyx Multi-Agent Mode ({num_agents} agents) ===")

    print()
    print("=" * 70)
    print(f"  Launching {num_agents} {llm_name} Agents")
    print("=" * 70)
    print()

    # Create multi-agent controller
    controller = MultiAgentController(
        project_path=project_path,
        verantyx_dir=verantyx_dir,
        llm_command=launch_cmd
    )

    # Define agent configurations
    # Agent 0 is MASTER, others are sub-agents
    agent_configs = []

    # Agent 0: Master (controls others)
    agent_configs.append({
        'name': 'Master',
        'role': 'Master agent - controls and coordinates all sub-agents'
    })

    # Sub-agents (Agent 1+)
    sub_agent_roles = ["Analyzer", "Designer", "Implementer", "Tester", "Reviewer"]

    for i in range(1, num_agents):
        role_index = i - 1
        role = sub_agent_roles[role_index] if role_index < len(sub_agent_roles) else f"SubAgent_{i}"
        agent_configs.append({
            'name': role,
            'role': f'Sub-agent responsible for {role.lower()}'
        })

    # Create and launch agents
    print(f"🚀 Creating {num_agents} agents...")
    print()

    if not controller.create_agents(agent_configs):
        print("\n❌ Failed to create agents")
        return

    print()
    print("=" * 70)
    print(f"  ✅ All {num_agents} Agents Connected!")
    print("=" * 70)
    print()
    print("  Hierarchy:")
    print(f"    Agent 0 (Master) ← Controls all sub-agents")
    for i in range(1, num_agents):
        agent_name = agent_configs[i]['name']
        print(f"    Agent {i} ({agent_name}) ← Controlled by Master")
    print()

    # Load user profile for personality-aware coordination
    controller.load_user_profile()

    # Start multi-agent UI
    ui = MultiAgentUI(controller=controller, llm_name=llm_name)

    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    finally:
        # Save aggregate Cross structure
        aggregate_file = controller.save_aggregate_cross()
        print(f"\n📌 Aggregate Cross structure saved to: {aggregate_file}")

        # Stop all agents
        controller.stop_all_agents()
        print(f"📌 {num_agents} agents stopped")
        print(f"📌 Individual Cross structures saved:")
        for agent in controller.agents:
            print(f"   • Agent {agent.agent_id} ({agent.agent_name}): {agent.cross_file}")


def start_auto_mode(project_path: Path, goal: Optional[str] = None):
    """Start autonomous mode"""
    # TODO: Implement autonomous mode
    print("🚀 Autonomous mode")
    print(f"Project: {project_path}")
    print(f"Goal: {goal or '(will ask interactively)'}")
    print("\n(Implementation coming soon...)")


def start_browse_mode(project_path: Path):
    """Start file browser mode"""
    # TODO: Implement browse mode
    print("📁 Browse mode")
    print(f"Project: {project_path}")
    print("\n(Implementation coming soon...)")
