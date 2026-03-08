"""
Multi-Agent UI - Interface for controlling multiple Claude agents

Provides UI for:
- Viewing all agents
- Sending input to specific agent or broadcast to all
- Viewing agent outputs
- Monitoring Cross structures
"""

import sys
import termios
import tty
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..engine.multi_agent_controller import MultiAgentController


class MultiAgentUI:
    """
    Multi-Agent UI using two-layer terminal structure

    Top layer: Agent outputs and status
    Bottom layer: Fixed input area with agent selection
    """

    def __init__(
        self,
        controller: MultiAgentController,
        llm_name: str
    ):
        self.controller = controller
        self.llm_name = llm_name
        self.running = True

        # UI state
        self.selected_agent = -1  # -1 = broadcast to all, 0+ = specific agent
        self.current_input = ""

        # Display tracking
        self.displayed_outputs: Dict[int, int] = {}  # agent_id -> num_displayed

        # Loading indicator
        self.waiting_for_response = False
        self.loading_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.loading_index = 0

    def print_header(self):
        """Print header"""
        print("\n" + "=" * 70)
        print(f"  Verantyx Multi-Agent Control ({len(self.controller.agents)} agents)")
        print("=" * 70)
        print()

    def print_agent_status(self):
        """Print status of all agents"""
        print("  🤖 Agents:")
        for agent in self.controller.agents:
            status_icon = "✅" if agent.running else "❌"
            msg_count = len(agent.messages)
            print(f"    [{agent.agent_id}] {agent.agent_name} {status_icon} ({msg_count} msgs)")
        print()

    def display_agent_output(self, agent_id: int, output: str):
        """Display output from specific agent"""
        agent = self.controller.agents[agent_id]
        timestamp = datetime.now().strftime('%H:%M:%S')

        print(f"\n🤖 Agent {agent_id} ({agent.agent_name}) [{timestamp}]:\n")

        # Clean and display
        import re

        # Remove ANSI escape sequences
        cleaned = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', output)
        cleaned = re.sub(r'\x1b\]0;[^\x07\x1b]*(\x07|\x1b\\)', '', cleaned)

        # Remove Claude UI elements
        cleaned = re.sub(r'^[─\s]{10,}$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^\s*>\s*\w{0,3}\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^\s*[✻✽✶✳✢·]\s*\w+….*$', '', cleaned, flags=re.MULTILINE)

        # Keep meaningful lines
        lines = cleaned.split('\n')
        meaningful_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line and len(stripped_line) > 2:
                if any(c.isalnum() for c in stripped_line):
                    meaningful_lines.append(line.rstrip())

        cleaned = '\n'.join(meaningful_lines)
        stripped = cleaned.strip()

        if len(stripped) >= 15:
            for line in stripped.split('\n'):
                print(f"  {line}")
            print()

    def update_input_area(self):
        """Update fixed input area at bottom"""
        # Save cursor and move to bottom
        sys.stdout.write("\033[s")  # Save cursor
        sys.stdout.write("\033[999;0H")  # Move to bottom
        sys.stdout.write("\033[3A")  # Move up 3 lines
        sys.stdout.write("\033[J")  # Clear to end of screen
        sys.stdout.flush()

        # Print separator
        print("─" * 70)

        # Print status line
        if self.waiting_for_response:
            print(f"{self.loading_chars[self.loading_index]} Waiting for agent responses...")
            self.loading_index = (self.loading_index + 1) % len(self.loading_chars)
        else:
            if self.selected_agent == -1:
                target = "ALL AGENTS"
            else:
                target = f"Agent {self.selected_agent}"
            print(f"Target: {target} | Tab: Switch | Enter: Send | Esc: Cancel | Ctrl+C: Quit")

        # Print input line
        if self.selected_agent == -1:
            prompt = "> [BROADCAST] "
        else:
            prompt = f"> [Agent {self.selected_agent}] "

        print(f"{prompt}{self.current_input}", end="", flush=True)

        # Restore cursor
        sys.stdout.write("\033[u")
        sys.stdout.flush()

    def switch_agent(self):
        """Switch to next agent (Tab key)"""
        self.selected_agent += 1
        if self.selected_agent >= len(self.controller.agents):
            self.selected_agent = -1  # Back to broadcast
        self.update_input_area()

    def send_input(self, text: str):
        """Send input to selected agent(s) with intelligent routing"""
        if not text.strip():
            return

        timestamp = datetime.now().strftime('%H:%M:%S')

        # Use intelligent routing if not explicitly targeting
        if self.selected_agent == -1:
            # Let routing layer decide
            print(f"\n👤 You [INTELLIGENT ROUTING] ({timestamp}): {text}\n")
            routing_result = self.controller.send_with_routing(text)

            # Show routing decision
            targets = routing_result['target_agents']
            routing_info = routing_result['routing_decision']

            if routing_info['extracted_agent_refs']:
                print(f"🔀 Detected agent reference: {routing_info['extracted_agent_refs']}")
                print(f"📍 Routing to: Agent(s) {targets}")
            elif routing_info['command_type'] == 'broadcast':
                print(f"📢 Broadcasting to all agents")
            else:
                print(f"🎯 Routing to: Master (Agent 0)")
            print()
        else:
            # Explicit targeting - send directly
            print(f"\n👤 You → Agent {self.selected_agent} ({timestamp}): {text}\n")
            self.controller.send_to_agent(self.selected_agent, text)

        self.waiting_for_response = True
        self.update_input_area()

    def run(self):
        """Run multi-agent UI"""
        self.print_header()
        self.print_agent_status()

        print("  💡 Tips:")
        print("    - Agent 0 is the MASTER agent (controls others)")
        print("    - Say '2番のエージェント' to route to Agent 2")
        print("    - Tab: Manually switch target agent")
        print("    - Intelligent routing detects agent references automatically")
        print("    - Each agent has its own Cross structure with progress tracking")
        print()

        # Reserve space for input area
        print("\n" * 3, end="")

        # Initialize displayed output tracking
        for agent in self.controller.agents:
            self.displayed_outputs[agent.agent_id] = 0

        # Get terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            # Set raw mode
            tty.setraw(fd)

            self.update_input_area()

            # Start output monitoring thread
            update_thread_running = True

            def monitor_outputs():
                """Monitor outputs from all agents"""
                while update_thread_running and self.running:
                    any_new_output = False

                    for agent in self.controller.agents:
                        outputs = agent.get_outputs()
                        displayed_count = self.displayed_outputs.get(agent.agent_id, 0)

                        if len(outputs) > displayed_count:
                            # New outputs available
                            for i in range(displayed_count, len(outputs)):
                                output = outputs[i]
                                self.display_agent_output(agent.agent_id, output)
                                agent.add_assistant_message(output)
                                any_new_output = True

                            self.displayed_outputs[agent.agent_id] = len(outputs)

                    if any_new_output:
                        self.waiting_for_response = False
                        self.update_input_area()

                    # Update loading animation
                    if self.waiting_for_response:
                        self.update_input_area()

                    time.sleep(0.2)

            monitor_thread = threading.Thread(target=monitor_outputs, daemon=True)
            monitor_thread.start()

            # Main input loop
            while self.running:
                # Read one character
                char = sys.stdin.read(1)

                # Handle Escape key
                if char == '\x1b':
                    try:
                        next_char = sys.stdin.read(1)
                        if next_char == '[':
                            arrow = sys.stdin.read(1)
                            # Ignore arrow keys
                            continue
                        else:
                            # Pure Esc - cancel input
                            self.current_input = ""
                            self.update_input_area()
                            continue
                    except:
                        continue

                # Handle Ctrl+C
                elif char == '\x03':
                    update_thread_running = False
                    print("\n\nStopping all agents... 👋\n")
                    break

                # Handle Tab
                elif char == '\t':
                    self.switch_agent()

                # Handle Enter
                elif char in ['\r', '\n']:
                    if self.current_input.strip():
                        user_input = self.current_input.strip()
                        self.current_input = ""

                        # Handle commands
                        if user_input.lower() in ['quit', 'exit', 'q']:
                            update_thread_running = False
                            print("\n\nStopping all agents... 👋\n")
                            break

                        # Send input
                        self.send_input(user_input)
                    else:
                        self.update_input_area()

                # Handle Backspace
                elif char in ['\x7f', '\x08']:
                    if self.current_input:
                        self.current_input = self.current_input[:-1]
                        self.update_input_area()

                # Handle regular characters
                elif char.isprintable():
                    self.current_input += char
                    self.update_input_area()

            update_thread_running = False

        except Exception as e:
            print(f"\n\nError: {e}\n")

        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            self.running = False
            print("\n")
