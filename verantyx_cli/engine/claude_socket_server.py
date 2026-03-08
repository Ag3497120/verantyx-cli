"""
Claude Socket Server - Receive I/O from Claude wrapper via socket

Runs in Verantyx-CLI and communicates with Claude wrapper in separate tab.
"""

import logging
import socket
import threading
import time
from typing import Optional, Callable, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ClaudeSocketServer:
    """
    Socket server for communicating with Claude wrapper

    Architecture:
    1. Start socket server (random port)
    2. Wait for Claude wrapper to connect
    3. Receive OUTPUT: messages from wrapper
    4. Send INPUT: messages to wrapper
    """

    def __init__(
        self,
        on_output: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize socket server

        Args:
            on_output: Callback when Claude output is received
        """
        self.on_output = on_output

        # Socket server
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.server_port: Optional[int] = None

        # State
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._receiver_thread: Optional[threading.Thread] = None

        # Output buffer
        self.outputs: List[str] = []

    def start(self) -> tuple[str, int]:
        """
        Start socket server

        Returns:
            (host, port) tuple
        """
        try:
            # Create socket server
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to random available port
            self.server_socket.bind(('localhost', 0))
            self.server_port = self.server_socket.getsockname()[1]

            self.server_socket.listen(1)
            logger.info(f"Socket server listening on port {self.server_port}")

            # Start listener thread
            self._running = True
            self._listener_thread = threading.Thread(
                target=self._accept_connection,
                daemon=True
            )
            self._listener_thread.start()

            return ('localhost', self.server_port)

        except Exception as e:
            logger.error(f"Failed to start socket server: {e}")
            raise

    def _accept_connection(self):
        """Accept connection from Claude wrapper"""
        try:
            logger.info("Waiting for Claude wrapper to connect...")
            print("📡 Waiting for Claude wrapper to connect...")

            self.server_socket.settimeout(60.0)  # 60 second timeout

            self.client_socket, addr = self.server_socket.accept()
            logger.info(f"✅ Claude wrapper connected from {addr}")
            print(f"✅ Claude wrapper connected from {addr}")

            # Read handshake
            handshake = self.client_socket.recv(100)
            if handshake == b"VERANTYX_CLAUDE_WRAPPER\n":
                logger.info("Handshake successful")
                print("✅ Handshake successful")
            else:
                logger.warning(f"Invalid handshake: {handshake}")

            # Start receiving data
            self._receiver_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True
            )
            self._receiver_thread.start()

        except socket.timeout:
            logger.error("Timeout waiting for Claude wrapper connection")
            print("❌ Timeout waiting for Claude wrapper")
            print("   The wrapper script may not have started correctly")
        except Exception as e:
            logger.error(f"Error accepting connection: {e}")
            print(f"❌ Error accepting connection: {e}")

    def _receive_loop(self):
        """Receive data from Claude wrapper"""
        try:
            buffer = b""

            while self._running and self.client_socket:
                data = self.client_socket.recv(4096)

                if not data:
                    logger.info("Claude wrapper disconnected")
                    print("\n🔌 Claude wrapper disconnected")
                    break

                buffer += data

                # Process messages with OUTPUT: prefix
                while b"OUTPUT:" in buffer:
                    # Find the start of OUTPUT: marker
                    idx = buffer.find(b"OUTPUT:")

                    if idx == -1:
                        break

                    # Extract output data (everything after OUTPUT: until next marker or end)
                    output_start = idx + 7  # len("OUTPUT:")

                    # Find next marker
                    next_marker = buffer.find(b"OUTPUT:", output_start)

                    if next_marker == -1:
                        # No next marker - take everything
                        output_data = buffer[output_start:]
                        buffer = b""
                    else:
                        # Take until next marker
                        output_data = buffer[output_start:next_marker]
                        buffer = buffer[next_marker:]

                    # Process output
                    if output_data:
                        decoded = output_data.decode('utf-8', errors='replace')
                        self.outputs.append(decoded)

                        if self.on_output:
                            self.on_output(decoded)

        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            print(f"❌ Error in receive loop: {e}")

    def send_input(self, text: str):
        """Send input to Claude wrapper"""
        if not self.client_socket:
            logger.error("Cannot send: no connection to Claude wrapper")
            print("❌ Cannot send: no connection to Claude wrapper")
            return

        try:
            logger.info(f"Sending to Claude: {text[:50]}...")

            # Send text + newline all at once
            # Wrapper will send it character-by-character to Claude
            message = f"INPUT:{text}\n".encode('utf-8')
            self.client_socket.sendall(message)

            logger.info(f"✅ Sent: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send: {e}")
            print(f"❌ Failed to send: {e}")

    def is_connected(self) -> bool:
        """Check if wrapper is connected"""
        return self.client_socket is not None

    def stop(self):
        """Stop server"""
        self._running = False

        if self.client_socket:
            self.client_socket.close()

        if self.server_socket:
            self.server_socket.close()

        logger.info("Socket server stopped")
