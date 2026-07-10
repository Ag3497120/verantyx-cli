use candle_core::{Device, Tensor, DType};
use candle_nn::ops::softmax;
use crate::{JCrossEngine, TensorType, MetalAttentionState};

impl JCrossEngine {
    pub fn project_vector_gpu(&self, layer_name: &str, x_t: &Tensor) -> Result<Tensor, String> {
        let meta = self.tensors.get(layer_name).ok_or(format!("Layer not found: {}", layer_name))?;
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let w_t = self.candle_tensors.get(layer_name).ok_or("Tensor missing")?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
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
                let w_t = self.candle_tensors.get(layer_name).ok_or("Tensor missing")?;
                let w_t_f32 = w_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                Ok(w_t_f32)
            },
            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                let x_col = if x_t_f16.rank() == 1 { 
                    x_t_f16.reshape((cols as usize, 1)).map_err(|e| e.to_string())? 
                } else { 
                    x_t_f16.t().map_err(|e| e.to_string())? 
                };
                
                let t_v = self.candle_tensors.get(&format!("{}.V", layer_name)).unwrap();
                let t_s = self.candle_tensors.get(&format!("{}.S", layer_name)).unwrap();
                let t_u = self.candle_tensors.get(&format!("{}.U", layer_name)).unwrap();
                
