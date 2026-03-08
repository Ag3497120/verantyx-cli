#!/usr/bin/env python3
"""
JCross Native Wrapper Runner

日本語JCrossで書かれたClaudeラッパーを実行します。
"""

import os
import sys
import pty
import select
import socket
from pathlib import Path

# JCrossインタプリタをインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "kofdai_computer"))

from jcross_ir_compiler import CrossIRCompiler


class SystemFunctions:
    """JCrossから呼び出されるsystem.*関数"""

    def __init__(self):
        self.pty_fd = None
        self.socket_fd = None
        self.pid = None

    def pty_spawn(self, params: dict) -> dict:
        """PTYでプロセスを起動"""
        try:
            command = params.get('command', 'claude')
            working_dir = params.get('working_dir', '.')

            # ディレクトリ変更
            original_dir = os.getcwd()
            os.chdir(working_dir)

            pid, master_fd = pty.fork()

            if pid == 0:
                # 子プロセス
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
            print(f"❌ PTY spawn error: {e}", flush=True)
            return {'success': 0, 'error': str(e)}

    def pty_write(self, params: dict) -> dict:
        """PTYに書き込み"""
        try:
            pty_fd = params.get('pty_fd', self.pty_fd)
            data = params.get('data', '')

            encoded = data.encode('utf-8')
            bytes_written = os.write(pty_fd, encoded)

            return {
                'success': 1,
                'bytes_written': bytes_written
            }
        except Exception as e:
            print(f"❌ PTY write error: {e}", flush=True)
            return {'success': 0, 'error': str(e)}

    def socket_connect(self, params: dict) -> dict:
        """ソケットに接続"""
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
            print(f"❌ Socket connect error: {e}", flush=True)
            return {'success': 0, 'error': str(e)}

    def socket_recv(self, params: dict) -> dict:
        """ソケットから受信"""
        try:
            socket_fd = params.get('socket_fd')
            buffer_size = params.get('buffer_size', 4096)
            timeout = params.get('timeout', 1.0)

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
            print(f"❌ Socket recv error: {e}", flush=True)
            return {'success': 0, 'error': str(e), 'data': ''}


def main():
    """JCross wrapperを実行"""

    if len(sys.argv) < 3:
        print("Usage: run_jcross_wrapper.py <host> <port> [project_path]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    project_path = sys.argv[3] if len(sys.argv) > 3 else "."

    # JCrossソースを読み込み
    jcross_file = Path(__file__).parent / "claude_wrapper_native.jcross"

    if not jcross_file.exists():
        print(f"❌ JCross wrapper not found: {jcross_file}")
        sys.exit(1)

    with open(jcross_file, 'r', encoding='utf-8') as f:
        source = f.read()

    # system.*関数を登録
    system_funcs = SystemFunctions()

    # JCrossコンパイラでコンパイル
    compiler = CrossIRCompiler()

    try:
        # ソースをコンパイル
        ir_code = compiler.compile(source)

        # 引数をグローバル変数として設定
        # JCrossプログラムから参照できるようにする
        # TODO: コンパイラのAPIに合わせて調整

        # 実行
        # system.*関数をextern関数として登録
        # TODO: コンパイラのAPIに合わせて調整

        print("✅ JCross wrapper compiled successfully", flush=True)

        # 実行 (仮実装 - IRランタイムが必要)
        # result = ir_code.execute(
        #     globals={
        #         'socket_host': host,
        #         'socket_port': port,
        #         'project_path': project_path
        #     },
        #     system=system_funcs
        # )

        # 仮: Python実装を使用
        print("⚠️  JCross実行は未実装 - Python実装にフォールバック", flush=True)
        from claude_wrapper import ClaudeWrapper
        wrapper = ClaudeWrapper(host, port, project_path)
        wrapper.run()

    except Exception as e:
        print(f"❌ JCross execution error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
