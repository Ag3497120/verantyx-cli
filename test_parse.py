import struct
with open("cli/qwen_27b.jcross", "rb") as f:
    f.read(12) # header
    offset = 12
    z_min = {}
    z_max = {}
    for _ in range(1000000):
        header = f.read(6)
        if not header: break
        z, col, row, mat = struct.unpack("<B H H B", header)
        block_offset = offset + 6
        if z not in z_min:
            z_min[z] = block_offset
            z_max[z] = block_offset
        else:
            z_min[z] = min(z_min[z], block_offset)
            z_max[z] = max(z_max[z], block_offset)
        
        offset += 6 + 8192
        f.seek(offset)
        
for z in sorted(z_min.keys()):
    span = z_max[z] - z_min[z]
    print(f"Z={z}: min={z_min[z]}, max={z_max[z]}, span={span}")

