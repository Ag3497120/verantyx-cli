import subprocess
import struct
import sys
import threading
import time

p = subprocess.Popen(["/Users/motonishikoudai/verantyx-cli/cli/.build/arm64-apple-macosx/release/verantyx-cli", "daemon", "/Users/motonishikoudai/verantyx-cli/cli/qwen_27b.jcross", "-v", "--embed-path", "", "--embed-offset", "0", "--embed-size", "0", "--head-path", "", "--head-offset", "0", "--head-size", "0", "--norm-path", "", "--norm-offset", "0", "--norm-size", "0"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def read_stderr():
    while True:
        line = p.stderr.readline()
        if not line: break
        sys.stdout.write(line.decode('utf-8', errors='ignore'))
        sys.stdout.flush()

threading.Thread(target=read_stderr, daemon=True).start()

ready = p.stdout.readline()
print("READY:", ready)
sys.stdout.flush()

# Send token
token = 46972
p.stdin.write(struct.pack('<I', token))
p.stdin.flush()

# Send GEN 1
p.stdin.write(b'GEN\n')
p.stdin.write(struct.pack('<I', 1))
p.stdin.flush()

time.sleep(2)
