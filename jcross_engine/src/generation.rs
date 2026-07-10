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

pub fn apply_rope(q: &mut [f32], k: &mut [f32], pos: usize, num_heads: usize, head_dim: usize, rope_theta: f32) {
    for head in 0..num_heads {
        for i in 0..(head_dim / 2) {
            let freq = 1.0 / rope_theta.powf(2.0 * (i as f32) / (head_dim as f32));
            let val = (pos as f32) * freq;
            let cos_val = val.cos();
            let sin_val = val.sin();

            let q_idx = head * head_dim + i * 2;
            let q0 = q[q_idx];
            let q1 = q[q_idx + 1];
            q[q_idx] = q0 * cos_val - q1 * sin_val;
            q[q_idx + 1] = q0 * sin_val + q1 * cos_val;

            if head < (k.len() / head_dim) { // GQA support
                let k_idx = head * head_dim + i * 2;
                let k0 = k[k_idx];
                let k1 = k[k_idx + 1];
                k[k_idx] = k0 * cos_val - k1 * sin_val;
                k[k_idx + 1] = k0 * sin_val + k1 * cos_val;
            }
        }
    }
}

pub struct AttentionState {
    pub kv_cache_k: Vec<Array2<f32>>, // [layer][pos, hidden]
    pub kv_cache_v: Vec<Array2<f32>>,
    pub num_heads: usize,
    pub head_dim: usize,
    pub rope_theta: f32,
}

impl AttentionState {
    pub fn new(num_layers: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32) -> Self {
        let mut kv_cache_k = Vec::with_capacity(num_layers);
        let mut kv_cache_v = Vec::with_capacity(num_layers);
        for _ in 0..num_layers {
            // Using a dynamic Array2 for cache: rows=sequence_length, cols=num_kv_heads * head_dim
            // For simplicity in this engine, we start with 0 sequence length
            kv_cache_k.push(Array2::zeros((0, num_kv_heads * head_dim))); 
            kv_cache_v.push(Array2::zeros((0, num_kv_heads * head_dim)));
        }
        Self {
            kv_cache_k,
            kv_cache_v,
            num_heads: num_kv_heads, // will be used to pass config
            head_dim,
            rope_theta,
        }
    }

    /// Appends a new sequence of K and V to the cache for a specific layer.
    /// In a real highly-optimized engine, this would use pre-allocated buffers.
    pub fn append_kv(&mut self, layer: usize, k: &Array1<f32>, v: &Array1<f32>) {
        let current_k = &self.kv_cache_k[layer];
        let seq_len = current_k.shape()[0];
        let dim = current_k.shape()[1];
        
        // Ensure k and v have the expected dimension
        assert_eq!(k.len(), dim);
        assert_eq!(v.len(), dim);
        
        // Concatenate along the sequence dimension (axis 0)
        let k_2d = k.clone().into_shape((1, dim)).unwrap();
        let v_2d = v.clone().into_shape((1, dim)).unwrap();
        
        if seq_len == 0 {
            self.kv_cache_k[layer] = k_2d;
            self.kv_cache_v[layer] = v_2d;
        } else {
            self.kv_cache_k[layer] = ndarray::concatenate(ndarray::Axis(0), &[current_k.view(), k_2d.view()]).unwrap();
            let current_v = &self.kv_cache_v[layer];
            self.kv_cache_v[layer] = ndarray::concatenate(ndarray::Axis(0), &[current_v.view(), v_2d.view()]).unwrap();
        }
    }
}

