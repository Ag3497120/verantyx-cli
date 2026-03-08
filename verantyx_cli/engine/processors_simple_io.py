"""
Simple IO Processors - Uses VM variables for all I/O

Pure design: Processors read from/write to VM variables
No parameters needed in JSON
"""

import os
import pty
import socket
import select

# Global socket registry
_SOCKETS = {}


def pty_fork_claude(params: dict) -> dict:
    """Fork Claude process in PTY"""
    command = params.get('command', 'claude')

    pid, master_fd = pty.fork()

    if pid == 0:
        # Child process
        os.execlp(command, command)

    # Parent - return result
    return {
        'pty_fd': master_fd,
        'pid': pid
    }


def socket_connect_literal(params: dict) -> dict:
    """Connect to localhost:52749 (literal for testing)"""
    vm_vars = params.get('__vm_vars__', {})

    # Read from VM variables if available, else use literals
    host = vm_vars.get('host', 'localhost')
    port = vm_vars.get('port', 52749)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    _SOCKETS[sock.fileno()] = sock

    return {'socket_fd': sock.fileno()}


def socket_recv_from_var(params: dict) -> dict:
    """Receive from socket (reads FD from VM vars)"""
    vm_vars = params.get('__vm_vars__', {})

    # Read socket FD from VM variables
    socket_fd = vm_vars.get('verantyx_fd')
    if socket_fd is None:
        return {'data': '', 'has_data': 0}

    size = 4096
    timeout = 1.0

    sock = _SOCKETS.get(socket_fd)
    if not sock:
        return {'data': '', 'has_data': 0}

    # Select with timeout
    readable, _, _ = select.select([sock], [], [], timeout)

    if readable:
        data = sock.recv(size)
        decoded = data.decode('utf-8', errors='replace')
        return {'data': decoded, 'has_data': 1}

    return {'data': '', 'has_data': 0}


def check_input_prefix(params: dict) -> dict:
    """Check if message starts with INPUT:"""
    vm_vars = params.get('__vm_vars__', {})

    message = vm_vars.get('check_msg', '')

    result = 1 if message.startswith('INPUT:') else 0

    return {'result': result}


def process_and_send_to_claude(params: dict) -> dict:
    """Process message and send to Claude"""
    vm_vars = params.get('__vm_vars__', {})

    message = vm_vars.get('message', '')
    claude_fd = vm_vars.get('claude_fd')

    if not message or claude_fd is None:
        return {}

    # Strip "INPUT:" prefix
    if message.startswith('INPUT:'):
        input_text = message[6:].strip()

        if input_text:
            # Send to Claude
            encoded = input_text.encode('utf-8')
            os.write(claude_fd, encoded)
            os.write(claude_fd, b'\r')  # Enter key

    return {}


def get_simple_io_processors():
    """Return simple processors that use VM variables"""
    return {
        'io.pty_fork': pty_fork_claude,
        'io.socket_connect_literal': socket_connect_literal,
        'io.socket_recv_from_var': socket_recv_from_var,
        'io.check_input_prefix': check_input_prefix,
        'io.process_and_send_to_claude': process_and_send_to_claude,
    }
