#!/usr/bin/env python3
"""
Claude Wrapper統合テスト

VM wrapper + Verantyx server の統合動作確認
"""

import socket
import time
import subprocess
import sys
from pathlib import Path


def start_wrapper(port):
    """Claude wrapperを起動"""
    wrapper_script = Path(__file__).parent / "verantyx_cli/engine/run_simple_wrapper.py"

    proc = subprocess.Popen(
        [sys.executable, str(wrapper_script), "localhost", str(port), "."],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    return proc


def send_message(sock, message):
    """メッセージ送信"""
    data = f"INPUT:{message}\n".encode('utf-8')
    sock.sendall(data)
    print(f"📤 Sent: INPUT:{message}")


def main():
    print("=" * 70)
    print("Claude Wrapper Integration Test")
    print("=" * 70)
    print()

    # ポート設定
    port = 59999

    # Step 1: サーバーソケット作成（先に起動）
    print("Step 1: Creating server socket...")
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind(("localhost", port))
        server_sock.listen(1)
        print(f"✅ Server listening on port {port}")
        print()

        # Step 2: Wrapperを起動
        print("Step 2: Starting Claude wrapper...")
        wrapper_proc = start_wrapper(port)

        # Wrapperの起動ログを表示（バックグラウンド）
        print()
        print("Wrapper output:")
        print("-" * 70)

        # Step 3: Wrapper からの接続を待つ
        print()
        print("Step 3: Waiting for wrapper connection...")
        server_sock.settimeout(5.0)

        try:
            client_sock, addr = server_sock.accept()
            print(f"✅ Wrapper connected from {addr}")
            print()

            # Step 4: テストメッセージ送信
            print("Step 4: Sending test messages...")
            print()

            # Message 1
            send_message(client_sock, "Hello Claude!")
            time.sleep(1)

            # Message 2
            send_message(client_sock, "How are you?")
            time.sleep(1)

            # Message 3
            send_message(client_sock, "Test complete")
            time.sleep(1)

            print()
            print("=" * 70)
            print("✅ Test completed successfully")
            print("=" * 70)

            # Wrapperの追加出力を表示
            print()
            print("Wrapper additional output:")
            print("-" * 70)
            for _ in range(10):
                line = wrapper_proc.stdout.readline()
                if line:
                    print(line.strip())
            print("-" * 70)

            client_sock.close()

        except socket.timeout:
            print("❌ Timeout waiting for wrapper connection")
            print("   Wrapper may not have connected to the server")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        server_sock.close()
        wrapper_proc.terminate()
        wrapper_proc.wait(timeout=2)

    print()
    print("Test finished")


if __name__ == "__main__":
    main()
