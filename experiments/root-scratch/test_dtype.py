import mlx.core as mx
print("mx.float16 is", mx.float16)
try:
    mx.set_default_dtype(mx.float16)
except Exception as e:
    print("set_default_dtype error:", e)
    
print("Attributes in mx:", [a for a in dir(mx) if 'default' in a or 'type' in a])
