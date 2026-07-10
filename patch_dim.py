with open("cli/scripts/bucket_relay_swarm_9b.py", "r") as f:
    text = f.read()
import re
text = re.sub(r'self\.hidden_dim = \d+', r'self.hidden_dim = 4096', text)
text = re.sub(r'memory_bank = TelepathicMemoryBank\(hidden_dim=1024\)', r'memory_bank = TelepathicMemoryBank(hidden_dim=4096)', text)
with open("cli/scripts/bucket_relay_swarm_9b.py", "w") as f:
    f.write(text)
