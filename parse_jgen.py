import sys

def parse(path):
    with open(path, 'rb') as f:
        while True:
            name_len_bytes = f.read(4)
            if not name_len_bytes: break
            name_len = int.from_bytes(name_len_bytes, 'little')
            name = f.read(name_len).decode('utf-8')
            tensor_type = int.from_bytes(f.read(4), 'little')
            
            if tensor_type == 1:
                rows = int.from_bytes(f.read(4), 'little')
                cols = int.from_bytes(f.read(4), 'little')
                rank = int.from_bytes(f.read(4), 'little')
                print(f"{name}: SVD ({rows}x{cols} r={rank})")
                bytes_to_skip = (rows*rank + rank + cols*rank + cols + rows + rank*rank)*2
            elif tensor_type == 2:
                rows = int.from_bytes(f.read(4), 'little')
                cols = int.from_bytes(f.read(4), 'little')
                print(f"{name}: Dense2D ({rows}x{cols})")
                bytes_to_skip = rows * cols * 2
            elif tensor_type == 3:
                length = int.from_bytes(f.read(4), 'little')
                print(f"{name}: Dense1D ({length})")
                bytes_to_skip = length * 2
            else:
                print("Unknown type")
                break
            
            f.seek(bytes_to_skip, 1)

parse('qwen_0.5b_full.jgen')
