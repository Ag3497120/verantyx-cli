import re

with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

old_rope = """        // 4. RoPE
        let mut q_vec = q_full.to_vec1::<f32>().map_err(|e| e.to_string())?;
        for i in 0..(q_pe_dim / 2) {
            let freq = 1.0 / rope_theta.powf(2.0 * (i as f32) / (q_pe_dim as f32));
            let val = (pos as f32) * freq;
            let cos_val = val.cos();
            let sin_val = val.sin();

            let k_idx = i;
            let k_idx2 = i + (q_pe_dim / 2);
            let k0 = k_pe_vec[k_idx];
            let k1 = k_pe_vec[k_idx2];
            k_pe_vec[k_idx] = k0 * cos_val - k1 * sin_val;
            k_pe_vec[k_idx2] = k0 * sin_val + k1 * cos_val;

            for head in 0..num_heads {
                let q_idx = head * q_head_dim + q_c_dim + i;
                let q_idx2 = head * q_head_dim + q_c_dim + i + (q_pe_dim / 2);
                let q0 = q_vec[q_idx];
                let q1 = q_vec[q_idx2];
                q_vec[q_idx] = q0 * cos_val - q1 * sin_val;
                q_vec[q_idx2] = q0 * sin_val + q1 * cos_val;
            }
        }"""

new_rope = """        // 4. RoPE
        let mut q_vec = q_full.to_vec1::<f32>().map_err(|e| e.to_string())?;
        for i in 0..(q_pe_dim / 2) {
            let freq = 1.0 / rope_theta.powf(2.0 * (i as f32) / (q_pe_dim as f32));
            let val = (pos as f32) * freq;
            let cos_val = val.cos();
            let sin_val = val.sin();

            // Interleaved style
            let k_idx = 2 * i;
            let k_idx2 = 2 * i + 1;
            let k0 = k_pe_vec[k_idx];
            let k1 = k_pe_vec[k_idx2];
            k_pe_vec[k_idx] = k0 * cos_val - k1 * sin_val;
            k_pe_vec[k_idx2] = k0 * sin_val + k1 * cos_val;

            for head in 0..num_heads {
                let q_idx = head * q_head_dim + q_c_dim + 2 * i;
                let q_idx2 = head * q_head_dim + q_c_dim + 2 * i + 1;
                let q0 = q_vec[q_idx];
                let q1 = q_vec[q_idx2];
                q_vec[q_idx] = q0 * cos_val - q1 * sin_val;
                q_vec[q_idx2] = q0 * sin_val + q1 * cos_val;
            }
        }"""

if old_rope in content:
    content = content.replace(old_rope, new_rope)
    with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
        f.write(content)
    print("Replaced RoPE!")
else:
    print("Could not find old RoPE code!")

