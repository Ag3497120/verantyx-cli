with open("cli/scripts/bucket_relay_swarm_9b.py", "r") as f:
    text = f.read()
import re
text = re.sub(r'os\.path\.join\(os\.path\.dirname\(__file__\),\s*"\.\./\.\./qwen_9b_full\.jgen"\)', r'"qwen_9b_full.jgen"', text)
with open("cli/scripts/bucket_relay_swarm_9b.py", "w") as f:
    f.write(text)
