#!/usr/bin/env python3
"""
Neural Engine Wrapper Runner - Claude WrapperをNeural Engineで実行

Hybrid Architecture:
- Neural Engine: State transition control (non-von Neumann)
- Python Processors: I/O operations (pure translation)
"""

import sys
from pathlib import Path

# Neural engineをインポート
neural_dir = Path(__file__).parent / "neural"
sys.path.insert(0, str(neural_dir))

from claude_wrapper_hybrid import run_claude_wrapper_hybrid


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: run_neural_wrapper.py <host> <port> [project_path]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    project_path = sys.argv[3] if len(sys.argv) > 3 else "."

    # Hybrid Architecture: Neural Engine + Python I/O
    run_claude_wrapper_hybrid(host, port, project_path)
