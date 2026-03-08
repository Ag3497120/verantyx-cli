"""
Test script to check ClaudeMonitor outputs
"""
from pathlib import Path
from verantyx_cli.engine.claude_monitor import ClaudeMonitor
import time

project_path = Path.cwd()

# Create monitor
monitor = ClaudeMonitor(
    project_path=project_path,
    llm_command="claude",
    monitor_only=True
)

# Launch Claude
print("Launching Claude...")
if monitor.launch_claude():
    print("✅ Claude launched")

    # Wait a bit for initial output
    time.sleep(3)

    print(f"\n📊 Statistics:")
    print(f"  User inputs: {len(monitor.user_inputs)}")
    print(f"  Claude outputs: {len(monitor.claude_outputs)}")

    if monitor.claude_outputs:
        print(f"\n📝 Latest outputs:")
        for i, output in enumerate(monitor.claude_outputs[-5:]):
            content = output['content']
            print(f"  [{i}] {len(content)} bytes: {content[:100]}...")

    # Send a test message
    print("\n🚀 Sending test message...")
    monitor.send_to_llm("こんにちは")

    # Wait for response
    time.sleep(5)

    print(f"\n📊 After sending message:")
    print(f"  User inputs: {len(monitor.user_inputs)}")
    print(f"  Claude outputs: {len(monitor.claude_outputs)}")

    if len(monitor.claude_outputs) > 5:
        print(f"\n📝 New outputs:")
        for i, output in enumerate(monitor.claude_outputs[-3:]):
            content = output['content']
            print(f"  [{i}] {len(content)} bytes: {content[:200]}...")

    # Stop
    monitor.stop()
else:
    print("❌ Failed to launch Claude")
