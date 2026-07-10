import re

def fix_shaders_metal():
    path = "Sources/VeraCore/Backends/Shaders.metal"
    with open(path, 'r') as f:
        content = f.read()
    
    # kernel_rmsnorm
    content = content.replace("kernel void kernel_rmsnorm(\n    device const half* in_vec [[buffer(0)]],", "kernel void kernel_rmsnorm(\n    device const float* in_vec [[buffer(0)]],")
    
    with open(path, 'w') as f:
        f.write(content)

def fix_lmhead_metal():
    path = "Sources/VeraCore/Backends/LMHeadShaders.metal"
    with open(path, 'r') as f:
        content = f.read()
        
    content = content.replace("kernel void kernel_lm_head_norm(\n    device const half* in_vec [[buffer(0)]],", "kernel void kernel_lm_head_norm(\n    device const float* in_vec [[buffer(0)]],")
    content = content.replace("z_spine[tid] = bf16_to_f32(embed_tokens[token_id * dim + tid]);", "z_spine[tid] = (float)(embed_tokens[token_id * dim + tid]);")
    content = content.replace("bf16_to_f32(final_norm_weight[i])", "(float)(final_norm_weight[i])")
    content = content.replace("bf16_to_f32(row[i])", "(float)(row[i])")
    content = content.replace("bf16_to_f32(weight[i])", "(float)(weight[i])")
    
    with open(path, 'w') as f:
        f.write(content)

def fix_attention_metal():
    path = "Sources/VeraCore/Backends/AttentionShaders.metal"
    with open(path, 'r') as f:
        content = f.read()
        
    content = content.replace("device half* out_qkv [[buffer(0)]]", "device float* out_qkv [[buffer(0)]]")
    content = content.replace("device const half* z_spine [[buffer(1)]]", "device const float* z_spine [[buffer(1)]]")
    content = content.replace("device const half* k_cache [[buffer(2)]]", "device const float* k_cache [[buffer(2)]]")
    content = content.replace("device const half* v_cache [[buffer(3)]]", "device const float* v_cache [[buffer(3)]]")
    # But wait, are caches float32? Yes, kvCacheBuffer is allocated as 4 bytes per element!
    # Wait! Are out_qkv and z_spine float32? Yes, all spine/intermediate buffers are Float32!
    
    with open(path, 'w') as f:
        f.write(content)

fix_shaders_metal()
fix_lmhead_metal()
# fix_attention_metal() # Wait, let me check KV cache first!
