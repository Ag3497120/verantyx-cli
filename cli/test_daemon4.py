import subprocess
import struct
import sys
import threading

# Use vera_bridge_daemon.py, but don't pipe stderr, just let it print to terminal!
p = subprocess.Popen(["python3", "scripts/vera_bridge_daemon.py", "フィボナッチ数列を生成するPythonコードを書いてください。", "50"])
p.wait()
