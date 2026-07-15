with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

patch = """            for head in 0..num_heads {
                let q_idx = head * q_head_dim + q_c_dim + i;
                let q_idx2 = head * q_head_dim + q_c_dim + i + (q_pe_dim / 2);
                let q0 = q_vec[q_idx];
                let q1 = q_vec[q_idx2];
                q_vec[q_idx] = q0 * cos_val - q1 * sin_val;
                q_vec[q_idx2] = q0 * sin_val + q1 * cos_val;
            }"""

content = content.replace("""            for head in 0..num_heads {
                let q_idx = head * q_head_dim + i;
                let q_idx2 = head * q_head_dim + i + (q_pe_dim / 2);
                let q0 = q_vec[q_idx];
                let q1 = q_vec[q_idx2];
                q_vec[q_idx] = q0 * cos_val - q1 * sin_val;
                q_vec[q_idx2] = q0 * sin_val + q1 * cos_val;
            }""", patch)

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
