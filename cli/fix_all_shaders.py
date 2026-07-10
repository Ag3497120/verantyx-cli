import os
import re

files = [
    "Sources/VeraCore/Backends/Shaders.metal",
    "Sources/VeraCore/Backends/LMHeadShaders.metal",
    "Sources/VeraCore/Backends/AttentionShaders.metal",
    "Sources/VeraCore/Backends/LinearAttentionShaders.metal"
]

def fix_content(content):
    # Fix bf16_to_f32 definition
    content = content.replace("inline float bf16_to_f32(half bfloat_val)", "inline float bf16_to_f32(ushort bfloat_val)")
    
    # In kernel_rmsnorm, weight should be ushort*
    content = re.sub(r'device const half\* weight \[\[buffer\(1\)\]\]', r'device const ushort* weight [[buffer(1)]]', content)
    
    # In kernel_block_matmul, matrix should be ushort*
    content = re.sub(r'device const half\* matrix \[\[buffer\(0\)\]\]', r'device const ushort* matrix [[buffer(0)]]', content)
    content = re.sub(r'device const half\* block_ptr =', r'device const ushort* block_ptr =', content)
    content = re.sub(r'device const half\* row_ptr =', r'device const ushort* row_ptr =', content)
    
    # In kernel_lm_head, lm_head_weight should be ushort*
    content = re.sub(r'device const half\* lm_head_weight \[\[buffer\(1\)\]\]', r'device const ushort* lm_head_weight [[buffer(1)]]', content)
    content = re.sub(r'device const half\* final_norm_weight \[\[buffer\(3\)\]\]', r'device const ushort* final_norm_weight [[buffer(3)]]', content)
    content = re.sub(r'device const half\* row =', r'device const ushort* row =', content)
    content = re.sub(r'\(float\)\(final_norm_weight\[i\]\)', r'bf16_to_f32(final_norm_weight[i])', content)
    content = re.sub(r'\(float\)\(row\[i\]\)', r'bf16_to_f32(row[i])', content)
    
    # In LinearAttentionShaders.metal, norm_weight should be ushort*
    content = re.sub(r'device const half\* norm_weight \[\[buffer\(3\)\]\]', r'device const ushort* norm_weight [[buffer(3)]]', content)
    content = re.sub(r'\(float\)norm_weight\[tid\]', r'bf16_to_f32(norm_weight[tid])', content)
    
    # In AttentionShaders.metal, kv_cache could still be half if we just store it as float16?
    # Actually Qwen is bfloat16, but KV cache doesn't matter if we just use half for storage.
    # Wait, the kv_cache is written from float to half: `kv_cache[offset] = (half)k_in[id]`
    # And read from half to float: `(float)k_head_ptr[d]`
    # This is fine because it's just casting float <-> half natively in Metal.
    
    return content

for f in files:
    if os.path.exists(f):
        with open(f, 'r') as file:
            content = file.read()
        
        # also replace some leftover bf16_to_f32(weight[i]) where weight is still half? 
        # wait, if weight is ushort, bf16_to_f32(weight[i]) will work!
        new_content = fix_content(content)
        
        with open(f, 'w') as file:
            file.write(new_content)
        print(f"Fixed {f}")
