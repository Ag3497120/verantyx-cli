import sys, mmap, struct
f = open('cli/qwen_0.5b_full.jgen', 'rb')
mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
offset = 12
name_len = struct.unpack("<H", mm[offset:offset+2])[0]
offset += 2
name = mm[offset:offset+name_len].decode('utf-8', errors='ignore')
offset += name_len
t_type = struct.unpack("<B", mm[offset:offset+1])[0]
offset += 1
rows, cols, rank = struct.unpack("<I I I", mm[offset:offset+12])
print(f"Name: {name}, Rows: {rows}, Cols: {cols}, Rank: {rank}")
