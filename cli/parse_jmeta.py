import struct

with open("qwen_27b.jmeta", "rb") as f:
    magic = f.read(4)
    version = struct.unpack('<I', f.read(4))[0]
    tensor_count = struct.unpack('<I', f.read(4))[0]
    
    print(f"Version: {version}, Tensors: {tensor_count}")
    
    # Try little-endian first. If tensor_count is absurdly large, try big-endian.
    # But wait, my swift code uses .load(as: UInt32.self), which means LITTLE ENDIAN!
    # Swift's native endianness on ARM64 is Little Endian!
    # So the file MUST be little endian!
    
    # Let me just dump the first 32 bytes of the file in hex to see!
