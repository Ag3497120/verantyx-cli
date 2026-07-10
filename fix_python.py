import re

with open("cli/scripts/vera_bridge_daemon.py", "r") as f:
    content = f.read()

# Change float16 to float32 for IPC
content = content.replace("out_bytes, dtype=np.float16", "out_bytes, dtype=np.float32")
content = content.replace("10240", "20480")

# Ensure embed_tokens output is float32
content = content.replace("vec = embed_tokens[current_token].numpy().tobytes()", "vec = embed_tokens[current_token].to(torch.float32).numpy().tobytes()")

with open("cli/scripts/vera_bridge_daemon.py", "w") as f:
    f.write(content)
