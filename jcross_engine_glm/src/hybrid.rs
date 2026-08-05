//! Qwen3.5 / Qwen3.6 / Ornith (`qwen35`) hybrid attention.
//!
//! Interleaves Gated DeltaNet (linear / recurrent) layers with gated full-attention
//! layers. Meta fields come from jgen_forge (GGUF `qwen35*` or HF `qwen3_5`).
//!
//! GGUF tensor contract (after forge rename):
//! - linear layers: `self_attn.query_key_value`, `self_attn.gate`,
//!   `linear_attn.{alpha,beta,a,dt.bias,conv1d,norm,out_proj}`
//! - full-attn layers: gated `q_proj` (2×heads×dim), `k/v/o_proj`, q/k norms

use ndarray::{Array1, Array2, Array3};
use serde_json::Value;

#[derive(Clone, Debug)]
pub struct HybridConfig {
    pub num_layers: usize,
    pub full_attention_interval: usize,
    /// SSM / GDN
    pub ssm_d_inner: usize,
    pub ssm_d_state: usize,
    pub ssm_n_group: usize,
    pub ssm_dt_rank: usize,
    pub ssm_d_conv: usize,
    pub rope_dim: usize,
    pub layer_types: Vec<String>, // "linear_attention" | "full_attention"
    /// False when the GDN dims came from built-in defaults rather than the
    /// sidecar. See `from_meta` — the loader refuses in that case.
    pub geometry_specified: bool,
}

impl HybridConfig {
    pub fn from_meta(meta: &Value) -> Option<Self> {
        let arch = meta
            .get("model_arch")
            .and_then(|v| v.as_str())
            .or_else(|| meta.get("hf_arch").and_then(|v| v.as_str()))
            .unwrap_or("");
        let support = meta.get("arch").and_then(|v| v.as_str()).unwrap_or("");
        let is_hybrid = support == "hybrid_ssm"
            || arch.contains("qwen35")
            || arch.contains("qwen3_5")
            || arch.contains("qwen3next")
            || arch.contains("qwen3.5")
            || arch.contains("qwen3.6");
        if !is_hybrid {
            // Also accept explicit linear_* dims (HF forge)
            let has_linear = meta.get("linear_num_value_heads").is_some()
                || meta.get("ssm_dt_rank").is_some();
            if !has_linear {
                return None;
            }
        }

        let num_layers = meta
            .get("num_layers")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as usize;
        let interval = meta
            .get("full_attention_interval")
            .and_then(|v| v.as_u64())
            .unwrap_or(4) as usize;
        let interval = interval.max(1);

        // Whether the sidecar actually specified the GDN geometry, as opposed
        // to us falling back to defaults below.
        //
        // Defaults are only safe for a model that happens to match them. A
        // Qwen3.5-0.8B converted before jgen_forge learned to emit these
        // fields loads "fine" and then dies inside layer 0 with
        // `qkv len 6144 != expected 8192` — the defaults describe a different
        // model. `is_specified` lets the caller refuse at load time instead,
        // which is the same rule the attention config already follows: never
        // run on a guess about the weights.
        let specified_keys = [
            "ssm_dt_rank", "linear_num_value_heads",
            "ssm_n_group", "linear_num_key_heads",
            "ssm_d_state", "linear_key_head_dim",
        ];
        let is_specified = specified_keys.iter().any(|k| meta.get(*k).is_some());

        let ssm_dt_rank = meta
            .get("ssm_dt_rank")
            .or_else(|| meta.get("linear_num_value_heads"))
            .and_then(|v| v.as_u64())
            .unwrap_or(32) as usize;
        let ssm_n_group = meta
            .get("ssm_n_group")
            .or_else(|| meta.get("linear_num_key_heads"))
            .and_then(|v| v.as_u64())
            .unwrap_or(16) as usize;
        let ssm_d_state = meta
            .get("ssm_d_state")
            .or_else(|| meta.get("linear_key_head_dim"))
            .and_then(|v| v.as_u64())
            .unwrap_or(128) as usize;
        let ssm_d_inner = meta
            .get("ssm_d_inner")
            .or_else(|| meta.get("linear_value_dim"))
            .and_then(|v| v.as_u64())
            .unwrap_or((ssm_dt_rank * ssm_d_state) as u64) as usize;
        let ssm_d_conv = meta
            .get("ssm_d_conv")
            .or_else(|| meta.get("linear_conv_kernel_dim"))
            .and_then(|v| v.as_u64())
            .unwrap_or(4) as usize;
        let rope_dim = meta
            .get("rope_dim")
            .or_else(|| meta.get("rope_dimension_count"))
            .and_then(|v| v.as_u64())
            .unwrap_or(64) as usize;

        let layer_types = if let Some(arr) = meta.get("layer_types").and_then(|v| v.as_array()) {
            arr.iter()
                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                .collect()
        } else {
            (0..num_layers)
                .map(|i| {
                    if (i + 1) % interval == 0 {
                        "full_attention".into()
                    } else {
                        "linear_attention".into()
                    }
                })
                .collect()
        };

        Some(Self {
            num_layers,
            full_attention_interval: interval,
            ssm_d_inner,
            ssm_d_state,
            ssm_n_group,
            ssm_dt_rank,
            ssm_d_conv,
            rope_dim,
            layer_types,
            geometry_specified: is_specified,
        })
    }

