import re
with open('Sources/VeraCore/Backends/LinearAttentionShaders.metal', 'r') as f:
    content = f.read()

# Fix q, k, v order in kernel_linear_recurrent_step
# q size = num_k_heads * head_k_dim
# k size = num_k_heads * head_k_dim
# v size = num_v_heads * head_v_dim
content = re.sub(
    r'device const float\* v_ptr = mixed_qkv \+ v_head \* head_v_dim;\s*'
    r'device const float\* k_ptr = mixed_qkv \+ \(num_v_heads \* head_v_dim\) \+ k_head \* head_k_dim;\s*'
    r'device const float\* q_ptr = mixed_qkv \+ \(num_v_heads \* head_v_dim\) \+ \(num_k_heads \* head_k_dim\) \+ k_head \* head_k_dim;',
    
    r'device const float* q_ptr = mixed_qkv + k_head * head_k_dim;\n'
    r'    device const float* k_ptr = mixed_qkv + (num_k_heads * head_k_dim) + k_head * head_k_dim;\n'
    r'    device const float* v_ptr = mixed_qkv + (num_k_heads * head_k_dim * 2) + v_head * head_v_dim;',
    content
)

# Also fix the L2 norm on Q and K which expects them to be at the END if v, k, q.
# Wait, L2 norm in VeraMetalBackend.swift is applied to Q and K!
# I will fix VeraMetalBackend.swift later.

with open('Sources/VeraCore/Backends/LinearAttentionShaders.metal', 'w') as f:
    f.write(content)
