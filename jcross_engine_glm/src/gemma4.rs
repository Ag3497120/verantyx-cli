//! Gemma4 (E2B/E4B) text-tower support for JCross.
//!
//! Features (subset implemented for vector council encode/generate):
//! - Per-layer head_dim (SWA 256 vs global 512)
//! - Sliding-window causal attention
//! - Shared KV: last N layers reuse KV from last non-shared layer of same type
//! - Post-attn / pre-ffn / post-ffn RMSNorms
//! - GeLU-tanh gated MLP (not SiLU/SwiGLU)
//! - PLE residual (token lookup + context proj → per-layer gated add)
//! - Final logit softcapping helper
//!
//! Vision/audio towers are never loaded (forge lang_only).

use ndarray::{Array1, Array2, Array3};

/// Main embed scale: √hidden (Gemma4TextScaledWordEmbedding).
pub fn embed_scale(hidden: usize) -> f32 {
    (hidden as f32).sqrt()
}

/// PLE token-table scale: √(hidden_size_per_layer_input).
pub fn ple_token_scale(ple_dim: usize) -> f32 {
    (ple_dim as f32).sqrt()
}

/// Context projection scale: 1/√hidden.
pub fn ple_model_proj_scale(hidden: usize) -> f32 {
    1.0 / (hidden as f32).sqrt()
}

/// Combine scale when both token-identity and context are present: 1/√2.
pub const PLE_COMBINE_SCALE: f32 = std::f32::consts::FRAC_1_SQRT_2;

/// RMSNorm over the last axis of a [seq, layers, ple_dim] tensor.
pub fn rms_norm_ple3(x: &mut Array3<f32>, weight: &[f32], eps: f32) {
    let (seq, layers, ple_dim) = (x.shape()[0], x.shape()[1], x.shape()[2]);
    assert_eq!(weight.len(), ple_dim);
    for s in 0..seq {
        for l in 0..layers {
            let mut sum_sq = 0.0f32;
            for d in 0..ple_dim {
                let v = x[[s, l, d]];
                sum_sq += v * v;
            }
            let rms = (sum_sq / (ple_dim as f32) + eps).sqrt();
            for d in 0..ple_dim {
                x[[s, l, d]] = (x[[s, l, d]] / rms) * weight[d];
            }
        }
    }
}

#[derive(Clone, Debug)]
pub struct Gemma4Config {
    pub num_layers: usize,
    pub num_heads: usize,
    pub num_kv_heads: usize,
    pub head_dim_swa: usize,
    pub global_head_dim: usize,
    pub sliding_window: usize,
    pub num_kv_shared_layers: usize,
    pub rope_theta_swa: f32,
    pub rope_theta_full: f32,
    pub final_logit_softcapping: f32,
    pub hidden_size_per_layer_input: usize,
    pub layer_types: Vec<String>, // "sliding_attention" | "full_attention"
    pub ple_omitted: bool,
}

impl Default for Gemma4Config {
    fn default() -> Self {
        Self {
            num_layers: 0,
            num_heads: 8,
            num_kv_heads: 2,
            head_dim_swa: 256,
            global_head_dim: 512,
            sliding_window: 512,
            num_kv_shared_layers: 0,
            rope_theta_swa: 10000.0,
            rope_theta_full: 1_000_000.0,
            final_logit_softcapping: 30.0,
            hidden_size_per_layer_input: 256,
            layer_types: Vec::new(),
            ple_omitted: true,
        }
    }
}

impl Gemma4Config {
    pub fn from_meta(meta: &serde_json::Value) -> Option<Self> {
        let arch = meta
            .get("model_arch")
            .and_then(|v| v.as_str())
            .or_else(|| meta.get("hf_arch").and_then(|v| v.as_str()));
        let is_g4 = match arch {
            Some(a) => a == "gemma4" || a.contains("gemma4"),
            None => false,
        };
        if !is_g4 {
            return None;
        }
        let layer_types: Vec<String> = meta
            .get("layer_types")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        Some(Self {
            num_layers: meta
                .get("num_layers")
                .and_then(|v| v.as_u64())
                .unwrap_or(layer_types.len() as u64) as usize,
            num_heads: meta.get("num_heads").and_then(|v| v.as_u64()).unwrap_or(8) as usize,
            num_kv_heads: meta
                .get("num_kv_heads")
                .and_then(|v| v.as_u64())
                .unwrap_or(2) as usize,
            head_dim_swa: meta
                .get("head_dim_swa")
                .or_else(|| meta.get("head_dim"))
                .and_then(|v| v.as_u64())
                .unwrap_or(256) as usize,
            global_head_dim: meta
                .get("global_head_dim")
                .and_then(|v| v.as_u64())
                .unwrap_or(512) as usize,
            sliding_window: meta
                .get("sliding_window")
                .and_then(|v| v.as_u64())
                .unwrap_or(512) as usize,
            num_kv_shared_layers: meta
                .get("num_kv_shared_layers")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as usize,
            rope_theta_swa: meta
                .get("rope_theta_swa")
                .or_else(|| meta.get("rope_theta"))
                .and_then(|v| v.as_f64())
                .unwrap_or(10000.0) as f32,
            rope_theta_full: meta
                .get("rope_theta_full")
                .and_then(|v| v.as_f64())
                .unwrap_or(1_000_000.0) as f32,
            final_logit_softcapping: meta
                .get("final_logit_softcapping")
                .and_then(|v| v.as_f64())
                .unwrap_or(30.0) as f32,
            hidden_size_per_layer_input: meta
                .get("hidden_size_per_layer_input")
                .and_then(|v| v.as_u64())
                .unwrap_or(256) as usize,
            layer_types,
            ple_omitted: meta
                .get("ple_omitted")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        })
    }

