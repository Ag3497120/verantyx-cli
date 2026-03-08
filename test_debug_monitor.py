#!/usr/bin/env python3
"""
Test script to debug Claude Monitor issues

Run this to see detailed logs of what's happening
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from verantyx_cli.engine.claude_monitor import ClaudeMonitor
import logging

# Set up logging to console for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    project_path = Path.cwd()
    logger.info(f"Project path: {project_path}")

    # Create monitor
    logger.info("Creating ClaudeMonitor...")
    monitor = ClaudeMonitor(
        project_path=project_path,
        llm_command="claude",
        monitor_only=True
    )

    # Launch Claude
    logger.info("Launching Claude...")
    if not monitor.launch_claude():
        logger.error("Failed to launch Claude")
        return

    logger.info("Claude launched successfully!")
    logger.info(f"Process PID: {monitor.process.pid}")
    logger.info(f"Master FD: {monitor.master_fd}")

    # Wait for Claude to initialize
    logger.info("Waiting 3 seconds for Claude to initialize...")
    time.sleep(3)

    # Check process health
    logger.info(f"Claude process alive: {monitor.is_llm_alive()}")
    logger.info(f"Number of outputs captured: {len(monitor.claude_outputs)}")

    if monitor.claude_outputs:
        logger.info("Recent outputs:")
        for i, output in enumerate(monitor.claude_outputs[-5:]):
            logger.info(f"  Output {i}: {output['content'][:100]}...")

    # Send a test message
    logger.info("Sending test message: 'こんにちは'")
    monitor.send_to_llm("こんにちは")

    # Wait for response
    logger.info("Waiting 5 seconds for response...")
    time.sleep(5)

    # Check outputs again
    logger.info(f"Number of outputs after message: {len(monitor.claude_outputs)}")

    if len(monitor.claude_outputs) > 0:
        logger.info("Latest outputs:")
        for i, output in enumerate(monitor.claude_outputs[-10:]):
            logger.info(f"  Output {i}: {output['content'][:100]}...")
    else:
        logger.warning("No outputs received!")

    # Check Cross structure
    cross_file = monitor.cross_output_file
    if cross_file.exists():
        size = cross_file.stat().st_size
        logger.info(f"Cross structure file: {cross_file} ({size} bytes)")
    else:
        logger.warning(f"Cross structure file not created: {cross_file}")

    # Stop monitor
    logger.info("Stopping monitor...")
    monitor.stop()
    logger.info("Done!")

if __name__ == "__main__":
    main()
