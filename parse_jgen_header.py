import struct
import json

with open("/home/ubuntu/model_glm.jgen", "rb") as f:
    magic = f.read(4)
    if magic != b"JGEN":
        print("Invalid magic:", magic)
    
    version = struct.unpack("<I", f.read(4))[0]
    
    # Check if there is a header length
    header_len_bytes = f.read(8)
    header_len = struct.unpack("<Q", header_len_bytes)[0]
    
    header_str = f.read(header_len).decode('utf-8')
    header = json.loads(header_str)
    
    print("vocab_size:", header.get('vocab_size', 'unknown'))
    print("hidden_size:", header.get('hidden_size', 'unknown'))
    
    norm = [t for t in header['tensors'] if 'input_layernorm.weight' in t['name']]
    if norm:
        print("Found norm:", norm[0])
    
    embed = [t for t in header['tensors'] if 'embed' in t['name']]
    if embed:
        print("Found embed:", embed[0])
