import mlx.core as mx

B = 1
L = 1
in_features = 5120
out_features = 5120
bits = 8
group_size = 64

x = mx.random.normal((B, L, in_features))
weight = mx.random.uniform(0, 255, (out_features, in_features // (32 // bits))).astype(mx.uint32)
scales = mx.random.normal((out_features, in_features // group_size))
biases = mx.random.normal((out_features, in_features // group_size))

try:
    y = mx.quantized_matmul(x, weight, scales, biases, transpose=True, group_size=group_size, bits=bits)
    mx.eval(y)
    print("Success! Output shape:", y.shape)
except Exception as e:
    print("Error:", type(e).__name__, "-", e)
