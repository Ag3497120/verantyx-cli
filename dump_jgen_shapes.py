import struct

def dump_jgen(path):
    with open(path, "rb") as f:
        magic = f.read(4)
        version = struct.unpack("<I", f.read(4))[0]
        
        offset = 8
        if version == 3:
            total_tensors = struct.unpack("<I", f.read(4))[0]
            offset += 4
        
        while True:
            # We just want the first few
            if version == 3:
                name_len_bytes = f.read(2)
                if not name_len_bytes: break
                name_len = struct.unpack("<H", name_len_bytes)[0]
            else:
                name_len_bytes = f.read(4)
                if not name_len_bytes: break
                name_len = struct.unpack("<I", name_len_bytes)[0]
            
            name = f.read(name_len).decode('utf-8')
            
            if version == 3:
                t_type = struct.unpack("<B", f.read(1))[0]
            else:
                t_type = struct.unpack("<I", f.read(4))[0]
                
            if t_type == 1:
                rows, cols, rank = struct.unpack("<III", f.read(12))
                total_bytes = (rows * rank * 2) + (rank * 2) + (cols * rank * 2) + (cols * 2) + (rows * 2) + (rank * rank * 2)
                print(f"SVDLossless: {name} (rows={rows}, cols={cols}, rank={rank})")
                f.seek(total_bytes, 1)
            elif t_type == 2:
                rows, cols = struct.unpack("<II", f.read(8))
                print(f"Dense2D: {name} (rows={rows}, cols={cols})")
                f.seek(rows * cols * 2, 1)
            elif t_type == 3:
                length = struct.unpack("<I", f.read(4))[0]
                print(f"Dense1D: {name} (length={length})")
                f.seek(length * 2, 1)
            
            if 'input_layernorm.weight' in name or 'embed_tokens' in name:
                pass
            else:
                # we don't print everything to avoid spam
                pass

dump_jgen("/home/ubuntu/model_glm.jgen")
