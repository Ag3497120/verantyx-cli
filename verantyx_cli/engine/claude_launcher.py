"""
Claude Launcher - Launch Claude in new terminal tab (macOS)

Launches Claude Code in a separate terminal tab and establishes
socket-based communication instead of PTY.
"""

import json
import logging
import os
import socket
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

logger = logging.getLogger(__name__)


class ClaudeLauncher:
    """
    Launch Claude in new terminal tab and communicate via socket

    Architecture:
    1. Verantyx-CLI creates socket server
    2. Opens new terminal tab with Claude
    3. Claude connects back to socket server
    4. Bidirectional communication via socket
    """

    def __init__(
        self,
        project_path: Path,
        llm_command: str = "claude",
        on_output: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize Claude launcher

        Args:
            project_path: Project directory
            llm_command: Command to launch LLM
            on_output: Callback for LLM output
        """
        self.project_path = project_path
        self.llm_command = llm_command
        self.on_output = on_output

        # Socket server
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.server_port: Optional[int] = None

        # Monitoring
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self.outputs: List[str] = []

        # Verantyx directory
        self.verantyx_dir = project_path / ".verantyx"
        self.verantyx_dir.mkdir(exist_ok=True)

    def launch(self) -> bool:
        """
        Launch Claude in new terminal tab

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
                return False

            # Create socket server
            if not self._create_socket_server():
                logger.error("Failed to create socket server")
                return False

            # Detect terminal type
            terminal_type = self._detect_terminal()
            logger.info(f"Detected terminal: {terminal_type}")

            # Open new terminal tab
            if terminal_type == "Terminal.app":
                self._open_terminal_app_tab()
            elif terminal_type == "iTerm":
                self._open_iterm_tab()
            else:
                logger.error(f"Unsupported terminal: {terminal_type}")
                return False

            logger.info(f"✅ {self.llm_command} launched in new tab")
            logger.info(f"   Socket server listening on port {self.server_port}")

            return True

        except Exception as e:
            logger.error(f"Failed to launch: {e}")
            return False

    def _create_socket_server(self) -> bool:
        """Create socket server for communication"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to random available port
            self.server_socket.bind(('localhost', 0))
            self.server_port = self.server_socket.getsockname()[1]

            self.server_socket.listen(1)
            logger.info(f"Socket server created on port {self.server_port}")

            # Start listener thread
            self._running = True
            self._listener_thread = threading.Thread(
                target=self._accept_connection,
                daemon=True
            )
            self._listener_thread.start()

            return True

        except Exception as e:
            logger.error(f"Failed to create socket server: {e}")
            return False

    def _accept_connection(self):
        """Accept connection from Claude wrapper"""
        try:
            logger.info("Waiting for Claude to connect...")
            self.server_socket.settimeout(30.0)  # 30 second timeout

            self.client_socket, addr = self.server_socket.accept()
            logger.info(f"✅ Claude connected from {addr}")

            # Start receiving data
            self._receive_loop()

        except socket.timeout:
            logger.error("Timeout waiting for Claude connection")
        except Exception as e:
            logger.error(f"Error accepting connection: {e}")

    def _receive_loop(self):
        """Receive data from Claude"""
        try:
            buffer = ""

            while self._running and self.client_socket:
                data = self.client_socket.recv(4096)

                if not data:
                    logger.info("Claude disconnected")
                    break

                decoded = data.decode('utf-8', errors='replace')
                buffer += decoded

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)

                    if line.strip():
                        self.outputs.append(line)

                        if self.on_output:
                            self.on_output(line)

        except Exception as e:
            logger.error(f"Error in receive loop: {e}")

    def _detect_terminal(self) -> str:
        """Detect terminal type"""
        term_program = os.environ.get('TERM_PROGRAM', '')

        if 'iTerm' in term_program:
            return 'iTerm'
        elif 'Apple_Terminal' in term_program or term_program == '':
            return 'Terminal.app'
        else:
            return 'Unknown'

    def _open_terminal_app_tab(self):
        """Open new Terminal.app tab with Claude"""
        # Create wrapper script that connects to socket
        wrapper_script = self._create_wrapper_script()

        # AppleScript to open new tab
        applescript = f'''
        tell application "Terminal"
            activate
            tell application "System Events"
                keystroke "t" using command down
            end tell
            delay 0.5
            do script "{wrapper_script}" in front window
        end tell
        '''

        subprocess.run(['osascript', '-e', applescript])
        logger.info("Opened new Terminal.app tab")

    def _open_iterm_tab(self):
        """Open new iTerm2 tab with Claude"""
        wrapper_script = self._create_wrapper_script()

        applescript = f'''
        tell application "iTerm"
            activate
            tell current window
                create tab with default profile
                tell current session
                    write text "{wrapper_script}"
                end tell
            end tell
        end tell
        '''

        subprocess.run(['osascript', '-e', applescript])
        logger.info("Opened new iTerm2 tab")

    def _create_wrapper_script(self) -> str:
        """Create wrapper script that runs Claude and forwards I/O to socket"""
        # For now, just return the command to run Claude directly
        # In future, we can create a Python wrapper that captures I/O
        return f"cd {self.project_path} && {self.llm_command}"

    def send(self, text: str):
        """Send text to Claude"""
        if not self.client_socket:
            logger.error("Cannot send: no connection to Claude")
            return

        try:
            message = text + '\n'
            self.client_socket.sendall(message.encode('utf-8'))
            logger.info(f"Sent to Claude: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send: {e}")

    def stop(self):
        """Stop launcher"""
        self._running = False

        if self.client_socket:
            self.client_socket.close()

        if self.server_socket:
            self.server_socket.close()

        logger.info("Launcher stopped")
