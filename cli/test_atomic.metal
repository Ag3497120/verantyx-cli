#include <metal_stdlib>
using namespace metal;

kernel void test_atomic(device atomic_float* out [[buffer(0)]]) {
    atomic_fetch_add_explicit(out, 1.0, memory_order_relaxed);
}
