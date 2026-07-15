import sys
import pexpect

print("Starting verantyx_shell.py...")
child = pexpect.spawn('python3 cli/scripts/verantyx_shell.py', encoding='utf-8')

child.expect('Swarm>', timeout=120)
print("Got prompt, sending command...")
child.sendline("Test prompt")

try:
    while True:
        line = child.readline()
        if not line: break
        sys.stdout.write(line)
except pexpect.EOF:
    pass
