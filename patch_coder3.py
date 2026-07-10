import os
with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    content = f.read()

content = content.replace('print("\\\n========================================")', 'print("\\n========================================")')
content = content.replace('print("\n========================================")', 'print("\\n========================================")')

with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(content)
