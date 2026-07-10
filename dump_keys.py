import struct

def main():
    with open('qwen_9b_full.jgen', 'rb') as f:
        magic = f.read(4)
        version = struct.unpack("<I", f.read(4))[0]
        count = struct.unpack("<I", f.read(4))[0]
        
        for _ in range(count):
            name_len_bytes = f.read(2)
            if not name_len_bytes:
                break
            name_len = struct.unpack("<H", name_len_bytes)[0]
            name = f.read(name_len).decode('utf-8', errors='ignore')
            ttype = struct.unpack("<B", f.read(1))[0]
            if ttype == 1:
                rows, cols, rank = struct.unpack("<I I I", f.read(12))
                bytes_to_skip = (rows*rank + rank + cols*rank + cols + rows + rank*rank) * 2
            elif ttype == 2:
                rows, cols = struct.unpack("<I I", f.read(8))
                bytes_to_skip = rows * cols * 2
            elif ttype == 3:
                length = struct.unpack("<I", f.read(4))[0]
                bytes_to_skip = length * 2
            else:
                break
            
            print(f"Name: {name}")
            f.seek(bytes_to_skip, 1)

if __name__ == "__main__":
    main()
