import re

with open("jcross_engine/src/lib.rs", "r") as f:
    code = f.read()

metal_struct = """
pub struct MetalAttentionState {
    pub kv_cache_k: Vec<Option<candle_core::Tensor>>,
    pub kv_cache_v: Vec<Option<candle_core::Tensor>>,
}
impl MetalAttentionState {
    pub fn new(num_layers: usize) -> Self {
        let mut k = Vec::with_capacity(num_layers);
        let mut v = Vec::with_capacity(num_layers);
        for _ in 0..num_layers {
            k.push(None);
            v.push(None);
        }
        Self { kv_cache_k: k, kv_cache_v: v }
    }
    pub fn append_kv(&mut self, layer: usize, k: candle_core::Tensor, v: candle_core::Tensor) -> Result<(), candle_core::Error> {
        if let Some(existing_k) = self.kv_cache_k[layer].as_ref() {
            self.kv_cache_k[layer] = Some(candle_core::Tensor::cat(&[existing_k, &k], 0)?);
            let existing_v = self.kv_cache_v[layer].as_ref().unwrap();
            self.kv_cache_v[layer] = Some(candle_core::Tensor::cat(&[existing_v, &v], 0)?);
        } else {
            self.kv_cache_k[layer] = Some(k);
            self.kv_cache_v[layer] = Some(v);
        }
        Ok(())
    }
}
"""

if "pub struct MetalAttentionState" not in code:
    code = code.replace("pub struct JCrossEngine {", metal_struct + "\npub struct JCrossEngine {")

# Add metal_kv_cache to JCrossEngine
if "metal_kv_cache:" not in code:
    code = code.replace("kv_cache: RefCell<Option<AttentionState>>,", "kv_cache: RefCell<Option<AttentionState>>,\n    metal_kv_cache: RefCell<Option<MetalAttentionState>>,")

# Initialize metal_kv_cache
if "metal_kv_cache: RefCell::new(None)" not in code:
    code = code.replace("kv_cache: RefCell::new(None),", "kv_cache: RefCell::new(None),\n            metal_kv_cache: RefCell::new(None),")

# Replace CPU attention with GPU attention in forward_transformer_layer
# Wait, forward_transformer_layer currently calls `sdpa(&q, cache_k, cache_v, ...)`
# We need to find that block.
block_to_replace = """            let attn_out = {
                let mut cache_opt = self.kv_cache.borrow_mut();
                if cache_opt.is_none() {
                    return Err("KV Cache not initialized".to_string());
                }
                let cache = cache_opt.as_mut().unwrap();
                
                cache.append_kv(layer, &k, &v);
                
                let cache_k = &cache.kv_cache_k[layer];
                let cache_v = &cache.kv_cache_v[layer];
                sdpa(&q, cache_k, cache_v, num_heads, num_kv_heads, head_dim)
            };"""

metal_attention = """            let attn_out = {
                let mut cache_opt = self.metal_kv_cache.borrow_mut();
                if cache_opt.is_none() {
                    return Err("Metal KV Cache not initialized".to_string());
                }
                let cache = cache_opt.as_mut().unwrap();
                
                // q: (num_heads * head_dim) -> (1, num_heads * head_dim)
                // k, v: (num_kv_heads * head_dim) -> (1, num_kv_heads * head_dim)
                let device = &self.candle_device;
                let q_t = candle_core::Tensor::from_slice(q.as_slice().unwrap(), (1, num_heads * head_dim), device).map_err(|e| e.to_string())?;
                let k_t = candle_core::Tensor::from_slice(k.as_slice().unwrap(), (1, num_kv_heads * head_dim), device).map_err(|e| e.to_string())?;
                let v_t = candle_core::Tensor::from_slice(v.as_slice().unwrap(), (1, num_kv_heads * head_dim), device).map_err(|e| e.to_string())?;
                
                cache.append_kv(layer, k_t, v_t).map_err(|e| e.to_string())?;
                
                let cache_k = cache.kv_cache_k[layer].as_ref().unwrap(); // (seq_len, num_kv_heads * head_dim)
                let cache_v = cache.kv_cache_v[layer].as_ref().unwrap();
                
                // We must reshape for GQA: Q: (1, num_heads, head_dim), K: (seq_len, num_kv_heads, head_dim)
                let seq_len = cache_k.dim(0).unwrap();
                let q_r = q_t.reshape((1, num_heads, head_dim)).map_err(|e| e.to_string())?;
                let k_r = cache_k.reshape((seq_len, num_kv_heads, head_dim)).map_err(|e| e.to_string())?;
                let v_r = cache_v.reshape((seq_len, num_kv_heads, head_dim)).map_err(|e| e.to_string())?;
                
                // Repeat K and V across heads to match num_heads
                let kv_groups = num_heads / num_kv_heads;
                // Candle repeat is tricky, let's use broadcast or explicit replication.
                // In Candle, we can index or stack. Or just write a small CPU loop?
                // Wait! If we bring cache_k and cache_v to CPU for SDPA, it's the SAME slow speed!
                // To do it on GPU properly without custom kernels:
                // We can do it per head!
                let mut out_heads = Vec::new();
                let scale = 1.0 / (head_dim as f32).sqrt();
                for h in 0..num_heads {
                    let kv_h = h / kv_groups;
                    // q_h: (1, head_dim)
                    let q_h = q_r.narrow(1, h, 1).map_err(|e| e.to_string())?.reshape((1, head_dim)).unwrap();
                    // k_h: (seq_len, head_dim)
                    let k_h = k_r.narrow(1, kv_h, 1).map_err(|e| e.to_string())?.reshape((seq_len, head_dim)).unwrap();
                    // v_h: (seq_len, head_dim)
                    let v_h = v_r.narrow(1, kv_h, 1).map_err(|e| e.to_string())?.reshape((seq_len, head_dim)).unwrap();
                    
                    // scores: (1, seq_len) = q_h * k_h.t()
                    let k_h_t = k_h.t().unwrap();
                    let mut scores = q_h.matmul(&k_h_t).map_err(|e| e.to_string())?;
                    // scale
                    let scale_t = candle_core::Tensor::new(scale, device).unwrap();
                    scores = scores.broadcast_mul(&scale_t).unwrap();
                    // softmax
                    let probs = candle_nn::ops::softmax(&scores, 1).map_err(|e| e.to_string())?;
                    // out_h: (1, head_dim) = probs * v_h
                    let out_h = probs.matmul(&v_h).map_err(|e| e.to_string())?;
                    out_heads.push(out_h);
                }
                
                // Cat all heads
                let out_t = candle_core::Tensor::cat(&out_heads, 1).map_err(|e| e.to_string())?; // (1, num_heads * head_dim)
                let out_f32 = out_t.to_dtype(candle_core::DType::F32).unwrap();
                let out_vec = out_f32.to_vec2::<f32>().unwrap();
                
                ndarray::Array1::from_vec(out_vec[0].clone())
            };"""

code = code.replace(block_to_replace, metal_attention)

# Need to update execute_generation_loop to initialize metal_kv_cache
gen_loop_cache_init = """        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, num_kv_heads, head_dim, rope_theta));
            }
        }"""
        
gen_loop_metal_init = """        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, num_kv_heads, head_dim, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }"""
        
code = code.replace(gen_loop_cache_init, gen_loop_metal_init)

with open("jcross_engine/src/lib.rs", "w") as f:
    f.write(code)

