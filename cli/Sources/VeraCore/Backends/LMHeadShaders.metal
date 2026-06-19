#include <metal_stdlib>
using namespace metal;



inline float bfloat16_to_float32(uint16_t b) {
    uint32_t val = ((uint32_t)b) << 16;
    return as_type<float>(val);
}

kernel void kernel_lm_head(
    device const float* z_spine [[buffer(0)]],
    device const ushort* lm_head_weight [[buffer(1)]],
    device float* logits [[buffer(2)]],
    device const ushort* final_norm_weight [[buffer(3)]],
    constant uint& vocab_size [[buffer(4)]],
    constant uint& dim [[buffer(5)]],
    device const float* variance_buffer [[buffer(6)]],
    uint tid [[thread_position_in_grid]]
) {
    if (tid >= vocab_size) return;
    
    float inv_norm = variance_buffer[0];
    
    float val = 0.0;
    device const ushort* row = lm_head_weight + tid * dim;
    for (uint i = 0; i < dim; ++i) {
        float fw = bfloat16_to_float32(final_norm_weight[i]);
        float rw = bfloat16_to_float32(row[i]);
        val += (float)z_spine[i] * inv_norm * fw * rw;
    }
    logits[tid] = val;
}

kernel void kernel_lm_head_norm(
    device const float* z_spine [[buffer(0)]],
    device float* variance_buffer [[buffer(1)]],
    threadgroup float* shared_sum [[threadgroup(0)]],
    constant uint& dim [[buffer(2)]],
    uint tid [[thread_position_in_threadgroup]],
    uint threads_per_threadgroup [[threads_per_threadgroup]]
) {
    float thread_sum = 0.0;
    for (uint i = tid; i < dim; i += threads_per_threadgroup) {
        float val = (float)z_spine[i];
        thread_sum += val * val;
    }
    shared_sum[tid] = thread_sum;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    for (uint s = threads_per_threadgroup / 2; s > 0; s >>= 1) {
        if (tid < s) shared_sum[tid] += shared_sum[tid + s];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    
    if (tid == 0) {
        float variance = shared_sum[0] / (float)dim;
        variance_buffer[0] = rsqrt(variance + 1e-6);
    }
}

kernel void kernel_argmax(
    device const float* logits [[buffer(0)]],
    device uint* out_token [[buffer(1)]],
    constant uint& vocab_size [[buffer(2)]],
    uint tid [[thread_position_in_grid]]
) {
    if (tid != 0) return;
    
    float max_val = -1e9;
    uint best_idx = 0;
    
    for (uint i = 0; i < vocab_size; ++i) {
        if (logits[i] > max_val) {
            max_val = logits[i];
            best_idx = i;
        }
    }
    out_token[0] = best_idx;
}

kernel void kernel_embed_lookup(
    device const ushort* embed_tokens [[buffer(0)]],
    device float* z_spine [[buffer(1)]],
    constant uint& token_id [[buffer(2)]],
    constant uint& dim [[buffer(3)]],
    uint tid [[thread_position_in_grid]]
) {
    if (tid >= dim) return;
    z_spine[tid] = bfloat16_to_float32(embed_tokens[token_id * dim + tid]);
}
