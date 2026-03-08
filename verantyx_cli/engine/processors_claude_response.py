"""
Claude Response Processor - PTYからClaudeの完全な応答を読み取る
"""

import os
import select
import time


def read_claude_response_complete(params: dict) -> dict:
    """
    Claudeの完全な応答を読み取る（応答が完了するまで待機）

    入力 (VM varsから読み取り):
        params with __vm_vars__ containing 'claude_fd'

    出力:
        {"data": str}
    """
    vm_vars = params.get('__vm_vars__', {})
    claude_fd = vm_vars.get('claude_fd')

    if not claude_fd:
        return {'data': ''}

    # 応答を蓄積
    response_buffer = ""
    max_wait_time = 30.0  # 最大30秒待機
    no_data_timeout = 2.0  # データがない状態で2秒経過したら終了

    start_time = time.time()
    last_data_time = time.time()

    while True:
        # タイムアウトチェック
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            break

        # データがない状態の時間チェック
        time_since_data = time.time() - last_data_time
        if response_buffer and time_since_data > no_data_timeout:
            # すでにデータがあり、2秒間新しいデータがない場合は完了とみなす
            break

        # 読み取り可能かチェック（0.5秒タイムアウト）
        readable, _, _ = select.select([claude_fd], [], [], 0.5)

        if readable:
            try:
                data = os.read(claude_fd, 4096)
                if data:
                    decoded = data.decode('utf-8', errors='replace')
                    response_buffer += decoded
                    last_data_time = time.time()

                    # 応答が完了した可能性のあるマーカーをチェック
                    # Claudeの応答は通常、プロンプト（">"）で終わる
                    if '\n> ' in response_buffer or response_buffer.endswith('> '):
                        # 少し待ってから終了（追加データがあるかもしれない）
                        time.sleep(0.5)

                        # 最後の読み取り
                        readable2, _, _ = select.select([claude_fd], [], [], 0.1)
                        if readable2:
                            final_data = os.read(claude_fd, 4096)
                            if final_data:
                                response_buffer += final_data.decode('utf-8', errors='replace')

                        break
                else:
                    # 0バイト = 接続終了
                    break
            except Exception as e:
                break

    return {'data': response_buffer}


def get_claude_response_processors():
    """Claude応答プロセッサを返す"""
    return {
        'io.read_claude_response_complete': read_claude_response_complete,
    }
