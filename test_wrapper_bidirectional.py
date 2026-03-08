#!/usr/bin/env python3
"""
Test bidirectional communication with Claude wrapper
"""

import socket
import time
import subprocess
import sys
from pathlib import Path

def main():
    # Create socket server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('localhost', 0))
    port = server.getsockname()[1]
    server.listen(1)

    print(f"🌐 Server listening on localhost:{port}")
    print()

    # Launch wrapper in subprocess
    wrapper_script = Path(__file__).parent / "verantyx-cli/verantyx_cli/engine/run_simple_wrapper.py"
    project_path = Path(__file__).parent / "verantyx-cli"

    print(f"🚀 Starting wrapper: {wrapper_script}")
    print(f"   Arguments: localhost {port} {project_path}")
    print()

    wrapper_proc = subprocess.Popen(
        [sys.executable, str(wrapper_script), 'localhost', str(port), str(project_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Wait for connection
    print("⏳ Waiting for wrapper to connect...")
    server.settimeout(10.0)

    try:
        client, addr = server.accept()
        print(f"✅ Wrapper connected from {addr}")
        print()
    except socket.timeout:
        print("❌ Wrapper did not connect in time")
        wrapper_proc.terminate()
        return

    client.settimeout(2.0)

    # Send test message
    test_messages = [
        "INPUT:こんにちは",
        "INPUT:Hello Claude!",
        "INPUT:Pythonについて教えて"
    ]

    for i, msg in enumerate(test_messages, 1):
        print(f"📤 Sending message {i}: {msg}")
        try:
            client.send(msg.encode('utf-8'))
            print(f"✅ Message {i} sent")
        except Exception as e:
            print(f"❌ Failed to send message {i}: {e}")
            break

        # Wait a bit for processing
        time.sleep(3)

        # Check wrapper output
        print("📊 Wrapper output:")
        while True:
            try:
                line = wrapper_proc.stdout.readline()
                if not line:
                    break
                print(f"   {line.rstrip()}")
            except:
                break

        print()

    # Keep connection alive
    print("⏳ Keeping connection alive (press Ctrl+C to stop)...")
    try:
        while True:
            time.sleep(1)
            # Check wrapper output
            try:
                line = wrapper_proc.stdout.readline()
                if line:
                    print(f"   {line.rstrip()}")
            except:
                pass
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping...")

    # Cleanup
    client.close()
    server.close()
    wrapper_proc.terminate()
    wrapper_proc.wait()
    print("✅ Cleanup complete")

if __name__ == "__main__":
    main()
