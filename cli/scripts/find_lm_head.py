import sys
import struct

filepath = "/Users/motonishikoudai/gemma_12b_commander.jcross"
print(f"Searching for lm_head in {filepath}...")

with open(filepath, "rb") as f:
    data = f.read(1024 * 1024 * 50) # Read first 50MB
    idx = data.find(b"lm_head")
    if idx == -1:
        idx = data.find(b"embed_tokens")
        
    if idx != -1:
        print(f"Found at offset: {idx}")
        # Print a few bytes around it
        start = max(0, idx - 20)
        end = min(len(data), idx + 50)
        chunk = data[start:end]
        print(f"Context: {chunk}")
        
        # Let's try to interpret the 10 bytes after the string
        # Assuming format: name_len (2), name (N), type (1), ...
        # But wait, we searched for the string itself.
        # Let's find the length prefix.
        