/// Scaled Dot-Product Attention (SDPA)
/// Computes: Attention(Q, K, V) = softmax(Q * K^T / sqrt(d)) * V
/// This is a simplified unoptimized version for POC.
/// q: (num_heads * head_dim)
/// cache_k: (seq_len, num_kv_heads * head_dim)
/// cache_v: (seq_len, num_kv_heads * head_dim)
pub fn sdpa(q: &Array1<f32>, cache_k: &Array2<f32>, cache_v: &Array2<f32>, num_heads: usize, num_kv_heads: usize, head_dim: usize) -> Array1<f32> {
    let seq_len = cache_k.shape()[0];
    let mut out = Array1::zeros(num_heads * head_dim);
    let scale = 1.0 / (head_dim as f32).sqrt();

    // Grouped-Query Attention logic: heads share KV
    let kv_groups = num_heads / num_kv_heads;

    for h in 0..num_heads {
        let kv_h = h / kv_groups; // Which KV head this Q head belongs to
        
        let q_head = q.slice(ndarray::s![h * head_dim .. (h + 1) * head_dim]);
        
        // 1. Compute scores: Q * K^T
        let mut scores = Array1::zeros(seq_len);
        for s in 0..seq_len {
            let k_head = cache_k.slice(ndarray::s![s, kv_h * head_dim .. (kv_h + 1) * head_dim]);
            scores[s] = q_head.dot(&k_head) * scale;
        }

        // 2. Softmax
        let max_score = scores.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        scores.mapv_inplace(|v| (v - max_score).exp());
        let sum: f32 = scores.sum();
        scores.mapv_inplace(|v| v / sum);

        // 3. Multiply by V
        let mut out_head = Array1::zeros(head_dim);
        for s in 0..seq_len {
            let v_head = cache_v.slice(ndarray::s![s, kv_h * head_dim .. (kv_h + 1) * head_dim]);
            let weight = scores[s];
            for i in 0..head_dim {
                out_head[i] += weight * v_head[i];
            }
        }
        
        let mut out_slice = out.slice_mut(ndarray::s![h * head_dim .. (h + 1) * head_dim]);
        out_slice.assign(&out_head);
    }
    
    out
}

pub fn swiglu(x: f32) -> f32 {
    // SiLU (Swish) = x * sigmoid(x)
    x * (1.0 / (1.0 + (-x).exp()))
}

pub fn apply_rope_chunked(q: &mut [f32], k: &mut [f32], start_pos: usize, seq_len: usize, num_heads: usize, num_kv_heads: usize, head_dim: usize, rope_theta: f32) {
    let q_stride = num_heads * head_dim;
    let k_stride = num_kv_heads * head_dim;
    for b in 0..seq_len {
        let pos = start_pos + b;
        let q_token = &mut q[b * q_stride .. (b + 1) * q_stride];
        let k_token = &mut k[b * k_stride .. (b + 1) * k_stride];
        apply_rope(q_token, k_token, pos, num_heads, head_dim, rope_theta);
    }
}

pub fn sdpa_chunked(q_chunk: &Array2<f32>, cache_k: &Array2<f32>, cache_v: &Array2<f32>, num_heads: usize, num_kv_heads: usize, head_dim: usize) -> Array2<f32> {
    let q_len = q_chunk.shape()[0];
    let kv_len = cache_k.shape()[0];
    let mut out = Array2::zeros((q_len, num_heads * head_dim));
    let scale = 1.0 / (head_dim as f32).sqrt();
    let kv_groups = num_heads / num_kv_heads;

    for h in 0..num_heads {
        let kv_h = h / kv_groups;
        let q_head = q_chunk.slice(ndarray::s![.., h * head_dim .. (h + 1) * head_dim]);
        let k_head = cache_k.slice(ndarray::s![.., kv_h * head_dim .. (kv_h + 1) * head_dim]);
        let v_head = cache_v.slice(ndarray::s![.., kv_h * head_dim .. (kv_h + 1) * head_dim]);
        
        let mut scores = q_head.dot(&k_head.t());
        scores.mapv_inplace(|v| v * scale);

        for i in 0..q_len {
            let mut row = scores.row_mut(i);
            let mask_threshold = (kv_len - q_len) + i;
            for j in 0..kv_len {
                if j > mask_threshold {
                    row[j] = f32::NEG_INFINITY;
                }
            }
            let max_score = row.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
            row.mapv_inplace(|v| (v - max_score).exp());
            let sum: f32 = row.sum();
            row.mapv_inplace(|v| v / sum);
        }

        let out_head = scores.dot(&v_head);
        let mut out_slice = out.slice_mut(ndarray::s![.., h * head_dim .. (h + 1) * head_dim]);
        out_slice.assign(&out_head);
    }
    
    out
}
