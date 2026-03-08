"""
Setup Wizard - Interactive LLM selection with arrow keys

Provides beautiful setup flow:
1. LLM provider selection (arrow keys)
2. Mode selection (subscription vs API)
3. Configuration input
"""

from pathlib import Path
from typing import Optional, Dict, Any, List

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, Center, VerticalScroll
from textual.widgets import Header, Footer, Static, Button, Input, Label, OptionList
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.screen import Screen


class LLMSelectionScreen(Screen):
    """LLM selection screen with arrow key navigation"""

    CSS = """
    LLMSelectionScreen {
        align: center middle;
    }

    #selection_container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 2;
        background: $surface;
    }

    .title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }

    .description {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    OptionList {
        height: 15;
        margin: 1;
        border: solid $primary;
    }

    #button_container {
        align: center middle;
        margin-top: 2;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_llm = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Center():
            with Vertical(id="selection_container"):
                yield Label(
                    "🚀 Verantyx-CLI Setup",
                    classes="title"
                )
                yield Label(
                    "Select your LLM provider (↑↓ arrows, Enter to select)",
                    classes="description"
                )

                # LLM options
                yield OptionList(
                    Option("Claude (Anthropic)", id="claude"),
                    Option("Gemini (Google)", id="gemini"),
                    Option("Codex (OpenAI)", id="codex"),
                    Option("─" * 40, id="separator", disabled=True),
                    Option("Claude API (requires API key)", id="claude_api"),
                    Option("Gemini API (requires API key)", id="gemini_api"),
                    Option("OpenAI API (requires API key)", id="openai_api"),
                    id="llm_list"
                )

                with Horizontal(id="button_container"):
                    yield Button("Cancel", id="cancel_button", variant="default")
                    yield Button("Next →", id="next_button", variant="primary")

        yield Footer()

    def on_mount(self):
        """Focus the option list on mount"""
        self.query_one("#llm_list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """Handle LLM selection"""
        if event.option.id != "separator":
            self.selected_llm = event.option.id
            # Auto-advance to next step
            self.dismiss({"llm": self.selected_llm})

    def on_button_pressed(self, event: Button.Pressed):
        """Handle button clicks"""
        if event.button.id == "cancel_button":
            self.dismiss(None)
        elif event.button.id == "next_button":
            # Get current selection
            option_list = self.query_one("#llm_list", OptionList)
            if option_list.highlighted is not None:
                selected = option_list.get_option_at_index(option_list.highlighted)
                if selected.id != "separator":
                    self.dismiss({"llm": selected.id})

    def action_cancel(self):
        """Cancel setup"""
        self.dismiss(None)


class ModeSelectionScreen(Screen):
    """Mode selection screen (subscription vs API)"""

    CSS = """
    ModeSelectionScreen {
        align: center middle;
    }

    #mode_container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 2;
        background: $surface;
    }

    .title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }

    .description {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    OptionList {
        height: 10;
        margin: 1;
        border: solid $primary;
    }

    #button_container {
        align: center middle;
        margin-top: 2;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, llm_name: str, **kwargs):
        super().__init__(**kwargs)
        self.llm_name = llm_name

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Center():
            with Vertical(id="mode_container"):
                yield Label(
                    f"🤖 {self.llm_name.upper()} Configuration",
                    classes="title"
                )
                yield Label(
                    "How do you want to use this LLM?",
                    classes="description"
                )

                # Mode options
                yield OptionList(
                    Option(
                        f"🚀 Launch {self.llm_name} CLI (subscription required)",
                        id="subscription"
                    ),
                    Option(
                        f"🔑 Use {self.llm_name} API (requires API key)",
                        id="api"
                    ),
                    id="mode_list"
                )

                with Horizontal(id="button_container"):
                    yield Button("← Back", id="back_button", variant="default")
                    yield Button("Next →", id="next_button", variant="primary")

        yield Footer()

    def on_mount(self):
        self.query_one("#mode_list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """Handle mode selection"""
        self.dismiss({"mode": event.option.id})

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back_button":
            self.dismiss({"back": True})
        elif event.button.id == "next_button":
            option_list = self.query_one("#mode_list", OptionList)
            if option_list.highlighted is not None:
                selected = option_list.get_option_at_index(option_list.highlighted)
                self.dismiss({"mode": selected.id})


class ConfigInputScreen(Screen):
    """Configuration input screen"""

    CSS = """
    ConfigInputScreen {
        align: center middle;
    }

    #config_container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 2;
        background: $surface;
    }

    .title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }

    .label {
        margin-top: 1;
        margin-bottom: 1;
    }

    .hint {
        color: $text-muted;
        margin-bottom: 2;
    }

    Input {
        margin-bottom: 2;
    }

    #button_container {
        align: center middle;
        margin-top: 2;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, llm_name: str, mode: str, **kwargs):
        super().__init__(**kwargs)
        self.llm_name = llm_name
        self.mode = mode

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Center():
            with Vertical(id="config_container"):
                yield Label(
                    f"⚙️  {self.llm_name.upper()} Configuration",
                    classes="title"
                )

                if self.mode == "subscription":
                    yield Label(
                        f"Enter the command to launch {self.llm_name}:",
                        classes="label"
                    )
                    yield Label(
                        f"💡 Example: {self.llm_name}",
                        classes="hint"
                    )
                    yield Input(
                        placeholder=f"{self.llm_name}",
                        value=self.llm_name,
                        id="config_input"
                    )
                    yield Label(
                        f"✨ {self.llm_name.capitalize()} will launch in a separate terminal",
                        classes="hint"
                    )
                else:  # API mode
                    yield Label(
                        f"Enter your {self.llm_name.upper()} API key:",
                        classes="label"
                    )
                    yield Label(
                        "🔒 Your API key will be stored securely",
                        classes="hint"
                    )
                    yield Input(
                        placeholder="sk-...",
                        password=True,
                        id="config_input"
                    )

                with Horizontal(id="button_container"):
                    yield Button("← Back", id="back_button", variant="default")
                    yield Button("🚀 Launch", id="launch_button", variant="success")

        yield Footer()

    def on_mount(self):
        self.query_one("#config_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back_button":
            self.dismiss({"back": True})
        elif event.button.id == "launch_button":
            input_value = self.query_one("#config_input", Input).value
            if input_value:
                self.dismiss({"config": input_value})

    def on_input_submitted(self, event: Input.Submitted):
        """Handle Enter key in input"""
        if event.value:
            self.dismiss({"config": event.value})


class SetupWizardApp(App):
    """Main setup wizard application"""

    def __init__(self, project_path: Path, **kwargs):
        super().__init__(**kwargs)
        self.project_path = project_path
        self.config: Optional[Dict[str, Any]] = None

    def on_mount(self):
        self.title = "Verantyx-CLI Setup"
        self.run_setup()

    def run_setup(self):
        """Run the setup wizard flow"""
        # Step 1: LLM Selection
        self.push_screen(LLMSelectionScreen(), self.handle_llm_selection)

    def handle_llm_selection(self, result):
        """Handle LLM selection result"""
        if result is None:
            # User cancelled
            self.exit()
            return

        llm = result["llm"]
        llm_name = llm.replace("_api", "")

        # Determine if API mode
        if llm.endswith("_api"):
            mode = "api"
        else:
            # Step 2: Mode Selection
            self.push_screen(
                ModeSelectionScreen(llm_name),
                lambda r: self.handle_mode_selection(r, llm_name)
            )
            return

        # Direct to config for API mode
        self.push_screen(
            ConfigInputScreen(llm_name, mode),
            lambda r: self.handle_config_input(r, llm_name, mode)
        )

    def handle_mode_selection(self, result, llm_name: str):
        """Handle mode selection result"""
        if result is None or result.get("back"):
            # Go back to LLM selection
            self.run_setup()
            return

        mode = result["mode"]

        # Step 3: Config Input
        self.push_screen(
            ConfigInputScreen(llm_name, mode),
            lambda r: self.handle_config_input(r, llm_name, mode)
        )

    def handle_config_input(self, result, llm_name: str, mode: str):
        """Handle config input result"""
        if result is None or result.get("back"):
            # Go back to mode selection
            self.push_screen(
                ModeSelectionScreen(llm_name),
                lambda r: self.handle_mode_selection(r, llm_name)
            )
            return

        config_value = result["config"]

        # Build final config
        self.config = {
            "llm_type": llm_name,
            "llm_mode": mode,
            "launch_command": config_value if mode == "subscription" else None,
            "api_key": config_value if mode == "api" else None
        }

        # Exit and return config
        self.exit()


def run_setup_wizard(project_path: Path) -> Dict[str, Any]:
    """
    Run setup wizard and return configuration

    Returns:
        Configuration dict with user's choices
    """
    app = SetupWizardApp(project_path=project_path)
    app.run()

    if app.config:
        return app.config
    else:
        # Default config if user cancelled
        return {
            "llm_type": "claude",
            "llm_mode": "subscription",
            "launch_command": "claude",
            "api_key": None
        }
