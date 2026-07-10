import re

with open("jcross_engine_glm/src/lib.rs", "r") as f:
    content = f.read()

target = """            if let (Ok(mut gate), Ok(up)) = (project_any(&shared_gate_names, &x_post_norm), project_any(&shared_up_names, &x_post_norm)) {
                for j in 0..gate.len() {
                    let g = gate[j];
                    // SiLU
                    gate[j] = g * (1.0 / (1.0 + (-g).exp())) * up[j];
                }
                if let Ok(down) = project_any(&shared_down_names, &gate) {
                    for j in 0..moe_out.len() {
                        moe_out[j] += down[j];
                    }
                }
            }"""

replacement = """            if let (Ok(mut gate), Ok(up)) = (project_any(&shared_gate_names, &x_post_norm), project_any(&shared_up_names, &x_post_norm)) {
                if layer == 3 {
                    println!("[Layer 3] Shared expert gate[0]={:?}, up[0]={:?}", gate[0], up[0]);
                }
                for j in 0..gate.len() {
                    let g = gate[j];
                    // SiLU
                    gate[j] = g * (1.0 / (1.0 + (-g).exp())) * up[j];
                }
                if let Ok(down) = project_any(&shared_down_names, &gate) {
                    if layer == 3 {
                        println!("[Layer 3] Shared expert down[0]={:?}", down[0]);
                    }
                    for j in 0..moe_out.len() {
                        moe_out[j] += down[j];
                    }
                } else if layer == 3 {
                    println!("[Layer 3] Shared expert down_proj FAILED!");
                }
            } else if layer == 3 {
                println!("[Layer 3] Shared expert gate/up project FAILED!");
            }"""

if target in content:
    content = content.replace(target, replacement)
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
