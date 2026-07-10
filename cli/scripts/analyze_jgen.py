import struct
import sys
import os

def analyze_jgen(filepath):
    print(f"Analyzing {filepath} ...")
    size = os.path.getsize(filepath)
    print(f"File size: {size / (1024*1024*1024):.2f} GB")
    
    with open(filepath, "rb") as f:
        magic = f.read(4)
        if magic != b"JGEN":
            print("Not a valid JGEN file.")
            return
            
        version = struct.unpack("<I", f.read(4))[0]
        tensor_count = struct.unpack("<I", f.read(4))[0]
        print(f"Version: {version}, Total Tensors: {tensor_count}")
        
        ranks = []
        rows_list = []
        
        for i in range(tensor_count):
            try:
                name_len = struct.unpack("<H", f.read(2))[0]
                name = f.read(name_len).decode('utf-8')
                t_type = struct.unpack("<B", f.read(1))[0]
                
                if t_type == 1:
                    rows, cols, rank = struct.unpack("<I I I", f.read(12))
                    ranks.append(rank)
                    rows_list.append((rows, cols))
                    
                    if i < 5 or i > tensor_count - 5:
                        print(f"  Tensor {i}: {name} - Rows: {rows}, Cols: {cols}, Rank: {rank}")
                    elif i == 5:
                        print(f"  ... (skipping intermediate tensors) ...")
                        
                    # Skip the actual weight data: U, S, V, mx, my
                    data_size = (rows*rank + rank + cols*rank + cols + rows) * 2
                    f.seek(data_size, os.SEEK_CUR)
            except Exception as e:
                print(f"Error parsing tensor {i}: {e}")
                break
                
        if ranks:
            print(f"Analyzed {len(ranks)} JCross tensors.")
            print(f"Average Rank: {sum(ranks)/len(ranks):.1f}")
            print(f"Min Rank: {min(ranks)}, Max Rank: {max(ranks)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_jgen(sys.argv[1])
    else:
        print("Usage: python3 analyze_jgen.py <path_to_jgen>")
