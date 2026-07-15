with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

content = content.replace("let k_idx = 2 * i;", "let k_idx = i;")
content = content.replace("let k_idx2 = 2 * i + 1;", "let k_idx2 = i + (q_pe_dim / 2);")
content = content.replace("let q_idx = head * q_head_dim + q_c_dim + 2 * i;", "let q_idx = head * q_head_dim + q_c_dim + i;")
content = content.replace("let q_idx2 = head * q_head_dim + q_c_dim + 2 * i + 1;", "let q_idx2 = head * q_head_dim + q_c_dim + i + (q_pe_dim / 2);")

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
