#include <metal_stdlib>
using namespace metal;



kernel void kernel_linear_conv1d(
    device float* mixed_qkv [[buffer(0)]],
    device float* conv_state [[buffer(1)]],
    device const half* weight [[buffer(2)]],
    device const float* bias [[buffer(3)]],
    constant uint& layer_idx [[buffer(4)]],
    constant uint& conv_dim [[buffer(5)]],
    constant uint& use_bias [[buffer(6)]],
    uint id [[thread_position_in_grid]]
) {
    if (id >= conv_dim) return;
    uint state_offset = layer_idx * (conv_dim * 3) + id * 3;
    uint weight_offset = id * 4;
    
    float x_new = mixed_qkv[id];
    float x0 = conv_state[state_offset + 0];
    float x1 = conv_state[state_offset + 1];
    float x2 = conv_state[state_offset + 2];
    
    conv_state[state_offset + 0] = x1;
    conv_state[state_offset + 1] = x2;
    conv_state[state_offset + 2] = x_new;
    
    float out = x0 * (float)(weight[weight_offset + 0]) +
                x1 * (float)(weight[weight_offset + 1]) +
                x2 * (float)(weight[weight_offset + 2]) +
                x_new * (float)(weight[weight_offset + 3]);
                
    if (use_bias > 0) out += bias[id];
    mixed_qkv[id] = out * (1.0 / (1.0 + exp(-out)));
}

kernel void kernel_linear_l2norm(
    device float* qkv_buffer [[buffer(0)]],
    constant uint& total_k_dim [[buffer(1)]],
    uint id [[thread_position_in_grid]]
) {
    uint num_k_heads = total_k_dim / 128;
    if (id >= num_k_heads) return;
    
    uint head_offset = id * 128;
    
    float q_sum = 0;
    float k_sum = 0;
    for (uint i = 0; i < 128; ++i) {
        float q_val = qkv_buffer[head_offset + i];
        float k_val = qkv_buffer[total_k_dim + head_offset + i];
        q_sum += q_val * q_val;
        k_sum += k_val * k_val;
    }
    
    // Python l2norm: x * rsqrt(sum(x^2) + 1e-6)
    float q_inv_norm = rsqrt(q_sum + 1e-6);
    float k_inv_norm = rsqrt(k_sum + 1e-6);
    
    // Python PyTorch delta rule scales query by 1 / sqrt(head_k_dim)
    q_inv_norm *= 0.08838834764; // 1.0 / sqrt(128.0)
    
    for (uint i = 0; i < 128; ++i) {
        qkv_buffer[head_offset + i] *= q_inv_norm;
        qkv_buffer[total_k_dim + head_offset + i] *= k_inv_norm;
    }
}

