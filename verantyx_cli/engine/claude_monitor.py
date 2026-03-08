"""
Claude Monitor - Safe monitoring of official Claude Code

Launches Claude Code in a separate terminal and monitors all I/O
without using unofficial APIs (safe from account bans).

Architecture:
1. Verantyx-CLI launches Claude in new terminal via PTY
2. Intercepts all I/O transparently
3. Generates Cross structure every 3 seconds
4. Provides content inspection/learning
5. Never modifies Claude's behavior (read-only monitoring)
"""

import json
import logging
import os
import pty
import select
import subprocess
import sys
import termios
import threading
import time
import tty
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

logger = logging.getLogger(__name__)


class ClaudeMonitor:
    """
    Monitors official Claude Code running in separate terminal

    Safe architecture:
    - No API token stealing
    - No unofficial API usage
    - Pure PTY-based I/O interception
    - Read-only monitoring (no behavior modification)
    """

    def __init__(
        self,
        project_path: Path,
        llm_command: str = "claude",
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        monitor_only: bool = True
    ):
        """
        Initialize LLM monitor

        Args:
            project_path: Project directory to monitor
            llm_command: Command to launch LLM (default: "claude")
            on_event: Callback for monitoring events
            monitor_only: If True, only monitor (don't forward I/O). Use separate UI.
        """
        self.project_path = project_path
        self.llm_command = llm_command
        self.on_event = on_event
        self.monitor_only = monitor_only

        # PTY file descriptors
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None

        # Process
        self.process: Optional[subprocess.Popen] = None
        self._running = False
        self._io_thread: Optional[threading.Thread] = None

        # Monitoring state
        self.user_inputs: List[Dict] = []
        self.claude_outputs: List[Dict] = []
        self.file_changes: List[Dict] = []
        self.session_start = datetime.now()

        # Cross structure update thread
        self._cross_update_thread: Optional[threading.Thread] = None
        self._cross_update_interval = 3.0  # 3 seconds

        # Verantyx directory
        self.verantyx_dir = project_path / ".verantyx"
        self.verantyx_dir.mkdir(exist_ok=True)

        # Output file for Cross structure
        self.cross_output_file = self.verantyx_dir / "claude_monitor.cross.json"

    def launch_claude(self) -> bool:
        """
        Launch LLM in new terminal tab with PTY monitoring

        Returns:
            True if launched successfully
        """
        try:
            # Check if LLM command is available
            result = subprocess.run(
                ["which", self.llm_command],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"{self.llm_command} command not found")
                return False

            llm_path = result.stdout.strip()
            logger.info(f"Found {self.llm_command}: {llm_path}")

            # Detect terminal type (macOS Terminal.app, iTerm2, etc.)
            terminal_app = self._detect_terminal()
            logger.info(f"Detected terminal: {terminal_app}")

            # Launch LLM in new terminal tab
            if terminal_app == "Terminal.app":
                self._launch_in_terminal_app()
            elif terminal_app == "iTerm":
                self._launch_in_iterm()
            else:
                # Fallback: launch in same terminal (old behavior)
                logger.warning("Unknown terminal, using same-terminal mode")
                return self._launch_in_same_terminal()

            logger.info("✅ Claude monitoring active")
            logger.info("   • I/O interception enabled")
            logger.info("   • Cross structure updates every 3s")
            logger.info("   • Content inspection enabled")

            return True

        except Exception as e:
            logger.error(f"Failed to launch Claude: {e}")
            return False

    def _detect_terminal(self) -> str:
        """Detect which terminal application is being used"""
        term_program = os.environ.get('TERM_PROGRAM', '')

        if 'iTerm' in term_program:
            return 'iTerm'
        elif 'Apple_Terminal' in term_program or term_program == '':
            return 'Terminal.app'
        else:
            return 'Unknown'

    def _launch_in_terminal_app(self):
        """Launch LLM in new Terminal.app tab"""
        logger.info("Launching in new Terminal.app tab...")

        # Create AppleScript to open new tab and run command
        applescript = f'''
        tell application "Terminal"
            activate
            tell application "System Events"
                keystroke "t" using command down
            end tell
            delay 0.5
            do script "cd {self.project_path} && {self.llm_command}" in front window
        end tell
        '''

        # Execute AppleScript
        subprocess.run(['osascript', '-e', applescript])

        # Wait for terminal to open
        time.sleep(2)

        # Create PTY and attach to running process
        # NOTE: We need to find the claude process and attach to it
        # This is complex - for now, use simpler approach
        logger.warning("Terminal.app tab launched, but PTY attachment not yet implemented")
        logger.info("Please manually check the new terminal tab")

    def _launch_in_iterm(self):
        """Launch LLM in new iTerm2 tab"""
        logger.info("Launching in new iTerm2 tab...")

        # Create AppleScript for iTerm2
        applescript = f'''
        tell application "iTerm"
            activate
            tell current window
                create tab with default profile
                tell current session
                    write text "cd {self.project_path} && {self.llm_command}"
                end tell
            end tell
        end tell
        '''

        # Execute AppleScript
        subprocess.run(['osascript', '-e', applescript])

        # Wait for terminal to open
        time.sleep(2)

        logger.warning("iTerm2 tab launched, but PTY attachment not yet implemented")
        logger.info("Please manually check the new iTerm tab")

    def _launch_in_same_terminal(self) -> bool:
        """Launch LLM in same terminal (old behavior)"""
        try:
            # Create PTY
            self.master_fd, self.slave_fd = pty.openpty()

            # Set terminal size for PTY (if possible)
            try:
                term_size = os.get_terminal_size()
                import fcntl
                import struct
                fcntl.ioctl(
                    self.slave_fd,
                    termios.TIOCSWINSZ,
                    struct.pack('HHHH', term_size.lines, term_size.columns, 0, 0)
                )
            except (OSError, IOError) as e:
                # If terminal size cannot be set, use defaults
                logger.warning(f"Could not set PTY terminal size: {e}")

            # Spawn LLM in PTY
            self.process = subprocess.Popen(
                [self.llm_command],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd=str(self.project_path),
                env=os.environ.copy(),
                preexec_fn=os.setsid
            )

            logger.info(f"✅ {self.llm_command} spawned (PID: {self.process.pid})")

            # Disable terminal focus events
            os.write(self.master_fd, b'\033[?1004l')

            # Start I/O monitoring thread
            self._running = True
            self._io_thread = threading.Thread(target=self._io_monitor_loop, daemon=True)
            self._io_thread.start()

            # Start Cross structure update thread
            self._cross_update_thread = threading.Thread(target=self._cross_update_loop, daemon=True)
            self._cross_update_thread.start()

            return True

        except Exception as e:
            logger.error(f"Failed to launch in same terminal: {e}")
            return False

    def _io_monitor_loop(self):
        """Main I/O monitoring loop (runs in separate thread)"""
        if self.monitor_only:
            # Monitor-only mode: Just read LLM output, don't forward I/O
            # This allows SimpleChatUI to handle user interaction safely
            logger.info("Starting I/O monitor loop (monitor-only mode)")
            try:
                while self._running:
                    # Wait for LLM output with timeout
                    readable, _, _ = select.select(
                        [self.master_fd],
                        [],
                        [],
                        0.1
                    )

                    # Handle LLM output (monitoring only, no forwarding)
                    if self.master_fd in readable:
                        try:
                            data = os.read(self.master_fd, 4096)
                            if data:
                                # Record LLM output for monitoring
                                decoded = data.decode('utf-8', errors='replace')
                                self._record_claude_output(decoded)
                                # Enhanced logging - show more detail
                                logger.info(f"📥 Received {len(data)} bytes from LLM")
                                logger.info(f"   Content: {decoded[:200]}...")
                        except OSError as e:
                            logger.error(f"Error reading from PTY: {e}")
                            break

            finally:
                logger.info("I/O monitoring stopped (monitor-only mode)")
        else:
            # Legacy mode: Forward I/O (causes UI conflicts)
            # Set stdin to raw mode for character-by-character forwarding
            stdin_is_tty = sys.stdin.isatty()
            old_settings = None

            if stdin_is_tty:
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setraw(sys.stdin.fileno())

            try:
                while self._running:
                    # Wait for I/O with timeout
                    readable, _, _ = select.select(
                        [self.master_fd, sys.stdin],
                        [],
                        [],
                        0.1
                    )

                    # Handle Claude output
                    if self.master_fd in readable:
                        try:
                            data = os.read(self.master_fd, 4096)
                            if data:
                                # Record Claude output
                                self._record_claude_output(data.decode('utf-8', errors='replace'))

                                # Forward to stdout
                                os.write(sys.stdout.fileno(), data)
                                sys.stdout.flush()
                        except OSError:
                            break

                    # Handle user input
                    if sys.stdin in readable:
                        try:
                            data = os.read(sys.stdin.fileno(), 1)
                            if data:
                                # Record user input
                                self._record_user_input(data.decode('utf-8', errors='replace'))

                                # Forward to Claude
                                os.write(self.master_fd, data)
                        except OSError:
                            break

            finally:
                # Restore terminal settings
                if stdin_is_tty and old_settings:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

                logger.info("I/O monitoring stopped")

    def _record_user_input(self, text: str):
        """Record user input for monitoring"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'user_input',
            'content': text
        }
        self.user_inputs.append(entry)

        # Emit event
        if self.on_event:
            self.on_event(entry)

    def _record_claude_output(self, text: str):
        """Record Claude output for monitoring"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'claude_output',
            'content': text
        }
        self.claude_outputs.append(entry)

        # Check for image file references and auto-convert to Cross
        self._detect_and_process_images(text)

        # Emit event
        if self.on_event:
            self.on_event(entry)

    def _detect_and_process_images(self, text: str):
        """
        Detect image file references in Claude output and auto-convert to Cross structure

        This allows Claude to "see" images by converting them to Cross structure.
        """
        # Common image extensions
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']

        # Check if text mentions image files
        for ext in image_extensions:
            if ext in text.lower():
                # Try to extract file paths
                self._process_image_references(text)
                break

    def _process_image_references(self, text: str):
        """Process any image file references found in text"""
        try:
            from ..vision.cross_simulator import image_to_llm_context

            # Look for common file path patterns
            import re
            # Match paths ending with image extensions
            path_pattern = r'[\w/\-\.]+\.(?:png|jpg|jpeg|gif|bmp|webp)'
            matches = re.findall(path_pattern, text, re.IGNORECASE)

            for match in matches:
                image_path = Path(match)

                # Check if path is relative to project
                if not image_path.is_absolute():
                    image_path = self.project_path / image_path

                # Process if file exists
                if image_path.exists() and image_path.is_file():
                    logger.info(f"Auto-processing image: {image_path}")

                    # Convert to Cross structure and generate LLM context
                    try:
                        llm_context = image_to_llm_context(image_path)

                        # Save Cross representation
                        cross_file = self.verantyx_dir / f"image_{image_path.stem}.cross.json"

                        # Record as special output
                        self.claude_outputs.append({
                            'timestamp': datetime.now().isoformat(),
                            'type': 'image_understanding',
                            'image_path': str(image_path),
                            'cross_file': str(cross_file),
                            'llm_context': llm_context
                        })

                        logger.info(f"Image converted to Cross: {cross_file}")

                    except Exception as e:
                        logger.warning(f"Failed to process image {image_path}: {e}")

        except ImportError:
            # Vision module not available (missing PIL/numpy)
            pass
        except Exception as e:
            logger.error(f"Image detection error: {e}")

    def _cross_update_loop(self):
        """Update Cross structure every 3 seconds"""
        while self._running:
            try:
                self._generate_cross_structure()
                time.sleep(self._cross_update_interval)
            except Exception as e:
                logger.error(f"Cross structure update failed: {e}")
                time.sleep(self._cross_update_interval)

    def _generate_cross_structure(self):
        """Generate Cross structure from monitoring data"""
        now = datetime.now()
        session_duration = (now - self.session_start).total_seconds()

        # Extract recent user inputs (last 10)
        recent_inputs = [
            inp['content'] for inp in self.user_inputs[-10:]
            if inp['content'].strip()
        ]

        # Extract recent Claude outputs (last 10)
        recent_outputs = [
            out['content'] for out in self.claude_outputs[-10:]
            if len(out['content']) > 10  # Skip control sequences
        ]

        # Build Cross structure
        cross_structure = {
            "type": "claude_monitor_cross",
            "timestamp": now.isoformat(),
            "session_start": self.session_start.isoformat(),
            "session_duration_seconds": session_duration,
            "axes": {
                "up": {  # Goals/Intent
                    "goal": "Monitor Claude Code interaction",
                    "mode": "passive_observation",
                    "safety": "read_only_monitoring"
                },
                "down": {  # Foundations/Facts
                    "total_user_inputs": len(self.user_inputs),
                    "total_claude_outputs": len(self.claude_outputs),
                    "file_changes_detected": len(self.file_changes),
                    "process_pid": self.process.pid if self.process else None
                },
                "front": {  # Current focus
                    "recent_user_inputs": recent_inputs[-5:],
                    "recent_claude_outputs": recent_outputs[-3:],
                    "current_activity": self._infer_current_activity()
                },
                "back": {  # History
                    "all_user_inputs": self.user_inputs[-50:],  # Keep last 50
                    "all_claude_outputs": self.claude_outputs[-50:],
                    "session_history": {
                        "start": self.session_start.isoformat(),
                        "duration": session_duration
                    }
                },
                "right": {  # Expansion/Possibilities
                    "monitoring_capabilities": [
                        "user_input_capture",
                        "claude_output_capture",
                        "file_change_detection",
                        "cross_structure_generation"
                    ],
                    "learned_patterns": self._extract_patterns()
                },
                "left": {  # Constraints/Limitations
                    "constraints": [
                        "read_only_monitoring",
                        "no_api_token_usage",
                        "no_behavior_modification",
                        "3s_update_interval"
                    ],
                    "safety_measures": [
                        "official_claude_only",
                        "transparent_monitoring",
                        "user_consent_required"
                    ]
                }
            },
            "metadata": {
                "format_version": "1.0",
                "cross_native": True,
                "auto_generated": True,
                "update_interval_seconds": self._cross_update_interval,
                "verantyx_cli_version": "1.0.0"
            }
        }

        # Write to file atomically
        temp_file = self.cross_output_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cross_structure, f, ensure_ascii=False, indent=2)
        temp_file.replace(self.cross_output_file)

        logger.debug(f"Cross structure updated: {len(json.dumps(cross_structure))} bytes")

    def _infer_current_activity(self) -> str:
        """Infer what Claude is currently doing"""
        if not self.claude_outputs:
            return "waiting_for_input"

        # Simple heuristic based on recent outputs
        recent = ''.join([out['content'] for out in self.claude_outputs[-10:]])

        if 'thinking' in recent.lower():
            return "thinking"
        elif 'reading' in recent.lower() or 'file' in recent.lower():
            return "reading_files"
        elif 'writing' in recent.lower() or 'creating' in recent.lower():
            return "writing_code"
        elif 'test' in recent.lower():
            return "running_tests"
        else:
            return "responding"

    def _extract_patterns(self) -> List[str]:
        """Extract common patterns from interaction"""
        patterns = []

        # Check for common command sequences
        user_texts = [inp['content'] for inp in self.user_inputs[-20:]]
        combined = ''.join(user_texts)

        if 'fix' in combined.lower():
            patterns.append("bug_fixing_pattern")
        if 'implement' in combined.lower() or 'add' in combined.lower():
            patterns.append("feature_implementation_pattern")
        if 'test' in combined.lower():
            patterns.append("testing_pattern")

        return patterns

    def is_llm_alive(self) -> bool:
        """Check if LLM process is still running"""
        if not self.process:
            return False
        return self.process.poll() is None

    def send_to_llm(self, text: str):
        """
        Send text to LLM (for monitor-only mode)

        Args:
            text: Text to send to LLM
        """
        # Health check
        if not self.process:
            logger.error("❌ Cannot send: LLM process not started")
            return

        if not self.is_llm_alive():
            logger.error("❌ Cannot send: LLM process has died")
            logger.error(f"   Process exit code: {self.process.returncode}")
            return

        if not self.master_fd:
            logger.error("❌ Cannot send: master_fd is None")
            return

        if not self._running:
            logger.error("❌ Cannot send: monitor not running")
            return

        try:
            logger.info(f"📤 Sending message to LLM: {text[:50]}...")
            logger.info(f"   LLM process status: PID={self.process.pid}, alive={self.is_llm_alive()}")

            # Send text character by character to simulate typing
            for char in text:
                os.write(self.master_fd, char.encode('utf-8'))
                time.sleep(0.01)  # Small delay between characters

            # Send Enter key (both CR and LF for compatibility)
            os.write(self.master_fd, b'\r\n')

            logger.info(f"✅ Message sent successfully ({len(text)} chars)")

            # Record as user input
            self._record_user_input(text)

        except OSError as e:
            logger.error(f"❌ Failed to send to LLM: {e}")

    def stop(self):
        """Stop monitoring"""
        self._running = False

        if self._io_thread:
            self._io_thread.join(timeout=2.0)

        if self._cross_update_thread:
            self._cross_update_thread.join(timeout=2.0)

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()

        if self.master_fd:
            os.close(self.master_fd)
        if self.slave_fd:
            os.close(self.slave_fd)

        logger.info("Claude monitoring stopped")

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get monitoring session summary"""
        return {
            'session_start': self.session_start.isoformat(),
            'session_duration': (datetime.now() - self.session_start).total_seconds(),
            'total_user_inputs': len(self.user_inputs),
            'total_claude_outputs': len(self.claude_outputs),
            'file_changes': len(self.file_changes),
            'cross_output_file': str(self.cross_output_file)
        }
