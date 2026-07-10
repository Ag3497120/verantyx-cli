import struct
import sys

def parse_jgen(filepath):
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'JGEN':
            print("Invalid magic")
            return
            
        version = struct.unpack('<I', f.read(4))[0]
        num_layers, rank = struct.unpack('<I I', f.read(8))
        print(f"JGEN Version: {version}, Layers: {num_layers}, Rank: {rank}")
        
        while True:
            type_byte = f.read(1)
            if not type_byte:
                break
            btype = type_byte[0]
            
            if btype == 0:
                rows, cols = struct.unpack('<I I', f.read(8))
                print(f"[0] Embed: {rows}x{cols}")
                f.seek(rows * cols * 2, 1)
            elif btype == 1:
                rows, cols = struct.unpack('<I I', f.read(8))
                print(f"[1] LM Head: {rows}x{cols}")
                f.seek(rows * cols * 2, 1)
            elif btype == 2:
                rows, cols = struct.unpack('<I I', f.read(8))
                print(f"[2] Final Norm: {rows}x{cols}")
                f.seek(rows * cols * 2, 1)
            elif btype == 3:
                z, rows, cols = struct.unpack('<B I I', f.read(9))
                print(f"[3] Attn Norm Z={z}: {rows}x{cols}")
                f.seek(rows * cols * 2, 1)
            elif btype == 4:
                z, rows, cols = struct.unpack('<B I I', f.read(9))
                print(f"[4] MLP Norm Z={z}: {rows}x{cols}")
                f.seek(rows * cols * 2, 1)
            elif btype == 5:
                z, mtype, rows, cols, mrank = struct.unpack('<B B I I I', f.read(14))
                print(f"[5] Generative Matrix Z={z}, Type={mtype}: {rows}x{cols} Rank={mrank}")
                # Data blocks: U, S, V, modX, modY
                u_size = rows * mrank * 2
                s_size = mrank * 2
                v_size = cols * mrank * 2
                mod_x_size = cols * 2
                mod_y_size = rows * 2
                
                f.seek(u_size + s_size + v_size + mod_x_size + mod_y_size, 1)

if __name__ == '__main__':
    parse_jgen(sys.argv[1])
