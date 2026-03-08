#!/usr/bin/env python3
"""
Claude Wrapper - JCross Bridge

Executes claude_wrapper.jcross with Python extern functions for PTY and socket operations.
"""

import os
import sys
import pty
import select
import socket
from pathlib import Path


# Add kofdai_computer directory to path to import jcross interpreter
# verantyx_v6/
#   ├── verantyx-cli/
#   └── kofdai_computer/
verantyx_v6_dir = Path(__file__).parent.parent.parent.parent
kofdai_dir = verantyx_v6_dir / "kofdai_computer"

if not kofdai_dir.exists():
    print(f"❌ kofdai_computer directory not found: {kofdai_dir}")
    sys.exit(1)

sys.path.insert(0, str(kofdai_dir))

try:
    from jcross_typed_ir_compiler import TypedJCrossCompiler
except ImportError as e:
    print(f"❌ JCross interpreter not found: {e}")
    print(f"   Looking in: {kofdai_dir}")
    print(f"   Make sure jcross_typed_ir_compiler.py exists")
    sys.exit(1)


class ClaudeWrapperExterns:
    """External functions for .jcross wrapper"""

    def __init__(self):
        self.master_fd = None
        self.sock = None

    def pty_spawn(self, cmd: str) -> int:
        """Spawn process in PTY"""
        try:
            pid, master_fd = pty.fork()

            if pid == 0:
                # Child process
                os.execlp(cmd, cmd)
            else:
                # Parent process
                self.master_fd = master_fd
                return master_fd
        except Exception as e:
            print(f"❌ PTY spawn error: {e}")
            return -1

    def pty_write(self, fd: int, data: str) -> int:
        """Write to PTY"""
        try:
            encoded = data.encode('utf-8')
            return os.write(fd, encoded)
        except Exception as e:
            print(f"❌ PTY write error: {e}")
            return -1

    def socket_connect(self, host: str, port: int) -> int:
        """Connect to socket"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            self.sock = sock
            return sock.fileno()
        except Exception as e:
            print(f"❌ Socket connect error: {e}")
            return -1

    def socket_recv(self, sock_fd: int, size: int) -> str:
        """Receive from socket"""
        try:
            data = self.sock.recv(size)
            return data.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"❌ Socket recv error: {e}")
            return ""

    def socket_send(self, sock_fd: int, data: str) -> int:
        """Send to socket"""
        try:
            encoded = data.encode('utf-8')
            return self.sock.send(encoded)
        except Exception as e:
            print(f"❌ Socket send error: {e}")
            return -1

    def select_read(self, fds: list, timeout: float) -> list:
        """Select on file descriptors"""
        try:
            # Convert to actual file objects
            fd_list = [self.sock] if self.sock else []
            readable, _, _ = select.select(fd_list, [], [], timeout)
            return [fd.fileno() for fd in readable]
        except Exception as e:
            print(f"❌ Select error: {e}")
            return []

    def print_func(self, msg: str):
        """Print message"""
        print(msg, flush=True)


def main():
    """Run .jcross wrapper with Python extern functions"""

    if len(sys.argv) < 3:
        print("Usage: claude_wrapper_jcross_bridge.py <host> <port> [project_path]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    project_path = sys.argv[3] if len(sys.argv) > 3 else "."

    # Load .jcross wrapper
    jcross_file = Path(__file__).parent / "claude_wrapper.jcross"

    if not jcross_file.exists():
        print(f"❌ JCross wrapper not found: {jcross_file}")
        sys.exit(1)

    # Create extern functions
    externs = ClaudeWrapperExterns()

    # Register extern functions
    extern_funcs = {
        'pty_spawn': externs.pty_spawn,
        'pty_write': externs.pty_write,
        'socket_connect': externs.socket_connect,
        'socket_recv': externs.socket_recv,
        'socket_send': externs.socket_send,
        'select_read': externs.select_read,
        'print': externs.print_func,
    }

    # Compile and run .jcross
    try:
        with open(jcross_file, 'r') as f:
            source = f.read()

        compiler = TypedJCrossCompiler()
        ir = compiler.compile(source)

        # Execute with extern functions
        # Pass command line args as global variables
        ir.globals['host'] = host
        ir.globals['port'] = port
        ir.globals['project_path'] = project_path

        result = ir.execute(extern_funcs=extern_funcs)

        sys.exit(result if isinstance(result, int) else 0)

    except Exception as e:
        print(f"❌ JCross execution error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
