use std::fs;

fn main() {
    let mut content = fs::read_to_string("jcross_engine_glm/src/lib.rs").unwrap();
    
    // 1. Insert get_candle_tensor
    let get_candle_tensor = r#"
    pub fn get_candle_tensor(&self, name: &str, device: &Device) -> Result<Tensor, String> {
        if let Some(meta) = self.tensors.get(name) {
            let start = meta.offset;
            let end = start + meta.byte_length;
            let raw_data = &self.mmap[start..end];
            let f16_slice = unsafe {
                std::slice::from_raw_parts(raw_data.as_ptr() as *const half::f16, meta.byte_length / 2)
            };
            match meta.tensor_type {
                TensorType::Dense2D { rows, cols } => {
                    return Tensor::from_slice(f16_slice, (rows as usize, cols as usize), device).map_err(|e| e.to_string());
                },
                TensorType::Dense1D { length } => {
                    return Tensor::from_slice(f16_slice, (length as usize,), device).map_err(|e| e.to_string());
                },
                _ => return Err(format!("Cannot load base tensor for SVD directly without suffix: {}", name)),
            }
        }
        
        if name.ends_with(".V") || name.ends_with(".S") || name.ends_with(".U") || name.ends_with(".mod_x") || name.ends_with(".mod_y") || name.ends_with(".c_valve") {
            let parts: Vec<&str> = name.rsplitn(2, '.').collect();
            if parts.len() == 2 {
                let base_name = parts[1];
                let suffix = parts[0];
                if let Some(meta) = self.tensors.get(base_name) {
                    if let TensorType::SVDLossless { rows, cols, rank } = meta.tensor_type {
                        let r = rank as usize;
                        let m = rows as usize;
                        let n = cols as usize;
                        
                        let start = meta.offset;
                        let raw_data = &self.mmap[start..start + meta.byte_length];
                        let f16_slice = unsafe {
                            std::slice::from_raw_parts(raw_data.as_ptr() as *const half::f16, meta.byte_length / 2)
                        };
                        
                        let v_len = r * n;
                        let s_len = r;
                        let u_len = m * r;
                        let mod_x_len = n;
                        let mod_y_len = m;
                        let c_valve_len = r * r;
                        
                        return match suffix {
                            "V" => Tensor::from_slice(&f16_slice[0..v_len], (r, n), device).map_err(|e| e.to_string()),
                            "S" => Tensor::from_slice(&f16_slice[v_len..v_len+s_len], (r,), device).map_err(|e| e.to_string()),
                            "U" => Tensor::from_slice(&f16_slice[v_len+s_len..v_len+s_len+u_len], (m, r), device).map_err(|e| e.to_string()),
                            "mod_x" => Tensor::from_slice(&f16_slice[v_len+s_len+u_len..v_len+s_len+u_len+mod_x_len], (n,), device).map_err(|e| e.to_string()),
                            "mod_y" => Tensor::from_slice(&f16_slice[v_len+s_len+u_len+mod_x_len..v_len+s_len+u_len+mod_x_len+mod_y_len], (m,), device).map_err(|e| e.to_string()),
                            "c_valve" => Tensor::from_slice(&f16_slice[v_len+s_len+u_len+mod_x_len+mod_y_len..v_len+s_len+u_len+mod_x_len+mod_y_len+c_valve_len], (r, r), device).map_err(|e| e.to_string()),
                            _ => Err(format!("Unknown suffix: {}", suffix)),
                        };
                    }
                }
            }
        }
        
        Err(format!("Tensor missing (Streaming VRAM): {}", name))
    }
"#;
    content = content.replace("impl JCrossEngine {", &format!("impl JCrossEngine {{\n{}", get_candle_tensor));
    
    // 2. Remove candle_tensors eager loading
    // Just find the loop `for (name, meta) in &tensors {` up to `println!("[JCross] All FP16 weights transferred to GPU.");`
    let start_idx = content.find("        for (name, meta) in &tensors {").unwrap();
    let end_idx = content.find("        println!(\"[JCross] All FP16 weights transferred to GPU.\");").unwrap() + 66;
    content.replace_range(start_idx..end_idx, "        // Streaming architecture: no eager loading to VRAM.");
    
    // 3. Replace candle_tensors usages
    content = content.replace(
        r#"        let w_t = self.candle_tensors.get(layer_name)
            .or_else(|| self.candle_tensors.get(&format!("{}.weight", layer_name)))
            .or_else(|| self.candle_tensors.get("output_layer.weight"))
            .or_else(|| self.candle_tensors.get("transformer.output_layer.weight"))
            .ok_or_else(|| format!("Tensor missing (VRAM): {}", layer_name))?;"#,
        r#"        let w_t = self.get_candle_tensor(layer_name, &self.candle_device)
            .or_else(|_| self.get_candle_tensor(&format!("{}.weight", layer_name), &self.candle_device))
            .or_else(|_| self.get_candle_tensor("output_layer.weight", &self.candle_device))
            .or_else(|_| self.get_candle_tensor("transformer.output_layer.weight", &self.candle_device))
            .map_err(|e| e.to_string())?;"#
    );
    
    content = content.replace("self.candle_tensors.get(layer_name).ok_or_else(|| format!(\"Tensor missing (VRAM): {}\", layer_name))?;", 
                              "self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;");
    content = content.replace("self.candle_tensors.get(layer_name).ok_or(\"Tensor missing\")?;",
                              "self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;");
    
    // .unwrap() usages for sub-tensors
    for suffix in ["V", "S", "U"] {
        let old = format!("self.candle_tensors.get(&format!(\"{{}}.{}\", layer_name)).unwrap();", suffix);
        let new = format!("self.get_candle_tensor(&format!(\"{{}}.{}\", layer_name), &self.candle_device).unwrap();", suffix);
        content = content.replace(&old, &new);
    }
    
    fs::write("jcross_engine_glm/src/lib.rs", content).unwrap();
    println!("Done");
}
