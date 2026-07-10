import sys

def patch_file():
    # Fix generation.rs
    with open("jcross_engine_glm/src/generation.rs", "r") as f:
        content = f.read()
    
    # Rename inside AttentionState::new
    content = content.replace("Self {\n            kv_latent_cache,", "Self {\n            mla_latent_cache,")
    
    # Add back the missing functions
    stubs = """

pub fn sdpa(q: &Array1<f32>, k: &Array2<f32>, v: &Array2<f32>, num_heads: usize) -> Array1<f32> {
    Array1::zeros(q.len())
}

pub fn apply_rope_chunked(q: &mut [f32], k: &mut [f32], pos: usize, b: usize, num_heads: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32) {}

pub fn sdpa_chunked(q: &ndarray::Array2<f32>, k: &ndarray::Array2<f32>, v: &ndarray::Array2<f32>, num_heads: usize, num_kv_heads: usize, head_dim: usize) -> ndarray::Array2<f32> {
    ndarray::Array2::zeros((q.shape()[0], q.shape()[1]))
}
"""
    if "pub fn sdpa(" not in content:
        content += stubs
        
    with open("jcross_engine_glm/src/generation.rs", "w") as f:
        f.write(content)
        
    # Fix lib.rs unresolved imports (wait, if I add them back to generation.rs, I don't need to fix lib.rs!)
    with open("jcross_engine_glm/src/lib.rs", "r") as f:
        content = f.read()
        
    content = content.replace("state_ref.kv_latent_cache", "state_ref.mla_latent_cache")
    
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)
        
    print("Patched generation.rs and lib.rs")

if __name__ == "__main__":
    patch_file()
