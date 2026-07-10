import subprocess, struct, time
cmd = ["./.build/arm64-apple-macosx/release/verantyx-cli", "daemon", "qwen_27b.jcross"]
process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
# wait for READY
while True:
    line = process.stdout.readline()
    if b"READY" in line:
        break
    time.sleep(0.1)

# send one token
process.stdin.write(struct.pack('<I', 151644))
process.stdin.flush()

out = process.stderr.read()
print(out.decode('utf-8'))
