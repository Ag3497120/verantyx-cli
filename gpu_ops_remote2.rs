use candle_core::{Device, Tensor, DType};
use candle_nn::ops::softmax;
use crate::{JCrossEngine, TensorType, MetalAttentionState};

impl JCrossEngine {
    pub fn project_vector_gpu(&self, layer_name: &str, x_t: &Tensor) -> Result<Tensor, String> {
        let meta = self.tensors.get(layer_name).ok_or(format!("Layer not found: {}", layer_name))?;
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::BF16).map_err(|e| e.to_string())?;
                // x_t is assumed (cols). We want w_t (rows, cols) * x_t (cols, 1) -> (rows, 1) -> (rows)
                let x_col = if x_t_f16.rank() == 1 { 
                    x_t_f16.reshape((cols as usize, 1)).map_err(|e| e.to_string())? 
                } else { 
                    x_t_f16.t().map_err(|e| e.to_string())? 
                };
                let y_t = w_t.matmul(&x_col).map_err(|e| e.to_string())?;
                let y_t_f32 = y_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                Ok(y_t_f32.flatten_all().map_err(|e| e.to_string())?)
            },
            TensorType::Dense1D { .. } => {
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
                let w_t_f32 = w_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                Ok(w_t_f32)
            },
            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t_f16 = x_t.to_dtype(DType::BF16).map_err(|e| e.to_string())?;
                let x_col = if x_t_f16.rank() == 1 { 
                    x_t_f16.reshape((cols as usize, 1)).map_err(|e| e.to_string())? 
                } else { 
                    x_t_f16.t().map_err(|e| e.to_string())? 
                };
                
                let t_mod_x = self.get_candle_tensor(&format!("{}.mod_x", layer_name), &self.candle_device).map_err(|e| e.to_string())?;
                let t_mod_x_f16 = t_mod_x.reshape((cols as usize, 1)).map_err(|e| e.to_string())?;
                let x_mod = x_col.broadcast_mul(&t_mod_x_f16).map_err(|e| e.to_string())?;

                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).map_err(|e| e.to_string())?;
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).map_err(|e| e.to_string())?;
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).map_err(|e| e.to_string())?;
                let t_c_valve = self.get_candle_tensor(&format!("{}.c_valve", layer_name), &self.candle_device).map_err(|e| e.to_string())?;
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?;
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                let temp_locked = t_c_valve.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let temp3 = t_u.matmul(&temp_locked).map_err(|e| e.to_string())?;
                
                let t_mod_y = self.get_candle_tensor(&format!("{}.mod_y", layer_name), &self.candle_device).map_err(|e| e.to_string())?;
                let t_mod_y_f16 = t_mod_y.reshape((rows as usize, 1)).map_err(|e| e.to_string())?;
                let temp4 = temp3.broadcast_add(&t_mod_y_f16).map_err(|e| e.to_string())?;

                let out_f32 = temp4.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                Ok(out_f32.flatten_all().map_err(|e| e.to_string())?)
            }
        }
    }

    pub fn forward_layer_gpu(
        &self, 
        layer: usize, 
        x: Tensor, 
        pos: usize, 
        rope_theta: f32
    ) -> Result<Tensor, String> {
let x_vec_in = x.to_vec1::<f32>().unwrap();        let mut min_in = f32::INFINITY;        let mut max_in = f32::NEG_INFINITY;        let mut has_nan_in = false;        for v in x_vec_in {            if v.is_nan() { has_nan_in = true; }            if v < min_in { min_in = v; }            if v > max_in { max_in = v; }        }        if layer == 0 {            println!("Layer {} IN stats: min={}, max={}, has_nan={}", layer, min_in, max_in, has_nan_in);        }
        let norm_eps = 1e-6f64;
        
                let project_any = |names: &[&str], input: &Tensor| -> Result<Tensor, String> {
            let mut last_err = String::new();
            for name in names {
                match self.project_vector_gpu(name, input) {
                    Ok(res) => return Ok(res),
                    Err(e) => { last_err = format!("{} error: {}", name, e); }
                }
            }
            Err(format!("None of the layers found: {:?}. Last error: {}", names, last_err))
        };

        // 1. RMSNorm (Input)
        let norm_names = [
            format!("model.language_model.layers.{}.input_layernorm.weight", layer),
            format!("model.layers.{}.input_layernorm.weight", layer)
        ];
        let norm_names_str: Vec<&str> = norm_names.iter().map(|s| s.as_str()).collect();
        let norm_w = project_any(&norm_names_str, &x)?;
        
        let x_f32 = x.to_dtype(DType::F32).map_err(|e| e.to_string())?;
        let x_sq = x_f32.sqr().map_err(|e| e.to_string())?;
        let x_sq_mean = x_sq.mean_keepdim(0).map_err(|e| e.to_string())?;
        let variance = (x_sq_mean + norm_eps).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?;
        
        let x_normalized = x_f32.broadcast_div(&variance).map_err(|e| e.to_string())?;
        let x_norm = x_normalized.broadcast_mul(&norm_w).map_err(|e| e.to_string())?;

        // MLA Hyperparameters for GLM-4 9B
        let num_heads = 64;
        let q_c_dim = 192;
        let q_pe_dim = 64;
        let q_head_dim = q_c_dim + q_pe_dim; // 256
        let v_head_dim = 256;
        let k_c_dim = 192; 

        // 2. Q Projection (Latent)
        let q_a_names = [format!("model.layers.{}.self_attn.q_a_proj.weight", layer)];
        let q_a_names_str: Vec<&str> = q_a_names.iter().map(|s| s.as_str()).collect();
        let q_a = project_any(&q_a_names_str, &x_norm)?; // (2048)

        let q_a_norm_name = format!("model.layers.{}.self_attn.q_a_layernorm.weight", layer);
        let mut q_a_norm_w = Tensor::ones(&[2048], DType::F32, &self.candle_device).unwrap();
        if let Ok(w_f32) = self.get_candle_tensor(&q_a_norm_name, &self.candle_device) {
            q_a_norm_w = w_f32.to_dtype(DType::F32).unwrap();
        }
        
        let q_a_sq = q_a.sqr().map_err(|e| e.to_string())?;
        let q_a_sq_mean = q_a_sq.mean_keepdim(0).map_err(|e| e.to_string())?;
        let q_a_variance = (q_a_sq_mean + norm_eps).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?;
        let q_a_normalized = q_a.broadcast_div(&q_a_variance).map_err(|e| e.to_string())?.broadcast_mul(&q_a_norm_w).map_err(|e| e.to_string())?;

        let q_b_names = [format!("model.layers.{}.self_attn.q_b_proj.weight", layer)];
        let q_b_names_str: Vec<&str> = q_b_names.iter().map(|s| s.as_str()).collect();
        let q_full = project_any(&q_b_names_str, &q_a_normalized)?; // (16384)

        // 3. KV Projection (Latent)
        let kv_a_names = [format!("model.layers.{}.self_attn.kv_a_proj_with_mqa.weight", layer)];
        let kv_a_names_str: Vec<&str> = kv_a_names.iter().map(|s| s.as_str()).collect();
        let kv_a_full = project_any(&kv_a_names_str, &x_norm)?; // (576)

        let kv_latent = kv_a_full.narrow(0, 0, 512).map_err(|e| e.to_string())?;
        let mut k_pe_vec = kv_a_full.narrow(0, 512, 64).map_err(|e| e.to_string())?.to_vec1::<f32>().map_err(|e| e.to_string())?;

        let kv_a_norm_name = format!("model.layers.{}.self_attn.kv_a_layernorm.weight", layer);
        let mut kv_a_norm_w = Tensor::ones(&[512], DType::F32, &self.candle_device).unwrap();
        if let Ok(w_f32) = self.get_candle_tensor(&kv_a_norm_name, &self.candle_device) {
            kv_a_norm_w = w_f32.to_dtype(DType::F32).unwrap();
        }

        let kv_latent_sq = kv_latent.sqr().map_err(|e| e.to_string())?;
        let kv_latent_sq_mean = kv_latent_sq.mean_keepdim(0).map_err(|e| e.to_string())?;
        let kv_latent_variance = (kv_latent_sq_mean + norm_eps).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?;
        let kv_latent_normalized = kv_latent.broadcast_div(&kv_latent_variance).map_err(|e| e.to_string())?.broadcast_mul(&kv_a_norm_w).map_err(|e| e.to_string())?;

        // 4. RoPE
        let mut q_vec = q_full.to_vec1::<f32>().map_err(|e| e.to_string())?;
        for i in 0..(q_pe_dim / 2) {
            let freq = 1.0 / rope_theta.powf(2.0 * (i as f32) / (q_pe_dim as f32));
            let val = (pos as f32) * freq;
            let cos_val = val.cos();
            let sin_val = val.sin();

            let k_idx = i;
            let k_idx2 = i + (q_pe_dim / 2);
            let k0 = k_pe_vec[k_idx];
            let k1 = k_pe_vec[k_idx2];
            k_pe_vec[k_idx] = k0 * cos_val - k1 * sin_val;
            k_pe_vec[k_idx2] = k0 * sin_val + k1 * cos_val;

            for head in 0..num_heads {
                let q_idx = head * q_head_dim + q_c_dim + i;
                let q_idx2 = head * q_head_dim + q_c_dim + i + (q_pe_dim / 2);
                let q0 = q_vec[q_idx];
                let q1 = q_vec[q_idx2];
                q_vec[q_idx] = q0 * cos_val - q1 * sin_val;
                q_vec[q_idx2] = q0 * sin_val + q1 * cos_val;
            }
        }

        let k_pe_cached = Tensor::from_vec(k_pe_vec.clone(), (64,), &self.candle_device).map_err(|e| e.to_string())?;
        
        {
            let mut cache = self.metal_kv_cache.borrow_mut();
            if let Some(state) = cache.as_mut() {
                let k_2d = kv_latent_normalized.reshape((1, 512)).map_err(|e| e.to_string())?;
                let v_2d = k_pe_cached.reshape((1, 64)).map_err(|e| e.to_string())?;
                state.append_kv(layer, k_2d, v_2d).map_err(|e| e.to_string())?;
            }
        }

        // 5. Compute Attention
        let mut attn_out_vec = vec![0.0f32; num_heads * v_head_dim]; // (16384)
        
        {
            let cache = self.metal_kv_cache.borrow();
            let state = cache.as_ref().unwrap();
            let seq_kv_latent_2d = state.k_cache[layer].as_ref().unwrap(); 
            let seq_k_pe_2d = state.v_cache[layer].as_ref().unwrap(); 
            let seq_len = seq_kv_latent_2d.dim(0).map_err(|e| e.to_string())?;

            let kv_b_names = [format!("model.layers.{}.self_attn.kv_b_proj.weight", layer)];
            let kv_b_names_str: Vec<&str> = kv_b_names.iter().map(|s| s.as_str()).collect();
            
            let mut seq_k_c = vec![0.0f32; seq_len * num_heads * k_c_dim];
            let mut seq_v_c = vec![0.0f32; seq_len * num_heads * v_head_dim];
            
            for s in 0..seq_len {
                let latent_1d = seq_kv_latent_2d.narrow(0, s, 1).map_err(|e| e.to_string())?.squeeze(0).map_err(|e| e.to_string())?;
                let kv_c_full = project_any(&kv_b_names_str, &latent_1d)?; 
                let kv_c_vec = kv_c_full.to_vec1::<f32>().map_err(|e| e.to_string())?;
                
                for h in 0..num_heads {
                    let k_start = h * (k_c_dim + v_head_dim);
                    let v_start = k_start + k_c_dim;
                    let k_c_head = &kv_c_vec[k_start .. k_start + k_c_dim];
                    let v_c_head = &kv_c_vec[v_start .. v_start + v_head_dim];
                    seq_k_c[s * (num_heads * k_c_dim) + h * k_c_dim .. s * (num_heads * k_c_dim) + (h + 1) * k_c_dim].copy_from_slice(k_c_head);
                    seq_v_c[s * (num_heads * v_head_dim) + h * v_head_dim .. s * (num_heads * v_head_dim) + (h + 1) * v_head_dim].copy_from_slice(v_c_head);
                }
            }
            
            let seq_k_pe = seq_k_pe_2d.to_vec2::<f32>().map_err(|e| e.to_string())?; 

            for h in 0..num_heads {
                let mut scores = vec![0.0f32; seq_len];
                let q_pe_head = &q_vec[h * q_head_dim .. h * q_head_dim + q_pe_dim]; 
                let q_c_head = &q_vec[h * q_head_dim + q_pe_dim .. (h + 1) * q_head_dim]; 

                for s in 0..seq_len {
                    let k_c_head = &seq_k_c[s * (num_heads * k_c_dim) + h * k_c_dim .. s * (num_heads * k_c_dim) + (h + 1) * k_c_dim];
                    
                    let mut score = 0.0;
                    for d in 0..k_c_dim { score += q_c_head[d] * k_c_head[d]; }
                    for d in 0..q_pe_dim { score += q_pe_head[d] * seq_k_pe[s][d]; }
                    
                    let scale = 1.0 / ((q_head_dim as f32).sqrt());
                    scores[s] = score * scale;
                }

                let mut max_val = f32::NEG_INFINITY;
                for &s_val in &scores { if s_val > max_val { max_val = s_val; } }
                let mut exp_sum = 0.0;
                for s_val in &mut scores {
                    *s_val = (*s_val - max_val).exp();
                    exp_sum += *s_val;
                }
                for s_val in &mut scores { *s_val /= exp_sum; }

                let mut out_head = vec![0.0f32; v_head_dim];
                for s in 0..seq_len {
                    let w = scores[s];
                    let v_head = &seq_v_c[s * (num_heads * v_head_dim) + h * v_head_dim .. s * (num_heads * v_head_dim) + (h + 1) * v_head_dim];
                    for d in 0..v_head_dim {
                        out_head[d] += w * v_head[d];
                    }
                }
                
                attn_out_vec[h * v_head_dim .. (h + 1) * v_head_dim].copy_from_slice(&out_head);
            }
        }
        
        let attn_out = Tensor::from_vec(attn_out_vec, (16384,), &self.candle_device).map_err(|e| e.to_string())?;

        // 6. o_proj
        let o_names = [format!("model.layers.{}.self_attn.o_proj.weight", layer)];
        let o_names_str: Vec<&str> = o_names.iter().map(|s| s.as_str()).collect();
        let attn_res = project_any(&o_names_str, &attn_out)?;

        // Residual
        let x_post_attn = (x + attn_res).map_err(|e| e.to_string())?;

        // 7. Post Attn Norm
        let post_norm_names = [
            format!("model.language_model.layers.{}.post_attention_layernorm.weight", layer),
            format!("model.layers.{}.post_attention_layernorm.weight", layer)
        ];
        let post_norm_names_str: Vec<&str> = post_norm_names.iter().map(|s| s.as_str()).collect();
        let post_norm_w = project_any(&post_norm_names_str, &x_post_attn)?;
        
        let pa_pow = x_post_attn.sqr().map_err(|e| e.to_string())?;
        let pa_mean = pa_pow.mean_keepdim(0).map_err(|e| e.to_string())?;
        let pa_rsqrt = (pa_mean + norm_eps).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?.recip().map_err(|e| e.to_string())?;
        let pa_norm = x_post_attn.broadcast_mul(&pa_rsqrt).map_err(|e| e.to_string())?.broadcast_mul(&post_norm_w).map_err(|e| e.to_string())?;

        // 8. MLP (SwiGLU) - MoE or Dense
        let router_names = [
            format!("model.layers.{}.mlp.router.weight", layer),
            format!("model.layers.{}.mlp.gate.weight", layer)
        ];
        let router_names_str: Vec<&str> = router_names.iter().map(|s| s.as_str()).collect();
        
        let mut mlp_out = x_post_attn.clone();
        
        if let Ok(router_w) = project_any(&router_names_str, &pa_norm) {
            // MoE
            let router_logits = router_w.to_dtype(DType::F32).map_err(|e| e.to_string())?.flatten_all().map_err(|e| e.to_string())?.to_vec1::<f32>().map_err(|e| e.to_string())?;
            
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
            if let Some(acc) = moe_acc {
                let scaled_acc = (acc * 2.5f64).map_err(|e| e.to_string())?;
                
                // Add shared experts
                let shared_gate_names = [format!("model.layers.{}.mlp.shared_experts.gate_proj.weight", layer)];
                let shared_up_names = [format!("model.layers.{}.mlp.shared_experts.up_proj.weight", layer)];
                let shared_down_names = [format!("model.layers.{}.mlp.shared_experts.down_proj.weight", layer)];
                let shared_gate_str: Vec<&str> = shared_gate_names.iter().map(|s| s.as_str()).collect();
                let shared_up_str: Vec<&str> = shared_up_names.iter().map(|s| s.as_str()).collect();
                let shared_down_str: Vec<&str> = shared_down_names.iter().map(|s| s.as_str()).collect();
                
                let mut shared_out = scaled_acc.clone();
                if let (Ok(gate), Ok(up)) = (project_any(&shared_gate_str, &pa_norm), project_any(&shared_up_str, &pa_norm)) {
                    let mut gate_vec = gate.to_vec1::<f32>().map_err(|e| e.to_string())?;
                    let up_vec = up.to_vec1::<f32>().map_err(|e| e.to_string())?;
                    for j in 0..gate_vec.len() {
                        gate_vec[j] = crate::generation::swiglu(gate_vec[j]) * up_vec[j];
                    }
                    let gate_tensor = Tensor::from_vec(gate_vec, (gate.dims()[0],), &self.candle_device).map_err(|e| e.to_string())?;
                    if let Ok(down) = project_any(&shared_down_str, &gate_tensor) {
                        shared_out = (scaled_acc + down).map_err(|e| e.to_string())?;
                    }
                }
                
                mlp_out = (x_post_attn + shared_out).map_err(|e| e.to_string())?;
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

        if layer == 0 || layer == 77 || layer == 3 {
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
        Ok(mlp_out)
    }

    pub fn execute_generation_loop_gpu(&self, prompt_tokens: &[u32], max_tokens: usize) -> Result<Vec<u32>, String> {
        {
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(78));
            }
        }
        
        let mut generated = Vec::new();
        let mut pos = 0;
        let mut current_token = prompt_tokens[0];
        
        let embed_meta = self.tensors.get("model.embed_tokens.weight")
            .or_else(|| self.tensors.get("model.language_model.embed_tokens.weight"))
            .ok_or("Embeddings not found")?;
        
        let vocab_size = 154880;
        let hidden_dim = 6144; // Should probably be dynamic, but this is fine for now
        
        let total_steps = prompt_tokens.len() - 1 + max_tokens;
        for step in 0..total_steps {
            if step < prompt_tokens.len() {
                current_token = prompt_tokens[step];
            }
            
            let mut x_vec = vec![0.0f32; hidden_dim];
            if current_token < vocab_size as u32 {
                let offset = embed_meta.offset + (current_token as usize) * hidden_dim * 2;
                let raw_data = &self.mmap[offset..offset + hidden_dim * 2];
                for i in 0..hidden_dim {
                    let bytes: [u8; 2] = [raw_data[i * 2], raw_data[i * 2 + 1]];
                    x_vec[i] = half::bf16::from_le_bytes(bytes).to_f32();
                }
            }
            
            let mut x = Tensor::from_vec(x_vec, (hidden_dim,), &self.candle_device).map_err(|e| e.to_string())?;
            
            for layer in 0..78 {
                x = self.forward_layer_gpu(layer, x, pos, 8000000.0)?;
            }
            
            // Output Norm
            let norm_names = [
                "model.language_model.norm.weight",
                "model.norm.weight"
            ];
            let mut norm_w_opt = None;
            for n in &norm_names {
                if let Ok(w) = self.project_vector_gpu(n, &x) {
                    norm_w_opt = Some(w);
                    break;
                }
            }
            if let Some(norm_w) = norm_w_opt {
                let norm_eps = 1e-6f64;
                let x_f32 = x.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let x_sq = x_f32.sqr().map_err(|e| e.to_string())?;
                let x_sq_mean = x_sq.mean_keepdim(0).map_err(|e| e.to_string())?;
                let variance = (x_sq_mean + norm_eps).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?;
                let x_normalized = x_f32.broadcast_div(&variance).map_err(|e| e.to_string())?;
                x = x_normalized.broadcast_mul(&norm_w).map_err(|e| e.to_string())?;
            }
            
            // LM Head
            let head_names = [
                "lm_head.weight",
                "model.language_model.output_layer.weight"
            ];
            let mut logits_opt = None;
            for n in &head_names {
                if let Ok(l) = self.project_vector_gpu(n, &x) {
                    logits_opt = Some(l);
                    break;
                }
            }
            
            let logits = logits_opt.ok_or("LM Head not found")?;
            let logits_vec = logits.to_vec1::<f32>().map_err(|e| e.to_string())?;
            
            let mut best_token = 0;
            let mut best_val = f32::NEG_INFINITY;
            for (i, &val) in logits_vec.iter().enumerate() {
                if val > best_val {
                    best_val = val;
                    best_token = i as u32;
                }
            }
            
            pos += 1;
            if step >= prompt_tokens.len() - 1 {
                generated.push(best_token);
                print!("{} ", best_token);
                use std::io::Write;
                std::io::stdout().flush().unwrap();
                current_token = best_token;
                if best_token == 151329 || best_token == 151336 || best_token == 151338 {
                    break;
                }
            }
        }
        
        Ok(generated)
    }
}
