import mlx.core as mx

x = mx.random.normal((1, 1, 5120))
try:
    y = x.reshape(1, 1, 10, 128)
    mx.eval(y)
except Exception as e:
    print("Error:", type(e).__name__, "-", e)
