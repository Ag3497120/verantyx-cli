use candle_core::{Device, Tensor, DType};
use candle_nn::ops::softmax;
use crate::{JCrossEngine, TensorType, MetalAttentionState};

// ============================================================================
// Batched full-GPU path for standard architectures (Qwen family).
// SVD weights are composed to dense once, uploaded to Metal/CUDA, and the whole
// forward (RMSNorm, QKV+bias, NeoX RoPE, causal GQA attention, SwiGLU) runs
// on-device. Falls back to the CPU path on any error.
// ============================================================================
impl JCrossEngine {
    fn tensor_bytes(t: &Tensor) -> usize {
        t.elem_count() * t.dtype().size_in_bytes()
    }

    /// FIFO eviction: keep the composed-weight cache under cache_budget_bytes.
    /// Evicted weights are recomposed from the f16 mmap on next use (slower,
    /// but bounded memory — a 9B jgen would otherwise pin ~36 GB of f32).
    fn gpu_cache_evict(&self, incoming: usize) {
        let budget = self.cache_budget_bytes;
        let mut bytes = self.gpu_cache_bytes.borrow_mut();
        let mut order = self.gpu_cache_order.borrow_mut();
        let mut cache = self.gpu_weight_cache.borrow_mut();
        while *bytes + incoming > budget && !order.is_empty() {
            let victim = order.remove(0);
            if let Some((w, b)) = cache.remove(&victim) {
                *bytes -= Self::tensor_bytes(&w) + b.as_ref().map(Self::tensor_bytes).unwrap_or(0);
            }
        }
    }

