import sys

def patch_file():
    with open("jcross_engine_glm/src/generation.rs", "r") as f:
        content = f.read()
    
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
    content = content.replace("""        let latent_2d = kv_latent.clone().into_shape((1, c_k)).unwrap();
        let k_pe_2d = k_pe.clone().into_shape((1, c_pe_dim)).unwrap();""", debug_code)
    
    with open("jcross_engine_glm/src/generation.rs", "w") as f:
        f.write(content)

if __name__ == "__main__":
    patch_file()
