#!/usr/bin/env python3
"""
Neural Engine Wrapper Runner - Claude WrapperをNeural Engineで実行

従来のVM実行からNeural Engine実行へ完全移行
ノイマン型アーキテクチャを排除
"""

import sys
from pathlib import Path

# Neural engineをインポート
neural_dir = Path(__file__).parent / "neural"
sys.path.insert(0, str(neural_dir))

from claude_wrapper_neural import run_claude_wrapper_neural_engine


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: run_neural_wrapper.py <host> <port> [project_path]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    project_path = sys.argv[3] if len(sys.argv) > 3 else "."

    # Neural Engineで実行
    run_claude_wrapper_neural_engine(host, port, project_path)
