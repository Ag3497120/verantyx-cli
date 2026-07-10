import Metal

guard let device = MTLCreateSystemDefaultDevice() else { exit(1) }
let source = """
kernel void kernel_rmsnorm(
    device float* in_vec [[buffer(0)]],
    device half* weight [[buffer(1)]],
    device float* out_vec [[buffer(2)]],
    constant uint& size [[buffer(3)]],
    uint tid [[thread_position_in_threadgroup]],
    uint threads_per_tg [[threads_per_threadgroup]]
) {
    threadgroup float tg_sum[1024];
    float local_sum = 0.0;
    for (uint i = tid; i < size; i += threads_per_tg) {
        local_sum += in_vec[i] * in_vec[i];
    }
    tg_sum[tid] = local_sum;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = threads_per_tg / 2; stride > 0; stride >>= 1) {
        if (tid < stride) tg_sum[tid] += tg_sum[tid + stride];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    float norm = 1.0 / sqrt((tg_sum[0] / (float)size) + 1e-6);
    for (uint i = tid; i < size; i += threads_per_tg) {
        out_vec[i] = (in_vec[i] * norm) * (float)weight[i];
    }
}
"""
let library = try! device.makeLibrary(source: source, options: nil)
let function = library.makeFunction(name: "kernel_rmsnorm")!
let pso = try! device.makeComputePipelineState(function: function)
print("maxTotalThreadsPerThreadgroup: \(pso.maxTotalThreadsPerThreadgroup)")
