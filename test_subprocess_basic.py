#!/usr/bin/env python3
"""
基本的なClaude Codeサブプロセステスト

問題切り分けのための最小限の実装
"""

import os
import sys
import pty
import select
import time

def test_claude_subprocess():
    """Claude Codeを起動して基本的な通信テスト"""
    print("🧪 Claude Code Subprocess Test")
    print()

    # PTYでClaudeを起動
    print("🚀 Starting Claude Code...")
    pid, master_fd = pty.fork()

    if pid == 0:
        # 子プロセス
        os.environ['TERM'] = 'xterm-256color'
        os.execvp("claude", ["claude"])
        sys.exit(1)

    # 親プロセス
    print(f"✅ Claude started (PID: {pid})")
    print()
    print("📺 Raw output from Claude:")
    print("=" * 70)

    # 初期出力を待機
    time.sleep(3)

    print("\n📤 Sending test prompt...")

    # プロンプトを送信
    prompt = "Hello! Say hi back."
    os.write(master_fd, prompt.encode('utf-8'))
    time.sleep(0.1)
    os.write(master_fd, b'\n')

    print(f"✅ Sent: {prompt}")
    print()
    print("📺 Claude response:")
    print("=" * 70)

    # 応答を待機（30秒）
    start_time = time.time()
    max_wait = 30

    try:
        while time.time() - start_time < max_wait:
            readable, _, _ = select.select([master_fd], [], [], 0.1)

            if master_fd in readable:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        # 生出力をそのまま表示
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                    else:
                        print("\n[Claude closed]")
                        break
                except OSError:
                    print("\n[Read error]")
                    break

    except KeyboardInterrupt:
        print("\n\n[Interrupted]")

    finally:
        print("\n" + "=" * 70)
        print("🛑 Cleaning up...")
        os.close(master_fd)
        os.kill(pid, 15)
        print("✅ Done")


if __name__ == "__main__":
    test_claude_subprocess()
