import subprocess
import struct
import sys
import threading
import time

prompt = "<|im_start|>user\nWhat is the capital of France?<|im_end|>\n<|im_start|>assistant\n"
p = subprocess.Popen(["python3", "scripts/vera_bridge_daemon.py", prompt, "2"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def read_stderr():
    while True:
        line = p.stderr.readline()
        if not line: break
        sys.stdout.write(line.decode('utf-8', errors='ignore'))
        sys.stdout.flush()

threading.Thread(target=read_stderr, daemon=True).start()

p.wait()
