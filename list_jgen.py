import struct
with open("qwen_9b_full.jgen", "rb") as f:
    magic = f.read(4)
    version = struct.unpack("<I", f.read(4))[0]
    total_tensors = struct.unpack("<I", f.read(4))[0]
    print(f"Total Tensors: {total_tensors}")
    for i in range(min(5, total_tensors)):
        name_len = struct.unpack("<H", f.read(2))[0]
        name = f.read(name_len).decode('utf-8')
        t_type = struct.unpack("<B", f.read(1))[0]
        print(name, t_type)
        if t_type == 1:
            f.seek(12, 1) # skip dimensions
            # We can't skip the rest easily without calculating size. Let's just break.
            break
        elif t_type == 2:
            f.seek(8, 1)
        elif t_type == 3:
            f.seek(4, 1)
