import re
with open('Sources/VeraCore/Backends/LinearAttentionShaders.metal', 'r') as f:
    content = f.read()

content = re.sub(
    r'head_ptr\[tid\] = val \* inv_norm \* \(float\)\(norm_weight\[tid\]\) \* silu_z;',
    r'head_ptr[tid] = val * inv_norm * (float)(norm_weight[v_head * head_v_dim + tid]) * silu_z;',
    content
)

with open('Sources/VeraCore/Backends/LinearAttentionShaders.metal', 'w') as f:
    f.write(content)
