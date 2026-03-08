"""
Remote Chat UI - Remote desktop-style interface for monitoring Claude/Gemini

Shows real-time output from separate terminal's Claude/Gemini like a remote desktop.
"""

from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Label, RichLog
from textual.binding import Binding
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown


class RemoteChatPanel(ScrollableContainer):
    """
    Panel showing real-time output from Claude/Gemini running in separate terminal

    Acts like a remote desktop viewer - shows exactly what's happening in the other terminal.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages = []

    def add_remote_output(self, text: str):
        """Add output from remote Claude/Gemini"""
        self.messages.append({
            'type': 'remote',
            'content': text,
            'timestamp': datetime.now()
        })
        self._update_display()

    def add_user_input(self, text: str):
        """Add user input (sent to remote)"""
        self.messages.append({
            'type': 'user',
            'content': text,
            'timestamp': datetime.now()
        })
        self._update_display()

    def add_system_message(self, text: str):
        """Add system message"""
        self.messages.append({
            'type': 'system',
            'content': text,
            'timestamp': datetime.now()
        })
        self._update_display()

    def _update_display(self):
        """Update the display with all messages"""
        # Clear and rebuild
        self.remove_children()

        for msg in self.messages[-50:]:  # Show last 50 messages
            msg_type = msg['type']
            content = msg['content']
            timestamp = msg['timestamp'].strftime('%H:%M:%S')

            if msg_type == 'user':
                # User input
                widget = Static(
                    f"[bold cyan][{timestamp}] > {content}[/bold cyan]",
                    classes="user_message"
                )
            elif msg_type == 'remote':
                # Remote Claude/Gemini output
                widget = Static(
                    f"[{timestamp}] {content}",
                    classes="remote_message"
                )
            elif msg_type == 'system':
                # System message
                widget = Static(
                    f"[dim][{timestamp}] ℹ️  {content}[/dim]",
                    classes="system_message"
                )

            self.mount(widget)

        # Auto-scroll to bottom
        self.scroll_end(animate=False)


class CrossStatusPanel(Static):
    """Shows Cross monitoring status"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.monitoring_active = False
        self.messages_captured = 0
        self.cross_updates = 0
        self.compacting_detected = False

    def update_status(
        self,
        messages_captured: int = None,
        cross_updates: int = None,
        compacting_detected: bool = None
    ):
        """Update status display"""
        if messages_captured is not None:
            self.messages_captured = messages_captured
        if cross_updates is not None:
            self.cross_updates = cross_updates
        if compacting_detected is not None:
            self.compacting_detected = compacting_detected

        status_text = f"""
[bold]📊 Cross Monitoring Status[/bold]

🔵 Monitoring: [green]Active[/green]
📝 Messages captured: {self.messages_captured}
🔄 Cross updates: {self.cross_updates}
⚠️  Compacting detected: {'[red]Yes[/red]' if self.compacting_detected else '[dim]No[/dim]'}

[dim]Last update: {datetime.now().strftime('%H:%M:%S')}[/dim]
        """

        self.update(status_text.strip())


class RemoteChatApp(App):
    """
    Main remote chat application

    Shows Claude/Gemini running in separate terminal like a remote desktop.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-rows: 1fr auto;
    }

    Header {
        column-span: 2;
    }

    #remote_chat_panel {
        column-span: 1;
        row-span: 1;
        border: solid $primary;
        padding: 1;
        height: 100%;
    }

    #cross_status_panel {
        column-span: 1;
        row-span: 1;
        border: solid $accent;
        padding: 1;
        height: 100%;
    }

    #input_container {
        column-span: 2;
        dock: bottom;
        height: auto;
        padding: 1;
        border: solid $primary;
    }

    Input {
        width: 100%;
    }

    Footer {
        column-span: 2;
    }

    .user_message {
        background: $boost;
        margin: 1 0;
    }

    .remote_message {
        margin: 1 0;
    }

    .system_message {
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+s", "show_cross", "Show Cross"),
    ]

    def __init__(
        self,
        project_path: Path,
        llm_name: str,
        on_user_input: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.project_path = project_path
        self.llm_name = llm_name
        self.on_user_input = on_user_input

        self.chat_panel = None
        self.status_panel = None
        self.input_box = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # Left: Remote chat panel
        yield RemoteChatPanel(id="remote_chat_panel")

        # Right: Cross status panel
        yield CrossStatusPanel(id="cross_status_panel")

        # Bottom: Input
        with Container(id="input_container"):
            yield Label(f"💬 Chat with {self.llm_name} (via separate terminal)")
            yield Input(
                placeholder="Type your message... (sent to remote terminal)",
                id="chat_input"
            )

        yield Footer()

    def on_mount(self):
        """Initialize on mount"""
        self.title = f"Verantyx-CLI → {self.llm_name} (Remote Mode)"

        # Get widget references
        self.chat_panel = self.query_one("#remote_chat_panel", RemoteChatPanel)
        self.status_panel = self.query_one("#cross_status_panel", CrossStatusPanel)
        self.input_box = self.query_one("#chat_input", Input)

        # Welcome message
        self.chat_panel.add_system_message(
            f"Connected to {self.llm_name} running in separate terminal"
        )
        self.chat_panel.add_system_message(
            "Verantyx is monitoring all I/O transparently"
        )
        self.chat_panel.add_system_message(
            "Cross structure updating every 3 seconds"
        )

        # Update status
        self.status_panel.monitoring_active = True
        self.status_panel.update_status()

        # Focus input
        self.input_box.focus()

    def on_input_submitted(self, event: Input.Submitted):
        """Handle user input submission"""
        user_input = event.value.strip()

        if not user_input:
            return

        # Clear input
        self.input_box.value = ""

        # Add to chat panel
        self.chat_panel.add_user_input(user_input)

        # Send to callback (which sends to remote terminal)
        if self.on_user_input:
            self.on_user_input(user_input)

        # Update status
        self.status_panel.update_status(
            messages_captured=self.status_panel.messages_captured + 1
        )

    def add_remote_output(self, text: str):
        """Add output from remote Claude/Gemini"""
        self.chat_panel.add_remote_output(text)

        # Update status
        self.status_panel.update_status(
            messages_captured=self.status_panel.messages_captured + 1
        )

    def on_cross_update(self):
        """Called when Cross structure is updated"""
        self.status_panel.update_status(
            cross_updates=self.status_panel.cross_updates + 1
        )

    def on_compacting_detected(self):
        """Called when compacting is detected"""
        self.chat_panel.add_system_message(
            "[bold red]⚠️  Compacting detected! Swapping documents...[/bold red]"
        )
        self.status_panel.update_status(compacting_detected=True)

    def action_clear_chat(self):
        """Clear chat panel"""
        self.chat_panel.messages = []
        self.chat_panel._update_display()

    def action_show_cross(self):
        """Show Cross structure (placeholder)"""
        self.chat_panel.add_system_message(
            "📊 Cross structure: .verantyx/claude_monitor.cross.json"
        )
