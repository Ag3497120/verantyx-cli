import re

with open("jcross_engine_glm/src/lib.rs", "r") as f:
    content = f.read()

target = """        if layer == 3 {
            println!("[Layer 3] x_post_norm[0]={:?}, rms2={:?}, post_norm_w[0]={:?}", x_post_norm[0], rms2, post_norm_w[0]);
        }"""

replacement = """        if layer == 3 || layer == 0 || layer == 78 {
            println!("[Layer {}] x_post_norm[0]={:?}", layer, x_post_norm[0]);
        }"""

if target in content:
    content = content.replace(target, replacement)
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
