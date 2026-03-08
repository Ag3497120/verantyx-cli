#!/usr/bin/env python3
"""
Test Claude Socket Connection - Diagnostic tool

Checks if:
1. Socket server can start
2. Claude wrapper can connect
3. Messages can be sent/received
"""

import sys
import time
from pathlib import Path

# Add verantyx_cli to path
sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.claude_socket_server import ClaudeSocketServer

print("=" * 70)
print("  Verantyx-CLI → Claude Connection Test")
print("=" * 70)
print()

# Test 1: Start socket server
print("Test 1: Starting socket server...")
server = ClaudeSocketServer()

try:
    host, port = server.start()
    print(f"✅ Socket server started on {host}:{port}")
    print()
except Exception as e:
    print(f"❌ Failed to start server: {e}")
    sys.exit(1)

# Test 2: Check connection status
print("Test 2: Checking connection status...")
print(f"   Server running: {server._running}")
print(f"   Client connected: {server.is_connected()}")
print()

# Test 3: Wait for connection (30 seconds)
print("Test 3: Waiting for Claude wrapper to connect...")
print("   (Start Claude in another terminal with wrapper)")
print()

start_time = time.time()
timeout = 30

while time.time() - start_time < timeout:
    if server.is_connected():
        print(f"✅ Claude wrapper connected!")
        break

    remaining = int(timeout - (time.time() - start_time))
    print(f"   Waiting... ({remaining}s remaining)", end='\r')
    time.sleep(1)
else:
    print()
    print("❌ Timeout: Claude wrapper did not connect")
    print()
    print("To test manually:")
    print(f"1. Run in another terminal: nc localhost {port}")
    print(f"2. Type: VERANTYX_CLAUDE_WRAPPER")
    print(f"3. Press Enter")
    server.stop()
    sys.exit(1)

print()

# Test 4: Send test message
print("Test 4: Sending test message...")
test_message = "Hello from Verantyx test!"

try:
    server.send_input(test_message)
    print(f"✅ Sent: {test_message}")
    print()
except Exception as e:
    print(f"❌ Failed to send: {e}")
    print()

# Test 5: Check for responses
print("Test 5: Checking for responses...")
print("   Waiting 5 seconds...")
time.sleep(5)

if server.outputs:
    print(f"✅ Received {len(server.outputs)} output(s):")
    for i, output in enumerate(server.outputs, 1):
        print(f"   {i}. {output[:100]}...")
else:
    print("⚠️  No outputs received (this may be normal if Claude hasn't responded)")

print()

# Summary
print("=" * 70)
print("  Test Summary")
print("=" * 70)
print()
print(f"✅ Socket server: Working")
print(f"{'✅' if server.is_connected() else '❌'} Connection: {'Connected' if server.is_connected() else 'Not connected'}")
print(f"{'✅' if server.outputs else '⚠️ '} Outputs: {len(server.outputs)} received")
print()

# Cleanup
print("Cleaning up...")
server.stop()
print("Done!")
