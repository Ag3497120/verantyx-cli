"""
Verantyx Processors - Cross Native System Functions

VerantyxのためのCrossプロセッサ群。
PTY、ソケット、ファイルシステム操作などをCross構造で提供。
"""

import os
import sys
import pty
import select
import socket
from typing import Any, Dict, Optional

# kofdai_computer のカーネルをインポート
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'kofdai_computer')))
from kernel import Axis


class VerantyxProcessors:
    """
    Verantyx用のプロセッサ集合

    JCrossプログラムから呼び出される「実行する system.xxx = {...}」に対応
    """

    def __init__(self):
        # プロセス状態
        self.pty_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.socket_fd: Optional[socket.socket] = None

    # ═══════════════════════════════════════════════════════════════
    # PTY Operations
    # ═══════════════════════════════════════════════════════════════

    def pty_spawn(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        PTYでプロセスを起動

        Args:
            params = {
                "command": "claude",
                "args": [],
                "working_dir": "."
            }

        Returns:
            {
                "success": 1 or 0,
                "pty_fd": int,
                "pid": int
            }
        """
        try:
            command = params.get('command', 'claude')
            working_dir = params.get('working_dir', '.')

            # ディレクトリ変更
            original_dir = os.getcwd()
            if working_dir and working_dir != '.':
                os.chdir(working_dir)

            # PTYフォーク
            pid, master_fd = pty.fork()

            if pid == 0:
                # 子プロセス - Claudeを実行
                os.execlp(command, command)
            else:
                # 親プロセス
                os.chdir(original_dir)
                self.pty_fd = master_fd
                self.pid = pid

                return {
                    'success': 1,
                    'pty_fd': master_fd,
                    'pid': pid
                }

        except Exception as e:
            print(f"❌ PTY spawn error: {e}", file=sys.stderr, flush=True)
            return {
                'success': 0,
                'error': str(e)
            }

    def pty_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        PTYに書き込み

        Args:
            params = {
                "pty_fd": int (optional, uses self.pty_fd if not provided),
                "data": str
            }

        Returns:
            {
                "success": 1 or 0,
                "bytes_written": int
            }
        """
        try:
            pty_fd = params.get('pty_fd', self.pty_fd)
            data = params.get('data', '')

            if pty_fd is None:
                return {'success': 0, 'error': 'No PTY FD available'}

            encoded = data.encode('utf-8')
            bytes_written = os.write(pty_fd, encoded)

            return {
                'success': 1,
                'bytes_written': bytes_written
            }

        except Exception as e:
            print(f"❌ PTY write error: {e}", file=sys.stderr, flush=True)
            return {
                'success': 0,
                'error': str(e)
            }

    # ═══════════════════════════════════════════════════════════════
    # Socket Operations
    # ═══════════════════════════════════════════════════════════════

    def socket_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        ソケットに接続

        Args:
            params = {
                "host": "localhost",
                "port": 52749
            }

        Returns:
            {
                "success": 1 or 0,
                "socket_fd": int
            }
        """
        try:
            host = params.get('host', 'localhost')
            port = params.get('port', 52749)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            self.socket_fd = sock

            return {
                'success': 1,
                'socket_fd': sock.fileno()
            }

        except Exception as e:
            print(f"❌ Socket connect error: {e}", file=sys.stderr, flush=True)
            return {
                'success': 0,
                'error': str(e)
            }

    def socket_recv(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        ソケットから受信

        Args:
            params = {
                "socket_fd": int (optional),
                "buffer_size": 4096,
                "timeout": 1.0
            }

        Returns:
            {
                "success": 1 or 0,
                "data": str
            }
        """
        try:
            buffer_size = params.get('buffer_size', 4096)
            timeout = params.get('timeout', 1.0)

            if self.socket_fd is None:
                return {'success': 0, 'error': 'No socket available', 'data': ''}

            # selectでタイムアウト付き受信
            readable, _, _ = select.select([self.socket_fd], [], [], timeout)

            if readable:
                data = self.socket_fd.recv(buffer_size)
                decoded = data.decode('utf-8', errors='replace')

                return {
                    'success': 1,
                    'data': decoded
                }
            else:
                # タイムアウト - 空文字列を返す
                return {
                    'success': 1,
                    'data': ''
                }

        except Exception as e:
            print(f"❌ Socket recv error: {e}", file=sys.stderr, flush=True)
            return {
                'success': 0,
                'error': str(e),
                'data': ''
            }

    # ═══════════════════════════════════════════════════════════════
    # String Operations (JCrossから使用)
    # ═══════════════════════════════════════════════════════════════

    def string_length(self, params: Dict[str, Any]) -> int:
        """文字列の長さを返す"""
        s = params.get('string', '')
        return len(s)

    def string_slice(self, params: Dict[str, Any]) -> str:
        """文字列をスライス"""
        s = params.get('string', '')
        start = params.get('start', 0)
        end = params.get('end', None)

        if end is None:
            return s[start:]
        else:
            return s[start:end]

    def string_trim(self, params: Dict[str, Any]) -> str:
        """文字列をトリム（前後の空白削除）"""
        s = params.get('string', '')
        return s.strip()

    def string_concat(self, params: Dict[str, Any]) -> str:
        """文字列を結合"""
        a = params.get('a', '')
        b = params.get('b', '')
        return str(a) + str(b)

    def string_startswith(self, params: Dict[str, Any]) -> int:
        """文字列が指定のプレフィックスで始まるか"""
        s = params.get('string', '')
        prefix = params.get('prefix', '')
        return 1 if s.startswith(prefix) else 0


# ═══════════════════════════════════════════════════════════════
# Processor Registration Helper
# ═══════════════════════════════════════════════════════════════

def get_verantyx_processors():
    """
    Verantyxプロセッサ辞書を取得

    JCrossから「実行する system.pty_spawn = {...}」のように呼び出せる

    Returns:
        Dict[str, callable]: プロセッサ名 -> 関数の辞書
    """
    proc_instance = VerantyxProcessors()

    return {
        'system.pty_spawn': proc_instance.pty_spawn,
        'system.pty_write': proc_instance.pty_write,
        'system.socket_connect': proc_instance.socket_connect,
        'system.socket_recv': proc_instance.socket_recv,
        'system.string_length': proc_instance.string_length,
        'system.string_slice': proc_instance.string_slice,
        'system.string_trim': proc_instance.string_trim,
        'system.string_concat': proc_instance.string_concat,
        'system.string_startswith': proc_instance.string_startswith,
    }
