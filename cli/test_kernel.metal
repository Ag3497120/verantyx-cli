#include <metal_stdlib>
using namespace metal;
kernel void test_kernel(device const uint8_t* in [[buffer(0)]], device uint8_t* out [[buffer(1)]], uint tid [[thread_position_in_grid]]) {
    out[tid] = in[tid];
}