    pub fn is_sliding(&self, layer: usize) -> bool {
        match self.layer_types.get(layer).map(|s| s.as_str()) {
            Some("full_attention") => false,
            Some("sliding_attention") => true,
            _ => ((layer + 1) % 6) != 0,
        }
    }

    pub fn head_dim(&self, layer: usize) -> usize {
        if self.is_sliding(layer) {
            self.head_dim_swa
        } else {
            self.global_head_dim
        }
    }

    pub fn rope_theta(&self, layer: usize) -> f32 {
        if self.is_sliding(layer) {
            self.rope_theta_swa
        } else {
            self.rope_theta_full
        }
    }

    /// Layers with index >= this compute their own KV; later shared layers reuse.
    pub fn kv_compute_end(&self) -> usize {
        self.num_layers.saturating_sub(self.num_kv_shared_layers)
    }

    pub fn computes_kv(&self, layer: usize) -> bool {
        layer < self.kv_compute_end()
    }

    /// Source layer whose KV cache a shared layer should read.
    pub fn kv_source_layer(&self, layer: usize) -> usize {
        if self.computes_kv(layer) {
            return layer;
        }
        // Reuse last non-shared layer of the same attention type
        let want_slide = self.is_sliding(layer);
        let end = self.kv_compute_end();
        let mut src = end.saturating_sub(1);
        for i in (0..end).rev() {
            if self.is_sliding(i) == want_slide {
                src = i;
                break;
            }
        }
        src
    }
}

/// GeLU approximation used by Gemma (tanh variant).
pub fn gelu_pytorch_tanh(x: f32) -> f32 {
    const SQRT_2_OVER_PI: f32 = 0.7978845608; // sqrt(2/pi)
    const COEFF: f32 = 0.044715;
    let inner = SQRT_2_OVER_PI * (x + COEFF * x * x * x);
    0.5 * x * (1.0 + inner.tanh())
}

pub fn apply_geglu(gate: &mut [f32], up: &[f32]) {
    assert_eq!(gate.len(), up.len());
    for i in 0..gate.len() {
        gate[i] = gelu_pytorch_tanh(gate[i]) * up[i];
    }
}

/// Softcap logits: softcap * tanh(logits / softcap)
pub fn softcap_logits(logits: &mut [f32], softcap: f32) {
    if softcap <= 0.0 {
        return;
    }
    for x in logits.iter_mut() {
        *x = softcap * (*x / softcap).tanh();
    }
}

/// Chunked SDPA with optional sliding window (in addition to causal mask).
pub fn sdpa_chunked_windowed(
    q: &Array2<f32>,
    k_cache: &Array2<f32>,
    v_cache: &Array2<f32>,
    num_heads: usize,
    num_kv_heads: usize,
    head_dim: usize,
    window: Option<usize>,
) -> Array2<f32> {
    let b = q.shape()[0];
    let seq_len = k_cache.shape()[0];
    let mut out = Array2::<f32>::zeros((b, num_heads * head_dim));
    let scale = (head_dim as f32).sqrt();
    let num_queries_per_kv = num_heads / num_kv_heads.max(1);

    for token_idx in 0..b {
        let q_token = q.row(token_idx);
        let q_slice = q_token.as_slice().unwrap();
        let visible_end = seq_len - b + token_idx + 1;
        let visible_start = match window {
            Some(w) if w > 0 => visible_end.saturating_sub(w),
            _ => 0,
        };

        for h in 0..num_heads {
            let span = visible_end - visible_start;
            let mut scores = vec![0.0; span];
            let q_head = &q_slice[h * head_dim..(h + 1) * head_dim];
            let kv_group = h / num_queries_per_kv;

            for (si, pos) in (visible_start..visible_end).enumerate() {
                let k_pos = k_cache.row(pos);
                let k_head = &k_pos.as_slice().unwrap()
                    [kv_group * head_dim..(kv_group + 1) * head_dim];
                let mut dot = 0.0;
                for i in 0..head_dim {
                    dot += q_head[i] * k_head[i];
                }
                scores[si] = dot / scale;
            }

            let mut max_score = f32::NEG_INFINITY;
            for &s in &scores {
                if s > max_score {
                    max_score = s;
                }
            }
            let mut exp_sum = 0.0;
            for s in &mut scores {
                *s = (*s - max_score).exp();
                exp_sum += *s;
            }
            for s in &mut scores {
                *s /= exp_sum.max(1e-12);
            }

            let mut out_head = vec![0.0; head_dim];
            for (si, pos) in (visible_start..visible_end).enumerate() {
                let v_pos = v_cache.row(pos);
                let v_head = &v_pos.as_slice().unwrap()
                    [kv_group * head_dim..(kv_group + 1) * head_dim];
                for i in 0..head_dim {
                    out_head[i] += scores[si] * v_head[i];
                }
            }
            for i in 0..head_dim {
                out[[token_idx, h * head_dim + i]] = out_head[i];
            }
        }
    }
    out
}

/// Single-token SDPA with window (decode path).
pub fn sdpa_gqa_windowed(
    q: &Array1<f32>,
    k_cache: &Array2<f32>,
    v_cache: &Array2<f32>,
    num_heads: usize,
    num_kv_heads: usize,
    head_dim: usize,
    window: Option<usize>,
) -> Array1<f32> {
    let q2 = q.clone().into_shape((1, q.len())).unwrap();
    let out2 = sdpa_chunked_windowed(
        &q2, k_cache, v_cache, num_heads, num_kv_heads, head_dim, window,
    );
    out2.row(0).to_owned()
}