    /// Returns (W^T (in,out) f32 on device, optional bias (out,) f32).
    /// SVDLossless: W = U·C·diag(S)·V_t·diag(mod_x), bias = mod_y. Cached.
    pub fn gpu_weight(&self, name: &str) -> Result<(Tensor, Option<Tensor>), String> {
        if let Some(hit) = self.gpu_weight_cache.borrow().get(name) {
            return Ok(hit.clone());
        }
        let meta = self.tensors.get(name).ok_or(format!("Tensor not found: {}", name))?;
        let dev = &self.candle_device;
        let entry = match meta.tensor_type {
            TensorType::Dense2D { .. } => {
                let w = self.get_candle_tensor(name, dev)?
                    .to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let wt = w.t().and_then(|t| t.contiguous()).map_err(|e| e.to_string())?;
                (wt, None)
            },
            TensorType::SVDLossless { rows: _, cols, rank } => {
                let f32d = |t: Tensor| t.to_dtype(DType::F32).map_err(|e| e.to_string());
                let u = f32d(self.get_candle_tensor(&format!("{}.U", name), dev)?)?;      // (m, r)
                let s = f32d(self.get_candle_tensor(&format!("{}.S", name), dev)?)?;      // (r,)
                let v_t = f32d(self.get_candle_tensor(&format!("{}.V", name), dev)?)?;    // (r, n)
                let c = f32d(self.get_candle_tensor(&format!("{}.c_valve", name), dev)?)?;// (r, r)
                let mod_x = f32d(self.get_candle_tensor(&format!("{}.mod_x", name), dev)?)?; // (n,)
                let mod_y = f32d(self.get_candle_tensor(&format!("{}.mod_y", name), dev)?)?; // (m,)
                let sv = v_t.broadcast_mul(&s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;                       // diag(S)·V_t (r, n)
                let csv = c.matmul(&sv).map_err(|e| e.to_string())?;    // (r, n)
                let w = u.matmul(&csv).map_err(|e| e.to_string())?;     // (m, n)
                let w = w.broadcast_mul(&mod_x.reshape((1, cols as usize)).map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;                       // ·diag(mod_x)
                let wt = w.t().and_then(|t| t.contiguous()).map_err(|e| e.to_string())?; // (n, m)
                (wt, Some(mod_y))
            },
            TensorType::Dense1D { .. } => {
                let w = self.get_candle_tensor(name, dev)?
                    .to_dtype(DType::F32).map_err(|e| e.to_string())?;
                (w, None)
            },
        };
        let sz = Self::tensor_bytes(&entry.0)
            + entry.1.as_ref().map(Self::tensor_bytes).unwrap_or(0);
        self.gpu_cache_evict(sz);
        self.gpu_weight_cache.borrow_mut().insert(name.to_string(), entry.clone());
        self.gpu_cache_order.borrow_mut().push(name.to_string());
        *self.gpu_cache_bytes.borrow_mut() += sz;
        Ok(entry)
    }

    fn gpu_linear(&self, names: &[String], x: &Tensor) -> Result<Tensor, String> {
        for name in names {
            if self.tensors.contains_key(name.as_str()) {
                let (wt, bias) = self.gpu_weight(name)?;
                let mut y = x.matmul(&wt).map_err(|e| e.to_string())?;
                if let Some(b) = bias {
                    let out = y.dim(1).map_err(|e| e.to_string())?;
                    y = y.broadcast_add(&b.reshape((1, out)).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                }
                return Ok(y);
            }
        }
        Err(format!("None of the layers found: {:?}", names))
    }

    fn gpu_vec1(&self, names: &[String]) -> Result<Tensor, String> {
        for name in names {
            if self.tensors.contains_key(name.as_str()) {
                return Ok(self.gpu_weight(name)?.0);
            }
        }
        Err(format!("None of the vectors found: {:?}", names))
    }

    fn gpu_rmsnorm(&self, x: &Tensor, w: &Tensor) -> Result<Tensor, String> {
        let c = x.dim(1).map_err(|e| e.to_string())?;
        let ss = x.sqr().and_then(|t| t.mean_keepdim(1)).map_err(|e| e.to_string())?;
        let rms = (ss + 1e-6f64).and_then(|t| t.sqrt()).map_err(|e| e.to_string())?;
        x.broadcast_div(&rms)
            .and_then(|t| t.broadcast_mul(&w.reshape((1, c))?))
            .map_err(|e| e.to_string())
    }

    /// Per-head RMSNorm (Qwen3-family QK-norm). x: (b, n_heads*head_dim), w: (head_dim).
    fn gpu_head_rmsnorm(&self, x: &Tensor, w: &Tensor, n_heads: usize, head_dim: usize)
        -> Result<Tensor, String> {
        let e = |e: candle_core::Error| e.to_string();
        let b = x.dim(0).map_err(e)?;
        let xh = x.reshape((b, n_heads, head_dim)).map_err(e)?;
        let ss = xh.sqr().and_then(|t| t.mean_keepdim(2)).map_err(e)?;
        let rms = (ss + 1e-6f64).and_then(|t| t.sqrt()).map_err(e)?;
        xh.broadcast_div(&rms)
            .and_then(|t| t.broadcast_mul(&w.reshape((1, 1, head_dim))?))
            .and_then(|t| t.reshape((b, n_heads * head_dim)))
            .map_err(e)
    }

    /// NeoX (rotate-half) RoPE on device. x: (b, n_heads*head_dim), positions start at start_pos.
    fn gpu_rope_neox(&self, x: &Tensor, n_heads: usize, start_pos: usize) -> Result<Tensor, String> {
        let hd = self.head_dim;
        let half = hd / 2;
        let b = x.dim(0).map_err(|e| e.to_string())?;
        // cos/sin tables (b, 1, half), CPU-built (small), broadcast over heads
        let mut cos_v = Vec::with_capacity(b * half);
        let mut sin_v = Vec::with_capacity(b * half);
        for t in 0..b {
            let pos = (start_pos + t) as f32;
            for i in 0..half {
                let freq = 1.0f32 / self.rope_theta.powf(2.0 * (i as f32) / (hd as f32));
                cos_v.push((pos * freq).cos());
                sin_v.push((pos * freq).sin());
            }
        }
        let dev = &self.candle_device;
        let cos = Tensor::from_vec(cos_v, (b, 1, half), dev).map_err(|e| e.to_string())?;
        let sin = Tensor::from_vec(sin_v, (b, 1, half), dev).map_err(|e| e.to_string())?;
        let xr = x.reshape((b, n_heads, hd)).map_err(|e| e.to_string())?;
        let x1 = xr.narrow(2, 0, half).map_err(|e| e.to_string())?;
        let x2 = xr.narrow(2, half, half).map_err(|e| e.to_string())?;
        let r1 = (x1.broadcast_mul(&cos).map_err(|e| e.to_string())?
            - x2.broadcast_mul(&sin).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        let r2 = (x2.broadcast_mul(&cos).map_err(|e| e.to_string())?
            + x1.broadcast_mul(&sin).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        Tensor::cat(&[&r1, &r2], 2)
            .and_then(|t| t.reshape((b, n_heads * hd)))
            .map_err(|e| e.to_string())
    }

    /// One transformer layer, batched on GPU. x: (b, hidden) f32.
    fn gpu_layer(&self, layer: usize, x: Tensor, start_pos: usize) -> Result<Tensor, String> {
        let e = |e: candle_core::Error| e.to_string();
        let (nh, nkv, hd) = (self.num_heads, self.num_kv_heads, self.head_dim);
        let b = x.dim(0).map_err(e)?;

        let names = |mid: &str| vec![
            format!("model.language_model.layers.{}.{}", layer, mid),
            format!("model.layers.{}.{}", layer, mid),
        ];

        // MoE layers are not implemented in the batched GPU path yet -> whole-pass CPU fallback
        if layer >= self.first_moe_layer
            && self.tensors.contains_key(&format!("model.layers.{}.mlp.gate.weight", layer)) {
            return Err("MoE layer: batched GPU path not implemented, using CPU".into());
        }

        // 1. Input RMSNorm
        let norm_w = self.gpu_vec1(&names("input_layernorm.weight"))?;
        let x_norm = self.gpu_rmsnorm(&x, &norm_w)?;

        // 2. QKV (+aux biases already merged in gpu_linear via .bias tensors below)
        let mut q = self.gpu_linear(&names("self_attn.q_proj.weight"), &x_norm)?;
        let mut k = self.gpu_linear(&names("self_attn.k_proj.weight"), &x_norm)?;
        let mut v = self.gpu_linear(&names("self_attn.v_proj.weight"), &x_norm)?;
        for (mat, proj) in [(&mut q, "q_proj"), (&mut k, "k_proj"), (&mut v, "v_proj")] {
            let bnames = names(&format!("self_attn.{}.bias", proj));
            if let Ok(bias) = self.gpu_vec1(&bnames) {
                let out = mat.dim(1).map_err(e)?;
                *mat = mat.broadcast_add(&bias.reshape((1, out)).map_err(e)?).map_err(e)?;
            }
        }

        // QK-norm (Qwen3-family): per-head RMSNorm before RoPE
        if let Ok(qw) = self.gpu_vec1(&names("self_attn.q_norm.weight")) {
            q = self.gpu_head_rmsnorm(&q, &qw, nh, hd)?;
        }
        if let Ok(kw) = self.gpu_vec1(&names("self_attn.k_norm.weight")) {
            k = self.gpu_head_rmsnorm(&k, &kw, nkv, hd)?;
        }

        // 3. RoPE (NeoX only in the batched path; GLM interleaved uses CPU fallback)
        if !self.rope_neox { return Err("GLM RoPE not supported in batched GPU path".into()); }
        let q = self.gpu_rope_neox(&q, nh, start_pos)?;
        let k = self.gpu_rope_neox(&k, nkv, start_pos)?;

        // 4. KV cache append (t, nkv*hd)
        let (k_all, v_all) = {
            let mut kv = self.gpu_kv.borrow_mut();
            let slot = &mut kv[layer];
            let k_new = match slot.0.take() {
                Some(prev) => Tensor::cat(&[&prev, &k], 0).map_err(e)?,
                None => k.clone(),
            };
            let v_new = match slot.1.take() {
                Some(prev) => Tensor::cat(&[&prev, &v], 0).map_err(e)?,
                None => v.clone(),
            };
            slot.0 = Some(k_new.clone());
            slot.1 = Some(v_new.clone());
            (k_new, v_new)
        };
        let t_total = k_all.dim(0).map_err(e)?;

        // 5. Causal GQA attention
        let g = nh / nkv;
        let qh = q.reshape((b, nh, hd)).map_err(e)?
            .transpose(0, 1).map_err(e)?.contiguous().map_err(e)?;          // (nh, b, hd)
        let kh = k_all.reshape((t_total, nkv, hd)).map_err(e)?
            .transpose(0, 1).map_err(e)?                                    // (nkv, t, hd)
            .transpose(1, 2).map_err(e)?.contiguous().map_err(e)?           // (nkv, hd, t)
            .reshape((nkv, 1, hd, t_total)).map_err(e)?
            .repeat((1, g, 1, 1)).map_err(e)?
            .reshape((nh, hd, t_total)).map_err(e)?;
        let vh = v_all.reshape((t_total, nkv, hd)).map_err(e)?
            .transpose(0, 1).map_err(e)?.contiguous().map_err(e)?           // (nkv, t, hd)
            .reshape((nkv, 1, t_total, hd)).map_err(e)?
            .repeat((1, g, 1, 1)).map_err(e)?
            .reshape((nh, t_total, hd)).map_err(e)?;

        let scale = 1.0f64 / (hd as f64).sqrt();
        let scores = (qh.matmul(&kh).map_err(e)? * scale).map_err(e)?;      // (nh, b, t)

        // causal mask: query i (global pos t_total-b+i) sees keys <= its position
        let mut mask_v = vec![0f32; b * t_total];
        for i in 0..b {
            let visible = t_total - b + i + 1;
            for j in visible..t_total { mask_v[i * t_total + j] = f32::NEG_INFINITY; }
        }
        let mask = Tensor::from_vec(mask_v, (1, b, t_total), &self.candle_device).map_err(e)?;
        let scores = scores.broadcast_add(&mask).map_err(e)?;
        let probs = softmax(&scores, 2).map_err(e)?;                         // (nh, b, t)
        let ctx = probs.matmul(&vh).map_err(e)?                              // (nh, b, hd)
            .transpose(0, 1).map_err(e)?.contiguous().map_err(e)?            // (b, nh, hd)
            .reshape((b, nh * hd)).map_err(e)?;

        // 6. Output projection + residual
        let attn_out = self.gpu_linear(&names("self_attn.o_proj.weight"), &ctx)?;
        let x = (x + attn_out).map_err(e)?;

        // 7. Post-attention norm + SwiGLU MLP + residual
        let post_w = self.gpu_vec1(&names("post_attention_layernorm.weight"))?;
        let x_post = self.gpu_rmsnorm(&x, &post_w)?;
        let gate = self.gpu_linear(&names("mlp.gate_proj.weight"), &x_post)?;
        let up = self.gpu_linear(&names("mlp.up_proj.weight"), &x_post)?;
        let act = (candle_nn::ops::silu(&gate).map_err(e)? * up).map_err(e)?;
        let down = self.gpu_linear(&names("mlp.down_proj.weight"), &act)?;
        (x + down).map_err(e)
    }

    fn gpu_embed_rows(&self, soft: &[Vec<f32>], tokens: &[u32]) -> Result<Tensor, String> {
        let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
            .or_else(|| self.tensors.get("model.embed_tokens.weight"))
            .or_else(|| self.tensors.get("embed_tokens"))
            .ok_or_else(|| "embed_tokens not found".to_string())?;
        let c = match embed_meta.tensor_type {
            TensorType::Dense2D { cols, .. } => cols as usize,
            _ => return Err("embed_tokens must be Dense2D".to_string()),
        };
        let b = soft.len() + tokens.len();
        let mut buf = Vec::with_capacity(b * c);
        for vec in soft {
            if vec.len() != c { return Err(format!("Soft token dim {} != hidden {}", vec.len(), c)); }
            buf.extend_from_slice(vec);
        }
        for &token in tokens {
            let row_offset = (token as usize) * c * 2;
            let raw = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + c * 2];
            for j in 0..c {
                let bytes = [raw[j * 2], raw[j * 2 + 1]];
                buf.push(half::f16::from_le_bytes(bytes).to_f32());
            }
        }
        Tensor::from_vec(buf, (b, c), &self.candle_device).map_err(|e| e.to_string())
    }

    fn gpu_final_norm(&self, x: &Tensor) -> Result<Tensor, String> {
        let norm_w = self.gpu_vec1(&[
            "model.language_model.norm.weight".to_string(),
            "model.norm.weight".to_string(),
        ])?;
        self.gpu_rmsnorm(x, &norm_w)
    }

    /// Full-GPU encode with optional soft (virtual) tokens. Returns final hidden of last token.
    pub fn encode_gpu_batched(&self, soft: &[Vec<f32>], tokens: &[u32]) -> Result<Vec<f32>, String> {
        {
            let mut kv = self.gpu_kv.borrow_mut();
            if kv.len() != self.num_layers { *kv = vec![(None, None); self.num_layers]; }
        }
        let start_pos = self.gpu_kv.borrow()[0].0.as_ref()
            .map(|t| t.dim(0).unwrap_or(0)).unwrap_or(0);
        let mut x = self.gpu_embed_rows(soft, tokens)?;
        for layer in 0..self.num_layers {
            x = self.gpu_layer(layer, x, start_pos)?;
        }
        let x = self.gpu_final_norm(&x)?;
        let b = x.dim(0).map_err(|e| e.to_string())?;
        x.narrow(0, b - 1, 1).and_then(|t| t.flatten_all()).map_err(|e| e.to_string())?
            .to_vec1::<f32>().map_err(|e| e.to_string())
    }

    /// Full-GPU generation: batched prefill + greedy decode.
    pub fn generate_gpu_batched(&self, prompt: &[u32], max_tokens: usize) -> Result<Vec<u32>, String> {
        let e = |e: candle_core::Error| e.to_string();
        {
            let mut kv = self.gpu_kv.borrow_mut();
            *kv = vec![(None, None); self.num_layers];
        }
        let lm_head = self.gpu_weight("lm_head")
            .or_else(|_| self.gpu_weight("lm_head.weight"))?.0;  // (hidden, vocab)

        let mut generated = Vec::new();
        let mut pos;
        // Prefill (batched)
        let mut x = self.gpu_embed_rows(&[], prompt)?;
        for layer in 0..self.num_layers {
            x = self.gpu_layer(layer, x, 0)?;
        }
        pos = prompt.len();
        let mut last = self.gpu_final_norm(&x)?;
        let b = last.dim(0).map_err(e)?;
        last = last.narrow(0, b - 1, 1).map_err(e)?;

        for _ in 0..max_tokens {
            let logits = last.matmul(&lm_head).map_err(e)?
                .flatten_all().map_err(e)?.to_vec1::<f32>().map_err(e)?;
            let mut best = 0u32; let mut best_val = f32::NEG_INFINITY;
            for (i, &v) in logits.iter().enumerate() {
                if v > best_val { best_val = v; best = i as u32; }
            }
            generated.push(best);
            if self.eos_tokens.contains(&best) { break; }
            let mut x = self.gpu_embed_rows(&[], &[best])?;
            for layer in 0..self.num_layers {
                x = self.gpu_layer(layer, x, pos)?;
            }
            pos += 1;
            last = self.gpu_final_norm(&x)?;
        }
        Ok(generated)
    }
}

impl JCrossEngine {
    pub fn project_vector_gpu(&self, layer_name: &str, x_t: &Tensor) -> Result<Tensor, String> {
        let meta = self.tensors.get(layer_name).ok_or(format!("Layer not found: {}", layer_name))?;
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
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
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
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
        let norm_eps = 1e-6f64;
        
        let project_any = |names: &[&str], input: &Tensor| -> Result<Tensor, String> {
            for name in names {
                if let Ok(res) = self.project_vector_gpu(name, input) {
                    return Ok(res);
                }
            }
            Err(format!("None of the layers found: {:?}", names))
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
                let q_idx = head * q_head_dim + i;
                let q_idx2 = head * q_head_dim + i + (q_pe_dim / 2);
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
        let router_names = [format!("model.layers.{}.mlp.router.weight", layer)];
        let router_names_str: Vec<&str> = router_names.iter().map(|s| s.as_str()).collect();
        
        let mut mlp_out = x_post_attn.clone();
        
        if let Ok(router_w) = project_any(&router_names_str, &pa_norm) {
            // MoE
            let router_logits = router_w.to_dtype(DType::F32).map_err(|e| e.to_string())?.flatten_all().map_err(|e| e.to_string())?.to_vec1::<f32>().map_err(|e| e.to_string())?;
            
            let k = 8;
            let mut experts_with_scores: Vec<(usize, f32)> = router_logits.iter().enumerate().map(|(i, &s)| {
                // Adaptive Pinning Mask: If the expert is not loaded in VRAM (candle_tensors), force logit to -inf
                let gate_name = format!("model.layers.{}.mlp.experts.{}.gate_proj.weight", layer, i);
                if self.candle_tensors.contains_key(&gate_name) {
                    (i, s)
                } else {
                    (i, f32::NEG_INFINITY)
                }
            }).collect();
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
                    x_vec[i] = half::f16::from_le_bytes(bytes).to_f32();
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
                current_token = best_token;
                if best_token == 151329 || best_token == 151336 || best_token == 151338 {
                    break;
                }
            }
        }
        
        Ok(generated)
    }
}
