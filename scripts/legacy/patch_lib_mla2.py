import sys

def patch_file():
    # Fix generation.rs
    with open("jcross_engine_glm/src/generation.rs", "r") as f:
        content = f.read()
    
    content = content.replace("pub kv_latent_cache: Vec<Array2<f32>>", "pub mla_latent_cache: Vec<Array2<f32>>")
    content = content.replace("kv_latent_cache:", "mla_latent_cache:")
    content = content.replace("self.kv_latent_cache", "self.mla_latent_cache")
    
    with open("jcross_engine_glm/src/generation.rs", "w") as f:
        f.write(content)
        
    # Fix lib.rs
    with open("jcross_engine_glm/src/lib.rs", "r") as f:
        content = f.read()
        
    # Fix forward_transformer_layer_chunked append_mla issue
    content = content.replace("cache.append_mla(layer, &k_token);", "cache.append_mla(layer, &k_token, &ndarray::Array1::zeros(64)); // STUB for chunked prefill")
    
    # Fix missing num_layers in the chunked prefill init
    content = content.replace("Some(crate::generation::AttentionState::new(79, k.len(), v.len(), 10000.0))", "Some(crate::generation::AttentionState::new(79, 512, 2, 64, 10000.0))")
    
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)
        
    print("Patched generation.rs and lib.rs")

if __name__ == "__main__":
    patch_file()
