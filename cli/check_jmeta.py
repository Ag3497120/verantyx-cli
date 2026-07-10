import struct
import json

with open("qwen_27b.jcross", "rb") as f:
    magic = f.read(4)
    if magic != b'SRCJ':
        print("Not SRCJ")
        exit()
    
    version = struct.unpack('<I', f.read(4))[0]
    json_len = struct.unpack('<Q', f.read(8))[0]
    json_str = f.read(json_len).decode('utf-8')
    metadata = json.loads(json_str)
    
    print("LM head jmeta:")
    if "64" in metadata["jmeta"]:
        print(metadata["jmeta"]["64"])
