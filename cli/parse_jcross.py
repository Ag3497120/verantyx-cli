import struct
import json

with open("qwen_27b.jcross", "rb") as f:
    f.seek(8)
    json_len = struct.unpack('<Q', f.read(8))[0]
    print("JSON len:", json_len)
    
    # Let's read just the first 100 bytes of json to see if it's readable
    json_str = f.read(100).decode('utf-8', errors='ignore')
    print("JSON start:", json_str)
