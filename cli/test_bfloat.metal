#include <metal_stdlib>
using namespace metal;

kernel void test_bf(device const bfloat* in, device float* out) {
    out[0] = (float)in[0];
}
