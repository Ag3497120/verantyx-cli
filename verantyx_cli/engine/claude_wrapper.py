#!/usr/bin/env python3
"""
Claude Wrapper - Wraps Claude Code and forwards I/O to Verantyx via socket

This script runs in the Claude tab and connects back to Verantyx-CLI.
All I/O is forwarded through socket communication.
"""

import os
import sys
import pty
import select
import socket
import threading
import time


class ClaudeWrapper:
    """
    Wrap Claude Code and forward I/O via socket

    Architecture:
    1. Launch Claude in PTY
    2. Connect to Verantyx socket server
    3. Forward Claude output → Verantyx
    4. Forward Verantyx input → Claude
    """

    def __init__(self, verantyx_host: str, verantyx_port: int, project_path: str):
        self.verantyx_host = verantyx_host
        self.verantyx_port = verantyx_port
        self.project_path = project_path

        # Socket connection to Verantyx
        self.sock: socket.socket = None

        # PTY for Claude
        self.master_fd = None
        self.claude_pid = None

        self.running = True

    def connect_to_verantyx(self) -> bool:
        """Connect to Verantyx socket server"""
        try:
            print(f"🔌 Connecting to Verantyx at {self.verantyx_host}:{self.verantyx_port}...")

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.verantyx_host, self.verantyx_port))

            print(f"✅ Connected to Verantyx")

            # Send handshake
            handshake = b"VERANTYX_CLAUDE_WRAPPER\n"
            self.sock.sendall(handshake)

            return True

        except Exception as e:
            print(f"❌ Failed to connect to Verantyx: {e}")
            return False

    def launch_claude(self) -> bool:
        """Launch Claude in PTY"""
        try:
            print(f"🚀 Launching Claude...")

            # Change to project directory
            os.chdir(self.project_path)

            # Create PTY and launch Claude
            self.claude_pid, self.master_fd = pty.fork()

            if self.claude_pid == 0:
                # Child process - exec Claude
                # Make sure output is visible
                os.environ['TERM'] = 'xterm-256color'
                os.execvp("claude", ["claude"])
                # Never reaches here if successful
            else:
                # Parent process - monitor I/O
                print(f"✅ Claude launched (PID: {self.claude_pid})")

                # Wait a bit for Claude to start
                time.sleep(1)

                # Check if Claude is still running
                import signal
                try:
                    os.kill(self.claude_pid, 0)  # Signal 0 just checks if process exists
                    print(f"✅ Claude process is running")
                except OSError:
                    print(f"❌ Claude process died immediately")
                    return False

                return True

        except Exception as e:
            print(f"❌ Failed to launch Claude: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self):
        """Main I/O forwarding loop"""
        print("🔄 Starting I/O forwarding...")
        print("📺 Claude output will be shown below:")
        print("=" * 70)

        try:
            while self.running:
                # Wait for I/O from Claude or Verantyx
                readable, _, _ = select.select(
                    [self.master_fd, self.sock],
                    [],
                    [],
                    0.1
                )

                # Forward Claude output → Verantyx AND display locally
                if self.master_fd in readable:
                    try:
                        data = os.read(self.master_fd, 4096)
                        if data:
                            # Display locally (so user can see Claude is working)
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()

                            # Also send to Verantyx via socket
                            message = b"OUTPUT:" + data
                            self.sock.sendall(message)
                        else:
                            # Claude closed
                            print("\n" + "=" * 70)
                            print("Claude closed")
                            break
                    except OSError as e:
                        print(f"\n❌ Error reading from Claude: {e}")
                        break

                # Forward Verantyx input → Claude
                if self.sock in readable:
                    try:
                        data = self.sock.recv(4096)
                        if data:
                            # Decode message
                            msg = data.decode('utf-8', errors='replace')

                            # Check for INPUT: prefix
                            if msg.startswith("INPUT:"):
                                # Extract input text (everything after "INPUT:" until newline)
                                input_text = msg[6:].rstrip('\n\r')

                                if input_text:
                                    # Send to Claude character by character (simulate typing)
                                    for char in input_text:
                                        os.write(self.master_fd, char.encode('utf-8'))
                                        time.sleep(0.01)  # Small delay between chars

                                    # Send Enter key
                                    os.write(self.master_fd, b'\r')

                                    print(f"\n📨 Sent to Claude: {input_text[:50]}...")
                        else:
                            # Verantyx closed
                            print("\n" + "=" * 70)
                            print("Verantyx closed")
                            break
                    except OSError as e:
                        print(f"\n❌ Error reading from socket: {e}")
                        break

        except KeyboardInterrupt:
            print("\n🛑 Wrapper interrupted")

        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up...")

        if self.sock:
            self.sock.close()

        if self.master_fd:
            os.close(self.master_fd)

        print("👋 Wrapper stopped")


def main():
    """Entry point"""
    if len(sys.argv) != 4:
        print("Usage: claude_wrapper.py <host> <port> <project_path>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    project_path = sys.argv[3]

    wrapper = ClaudeWrapper(host, port, project_path)

    # Connect to Verantyx
    if not wrapper.connect_to_verantyx():
        sys.exit(1)

    # Launch Claude
    if not wrapper.launch_claude():
        sys.exit(1)

    # Run I/O forwarding
    wrapper.run()


if __name__ == "__main__":
    main()
