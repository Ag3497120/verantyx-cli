use ndarray::{Array1, Array2};
use std::f32::consts::PI;

pub struct RMSNorm {
    weight: Array1<f32>,
    eps: f32,
}

impl RMSNorm {
    pub fn new(weight: Vec<f32>, eps: f32) -> Self {
        Self {
            weight: Array1::from_vec(weight),
            eps,
        }
    }

    pub fn forward(&self, x: &Array1<f32>) -> Array1<f32> {
        let n = x.len() as f32;
        let mut sum_sq = 0.0;
        for &val in x.iter() {
            sum_sq += val * val;
        }
        let rms = (sum_sq / n + self.eps).sqrt();
        
        let mut out = x.clone();
        for (i, val) in out.iter_mut().enumerate() {
            *val = (*val / rms) * self.weight[i];
        }
        out
    }
}

pub fn apply_rope_glm(q: &mut [f32], k: &mut [f32], pos: usize, num_heads: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32, q_pe_offset: usize) {
    let rotary_dim = if head_dim == 128 { 64 } else { head_dim }; 
    let mut inv_freq = vec![0.0; rotary_dim / 2];
    for i in 0..(rotary_dim / 2) {
        inv_freq[i] = 1.0 / rope_theta.powf(2.0 * (i as f32) / (rotary_dim as f32));
    }
    let t = pos as f32;
    let mut freqs = vec![0.0; rotary_dim / 2];
    for i in 0..(rotary_dim / 2) {
        freqs[i] = t * inv_freq[i];
    }
    let mut emb = vec![0.0; rotary_dim];
    for i in 0..(rotary_dim / 2) {
        emb[i] = freqs[i].cos();
        emb[i + rotary_dim / 2] = freqs[i].sin();
    }

    for h in 0..num_heads {
        let q_head = &mut q[h * head_dim + q_pe_offset .. h * head_dim + q_pe_offset + rotary_dim];
        for i in 0..(rotary_dim / 2) {
            let q1 = q_head[2 * i];
            let q2 = q_head[2 * i + 1];
            q_head[2 * i] = q1 * emb[i] - q2 * emb[i + rotary_dim / 2];
            q_head[2 * i + 1] = q1 * emb[i + rotary_dim / 2] + q2 * emb[i];
        }
    }

    let kv_head_dim = head_dim; 
    for h in 0..num_kv_heads {
        let k_head = &mut k[h * kv_head_dim .. h * kv_head_dim + rotary_dim];
        for i in 0..(rotary_dim / 2) {
            let k1 = k_head[2 * i];
            let k2 = k_head[2 * i + 1];
            k_head[2 * i] = k1 * emb[i] - k2 * emb[i + rotary_dim / 2];
            k_head[2 * i + 1] = k1 * emb[i + rotary_dim / 2] + k2 * emb[i];
        }
    }
}

pub fn apply_rope_chunked_glm(q: &mut [f32], k: &mut [f32], start_pos: usize, seq_len: usize, num_heads: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32) {
    let q_len = num_heads * head_dim;
    let k_len = num_kv_heads * head_dim;
    for t in 0..seq_len {
        let pos = start_pos + t;
        let q_token = &mut q[t * q_len .. (t + 1) * q_len];
        let k_token = &mut k[t * k_len .. (t + 1) * k_len];
        apply_rope_glm(q_token, k_token, pos, num_heads, num_kv_heads, head_dim, rope_theta, 0);
    }
}

/// NeoX-style ("rotate half") RoPE used by Qwen/Gemma/Llama-family models.
/// Pairs dimension i with dimension i + head_dim/2, unlike the interleaved GLM variant.
pub fn apply_rope_neox(q: &mut [f32], k: &mut [f32], pos: usize, num_heads: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32) {
    apply_rope_neox_partial(q, k, pos, num_heads, num_kv_heads, head_dim, head_dim, rope_theta);
}

