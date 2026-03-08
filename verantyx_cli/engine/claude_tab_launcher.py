"""
Claude Tab Launcher - Simple launcher for Claude in new terminal tab

Opens a new terminal tab and runs Claude directly.
No PTY, no socket - just visual verification that Claude is running.
"""

import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ClaudeTabLauncher:
    """
    Launch Claude in new terminal tab

    Simple approach:
    1. Open new terminal tab
    2. Run 'claude' command in that tab
    3. User can see Claude running in separate tab
    4. Verantyx-CLI runs in original tab
    """

    def __init__(
        self,
        project_path: Path,
        llm_command: str = "claude",
        socket_host: str = "localhost",
        socket_port: int = 0
    ):
        """
        Initialize launcher

        Args:
            project_path: Project directory
            llm_command: Command to launch (claude, gemini, etc.)
            socket_host: Socket server host
            socket_port: Socket server port
        """
        self.project_path = project_path
        self.llm_command = llm_command
        self.socket_host = socket_host
        self.socket_port = socket_port

    def launch(self) -> bool:
        """
        Launch LLM in new terminal tab

        Returns:
            True if launched successfully
        """
        try:
            # Check if command exists
            result = subprocess.run(
                ["which", self.llm_command],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"{self.llm_command} command not found")
                print(f"❌ {self.llm_command} command not found in PATH")
                print(f"   Please install {self.llm_command} first")
                return False

            llm_path = result.stdout.strip()
            logger.info(f"Found {self.llm_command}: {llm_path}")

            # Detect terminal type
            terminal_type = self._detect_terminal()
            logger.info(f"Detected terminal: {terminal_type}")

            print(f"🚀 Launching {self.llm_command} in new terminal tab...")

            # Open new tab based on terminal type
            if terminal_type == "Terminal.app":
                success = self._open_terminal_app_tab()
            elif terminal_type == "iTerm":
                success = self._open_iterm_tab()
            else:
                print(f"❌ Unsupported terminal: {terminal_type}")
                print("   Please use Terminal.app or iTerm2")
                return False

            if success:
                print(f"✅ {self.llm_command} launched in new tab")
                print(f"   Check the new tab to confirm {self.llm_command} is running")
                print()
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Failed to launch: {e}")
            print(f"❌ Failed to launch: {e}")
            return False

    def _detect_terminal(self) -> str:
        """Detect which terminal is being used"""
        term_program = os.environ.get('TERM_PROGRAM', '')

        if 'iTerm' in term_program:
            return 'iTerm'
        elif 'Apple_Terminal' in term_program or term_program == '':
            return 'Terminal.app'
        else:
            return 'Unknown'

    def _get_wrapper_command(self) -> str:
        """Get command to run wrapper script"""
        import sys

        # Get path to wrapper script
        wrapper_script = Path(__file__).parent / "claude_wrapper.py"

        # Use same Python as Verantyx
        python_cmd = sys.executable

        # Build command
        cmd = f"{python_cmd} '{wrapper_script}' {self.socket_host} {self.socket_port} '{self.project_path}'"

        return cmd

    def _open_terminal_app_tab(self) -> bool:
        """Open new Terminal.app tab and run command"""
        try:
            # Get wrapper command
            wrapper_cmd = self._get_wrapper_command()

            # AppleScript to open new tab and run command
            applescript = f'''
            tell application "Terminal"
                activate
                tell application "System Events"
                    keystroke "t" using command down
                end tell
                delay 0.5
                do script "{wrapper_cmd}" in front window
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"AppleScript failed: {result.stderr}")
                return False

            # Wait for tab to open
            time.sleep(1)
            return True

        except Exception as e:
            logger.error(f"Failed to open Terminal.app tab: {e}")
            return False

    def _open_iterm_tab(self) -> bool:
        """Open new iTerm2 tab and run command"""
        try:
            # Get wrapper command
            wrapper_cmd = self._get_wrapper_command()

            # AppleScript for iTerm2
            applescript = f'''
            tell application "iTerm"
                activate
                tell current window
                    create tab with default profile
                    tell current session
                        write text "{wrapper_cmd}"
                    end tell
                end tell
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"AppleScript failed: {result.stderr}")
                return False

            # Wait for tab to open
            time.sleep(1)
            return True

        except Exception as e:
            logger.error(f"Failed to open iTerm tab: {e}")
            return False


def launch_claude_in_new_tab(
    project_path: Path,
    llm_command: str = "claude",
    socket_host: str = "localhost",
    socket_port: int = 0
) -> bool:
    """
    Helper function to launch Claude in new tab

    Args:
        project_path: Project directory
        llm_command: Command to launch
        socket_host: Socket server host
        socket_port: Socket server port

    Returns:
        True if successful
    """
    launcher = ClaudeTabLauncher(project_path, llm_command, socket_host, socket_port)
    return launcher.launch()
