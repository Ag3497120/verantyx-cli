import struct
import numpy as np

with open("qwen_27b.jmeta", "rb") as f:
    f.seek(14) # skip magic(4), version(4), z(1), mtype(1), length(4)
    data = f.read(10)
    arr = np.frombuffer(data, dtype=np.float16)
    print("final_norm_weight first 5 elements as float16:", arr)
    
    # Let's also decode as bfloat16 just in case!
    # bfloat16 in numpy requires a trick (if not using ml_dtypes)
    # Actually I can just view as uint16, shift left 16, and view as float32
    u16 = np.frombuffer(data, dtype=np.uint16)
    u32 = np.zeros(5, dtype=np.uint32)
    u32[:] = u16
    u32 <<= 16
    bf16 = u32.view(np.float32)
    print("final_norm_weight first 5 elements as bfloat16:", bf16)
