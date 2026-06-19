#include <metal_stdlib>
using namespace metal;

inline float f16_to_float(ushort b) {
    return (float)as_type<half>(b);
}

kernel void kernel_add(
    device float* a [[buffer(0)]],
    device float* b [[buffer(1)]],
    constant uint& size [[buffer(2)]],
    constant float& amplification [[buffer(3)]],
    uint id [[thread_position_in_grid]]
) {
    if (id < size) {
        a[id] += b[id] * amplification;
    }
}

kernel void kernel_zero(
    device float* a [[buffer(0)]],
    constant uint& size [[buffer(1)]],
    uint id [[thread_position_in_grid]]
) {
    if (id < size) {
        atomic_store_explicit((device atomic_float*)&a[id], 0.0, memory_order_relaxed);
    }
}

kernel void kernel_swiglu(
    device float* gate [[buffer(0)]],
    device float* up [[buffer(1)]],
    constant uint& size [[buffer(2)]],
    uint id [[thread_position_in_grid]]
) {
    if (id >= size) return;
    float x = gate[id];
    // SiLU = x * sigmoid(x)
    float silu = x / (1.0 + exp(-x));
    gate[id] = silu * up[id];
}



kernel void kernel_clear_buffer(
    device float* out_vec [[buffer(0)]],
    uint id [[thread_position_in_grid]]
) {
    out_vec[id] = 0.0;
}

kernel void kernel_rmsnorm(
    device const float* in_vec [[buffer(0)]],
    device const half* weight [[buffer(1)]],
    device float* out_vec [[buffer(2)]],
    constant uint& size [[buffer(3)]],
    threadgroup float* shared_sum [[threadgroup(0)]],
    uint tid [[thread_position_in_threadgroup]],
    uint threads_per_threadgroup [[threads_per_threadgroup]]
) {
    float sum_sq = 0.0;
    for (uint i = tid; i < size; i += threads_per_threadgroup) {
        float val = (float)in_vec[i];
        sum_sq += val * val;
    }
    shared_sum[tid] = sum_sq;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    for (uint s = threads_per_threadgroup / 2; s > 0; s >>= 1) {
        if (tid < s) shared_sum[tid] += shared_sum[tid + s];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    
    float inv_norm = 1.0;
    if (tid == 0) {
        float mean_sq = shared_sum[0] / (float)size;
        shared_sum[0] = rsqrt(mean_sq + 1e-6);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    inv_norm = shared_sum[0];
    
    for (uint i = tid; i < size; i += threads_per_threadgroup) {
        out_vec[i] = (float)in_vec[i] * inv_norm * (float)(weight[i]);
    }
}

struct BlockInfo {
    uint rowIdx;
    uint colIdx;
    uint blockSize;
    uint pad;
    uint64_t byteOffset;
};

kernel void kernel_block_matmul(
    device const ushort* file_data_0 [[buffer(0)]],
    device const ushort* file_data_1 [[buffer(1)]],
    device const float* in_vec [[buffer(2)]],
    device atomic_float* out_vec [[buffer(3)]],
    device const BlockInfo* block_infos [[buffer(4)]],
    uint tid [[thread_position_in_threadgroup]], // 0...63
    uint bid [[threadgroup_position_in_grid]]
) {
    BlockInfo b = block_infos[bid];
    uint local_row = tid;
    
    device const ushort* block_ptr;
    if (b.pad == 0) block_ptr = file_data_0 + (b.byteOffset / 2);
    else block_ptr = file_data_1 + (b.byteOffset / 2);

    float sum = 0.0;
    device const ushort* row_ptr = block_ptr + local_row * 64;
    device const float* vec_ptr = in_vec + b.colIdx * 64;
    
    for (uint i = 0; i < 64; i += 4) {
        float w0 = f16_to_float(row_ptr[i]);
        float w1 = f16_to_float(row_ptr[i+1]);
        float w2 = f16_to_float(row_ptr[i+2]);
        float w3 = f16_to_float(row_ptr[i+3]);
        
        float v0 = vec_ptr[i];
        float v1 = vec_ptr[i+1];
        float v2 = vec_ptr[i+2];
        float v3 = vec_ptr[i+3];
        
        sum += w0*v0 + w1*v1 + w2*v2 + w3*v3;
    }
    
    uint global_row = b.rowIdx * 64 + local_row;
    atomic_fetch_add_explicit(&out_vec[global_row], sum, memory_order_relaxed);
}



kernel void kernel_split_q_gate(
    device const float* in_qkv [[buffer(0)]],
    device float* out_q [[buffer(1)]],
    device float* out_gate [[buffer(2)]],
    constant uint& num_heads [[buffer(3)]],
    constant uint& head_dim [[buffer(4)]],
    uint id [[thread_position_in_grid]]
) {
    if (id >= num_heads * head_dim) return;
    uint head_idx = id / head_dim;
    uint i = id % head_dim;
    uint in_idx = head_idx * (head_dim * 2) + i;
    out_q[id] = in_qkv[in_idx];
    out_gate[id] = in_qkv[in_idx + head_dim];
}

kernel void kernel_silu_mul(
    device float* q_out [[buffer(0)]],
    device const float* gate [[buffer(1)]],
    uint id [[thread_position_in_grid]]
) {
    float x = gate[id];
    float sigmoid_x = 1.0 / (1.0 + exp(-x));
    q_out[id] *= sigmoid_x;
}

kernel void kernel_generative_h(
    device const half* V [[buffer(0)]],        // shape: (cols, rank)
    device const float* in_vec [[buffer(1)]],  // shape: (cols)
    device const half* mod_x [[buffer(2)]],    // shape: (cols)
    device float* out_h [[buffer(3)]],         // shape: (rank)
    constant uint& cols [[buffer(4)]],
    constant uint& rank [[buffer(5)]],
    uint k [[thread_position_in_grid]]         // 0...rank-1
) {
    if (k >= rank) return;
    
    float sum = 0.0;
    // V is stored row-major: V[j, k] is at V[j * rank + k]
    for (uint j = 0; j < cols; j++) {
        float v_val = (float)V[j * rank + k];
        float mod_val = (float)mod_x[j];
        float x_val = in_vec[j];
        sum += v_val * mod_val * x_val;
    }
    
    out_h[k] = sum;
}

kernel void kernel_generative_y(
    device const half* U [[buffer(0)]],        // shape: (rows, rank)
    device const half* S [[buffer(1)]],        // shape: (rank)
    device const half* mod_y [[buffer(2)]],    // shape: (rows)
    device const float* in_h [[buffer(3)]],    // shape: (rank)
    device atomic_float* out_y [[buffer(4)]],  // shape: (rows) -> atomic add
    constant uint& rows [[buffer(5)]],
    constant uint& rank [[buffer(6)]],
    uint i [[thread_position_in_grid]]         // 0...rows-1
) {
    if (i >= rows) return;
    
    float sum = 0.0;
    // U is stored row-major: U[i, k] is at U[i * rank + k]
    for (uint k = 0; k < rank; k++) {
        float u_val = (float)U[i * rank + k];
        float s_val = (float)S[k];
        float h_val = in_h[k];
        sum += u_val * s_val * h_val;
    }
    
    float mod_val = (float)mod_y[i];
    float final_val = sum * mod_val;
    
    atomic_fetch_add_explicit(&out_y[i], final_val, memory_order_relaxed);
}
