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
        self.claude_pid = None  # Track Claude process ID

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

                # Get Claude PID for cleanup
                time.sleep(2)  # Wait for process to start
                self._get_claude_pid()

                if self.claude_pid:
                    print(f"   Process ID: {self.claude_pid}")
                    logger.info(f"Tracked {self.llm_command} PID: {self.claude_pid}")

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

    def cleanup(self):
        """
        Cleanup: Kill Claude process and close tab when Verantyx exits
        """
        try:
            # Step 1: Kill Claude process by PID if we have it
            if self.claude_pid:
                logger.info(f"Killing {self.llm_command} process (PID: {self.claude_pid})")
                try:
                    import signal
                    os.kill(self.claude_pid, signal.SIGTERM)
                    time.sleep(0.5)
                    # Force kill if still running
                    try:
                        os.kill(self.claude_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Already dead
                    logger.info(f"Process {self.claude_pid} killed")
                except ProcessLookupError:
                    logger.info(f"Process {self.claude_pid} already terminated")
                except Exception as e:
                    logger.error(f"Failed to kill process {self.claude_pid}: {e}")

            # Step 2: Kill any remaining Claude processes (fallback)
            self._kill_all_claude_processes()

            # Step 3: Close the terminal tab
            terminal_type = self._detect_terminal()
            logger.info(f"Closing {self.llm_command} tab in {terminal_type}")

            if terminal_type == "Terminal.app":
                self._close_terminal_app_tab()
            elif terminal_type == "iTerm":
                self._close_iterm_tab()

        except Exception as e:
            logger.error(f"Failed to cleanup: {e}")

    def _get_claude_pid(self):
        """Get the PID of the most recently started Claude process"""
        try:
            # Get all Claude processes sorted by start time (newest first)
            result = subprocess.run(
                ['pgrep', '-n', '-f', self.llm_command],  # -n = newest
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                self.claude_pid = int(result.stdout.strip())
                logger.info(f"Found {self.llm_command} PID: {self.claude_pid}")
            else:
                logger.warning(f"Could not find {self.llm_command} PID")

        except Exception as e:
            logger.error(f"Failed to get Claude PID: {e}")

    def _kill_all_claude_processes(self):
        """Kill all Claude processes (fallback cleanup)"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', self.llm_command],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                logger.info(f"Found {len(pids)} {self.llm_command} processes to kill")

                for pid in pids:
                    if pid.strip():
                        try:
                            subprocess.run(['kill', '-9', pid.strip()], check=False)
                            logger.info(f"Killed {self.llm_command} process: {pid}")
                        except Exception as e:
                            logger.error(f"Failed to kill process {pid}: {e}")
            else:
                logger.info(f"No {self.llm_command} processes found")

        except Exception as e:
            logger.error(f"Failed to kill Claude processes: {e}")

    def _close_terminal_app_tab(self):
        """Close the Claude tab in Terminal.app"""
        try:
            # Find and close the tab running Claude
            applescript = '''
            tell application "Terminal"
                set allWindows to every window
                repeat with aWindow in allWindows
                    set allTabs to every tab of aWindow
                    repeat with aTab in allTabs
                        set tabProcesses to processes of aTab
                        if tabProcesses contains "claude" then
                            close aTab
                            return
                        end if
                    end repeat
                end repeat
            end tell
            '''

            subprocess.run(['osascript', '-e', applescript], capture_output=True)
            logger.info("Closed Terminal.app tab running Claude")

        except Exception as e:
            logger.error(f"Failed to close Terminal.app tab: {e}")

    def _close_iterm_tab(self):
        """Close the Claude tab in iTerm"""
        try:
            # Find and close the tab running Claude
            applescript = '''
            tell application "iTerm"
                repeat with aWindow in windows
                    repeat with aTab in tabs of aWindow
                        set tabName to name of current session of aTab
                        if tabName contains "claude" then
                            close aTab
                            return
                        end if
                    end repeat
                end repeat
            end tell
            '''

            subprocess.run(['osascript', '-e', applescript], capture_output=True)
            logger.info("Closed iTerm tab running Claude")

        except Exception as e:
            logger.error(f"Failed to close iTerm tab: {e}")


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
