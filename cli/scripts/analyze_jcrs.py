import struct
import sys
import os

def analyze_jcrs(filepath):
    print(f"Analyzing {filepath} ...")
    size = os.path.getsize(filepath)
    print(f"File size: {size / (1024*1024*1024):.2f} GB")
    
    with open(filepath, "rb") as f:
        magic = f.read(4)
        if magic != b"JCRS":
            print("Not a valid JCRS file.")
            return
            
        version = struct.unpack("<I", f.read(4))[0]
        tensor_count = struct.unpack("<I", f.read(4))[0]
        print(f"Version: {version}, Total Tensors: {tensor_count}")
        
        for i in range(min(5, tensor_count)):
            try:
                name_len = struct.unpack("<H", f.read(2))[0]
                name = f.read(name_len).decode('utf-8')
                t_type = struct.unpack("<B", f.read(1))[0]
                
                # Try to guess the format based on type. In JGEN (v1) this was usually float16 Dense (0) or JCross (1)
                if t_type == 1: # JCross (rows, cols, rank)
                    rows, cols, rank = struct.unpack("<I I I", f.read(12))
                    print(f"  Tensor {i} [JCross]: {name} - Rows: {rows}, Cols: {cols}, Rank: {rank}")
                    # Skip bytes. Let's assume float16 (2 bytes per param)
                    data_size = (rows*rank + rank + cols*rank + cols + rows) * 2
                    f.seek(data_size, os.SEEK_CUR)
                elif t_type == 0: # Dense (rows, cols)
                    rows, cols = struct.unpack("<I I", f.read(8))
                    print(f"  Tensor {i} [Dense]: {name} - Rows: {rows}, Cols: {cols}")
                    # Assume float16
                    data_size = rows * cols * 2
                    f.seek(data_size, os.SEEK_CUR)
                else:
                    print(f"  Unknown tensor type: {t_type}")
                    break
            except Exception as e:
                print(f"Error parsing tensor {i}: {e}")
                break

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_jcrs(sys.argv[1])
    else:
        print("Usage: python3 analyze_jcrs.py <path_to_jcrs>")
