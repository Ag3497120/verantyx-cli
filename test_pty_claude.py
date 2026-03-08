#!/usr/bin/env python3
"""
Test PTY-based Claude interaction
"""

import os
import pty
import select
import time

def main():
    print("🚀 Testing PTY-based Claude interaction")
    print()

    # Fork Claude
    print("📦 Forking Claude...")
    pid, master_fd = pty.fork()

    if pid == 0:
        # Child process - run Claude
        os.execlp('claude', 'claude')

    # Parent process
    print(f"✅ Claude forked (PID: {pid})")
    print(f"   Master FD: {master_fd}")
    print()

    # Wait for Claude to start
    print("⏳ Waiting for Claude to initialize...")
    time.sleep(2)

    # Read initial output
    print("📖 Reading initial output from Claude:")
    print("-" * 70)

    for i in range(10):
        try:
            readable, _, _ = select.select([master_fd], [], [], 0.5)
            if readable:
                data = os.read(master_fd, 4096)
                output = data.decode('utf-8', errors='replace')
                print(output, end='', flush=True)
            else:
                print(f"[No data in iteration {i+1}]")
        except Exception as e:
            print(f"Error reading: {e}")
            break

    print()
    print("-" * 70)
    print()

    # Send a test message
    test_message = "Hello Claude!\n"
    print(f"📤 Sending: {test_message.strip()}")
    os.write(master_fd, test_message.encode('utf-8'))

    # Read response
    print("📖 Reading response:")
    print("-" * 70)

    time.sleep(1)

    for i in range(20):
        try:
            readable, _, _ = select.select([master_fd], [], [], 0.5)
            if readable:
                data = os.read(master_fd, 4096)
                output = data.decode('utf-8', errors='replace')
                print(output, end='', flush=True)
            else:
                print(f"[No more data]")
                break
        except Exception as e:
            print(f"Error: {e}")
            break

    print()
    print("-" * 70)
    print()
    print("✅ Test complete")

    # Cleanup
    import signal
    os.kill(pid, signal.SIGTERM)

if __name__ == "__main__":
    main()