/// NeoX RoPE on the first `rotary_dim` features of each head (Qwen3.5 partial RoPE).
pub fn apply_rope_neox_partial(
    q: &mut [f32],
    k: &mut [f32],
    pos: usize,
    num_heads: usize,
    num_kv_heads: usize,
    head_dim: usize,
    rotary_dim: usize,
    rope_theta: f32,
) {
    let rotary_dim = rotary_dim.min(head_dim);
    if rotary_dim < 2 {
        return;
    }
    let half = rotary_dim / 2;
    let t = pos as f32;
    let mut cos = vec![0.0f32; half];
    let mut sin = vec![0.0f32; half];
    for i in 0..half {
        let inv_freq = 1.0 / rope_theta.powf(2.0 * (i as f32) / (rotary_dim as f32));
        let v = t * inv_freq;
        cos[i] = v.cos();
        sin[i] = v.sin();
    }

    for h in 0..num_heads {
        let base = h * head_dim;
        for i in 0..half {
            let x1 = q[base + i];
            let x2 = q[base + i + half];
            q[base + i] = x1 * cos[i] - x2 * sin[i];
            q[base + i + half] = x2 * cos[i] + x1 * sin[i];
        }
    }
    for h in 0..num_kv_heads {
        let base = h * head_dim;
        for i in 0..half {
            let x1 = k[base + i];
            let x2 = k[base + i + half];
            k[base + i] = x1 * cos[i] - x2 * sin[i];
            k[base + i + half] = x2 * cos[i] + x1 * sin[i];
        }
    }
}

pub fn apply_rope_chunked_neox(q: &mut [f32], k: &mut [f32], start_pos: usize, seq_len: usize, num_heads: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32) {
    let q_len = num_heads * head_dim;
    let k_len = num_kv_heads * head_dim;
    for t in 0..seq_len {
        let pos = start_pos + t;
        let q_token = &mut q[t * q_len .. (t + 1) * q_len];
        let k_token = &mut k[t * k_len .. (t + 1) * k_len];
        apply_rope_neox(q_token, k_token, pos, num_heads, num_kv_heads, head_dim, rope_theta);
    }
}

pub struct AttentionState {
    pub k_cache: Vec<Array2<f32>>, // [layer][seq_len, num_kv_heads * head_dim]
    pub v_cache: Vec<Array2<f32>>, // [layer][seq_len, num_kv_heads * head_dim]
    pub rope_theta: f32,
}

impl AttentionState {
    pub fn new(num_layers: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32) -> Self {
        let mut k_cache = Vec::with_capacity(num_layers);
        let mut v_cache = Vec::with_capacity(num_layers);
        for _ in 0..num_layers {
            k_cache.push(Array2::zeros((0, num_kv_heads * head_dim))); 
            v_cache.push(Array2::zeros((0, num_kv_heads * head_dim)));
        }
        Self {
            k_cache,
            v_cache,
            rope_theta,
        }
    }

    pub fn append_kv(&mut self, layer: usize, k: &Array1<f32>, v: &Array1<f32>) {
        let kv_dim = k.len();
        
        let k_2d = k.clone().into_shape((1, kv_dim)).unwrap();
        let v_2d = v.clone().into_shape((1, kv_dim)).unwrap();

        let seq_len = self.k_cache[layer].shape()[0];
        if seq_len == 0 {
            self.k_cache[layer] = k_2d;
            self.v_cache[layer] = v_2d;
        } else {
            self.k_cache[layer] = ndarray::concatenate(ndarray::Axis(0), &[self.k_cache[layer].view(), k_2d.view()]).unwrap();
            self.v_cache[layer] = ndarray::concatenate(ndarray::Axis(0), &[self.v_cache[layer].view(), v_2d.view()]).unwrap();
        }
    }
}

pub fn swiglu(x: f32) -> f32 {
    x * (1.0 / (1.0 + (-x).exp()))
}

