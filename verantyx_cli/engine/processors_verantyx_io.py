"""
Verantyx IO Processors - Pure Input/Output Translation

Pythonは入出力変換のみ。ロジックは一切含まない。
全てのロジックはJCross（Cross構造）で実装される。

設計原則:
1. if文禁止 - 条件分岐はJCrossで行う
2. ループ禁止 - 反復はCross構造の遷移で行う
3. 状態管理禁止 - 状態はCross構造に格納
4. 型変換のみ - 外部世界 ⇄ Cross構造のデータ変換
"""

import os
import pty
import socket
import select


# ═══════════════════════════════════════════════════════════════
# PTY変換器 - プロセス生成と入出力
# ═══════════════════════════════════════════════════════════════

def pty_fork_process(params: dict) -> dict:
    """
    プロセスをPTYでフォーク（純粋な変換）

    入力（Cross構造から）:
        {"command": "claude"}

    出力（Cross構造へ）:
        {"pty_fd": int, "pid": int}
    """
    command = params.get('command', 'claude')

    pid, master_fd = pty.fork()

    # 子プロセス
    if pid == 0:
        os.execlp(command, command)

    # 親プロセス - データを返すのみ
    return {
        'pty_fd': master_fd,
        'pid': pid
    }


def pty_write_bytes(params: dict) -> dict:
    """
    PTYにバイト列を書き込む（純粋な変換）

    入力:
        {"pty_fd": int, "data": str}

    出力:
        {"bytes_written": int}
    """
    pty_fd = params['pty_fd']
    data = params['data']

    encoded = data.encode('utf-8')
    bytes_written = os.write(pty_fd, encoded)

    return {'bytes_written': bytes_written}


def pty_read_bytes(params: dict) -> dict:
    """
    PTYからバイト列を読み込む（純粋な変換）

    入力:
        {"pty_fd": int, "size": int, "timeout": float}
        または VM変数から読み取り

    出力:
        {"data": str}
    """
    # VM変数から読み取り
    vm_vars = params.get('__vm_vars__', {})
    pty_fd = params.get('pty_fd') or vm_vars.get('claude_fd')
    size = params.get('size', 4096)
    timeout = params.get('timeout', 0.0)

    if not pty_fd:
        return {'data': ''}

    try:
        # タイムアウト付きselect
        readable, _, _ = select.select([pty_fd], [], [], timeout)

        if not readable:
            return {'data': ''}

        data = os.read(pty_fd, size)
        decoded = data.decode('utf-8', errors='replace')

        return {'data': decoded}
    except Exception as e:
        return {'data': ''}


# ═══════════════════════════════════════════════════════════════
# Socket変換器 - ネットワーク入出力
# ═══════════════════════════════════════════════════════════════

def socket_create_and_connect(params: dict) -> dict:
    """
    ソケットを作成して接続（純粋な変換）

    入力 (gets host/port from VM variables via __vm_vars__):
        params: dict with __vm_vars__ injected by VM

    出力:
        {"socket_fd": int}
    """
    # Get VM variables
    vm_vars = params.get('__vm_vars__', {})

    # Read host and port from VM variables
    host = vm_vars.get('host', 'localhost')
    port = vm_vars.get('port', 0)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # グローバルに保持（Cross構造がファイルディスクリプタを管理）
    _SOCKETS[sock.fileno()] = sock

    return {'socket_fd': sock.fileno()}


def socket_recv_bytes(params: dict) -> dict:
    """
    ソケットからバイト列を受信（純粋な変換）

    入力 (reads socket_fd from VM vars):
        {"size": int, "timeout": float}
        + __vm_vars__ with verantyx_fd

    出力:
        {"data": str, "has_data": int}
    """
    # Get VM variables
    vm_vars = params.get('__vm_vars__', {})

    # Read socket_fd from VM variables (stored as verantyx_fd or current_fd)
    socket_fd = vm_vars.get('verantyx_fd') or vm_vars.get('current_fd')
    size = params.get('size', 4096)
    timeout = params.get('timeout', 1.0)

    sock = _SOCKETS.get(socket_fd)

    # selectでタイムアウト
    readable, _, _ = select.select([sock], [], [], timeout)

    # データがあれば受信
    if readable:
        data = sock.recv(size)
        decoded = data.decode('utf-8', errors='replace')
        return {'data': decoded, 'has_data': 1}

    # タイムアウト
    return {'data': '', 'has_data': 0}


# ═══════════════════════════════════════════════════════════════
# 文字列変換器 - データ操作
# ═══════════════════════════════════════════════════════════════

def string_get_length(params: dict) -> dict:
    """文字列の長さを取得（純粋な変換）"""
    s = params['string']
    return {'length': len(s)}


def string_slice(params: dict) -> dict:
    """文字列をスライス（純粋な変換）"""
    s = params['string']
    start = params.get('start', 0)
    end = params.get('end', len(s))
    return {'result': s[start:end]}


def string_trim_whitespace(params: dict) -> dict:
    """文字列の前後空白を削除（純粋な変換）"""
    s = params['string']
    return {'result': s.strip()}


def string_concat(params: dict) -> dict:
    """2つの文字列を結合（純粋な変換）"""
    a = params['a']
    b = params['b']
    return {'result': str(a) + str(b)}


def string_starts_with(params: dict) -> dict:
    """文字列が指定プレフィックスで始まるか（純粋な変換）"""
    s = params['string']
    prefix = params['prefix']
    return {'result': 1 if s.startswith(prefix) else 0}


