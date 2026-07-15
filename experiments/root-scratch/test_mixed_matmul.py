import mlx.core as mx

x = mx.random.normal((1, 1, 5120)).astype(mx.float32)
w = mx.random.normal((5120, 5120)).astype(mx.float16)

try:
    y = mx.matmul(x, w.T)
    mx.eval(y)
    print("Success Mixed Matmul! Output shape:", y.shape)
except Exception as e:
    print("Error:", type(e).__name__, "-", e)