                let temp1 = t_v.matmul(&x_col).map_err(|e| e.to_string())?;
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let out_f32 = temp3.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                Ok(out_f32.flatten_all().map_err(|e| e.to_string())?)
            }
        }
    }

    pub fn forward_layer_gpu(
        &self, 
        layer: usize, 
        mut x: Tensor, 
        pos: usize, 
        rope_theta: f32
    ) -> Result<Tensor, String> {
        let norm_eps = 1e-6f64;
        
        let project_any = |names: &[&str], input: &Tensor| -> Result<Tensor, String> {
            for name in names {
                if let Ok(res) = self.project_vector_gpu(name, input) {
                    return Ok(res);
                }
            }
            Err(format!("None of the layers found: {:?}", names))
        };

        // 1. RMSNorm
        let norm_names = [
            &format!("model.language_model.layers.{}.input_layernorm.weight", layer)[..],
            &format!("model.layers.{}.input_layernorm.weight", layer)[..]
        ];
        let norm_w = project_any(&norm_names, &x)?;
        
        let x_pow = x.sqr().map_err(|e| e.to_string())?;
        let x_mean = x_pow.mean_keepdim(0).map_err(|e| e.to_string())?;
        let x_rsqrt = (x_mean + norm_eps).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?.recip().map_err(|e| e.to_string())?;
        
        let x_norm = x.broadcast_mul(&x_rsqrt).map_err(|e| e.to_string())?.broadcast_mul(&norm_w).map_err(|e| e.to_string())?;

        // 2. QKV
        let q_names = [&format!("model.language_model.layers.{}.self_attn.q_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]];
        let k_names = [&format!("model.language_model.layers.{}.self_attn.k_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.k_proj.weight", layer)[..]];
        let v_names = [&format!("model.language_model.layers.{}.self_attn.v_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.v_proj.weight", layer)[..]];
        
        // Wait, for 0.5B:
        let num_heads = 14;
        let num_kv_heads = 2;
        let head_dim = 64; 

        let q_res = project_any(&q_names, &x_norm)?;
        let k_res = project_any(&k_names, &x_norm)?;
        let v_res = project_any(&v_names, &x_norm)?;

        // Reshape for attention
        let q = q_res.reshape((1, num_heads, head_dim)).map_err(|e| e.to_string())?;
        let k = k_res.reshape((1, num_kv_heads, head_dim)).map_err(|e| e.to_string())?;
        let v = v_res.reshape((1, num_kv_heads, head_dim)).map_err(|e| e.to_string())?;

        // RoPE using manual computation to ensure compatibility without candle_nn::rotary_emb complexities
        let mut cos_vec = Vec::with_capacity(head_dim);
        let mut sin_vec = Vec::with_capacity(head_dim);
        for i in (0..head_dim).step_by(2) {
            let freq = 1.0 / rope_theta.powf((i as f32) / (head_dim as f32));
            let val = (pos as f32) * freq;
            cos_vec.push(val.cos());
            cos_vec.push(val.cos());
            sin_vec.push(val.sin());
            sin_vec.push(val.sin());
        }
        let cos_t = Tensor::from_vec(cos_vec.clone(), (1, 1, head_dim), &self.candle_device).map_err(|e| e.to_string())?;
        let sin_t = Tensor::from_vec(sin_vec.clone(), (1, 1, head_dim), &self.candle_device).map_err(|e| e.to_string())?;

        // Basic rope for q and k: q * cos + q_shifted * sin
        // q_shifted = [-q[1], q[0], -q[3], q[2], ...]
        let q_paired = q.reshape((1, num_heads, head_dim / 2, 2)).map_err(|e| e.to_string())?;
        let q0 = q_paired.narrow(3, 0, 1).map_err(|e| e.to_string())?;
        let q1 = q_paired.narrow(3, 1, 1).map_err(|e| e.to_string())?;
        let neg_q1 = q1.affine(-1.0, 0.0).map_err(|e| e.to_string())?;
        let q_shifted = Tensor::cat(&[&neg_q1, &q0], 3).map_err(|e| e.to_string())?.reshape((1, num_heads, head_dim)).map_err(|e| e.to_string())?;
        
        // q_rot = q * cos + q_shifted * sin
        let q_cos = q.broadcast_mul(&cos_t).map_err(|e| e.to_string())?;
        let q_sin = q_shifted.broadcast_mul(&sin_t).map_err(|e| e.to_string())?;
        let q_rot_t = (q_cos + q_sin).map_err(|e| e.to_string())?.contiguous().map_err(|e| e.to_string())?;

        let k_paired = k.reshape((1, num_kv_heads, head_dim / 2, 2)).map_err(|e| e.to_string())?;
        let k0 = k_paired.narrow(3, 0, 1).map_err(|e| e.to_string())?;
        let k1 = k_paired.narrow(3, 1, 1).map_err(|e| e.to_string())?;
        let neg_k1 = k1.affine(-1.0, 0.0).map_err(|e| e.to_string())?;
        let k_shifted = Tensor::cat(&[&neg_k1, &k0], 3).map_err(|e| e.to_string())?.reshape((1, num_kv_heads, head_dim)).map_err(|e| e.to_string())?;

        let k_cos = k.broadcast_mul(&cos_t).map_err(|e| e.to_string())?;
        let k_sin = k_shifted.broadcast_mul(&sin_t).map_err(|e| e.to_string())?;
        let k_rot_t = (k_cos + k_sin).map_err(|e| e.to_string())?.contiguous().map_err(|e| e.to_string())?;

        // Append to KV cache
        let mut mcache_ref = self.metal_kv_cache.borrow_mut();
        let mcache = mcache_ref.as_mut().unwrap();
        mcache.append_kv(layer, k_rot_t.clone(), v.clone()).map_err(|e| e.to_string())?;

        // Get full cache
        let k_cache = mcache.kv_cache_k[layer].as_ref().unwrap(); // (seq_len, num_kv_heads, head_dim)
        let v_cache = mcache.kv_cache_v[layer].as_ref().unwrap();

        // SDPA
        // k_cache: (seq, num_kv, head_dim)
        // Repeat KV for GQA
        let num_queries_per_kv = num_heads / num_kv_heads;
        let k_cache_rep = k_cache.unsqueeze(2).map_err(|e| e.to_string())?
            .repeat(&[1, 1, num_queries_per_kv, 1]).map_err(|e| e.to_string())?
            .reshape((k_cache.dim(0).unwrap(), num_heads, head_dim)).map_err(|e| e.to_string())?;
        
        let v_cache_rep = v_cache.unsqueeze(2).map_err(|e| e.to_string())?
            .repeat(&[1, 1, num_queries_per_kv, 1]).map_err(|e| e.to_string())?
            .reshape((v_cache.dim(0).unwrap(), num_heads, head_dim)).map_err(|e| e.to_string())?;

        // Transpose for matmul
        // q_rot_t: (1, num_heads, head_dim) -> (num_heads, 1, head_dim)
        let q_trans = q_rot_t.transpose(0, 1).map_err(|e| e.to_string())?.contiguous().map_err(|e| e.to_string())?; 
        // k_cache_rep: (seq, num_heads, head_dim) -> (num_heads, head_dim, seq)
        let k_trans = k_cache_rep.transpose(0, 1).map_err(|e| e.to_string())?.transpose(1, 2).map_err(|e| e.to_string())?.contiguous().map_err(|e| e.to_string())?;
        // v_cache_rep: (seq, num_heads, head_dim) -> (num_heads, seq, head_dim)
        let v_trans = v_cache_rep.transpose(0, 1).map_err(|e| e.to_string())?.contiguous().map_err(|e| e.to_string())?;

        // att = q * k^T / sqrt(head_dim)
        let att = q_trans.matmul(&k_trans).map_err(|e| e.to_string())?; // (num_heads, 1, seq)
        let att = (att / (head_dim as f64).sqrt()).map_err(|e| e.to_string())?;
        
        let att_soft = softmax(&att, 2).map_err(|e| e.to_string())?;
        let out = att_soft.matmul(&v_trans).map_err(|e| e.to_string())?; // (num_heads, 1, head_dim)
        
        // Transpose back to (1, num_heads, head_dim) and flatten
        let out_flat = out.transpose(0, 1).map_err(|e| e.to_string())?.contiguous().map_err(|e| e.to_string())?.flatten_all().map_err(|e| e.to_string())?;

        // O_proj
        let o_names = [&format!("model.language_model.layers.{}.self_attn.o_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.o_proj.weight", layer)[..]];
        let o_res = project_any(&o_names, &out_flat)?;

        let mut x_post_attn = (x + o_res).map_err(|e| e.to_string())?;

        // Post Attn Norm
        let post_norm_names = [
            &format!("model.language_model.layers.{}.post_attention_layernorm.weight", layer)[..],
            &format!("model.layers.{}.post_attention_layernorm.weight", layer)[..]
        ];
        let post_norm_w = project_any(&post_norm_names, &x_post_attn)?;
        
        let pa_pow = x_post_attn.sqr().map_err(|e| e.to_string())?;
        let pa_mean = pa_pow.mean_keepdim(0).map_err(|e| e.to_string())?;
        let pa_rsqrt = (pa_mean + norm_eps).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?.recip().map_err(|e| e.to_string())?;
        let pa_norm = x_post_attn.broadcast_mul(&pa_rsqrt).map_err(|e| e.to_string())?.broadcast_mul(&post_norm_w).map_err(|e| e.to_string())?;

        // MLP (SwiGLU)
        let gate_names = [&format!("model.language_model.layers.{}.mlp.gate_proj.weight", layer)[..], &format!("model.layers.{}.mlp.gate_proj.weight", layer)[..]];
        let up_names = [&format!("model.language_model.layers.{}.mlp.up_proj.weight", layer)[..], &format!("model.layers.{}.mlp.up_proj.weight", layer)[..]];
        let down_names = [&format!("model.language_model.layers.{}.mlp.down_proj.weight", layer)[..], &format!("model.layers.{}.mlp.down_proj.weight", layer)[..]];
        
        let gate = project_any(&gate_names, &pa_norm)?;
        let up = project_any(&up_names, &pa_norm)?;
        
        // SwiGLU: x * sigmoid(x) * up
        let swish = candle_nn::ops::silu(&gate).map_err(|e| e.to_string())?;
        let intermediate = (swish * up).map_err(|e| e.to_string())?;
        
        let mlp_out = project_any(&down_names, &intermediate)?;

        x_post_attn = (x_post_attn + mlp_out).map_err(|e| e.to_string())?;

        Ok(x_post_attn)
    }

    pub fn execute_generation_loop_gpu(&self, seed_token: u32, max_tokens: usize) -> Result<Vec<u32>, String> {
        let mut generated = Vec::new();
        let mut current_token = seed_token;
        let mut pos = 0;
        
        let num_layers = 24;
        let rope_theta = 10000.0; // Qwen default

        // Initialize Metal cache if empty
        {
            let mut mcache_opt = self.metal_kv_cache.borrow_mut();
            if mcache_opt.is_none() {
                *mcache_opt = Some(MetalAttentionState::new(num_layers));
            }
            let mcache = mcache_opt.as_mut().unwrap();
            
            let cpu_cache_opt = self.kv_cache.borrow();
            println!("[Coder] cpu_cache_opt.is_some: {}", cpu_cache_opt.is_some());
            if let Some(cpu_cache) = cpu_cache_opt.as_ref() {
                println!("[Coder] cpu_cache.kv_cache_k.len: {}", cpu_cache.kv_cache_k.len());
                if cpu_cache.kv_cache_k.len() > 0 {
                    println!("[Coder] cpu_cache.kv_cache_k[0].shape: {:?}", cpu_cache.kv_cache_k[0].shape());
                    pos = cpu_cache.kv_cache_k[0].shape()[0];
                }
                println!("[Coder] Calling sync_from_cpu...");
                mcache.sync_from_cpu(cpu_cache, &self.candle_device).map_err(|e| e.to_string())?;
                println!("[Coder] sync_from_cpu done!");
            }
        }

        let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
            .or_else(|| self.tensors.get("model.embed_tokens.weight"))
            .or_else(|| self.tensors.get("embed_tokens"))
            .ok_or_else(|| "embed_tokens not found".to_string())?;

        let c = match embed_meta.tensor_type {
            TensorType::Dense2D { cols, .. } => cols as usize,
            _ => return Err("embed_tokens must be Dense2D".to_string()),
        };

        for step in 0..max_tokens {
            println!("[Coder] Generating token {}/{} (pos: {})", step + 1, max_tokens, pos);
            use std::io::Write;
            let _ = std::io::stdout().flush();

            // Get embedding
            let row_offset = (current_token as usize) * c * 2;
            let raw_data = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + (c * 2)];
            let mut emb = Vec::with_capacity(c);
            let mut offset = 0;
            for _ in 0..c {
                let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                emb.push(half::f16::from_le_bytes(bytes).to_f32());
                offset += 2;
            }
            
            let mut x = Tensor::from_vec(emb, c, &self.candle_device).map_err(|e| e.to_string())?;

            for layer in 0..num_layers {
                x = self.forward_layer_gpu(layer, x, pos, rope_theta)?;
            }
            
            // Final Norm
            let norm_names = ["model.language_model.norm.weight", "model.norm.weight"];
            let mut final_norm_w = None;
            for name in norm_names.iter() {
                if let Ok(w) = self.project_vector_gpu(name, &x) {
                    final_norm_w = Some(w);
                    break;
                }
            }
            let final_norm_w = final_norm_w.ok_or("Final norm not found")?;
            
            let x_pow = x.sqr().map_err(|e| e.to_string())?;
            let x_mean = x_pow.mean_keepdim(0).map_err(|e| e.to_string())?;
            let x_rsqrt = (x_mean + 1e-6f64).map_err(|e| e.to_string())?.sqrt().map_err(|e| e.to_string())?.recip().map_err(|e| e.to_string())?;
            let x_norm = x.broadcast_mul(&x_rsqrt).map_err(|e| e.to_string())?.broadcast_mul(&final_norm_w).map_err(|e| e.to_string())?;
            
            // Projection
            let logits_t = self.project_vector_gpu("lm_head", &x_norm)?;
            let logits_vec = logits_t.to_vec1::<f32>().map_err(|e| e.to_string())?;
            
            let mut best_token = 0;
            let mut max_logit = f32::NEG_INFINITY;
            for (i, &logit) in logits_vec.iter().enumerate() {
                if logit > max_logit {
                    max_logit = logit;
                    best_token = i as u32;
                }
            }
            
            let next_token = best_token;
            generated.push(next_token);
            current_token = next_token;
            pos += 1;
            
            if next_token == 151643 || next_token == 151645 {
                break;
            }
        }
        
        Ok(generated)
    }
}
