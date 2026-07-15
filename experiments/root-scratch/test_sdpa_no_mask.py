import mlx.core as mx

B = 1
nH = 40
L_q = 1
L_k = 5
hD = 128

q = mx.random.normal((B, nH, L_q, hD))
k = mx.random.normal((B, nH, L_k, hD))
v = mx.random.normal((B, nH, L_k, hD))

try:
    y = mx.fast.scaled_dot_product_attention(q, k, v, scale=1.0, mask=None)
    mx.eval(y)
    print("Success SDPA No Mask! Output shape:", y.shape)
except Exception as e:
    print("Error:", type(e).__name__, "-", e)
