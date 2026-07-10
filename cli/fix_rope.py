import re
with open('Sources/VeraCore/Backends/AttentionShaders.metal', 'r') as f:
    content = f.read()

new_rope = """kernel void kernel_rope(
    device float* q_vec [[buffer(0)]],
    device float* k_vec [[buffer(1)]],
    constant uint& num_q_heads [[buffer(2)]],
    constant uint& num_k_heads [[buffer(3)]],
    constant uint& head_dim [[buffer(4)]],
    constant uint& pos [[buffer(5)]],
    uint id [[thread_position_in_grid]]
) {
    uint q_size = num_q_heads * head_dim;
    uint k_size = num_k_heads * head_dim;
    
    // id goes from 0 to max(q_size, k_size) / 2 - 1
    // GPT-NeoX style pairs: x[i] and x[i + head_dim/2]
    
    uint half_dim = head_dim / 2;
    uint head_idx = id / half_dim;
    uint d = id % half_dim;
    
    float freq = 1.0 / pow(1000000.0, (float)(d * 2) / (float)head_dim);
    float val = (float)pos * freq;
    float cos_val = cos(val);
    float sin_val = sin(val);
    
    if (id < q_size / 2) {
        uint q_head_idx = id / half_dim;
        uint q_d = id % half_dim;
        uint q_idx = q_head_idx * head_dim + q_d;
        uint q_idx_partner = q_idx + half_dim;
        
        float q0 = q_vec[q_idx];
        float q1 = q_vec[q_idx_partner];
        
        q_vec[q_idx] = q0 * cos_val - q1 * sin_val;
        q_vec[q_idx_partner] = q0 * sin_val + q1 * cos_val;
    }
    
    if (id < k_size / 2) {
        uint k_head_idx = id / half_dim;
        uint k_d = id % half_dim;
        uint k_idx = k_head_idx * head_dim + k_d;
        uint k_idx_partner = k_idx + half_dim;
        
        float k0 = k_vec[k_idx];
        float k1 = k_vec[k_idx_partner];
        
        k_vec[k_idx] = k0 * cos_val - k1 * sin_val;
        k_vec[k_idx_partner] = k0 * sin_val + k1 * cos_val;
    }
}
"""

content = re.sub(r'kernel void kernel_rope\([^}]+\}', new_rope, content)

with open('Sources/VeraCore/Backends/AttentionShaders.metal', 'w') as f:
    f.write(content)
