#include <metal_stdlib>
using namespace metal;

kernel void kernel_rope(
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
    uint rope_half_dim = head_dim / 2; // For Qwen, rotate entire head
    uint head_idx = id / half_dim;
    uint d = id % half_dim;
    
    if (d >= rope_half_dim) return; // Only rotate first elements
    
    float freq = 1.0 / pow(1000000.0, (float)(d * 2) / (float)(rope_half_dim * 2));
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

kernel void kernel_write_kv_cache(
    device const float* k_in [[buffer(0)]],
    device const float* v_in [[buffer(1)]],
    device half* kv_cache [[buffer(2)]],
    constant uint& layer_idx [[buffer(3)]],
    constant uint& pos [[buffer(4)]],
    uint id [[thread_position_in_grid]]
) {
    if (id >= 1024) return;
    // kv_cache shape: (num_layers, max_seq_len, 2, num_kv_heads * head_dim)
    // 64 layers, 4096 seq_len, 2, 1024
    uint offset = layer_idx * (4096 * 2 * 1024) + pos * (2 * 1024);
    kv_cache[offset + id] = (half)k_in[id];
    kv_cache[offset + 1024 + id] = (half)v_in[id];
}

kernel void kernel_attention(
    device const float* q_vec [[buffer(0)]],
    device const half* kv_cache [[buffer(1)]],
    device float* out_vec [[buffer(2)]],
    constant uint& seq_len [[buffer(3)]],
    constant uint& layer_idx [[buffer(4)]],
    constant uint& num_q_heads [[buffer(5)]],
    constant uint& num_kv_heads [[buffer(6)]],
    constant uint& head_dim [[buffer(7)]],
    threadgroup float* shared_scores [[threadgroup(0)]],
    uint q_head [[threadgroup_position_in_grid]],
    uint tid [[thread_position_in_threadgroup]],
    uint threads_per_tg [[threads_per_threadgroup]]
) {
    uint kv_head = q_head / (num_q_heads / num_kv_heads);
    device const float* q_head_ptr = q_vec + q_head * head_dim;
    float scale = 1.0 / sqrt((float)head_dim);
    
    // offset to current layer's KV cache
    uint layer_offset = layer_idx * (4096 * 2 * 1024);
    
    for (uint t = tid; t < seq_len; t += threads_per_tg) {
        uint token_offset = layer_offset + t * (2 * 1024);
        device const half* k_head_ptr = kv_cache + token_offset + kv_head * head_dim;
        
        float score = 0.0;
        for (uint d = 0; d < head_dim; ++d) {
            score += q_head_ptr[d] * (float)k_head_ptr[d];
        }
        shared_scores[t] = score * scale;
    }
    
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    // Softmax (Computed by a single thread to avoid race conditions)
    if (tid == 0) {
        float max_score = -INFINITY;
        for (uint t = 0; t < seq_len; ++t) {
            float s = shared_scores[t];
            max_score = max(max_score, s);
        }
        
        float sum_exp = 0.0;
        for (uint t = 0; t < seq_len; ++t) {
            float e = exp(shared_scores[t] - max_score);
            shared_scores[t] = e;
            sum_exp += e;
        }
        
        for (uint t = 0; t < seq_len; ++t) {
            shared_scores[t] /= sum_exp;
        }
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    for (uint d = tid; d < head_dim; d += threads_per_tg) {
        float out_val = 0.0;
        for (uint t = 0; t < seq_len; ++t) {
            uint token_offset = layer_offset + t * (2 * 1024);
            device const half* v_head_ptr = kv_cache + token_offset + 1024 + kv_head * head_dim;
            out_val += shared_scores[t] * (float)v_head_ptr[d];
        }
        out_vec[q_head * head_dim + d] = out_val;
    }
}

kernel void kernel_head_rmsnorm(
    device float* vec [[buffer(0)]],
    device const half* weight [[buffer(1)]],
    constant uint& head_dim [[buffer(2)]],
    threadgroup float* shared_sum [[threadgroup(0)]],
    uint head_id [[threadgroup_position_in_grid]],
    uint tid [[thread_position_in_threadgroup]]
) {
    device float* head_ptr = vec + head_id * head_dim;
    float val = head_ptr[tid];
    shared_sum[tid] = val * val;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    // Assumes head_dim <= 256
    for (uint s = 128; s > 0; s >>= 1) {
        if (tid < s) shared_sum[tid] += shared_sum[tid + s];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    
    float variance = shared_sum[0] / (float)head_dim;
    float inv_norm = rsqrt(variance + 1e-6);
    
    head_ptr[tid] = val * inv_norm * (float)weight[tid];
}

kernel void kernel_qk_norm(
    device float* x_vec [[buffer(0)]],
    device const float* w [[buffer(1)]],
    constant uint& head_dim [[buffer(2)]],
    threadgroup float* shared_sum [[threadgroup(0)]],
    uint head_id [[threadgroup_position_in_grid]],
    uint tid [[thread_position_in_threadgroup]]
) {
    if (tid < head_dim) {
        float val = x_vec[head_id * head_dim + tid];
        shared_sum[tid] = val * val;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    // Simple reduction
    for (uint stride = head_dim / 2; stride > 0; stride /= 2) {
        if (tid < stride) {
            shared_sum[tid] += shared_sum[tid + stride];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    
    float variance = shared_sum[0] / float(head_dim);
    float inv_std = rsqrt(variance + 1e-6f);
    
    if (tid < head_dim) {
        float val = x_vec[head_id * head_dim + tid];
        x_vec[head_id * head_dim + tid] = val * inv_std * w[tid];
    }
}
