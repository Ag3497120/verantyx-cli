import mlx.core as mx

try:
    a = mx.random.normal((1, 1, 1))
    b = mx.random.normal((5120, 65540))
    c = mx.matmul(a, b)
    mx.eval(c)
    print("Success")
except Exception as e:
    print("Error:", e)
