import subprocess
import time

cmd = [
    "./.build/arm64-apple-macosx/release/verantyx-cli",
    "daemon",
    "qwen_27b.jcross",
    "--embed", "model-00001-of-00015.safetensors", "--embed-offset", "375440", "--embed-size", "782041088",
    "--lm-head", "model-00015-of-00015.safetensors", "--lm-head-offset", "1214064", "--lm-head-size", "782041088",
    "--norm", "model-00015-of-00015.safetensors", "--norm-offset", "783255160", "--norm-size", "10240"
]

process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

import threading
def read_err():
    for line in process.stderr:
        print("STDERR:", line.decode(errors='ignore').strip())
t = threading.Thread(target=read_err, daemon=True)
t.start()

while True:
    line = process.stdout.readline()
    print("STDOUT:", line.decode(errors='ignore').strip())
    if b"READY" in line:
        break

import struct
process.stdin.write(struct.pack('<I', 20)) # max_tokens
process.stdin.write(struct.pack('<I', 1))  # prompt length
process.stdin.write(struct.pack('<I', 151644)) # prompt token
process.stdin.flush()

while True:
    out = process.stdout.read(4)
    if not out:
        break
    print("GOT TOKEN:", struct.unpack('<I', out)[0])

process.wait()
print("SWIFT EXIT CODE:", process.returncode)