    pub fn is_linear_layer(&self, layer: usize) -> bool {
        if let Some(t) = self.layer_types.get(layer) {
            return t == "linear_attention" || t == "linear";
        }
        let iv = self.full_attention_interval.max(1);
        (layer + 1) % iv != 0
    }

    pub fn num_k_heads(&self) -> usize {
        self.ssm_n_group
    }
    pub fn num_v_heads(&self) -> usize {
        self.ssm_dt_rank
    }
    pub fn head_k_dim(&self) -> usize {
        self.ssm_d_state
    }
    pub fn head_v_dim(&self) -> usize {
        self.ssm_d_inner / self.ssm_dt_rank.max(1)
    }
    pub fn key_dim(&self) -> usize {
        self.num_k_heads() * self.head_k_dim()
    }
    pub fn value_dim(&self) -> usize {
        self.num_v_heads() * self.head_v_dim()
    }
    pub fn qkv_dim(&self) -> usize {
        self.key_dim() * 2 + self.value_dim()
    }
}

/// Per-layer recurrent + conv state for Gated DeltaNet.
pub struct HybridRuntimeState {
    /// [layer][v_heads, d_k, d_v]
    pub delta: Vec<Option<Array3<f32>>>,
    /// [layer][channels, kernel-1] previous conv inputs
    pub conv: Vec<Option<Array2<f32>>>,
}

impl HybridRuntimeState {
    pub fn new(num_layers: usize) -> Self {
        Self {
            delta: (0..num_layers).map(|_| None).collect(),
            conv: (0..num_layers).map(|_| None).collect(),
        }
    }

    pub fn clear(&mut self) {
        for s in &mut self.delta {
            *s = None;
        }
        for s in &mut self.conv {
            *s = None;
        }
    }
}

#[inline]
pub fn softplus(x: f32) -> f32 {
    if x > 20.0 {
        x
    } else {
        (1.0 + x.exp()).ln()
    }
}

#[inline]
pub fn silu(x: f32) -> f32 {
    x / (1.0 + (-x).exp())
}

pub fn l2_normalize(v: &mut [f32], eps: f32) {
    let mut s = 0.0f32;
    for &x in v.iter() {
        s += x * x;
    }
    let inv = (s + eps).sqrt().recip();
    for x in v.iter_mut() {
        *x *= inv;
    }
}

/// Depthwise causal conv1d single-token step.
/// `weight`: (channels, kernel), `state`: (channels, kernel-1) or None.
/// Returns (y, new_state).
pub fn causal_conv1d_step(
    x: &[f32],
    weight: &Array2<f32>,
    state: Option<&Array2<f32>>,
) -> (Array1<f32>, Array2<f32>) {
    let (channels, kernel) = (weight.shape()[0], weight.shape()[1]);
    assert_eq!(x.len(), channels);
    let mut window = Array2::<f32>::zeros((channels, kernel));
    if kernel > 1 {
        if let Some(st) = state {
            assert_eq!(st.shape(), &[channels, kernel - 1]);
            for c in 0..channels {
                for k in 0..(kernel - 1) {
                    window[[c, k]] = st[[c, k]];
                }
            }
        }
    }
    for c in 0..channels {
        window[[c, kernel - 1]] = x[c];
    }
    let mut y = Array1::<f32>::zeros(channels);
    for c in 0..channels {
        let mut acc = 0.0f32;
        for k in 0..kernel {
            acc += weight[[c, k]] * window[[c, k]];
        }
        y[c] = silu(acc);
    }
    let new_state = if kernel > 1 {
        window.slice(ndarray::s![.., 1..]).to_owned()
    } else {
        Array2::zeros((channels, 0))
    };
    (y, new_state)
}

