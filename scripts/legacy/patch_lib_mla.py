import sys

def patch_file():
    with open("jcross_engine_glm/src/lib.rs", "r") as f:
        content = f.read()
    
    # We will find the exact string to replace
    old_qkv_block = """        // 2. QKV Projections
        let q_names = [&format!("model.language_model.layers.{}.self_attn.q_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]];
        let q_names = [&format!("model.language_model.layers.{}.self_attn.q_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]];
        let k_names = [&format!("model.language_model.layers.{}.self_attn.k_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.k_proj.weight", layer)[..]];
        let v_names = [&format!("model.language_model.layers.{}.self_attn.v_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.v_proj.weight", layer)[..]];

        let head_dim = 64; 
        
        let mut q_res = project_any(&q_names, &x_norm);
        let mut k_res = project_any(&k_names, &x_norm);
        let mut v_res = project_any(&v_names, &x_norm);
        
        if let Ok(ref mut q) = q_res {
            if q.len() == 8192 {
                // Bug in conversion script produced 8192 output for q_proj, take first 4096
                *q = q.slice(ndarray::s![..4096]).to_owned();
            }
        }

        if let (Ok(mut q), Ok(mut k), Ok(v)) = (q_res, k_res, v_res) {
            let num_heads = 14;
            let num_kv_heads = 2;

            // 3. Apply RoPE
            let q_slice = q.as_slice_mut().unwrap();
            let k_slice = k.as_slice_mut().unwrap();
            apply_rope(q_slice, k_slice, pos, num_heads, head_dim, rope_theta);

            // 4. Update KV Cache & Attention
            let attn_out = {
                let mut cache_opt = self.kv_cache.borrow_mut();
                if cache_opt.is_none() {
                    return Err("KV Cache not initialized".to_string());
                }
                let cache = cache_opt.as_mut().unwrap();
                
                cache.append_mla(layer, &k);
                
                // SDPA
                let cache_k = &cache.mla_latent_cache[layer];
                let cache_v = &cache.mla_latent_cache[layer];
                sdpa(&q, cache_k, cache_v, num_heads, num_kv_heads, head_dim)
            };

            // 5. Output Projection
            let o_names = [&format!("model.language_model.layers.{}.self_attn.o_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.o_proj.weight", layer)[..]];
            if let Ok(attn_proj) = project_any(&o_names, &attn_out) {
                x = x + attn_proj;
            }
        }"""
        
    new_qkv_block = """        // 2. Q Projections (MLA)
        let q_a_names = [&format!("model.layers.{}.self_attn.q_a_proj.weight", layer)[..]];
        let q_b_names = [&format!("model.layers.{}.self_attn.q_b_proj.weight", layer)[..]];
        let q_a_layernorm_names = [&format!("model.layers.{}.self_attn.q_a_layernorm.weight", layer)[..]];
        let wq_b_names = [&format!("model.layers.{}.self_attn.indexer.wq_b.weight", layer)[..]];

        // 3. KV Projections (MLA)
        let kv_a_names = [&format!("model.layers.{}.self_attn.kv_a_proj_with_mqa.weight", layer)[..]];
        let kv_a_layernorm_names = [&format!("model.layers.{}.self_attn.kv_a_layernorm.weight", layer)[..]];

        let mut q_c = ndarray::Array1::<f32>::zeros(16384);
        let mut q_pe = ndarray::Array1::<f32>::zeros(4096);
        let mut k_pe = ndarray::Array1::<f32>::zeros(128);
        let mut kv_latent = ndarray::Array1::<f32>::zeros(512);
        let mut kv_a_norm_weights = vec![1.0; 512];

        let mut found_mla = false;

        if let Ok(q_a) = project_any(&q_a_names, &x_norm) {
            found_mla = true;
            if let Ok(q_a_norm_w) = project_any(&q_a_layernorm_names, &x_norm) {
                let q_a_layernorm = crate::generation::RMSNorm::new(q_a_norm_w.into_raw_vec(), 1e-5);
                let q_a_normalized = q_a_layernorm.forward(&q_a);

                if let Ok(qc) = project_any(&q_b_names, &q_a_normalized) {
                    q_c = qc;
                }
                if let Ok(qpe) = project_any(&wq_b_names, &q_a_normalized) {
                    q_pe = qpe;
                }
            }
        }

        if found_mla {
            if let Ok(kv_a) = project_any(&kv_a_names, &x_norm) {
                kv_latent = kv_a.slice(ndarray::s![..512]).to_owned();
                k_pe = kv_a.slice(ndarray::s![512..]).to_owned();
                
                if let Ok(kv_a_norm_w) = project_any(&kv_a_layernorm_names, &x_norm) {
                    kv_a_norm_weights = kv_a_norm_w.into_raw_vec();
                }
            }

            crate::generation::apply_rope(
                q_pe.as_slice_mut().unwrap(),
                k_pe.as_slice_mut().unwrap(),
                pos,
                64,
                64,
                10000.0,
            );

            let mut cache_opt = self.kv_cache.borrow_mut();
            if cache_opt.is_none() {
                *cache_opt = Some(crate::generation::AttentionState::new(79, 512, 2, 64, 10000.0));
            }
            let state_ref = cache_opt.as_mut().unwrap();
            state_ref.append_mla(layer, &kv_latent, &k_pe);
            
            let kv_b_names = [format!("model.layers.{}.self_attn.kv_b_proj.weight", layer)];
            let kv_a_layernorm = crate::generation::RMSNorm::new(kv_a_norm_weights, 1e-5);

            let attn_out = crate::generation::sdpa_mla(
                &q_c,
                &q_pe,
                &state_ref.kv_latent_cache[layer],
                &state_ref.k_pe_cache[layer],
                |latent| {
                    let latent_norm = kv_a_layernorm.forward(latent);
                    let name = &kv_b_names[0][..];
                    
                    if let Ok(w_t) = self.get_candle_tensor(name, &self.candle_device) {
                        let x_t = candle_core::Tensor::from_slice(latent_norm.as_slice().unwrap(), (512, 1), &self.candle_device).unwrap();
                        let x_t_f16 = x_t.to_dtype(candle_core::DType::F16).unwrap();
                        
                        if let Ok(t_s) = self.get_candle_tensor(&format!("{}.S", name), &self.candle_device) {
                            let t_v = self.get_candle_tensor(&format!("{}.V", name), &self.candle_device).unwrap();
                            let t_u = self.get_candle_tensor(&format!("{}.U", name), &self.candle_device).unwrap();
                            
                            let temp1 = t_v.matmul(&x_t_f16).unwrap();
                            let rank = t_s.dims()[0];
                            let s_col = t_s.reshape((rank, 1)).unwrap();
                            let temp2 = temp1.broadcast_mul(&s_col).unwrap();
                            let temp3 = t_u.matmul(&temp2).unwrap();
                            
                            let out_f32 = temp3.to_dtype(candle_core::DType::F32).unwrap();
                            let out_vec = out_f32.to_vec2::<f32>().unwrap();
                            ndarray::Array1::from_vec(out_vec.into_iter().flatten().collect())
                        } else {
                            // Dense2D fallback just in case
                            let y_t = w_t.matmul(&x_t_f16).unwrap();
                            let out_f32 = y_t.to_dtype(candle_core::DType::F32).unwrap();
                            let out_vec = out_f32.to_vec2::<f32>().unwrap();
                            ndarray::Array1::from_vec(out_vec.into_iter().flatten().collect())
                        }
                    } else {
                        ndarray::Array1::zeros(28672)
                    }
                },
                64,
                2,
                64,
                16384,
            );
            
            let o_names = [&format!("model.layers.{}.self_attn.o_proj.weight", layer)[..]];
            if let Ok(out) = project_any(&o_names, &attn_out) {
                for i in 0..x.len() {
                    x[i] += out[i];
                }
            }
        }"""
        
    if old_qkv_block in content:
        content = content.replace(old_qkv_block, new_qkv_block)
        print("Successfully replaced QKV block in forward_transformer_layer")
    else:
        print("Could not find the exact QKV block to replace!")
        
    with open("jcross_engine_glm/src/lib.rs", "w") as f:
        f.write(content)

if __name__ == "__main__":
    patch_file()
