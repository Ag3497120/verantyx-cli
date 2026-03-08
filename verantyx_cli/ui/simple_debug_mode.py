"""
Simple Debug Mode - Test socket communication without full UI

Use this to verify:
1. Socket server starts
2. Messages can be sent
3. Claude wrapper connects
"""

import sys
import time
from pathlib import Path

from ..engine.claude_socket_server import ClaudeSocketServer


def run_debug_mode():
    """Run simple debug mode to test communication"""
    print()
    print("=" * 70)
    print("  Verantyx-CLI Debug Mode - Socket Communication Test")
    print("=" * 70)
    print()

    # Start socket server
    print("1️⃣  Starting socket server...")
    server = ClaudeSocketServer(
        on_output=lambda text: print(f"📥 Received from Claude: {text[:100]}...")
    )

    try:
        host, port = server.start()
        print(f"   ✅ Server started on {host}:{port}")
        print()
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    # Wait for connection
    print("2️⃣  Waiting for Claude wrapper connection...")
    print(f"   Expected: Claude wrapper should connect within 60 seconds")
    print()

    # Check connection every second
    for i in range(60):
        if server.is_connected():
            print(f"   ✅ Claude wrapper connected!")
            break
        print(f"   Waiting... ({60-i}s remaining)", end='\r')
        time.sleep(1)
    else:
        print()
        print(f"   ❌ Timeout: No connection received")
        print()
        print("   Debug info:")
        print(f"   - Server running: {server._running}")
        print(f"   - Server port: {port}")
        print(f"   - Is connected: {server.is_connected()}")
        print()
        server.stop()
        return

    print()

    # Send test messages
    print("3️⃣  Testing message sending...")
    print()

    test_messages = [
        "Hello Claude!",
        "What is 2+2?",
        "Tell me about Python",
    ]

    for i, msg in enumerate(test_messages, 1):
        print(f"   [{i}] Sending: {msg}")
        server.send_input(msg)
        time.sleep(2)
        print(f"       Outputs received: {len(server.outputs)}")
        print()

    # Show results
    print("4️⃣  Results:")
    print(f"   Total outputs: {len(server.outputs)}")

    if server.outputs:
        print()
        print("   Last 5 outputs:")
        for i, output in enumerate(server.outputs[-5:], 1):
            print(f"   {i}. {output[:200]}...")
    else:
        print("   ⚠️  No outputs received")
        print()
        print("   Possible issues:")
        print("   - Claude wrapper not sending OUTPUT: prefix")
        print("   - Claude not responding")
        print("   - Socket communication broken")

    print()
    print("5️⃣  Connection info:")
    print(f"   Connected: {server.is_connected()}")
    print(f"   Client socket: {server.client_socket}")
    print(f"   Running: {server._running}")

    print()
    print("Press Ctrl+C to exit...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("Shutting down...")
        server.stop()
        print("Done!")


if __name__ == "__main__":
    run_debug_mode()
