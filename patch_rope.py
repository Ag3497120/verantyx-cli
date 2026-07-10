import re

with open("jcross_engine_glm/src/generation.rs", "r") as f:
    content = f.read()

target = """pub fn apply_rope(q: &mut Array2<f32>, k: &mut Array2<f32>, seq_len: usize, b: usize, rope_theta: f32) {
    let dim = q.shape()[1];
    for i in 0..b {
        let pos = seq_len + i;
        for j in (0..dim).step_by(2) {
            let inv_freq = 1.0 / rope_theta.powf(j as f32 / dim as f32);
            let angle = pos as f32 * inv_freq;
            let (sin, cos) = angle.sin_cos();
            
            let q_0 = q[[i, j]];
            let q_1 = q[[i, j+1]];
            q[[i, j]] = q_0 * cos - q_1 * sin;
            q[[i, j+1]] = q_1 * cos + q_0 * sin;
            
            let k_0 = k[[i, j]];
            let k_1 = k[[i, j+1]];
            k[[i, j]] = k_0 * cos - k_1 * sin;
            k[[i, j+1]] = k_1 * cos + k_0 * sin;
        }
    }
}"""

replacement = """pub fn apply_rope(q: &mut Array2<f32>, k: &mut Array2<f32>, seq_len: usize, b: usize, rope_theta: f32) {
    let dim = q.shape()[1];
    let half_dim = dim / 2;
    for i in 0..b {
        let pos = seq_len + i;
        for j in 0..half_dim {
            // In half-rotated RoPE, the frequencies usually use j*2.
            let inv_freq = 1.0 / rope_theta.powf((j * 2) as f32 / dim as f32);
            let angle = pos as f32 * inv_freq;
            let (sin, cos) = angle.sin_cos();
            
            let q_0 = q[[i, j]];
            let q_1 = q[[i, j + half_dim]];
            q[[i, j]] = q_0 * cos - q_1 * sin;
            q[[i, j + half_dim]] = q_1 * cos + q_0 * sin;
            
            let k_0 = k[[i, j]];
            let k_1 = k[[i, j + half_dim]];
            k[[i, j]] = k_0 * cos - k_1 * sin;
            k[[i, j + half_dim]] = k_1 * cos + k_0 * sin;
        }
    }
}"""

if target in content:
    content = content.replace(target, replacement)
    with open("jcross_engine_glm/src/generation.rs", "w") as f:
        f.write(content)
    print("Patched RoPE successfully")
else:
    print("RoPE Target not found")
