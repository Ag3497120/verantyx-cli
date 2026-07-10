import sys

def patch_file():
    with open("jcross_engine_glm/src/generation.rs", "r") as f:
        content = f.read()
    
    # Fix cache initialization dimension
    content = content.replace("k_pe_cache.push(Array2::zeros((0, num_kv_heads * c_pe)));", "k_pe_cache.push(Array2::zeros((0, c_pe)));")
    
    # Fix sdpa_mla indexing for k_pe_head
    content = content.replace("let k_pe_head = &k_pe_pos.as_slice().unwrap()[kv_group * c_pe .. (kv_group + 1) * c_pe];", "let k_pe_head = &k_pe_pos.as_slice().unwrap()[0 .. c_pe];")
    
    # Remove the debug code from patch 5 if it's there
    debug_code = """
        if kv_latent.len() != c_k {
            println!("Shape error: kv_latent len {} != c_k {}", kv_latent.len(), c_k);
        }
        if k_pe.len() != c_pe_dim {
            println!("Shape error: k_pe len {} != c_pe_dim {}", k_pe.len(), c_pe_dim);
        }
        let latent_2d = kv_latent.clone().into_shape((1, c_k)).unwrap();
        let k_pe_2d = k_pe.clone().into_shape((1, c_pe_dim)).unwrap();
"""
    new_code = """
        let latent_2d = kv_latent.clone().into_shape((1, c_k)).unwrap();
        let k_pe_2d = k_pe.clone().into_shape((1, c_pe_dim)).unwrap();
"""
    content = content.replace(debug_code, new_code)
    
    with open("jcross_engine_glm/src/generation.rs", "w") as f:
        f.write(content)

if __name__ == "__main__":
    patch_file()
