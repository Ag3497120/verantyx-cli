import struct
def read_jcross(file_path):
    with open(file_path, "rb") as f:
        magic = f.read(4)
        if magic != b"JGEN": return
        version = struct.unpack("<I", f.read(4))[0]
        
        while True:
            name_len_bytes = f.read(4)
            if not name_len_bytes: break
            name_len = struct.unpack("<I", name_len_bytes)[0]
            name = f.read(name_len).decode('utf-8')
            tensor_type = struct.unpack("<I", f.read(4))[0]
            
            if "o_proj" in name and "layers.0" in name:
                print(name, "Type:", tensor_type)
            
            if tensor_type == 1:
                rows = struct.unpack("<I", f.read(4))[0]
                cols = struct.unpack("<I", f.read(4))[0]
                rank = struct.unpack("<I", f.read(4))[0]
                f.read(rows * rank * 2)
                f.read(rank * 2)
                f.read(rank * cols * 2)
                f.read(cols * 2)
                f.read(rows * 2)
                f.read(rank * rank * 2)
            elif tensor_type == 2:
                rows = struct.unpack("<I", f.read(4))[0]
                cols = struct.unpack("<I", f.read(4))[0]
                f.read(rows * cols * 2)
            elif tensor_type == 3:
                numel = struct.unpack("<I", f.read(4))[0]
                f.read(numel * 2)

read_jcross("/home/ubuntu/model_glm.jgen")
