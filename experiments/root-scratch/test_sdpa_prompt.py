import mlx.core as mx

B = 1
nH = 40
L = 5
hD = 128

q = mx.random.normal((B, nH, L, hD))
k = mx.random.normal((B, nH, L, hD))
v = mx.random.normal((B, nH, L, hD))

linds = mx.arange(L)[:, None]
rinds = mx.arange(L)[None, :]
mask_bool = linds >= rinds
mask = mx.where(mask_bool, mx.zeros(1), mx.array(-float('inf')))

try:
    y = mx.fast.scaled_dot_product_attention(q, k, v, scale=1.0, mask=mask)
    mx.eval(y)
    print("Success SDPA Prompt! Output shape:", y.shape)
except Exception as e:
    print("Error:", type(e).__name__, "-", e)
