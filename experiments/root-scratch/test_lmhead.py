import mlx.core as mx

x = mx.random.normal((1, 1, 5120))
w = mx.random.normal((65540, 5120))

try:
    y = mx.matmul(x, w.T)
    mx.eval(y)
    print("Success LMHead! Output shape:", y.shape)
except Exception as e:
    print("Error:", type(e).__name__, "-", e)
