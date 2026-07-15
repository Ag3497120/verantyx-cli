import re

with open("jcross_engine_glm/src/lib.rs", "r") as f:
    content = f.read()

target = """            if let (Ok(mut gate), Ok(up)) = (self.project_matrix(&shared_gate_names[0], &x_post_norm), self.project_matrix(&shared_up_names[0], &x_post_norm)) {
                for i in 0..b {
                    for j in 0..gate.shape()[1] {
                        let g = gate[[i, j]];
                        // SiLU
                        gate[[i, j]] = g * (1.0 / (1.0 + (-g).exp())) * up[[i, j]];
                    }
                }
                if let Ok(down) = self.project_matrix(&shared_down_names[0], &gate) {
                    for i in 0..b {
                        for j in 0..moe_out.shape()[1] {
                            moe_out[[i, j]] += down[[i, j]];
                        }
                    }
                }
            }"""

replacement = """            if let (Ok(mut gate), Ok(up)) = (self.project_matrix(&shared_gate_names[0], &x_post_norm), self.project_matrix(&shared_up_names[0], &x_post_norm)) {
                if layer == 3 {
                    println!("[Chunked Layer 3] Shared expert gate[0,0]={:?}, up[0,0]={:?}", gate[[0,0]], up[[0,0]]);
                }
                for i in 0..b {
                    for j in 0..gate.shape()[1] {
                        let g = gate[[i, j]];
                        // SiLU
                        gate[[i, j]] = g * (1.0 / (1.0 + (-g).exp())) * up[[i, j]];
                    }
                }
                if let Ok(down) = self.project_matrix(&shared_down_names[0], &gate) {
                    if layer == 3 {
                        println!("[Chunked Layer 3] Shared expert down[0,0]={:?}", down[[0,0]]);
                    }
                    for i in 0..b {
                        for j in 0..moe_out.shape()[1] {
                            moe_out[[i, j]] += down[[i, j]];
                        }
                    }
                } else if layer == 3 {
                    println!("[Chunked Layer 3] Shared expert down_proj FAILED!");
                }
            } else if layer == 3 {
                println!("[Chunked Layer 3] Shared expert gate/up project FAILED!");
            }"""

if target in content:
    content = content.replace(target, replacement)
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)
    print("Patched chunked successfully")
else:
    print("Target chunked not found")
