import mlx.core as mx

x = mx.random.normal((1, 1, 5120))
w = mx.random.randint(0, 255, (5120, 1280), dtype=mx.uint32) # Should be [1280, 5120]
s = mx.random.normal((5120, 20))
b = mx.random.normal((5120, 20))

try:
    y = mx.quantized_matmul(x, w, scales=s, biases=b, transpose=True, group_size=64, bits=8)
    mx.eval(y)
    print("Success")
except Exception as e:
    print("Error:", str(e))
