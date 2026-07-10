import struct
with open("/Users/motonishikoudai/verantyx-cli/cli/qwen_27b.jmeta", "rb") as f:
    f.read(4) # JMET
    f.read(4) # version
    while True:
        header = f.read(6)
        if not header or len(header) < 6: break
        z, mtype, size = struct.unpack("<B B I", header)
        if z == 0 and mtype == 0:
            print(f"Layer {z} has input_layernorm!")
        f.read(size)