/// One-token gated delta rule update.
/// state: (H, d_k, d_v); q,k: (H, d_k); v: (H, d_v); g_log, beta: (H,)
/// `g_log` is already the log-space gate (≤0); decay = exp(g_log).
pub fn gated_delta_step(
    state: &mut Array3<f32>,
    q: &Array2<f32>,
    k: &Array2<f32>,
    v: &Array2<f32>,
    g_log: &[f32],
    beta: &[f32],
) -> Array2<f32> {
    let (h, d_k, d_v) = (state.shape()[0], state.shape()[1], state.shape()[2]);
    let scale = 1.0 / (d_k as f32).sqrt();
    let mut out = Array2::<f32>::zeros((h, d_v));
    for hi in 0..h {
        let decay = g_log[hi].exp();
        // state *= decay
        for i in 0..d_k {
            for j in 0..d_v {
                state[[hi, i, j]] *= decay;
            }
        }
        // kv_mem = state @ k  → (d_v,)
        let mut kv_mem = vec![0.0f32; d_v];
        for j in 0..d_v {
            let mut acc = 0.0f32;
            for i in 0..d_k {
                acc += state[[hi, i, j]] * k[[hi, i]];
            }
            kv_mem[j] = acc;
        }
        let b = beta[hi];
        // state += k ⊗ (β (v - kv_mem))
        for i in 0..d_k {
            let ki = k[[hi, i]];
            for j in 0..d_v {
                let delta = b * (v[[hi, j]] - kv_mem[j]);
                state[[hi, i, j]] += ki * delta;
            }
        }
        // y = state @ q * scale
        for j in 0..d_v {
            let mut acc = 0.0f32;
            for i in 0..d_k {
                acc += state[[hi, i, j]] * q[[hi, i]];
            }
            out[[hi, j]] = acc * scale;
        }
    }
    out
}

/// Gated RMSNorm: RMSNorm(x) * SiLU(z), both shaped (H, d_v) flat as H*d_v.
pub fn gated_rms_norm(y: &mut [f32], z: &[f32], weight: &[f32], eps: f32) {
    let d = weight.len();
    assert_eq!(y.len() % d, 0);
    assert_eq!(y.len(), z.len());
    let n_heads = y.len() / d;
    for h in 0..n_heads {
        let base = h * d;
        let mut sum_sq = 0.0f32;
        for i in 0..d {
            let v = y[base + i];
            sum_sq += v * v;
        }
        let rms = (sum_sq / (d as f32) + eps).sqrt();
        for i in 0..d {
            let n = (y[base + i] / rms) * weight[i];
            y[base + i] = n * silu(z[base + i]);
        }
    }
}

/// Split gated Q projection: layout [head0_Q | head0_G | head1_Q | head1_G | ...]
pub fn split_gated_q(
    q_full: &[f32],
    num_heads: usize,
    head_dim: usize,
) -> (Array1<f32>, Array1<f32>) {
    let mut q = Array1::<f32>::zeros(num_heads * head_dim);
    let mut gate = Array1::<f32>::zeros(num_heads * head_dim);
    for h in 0..num_heads {
        let src = h * head_dim * 2;
        let dst = h * head_dim;
        for i in 0..head_dim {
            q[dst + i] = q_full[src + i];
            gate[dst + i] = q_full[src + head_dim + i];
        }
    }
    (q, gate)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn softplus_stable() {
        assert!((softplus(0.0) - (2.0f32).ln()).abs() < 1e-5);
        assert!(softplus(100.0) > 99.0);
    }

    #[test]
    fn gdn_step_smoke() {
        let h = 2;
        let dk = 4;
        let dv = 4;
        let mut state = Array3::<f32>::zeros((h, dk, dv));
        let q = Array2::from_shape_fn((h, dk), |(i, j)| (i + j) as f32 * 0.01);
        let k = q.clone();
        let v = Array2::from_shape_fn((h, dv), |(i, j)| (i * 2 + j) as f32 * 0.01);
        let g = vec![-0.1f32; h];
        let beta = vec![0.5f32; h];
        let out = gated_delta_step(&mut state, &q, &k, &v, &g, &beta);
        assert_eq!(out.shape(), &[h, dv]);
        assert!(state.iter().any(|&x| x.abs() > 0.0));
    }

    #[test]
    fn layer_type_interval() {
        let cfg = HybridConfig {
            num_layers: 8,
            full_attention_interval: 4,
            ssm_d_inner: 4096,
            ssm_d_state: 128,
            ssm_n_group: 16,
            ssm_dt_rank: 32,
            ssm_d_conv: 4,
            rope_dim: 64,
            layer_types: vec![],
            // Added when the loader started refusing hybrids whose sidecar does
            // not name the GDN geometry. This test builds a config directly, so
            // the geometry is specified by construction.
            geometry_specified: true,
        };
        assert!(cfg.is_linear_layer(0));
        assert!(cfg.is_linear_layer(2));
        assert!(!cfg.is_linear_layer(3));
        assert!(!cfg.is_linear_layer(7));
    }
}
