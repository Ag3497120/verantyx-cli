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
        {"pty_fd": int, "size": int}

    出力:
        {"data": str}
    """
    pty_fd = params['pty_fd']
    size = params.get('size', 4096)

    data = os.read(pty_fd, size)
    decoded = data.decode('utf-8', errors='replace')

    return {'data': decoded}


# ═══════════════════════════════════════════════════════════════
# Socket変換器 - ネットワーク入出力
# ═══════════════════════════════════════════════════════════════

def socket_create_and_connect(params: dict) -> dict:
    """
    ソケットを作成して接続（純粋な変換）

    入力:
        {"host": "localhost", "port": 52749}

    出力:
        {"socket_fd": int}
    """
    host = params['host']
    port = params['port']

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # グローバルに保持（Cross構造がファイルディスクリプタを管理）
    _SOCKETS[sock.fileno()] = sock

    return {'socket_fd': sock.fileno()}


def socket_recv_bytes(params: dict) -> dict:
    """
    ソケットからバイト列を受信（純粋な変換）

    入力:
        {"socket_fd": int, "size": int, "timeout": float}

    出力:
        {"data": str, "has_data": int}
    """
    socket_fd = params['socket_fd']
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

        # Socket入出力
        'io.socket_connect': socket_create_and_connect,
        'io.socket_recv': socket_recv_bytes,

        # 文字列変換
        'io.string_length': string_get_length,
        'io.string_slice': string_slice,
        'io.string_trim': string_trim_whitespace,
        'io.string_concat': string_concat,
        'io.string_starts_with': string_starts_with,
    }
