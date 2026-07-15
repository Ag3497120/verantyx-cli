import mlx.core as mx

B = 1
L = 1
nState = 5120
nMlp = 13696

x = mx.random.normal((B, L, nState))
mlpGate = mx.random.normal((nMlp, nState))
mlpLinear = mx.random.normal((nMlp, nState))
mlpResid = mx.random.normal((nState, nMlp))

try:
    gate = mx.matmul(x, mlpGate.T).astype(mx.float32)
    linear = mx.matmul(x, mlpLinear.T).astype(mx.float32)
    hidden = mx.silu(gate) * linear
    out = mx.matmul(hidden.astype(mx.float16), mlpResid.T)
    print("Success MLP! Output shape:", out.shape)
except Exception as e:
    print("Error:", e)

