with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

import re
patch = """        if layer == 0 || layer == 77 || layer == 3 {
            let x_vec = mlp_out.to_vec1::<f32>().unwrap();
            let mut min = f32::INFINITY;
            let mut max = f32::NEG_INFINITY;
            let mut has_nan = false;
            for v in x_vec {
                if v.is_nan() { has_nan = true; }
                if v < min { min = v; }
                if v > max { max = v; }
            }
            println!("Layer {} mlp_out stats: min={}, max={}, has_nan={}", layer, min, max, has_nan);
        }
        Ok(mlp_out)"""

content = re.sub(r'        if layer == 0 \|\| layer == 77 \|\| layer == 3 \{.*?        Ok\(mlp_out\)', patch, content, flags=re.DOTALL)

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
