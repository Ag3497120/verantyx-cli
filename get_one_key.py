import struct
with open("qwen_9b_full.jgen", "rb") as f:
    f.seek(12)
    while True:
        name_len_data = f.read(2)
        if not name_len_data:
            break
        name_len = struct.unpack("<H", name_len_data)[0]
        name = f.read(name_len).decode('utf-8')
        t_type = struct.unpack("<B", f.read(1))[0]
        if ".o_proj" in name:
            print(f"Found Key: {name}")
            break
        if t_type == 1:
            f.seek(12, 1) # SVDLossless meta size
            # wait, JGEN v3 has U, S, V, mod_x, mod_y, C_valve data following the metadata
            # We must parse the exact sizes from the metadata!
            rows, cols, rank = struct.unpack("<III", f.read(12))
            bytes_to_skip = (rows*rank + rank + cols*rank + cols + rows + rank*rank) * 2
            f.seek(bytes_to_skip, 1)
        elif t_type == 2:
            rows, cols = struct.unpack("<II", f.read(8))
            f.seek(rows * cols * 2, 1)
        elif t_type == 3:
            cols = struct.unpack("<I", f.read(4))[0]
            f.seek(cols * 2, 1)
