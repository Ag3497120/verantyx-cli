import re

with open('/Users/motonishikoudai/verantyx-cli/jcross_engine_glm/src/gpu_ops.rs', 'r') as f:
    content = f.read()

# Replace the entire MLP section
mlp_start = content.find('        // 8. MLP (SwiGLU) - MoE or Dense')
mlp_end = content.find('        // 9. Output assignment')

new_mlp = """        // 8. MLP (SwiGLU) - MoE or Dense
        let is_moe = layer >= 3;
        let mut mlp_out = x_post_attn.clone();

        if is_moe {
            let router_names = [format!("model.layers.{}.mlp.gate.weight", layer)];
            let router_names_str: Vec<&str> = router_names.iter().map(|s| s.as_str()).collect();
            
            if let Ok(router_w) = project_any(&router_names_str, &pa_norm) {
                let mut router_logits = router_w.to_dtype(DType::F32).map_err(|e| e.to_string())?.flatten_all().map_err(|e| e.to_string())?.to_vec1::<f32>().map_err(|e| e.to_string())?;
                
                let bias_names = [format!("model.layers.{}.mlp.gate.e_score_correction_bias", layer)];
                let bias_names_str: Vec<&str> = bias_names.iter().map(|s| s.as_str()).collect();
                if let Ok(bias) = project_any(&bias_names_str, &pa_norm) {
                    let bias_vec = bias.to_dtype(DType::F32).map_err(|e| e.to_string())?.flatten_all().map_err(|e| e.to_string())?.to_vec1::<f32>().map_err(|e| e.to_string())?;
                    for i in 0..router_logits.len() {
                        router_logits[i] += bias_vec[i];
                    }
                }
                
                let k = 8;
                let mut experts_with_scores: Vec<(usize, f32)> = router_logits.iter().enumerate().map(|(i, &s)| (i, s)).collect();
                experts_with_scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
                let top_k_experts: Vec<_> = experts_with_scores.into_iter().take(k).collect();
                
                let mut top_k_probs = vec![0.0; k];
                let mut sum_probs = 0.0;
                for i in 0..k {
                    let s = 1.0 / (1.0 + (-top_k_experts[i].1).exp()); 
                    top_k_probs[i] = s;
                    sum_probs += s;
                }
                for i in 0..k {
                    top_k_probs[i] /= sum_probs;
                }
                
                let mut moe_acc: Option<Tensor> = None;
                
                for (i, &(expert_idx, _)) in top_k_experts.iter().enumerate() {
                    let gate_names = [format!("model.layers.{}.mlp.experts.{}.gate_proj.weight", layer, expert_idx)];
                    let up_names = [format!("model.layers.{}.mlp.experts.{}.up_proj.weight", layer, expert_idx)];
                    let down_names = [format!("model.layers.{}.mlp.experts.{}.down_proj.weight", layer, expert_idx)];
                    let gate_names_str: Vec<&str> = gate_names.iter().map(|s| s.as_str()).collect();
                    let up_names_str: Vec<&str> = up_names.iter().map(|s| s.as_str()).collect();
                    let down_names_str: Vec<&str> = down_names.iter().map(|s| s.as_str()).collect();
                    
                    if let (Ok(gate), Ok(up)) = (project_any(&gate_names_str, &pa_norm), project_any(&up_names_str, &pa_norm)) {
                        let mut gate_vec = gate.to_vec1::<f32>().map_err(|e| e.to_string())?;
                        let up_vec = up.to_vec1::<f32>().map_err(|e| e.to_string())?;
                        for j in 0..gate_vec.len() {
                            gate_vec[j] = crate::generation::swiglu(gate_vec[j]) * up_vec[j];
                        }
                        let gate_tensor = Tensor::from_vec(gate_vec, (gate.dims()[0],), &self.candle_device).map_err(|e| e.to_string())?;
                        
                        if let Ok(down) = project_any(&down_names_str, &gate_tensor) {
                            let weighted = (down * (top_k_probs[i] as f64)).map_err(|e| e.to_string())?;
                            if let Some(acc) = moe_acc {
                                moe_acc = Some((acc + weighted).map_err(|e| e.to_string())?);
                            } else {
                                moe_acc = Some(weighted);
                            }
                        }
                    }
                }
                
                let shared_gate_names = [format!("model.layers.{}.mlp.shared_experts.gate_proj.weight", layer)];
                let shared_up_names = [format!("model.layers.{}.mlp.shared_experts.up_proj.weight", layer)];
                let shared_down_names = [format!("model.layers.{}.mlp.shared_experts.down_proj.weight", layer)];
                let shared_gate_names_str: Vec<&str> = shared_gate_names.iter().map(|s| s.as_str()).collect();
                let shared_up_names_str: Vec<&str> = shared_up_names.iter().map(|s| s.as_str()).collect();
                let shared_down_names_str: Vec<&str> = shared_down_names.iter().map(|s| s.as_str()).collect();

                if let (Ok(gate), Ok(up)) = (project_any(&shared_gate_names_str, &pa_norm), project_any(&shared_up_names_str, &pa_norm)) {
                    let mut gate_vec = gate.to_vec1::<f32>().map_err(|e| e.to_string())?;
                    let up_vec = up.to_vec1::<f32>().map_err(|e| e.to_string())?;
                    for j in 0..gate_vec.len() {
                        gate_vec[j] = crate::generation::swiglu(gate_vec[j]) * up_vec[j];
                    }
                    let gate_tensor = Tensor::from_vec(gate_vec, (gate.dims()[0],), &self.candle_device).map_err(|e| e.to_string())?;
                    
                    if let Ok(down) = project_any(&shared_down_names_str, &gate_tensor) {
                        if let Some(acc) = moe_acc {
                            moe_acc = Some((acc + down).map_err(|e| e.to_string())?);
                        } else {
                            moe_acc = Some(down);
                        }
                    }
                }

                if let Some(acc) = moe_acc {
                    mlp_out = (x_post_attn + acc).map_err(|e| e.to_string())?;
                }
            }
        } else {
            // Dense
            let gate_names = [format!("model.layers.{}.mlp.gate_proj.weight", layer)];
            let up_names = [format!("model.layers.{}.mlp.up_proj.weight", layer)];
            let down_names = [format!("model.layers.{}.mlp.down_proj.weight", layer)];
            let gate_names_str: Vec<&str> = gate_names.iter().map(|s| s.as_str()).collect();
            let up_names_str: Vec<&str> = up_names.iter().map(|s| s.as_str()).collect();
            let down_names_str: Vec<&str> = down_names.iter().map(|s| s.as_str()).collect();
            
            if let (Ok(gate), Ok(up)) = (project_any(&gate_names_str, &pa_norm), project_any(&up_names_str, &pa_norm)) {
                let mut gate_vec = gate.to_vec1::<f32>().map_err(|e| e.to_string())?;
                let up_vec = up.to_vec1::<f32>().map_err(|e| e.to_string())?;
                for i in 0..gate_vec.len() {
                    gate_vec[i] = crate::generation::swiglu(gate_vec[i]) * up_vec[i];
                }
                let gate_tensor = Tensor::from_vec(gate_vec, (gate.dims()[0],), &self.candle_device).map_err(|e| e.to_string())?;
                if let Ok(down) = project_any(&down_names_str, &gate_tensor) {
                    mlp_out = (x_post_attn + down).map_err(|e| e.to_string())?;
                }
            }
        }

"""

new_content = content[:mlp_start] + new_mlp + content[mlp_end:]
with open('/Users/motonishikoudai/verantyx-cli/jcross_engine_glm/src/gpu_ops.rs', 'w') as f:
    f.write(new_content)
print("GPU MoE logic patched successfully.")
