import os
import re

files = [
    "Sources/VeraCore/Backends/Shaders.metal",
    "Sources/VeraCore/Backends/LMHeadShaders.metal",
    "Sources/VeraCore/Backends/AttentionShaders.metal",
    "Sources/VeraCore/Backends/LinearAttentionShaders.metal"
]

def fix_content(content):
    # Remove bf16_to_f32 definition completely
    content = re.sub(r'inline float bf16_to_f32\(ushort bfloat_val\) \{[\s\S]*?\}', '', content)
    
    # In kernel_rmsnorm, weight should be half*
    content = re.sub(r'device const ushort\* weight \[\[buffer\(1\)\]\]', r'device const half* weight [[buffer(1)]]', content)
    
    # In kernel_block_matmul
    content = re.sub(r'device const ushort\* matrix \[\[buffer\(0\)\]\]', r'device const half* matrix [[buffer(0)]]', content)
    content = re.sub(r'device const ushort\* block_ptr', r'device const half* block_ptr', content)
    content = re.sub(r'device const ushort\* row_ptr', r'device const half* row_ptr', content)
    content = re.sub(r'device const ushort\* file_data_0 \[\[buffer\(0\)\]\]', r'device const half* file_data_0 [[buffer(0)]]', content)
    content = re.sub(r'device const ushort\* file_data_1 \[\[buffer\(1\)\]\]', r'device const half* file_data_1 [[buffer(1)]]', content)
    
    # LMHeadShaders
    content = re.sub(r'device const ushort\* lm_head_weight \[\[buffer\(1\)\]\]', r'device const half* lm_head_weight [[buffer(1)]]', content)
    content = re.sub(r'device const ushort\* final_norm_weight \[\[buffer\(3\)\]\]', r'device const half* final_norm_weight [[buffer(3)]]', content)
    content = re.sub(r'device const ushort\* row =', r'device const half* row =', content)
    content = re.sub(r'device const ushort\* embed_tokens \[\[buffer\(0\)\]\]', r'device const half* embed_tokens [[buffer(0)]]', content)
    
    # LinearAttentionShaders
    content = re.sub(r'device const ushort\* norm_weight \[\[buffer\(3\)\]\]', r'device const half* norm_weight [[buffer(3)]]', content)
    content = re.sub(r'device const ushort\* weight \[\[buffer\(2\)\]\]', r'device const half* weight [[buffer(2)]]', content)
    content = re.sub(r'device const ushort\* dt_bias \[\[buffer\(3\)\]\]', r'device const half* dt_bias [[buffer(3)]]', content)
    content = re.sub(r'device const ushort\* A_log \[\[buffer\(4\)\]\]', r'device const half* A_log [[buffer(4)]]', content)
    
    # Replace bf16_to_f32(...) with (float)(...)
    content = re.sub(r'bf16_to_f32\(([^)]+)\)', r'(float)(\1)', content)
    
    return content

for f in files:
    if os.path.exists(f):
        with open(f, 'r') as file:
            content = file.read()
        
        new_content = fix_content(content)
        
        with open(f, 'w') as file:
            file.write(new_content)
        print(f"Reverted {f}")