pub fn sdpa_gqa(
    q: &Array1<f32>,
    k_cache: &Array2<f32>, // [seq_len, num_kv_heads * head_dim]
    v_cache: &Array2<f32>, // [seq_len, num_kv_heads * head_dim]
    num_heads: usize,
    num_kv_heads: usize,
    head_dim: usize,
) -> Array1<f32> 
{
    let seq_len = k_cache.shape()[0];
    let mut out = Array1::<f32>::zeros(num_heads * head_dim);
    let scale = (head_dim as f32).sqrt();
    let num_queries_per_kv = num_heads / num_kv_heads;

    for h in 0..num_heads {
        let mut scores = vec![0.0; seq_len];
        let q_head = &q.as_slice().unwrap()[h * head_dim .. (h + 1) * head_dim];
        let kv_group = h / num_queries_per_kv;
        
        for pos in 0..seq_len {
            let k_pos = k_cache.row(pos);
            let k_head = &k_pos.as_slice().unwrap()[kv_group * head_dim .. (kv_group + 1) * head_dim];
            
            let mut dot = 0.0;
            for i in 0..head_dim {
                dot += q_head[i] * k_head[i];
            }
            scores[pos] = dot / scale;
        }
        
        let mut max_score = f32::NEG_INFINITY;
        for &s in &scores {
            if s > max_score { max_score = s; }
        }
        let mut exp_sum = 0.0;
        for s in &mut scores {
            *s = (*s - max_score).exp();
            exp_sum += *s;
        }
        for s in &mut scores {
            *s /= exp_sum;
        }
        
        let mut out_head = vec![0.0; head_dim];
        for pos in 0..seq_len {
            let v_pos = v_cache.row(pos);
            let v_head = &v_pos.as_slice().unwrap()[kv_group * head_dim .. (kv_group + 1) * head_dim];
            for i in 0..head_dim {
                out_head[i] += scores[pos] * v_head[i];
            }
        }
        
        for i in 0..head_dim {
            out[h * head_dim + i] = out_head[i];
        }
    }
    
    out
}

pub fn sdpa_chunked(
    q: &ndarray::Array2<f32>,
    k_cache: &ndarray::Array2<f32>, // [seq_len, num_kv_heads * head_dim]
    v_cache: &ndarray::Array2<f32>, // [seq_len, num_kv_heads * head_dim]
    num_heads: usize,
    num_kv_heads: usize,
    head_dim: usize,
) -> ndarray::Array2<f32> {
    let b = q.shape()[0];
    let seq_len = k_cache.shape()[0];
    let mut out = ndarray::Array2::<f32>::zeros((b, num_heads * head_dim));
    let scale = (head_dim as f32).sqrt();
    let num_queries_per_kv = num_heads / num_kv_heads;

    for token_idx in 0..b {
        let q_token = q.row(token_idx);
        let q_slice = q_token.as_slice().unwrap();
        // Causal mask: this query's absolute position within the cache
        let visible_len = seq_len - b + token_idx + 1;
        
        for h in 0..num_heads {
            let mut scores = vec![0.0; visible_len];
            let q_head = &q_slice[h * head_dim .. (h + 1) * head_dim];
            let kv_group = h / num_queries_per_kv;
            
            for pos in 0..visible_len {
                let k_pos = k_cache.row(pos);
                let k_head = &k_pos.as_slice().unwrap()[kv_group * head_dim .. (kv_group + 1) * head_dim];
                
                let mut dot = 0.0;
                for i in 0..head_dim {
                    dot += q_head[i] * k_head[i];
                }
                scores[pos] = dot / scale;
            }
            
            let mut max_score = f32::NEG_INFINITY;
            for &s in &scores {
                if s > max_score { max_score = s; }
            }
            let mut exp_sum = 0.0;
            for s in &mut scores {
                *s = (*s - max_score).exp();
                exp_sum += *s;
            }
            for s in &mut scores {
                *s /= exp_sum;
            }
            
            let mut out_head = vec![0.0; head_dim];
            for pos in 0..visible_len {
                let v_pos = v_cache.row(pos);
                let v_head = &v_pos.as_slice().unwrap()[kv_group * head_dim .. (kv_group + 1) * head_dim];
                for i in 0..head_dim {
                    out_head[i] += scores[pos] * v_head[i];
                }
            }
            
            for i in 0..head_dim {
                out[[token_idx, h * head_dim + i]] = out_head[i];
            }
        }
    }
    
    out
}
