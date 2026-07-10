import struct
import numpy as np

def print_decoded(data, name):
    print(f"--- {name} ---")
    print(f"Raw hex: {data.hex()}")
    # float16
    f16 = np.frombuffer(data, dtype=np.float16)
    print(f"float16 (LE): {f16}")
    
    # bfloat16 (we can parse manually or use struct)
    bf16_vals = []
    for i in range(0, len(data), 2):
        chunk = data[i:i+2]
        # convert to float32 by padding 16 bits of 0 at the end
        f32_bytes = b'\x00\x00' + chunk
        val = struct.unpack('<f', f32_bytes)[0]
        bf16_vals.append(val)
    print(f"bfloat16 (LE): {bf16_vals}")

with open("qwen_27b.jcross", "rb") as f:
    f.seek(50334720) # Z=0 linearQkv first block
    data = f.read(16)
    print_decoded(data, "Z=0 linearQkv block")
