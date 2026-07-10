import struct
import numpy as np

def check_nan(filepath="telepathic_coder_lossless.jgen"):
    print(f"Checking {filepath} for NaNs...")
    try:
        with open(filepath, "rb") as f:
            f.seek(12)
            while True:
                b = f.read(2)
                if not b or len(b) < 2: break
                name_len = struct.unpack("<H", b)[0]
                name = f.read(name_len).decode('utf-8')
                t_type = struct.unpack("<B", f.read(1))[0]
                
                if t_type == 1:
                    rows, cols, rank = struct.unpack("<I I I", f.read(12))
                    
                    def check_and_read(size_bytes, label):
                        data = f.read(size_bytes)
                        arr = np.frombuffer(data, dtype=np.float16)
                        if np.isnan(arr).any() or np.isinf(arr).any():
                            print(f"[{name}] {label} CONTAINS NaN/Inf!")
                            return True
                        if len(arr) > 0:
                            amax = np.max(np.abs(arr))
                            if amax > 50.0:
                                print(f"[{name}] {label} has extreme values! max_abs={amax:.2f}, mean={np.mean(arr):.4f}")
                        return False
                        
                    has_nan = False
                    has_nan |= check_and_read(rows * rank * 2, "U")
                    has_nan |= check_and_read(rank * 2, "S")
                    has_nan |= check_and_read(cols * rank * 2, "V")
                    has_nan |= check_and_read(cols * 2, "mx")
                    has_nan |= check_and_read(rows * 2, "my")
                    
                    if has_nan:
                        return
                elif t_type == 2:
                    rows, cols = struct.unpack("<I I", f.read(8))
                    f.seek(rows * cols * 2, 1)
                elif t_type == 3:
                    v_size = struct.unpack("<I", f.read(4))[0]
                    f.seek(v_size * 2, 1)
        print("Scan complete. No NaNs found.")
    except Exception as e:
        print(f"Error: {e}")

check_nan()
