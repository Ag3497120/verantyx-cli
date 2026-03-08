"""
Simple Chat UI - Safe terminal-based chat interface

Zero-dependency implementation using only standard Python libraries.
No Textual, no raw mode, no ANSI escape sequences.
Works perfectly with Japanese IME.

Fixed input bar at bottom like Claude Code.
"""

import json
import sys
import termios
import tty
import threading
import time
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from ..utils.output_filter import filter_llm_output
from .image_chat_handler import ImageChatHandler


class SimpleChatUI:
    """
    Simple chat UI using standard print/input

    Safe for:
    - Japanese IME
    - All terminal environments
    - Remote monitoring
    """

    def __init__(
        self,
        llm_name: str,
        on_user_input: Optional[Callable[[str], None]] = None,
        cross_file: Optional[Path] = None,
        verantyx_dir: Optional[Path] = None
    ):
        self.llm_name = llm_name
        self.on_user_input = on_user_input
        self.running = True
        self.cross_file = cross_file

        # Message history
        self.messages = []
        self.max_display = 10  # Show last 10 messages

        # Status
        self.status = {
            'monitoring': True,
            'messages_captured': 0,
            'cross_updates': 0,
            'compacting_detected': False
        }

        # Loading indicator
        self.waiting_for_response = False
        self.loading_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.loading_index = 0

        # Cross memory cache
        self.cross_data = None
        self.cross_last_updated = None

        # Display lock to prevent scrolling during input
        self.input_in_progress = False

        # Image chat handler
        if verantyx_dir:
            self.image_handler = ImageChatHandler(verantyx_dir)
        else:
            self.image_handler = None

    def print_header(self):
        """Print chat header"""
        print("\n" + "=" * 70)
        print(f"  Verantyx-CLI → {self.llm_name} (Remote Mode)")
        print("=" * 70)
        print()

    def load_cross_data(self):
        """Load Cross memory data if available"""
        if self.cross_file and self.cross_file.exists():
            try:
                with open(self.cross_file, 'r', encoding='utf-8') as f:
                    self.cross_data = json.load(f)
                    self.cross_last_updated = datetime.now()
            except (json.JSONDecodeError, IOError):
                self.cross_data = None

    def print_status(self):
        """Print current status and Cross memory info"""
        print()
        print("  📊 Status:")
        print(f"    Monitoring: {'✅ Active' if self.status['monitoring'] else '❌ Inactive'}")
        print(f"    Messages: {self.status['messages_captured']}")
        print(f"    Cross updates: {self.status['cross_updates']}")
        if self.status['compacting_detected']:
            print(f"    ⚠️  Compacting detected!")
        print()

        # Load latest Cross data
        self.load_cross_data()

        # Display Cross memory summary
        if self.cross_data:
            print("  🧠 Cross Memory:")
            axes = self.cross_data.get('axes', {})

            # Show current activity
            front = axes.get('front', {})
            current_activity = front.get('current_activity', 'unknown')
            print(f"    Current: {current_activity}")

            # Show statistics
            down = axes.get('down', {})
            total_inputs = down.get('total_user_inputs', 0)
            total_outputs = down.get('total_claude_outputs', 0)
            print(f"    I/O: {total_inputs} in / {total_outputs} out")

            # Show learned patterns
            right = axes.get('right', {})
            patterns = right.get('learned_patterns', [])
            if patterns:
                print(f"    Patterns: {', '.join(patterns[:3])}")

            print()

        print("  💡 Tips:")
        print("    - Press Enter to send message")
        print("    - Type 'refresh' to update display")
        print("    - Type 'quit' to exit")
        if self.image_handler and self.image_handler.vision_available:
            print("    - Type '/image <path>' or paste image path to convert")
            print("    - Type '/help image' for image conversion help")
        print()

    def display_latest_response(self):
        """Display only the latest assistant response"""
        if not self.messages:
            return

        # Find the last assistant message
        for msg in reversed(self.messages):
            if msg['type'] == 'assistant':
                timestamp = msg['timestamp'].strftime('%H:%M:%S')
                content = msg['content']

                # Print response to chat area
                print(f"\n🤖 {self.llm_name} ({timestamp}):\n")
                # Print full response
                for line in content.split('\n'):
                    print(f"  {line}")
                print()

                # Update input area
                self.update_input_area()
                break

    def add_message(self, msg_type: str, content: str):
        """Add message to history"""
        self.messages.append({
            'type': msg_type,
            'content': content,
            'timestamp': datetime.now()
        })
        self.status['messages_captured'] += 1

        # If assistant message received, stop waiting and display
        if msg_type == 'assistant':
            self.waiting_for_response = False
            # Display the response immediately
            self.display_latest_response()

    def update_status(self, **kwargs):
        """Update status"""
        self.status.update(kwargs)

    def display(self):
        """Display current state - simplified, no screen clearing"""
        # Just print the latest messages, don't clear screen
        pass  # Will be called manually when needed

    def save_cursor_and_clear_input_area(self):
        """Save cursor, move to input area, and clear it"""
        # Save current cursor position
        sys.stdout.write("\033[s")
        # Move to last 3 lines (input area)
        sys.stdout.write("\033[999;0H")  # Move to bottom
        sys.stdout.write("\033[3A")  # Move up 3 lines
        # Clear from cursor to end of screen
        sys.stdout.write("\033[J")
        sys.stdout.flush()

    def restore_cursor(self):
        """Restore cursor to saved position"""
        sys.stdout.write("\033[u")
        sys.stdout.flush()

    def update_input_area(self, current_input="", status_msg=""):
        """Update the fixed input area at bottom"""
        # Save current position
        self.save_cursor_and_clear_input_area()

        # Print separator
        print("─" * 70)

        # Print status line
        if status_msg:
            print(status_msg)
        elif self.waiting_for_response:
            # Animate waiting indicator
            print(f"{self.loading_chars[self.loading_index]} Waiting for {self.llm_name} response... (Press Esc to stop)")
            self.loading_index = (self.loading_index + 1) % len(self.loading_chars)
        else:
            print(f"Messages: {len(self.messages)} | Enter: Send | Esc: Cancel | Ctrl+C: Quit")

        # Print input line
        print(f"> {current_input}", end="", flush=True)

        # Restore cursor to chat area
        self.restore_cursor()

    def run(self):
        """Run chat UI - Two-layer mode (chat area + fixed input area)"""
        # Print welcome message
        print("\n" + "=" * 70)
        print(f"  Verantyx-CLI → {self.llm_name}")
        print("=" * 70)
        print()

        # Reserve space for input area (3 lines at bottom)
        print("\n" * 3, end="")

        # Get terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            # Set raw mode for character-by-character input
            tty.setraw(fd)

            current_input = ""
            self.update_input_area(current_input)

            # Start input area update thread
            import threading
            update_thread_running = True

            def update_input_thread():
                while update_thread_running and self.running:
                    if self.waiting_for_response:
                        self.update_input_area(current_input)
                    time.sleep(0.2)  # Update loading animation

            input_thread = threading.Thread(target=update_input_thread, daemon=True)
            input_thread.start()

            while self.running:
                # Read one character
                char = sys.stdin.read(1)

                # Handle Escape key
                if char == '\x1b':
                    # Try to read escape sequence
                    try:
                        next_char = sys.stdin.read(1)
                        if next_char == '[':
                            arrow = sys.stdin.read(1)
                            # Ignore arrow keys
                            continue
                        else:
                            # Pure Esc - cancel input or stop response
                            if self.waiting_for_response:
                                self.waiting_for_response = False
                                # Print to chat area
                                print("\n⚠️  Response stopped by user\n")
                            else:
                                current_input = ""
                            self.update_input_area(current_input)
                            continue
                    except:
                        continue

                # Handle Ctrl+C
                elif char == '\x03':
                    update_thread_running = False
                    print("\n\nGoodbye! 👋\n")
                    break

                # Handle Enter
                elif char in ['\r', '\n']:
                    if current_input.strip():
                        user_input = current_input.strip()
                        current_input = ""

                        # Handle commands
                        if user_input.lower() in ['quit', 'exit', 'q']:
                            update_thread_running = False
                            print("\n\nGoodbye! 👋\n")
                            break

                        # Handle help command
                        if user_input.lower() == '/help image':
                            if self.image_handler:
                                print(f"\n{self.image_handler.get_help_text()}\n")
                            else:
                                print("\n❌ Image support not initialized\n")
                            self.update_input_area(current_input)
                            continue

                        # Process input (check for images)
                        processed_input = user_input
                        if self.image_handler:
                            processed_input, cross_structure = self.image_handler.process_input(user_input)

                            # If image was converted, print the conversion info
                            if cross_structure:
                                print(f"\n🖼️  Image Conversion:\n")
                                for line in processed_input.split('\n'):
                                    print(f"  {line}")
                                print()

                        # Add user message
                        self.add_message('user', processed_input)

                        # Print user message to chat area (if not already printed above)
                        if not (self.image_handler and cross_structure):
                            print(f"\n👤 You: {user_input}\n")

                        # Send to callback if available
                        if self.on_user_input:
                            # Set waiting flag (expecting remote response)
                            self.waiting_for_response = True
                            self.update_input_area(current_input)
                            # Send processed input (with image info if applicable)
                            self.on_user_input(processed_input)
                        else:
                            # No remote connection - just echo locally
                            print(f"  (Message recorded locally - Claude is in separate tab)\n")
                            self.update_input_area(current_input)

                    else:
                        # Empty input
                        self.update_input_area(current_input)

                # Handle Backspace
                elif char in ['\x7f', '\x08']:
                    if current_input:
                        current_input = current_input[:-1]
                        self.update_input_area(current_input)

                # Handle regular characters
                elif char.isprintable():
                    current_input += char
                    self.update_input_area(current_input)

            update_thread_running = False

        except Exception as e:
            print(f"\n\nError: {e}\n")

        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            self.running = False
            print("\n")

    def add_remote_output(self, text: str):
        """Add output from remote LLM"""
        import re
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"📥 Raw output ({len(text)} chars): {text[:200]}...")

        # Remove ALL ANSI escape sequences (including CSI, OSC, etc.)
        # CSI sequences
        cleaned = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', text)
        # OSC sequences (]0;...BEL or ]0;...ESC\)
        cleaned = re.sub(r'\x1b\]0;[^\x07\x1b]*(\x07|\x1b\\)', '', cleaned)
        cleaned = re.sub(r'\]0;[^\x07\x1b]*(\x07|\x1b\\)', '', cleaned)
        # Other escape sequences
        cleaned = re.sub(r'\x1b[^\x1b]*', '', cleaned)

        # Remove control characters except newlines
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', cleaned)

        # Remove Claude UI elements
        # Remove separators (any line with mostly ─)
        cleaned = re.sub(r'^[─\s]{10,}$', '', cleaned, flags=re.MULTILINE)
        # Remove prompt lines ("> " alone or with minimal content)
        cleaned = re.sub(r'^\s*>\s*\w{0,3}\s*$', '', cleaned, flags=re.MULTILINE)
        # Remove "? for shortcuts" and similar
        cleaned = re.sub(r'^\s*\?\s*for\s+shortcuts.*$', '', cleaned, flags=re.MULTILINE)
        # Remove "Thinking on/off"
        cleaned = re.sub(r'^\s*Thinking\s+(on|off).*$', '', cleaned, flags=re.MULTILINE)
        # Remove loading/status messages
        cleaned = re.sub(r'^\s*[✻✽✶✳✢·]\s*\w+….*$', '', cleaned, flags=re.MULTILINE)

        # Remove empty lines and lines with only whitespace
        lines = cleaned.split('\n')
        meaningful_lines = []
        for line in lines:
            stripped_line = line.strip()
            # Keep only lines with meaningful content
            if stripped_line and len(stripped_line) > 2:
                # Must have at least one alphanumeric character
                if any(c.isalnum() for c in stripped_line):
                    meaningful_lines.append(line.rstrip())

        # Rejoin with single newlines
        cleaned = '\n'.join(meaningful_lines)

        # Remove excessive newlines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        logger.info(f"✨ Cleaned output ({len(cleaned)} chars): {cleaned[:200]}...")

        # Only keep if it has meaningful content
        stripped = cleaned.strip()

        # Skip if empty
        if not stripped:
            logger.warning(f"❌ Filtered out (empty after cleaning)")
            return

        # Skip if too short (likely UI fragment)
        if len(stripped) < 15:
            logger.warning(f"❌ Filtered out (too short: {len(stripped)} chars)")
            return

        # Skip if it doesn't contain the response marker ⏺
        # This ensures we only show actual Claude responses
        if '⏺' not in text:
            # Allow through if it has substantial content (more than 50 chars)
            if len(stripped) < 50:
                logger.warning(f"❌ Filtered out (no response marker and short)")
                return

        logger.info(f"✅ Adding to chat: {stripped[:100]}...")
        self.add_message('assistant', cleaned)

    def on_cross_update(self):
        """Called when Cross structure updates"""
        self.status['cross_updates'] += 1

    def on_compacting_detected(self):
        """Called when compacting detected"""
        self.status['compacting_detected'] = True
        self.add_message('system', '⚠️  Compacting detected! Documents swapped.')


def start_simple_chat(
    llm_name: str,
    on_user_input: Optional[Callable[[str], None]] = None
):
    """
    Start simple chat UI

    Args:
        llm_name: Name of LLM
        on_user_input: Callback for user input
    """
    ui = SimpleChatUI(llm_name, on_user_input)
    ui.add_message('system', f'Connected to {llm_name}')
    ui.add_message('system', 'Monitoring all I/O transparently')

    # Run UI
    ui.run()

    return ui
