import re

with open("jcross_engine_glm/src/lib.rs", "r") as f:
    content = f.read()

target = """        let mut x_post_norm = x.clone();
        for (i, val) in x_post_norm.iter_mut().enumerate() { *val = (*val / rms) * norm_w[i]; }"""

replacement = """        let mut x_post_norm = x.clone();
        for (i, val) in x_post_norm.iter_mut().enumerate() { *val = (*val / rms) * norm_w[i]; }
        if layer == 3 {
            println!("[Layer 3] x_post_norm[0]={:?}, rms={:?}, norm_w[0]={:?}", x_post_norm[0], rms, norm_w[0]);
        }"""

if target in content:
    content = content.replace(target, replacement)
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
