with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

# Fix 1: RoPE is applied to the FIRST 64 elements of q_vec for each head!
# So q_idx should be `head * q_head_dim + i` instead of `head * q_head_dim + q_c_dim + i`
content = content.replace("let q_idx = head * q_head_dim + q_c_dim + i;", "let q_idx = head * q_head_dim + i;")
content = content.replace("let q_idx2 = head * q_head_dim + q_c_dim + i + (q_pe_dim / 2);", "let q_idx2 = head * q_head_dim + i + (q_pe_dim / 2);")
content = content.replace("let q_idx = head * q_head_dim + q_c_dim + 2 * i;", "let q_idx = head * q_head_dim + 2 * i;")
content = content.replace("let q_idx2 = head * q_head_dim + q_c_dim + 2 * i + 1;", "let q_idx2 = head * q_head_dim + 2 * i + 1;")

# Fix 2: Attention scoring must extract q_pe from the FIRST 64 elements, and q_c from the LAST 192 elements!
old_extract = """                let q_c_head = &q_vec[h * q_head_dim .. h * q_head_dim + k_c_dim]; 
                let q_pe_head = &q_vec[h * q_head_dim + k_c_dim .. (h + 1) * q_head_dim];"""
new_extract = """                let q_pe_head = &q_vec[h * q_head_dim .. h * q_head_dim + q_pe_dim]; 
                let q_c_head = &q_vec[h * q_head_dim + q_pe_dim .. (h + 1) * q_head_dim];"""
if old_extract in content:
    content = content.replace(old_extract, new_extract)
else:
    print("Could not find old extract!")

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
print("Fixed q_pe order in gpu_ops.rs")
