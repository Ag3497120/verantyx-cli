import mlx.core as mx

B = 1
nH = 40
nKv = 10
L_q = 1
L_kv = 5
hD = 128

q = mx.random.normal((B, nH, L_q, hD))
k = mx.random.normal((B, nKv, L_kv, hD))
v = mx.random.normal((B, nKv, L_kv, hD))

# Tile k and v
repeats = nH // nKv
k = mx.tile(k, (1, repeats, 1, 1))
v = mx.tile(v, (1, repeats, 1, 1))

# Mask
linds = mx.arange(L_q)[:, None]
rinds = mx.arange(L_kv)[None, :]
mask_bool = linds >= rinds
mask = mx.where(mask_bool, mx.zeros(1), mx.array(-float('inf')))

try:
    out = mx.fast.scaled_dot_product_attention(q, k, v, scale=1.0, mask=mask)
    print("Success! Output shape:", out.shape)
except Exception as e:
    print("Error:", e)
