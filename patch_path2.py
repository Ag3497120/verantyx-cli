with open("cli/scripts/bucket_relay_swarm_9b.py", "r") as f:
    text = f.read()
import re
text = re.sub(r'os\.path\.join\(workspace_dir, "cli", "\.\./\.\./qwen_9b_full\.jgen"\)', r'"/Users/motonishikoudai/verantyx-cli/qwen_9b_full.jgen"', text)
text = re.sub(r'os\.path\.join\(workspace_dir, "\.\./\.\./qwen_9b_full\.jgen"\)', r'"/Users/motonishikoudai/verantyx-cli/qwen_9b_full.jgen"', text)
with open("cli/scripts/bucket_relay_swarm_9b.py", "w") as f:
    f.write(text)
