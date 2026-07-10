import struct

def parse_jcross():
    path = "qwen_27b.jcross"
    with open(path, "rb") as f:
        data = f.read(1024 * 1024 * 200) # 200MB
    offset = 8
    unique_types = set()
    layer_types = {}
    while offset < len(data) - 10:
        tensor_size = struct.unpack("<I", data[offset:offset+4])[0]
        z = data[offset+4]
        mtype = data[offset+5]
        num_blocks = struct.unpack("<I", data[offset+6:offset+10])[0]
        
        if z not in layer_types:
            layer_types[z] = set()
        layer_types[z].add(mtype)
        unique_types.add(mtype)
        
        # Advance by tensor_size
        offset += tensor_size
        
    print(f"Unique types: {unique_types}")
    print(f"Layer 0 types: {layer_types.get(0)}")
    print(f"Layer 4 types: {layer_types.get(4)}")

parse_jcross()
