with open("cli/scripts/telepathic_coder_experimental.py", "r") as f:
    text = f.read()
import re
text = re.sub(r'Qwen/Qwen1\.5-0\.5B-Chat', r'Qwen/Qwen3.5-9B', text)
text = re.sub(r'Qwen/Qwen2\.5-0\.5B-Instruct', r'Qwen/Qwen3.5-9B', text)
text = re.sub(r'Qwen 0\.5B JGEN', r'Qwen 9B JGEN', text)
text = re.sub(r'Qwen-0\.5B', r'Qwen-9B', text)
with open("cli/scripts/telepathic_coder_experimental.py", "w") as f:
    f.write(text)
