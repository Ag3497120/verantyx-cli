import sys

def patch_file():
    with open("jcross_engine_glm/src/generation.rs", "r") as f:
        content = f.read()
    
    # Just replace all kv_latent_cache with mla_latent_cache
    content = content.replace("kv_latent_cache", "mla_latent_cache")
    
    with open("jcross_engine_glm/src/generation.rs", "w") as f:
        f.write(content)
        
    with open("jcross_engine_glm/src/lib.rs", "r") as f:
        content = f.read()
        
    content = content.replace("kv_latent_cache", "mla_latent_cache")
    
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)
        
    print("Patched completely!")

if __name__ == "__main__":
    patch_file()
