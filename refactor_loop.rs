use std::fs;
fn main() {
    let mut content = fs::read_to_string("jcross_engine_glm/src/lib.rs").unwrap();
    
    // Replace the signature
    content = content.replace(
        "pub fn execute_generation_loop(&self, start_token: u32, max_tokens: usize) -> Result<Vec<u32>, String> {",
        "pub fn execute_generation_loop(&self, prompt: &[u32], max_tokens: usize) -> Result<Vec<u32>, String> {"
    );
    
    // Replace the initialization inside
    let init_old = r#"        let mut generated = Vec::new();
        generated.push(start_token);
        
        let mut current_token = start_token;
        
        let num_layers = 24;"#;
    let init_new = r#"        let mut generated = Vec::new();
        let mut current_token = prompt[0];
        let mut pos = 0;
        let num_layers = 80;
        let rope_theta = 10000.0;
        
        // Prefill
        for (i, &token) in prompt.iter().enumerate() {
            if i > 0 {
                let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight").unwrap();
                let c = match embed_meta.tensor_type { TensorType::Dense2D { cols, .. } => cols as usize, _ => 0 };
                let row_offset = (current_token as usize) * c * 2;
                let raw_data = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + (c * 2)];
                let mut emb = Vec::with_capacity(c);
                let mut offset = 0;
                for _ in 0..c {
                    let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                    emb.push(half::f16::from_le_bytes(bytes).to_f32());
                    offset += 2;
                }
                let mut x = ndarray::Array1::from_vec(emb);
                for layer in 0..num_layers {
                    x = self.forward_transformer_layer(layer, x, pos, rope_theta).unwrap();
                }
                current_token = token;
                pos += 1;
            }
        }
"#;
    content = content.replace(init_old, init_new);
    fs::write("jcross_engine_glm/src/lib.rs", content).unwrap();
}
