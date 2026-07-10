with open("jcross_engine_glm/src/gpu_ops.rs", "r") as f:
    content = f.read()

patch = """    pub fn forward_layer_gpu(&mut self, layer: usize, x: Tensor, pos: usize, rope_theta: f32) -> Result<Tensor, String> {
        let x_vec_in = x.to_vec1::<f32>().unwrap();
        let mut min_in = f32::INFINITY;
        let mut max_in = f32::NEG_INFINITY;
        let mut has_nan_in = false;
        for v in x_vec_in {
            if v.is_nan() { has_nan_in = true; }
            if v < min_in { min_in = v; }
            if v > max_in { max_in = v; }
        }
        if layer == 0 {
            println!("Layer {} IN stats: min={}, max={}, has_nan={}", layer, min_in, max_in, has_nan_in);
        }

        let num_heads = 64;"""

import re
content = re.sub(r'    pub fn forward_layer_gpu\(&mut self, layer: usize, x: Tensor, pos: usize, rope_theta: f32\) -> Result<Tensor, String> \{\n        let num_heads = 64;', patch, content)

with open("jcross_engine_glm/src/gpu_ops.rs", "w") as f:
    f.write(content)