# ═══════════════════════════════════════════════════════════════
# Verantyx固有の複合変換器
# ═══════════════════════════════════════════════════════════════

def socket_recv_from_var(params: dict) -> dict:
    """
    VM変数からソケットFDを読み取って受信（純粋な変換）

    入力 (VM varsから読み取り):
        params with __vm_vars__

    出力:
        {"data": str, "has_data": int}
    """
    # VM変数から読み取り
    vm_vars = params.get('__vm_vars__', {})
    socket_fd = vm_vars.get('verantyx_fd')

    if not socket_fd:
        return {'data': '', 'has_data': 0}

    sock = _SOCKETS.get(socket_fd)
    if not sock:
        return {'data': '', 'has_data': 0}

    # タイムアウト付き受信
    timeout = params.get('timeout', 0.1)
    readable, _, _ = select.select([sock], [], [], timeout)

    if readable:
        data = sock.recv(4096)

        # 0バイト受信 = 接続終了
        if not data:
            return {'data': '', 'has_data': 0}

        decoded = data.decode('utf-8', errors='replace')

        # デコード後も空なら has_data=0
        if not decoded or not decoded.strip():
            return {'data': '', 'has_data': 0}

        return {'data': decoded, 'has_data': 1}

    return {'data': '', 'has_data': 0}


def socket_connect_literal(params: dict) -> dict:
    """
    リテラル値でソケット接続（テスト用）

    入力 (VM varsから読み取り):
        params with __vm_vars__

    出力:
        {"socket_fd": int}
    """
    # VM変数から読み取り
    vm_vars = params.get('__vm_vars__', {})
    host = vm_vars.get('host', 'localhost')
    port = vm_vars.get('port', 0)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    _SOCKETS[sock.fileno()] = sock

    return {'socket_fd': sock.fileno()}


def check_input_prefix(params: dict) -> dict:
    """
    メッセージが"INPUT:"で始まるかチェック（純粋な変換）

    入力 (VM varsから読み取り):
        params with __vm_vars__ containing 'check_msg'

    出力:
        {"result": int}  # 1 if starts with "INPUT:", 0 otherwise
    """
    vm_vars = params.get('__vm_vars__', {})
    message = vm_vars.get('check_msg', '')

    result = 1 if message.startswith('INPUT:') else 0

    return {'result': result}


def process_and_send_to_claude(params: dict) -> dict:
    """
    メッセージを処理してClaudeに送信（純粋な変換）

    入力 (VM varsから読み取り):
        params with __vm_vars__ containing 'message', 'claude_fd'

    出力:
        {"bytes_written": int}
    """
    vm_vars = params.get('__vm_vars__', {})
    message = vm_vars.get('message', '')
    claude_fd = vm_vars.get('claude_fd')

    if not claude_fd:
        return {'bytes_written': 0}

    # "INPUT:"プレフィックスを削除
    if message.startswith('INPUT:'):
        message = message[6:].strip()

    # Claudeに送信 (改行を追加)
    message_with_newline = message + '\n'
    encoded = message_with_newline.encode('utf-8')
    bytes_written = os.write(claude_fd, encoded)

    return {'bytes_written': bytes_written}


def socket_send_output(params: dict) -> dict:
    """
    Claudeの出力をVerantyxに送信（純粋な変換）

    入力 (VM varsから読み取り):
        params with __vm_vars__ containing 'output_to_send', 'verantyx_fd'

    出力:
        {"bytes_sent": int}
    """
    vm_vars = params.get('__vm_vars__', {})
    output = vm_vars.get('output_to_send', '')
    verantyx_fd = vm_vars.get('verantyx_fd')

    if not verantyx_fd or not output:
        return {'bytes_sent': 0}

    # "OUTPUT:"プレフィックスを追加
    message_with_prefix = f"OUTPUT:{output}"

    # ソケットから取得
    sock = _SOCKETS.get(verantyx_fd)
    if not sock:
        return {'bytes_sent': 0}

    # 送信
    try:
        encoded = message_with_prefix.encode('utf-8')
        sock.sendall(encoded)
        return {'bytes_sent': len(encoded)}
    except Exception as e:
        return {'bytes_sent': 0}


# ═══════════════════════════════════════════════════════════════
# グローバルソケット管理（Cross構造が管理するFDのみ）
# ═══════════════════════════════════════════════════════════════

_SOCKETS = {}


# ═══════════════════════════════════════════════════════════════
# プロセッサ登録
# ═══════════════════════════════════════════════════════════════

def get_verantyx_io_processors():
    """
    入出力変換器のみを返す

    全ての関数は純粋な変換：
    - 入力を受け取る
    - 変換する
    - 出力を返す

    ロジックは一切含まない。
    """
    return {
        # PTY入出力
        'io.pty_fork': pty_fork_process,
        'io.pty_write': pty_write_bytes,
        'io.pty_read': pty_read_bytes,

        # Socket入出力 (基本)
        'io.socket_connect': socket_create_and_connect,
        'io.socket_recv': socket_recv_bytes,

        # Socket入出力 (Verantyx固有)
        'io.socket_recv_from_var': socket_recv_from_var,
        'io.socket_connect_literal': socket_connect_literal,
        'io.socket_send_output': socket_send_output,

        # 文字列変換
        'io.string_length': string_get_length,
        'io.string_slice': string_slice,
        'io.string_trim': string_trim_whitespace,
        'io.string_concat': string_concat,
        'io.string_starts_with': string_starts_with,

        # Verantyx固有の複合変換
        'io.check_input_prefix': check_input_prefix,
        'io.process_and_send_to_claude': process_and_send_to_claude,
    }