kernel void kernel_linear_recurrent_step(
    device const float* mixed_qkv [[buffer(0)]],
    device const float* b [[buffer(1)]],
    device const float* a [[buffer(2)]],
    device const half* dt_bias [[buffer(3)]],
    device const half* A_log [[buffer(4)]],
    device float* recurrent_state [[buffer(5)]],
    device float* core_attn_out [[buffer(6)]],
    constant uint& layer_idx [[buffer(7)]],
    constant uint& num_v_heads [[buffer(8)]],
    constant uint& num_k_heads [[buffer(9)]],
    constant uint& head_k_dim [[buffer(10)]],
    constant uint& head_v_dim [[buffer(11)]],
    uint v_head [[threadgroup_position_in_grid]],
    uint v_dim [[thread_position_in_threadgroup]]
) {
    uint k_head = v_head / (num_v_heads / num_k_heads);
    
    device const float* q_ptr = mixed_qkv + k_head * head_k_dim;
    device const float* k_ptr = mixed_qkv + (num_k_heads * head_k_dim) + k_head * head_k_dim;
    device const float* v_ptr = mixed_qkv + (num_k_heads * head_k_dim * 2) + v_head * head_v_dim;
    
    float b_val = b[v_head];
    float beta = 1.0 / (1.0 + exp(-b_val));
    
    float a_val = a[v_head];
    float a_dt = a_val + (float)dt_bias[v_head];
    float softplus_a = log(1.0 + exp(a_dt));
    
    float g_val = -exp((float)A_log[v_head]) * softplus_a;
    float g_t = exp(g_val);
    
    float v_t = v_ptr[v_dim];
    
    // state offset: layer_idx * (48 * 128 * 128) + v_head * (128 * 128) + k_dim * 128 + v_dim
    // Let's iterate over k_dim inside this thread to update the column of the state matrix.
    // Each thread (v_dim) processes a specific column of the state matrix.
    // First pass: compute kv_mem = sum_k (state[k, v] * k_t[k])
    // Note: state is multiplied by g_t before being used
    float kv_mem = 0.0;
    uint state_base = layer_idx * (num_v_heads * head_k_dim * head_v_dim) + v_head * (head_k_dim * head_v_dim) + v_dim;
    
    for (uint k = 0; k < head_k_dim; ++k) {
        uint idx = state_base + k * head_v_dim;
        float state_val = recurrent_state[idx] * g_t;
        kv_mem += state_val * k_ptr[k];
    }
    
    // Compute delta = (v_t - kv_mem) * beta
    float delta = (v_t - kv_mem) * beta;
    
    // Second pass: Update state and compute out_val = sum_k (state * q_t)
    float out_val = 0.0;
    for (uint k = 0; k < head_k_dim; ++k) {
        uint idx = state_base + k * head_v_dim;
        float state_val = recurrent_state[idx] * g_t;
        state_val += k_ptr[k] * delta;
        recurrent_state[idx] = state_val;
        out_val += state_val * q_ptr[k];
    }
    
    core_attn_out[v_head * head_v_dim + v_dim] = out_val;
}
kernel void kernel_linear_rmsnorm_gated(
    device float* core_attn_out [[buffer(0)]], // [48, 128]
    device const float* z [[buffer(1)]], // [48, 128]
    threadgroup float* shared_sum [[threadgroup(0)]], // 128 floats
    constant uint& head_v_dim [[buffer(2)]], // 128
    device const half* norm_weight [[buffer(3)]], // [128]
    uint v_head [[threadgroup_position_in_grid]], // 0 to 47
    uint tid [[thread_position_in_threadgroup]] // 0 to 127
) {
    device float* head_ptr = core_attn_out + v_head * head_v_dim;
    device const float* z_ptr = z + v_head * head_v_dim;
    
    float val = head_ptr[tid];
    shared_sum[tid] = val * val;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    for (uint s = head_v_dim / 2; s > 0; s >>= 1) {
        if (tid < s) shared_sum[tid] += shared_sum[tid + s];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    
    float variance = shared_sum[0] / (float)head_v_dim;
    float inv_norm = rsqrt(variance + 1e-12);
    
    float z_val = z_ptr[tid];
    float silu_z = z_val * (1.0 / (1.0 + exp(-z_val)));
    
    head_ptr[tid] = val * inv_norm * (float)(norm_weight[v_head * head_v_dim + tid]) * silu_z;
}

kernel void kernel_linear_gated_only(
    device float* core_attn_out [[buffer(0)]], // [48, 128]
    device const float* z [[buffer(1)]], // [48, 128]
    constant uint& head_v_dim [[buffer(2)]], // 128
    uint v_head [[threadgroup_position_in_grid]], // 0 to 47
    uint tid [[thread_position_in_threadgroup]] // 0 to 127
) {
    device float* head_ptr = core_attn_out + v_head * head_v_dim;
    device const float* z_ptr = z + v_head * head_v_dim;
    
    float val = head_ptr[tid];
    float z_val = z_ptr[tid];
    float silu_z = z_val * (1.0 / (1.0 + exp(-z_val)));
    
    head_ptr[tid] = val * silu_z;
}
