use memmap2::{Mmap, MmapOptions};
use std::collections::HashMap;
use std::fs::File;
use std::io;
use std::path::Path;
#[cfg(feature = "metal")]
extern crate blas_src;
use ndarray::{ArrayView2, ArrayView1, Array1};
use half::f16;
use candle_core::{Device, Tensor, DType};

mod generation;
mod tokenizer_ffi;
mod gpu_ops;
mod puzzle_math;
mod gemma4;
pub mod prefetch;

#[derive(Debug)]
pub enum TensorType {
    SVDLossless { rows: u32, cols: u32, rank: u32 },
    Dense2D { rows: u32, cols: u32 },
    Dense1D { length: u32 },
}

#[derive(Debug)]
pub struct JCrossTensorMeta {
    pub tensor_type: TensorType,
    pub offset: usize,
    pub byte_length: usize,
}

use crate::generation::{sdpa_gqa, apply_rope_glm, apply_rope_chunked_glm, apply_rope_neox, apply_rope_chunked_neox, sdpa_chunked, AttentionState, swiglu};
use crate::gemma4::{
    Gemma4Config, PLE_COMBINE_SCALE, apply_geglu, embed_scale as gemma4_embed_scale,
    gelu_pytorch_tanh, ple_model_proj_scale, ple_token_scale, rms_norm_ple3,
    sdpa_chunked_windowed, sdpa_gqa_windowed, softcap_logits,
};


pub struct MetalAttentionState {
    pub k_cache: Vec<Option<candle_core::Tensor>>,
    pub v_cache: Vec<Option<candle_core::Tensor>>,
}
impl MetalAttentionState {
    pub fn new(num_layers: usize) -> Self {
        let mut k = Vec::with_capacity(num_layers);
        let mut v = Vec::with_capacity(num_layers);
        for _ in 0..num_layers {
            k.push(None);
            v.push(None);
        }
        Self { k_cache: k, v_cache: v }
    }
    
    pub fn append_kv(&mut self, layer: usize, new_k: candle_core::Tensor, new_v: candle_core::Tensor) -> Result<(), candle_core::Error> {
        if let Some(existing) = self.k_cache[layer].as_ref() {
            self.k_cache[layer] = Some(candle_core::Tensor::cat(&[existing, &new_k], 0)?);
            self.v_cache[layer] = Some(candle_core::Tensor::cat(&[self.v_cache[layer].as_ref().unwrap(), &new_v], 0)?);
        } else {
            self.k_cache[layer] = Some(new_k);
            self.v_cache[layer] = Some(new_v);
        }
        Ok(())
    }

    pub fn sync_from_cpu(&mut self, cpu_cache: &AttentionState, device: &candle_core::Device) -> Result<(), candle_core::Error> {
        let num_layers = cpu_cache.k_cache.len();
        
        for layer in 0..num_layers {
            let arr_k = &cpu_cache.k_cache[layer];
            let arr_v = &cpu_cache.v_cache[layer];
            let seq_len = arr_k.shape()[0];
            
            if seq_len == 0 {
                continue;
            }
            
            let dim = arr_k.shape()[1]; // num_kv_heads * head_dim
            let mut vec_k = Vec::with_capacity(seq_len * dim);
            for x in arr_k.iter() {
                vec_k.push(*x);
            }
            let mut vec_v = Vec::with_capacity(seq_len * dim);
            for x in arr_v.iter() {
                vec_v.push(*x);
            }
            
            let tensor_k = candle_core::Tensor::from_vec(vec_k, (seq_len, dim), device)?;
            let tensor_v = candle_core::Tensor::from_vec(vec_v, (seq_len, dim), device)?;
            self.k_cache[layer] = Some(tensor_k);
            self.v_cache[layer] = Some(tensor_v);
        }
        Ok(())
    }
}

pub struct JCrossEngine {
    mmap: Mmap,
    pub tensors: HashMap<String, JCrossTensorMeta>,
    pub candle_tensors: HashMap<String, Tensor>,
    pub candle_device: Device,
    pub kv_cache: std::cell::RefCell<Option<AttentionState>>,
    pub metal_kv_cache: std::cell::RefCell<Option<MetalAttentionState>>,
    pub prefetch_cache: std::cell::RefCell<HashMap<usize, Vec<usize>>>,
    pub expert_usage_stats: std::cell::RefCell<HashMap<usize, u64>>,
    pub l1_cache: std::cell::RefCell<HashMap<String, Vec<u8>>>,
    pub cpu_tensors_f32: std::cell::RefCell<HashMap<String, ndarray::Array2<f32>>>,
    pub cpu_vectors_f32: std::cell::RefCell<HashMap<String, ndarray::Array1<f32>>>,
    /// GPU (Metal/CUDA) composed weights: name -> (W^T (in,out) f32, optional bias (out)).
    /// SVDLossless tensors are composed once (U·C·diag(S)·V·diag(mod_x)) and cached.
    pub gpu_weight_cache: std::cell::RefCell<HashMap<String, (Tensor, Option<Tensor>)>>,
    /// FIFO order + byte accounting for gpu_weight_cache eviction (OOM protection).
    pub gpu_cache_order: std::cell::RefCell<Vec<String>>,
    pub gpu_cache_bytes: std::cell::RefCell<usize>,
    /// Byte accounting for cpu_tensors_f32/cpu_vectors_f32 (cleared wholesale when over budget).
    pub cpu_cache_bytes: std::cell::RefCell<usize>,
    /// Weight-cache budget in bytes (env JCROSS_CACHE_GB, default 8 GB).
    /// Composed-f32 caches for big models (9B = ~36 GB) must not grow unbounded.
    pub cache_budget_bytes: usize,
    /// GPU KV cache: per layer (K, V) tensors of shape (t, kv_heads*head_dim) f32.
    pub gpu_kv: std::cell::RefCell<Vec<(Option<Tensor>, Option<Tensor>)>>,
    pub num_layers: usize,
    pub num_heads: usize,
    pub num_kv_heads: usize,
    pub head_dim: usize,
    pub rope_theta: f32,
    /// true = NeoX/rotate-half RoPE (Qwen/Gemma), false = interleaved GLM RoPE
    pub rope_neox: bool,
    /// Generation stop tokens (default: Qwen <|endoftext|>/<|im_end|>). Overridable via .meta.json
    pub eos_tokens: Vec<u32>,
    /// MoE config (meta.json driven). Defaults preserve GLM-5.2 behaviour.
    pub moe_top_k: usize,
    /// true = softmax over top-k router logits (Qwen-MoE), false = sigmoid+normalize (GLM/DeepSeek)
    pub moe_softmax: bool,
    /// Layers below this index use the dense MLP fallback (first_k_dense_replace)
    pub first_moe_layer: usize,
    /// Gemma4 text-tower config (None = not a gemma4 model)
    pub gemma4: Option<Gemma4Config>,
}

impl JCrossEngine {

    /// 利用可能な最速デバイスを実行時に選ぶ: CUDA (Windows/Linux) -> Metal (macOS) -> CPU。
    /// JCROSS_DEVICE=cpu|cuda|metal で強制指定も可能。
    pub fn pick_device() -> Device {
        match std::env::var("JCROSS_DEVICE").as_deref() {
            Ok("cpu") => return Device::Cpu,
            #[cfg(feature = "cuda")]
            Ok("cuda") => return Device::new_cuda(0).unwrap_or(Device::Cpu),
            #[cfg(feature = "metal")]
            Ok("metal") => return Device::new_metal(0).unwrap_or(Device::Cpu),
            _ => {}
        }
        #[cfg(feature = "cuda")]
        if let Ok(d) = Device::new_cuda(0) {
            return d;
        }
        #[cfg(feature = "metal")]
        if let Ok(d) = Device::new_metal(0) {
            return d;
        }
        Device::Cpu
    }

    pub fn get_candle_tensor(&self, name: &str, device: &Device) -> Result<Tensor, String> {
        // Check VRAM L0 Cache (Adaptive Pinning)
        if let Some(pinned_tensor) = self.candle_tensors.get(name) {
            return Ok(pinned_tensor.clone());
        }

        if let Some(meta) = self.tensors.get(name) {
            let raw_data = self.get_raw_slice(name).ok_or_else(|| "Could not read tensor data".to_string())?;
            let f16_slice = unsafe {
                std::slice::from_raw_parts(raw_data.as_ptr() as *const half::f16, meta.byte_length / 2)
            };
            match meta.tensor_type {
                TensorType::Dense2D { rows, cols } => {
                    return Tensor::from_slice(f16_slice, (rows as usize, cols as usize), device).map_err(|e| e.to_string());
                },
                TensorType::Dense1D { length } => {
                    return Tensor::from_slice(f16_slice, (length as usize,), device).map_err(|e| e.to_string());
                },
                _ => return Err(format!("Cannot load base tensor for SVD directly without suffix: {}", name)),
            }
        }
        
        if name.ends_with(".V") || name.ends_with(".S") || name.ends_with(".U") || name.ends_with(".mod_x") || name.ends_with(".mod_y") || name.ends_with(".c_valve") {
            let parts: Vec<&str> = name.rsplitn(2, '.').collect();
            if parts.len() == 2 {
                let base_name = parts[1];
                let suffix = parts[0];
                if let Some(meta) = self.tensors.get(base_name) {
                    if let TensorType::SVDLossless { rows, cols, rank } = meta.tensor_type {
                        let r = rank as usize;
                        let m = rows as usize;
                        let n = cols as usize;
                        
                        let start = meta.offset;
                        let raw_data = &self.mmap[start..start + meta.byte_length];
                        let f16_slice = unsafe {
                            std::slice::from_raw_parts(raw_data.as_ptr() as *const half::f16, meta.byte_length / 2)
                        };
                        
                        // JGEN v3 layout (see build_ornith_jgen.py): U (m,r), S (r), V (n,r), mod_x (n), mod_y (m), c_valve (r,r)
                        let u_len = m * r;
                        let s_len = r;
                        let v_len = n * r;
                        let mod_x_len = n;
                        let mod_y_len = m;
                        let c_valve_len = r * r;
                        
                        return match suffix {
                            "U" => Tensor::from_slice(&f16_slice[0..u_len], (m, r), device).map_err(|e| e.to_string()),
                            "S" => Tensor::from_slice(&f16_slice[u_len..u_len+s_len], (r,), device).map_err(|e| e.to_string()),
                            // Stored as V^T transposed (n, r); callers expect (r, n) for V^T @ x
                            "V" => Tensor::from_slice(&f16_slice[u_len+s_len..u_len+s_len+v_len], (n, r), device)
                                .and_then(|t| t.t()?.contiguous())
                                .map_err(|e| e.to_string()),
                            "mod_x" => Tensor::from_slice(&f16_slice[u_len+s_len+v_len..u_len+s_len+v_len+mod_x_len], (n,), device).map_err(|e| e.to_string()),
                            "mod_y" => Tensor::from_slice(&f16_slice[u_len+s_len+v_len+mod_x_len..u_len+s_len+v_len+mod_x_len+mod_y_len], (m,), device).map_err(|e| e.to_string()),
                            "c_valve" => Tensor::from_slice(&f16_slice[u_len+s_len+v_len+mod_x_len+mod_y_len..u_len+s_len+v_len+mod_x_len+mod_y_len+c_valve_len], (r, r), device).map_err(|e| e.to_string()),
                            _ => Err(format!("Unknown suffix: {}", suffix)),
                        };
                    }
                }
            }
        }
        
        Err(format!("Tensor missing (Streaming VRAM): {}", name))
    }

    /// Loads and pins specific experts into VRAM statically based on the user's selected domain.
    pub fn pin_domain_experts(&mut self, active_experts: &[usize]) -> Result<(), String> {
        let num_layers = self.kv_cache.borrow().as_ref().map(|c| c.k_cache.len()).unwrap_or(60);
        let mut pinned_count = 0;
        
        // 1. Pin Core Tensors (Attention, Shared Experts)
        let core_prefixes = vec!["self_attn", "mlp.shared", "input_layernorm", "post_attention_layernorm", "embed", "norm"];
        let mut tensors_to_pin = Vec::new();
        
        for name in self.tensors.keys() {
            let is_core = core_prefixes.iter().any(|&p| name.contains(p));
            let mut is_active_expert = false;
            
            if name.contains("mlp.experts") {
                for &expert_idx in active_experts {
                    let expert_prefix = format!(".experts.{}.", expert_idx);
                    if name.contains(&expert_prefix) {
                        is_active_expert = true;
                        break;
                    }
                }
            }
            
            if is_core || is_active_expert {
                tensors_to_pin.push(name.clone());
            }
        }

        // 2. Load and Pin
        for name in tensors_to_pin {
            // We use get_candle_tensor which will read from mmap and load onto VRAM
            let tensor = self.get_candle_tensor(&name, &self.candle_device)?;
            self.candle_tensors.insert(name, tensor);
            pinned_count += 1;
        }
        
        println!("[Adaptive Pinning] Successfully pinned {} tensors into VRAM.", pinned_count);
        Ok(())
    }

    /// Zero-copy mmap loader for the JGEN binary format.
    /// This is NOT a mock. It strictly parses the binary layout defined by `jcross_build_lossless_9b.py`.
    pub fn load_jgen<P: AsRef<Path>>(path: P) -> io::Result<Self> {
        let aux_path = format!("{}.aux", path.as_ref().display());
        let meta_path = format!("{}.meta.json", path.as_ref().display());
        let file = File::open(path)?;
        let mmap = unsafe { MmapOptions::new().map(&file)? };

        if mmap.len() < 12 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "File too small to be JGEN"));
        }

        let magic = &mmap[0..4];
        if magic != b"JGEN" {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Invalid magic bytes"));
        }

        let version = u32::from_le_bytes(mmap[4..8].try_into().unwrap());
        let mut tensors = HashMap::new();
        let mut offset = 8;
        let mut version_3_count = 0;
        let total_tensors = if version == 3 {
            let t = u32::from_le_bytes(mmap[8..12].try_into().unwrap());
            offset = 12;
            t
        } else if version == 1 {
            0
        } else {
            return Err(io::Error::new(io::ErrorKind::InvalidData, format!("Unsupported JGEN version: {}", version)));
        };

        while offset < mmap.len() {
            if version == 3 && version_3_count >= total_tensors {
                break;
            }
            version_3_count += 1;

            let name_len = if version == 3 {
                let l = u16::from_le_bytes(mmap[offset..offset+2].try_into().unwrap()) as usize;
                offset += 2;
                l
            } else {
                let l = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap()) as usize;
                offset += 4;
                l
            };

            let name = String::from_utf8(mmap[offset..offset+name_len].to_vec())
                .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "Invalid UTF-8 in tensor name"))?;
            offset += name_len;

            let t_type = if version == 3 {
                let t = mmap[offset] as u32;
                offset += 1;
                t
            } else {
                let t = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap());
                offset += 4;
                t
            };

            match t_type {
                1 => { // SVDLossless
                    let rows = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap());
                    let cols = u32::from_le_bytes(mmap[offset+4..offset+8].try_into().unwrap());
                    let rank = u32::from_le_bytes(mmap[offset+8..offset+12].try_into().unwrap());
                    offset += 12;

                    // Cast before multiply — u32 overflow on large ranks/dims
                    let (r, c, k) = (rows as usize, cols as usize, rank as usize);
                    let u_len = r * k * 2;
                    let s_len = k * 2;
                    let v_len = c * k * 2;
                    let mod_x_len = c * 2;
                    let mod_y_len = r * 2;
                    let c_valve_len = k * k * 2;

                    let total_bytes = u_len + s_len + v_len + mod_x_len + mod_y_len + c_valve_len;

                    tensors.insert(name, JCrossTensorMeta {
                        tensor_type: TensorType::SVDLossless { rows, cols, rank },
                        offset,
                        byte_length: total_bytes,
                    });
                    offset += total_bytes;
                },
                2 => { // Dense2D
                    let rows = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap());
                    let cols = u32::from_le_bytes(mmap[offset+4..offset+8].try_into().unwrap());
                    offset += 8;

                    // Critical: rows*cols*2 can exceed u32 (e.g. gemma4 PLE 262144×10752×2)
                    let total_bytes = (rows as usize) * (cols as usize) * 2;
                    tensors.insert(name, JCrossTensorMeta {
                        tensor_type: TensorType::Dense2D { rows, cols },
                        offset,
                        byte_length: total_bytes,
                    });
                    offset += total_bytes;
                },
                3 => { // Dense1D
                    let length = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap());
                    offset += 4;

                    let total_bytes = (length as usize) * 2;
                    tensors.insert(name, JCrossTensorMeta {
                        tensor_type: TensorType::Dense1D { length },
                        offset,
                        byte_length: total_bytes,
                    });
                    offset += total_bytes;
                },
                _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "Unknown tensor type")),
            }
        }

        // CUDA -> Metal -> CPU の順に実行時フォールバック (ビルド時 feature で有効化)
        let candle_device = Self::pick_device();
        println!("[JCross] Initializing GPU Device: {:?}", candle_device);
        let mut candle_tensors = HashMap::new();
        
        for name in tensors.keys() {
            if name.contains("layers.3.mlp") {
                println!("[JCross DEBUG] Found layer 3 tensor: {}", name);
            }
        }
        // Dynamic configuration extraction
        let mut max_layer = 0;
        for name in tensors.keys() {
            if name.contains(".layers.") {
                if let Some(start_idx) = name.find(".layers.") {
                    let sub = &name[start_idx + 8..];
                    if let Some(end_idx) = sub.find('.') {
                        if let Ok(layer_idx) = sub[..end_idx].parse::<usize>() {
                            if layer_idx > max_layer {
                                max_layer = layer_idx;
                            }
                        }
                    }
                }
            }
        }
        let mut num_layers = if max_layer > 0 { max_layer + 1 } else { 79 };

        let embed_meta = tensors.get("model.language_model.embed_tokens.weight")
            .or_else(|| tensors.get("model.embed_tokens.weight"))
            .or_else(|| tensors.get("embed_tokens"));
            
        let hidden_dim = match embed_meta {
            Some(meta) => match meta.tensor_type {
                TensorType::Dense2D { cols, .. } => cols as usize,
                _ => 1024,
            },
            None => 1024,
        };

        let q_proj_name = format!("model.layers.0.self_attn.q_proj.weight");
        let q_proj_meta = tensors.get(&q_proj_name)
            .or_else(|| tensors.get("model.language_model.layers.0.self_attn.q_proj.weight"));
            
        let attention_dim = match q_proj_meta {
            Some(meta) => match meta.tensor_type {
                TensorType::SVDLossless { cols, .. } => cols as usize,
                TensorType::Dense2D { cols, .. } => cols as usize,
                _ => hidden_dim,
            },
            None => hidden_dim,
        };

        let (mut num_heads, mut num_kv_heads, mut head_dim, mut rope_theta, mut rope_neox) = match attention_dim {
            1024 => (16, 16, 64, 10000.0, true), // Qwen1.5-0.5B
            896 => (14, 2, 64, 10000.0, true),   // Qwen2.5-0.5B
            3584 => (16, 8, 256, 10000.0, true), // Gemma-2-9B (attention dim=3584)
            4096 => (32, 8, 128, 10000.0, true), // Gemma-2-9B (alternative / fallback)
            1536 => (12, 2, 128, 10000.0, true), // Qwen 2.5-1.5B
            _ => (64, 64, 64, 8000000.0, false), // GLM-5.2
        };

        // Optional sidecar config (<model>.meta.json) written by jgen_forge.py.
        // Overrides the heuristic table above so any converted model gets exact settings.
        let mut eos_tokens: Vec<u32> = vec![151643, 151645]; // Qwen defaults
        let mut moe_top_k = 8usize;          // GLM-5.2 default
        let mut moe_softmax = false;         // GLM/DeepSeek sigmoid scoring default
        let mut first_moe_layer = 3usize;    // GLM-5.2 first_k_dense_replace
        let mut gemma4_cfg: Option<Gemma4Config> = None;
        if let Ok(meta_str) = std::fs::read_to_string(&meta_path) {
            if let Ok(meta) = serde_json::from_str::<serde_json::Value>(&meta_str) {
                if let Some(v) = meta.get("num_heads").and_then(|v| v.as_u64()) { num_heads = v as usize; }
                if let Some(v) = meta.get("num_kv_heads").and_then(|v| v.as_u64()) { num_kv_heads = v as usize; }
                if let Some(v) = meta.get("head_dim").and_then(|v| v.as_u64()) { head_dim = v as usize; }
                if let Some(v) = meta.get("rope_theta").and_then(|v| v.as_f64()) { rope_theta = v as f32; }
                if let Some(v) = meta.get("rope_neox").and_then(|v| v.as_bool()) { rope_neox = v; }
                if let Some(arr) = meta.get("eos_tokens").and_then(|v| v.as_array()) {
                    let toks: Vec<u32> = arr.iter().filter_map(|v| v.as_u64().map(|t| t as u32)).collect();
                    if !toks.is_empty() { eos_tokens = toks; }
                }
                if let Some(v) = meta.get("moe_top_k").and_then(|v| v.as_u64()) { moe_top_k = v as usize; }
                if let Some(v) = meta.get("moe_score_func").and_then(|v| v.as_str()) { moe_softmax = v == "softmax"; }
                if let Some(v) = meta.get("first_moe_layer").and_then(|v| v.as_u64()) { first_moe_layer = v as usize; }
                gemma4_cfg = Gemma4Config::from_meta(&meta);
                if let Some(ref g4) = gemma4_cfg {
                    // Prefer meta num_layers for gemma4 (tensor scan can include vision leftovers)
                    if g4.num_layers > 0 { num_layers = g4.num_layers; }
                    num_heads = g4.num_heads;
                    num_kv_heads = g4.num_kv_heads;
                    head_dim = g4.head_dim_swa;
                    rope_theta = g4.rope_theta_swa;
                    rope_neox = true;
                    println!("[JCross] Gemma4 mode: layers={} swa_hd={} global_hd={} window={} shared_kv={} ple_omitted={}",
                        g4.num_layers, g4.head_dim_swa, g4.global_head_dim, g4.sliding_window,
                        g4.num_kv_shared_layers, g4.ple_omitted);
                }
                println!("[JCross] Applied sidecar config from {}", meta_path);
            }
        }

        println!("[JCross] Detected Model Config: num_layers={}, hidden_dim={}, num_heads={}, num_kv_heads={}, head_dim={}, rope_theta={}", 
            num_layers, hidden_dim, num_heads, num_kv_heads, head_dim, rope_theta);

        // Optional sidecar file (<model>.aux, same JGEN v3 layout) for tensors missing from
        // the main file (e.g. Qwen q/k/v attention biases). Loaded fully into the L1 RAM cache.
        let mut aux_l1: HashMap<String, Vec<u8>> = HashMap::new();
        if let Ok(aux_bytes) = std::fs::read(&aux_path) {
            if aux_bytes.len() > 12 && &aux_bytes[0..4] == b"JGEN" {
                let aux_total = u32::from_le_bytes(aux_bytes[8..12].try_into().unwrap());
                let mut off = 12usize;
                for _ in 0..aux_total {
                    let name_len = u16::from_le_bytes(aux_bytes[off..off+2].try_into().unwrap()) as usize;
                    off += 2;
                    let name = String::from_utf8_lossy(&aux_bytes[off..off+name_len]).to_string();
                    off += name_len;
                    let t = aux_bytes[off];
                    off += 1;
                    let (tensor_type, nbytes) = match t {
                        2 => {
                            let rows = u32::from_le_bytes(aux_bytes[off..off+4].try_into().unwrap());
                            let cols = u32::from_le_bytes(aux_bytes[off+4..off+8].try_into().unwrap());
                            off += 8;
                            (TensorType::Dense2D { rows, cols }, (rows as usize) * (cols as usize) * 2)
                        },
                        3 => {
                            let length = u32::from_le_bytes(aux_bytes[off..off+4].try_into().unwrap());
                            off += 4;
                            (TensorType::Dense1D { length }, (length as usize) * 2)
                        },
                        _ => break,
                    };
                    aux_l1.insert(name.clone(), aux_bytes[off..off+nbytes].to_vec());
                    // offset points into the aux file, never dereferenced against the main mmap
                    // because get_raw_slice/get_candle_tensor hit the L1 cache first.
                    tensors.insert(name, JCrossTensorMeta { tensor_type, offset: 0, byte_length: nbytes });
                    off += nbytes;
                }
                println!("[JCross] Loaded {} auxiliary tensors from {}", aux_l1.len(), aux_path);
            }
        }

        Ok(JCrossEngine { 
            mmap, 
            tensors, 
            candle_tensors, 
            candle_device, 
            kv_cache: std::cell::RefCell::new(None), 
            metal_kv_cache: std::cell::RefCell::new(None), 
            prefetch_cache: std::cell::RefCell::new(HashMap::new()),
            expert_usage_stats: std::cell::RefCell::new(HashMap::new()),
            l1_cache: std::cell::RefCell::new(aux_l1),
            cpu_tensors_f32: std::cell::RefCell::new(HashMap::new()),
            cpu_vectors_f32: std::cell::RefCell::new(HashMap::new()),
            gpu_weight_cache: std::cell::RefCell::new(HashMap::new()),
            gpu_cache_order: std::cell::RefCell::new(Vec::new()),
            gpu_cache_bytes: std::cell::RefCell::new(0),
            cpu_cache_bytes: std::cell::RefCell::new(0),
            cache_budget_bytes: std::env::var("JCROSS_CACHE_GB")
                .ok().and_then(|v| v.parse::<f64>().ok())
                .map(|g| (g * 1e9) as usize)
                .unwrap_or(8_000_000_000),
            gpu_kv: std::cell::RefCell::new(vec![(None, None); num_layers]),
            num_layers,
            num_heads,
            num_kv_heads,
            head_dim,
            rope_theta,
            rope_neox,
            eos_tokens,
            moe_top_k,
            moe_softmax,
            first_moe_layer,
            gemma4: gemma4_cfg,
        })
    }

    /// Fetches a raw slice of memory for a given tensor. Zero copy from L1 or mmap.
    pub fn get_raw_slice<'a>(&'a self, name: &str) -> Option<std::borrow::Cow<'a, [u8]>> {
        if let Some(meta) = self.tensors.get(name) {
            // Check L1 cache first (Hot experts)
            if let Ok(l1) = self.l1_cache.try_borrow() {
                if let Some(cached_data) = l1.get(name) {
                    return Some(std::borrow::Cow::Owned(cached_data.clone()));
                }
            }
            // Fallback to L2 mmap (Zero-delay load)
            Some(std::borrow::Cow::Borrowed(&self.mmap[meta.offset..meta.offset + meta.byte_length]))
        } else {
            None
        }
    }

    /// Records usage of a specific expert and optionally promotes it if hot
    pub fn record_expert_usage(&self, layer: usize, expert_idx: usize) {
        if let Ok(mut stats) = self.expert_usage_stats.try_borrow_mut() {
            let count = stats.entry(layer * 1000 + expert_idx).or_insert(0);
            *count += 1;
        }
    }

    /// Promotes hot experts from L2 (mmap) to L1 (RAM)
    pub fn promote_hot_experts(&self, threshold: u64) {
        if let (Ok(stats), Ok(mut l1)) = (self.expert_usage_stats.try_borrow(), self.l1_cache.try_borrow_mut()) {
            for (&id, &count) in stats.iter() {
                if count >= threshold {
                    let layer = id / 1000;
                    let expert_idx = id % 1000;
                    let names = [
                        format!("model.layers.{}.mlp.experts.{}.gate_proj.weight", layer, expert_idx),
                        format!("model.layers.{}.mlp.experts.{}.up_proj.weight", layer, expert_idx),
                        format!("model.layers.{}.mlp.experts.{}.down_proj.weight", layer, expert_idx),
                    ];
                    
                    for name in names.iter() {
                        if !l1.contains_key(name) {
                            if let Some(meta) = self.tensors.get(name) {
                                let data = self.mmap[meta.offset..meta.offset + meta.byte_length].to_vec();
                                l1.insert(name.clone(), data);
                                println!("[Profiler] Expert (Layer {}, ID {}) promoted to L1 Cache! ({})", layer, expert_idx, name);
                            }
                        }
                    }
                }
            }
        }
    }

    /// Saves the current expert usage stats to a JSON profile
    pub fn save_profile(&self, path: &str) {
        if let Ok(stats) = self.expert_usage_stats.try_borrow() {
            let mut json = String::from("{\n");
            let mut i = 0;
            let len = stats.len();
            for (&id, &count) in stats.iter() {
                json.push_str(&format!("  \"{}\": {}", id, count));
                if i < len - 1 {
                    json.push(',');
                }
                json.push('\n');
                i += 1;
            }
            json.push_str("}\n");
            let _ = std::fs::write(path, json);
        }
    }

    /// Loads expert usage stats from a JSON profile
    pub fn load_profile(&self, path: &str) {
        if let Ok(json) = std::fs::read_to_string(path) {
            if let Ok(mut stats) = self.expert_usage_stats.try_borrow_mut() {
                for line in json.lines() {
                    if line.contains(':') {
                        let parts: Vec<&str> = line.split(':').collect();
                        if parts.len() == 2 {
                            let key_str = parts[0].trim().trim_matches('"');
                            let val_str = parts[1].trim().trim_matches(',').trim();
                            if let (Ok(id), Ok(count)) = (key_str.parse::<usize>(), val_str.parse::<u64>()) {
                                stats.insert(id, count);
                            }
                        }
                    }
                }
            }
        }
    }

    /// Performs the mathematical Subspace Projection (Cascading Lock).
    /// This is NOT random noise (`torch.randn`). This performs the actual linear algebra:
    /// y = U * S * (V^T * (x * mod_x)) + mod_y
    /// To do this in Rust properly with ndarray, we read the bf16 bits, convert to f32, and compute.
    pub fn execute_svd_projection(&self, layer_name: &str, input_vector: &[f32]) -> Result<Vec<f32>, String> {
        let meta = self.tensors.get(layer_name).ok_or_else(|| format!("Layer not found (mmap): {}", layer_name))?;
        
        let (rows, cols, rank) = match meta.tensor_type {
            TensorType::SVDLossless { rows, cols, rank } => (rows as usize, cols as usize, rank as usize),
            _ => return Err("Target tensor is not an SVD Lossless type".to_string()),
        };

        if input_vector.len() != cols {
            return Err(format!("Input vector dimension mismatch. Expected {}, got {}", cols, input_vector.len()));
        }

        let u_key = format!("{}.U", layer_name);
        let s_key = format!("{}.S", layer_name);
        let v_key = format!("{}.V", layer_name);
        let mod_x_key = format!("{}.mod_x", layer_name);
        let mod_y_key = format!("{}.mod_y", layer_name);
        let c_valve_key = format!("{}.c_valve", layer_name);

        let cached = {
            let tensors_cache = self.cpu_tensors_f32.borrow();
            let vectors_cache = self.cpu_vectors_f32.borrow();
            if tensors_cache.contains_key(&u_key) {
                Some((
                    tensors_cache.get(&u_key).unwrap().clone(),
                    vectors_cache.get(&s_key).unwrap().clone(),
                    tensors_cache.get(&v_key).unwrap().clone(),
                    vectors_cache.get(&mod_x_key).unwrap().clone(),
                    vectors_cache.get(&mod_y_key).unwrap().clone(),
                    tensors_cache.get(&c_valve_key).unwrap().clone(),
                ))
            } else {
                None
            }
        };

        let (u_mat, s_diag, v_mat, mod_x, mod_y, c_valve) = if let Some(cached_mats) = cached {
            cached_mats
        } else {
            let raw_data = self.get_raw_slice(layer_name).ok_or_else(|| "Could not read tensor data".to_string())?;
            let mut offset = 0;
            let mut read_f16_to_f32 = |length: usize| -> Vec<f32> {
                let mut result = Vec::with_capacity(length);
                for _ in 0..length {
                    let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                    let val = f16::from_le_bytes(bytes);
                    result.push(val.to_f32());
                    offset += 2;
                }
                result
            };

            let u_vec = read_f16_to_f32(rows * rank);
            let s_vec = read_f16_to_f32(rank);
            let v_vec = read_f16_to_f32(cols * rank);
            let mod_x_vec = read_f16_to_f32(cols);
            let mod_y_vec = read_f16_to_f32(rows);
            let c_valve_vec = read_f16_to_f32(rank * rank);

            let u_mat = ndarray::Array2::from_shape_vec((rows, rank), u_vec).unwrap();
            let s_diag = ndarray::Array1::from_vec(s_vec);
            let v_mat = ndarray::Array2::from_shape_vec((cols, rank), v_vec).unwrap();
            let mod_x = ndarray::Array1::from_vec(mod_x_vec);
            let mod_y = ndarray::Array1::from_vec(mod_y_vec);
            let c_valve = ndarray::Array2::from_shape_vec((rank, rank), c_valve_vec).unwrap();

            // 予算を超えたら丸ごと解放してから積む (SVD再構成はmmapから再読可能)
            let add_bytes = (u_mat.len() + s_diag.len() + v_mat.len()
                + mod_x.len() + mod_y.len() + c_valve.len()) * 4;
            {
                let mut used = self.cpu_cache_bytes.borrow_mut();
                if *used + add_bytes > self.cache_budget_bytes {
                    self.cpu_tensors_f32.borrow_mut().clear();
                    self.cpu_vectors_f32.borrow_mut().clear();
                    *used = 0;
                }
                *used += add_bytes;
            }
            self.cpu_tensors_f32.borrow_mut().insert(u_key, u_mat.clone());
            self.cpu_vectors_f32.borrow_mut().insert(s_key, s_diag.clone());
            self.cpu_tensors_f32.borrow_mut().insert(v_key, v_mat.clone());
            self.cpu_vectors_f32.borrow_mut().insert(mod_x_key, mod_x.clone());
            self.cpu_vectors_f32.borrow_mut().insert(mod_y_key, mod_y.clone());
            self.cpu_tensors_f32.borrow_mut().insert(c_valve_key, c_valve.clone());

            (u_mat, s_diag, v_mat, mod_x, mod_y, c_valve)
        };

        let input_nd = ndarray::Array1::from_vec(input_vector.to_vec());

        // --- Mathematically pure projection steps ---
        
        // 1. Modulate input: x' = x * mod_x
        let x_mod = input_nd * mod_x;

        // 2. Projection into Latent Concept Space (V is cols x rank. We want to project from cols to rank, so V^T * x')
        // In ndarray, V is (cols, rank). Its transpose is (rank, cols).
        let z = v_mat.t().dot(&x_mod);

        // 3. Scale by Singular Values
        let z_scaled = z * s_diag;

        // 4. Cascading Lock (Application of C_valve - The Orthogonal Subspace Filter)
        let z_locked = c_valve.dot(&z_scaled);

        // 5. Projection back into Output Space
        let y = u_mat.dot(&z_locked);

        // 6. Output Modulation
        let result = y + mod_y;

        Ok(result.into_raw_vec())
    }

    /// Performs a standard Dense matrix-vector multiplication (e.g., for lm_head)
    /// y = W * x
    pub fn execute_dense_projection(&self, layer_name: &str, input_vector: &[f32]) -> Result<Vec<f32>, String> {
        let meta = self.tensors.get(layer_name)
            .or_else(|| self.tensors.get(&format!("{}.weight", layer_name)))
            .or_else(|| self.tensors.get("output_layer.weight"))
            .or_else(|| self.tensors.get("transformer.output_layer.weight"))
            .ok_or_else(|| format!("Layer not found (mmap): {}", layer_name))?;
        
        let (rows, cols) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err("Not Dense2D".to_string()),
        };
        let w_t = self.get_candle_tensor(layer_name, &self.candle_device)
            .or_else(|_| self.get_candle_tensor(&format!("{}.weight", layer_name), &self.candle_device))
            .or_else(|_| self.get_candle_tensor("output_layer.weight", &self.candle_device))
            .or_else(|_| self.get_candle_tensor("transformer.output_layer.weight", &self.candle_device))
            .map_err(|e| e.to_string())?;
        let w_t_f16 = w_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
        
        let x_t = Tensor::from_slice(input_vector, (cols, 1), &self.candle_device).map_err(|e| e.to_string())?;
        let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
        let y_t = w_t_f16.matmul(&x_t_f16).map_err(|e| e.to_string())?;
        let y_t_f32 = y_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
        let y = y_t_f32.to_vec2::<f32>().map_err(|e| e.to_string())?;
        Ok(y.into_iter().flatten().collect())
    }

    /// Performs Telepathic Resonance (OOD Prevention)
    /// Mathematically forces the intent vector into the true token manifold.
    /// 1. logits = lm_head * x
    /// 2. probs = softmax(logits / temp)
    /// 3. y = lm_head^T * probs
    pub fn execute_telepathic_resonance(&self, layer_name: &str, input_vector: &[f32], temperature: f32) -> Result<Vec<f32>, String> {
        let meta = self.tensors.get(layer_name)
            .or_else(|| self.tensors.get(&format!("{}.weight", layer_name)))
            .or_else(|| self.tensors.get("output_layer.weight"))
            .ok_or_else(|| format!("Layer not found (mmap): {}", layer_name))?;
        
        let (vocab_size, hidden_dim) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err("Target tensor is not a Dense2D type (expected lm_head)".to_string()),
        };

        if input_vector.len() != hidden_dim {
            return Err(format!("Input vector dimension mismatch. Expected {}, got {}", hidden_dim, input_vector.len()));
        }

        let raw_data = &self.mmap[meta.offset..meta.offset + meta.byte_length];
        let mut offset = 0;

        let mut read_f16_to_f32 = |length: usize| -> Vec<f32> {
            let mut result = Vec::with_capacity(length);
            for _ in 0..length {
                let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                let val = f16::from_le_bytes(bytes);
                result.push(val.to_f32());
                offset += 2;
            }
            result
        };

        // Load lm_head weights
        let w_vec = read_f16_to_f32(vocab_size * hidden_dim);
        let w_mat = ndarray::Array2::from_shape_vec((vocab_size, hidden_dim), w_vec).unwrap();
        let x_nd = ndarray::Array1::from_vec(input_vector.to_vec());

        // 1. Calculate logits
        let mut logits = w_mat.dot(&x_nd);

        // 2. Apply Temperature and Stable Softmax
        let temp = if temperature > 0.0 { temperature } else { 0.1 };
        logits.mapv_inplace(|v| v / temp);

        let max_logit = logits.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        logits.mapv_inplace(|v| (v - max_logit).exp());
        let sum: f32 = logits.sum();
        logits.mapv_inplace(|v| v / sum);

        // 3. Resynthesize
        let thought_embeds = w_mat.t().dot(&logits);

        Ok(thought_embeds.into_raw_vec())
    }

    /// Performs Latent Resonance Search (Puzzle Inference)
    /// 1. Projects the thought vector to vocabulary space to compute entropy.
    /// 2. Locks the axis (token) with the lowest entropy (or highest resonance).
    /// 3. Returns the locked token ID and its mathematical entropy score.
    pub fn execute_puzzle_inference(&self, layer_name: &str, input_vector: &[f32]) -> Result<(u32, f32), String> {
        let meta = self.tensors.get(layer_name).ok_or_else(|| format!("Layer not found (mmap): {}", layer_name))?;
        
        let (vocab_size, hidden_dim) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err("Target tensor is not a Dense2D type (expected lm_head)".to_string()),
        };

        if input_vector.len() != hidden_dim {
            return Err(format!("Input vector dimension mismatch. Expected {}, got {}", hidden_dim, input_vector.len()));
        }

        let raw_data = &self.mmap[meta.offset..meta.offset + meta.byte_length];
        let mut offset = 0;

        let mut read_f16_to_f32 = |length: usize| -> Vec<f32> {
            let mut result = Vec::with_capacity(length);
            for _ in 0..length {
                let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                let val = f16::from_le_bytes(bytes);
                result.push(val.to_f32());
                offset += 2;
            }
            result
        };

        let w_vec = read_f16_to_f32(vocab_size * hidden_dim);
        let w_mat = ndarray::Array2::from_shape_vec((vocab_size, hidden_dim), w_vec).unwrap();
        let x_nd = ndarray::Array1::from_vec(input_vector.to_vec());

        // 1. Compute Logits
        let mut logits = w_mat.dot(&x_nd);

        // 2. Stable Softmax for exact Shannon Entropy
        let max_logit = logits.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        logits.mapv_inplace(|v| (v - max_logit).exp());
        let sum: f32 = logits.sum();
        logits.mapv_inplace(|v| v / sum); 

        // 3. Find Token with Highest Resonance
        let mut best_token = 0;
        let mut max_prob = -1.0;
        let mut entropy = 0.0;

        for (i, &prob) in logits.iter().enumerate() {
            if prob > 0.0 {
                entropy -= prob * prob.log2();
            }
            if prob > max_prob {
                max_prob = prob;
                best_token = i;
            }
        }

        Ok((best_token as u32, entropy))
    }

    /// Full top-K vocabulary distribution (softmax over lm_head logits), for
    /// callers that need more than the argmax -- divergence-packet claims,
    /// soft-sequence construction, dissent-key extraction, etc. Shares the
    /// same softmax computation as `execute_puzzle_inference` but returns the
    /// top-K (token_id, prob) pairs instead of collapsing to the argmax.
    pub fn execute_topk_distribution(&self, layer_name: &str, input_vector: &[f32], k: usize) -> Result<Vec<(u32, f32)>, String> {
        let meta = self.tensors.get(layer_name).ok_or_else(|| format!("Layer not found (mmap): {}", layer_name))?;

        let (vocab_size, hidden_dim) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err("Target tensor is not a Dense2D type (expected lm_head)".to_string()),
        };

        if input_vector.len() != hidden_dim {
            return Err(format!("Input vector dimension mismatch. Expected {}, got {}", hidden_dim, input_vector.len()));
        }

        let raw_data = &self.mmap[meta.offset..meta.offset + meta.byte_length];
        let mut offset = 0;

        let mut read_f16_to_f32 = |length: usize| -> Vec<f32> {
            let mut result = Vec::with_capacity(length);
            for _ in 0..length {
                let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                let val = f16::from_le_bytes(bytes);
                result.push(val.to_f32());
                offset += 2;
            }
            result
        };

        let w_vec = read_f16_to_f32(vocab_size * hidden_dim);
        let w_mat = ndarray::Array2::from_shape_vec((vocab_size, hidden_dim), w_vec).unwrap();
        let x_nd = ndarray::Array1::from_vec(input_vector.to_vec());

        let mut logits = w_mat.dot(&x_nd);
        let max_logit = logits.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        logits.mapv_inplace(|v| (v - max_logit).exp());
        let sum: f32 = logits.sum();
        logits.mapv_inplace(|v| v / sum);

        let mut indexed: Vec<(usize, f32)> = logits.iter().cloned().enumerate().collect();
        indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let k = k.min(indexed.len());
        Ok(indexed.into_iter().take(k).map(|(i, p)| (i as u32, p)).collect())
    }

    /// [NEW FFI ENTRY] optimize thought vector directly using Latent Gradient Descent
    pub fn optimize_thought_in_place(&self, layer_name: &str, input_vector: &mut [f32], max_steps: usize, lr: f32, temperature: f32) -> Result<f32, String> {
        let meta = self.tensors.get(layer_name).ok_or_else(|| format!("Layer not found (mmap): {}", layer_name))?;
        
        let (vocab_size, hidden_dim) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err("Target tensor is not a Dense2D type (expected lm_head)".to_string()),
        };

        if input_vector.len() != hidden_dim {
            return Err(format!("Input vector dimension mismatch. Expected {}, got {}", hidden_dim, input_vector.len()));
        }

        let raw_data = &self.mmap[meta.offset..meta.offset + meta.byte_length];
        let mut offset = 0;

        let mut read_f16_to_f32 = |length: usize| -> Vec<f32> {
            let mut result = Vec::with_capacity(length);
            for _ in 0..length {
                let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                let val = f16::from_le_bytes(bytes);
                result.push(val.to_f32());
                offset += 2;
            }
            result
        };

        let w_vec = read_f16_to_f32(vocab_size * hidden_dim);
        let w_mat = ndarray::Array2::from_shape_vec((vocab_size, hidden_dim), w_vec).unwrap();
        let x_nd = ndarray::Array1::from_vec(input_vector.to_vec());

        // Call the true Puzzle Inference (Gradient Descent)
        let (optimized_x, final_entropy) = crate::puzzle_math::optimize_thought_vector(&w_mat, &x_nd, max_steps, lr, temperature);
        
        // Write back
        input_vector.copy_from_slice(optimized_x.as_slice().unwrap());

        Ok(final_entropy)
    }

    /// Helper method to project a vector through a tensor (Dense or SVD)
    pub fn project_vector(&self, layer_name: &str, input: &Array1<f32>) -> Result<Array1<f32>, String> {
        let meta = self.tensors.get(layer_name).ok_or_else(|| format!("Layer not found (mmap): {}", layer_name))?;
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let (rows, cols) = (rows as usize, cols as usize);
                let raw_data = self.get_raw_slice(layer_name).ok_or_else(|| "Could not read tensor data".to_string())?;
                let mut offset = 0;
                let mut w_vec = Vec::with_capacity(rows * cols);
                for _ in 0..(rows * cols) {
                    let bytes = [raw_data[offset], raw_data[offset+1]];
                    w_vec.push(f16::from_le_bytes(bytes).to_f32());
                    offset += 2;
                }
                let w_mat = ndarray::Array2::from_shape_vec((rows, cols), w_vec).unwrap();
                Ok(w_mat.dot(input))
            },
            TensorType::Dense1D { length } => {
                let length = length as usize;
                let raw_data = self.get_raw_slice(layer_name).ok_or_else(|| "Could not read tensor data".to_string())?;
                let mut offset = 0;
                let mut w_vec = Vec::with_capacity(length);
                for _ in 0..length {
                    let bytes = [raw_data[offset], raw_data[offset+1]];
                    w_vec.push(f16::from_le_bytes(bytes).to_f32());
                    offset += 2;
                }
                Ok(Array1::from_vec(w_vec))
            },
            TensorType::SVDLossless { .. } => {
                let out_vec = self.execute_svd_projection(layer_name, input.as_slice().unwrap())?;
                Ok(Array1::from_vec(out_vec))
            }
        }
    }

    pub fn project_matrix(&self, layer_name: &str, input: &ndarray::Array2<f32>) -> Result<ndarray::Array2<f32>, String> {
        let meta = self.tensors.get(layer_name).ok_or_else(|| format!("Layer not found: {}", layer_name))?;
        let b = input.shape()[0];
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let (rows, cols) = (rows as usize, cols as usize);
                let raw_data = self.get_raw_slice(layer_name).ok_or_else(|| "Could not read tensor data".to_string())?;
                let mut offset = 0;
                let mut w_vec = Vec::with_capacity(rows * cols);
                for _ in 0..(rows * cols) {
                    let bytes = [raw_data[offset], raw_data[offset+1]];
                    w_vec.push(f16::from_le_bytes(bytes).to_f32());
                    offset += 2;
                }
                let w_mat = ndarray::Array2::from_shape_vec((rows, cols), w_vec).unwrap();
                let mut out = ndarray::Array2::<f32>::zeros((b, rows));
                for i in 0..b {
                    let row = input.row(i).to_owned();
                    let out_row = w_mat.dot(&row);
                    for r in 0..rows {
                        out[[i, r]] = out_row[r];
                    }
                }
                Ok(out)
            },
            TensorType::Dense1D { length } => {
                let length = length as usize;
                let raw_data = self.get_raw_slice(layer_name).ok_or_else(|| "Could not read tensor data".to_string())?;
                let mut offset = 0;
                let mut w_vec = Vec::with_capacity(length);
                for _ in 0..length {
                    let bytes = [raw_data[offset], raw_data[offset+1]];
                    w_vec.push(f16::from_le_bytes(bytes).to_f32());
                    offset += 2;
                }
                Ok(ndarray::Array2::from_shape_fn((b, length), |(_, j)| w_vec[j]))
            },
            TensorType::SVDLossless { rows, .. } => {
                let rows = rows as usize;
                let mut out = ndarray::Array2::<f32>::zeros((b, rows));
                for i in 0..b {
                    let row = input.row(i).to_owned();
                    let out_row = self.execute_svd_projection(layer_name, row.as_slice().unwrap())?;
                    for r in 0..rows {
                        out[[i, r]] = out_row[r];
                    }
                }
                Ok(out)
            }
        }
    }

    /// Per-head RMSNorm for Q/K (Qwen3-family "QK-norm"), applied before RoPE.
    /// `data` is a flat slice of one or more tokens: len = n_tokens * n_heads * head_dim.
    fn apply_head_rmsnorm(data: &mut [f32], w: &[f32], head_dim: usize) {
        let eps = 1e-6f32;
        for chunk in data.chunks_mut(head_dim) {
            let mut ss = 0.0f32;
            for &v in chunk.iter() { ss += v * v; }
            let r = (ss / head_dim as f32 + eps).sqrt();
            for (j, v) in chunk.iter_mut().enumerate() { *v = (*v / r) * w[j]; }
        }
    }

    /// Fetch a QK-norm weight vector for a layer if present (returns None otherwise).
    fn qk_norm_weight(&self, layer: usize, which: &str) -> Option<Vec<f32>> {
        let names = [
            format!("model.layers.{}.self_attn.{}_norm.weight", layer, which),
            format!("model.language_model.layers.{}.self_attn.{}_norm.weight", layer, which),
        ];
        for nm in &names {
            if let Some(meta) = self.tensors.get(nm.as_str()) {
                if let TensorType::Dense1D { length } = meta.tensor_type {
                    let raw = self.get_raw_slice(nm)?;
                    let n = length as usize;
                    let mut out = Vec::with_capacity(n);
                    for i in 0..n {
                        let b: [u8; 2] = [raw[i * 2], raw[i * 2 + 1]];
                        out.push(f16::from_le_bytes(b).to_f32());
                    }
                    return Some(out);
                }
            }
        }
        None
    }

    pub fn forward_transformer_layer(
        &self, 
        layer: usize, 
        mut x: Array1<f32>, 
        pos: usize, 
        rope_theta: f32
    ) -> Result<Array1<f32>, String> {
        if self.gemma4.is_some() {
            // Callers that need PLE should invoke forward_gemma4_layer directly.
            return self.forward_gemma4_layer(layer, x, pos, None);
        }
        let norm_eps = 1e-6; // Qwen default

        // Helper to try multiple layer names
        let project_any = |names: &[&str], input: &Array1<f32>| -> Result<Array1<f32>, String> {
            for name in names {
                if let Ok(res) = self.project_vector(name, input) {
                    return Ok(res);
                }
            }
            Err(format!("None of the layers found: {:?}", names))
        };

        // 1. Input RMSNorm
        let norm_names = [
            &format!("model.language_model.layers.{}.input_layernorm.weight", layer)[..],
            &format!("model.layers.{}.input_layernorm.weight", layer)[..]
        ];
        let norm_w = project_any(&norm_names, &x)?;
        
        let mut sum_sq = 0.0;
        for &val in x.iter() { sum_sq += val * val; }
        let rms = (sum_sq / (x.len() as f32) + norm_eps).sqrt();
        
        let mut x_norm = x.clone();
        for (i, val) in x_norm.iter_mut().enumerate() { *val = (*val / rms) * norm_w[i]; }

        // 2. QKV Projection (Standard Qwen/Gemma Fallback vs GLM-4 GQA)
        let qkv_names = [&format!("model.layers.{}.self_attn.query_key_value.weight", layer)[..]];
        let qkv_bias_names = [&format!("model.layers.{}.self_attn.query_key_value.bias", layer)[..]];
        
        if let Ok(mut qkv) = project_any(&qkv_names, &x_norm) {
            // GLM-4/5.2 結合テンソル処理
            if let Ok(qkv_bias) = project_any(&qkv_bias_names, &x_norm) {
                for i in 0..qkv.len() {
                    qkv[i] += qkv_bias[i];
                }
            }

            let head_dim = 128;
            let num_heads = 32;
            let num_kv_heads = 2;
            let q_len = num_heads * head_dim; // 4096
            let k_len = num_kv_heads * head_dim; // 256
            let v_len = num_kv_heads * head_dim; // 256
            
            let mut q_c = qkv.slice(ndarray::s![0..q_len]).to_owned();
            let mut k_c = qkv.slice(ndarray::s![q_len..q_len + k_len]).to_owned();
            let v_c = qkv.slice(ndarray::s![q_len + k_len..q_len + k_len + v_len]).to_owned();

            crate::generation::apply_rope_glm(
                q_c.as_slice_mut().unwrap(),
                k_c.as_slice_mut().unwrap(),
                pos,
                num_heads,
                num_kv_heads,
                head_dim,
                rope_theta,
                0,
            );

            let mut cache_opt = self.kv_cache.borrow_mut();
            if cache_opt.is_none() {
                *cache_opt = Some(crate::generation::AttentionState::new(self.num_layers, 2, 128, rope_theta));
            }
            let state_ref = cache_opt.as_mut().unwrap();
            state_ref.append_kv(layer, &k_c, &v_c);
            
            let attn_out = crate::generation::sdpa_gqa(
                &q_c,
                &state_ref.k_cache[layer],
                &state_ref.v_cache[layer],
                num_heads,
                num_kv_heads,
                head_dim,
            );
            
            let dense_names = [&format!("model.layers.{}.self_attn.dense.weight", layer)[..]];
            if let Ok(out) = project_any(&dense_names, &attn_out) {
                for i in 0..x.len() {
                    x[i] += out[i];
                }
            }
        } else {
            // 標準的な Qwen/Gemma のフォールバック
            let q_names = [
                &format!("model.layers.{}.self_attn.q_proj.weight", layer)[..],
                &format!("model.language_model.layers.{}.self_attn.q_proj.weight", layer)[..]
            ];
            let k_names = [
                &format!("model.layers.{}.self_attn.k_proj.weight", layer)[..],
                &format!("model.language_model.layers.{}.self_attn.k_proj.weight", layer)[..]
            ];
            let v_names = [
                &format!("model.layers.{}.self_attn.v_proj.weight", layer)[..],
                &format!("model.language_model.layers.{}.self_attn.v_proj.weight", layer)[..]
            ];

            if let (Ok(mut q_c), Ok(mut k_c), Ok(mut v_c)) = (
                project_any(&q_names, &x_norm),
                project_any(&k_names, &x_norm),
                project_any(&v_names, &x_norm),
            ) {
                let num_heads = self.num_heads;
                let num_kv_heads = self.num_kv_heads;
                let head_dim = self.head_dim;
                
                // Qwen-family models use attention biases (applied before RoPE)
                for (vec, proj) in [(&mut q_c, "q_proj"), (&mut k_c, "k_proj"), (&mut v_c, "v_proj")] {
                    let bias_names = [
                        format!("model.layers.{}.self_attn.{}.bias", layer, proj),
                        format!("model.language_model.layers.{}.self_attn.{}.bias", layer, proj),
                    ];
                    for bname in &bias_names {
                        if self.tensors.contains_key(bname.as_str()) {
                            if let Ok(b) = self.project_vector(bname, &x_norm) {
                                if b.len() == vec.len() {
                                    *vec = &*vec + &b;
                                }
                            }
                            break;
                        }
                    }
                }

                // QK-norm (Qwen3-family): per-head RMSNorm before RoPE
                if let Some(w) = self.qk_norm_weight(layer, "q") {
                    if w.len() == head_dim {
                        Self::apply_head_rmsnorm(q_c.as_slice_mut().unwrap(), &w, head_dim);
                    }
                }
                if let Some(w) = self.qk_norm_weight(layer, "k") {
                    if w.len() == head_dim {
                        Self::apply_head_rmsnorm(k_c.as_slice_mut().unwrap(), &w, head_dim);
                    }
                }

                if self.rope_neox {
                    apply_rope_neox(
                        q_c.as_slice_mut().unwrap(),
                        k_c.as_slice_mut().unwrap(),
                        pos,
                        num_heads,
                        num_kv_heads,
                        head_dim,
                        rope_theta,
                    );
                } else {
                    apply_rope_glm(
                        q_c.as_slice_mut().unwrap(),
                        k_c.as_slice_mut().unwrap(),
                        pos,
                        num_heads,
                        num_kv_heads,
                        head_dim,
                        rope_theta,
                        0,
                    );
                }

                let mut cache_opt = self.kv_cache.borrow_mut();
                if cache_opt.is_none() {
                    *cache_opt = Some(crate::generation::AttentionState::new(self.num_layers, num_kv_heads, head_dim, rope_theta));
                }
                let state_ref = cache_opt.as_mut().unwrap();
                state_ref.append_kv(layer, &k_c, &v_c);
                
                let attn_out = crate::generation::sdpa_gqa(
                    &q_c,
                    &state_ref.k_cache[layer],
                    &state_ref.v_cache[layer],
                    num_heads,
                    num_kv_heads,
                    head_dim,
                );
                
                let dense_names = [
                    &format!("model.layers.{}.self_attn.o_proj.weight", layer)[..],
                    &format!("model.language_model.layers.{}.self_attn.o_proj.weight", layer)[..],
                    &format!("model.layers.{}.self_attn.dense.weight", layer)[..]
                ];
                if let Ok(out) = project_any(&dense_names, &attn_out) {
                    for i in 0..x.len() {
                        x[i] += out[i];
                    }
                }
            }
        }

        // 6. Post-Attention RMSNorm
        let post_names = [
            &format!("model.language_model.layers.{}.post_attention_layernorm.weight", layer)[..],
            &format!("model.layers.{}.post_attention_layernorm.weight", layer)[..]
        ];
        let post_norm_w = project_any(&post_names, &x)?;
        
        sum_sq = 0.0;
        for &val in x.iter() { sum_sq += val * val; }
        let rms2 = (sum_sq / (x.len() as f32) + norm_eps).sqrt();
        let mut x_post_norm = x.clone();
        for (i, val) in x_post_norm.iter_mut().enumerate() { *val = (*val / rms2) * post_norm_w[i]; }

        // 7. MLP Projections (Dense/MoE or Standard Fallback)
        let router_names = [&format!("model.layers.{}.mlp.gate.weight", layer)[..]];
        let has_router = router_names.iter().any(|&name| self.tensors.contains_key(name));
        let is_moe = layer >= self.first_moe_layer && has_router;

        if is_moe {
            let router_w = project_any(&router_names, &x_post_norm)?; // Router logits over experts
            let bias_names = [&format!("model.layers.{}.mlp.gate.e_score_correction_bias", layer)[..]];
            let mut scores = router_w;
            if let Ok(bias) = project_any(&bias_names, &x_post_norm) {
                for i in 0..scores.len() {
                    scores[i] += bias[i];
                }
            }
            let k = self.moe_top_k.min(scores.len());
            let mut experts_with_scores: Vec<(usize, f32)> = scores.iter().enumerate().map(|(i, &s)| (i, s)).collect();
            experts_with_scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            
            let top_k_experts: Vec<_> = experts_with_scores.into_iter().take(k).collect();
            
            // Save active experts to prefetch cache for next token
            if let Ok(mut pc) = self.prefetch_cache.try_borrow_mut() {
                let expert_ids: Vec<usize> = top_k_experts.iter().map(|&(idx, _)| idx).collect();
                pc.insert(layer as usize, expert_ids);
            }
            
            // Score normalization: softmax (Qwen-MoE) or sigmoid+normalize (GLM/DeepSeek)
            let mut top_k_probs = vec![0.0; k];
            let mut sum_probs = 0.0;
            if self.moe_softmax {
                let m = top_k_experts.iter().map(|e| e.1).fold(f32::NEG_INFINITY, f32::max);
                for i in 0..k {
                    let s = (top_k_experts[i].1 - m).exp();
                    top_k_probs[i] = s;
                    sum_probs += s;
                }
            } else {
                for i in 0..k {
                    let s = 1.0 / (1.0 + (-top_k_experts[i].1).exp());
                    top_k_probs[i] = s;
                    sum_probs += s;
                }
            }
            for i in 0..k {
                top_k_probs[i] /= sum_probs;
            }
            
            let mut moe_out = ndarray::Array1::<f32>::zeros(x_post_norm.len());

            // Iterate over top K routed experts
            for (i, &(expert_idx, _)) in top_k_experts.iter().enumerate() {
                self.record_expert_usage(layer, expert_idx);
                
                let gate_names = [&format!("model.layers.{}.mlp.experts.{}.gate_proj.weight", layer, expert_idx)[..]];
                let up_names = [&format!("model.layers.{}.mlp.experts.{}.up_proj.weight", layer, expert_idx)[..]];
                let down_names = [&format!("model.layers.{}.mlp.experts.{}.down_proj.weight", layer, expert_idx)[..]];
                
                if let (Ok(mut gate), Ok(up)) = (project_any(&gate_names, &x_post_norm), project_any(&up_names, &x_post_norm)) {
                    for (j, val) in gate.iter_mut().enumerate() {
                        *val = swiglu(*val) * up[j];
                    }
                    if let Ok(down) = project_any(&down_names, &gate) {
                        for j in 0..moe_out.len() {
                            moe_out[j] += down[j] * top_k_probs[i];
                        }
                    }
                }
            }
            
            // Add Shared Expert
            let shared_gate_names = [&format!("model.layers.{}.mlp.shared_experts.gate_proj.weight", layer)[..]];
            let shared_up_names = [&format!("model.layers.{}.mlp.shared_experts.up_proj.weight", layer)[..]];
            let shared_down_names = [&format!("model.layers.{}.mlp.shared_experts.down_proj.weight", layer)[..]];
            
            if let (Ok(mut gate), Ok(up)) = (project_any(&shared_gate_names, &x_post_norm), project_any(&shared_up_names, &x_post_norm)) {
                for (j, val) in gate.iter_mut().enumerate() {
                    *val = swiglu(*val) * up[j];
                }
                if let Ok(down) = project_any(&shared_down_names, &gate) {
                    for j in 0..moe_out.len() {
                        moe_out[j] += down[j];
                    }
                }
            }
            x = x + moe_out;
        } else {
            // Dense MLP fallback (Standard Qwen/Gemma and GLM dense layers)
            let gate_names = [
                &format!("model.layers.{}.mlp.gate_proj.weight", layer)[..],
                &format!("model.language_model.layers.{}.mlp.gate_proj.weight", layer)[..]
            ];
            let up_names = [
                &format!("model.layers.{}.mlp.up_proj.weight", layer)[..],
                &format!("model.language_model.layers.{}.mlp.up_proj.weight", layer)[..]
            ];
            let down_names = [
                &format!("model.layers.{}.mlp.down_proj.weight", layer)[..],
                &format!("model.language_model.layers.{}.mlp.down_proj.weight", layer)[..]
            ];

            if let (Ok(mut gate), Ok(up)) = (project_any(&gate_names, &x_post_norm), project_any(&up_names, &x_post_norm)) {
                for (i, val) in gate.iter_mut().enumerate() {
                    *val = swiglu(*val) * up[i];
                }
                if let Ok(mlp_out) = project_any(&down_names, &gate) {
                    x = x + mlp_out;
                }
            }
        }

        Ok(x)
    }

    /// Execute Worker Forward Pass (Encode Prompt to Intent Vector)

    pub fn forward_transformer_layer_chunked(
        &self, 
        layer: usize, 
        mut x: ndarray::Array2<f32>, 
        start_pos: usize, 
        rope_theta: f32
    ) -> Result<ndarray::Array2<f32>, String> {
        if self.gemma4.is_some() {
            // Callers that need PLE should invoke forward_gemma4_layer_chunked directly.
            return self.forward_gemma4_layer_chunked(layer, x, start_pos, None);
        }
        let norm_eps = 1e-6;
        let b = x.shape()[0];
        let hidden_dim = x.shape()[1];

        let project_any = |names: &[&str], input: &ndarray::Array2<f32>| -> Result<ndarray::Array2<f32>, String> {
            for name in names {
                if let Ok(res) = self.project_matrix(name, input) {
                    return Ok(res);
                }
            }
            Err(format!("None of the layers found: {:?}", names))
        };

        // 1. Input RMSNorm
        let norm_names = [
            &format!("model.language_model.layers.{}.input_layernorm.weight", layer)[..],
            &format!("model.layers.{}.input_layernorm.weight", layer)[..]
        ];
        let norm_w = project_any(&norm_names, &x)?;
        
        let mut x_norm = x.clone();
        for i in 0..b {
            let mut sum_sq = 0.0;
            for j in 0..hidden_dim { sum_sq += x[[i, j]] * x[[i, j]]; }
            let rms = (sum_sq / (hidden_dim as f32) + norm_eps).sqrt();
            for j in 0..hidden_dim { x_norm[[i, j]] = (x_norm[[i, j]] / rms) * norm_w[[i, j]]; }
        }

        // 2. QKV Projections
        let q_names = [&format!("model.language_model.layers.{}.self_attn.q_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]];
        let k_names = [&format!("model.language_model.layers.{}.self_attn.k_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.k_proj.weight", layer)[..]];
        let v_names = [&format!("model.language_model.layers.{}.self_attn.v_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.v_proj.weight", layer)[..]];

        let head_dim = self.head_dim;
        
        let mut q_res = project_any(&q_names, &x_norm);
        let mut k_res = project_any(&k_names, &x_norm);
        let mut v_res = project_any(&v_names, &x_norm);
        
        if let Ok(ref mut q) = q_res {
            if q.shape()[1] == 8192 {
                *q = q.slice(ndarray::s![.., ..4096]).to_owned();
            }
        }

        if let (Ok(mut q), Ok(mut k), Ok(mut v)) = (q_res, k_res, v_res) {
            let num_heads = self.num_heads;
            let num_kv_heads = self.num_kv_heads;

            // Qwen-family attention biases (applied before RoPE)
            for (mat, proj) in [(&mut q, "q_proj"), (&mut k, "k_proj"), (&mut v, "v_proj")] {
                let bias_names = [
                    format!("model.layers.{}.self_attn.{}.bias", layer, proj),
                    format!("model.language_model.layers.{}.self_attn.{}.bias", layer, proj),
                ];
                for bname in &bias_names {
                    if self.tensors.contains_key(bname.as_str()) {
                        if let Ok(b_mat) = self.project_matrix(bname, &x_norm) {
                            if b_mat.shape() == mat.shape() {
                                *mat = &*mat + &b_mat;
                            }
                        }
                        break;
                    }
                }
            }

            // QK-norm (Qwen3-family): per-head RMSNorm before RoPE
            if let Some(w) = self.qk_norm_weight(layer, "q") {
                if w.len() == head_dim {
                    Self::apply_head_rmsnorm(q.as_slice_mut().unwrap(), &w, head_dim);
                }
            }
            if let Some(w) = self.qk_norm_weight(layer, "k") {
                if w.len() == head_dim {
                    Self::apply_head_rmsnorm(k.as_slice_mut().unwrap(), &w, head_dim);
                }
            }

            // 3. Apply RoPE Chunked
            let q_slice = q.as_slice_mut().unwrap();
            let k_slice = k.as_slice_mut().unwrap();
            if self.rope_neox {
                apply_rope_chunked_neox(q_slice, k_slice, start_pos, b, num_heads, num_kv_heads, head_dim, rope_theta);
            } else {
                apply_rope_chunked_glm(q_slice, k_slice, start_pos, b, num_heads, num_kv_heads, head_dim, rope_theta);
            }

            // 4. Update KV Cache & Attention
            let attn_out = {
                let mut cache_opt = self.kv_cache.borrow_mut();
                if cache_opt.is_none() {
                    return Err("KV Cache not initialized".to_string());
                }
                let cache = cache_opt.as_mut().unwrap();
                
                // Append b tokens.
                // AttentionState::append_kv takes Array1. We need to append Array2.
                // So we loop over b tokens to append.
                for i in 0..b {
                    let k_token = k.slice(ndarray::s![i, ..]).to_owned();
                    let v_token = v.slice(ndarray::s![i, ..]).to_owned();
                    cache.append_kv(layer, &k_token, &v_token);
                }
                
                let cache_k = &cache.k_cache[layer];
                let cache_v = &cache.v_cache[layer];
                sdpa_chunked(&q, cache_k, cache_v, num_heads, num_kv_heads, head_dim)
            };

            // 5. Output Projection
            let o_names = [&format!("model.language_model.layers.{}.self_attn.o_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.o_proj.weight", layer)[..]];
            if let Ok(attn_proj) = project_any(&o_names, &attn_out) {
                x = x + attn_proj;
            }
        }

        // 6. Post-Attention RMSNorm
        let post_names = [&format!("model.language_model.layers.{}.post_attention_layernorm.weight", layer)[..], &format!("model.layers.{}.post_attention_layernorm.weight", layer)[..]];
        let post_norm_w = project_any(&post_names, &x)?;
        
        let mut x_post_norm = x.clone();
        for i in 0..b {
            let mut sum_sq = 0.0;
            for j in 0..hidden_dim { sum_sq += x[[i, j]] * x[[i, j]]; }
            let rms2 = (sum_sq / (hidden_dim as f32) + norm_eps).sqrt();
            for j in 0..hidden_dim { x_post_norm[[i, j]] = (x_post_norm[[i, j]] / rms2) * post_norm_w[[i, j]]; }
        }

        // 7. MLP Projections (MoE router present? -> per-token expert dispatch)
        let router_name = format!("model.layers.{}.mlp.gate.weight", layer);
        let is_moe = layer >= self.first_moe_layer && self.tensors.contains_key(router_name.as_str());

        if is_moe {
            // 行 (トークン) ごとに単一トークン用の MoE 経路を適用する
            for i in 0..b {
                let row = x_post_norm.slice(ndarray::s![i, ..]).to_owned();
                let moe_out = self.moe_mlp_single(layer, &row)?;
                for j in 0..hidden_dim {
                    x[[i, j]] += moe_out[j];
                }
            }
        } else {
            let gate_names = [&format!("model.language_model.layers.{}.mlp.gate_proj.weight", layer)[..], &format!("model.layers.{}.mlp.gate_proj.weight", layer)[..]];
            let up_names = [&format!("model.language_model.layers.{}.mlp.up_proj.weight", layer)[..], &format!("model.layers.{}.mlp.up_proj.weight", layer)[..]];
            let down_names = [&format!("model.language_model.layers.{}.mlp.down_proj.weight", layer)[..], &format!("model.layers.{}.mlp.down_proj.weight", layer)[..]];

            if let (Ok(mut gate), Ok(up)) = (project_any(&gate_names, &x_post_norm), project_any(&up_names, &x_post_norm)) {
                for i in 0..b {
                    for j in 0..gate.shape()[1] {
                        gate[[i, j]] = swiglu(gate[[i, j]]) * up[[i, j]];
                    }
                }

                if let Ok(mlp_out) = project_any(&down_names, &gate) {
                    x = x + mlp_out;
                }
            }
        }

        Ok(x)
    }

    /// Read one fp16 Dense2D row into f32.
    fn read_dense2d_row(&self, name: &str, row: usize) -> Result<Vec<f32>, String> {
        let meta = self.tensors.get(name).ok_or_else(|| format!("missing {}", name))?;
        let (rows, cols) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err(format!("{} not Dense2D", name)),
        };
        if row >= rows {
            return Err(format!("{} row {} out of {}", name, row, rows));
        }
        let raw = self.get_raw_slice(name).ok_or_else(|| format!("unreadable {}", name))?;
        let start = row * cols * 2;
        let mut out = Vec::with_capacity(cols);
        for j in 0..cols {
            let o = start + j * 2;
            out.push(f16::from_le_bytes([raw[o], raw[o + 1]]).to_f32());
        }
        Ok(out)
    }

    /// Build PLE tensor [seq, layers, ple_dim] from scaled embeds + optional token ids.
    /// Positions with `token_ids[i] == None` (soft tokens) use context-only projection.
    pub(crate) fn gemma4_build_ple(
        &self,
        embeds: &ndarray::Array2<f32>,
        token_ids: &[Option<u32>],
    ) -> Result<ndarray::Array3<f32>, String> {
        let g4 = self.gemma4.as_ref().ok_or("not gemma4")?;
        let seq = embeds.shape()[0];
        let hidden = embeds.shape()[1];
        let layers = g4.num_layers;
        let ple_dim = g4.hidden_size_per_layer_input.max(1);
        if token_ids.len() != seq {
            return Err(format!("PLE token_ids len {} != seq {}", token_ids.len(), seq));
        }
        if g4.ple_omitted {
            return Ok(ndarray::Array3::<f32>::zeros((seq, layers, ple_dim)));
        }
        if !self.tensors.contains_key("model.per_layer_token_embd.weight") {
            return Err("PLE embd missing (reconvert without --no-ple)".into());
        }

        // Context-aware: Linear(hidden → layers*ple_dim) * 1/√hidden → reshape → RMSNorm
        let mut ctx = self.project_matrix("model.per_layer_model_proj.weight", embeds)?;
        let scale = ple_model_proj_scale(hidden);
        ctx.mapv_inplace(|v| v * scale);
        if ctx.shape()[1] != layers * ple_dim {
            return Err(format!(
                "PLE proj out {} != layers*ple_dim {}",
                ctx.shape()[1],
                layers * ple_dim
            ));
        }
        let mut ctx3 = ctx
            .into_shape((seq, layers, ple_dim))
            .map_err(|e| e.to_string())?;
        let norm_w = self.project_vector(
            "model.per_layer_proj_norm.weight",
            &Array1::<f32>::zeros(ple_dim),
        )?;
        if norm_w.len() != ple_dim {
            return Err(format!("ple proj norm len {} != {}", norm_w.len(), ple_dim));
        }
        rms_norm_ple3(&mut ctx3, norm_w.as_slice().unwrap(), 1e-6);

        // Token-identity: scaled PLE table lookup
        let mut tok3 = ndarray::Array3::<f32>::zeros((seq, layers, ple_dim));
        let tscale = ple_token_scale(ple_dim);
        let mut any_tok = false;
        for (i, tid) in token_ids.iter().enumerate() {
            if let Some(tok) = tid {
                any_tok = true;
                let row = self.read_dense2d_row("model.per_layer_token_embd.weight", *tok as usize)?;
                if row.len() != layers * ple_dim {
                    return Err(format!(
                        "PLE row len {} != {}",
                        row.len(),
                        layers * ple_dim
                    ));
                }
                for l in 0..layers {
                    for d in 0..ple_dim {
                        tok3[[i, l, d]] = row[l * ple_dim + d] * tscale;
                    }
                }
            }
        }

        let mut out = ndarray::Array3::<f32>::zeros((seq, layers, ple_dim));
        for i in 0..seq {
            if token_ids[i].is_some() && any_tok {
                for l in 0..layers {
                    for d in 0..ple_dim {
                        out[[i, l, d]] =
                            (ctx3[[i, l, d]] + tok3[[i, l, d]]) * PLE_COMBINE_SCALE;
                    }
                }
            } else {
                // Soft / missing ids: context only (HF multimodal path)
                for l in 0..layers {
                    for d in 0..ple_dim {
                        out[[i, l, d]] = ctx3[[i, l, d]];
                    }
                }
            }
        }
        Ok(out)
    }

    /// Layer-local PLE inject: residual += post_norm(proj(gelu(gate(h)) ⊙ ple))
    fn gemma4_apply_ple_chunked(
        &self,
        layer: usize,
        mut x: ndarray::Array2<f32>,
        ple: &ndarray::Array2<f32>, // [b, ple_dim]
    ) -> Result<ndarray::Array2<f32>, String> {
        let b = x.shape()[0];
        if ple.shape()[0] != b {
            return Err("PLE batch mismatch".into());
        }
        let gate = self.project_matrix(
            &format!("model.layers.{}.per_layer_input.gate.weight", layer),
            &x,
        )?;
        let mut gated = gate;
        {
            let flat = gated.as_slice_mut().unwrap();
            for v in flat.iter_mut() {
                *v = gelu_pytorch_tanh(*v);
            }
        }
        // elementwise * ple
        for i in 0..b {
            for d in 0..ple.shape()[1] {
                gated[[i, d]] *= ple[[i, d]];
            }
        }
        let proj = self.project_matrix(
            &format!("model.layers.{}.per_layer_input.proj.weight", layer),
            &gated,
        )?;
        let hidden = x.shape()[1];
        let w = self.project_vector(
            &format!("model.layers.{}.gemma4_post_norm.weight", layer),
            &Array1::<f32>::zeros(hidden),
        )?;
        let mut branch = proj;
        for i in 0..b {
            let mut sum_sq = 0.0f32;
            for j in 0..hidden {
                sum_sq += branch[[i, j]] * branch[[i, j]];
            }
            let rms = (sum_sq / (hidden as f32) + 1e-6).sqrt();
            for j in 0..hidden {
                branch[[i, j]] = (branch[[i, j]] / rms) * w[j];
            }
        }
        x = x + branch;
        Ok(x)
    }

    fn gemma4_apply_ple_token(
        &self,
        layer: usize,
        mut x: Array1<f32>,
        ple: &Array1<f32>,
    ) -> Result<Array1<f32>, String> {
        let gate = self.project_vector(
            &format!("model.layers.{}.per_layer_input.gate.weight", layer),
            &x,
        )?;
        let mut gated = gate;
        for v in gated.iter_mut() {
            *v = gelu_pytorch_tanh(*v);
        }
        if gated.len() != ple.len() {
            return Err(format!(
                "PLE gate {} != ple {}",
                gated.len(),
                ple.len()
            ));
        }
        for i in 0..gated.len() {
            gated[i] *= ple[i];
        }
        let proj = self.project_vector(
            &format!("model.layers.{}.per_layer_input.proj.weight", layer),
            &gated,
        )?;
        let w = self.project_vector(
            &format!("model.layers.{}.gemma4_post_norm.weight", layer),
            &x,
        )?;
        let hidden = x.len();
        let mut sum_sq = 0.0f32;
        for &v in proj.iter() {
            sum_sq += v * v;
        }
        let rms = (sum_sq / (hidden as f32) + 1e-6).sqrt();
        let mut branch = proj;
        for i in 0..hidden {
            branch[i] = (branch[i] / rms) * w[i];
        }
        Ok(x + branch)
    }

    /// Gemma4 text-tower layer (prefill/encode chunked path).
    /// Topology: attn_norm → attn(+window) → +res → post_attn_norm →
    ///           pre_ffn_norm → GeGLU mlp → +res → post_ffn_norm → PLE residual → scale.
    fn forward_gemma4_layer_chunked(
        &self,
        layer: usize,
        mut x: ndarray::Array2<f32>,
        start_pos: usize,
        ple: Option<&ndarray::Array2<f32>>, // [b, ple_dim]
    ) -> Result<ndarray::Array2<f32>, String> {
        let g4 = self.gemma4.as_ref().ok_or("not gemma4")?;
        let norm_eps = 1e-6f32;
        let b = x.shape()[0];
        let hidden_dim = x.shape()[1];
        let head_dim = g4.head_dim(layer);
        let num_heads = g4.num_heads;
        let num_kv_heads = g4.num_kv_heads;
        let rope_theta = g4.rope_theta(layer);
        let window = if g4.is_sliding(layer) {
            Some(g4.sliding_window)
        } else {
            None
        };

        let project_any = |names: &[&str], input: &ndarray::Array2<f32>| -> Result<ndarray::Array2<f32>, String> {
            for name in names {
                if let Ok(res) = self.project_matrix(name, input) {
                    return Ok(res);
                }
            }
            Err(format!("None of the tensors found: {:?}", names))
        };
        let rms_norm_rows = |xin: &ndarray::Array2<f32>, w: &ndarray::Array2<f32>| -> ndarray::Array2<f32> {
            let mut out = xin.clone();
            for i in 0..b {
                let mut sum_sq = 0.0;
                for j in 0..hidden_dim { sum_sq += xin[[i, j]] * xin[[i, j]]; }
                let rms = (sum_sq / (hidden_dim as f32) + norm_eps).sqrt();
                for j in 0..hidden_dim {
                    out[[i, j]] = (xin[[i, j]] / rms) * w[[i, j]];
                }
            }
            out
        };

        // 1. Pre-attn RMSNorm
        let attn_norm = project_any(&[
            &format!("model.layers.{}.input_layernorm.weight", layer)[..],
        ], &x)?;
        let x_norm = rms_norm_rows(&x, &attn_norm);

        // 2. QKV
        let mut q = project_any(&[&format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]], &x_norm)?;
        let k_res = project_any(&[&format!("model.layers.{}.self_attn.k_proj.weight", layer)[..]], &x_norm);
        let v_res = project_any(&[&format!("model.layers.{}.self_attn.v_proj.weight", layer)[..]], &x_norm);

        let computes_kv = g4.computes_kv(layer);
        let kv_src = g4.kv_source_layer(layer);

        // QK-norm (per-head, dim = head_dim for this layer)
        if let Some(w) = self.qk_norm_weight(layer, "q") {
            if w.len() == head_dim {
                Self::apply_head_rmsnorm(q.as_slice_mut().unwrap(), &w, head_dim);
            }
        }

        let attn_out = {
            let mut cache_opt = self.kv_cache.borrow_mut();
            if cache_opt.is_none() {
                return Err("KV Cache not initialized".to_string());
            }
            let cache = cache_opt.as_mut().unwrap();

            if computes_kv {
                let mut k = k_res?;
                let mut v = v_res?;
                if let Some(w) = self.qk_norm_weight(layer, "k") {
                    if w.len() == head_dim {
                        Self::apply_head_rmsnorm(k.as_slice_mut().unwrap(), &w, head_dim);
                    }
                }
                let q_slice = q.as_slice_mut().unwrap();
                let k_slice = k.as_slice_mut().unwrap();
                apply_rope_chunked_neox(
                    q_slice, k_slice, start_pos, b, num_heads, num_kv_heads, head_dim, rope_theta,
                );
                for i in 0..b {
                    let k_token = k.slice(ndarray::s![i, ..]).to_owned();
                    let v_token = v.slice(ndarray::s![i, ..]).to_owned();
                    cache.append_kv(layer, &k_token, &v_token);
                }
            } else {
                // Shared KV: still RoPE Q with this layer's theta/head_dim
                let q_slice = q.as_slice_mut().unwrap();
                // dummy k buffer for rope API (same layout as Q's kv width)
                let mut k_dummy = ndarray::Array2::<f32>::zeros((b, num_kv_heads * head_dim));
                let k_slice = k_dummy.as_slice_mut().unwrap();
                apply_rope_chunked_neox(
                    q_slice, k_slice, start_pos, b, num_heads, num_kv_heads, head_dim, rope_theta,
                );
            }

            let cache_k = &cache.k_cache[if computes_kv { layer } else { kv_src }];
            let cache_v = &cache.v_cache[if computes_kv { layer } else { kv_src }];
            if cache_k.shape()[0] == 0 {
                return Err(format!(
                    "gemma4 layer {}: empty KV cache (src={})",
                    layer, kv_src
                ));
            }
            // Shared layers may have different head_dim than source — require match
            let kv_dim = cache_k.shape()[1];
            if kv_dim != num_kv_heads * head_dim {
                return Err(format!(
                    "gemma4 layer {}: KV dim {} != expected {} (shared src {})",
                    layer, kv_dim, num_kv_heads * head_dim, kv_src
                ));
            }
            sdpa_chunked_windowed(
                &q, cache_k, cache_v, num_heads, num_kv_heads, head_dim, window,
            )
        };

        let o_proj = project_any(
            &[&format!("model.layers.{}.self_attn.o_proj.weight", layer)[..]],
            &attn_out,
        )?;
        // Post-attn norm on attention output (Gemma-style) then residual
        let post_attn_names = [
            &format!("model.layers.{}.post_self_attn_layernorm.weight", layer)[..],
        ];
        let attn_branch = if let Ok(w) = project_any(&post_attn_names, &o_proj) {
            rms_norm_rows(&o_proj, &w)
        } else {
            o_proj
        };
        x = x + attn_branch;

        // Pre-FFN norm
        let pre_ffn_names = [
            &format!("model.layers.{}.pre_feedforward_layernorm.weight", layer)[..],
            &format!("model.layers.{}.post_attention_layernorm.weight", layer)[..],
        ];
        let pre_ffn_w = project_any(&pre_ffn_names, &x)?;
        let x_ffn = rms_norm_rows(&x, &pre_ffn_w);

        let gate_names = [&format!("model.layers.{}.mlp.gate_proj.weight", layer)[..]];
        let up_names = [&format!("model.layers.{}.mlp.up_proj.weight", layer)[..]];
        let down_names = [&format!("model.layers.{}.mlp.down_proj.weight", layer)[..]];
        if let (Ok(mut gate), Ok(up)) = (project_any(&gate_names, &x_ffn), project_any(&up_names, &x_ffn)) {
            let flat_g = gate.as_slice_mut().unwrap();
            let flat_u = up.as_slice().unwrap();
            apply_geglu(flat_g, flat_u);
            if let Ok(mlp_out) = project_any(&down_names, &gate) {
                let post_ffn_names = [
                    &format!("model.layers.{}.post_feedforward_layernorm.weight", layer)[..],
                ];
                let mlp_branch = if let Ok(w) = project_any(&post_ffn_names, &mlp_out) {
                    rms_norm_rows(&mlp_out, &w)
                } else {
                    mlp_out
                };
                x = x + mlp_branch;
            }
        }

        // PLE residual (after MLP block)
        if let Some(ple_b) = ple {
            x = self.gemma4_apply_ple_chunked(layer, x, ple_b)?;
        }

        // Optional layer output scale (scalar Dense1D)
        let scale_name = format!("model.layers.{}.layer_output_scale.weight", layer);
        if let Some(meta) = self.tensors.get(scale_name.as_str()) {
            if let TensorType::Dense1D { length } = meta.tensor_type {
                if length >= 1 {
                    if let Some(raw) = self.get_raw_slice(&scale_name) {
                        let sc = f16::from_le_bytes([raw[0], raw[1]]).to_f32();
                        x.mapv_inplace(|v| v * sc);
                    }
                }
            }
        }

        Ok(x)
    }

    /// Gemma4 single-token decode layer (mirrors chunked encode topology).
    fn forward_gemma4_layer(
        &self,
        layer: usize,
        mut x: Array1<f32>,
        pos: usize,
        ple: Option<&Array1<f32>>,
    ) -> Result<Array1<f32>, String> {
        let g4 = self.gemma4.as_ref().ok_or("not gemma4")?;
        let norm_eps = 1e-6f32;
        let hidden_dim = x.len();
        let head_dim = g4.head_dim(layer);
        let num_heads = g4.num_heads;
        let num_kv_heads = g4.num_kv_heads;
        let rope_theta = g4.rope_theta(layer);
        let window = if g4.is_sliding(layer) {
            Some(g4.sliding_window)
        } else {
            None
        };

        let project_any = |names: &[&str], input: &Array1<f32>| -> Result<Array1<f32>, String> {
            for name in names {
                if let Ok(res) = self.project_vector(name, input) {
                    return Ok(res);
                }
            }
            Err(format!("None of the tensors found: {:?}", names))
        };
        let rms_norm = |xin: &Array1<f32>, w: &Array1<f32>| -> Array1<f32> {
            let mut sum_sq = 0.0f32;
            for &v in xin.iter() {
                sum_sq += v * v;
            }
            let rms = (sum_sq / (hidden_dim as f32) + norm_eps).sqrt();
            let mut out = xin.clone();
            for i in 0..hidden_dim {
                out[i] = (xin[i] / rms) * w[i];
            }
            out
        };

        let attn_norm = project_any(
            &[&format!("model.layers.{}.input_layernorm.weight", layer)[..]],
            &x,
        )?;
        let x_norm = rms_norm(&x, &attn_norm);

        let mut q = project_any(
            &[&format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]],
            &x_norm,
        )?;
        let k_res = project_any(
            &[&format!("model.layers.{}.self_attn.k_proj.weight", layer)[..]],
            &x_norm,
        );
        let v_res = project_any(
            &[&format!("model.layers.{}.self_attn.v_proj.weight", layer)[..]],
            &x_norm,
        );

        let computes_kv = g4.computes_kv(layer);
        let kv_src = g4.kv_source_layer(layer);

        if let Some(w) = self.qk_norm_weight(layer, "q") {
            if w.len() == head_dim {
                Self::apply_head_rmsnorm(q.as_slice_mut().unwrap(), &w, head_dim);
            }
        }

        let attn_out = {
            let mut cache_opt = self.kv_cache.borrow_mut();
            if cache_opt.is_none() {
                return Err("KV Cache not initialized".to_string());
            }
            let cache = cache_opt.as_mut().unwrap();

            if computes_kv {
                let mut k = k_res?;
                let mut v = v_res?;
                if let Some(w) = self.qk_norm_weight(layer, "k") {
                    if w.len() == head_dim {
                        Self::apply_head_rmsnorm(k.as_slice_mut().unwrap(), &w, head_dim);
                    }
                }
                apply_rope_neox(
                    q.as_slice_mut().unwrap(),
                    k.as_slice_mut().unwrap(),
                    pos,
                    num_heads,
                    num_kv_heads,
                    head_dim,
                    rope_theta,
                );
                cache.append_kv(layer, &k, &v);
            } else {
                let mut k_dummy = Array1::<f32>::zeros(num_kv_heads * head_dim);
                apply_rope_neox(
                    q.as_slice_mut().unwrap(),
                    k_dummy.as_slice_mut().unwrap(),
                    pos,
                    num_heads,
                    num_kv_heads,
                    head_dim,
                    rope_theta,
                );
            }

            let cache_k = &cache.k_cache[if computes_kv { layer } else { kv_src }];
            let cache_v = &cache.v_cache[if computes_kv { layer } else { kv_src }];
            if cache_k.shape()[0] == 0 {
                return Err(format!(
                    "gemma4 decode layer {}: empty KV cache (src={})",
                    layer, kv_src
                ));
            }
            let kv_dim = cache_k.shape()[1];
            if kv_dim != num_kv_heads * head_dim {
                return Err(format!(
                    "gemma4 decode layer {}: KV dim {} != expected {} (shared src {})",
                    layer, kv_dim, num_kv_heads * head_dim, kv_src
                ));
            }
            sdpa_gqa_windowed(
                &q, cache_k, cache_v, num_heads, num_kv_heads, head_dim, window,
            )
        };

        let o_proj = project_any(
            &[&format!("model.layers.{}.self_attn.o_proj.weight", layer)[..]],
            &attn_out,
        )?;
        let post_attn_names = [
            &format!("model.layers.{}.post_self_attn_layernorm.weight", layer)[..],
        ];
        let attn_branch = if let Ok(w) = project_any(&post_attn_names, &o_proj) {
            rms_norm(&o_proj, &w)
        } else {
            o_proj
        };
        x = x + attn_branch;

        let pre_ffn_names = [
            &format!("model.layers.{}.pre_feedforward_layernorm.weight", layer)[..],
            &format!("model.layers.{}.post_attention_layernorm.weight", layer)[..],
        ];
        let pre_ffn_w = project_any(&pre_ffn_names, &x)?;
        let x_ffn = rms_norm(&x, &pre_ffn_w);

        let gate_names = [&format!("model.layers.{}.mlp.gate_proj.weight", layer)[..]];
        let up_names = [&format!("model.layers.{}.mlp.up_proj.weight", layer)[..]];
        let down_names = [&format!("model.layers.{}.mlp.down_proj.weight", layer)[..]];
        if let (Ok(mut gate), Ok(up)) = (project_any(&gate_names, &x_ffn), project_any(&up_names, &x_ffn)) {
            let flat_g = gate.as_slice_mut().unwrap();
            let flat_u = up.as_slice().unwrap();
            apply_geglu(flat_g, flat_u);
            if let Ok(mlp_out) = project_any(&down_names, &gate) {
                let post_ffn_names = [
                    &format!("model.layers.{}.post_feedforward_layernorm.weight", layer)[..],
                ];
                let mlp_branch = if let Ok(w) = project_any(&post_ffn_names, &mlp_out) {
                    rms_norm(&mlp_out, &w)
                } else {
                    mlp_out
                };
                x = x + mlp_branch;
            }
        }

        if let Some(ple_v) = ple {
            x = self.gemma4_apply_ple_token(layer, x, ple_v)?;
        }

        let scale_name = format!("model.layers.{}.layer_output_scale.weight", layer);
        if let Some(meta) = self.tensors.get(scale_name.as_str()) {
            if let TensorType::Dense1D { length } = meta.tensor_type {
                if length >= 1 {
                    if let Some(raw) = self.get_raw_slice(&scale_name) {
                        let sc = f16::from_le_bytes([raw[0], raw[1]]).to_f32();
                        x.mapv_inplace(|v| v * sc);
                    }
                }
            }
        }

        Ok(x)
    }

    /// MoE MLP for a single (already post-attention-normed) token vector.
    /// Shared by the chunked prefill path; mirrors the logic in forward_transformer_layer.
    fn moe_mlp_single(&self, layer: usize, x_post_norm: &Array1<f32>) -> Result<Array1<f32>, String> {
        let project_any = |names: &[&str], input: &Array1<f32>| -> Result<Array1<f32>, String> {
            for name in names {
                if let Ok(res) = self.project_vector(name, input) {
                    return Ok(res);
                }
            }
            Err(format!("None of the layers found: {:?}", names))
        };
        let router_names = [&format!("model.layers.{}.mlp.gate.weight", layer)[..]];
        let mut scores = project_any(&router_names, x_post_norm)?;
        let bias_names = [&format!("model.layers.{}.mlp.gate.e_score_correction_bias", layer)[..]];
        if let Ok(bias) = project_any(&bias_names, x_post_norm) {
            for i in 0..scores.len() {
                scores[i] += bias[i];
            }
        }
        let k = self.moe_top_k.min(scores.len());
        let mut ranked: Vec<(usize, f32)> = scores.iter().enumerate().map(|(i, &s)| (i, s)).collect();
        ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let top: Vec<_> = ranked.into_iter().take(k).collect();

        let mut probs = vec![0.0f32; k];
        let mut sum = 0.0f32;
        if self.moe_softmax {
            let m = top.iter().map(|e| e.1).fold(f32::NEG_INFINITY, f32::max);
            for i in 0..k { probs[i] = (top[i].1 - m).exp(); sum += probs[i]; }
        } else {
            for i in 0..k { probs[i] = 1.0 / (1.0 + (-top[i].1).exp()); sum += probs[i]; }
        }
        for p in probs.iter_mut() { *p /= sum; }

        let mut moe_out = Array1::<f32>::zeros(x_post_norm.len());
        for (i, &(expert_idx, _)) in top.iter().enumerate() {
            self.record_expert_usage(layer, expert_idx);
            let gate_names = [&format!("model.layers.{}.mlp.experts.{}.gate_proj.weight", layer, expert_idx)[..]];
            let up_names = [&format!("model.layers.{}.mlp.experts.{}.up_proj.weight", layer, expert_idx)[..]];
            let down_names = [&format!("model.layers.{}.mlp.experts.{}.down_proj.weight", layer, expert_idx)[..]];
            if let (Ok(mut gate), Ok(up)) = (project_any(&gate_names, x_post_norm), project_any(&up_names, x_post_norm)) {
                for (j, val) in gate.iter_mut().enumerate() {
                    *val = swiglu(*val) * up[j];
                }
                if let Ok(down) = project_any(&down_names, &gate) {
                    for j in 0..moe_out.len() {
                        moe_out[j] += down[j] * probs[i];
                    }
                }
            }
        }
        // Shared expert (present in GLM/DeepSeek/Qwen2-MoE style models)
        let sg = [&format!("model.layers.{}.mlp.shared_experts.gate_proj.weight", layer)[..]];
        let su = [&format!("model.layers.{}.mlp.shared_experts.up_proj.weight", layer)[..]];
        let sd = [&format!("model.layers.{}.mlp.shared_experts.down_proj.weight", layer)[..]];
        if let (Ok(mut gate), Ok(up)) = (project_any(&sg, x_post_norm), project_any(&su, x_post_norm)) {
            for (j, val) in gate.iter_mut().enumerate() {
                *val = swiglu(*val) * up[j];
            }
            if let Ok(down) = project_any(&sd, &gate) {
                for j in 0..moe_out.len() {
                    moe_out[j] += down[j];
                }
            }
        }
        Ok(moe_out)
    }

    pub fn execute_worker_forward(&self, tokens: &[u32]) -> Result<Vec<f32>, String> {
        self.execute_worker_forward_soft(&[], tokens)
    }

    /// Forward pass with optional "soft tokens": raw embedding-space vectors
    /// (e.g. another agent's thought vector re-synthesized onto the token manifold)
    /// prepended as virtual tokens before the real token embeddings.
    /// This is the vector-communication entry point: no text mediation.
    pub fn execute_worker_forward_soft(&self, soft: &[Vec<f32>], tokens: &[u32]) -> Result<Vec<f32>, String> {
        if tokens.is_empty() && soft.is_empty() { return Err("Empty token list".to_string()); }

        if self.gpu_enabled() {
            match self.encode_gpu_batched(soft, tokens) {
                Ok(v) => return Ok(v),
                Err(e) => eprintln!("[JCross GPU] encode failed ({}), falling back to CPU", e),
            }
        }
        
        let num_layers = self.num_layers; 
        let num_heads = self.num_heads;
        let num_kv_heads = self.num_kv_heads;
        let head_dim = self.head_dim; 
        let rope_theta = self.rope_theta;
        
        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, num_kv_heads, head_dim, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }
        
        let chunk_size = 1024;
        let mut x_final = Vec::new();
        let mut pos = 0;
        let n_soft = soft.len();
        let total_len = n_soft + tokens.len();

        for chunk_start in (0..total_len).step_by(chunk_size) {
            let chunk_end = std::cmp::min(chunk_start + chunk_size, total_len);
            let b = chunk_end - chunk_start;
            
            println!("[Rust Worker] Processing chunk {}/{} (tokens {} to {})", chunk_start / chunk_size + 1, (total_len + chunk_size - 1) / chunk_size, chunk_start, chunk_end);
            
            let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
                .or_else(|| self.tensors.get("model.embed_tokens.weight"))
                .or_else(|| self.tensors.get("embed_tokens"))
                .ok_or_else(|| "embed_tokens not found".to_string())?;
                
            let c = match embed_meta.tensor_type {
                TensorType::Dense2D { cols, .. } => cols as usize,
                _ => return Err("embed_tokens must be Dense2D".to_string()),
            };

            let mut x_arr = ndarray::Array2::<f32>::zeros((b, c));
            let mut token_ids: Vec<Option<u32>> = Vec::with_capacity(b);
            
            for i in 0..b {
                let seq_idx = chunk_start + i;
                if seq_idx < n_soft {
                    // Virtual token: another agent's thought vector, injected directly
                    let vec = &soft[seq_idx];
                    if vec.len() != c { return Err(format!("Soft token dim {} != hidden {}", vec.len(), c)); }
                    for j in 0..c { x_arr[[i, j]] = vec[j]; }
                    token_ids.push(None);
                } else {
                    let token = tokens[seq_idx - n_soft];
                    let row_offset = (token as usize) * c * 2;
                    let raw_data = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + (c * 2)];
                    let mut offset = 0;
                    for j in 0..c {
                        let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                        x_arr[[i, j]] = f16::from_le_bytes(bytes).to_f32();
                        offset += 2;
                    }
                    token_ids.push(Some(token));
                }
            }

            // Gemma4: scale real token embeds by √hidden (soft vectors already live in act-space)
            let ple3 = if let Some(ref g4) = self.gemma4 {
                let esc = gemma4_embed_scale(c);
                for i in 0..b {
                    if token_ids[i].is_some() {
                        for j in 0..c {
                            x_arr[[i, j]] *= esc;
                        }
                    }
                }
                if !g4.ple_omitted {
                    Some(self.gemma4_build_ple(&x_arr, &token_ids)?)
                } else {
                    None
                }
            } else {
                None
            };

            for layer in 0..num_layers {
                if self.gemma4.is_some() {
                    let ple_l = ple3.as_ref().map(|p| p.slice(ndarray::s![.., layer, ..]).to_owned());
                    x_arr = self.forward_gemma4_layer_chunked(
                        layer, x_arr, pos, ple_l.as_ref(),
                    )?;
                } else {
                    x_arr = self.forward_transformer_layer_chunked(layer, x_arr, pos, rope_theta)?;
                }
            }
            
            let norm_names = ["model.language_model.norm.weight", "model.norm.weight"];
            let mut final_norm_w = None;
            for name in norm_names.iter() {
                if let Ok(w) = self.project_matrix(name, &x_arr) {
                    final_norm_w = Some(w);
                    break;
                }
            }
            let final_norm_w = final_norm_w.ok_or("Final norm not found")?;
            
            for i in 0..b {
                let mut sum_sq = 0.0;
                for j in 0..c { sum_sq += x_arr[[i, j]] * x_arr[[i, j]]; }
                let rms = (sum_sq / (c as f32) + 1e-6).sqrt();
                for j in 0..c { x_arr[[i, j]] = (x_arr[[i, j]] / rms) * final_norm_w[[i, j]]; }
            }
            
            if chunk_end == total_len {
                let last_token_row = x_arr.slice(ndarray::s![b - 1, ..]).to_owned();
                x_final = last_token_row.into_raw_vec();
            }
            
            pos += b;
        }
        
        Ok(x_final)
    }

    /// Hidden dim from embed_tokens columns.
    pub fn hidden_dim(&self) -> Result<usize, String> {
        let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
            .or_else(|| self.tensors.get("model.embed_tokens.weight"))
            .or_else(|| self.tensors.get("embed_tokens"))
            .ok_or_else(|| "embed_tokens not found".to_string())?;
        match embed_meta.tensor_type {
            TensorType::Dense2D { cols, .. } => Ok(cols as usize),
            _ => Err("embed_tokens must be Dense2D".to_string()),
        }
    }

    /// CPU-only forward that snapshots last-token residual after selected layers.
    /// Layer index `num_layers` means "after final RMS norm" (same space as `encode`).
    /// Requested layers must be unique and in ascending order is not required; results
    /// are returned in the same order as `layers`.
    pub fn execute_worker_forward_layers(
        &self,
        soft: &[Vec<f32>],
        tokens: &[u32],
        layers: &[usize],
    ) -> Result<Vec<Vec<f32>>, String> {
        if tokens.is_empty() && soft.is_empty() {
            return Err("Empty token list".to_string());
        }
        if layers.is_empty() {
            return Err("No layers requested".to_string());
        }
        for &l in layers {
            if l > self.num_layers {
                return Err(format!("layer {} out of range 0..={}", l, self.num_layers));
            }
        }

        let num_layers = self.num_layers;
        let num_heads = self.num_heads;
        let num_kv_heads = self.num_kv_heads;
        let head_dim = self.head_dim;
        let rope_theta = self.rope_theta;
        let c = self.hidden_dim()?;

        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, num_kv_heads, head_dim, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }

        let n_soft = soft.len();
        let total_len = n_soft + tokens.len();
        let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
            .or_else(|| self.tensors.get("model.embed_tokens.weight"))
            .or_else(|| self.tensors.get("embed_tokens"))
            .ok_or_else(|| "embed_tokens not found".to_string())?;

        let mut x_arr = ndarray::Array2::<f32>::zeros((total_len, c));
        let mut token_ids: Vec<Option<u32>> = Vec::with_capacity(total_len);
        for i in 0..total_len {
            if i < n_soft {
                let vec = &soft[i];
                if vec.len() != c {
                    return Err(format!("Soft token dim {} != hidden {}", vec.len(), c));
                }
                for j in 0..c { x_arr[[i, j]] = vec[j]; }
                token_ids.push(None);
            } else {
                let token = tokens[i - n_soft];
                let row_offset = (token as usize) * c * 2;
                let raw_data = &self.mmap[embed_meta.offset + row_offset
                    .. embed_meta.offset + row_offset + (c * 2)];
                let mut offset = 0;
                for j in 0..c {
                    let bytes: [u8; 2] = [raw_data[offset], raw_data[offset + 1]];
                    x_arr[[i, j]] = f16::from_le_bytes(bytes).to_f32();
                    offset += 2;
                }
                token_ids.push(Some(token));
            }
        }

        let ple3 = if let Some(ref g4) = self.gemma4 {
            let esc = gemma4_embed_scale(c);
            for i in 0..total_len {
                if token_ids[i].is_some() {
                    for j in 0..c {
                        x_arr[[i, j]] *= esc;
                    }
                }
            }
            if !g4.ple_omitted {
                Some(self.gemma4_build_ple(&x_arr, &token_ids)?)
            } else {
                None
            }
        } else {
            None
        };

        let want_final = layers.iter().any(|&l| l == num_layers);
        let mut snapshots: HashMap<usize, Vec<f32>> = HashMap::new();

        for layer in 0..num_layers {
            if self.gemma4.is_some() {
                let ple_l = ple3.as_ref().map(|p| p.slice(ndarray::s![.., layer, ..]).to_owned());
                x_arr = self.forward_gemma4_layer_chunked(layer, x_arr, 0, ple_l.as_ref())?;
            } else {
                x_arr = self.forward_transformer_layer_chunked(layer, x_arr, 0, rope_theta)?;
            }
            if layers.iter().any(|&l| l == layer) {
                let last = x_arr.slice(ndarray::s![total_len - 1, ..]).to_owned();
                snapshots.insert(layer, last.into_raw_vec());
            }
        }

        if want_final {
            let norm_names = ["model.language_model.norm.weight", "model.norm.weight"];
            let mut final_norm_w = None;
            for name in norm_names.iter() {
                if let Ok(w) = self.project_matrix(name, &x_arr) {
                    final_norm_w = Some(w);
                    break;
                }
            }
            let final_norm_w = final_norm_w.ok_or("Final norm not found")?;
            let mut x_norm = x_arr.clone();
            for i in 0..total_len {
                let mut sum_sq = 0.0;
                for j in 0..c { sum_sq += x_norm[[i, j]] * x_norm[[i, j]]; }
                let rms = (sum_sq / (c as f32) + 1e-6).sqrt();
                for j in 0..c {
                    x_norm[[i, j]] = (x_norm[[i, j]] / rms) * final_norm_w[[i, j]];
                }
            }
            let last = x_norm.slice(ndarray::s![total_len - 1, ..]).to_owned();
            snapshots.insert(num_layers, last.into_raw_vec());
        }

        let mut out = Vec::with_capacity(layers.len());
        for &l in layers {
            out.push(snapshots.get(&l).cloned()
                .ok_or_else(|| format!("missing snapshot for layer {}", l))?);
        }
        Ok(out)
    }

    /// Inject (blend) a hidden vector into the residual stream *before* `inject_layer`,
    /// then continue through remaining layers + final norm. Returns final-norm last token.
    /// `alpha`: out = (1-alpha)*x + alpha*inject (at last position).
    pub fn execute_inject_at_layer(
        &self,
        soft: &[Vec<f32>],
        tokens: &[u32],
        inject_layer: usize,
        inject: &[f32],
        alpha: f32,
    ) -> Result<Vec<f32>, String> {
        if tokens.is_empty() && soft.is_empty() {
            return Err("Empty token list".to_string());
        }
        if inject_layer > self.num_layers {
            return Err(format!("inject_layer {} out of range 0..={}", inject_layer, self.num_layers));
        }
        let c = self.hidden_dim()?;
        if inject.len() != c {
            return Err(format!("inject dim {} != hidden {}", inject.len(), c));
        }

        let num_layers = self.num_layers;
        let num_heads = self.num_heads;
        let num_kv_heads = self.num_kv_heads;
        let head_dim = self.head_dim;
        let rope_theta = self.rope_theta;

        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, num_kv_heads, head_dim, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }

        let n_soft = soft.len();
        let total_len = n_soft + tokens.len();
        let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
            .or_else(|| self.tensors.get("model.embed_tokens.weight"))
            .or_else(|| self.tensors.get("embed_tokens"))
            .ok_or_else(|| "embed_tokens not found".to_string())?;

        let mut x_arr = ndarray::Array2::<f32>::zeros((total_len, c));
        let mut token_ids: Vec<Option<u32>> = Vec::with_capacity(total_len);
        for i in 0..total_len {
            if i < n_soft {
                let vec = &soft[i];
                if vec.len() != c {
                    return Err(format!("Soft token dim {} != hidden {}", vec.len(), c));
                }
                for j in 0..c { x_arr[[i, j]] = vec[j]; }
                token_ids.push(None);
            } else {
                let token = tokens[i - n_soft];
                let row_offset = (token as usize) * c * 2;
                let raw_data = &self.mmap[embed_meta.offset + row_offset
                    .. embed_meta.offset + row_offset + (c * 2)];
                let mut offset = 0;
                for j in 0..c {
                    let bytes: [u8; 2] = [raw_data[offset], raw_data[offset + 1]];
                    x_arr[[i, j]] = f16::from_le_bytes(bytes).to_f32();
                    offset += 2;
                }
                token_ids.push(Some(token));
            }
        }

        let ple3 = if let Some(ref g4) = self.gemma4 {
            let esc = gemma4_embed_scale(c);
            for i in 0..total_len {
                if token_ids[i].is_some() {
                    for j in 0..c {
                        x_arr[[i, j]] *= esc;
                    }
                }
            }
            if !g4.ple_omitted {
                Some(self.gemma4_build_ple(&x_arr, &token_ids)?)
            } else {
                None
            }
        } else {
            None
        };

        let last = total_len - 1;
        let a = alpha.clamp(0.0, 1.0);

        // Inject before layer 0 means blend into embeddings.
        if inject_layer == 0 {
            for j in 0..c {
                x_arr[[last, j]] = (1.0 - a) * x_arr[[last, j]] + a * inject[j];
            }
        }

        for layer in 0..num_layers {
            if inject_layer > 0 && layer == inject_layer {
                for j in 0..c {
                    x_arr[[last, j]] = (1.0 - a) * x_arr[[last, j]] + a * inject[j];
                }
            }
            if self.gemma4.is_some() {
                let ple_l = ple3.as_ref().map(|p| p.slice(ndarray::s![.., layer, ..]).to_owned());
                x_arr = self.forward_gemma4_layer_chunked(layer, x_arr, 0, ple_l.as_ref())?;
            } else {
                x_arr = self.forward_transformer_layer_chunked(layer, x_arr, 0, rope_theta)?;
            }
        }

        // Inject after all layers (into pre-norm residual), then final-norm.
        if inject_layer == num_layers {
            for j in 0..c {
                x_arr[[last, j]] = (1.0 - a) * x_arr[[last, j]] + a * inject[j];
            }
        }

        let norm_names = ["model.language_model.norm.weight", "model.norm.weight"];
        let mut final_norm_w = None;
        for name in norm_names.iter() {
            if let Ok(w) = self.project_matrix(name, &x_arr) {
                final_norm_w = Some(w);
                break;
            }
        }
        let final_norm_w = final_norm_w.ok_or("Final norm not found")?;
        for i in 0..total_len {
            let mut sum_sq = 0.0;
            for j in 0..c { sum_sq += x_arr[[i, j]] * x_arr[[i, j]]; }
            let rms = (sum_sq / (c as f32) + 1e-6).sqrt();
            for j in 0..c {
                x_arr[[i, j]] = (x_arr[[i, j]] / rms) * final_norm_w[[i, j]];
            }
        }
        let last_row = x_arr.slice(ndarray::s![last, ..]).to_owned();
        Ok(last_row.into_raw_vec())
    }

    /// Milestone P: blend MULTIPLE (layer, vector, alpha) injections into ONE
    /// forward pass, and snapshot the residual at each requested observe
    /// layer -- combines `execute_worker_forward_layers`'s snapshot HashMap
    /// with `execute_inject_at_layer`'s blend, in the same `for layer in
    /// 0..num_layers` loop (no extra passes, no KV-cache changes needed:
    /// this is the same non-cached CPU-chunked path both existing methods
    /// already use).
    ///
    /// Semantics are inherited verbatim from each existing method rather
    /// than invented fresh, since the two disagree on what "layer 0" means
    /// and unifying them silently would be a real behavior change:
    ///   - `inject_layers`: PRE-layer blend, exactly like
    ///     `execute_inject_at_layer` (layer 0 = raw embedding, before layer
    ///     0 runs; layer == num_layers = after the last layer, before final
    ///     norm).
    ///   - `observe_layers`: POST-layer snapshot, exactly like
    ///     `execute_worker_forward_layers` (layer L = residual right after
    ///     layer L has run; layer == num_layers = after final norm).
    pub fn execute_inject_multi_layer(
        &self,
        soft: &[Vec<f32>],
        tokens: &[u32],
        inject_layers: &[usize],
        inject_vecs: &[Vec<f32>],
        alphas: &[f32],
        observe_layers: &[usize],
    ) -> Result<HashMap<usize, Vec<f32>>, String> {
        if tokens.is_empty() && soft.is_empty() {
            return Err("Empty token list".to_string());
        }
        if inject_layers.len() != inject_vecs.len() || inject_layers.len() != alphas.len() {
            return Err("inject_layers/inject_vecs/alphas length mismatch".to_string());
        }
        let num_layers = self.num_layers;
        for &l in inject_layers.iter().chain(observe_layers.iter()) {
            if l > num_layers {
                return Err(format!("layer {} out of range 0..={}", l, num_layers));
            }
        }
        let c = self.hidden_dim()?;
        for v in inject_vecs {
            if v.len() != c {
                return Err(format!("inject dim {} != hidden {}", v.len(), c));
            }
        }

        let num_kv_heads = self.num_kv_heads;
        let head_dim = self.head_dim;
        let rope_theta = self.rope_theta;

        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, num_kv_heads, head_dim, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }

        let n_soft = soft.len();
        let total_len = n_soft + tokens.len();
        let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
            .or_else(|| self.tensors.get("model.embed_tokens.weight"))
            .or_else(|| self.tensors.get("embed_tokens"))
            .ok_or_else(|| "embed_tokens not found".to_string())?;

        let mut x_arr = ndarray::Array2::<f32>::zeros((total_len, c));
        let mut token_ids: Vec<Option<u32>> = Vec::with_capacity(total_len);
        for i in 0..total_len {
            if i < n_soft {
                let vec = &soft[i];
                if vec.len() != c {
                    return Err(format!("Soft token dim {} != hidden {}", vec.len(), c));
                }
                for j in 0..c { x_arr[[i, j]] = vec[j]; }
                token_ids.push(None);
            } else {
                let token = tokens[i - n_soft];
                let row_offset = (token as usize) * c * 2;
                let raw_data = &self.mmap[embed_meta.offset + row_offset
                    .. embed_meta.offset + row_offset + (c * 2)];
                let mut offset = 0;
                for j in 0..c {
                    let bytes: [u8; 2] = [raw_data[offset], raw_data[offset + 1]];
                    x_arr[[i, j]] = f16::from_le_bytes(bytes).to_f32();
                    offset += 2;
                }
                token_ids.push(Some(token));
            }
        }

        let ple3 = if let Some(ref g4) = self.gemma4 {
            let esc = gemma4_embed_scale(c);
            for i in 0..total_len {
                if token_ids[i].is_some() {
                    for j in 0..c {
                        x_arr[[i, j]] *= esc;
                    }
                }
            }
            if !g4.ple_omitted {
                Some(self.gemma4_build_ple(&x_arr, &token_ids)?)
            } else {
                None
            }
        } else {
            None
        };

        let last = total_len - 1;
        let inject_map: HashMap<usize, (&Vec<f32>, f32)> = inject_layers.iter().enumerate()
            .map(|(i, &l)| (l, (&inject_vecs[i], alphas[i].clamp(0.0, 1.0))))
            .collect();

        // Inject before layer 0 means blend into embeddings (matches
        // execute_inject_at_layer's own inject_layer==0 special case).
        if let Some(&(vec, a)) = inject_map.get(&0) {
            for j in 0..c {
                x_arr[[last, j]] = (1.0 - a) * x_arr[[last, j]] + a * vec[j];
            }
        }

        let mut snapshots: HashMap<usize, Vec<f32>> = HashMap::new();

        for layer in 0..num_layers {
            if layer > 0 {
                if let Some(&(vec, a)) = inject_map.get(&layer) {
                    for j in 0..c {
                        x_arr[[last, j]] = (1.0 - a) * x_arr[[last, j]] + a * vec[j];
                    }
                }
            }
            if self.gemma4.is_some() {
                let ple_l = ple3.as_ref().map(|p| p.slice(ndarray::s![.., layer, ..]).to_owned());
                x_arr = self.forward_gemma4_layer_chunked(layer, x_arr, 0, ple_l.as_ref())?;
            } else {
                x_arr = self.forward_transformer_layer_chunked(layer, x_arr, 0, rope_theta)?;
            }
            if observe_layers.iter().any(|&l| l == layer) {
                snapshots.insert(layer, x_arr.slice(ndarray::s![last, ..]).to_owned().into_raw_vec());
            }
        }

        // Inject after all layers (into pre-norm residual), matching
        // execute_inject_at_layer's inject_layer==num_layers case.
        if let Some(&(vec, a)) = inject_map.get(&num_layers) {
            for j in 0..c {
                x_arr[[last, j]] = (1.0 - a) * x_arr[[last, j]] + a * vec[j];
            }
        }

        if observe_layers.iter().any(|&l| l == num_layers) {
            let norm_names = ["model.language_model.norm.weight", "model.norm.weight"];
            let mut final_norm_w = None;
            for name in norm_names.iter() {
                if let Ok(w) = self.project_matrix(name, &x_arr) {
                    final_norm_w = Some(w);
                    break;
                }
            }
            let final_norm_w = final_norm_w.ok_or("Final norm not found")?;
            let mut x_norm = x_arr.clone();
            for i in 0..total_len {
                let mut sum_sq = 0.0;
                for j in 0..c { sum_sq += x_norm[[i, j]] * x_norm[[i, j]]; }
                let rms = (sum_sq / (c as f32) + 1e-6).sqrt();
                for j in 0..c {
                    x_norm[[i, j]] = (x_norm[[i, j]] / rms) * final_norm_w[[i, j]];
                }
            }
            snapshots.insert(num_layers, x_norm.slice(ndarray::s![last, ..]).to_owned().into_raw_vec());
        }

        Ok(snapshots)
    }

    /// Public wrapper over `load_token_embed`, for callers that just need a
    /// raw input-embedding row (e.g. soft-token sequence construction) rather
    /// than a full forward pass.
    pub fn embedding_row(&self, token: u32) -> Result<Vec<f32>, String> {
        self.load_token_embed(token).map(|a| a.into_raw_vec())
    }

    /// Embed one token (fp16 row) and optionally apply Gemma4 √hidden scale.
    fn load_token_embed(&self, token: u32) -> Result<Array1<f32>, String> {
        let row = self.read_dense2d_row("embed_tokens", token as usize)
            .or_else(|_| self.read_dense2d_row("model.embed_tokens.weight", token as usize))
            .or_else(|_| self.read_dense2d_row("model.language_model.embed_tokens.weight", token as usize))?;
        let mut x = Array1::from_vec(row);
        if self.gemma4.is_some() {
            let esc = gemma4_embed_scale(x.len());
            x.mapv_inplace(|v| v * esc);
        }
        Ok(x)
    }

    /// Run all transformer layers for one token; Gemma4 path includes PLE.
    fn forward_all_layers_token(
        &self,
        mut x: Array1<f32>,
        token: u32,
        pos: usize,
        rope_theta: f32,
    ) -> Result<Array1<f32>, String> {
        let ple_tok = if let Some(ref g4) = self.gemma4 {
            if !g4.ple_omitted {
                let emb2 = x.clone().into_shape((1, x.len())).map_err(|e| e.to_string())?;
                let ple3 = self.gemma4_build_ple(&emb2, &[Some(token)])?;
                Some(ple3)
            } else {
                None
            }
        } else {
            None
        };
        for layer in 0..self.num_layers {
            if self.gemma4.is_some() {
                let ple_l = ple_tok.as_ref().map(|p| {
                    let mut v = Array1::<f32>::zeros(p.shape()[2]);
                    for d in 0..p.shape()[2] {
                        v[d] = p[[0, layer, d]];
                    }
                    v
                });
                x = self.forward_gemma4_layer(layer, x, pos, ple_l.as_ref())?;
            } else {
                x = self.forward_transformer_layer(layer, x, pos, rope_theta)?;
            }
        }
        Ok(x)
    }

    /// Whether the batched GPU path is used (Metal/CUDA device present, JCROSS_GPU!=0).
    /// Gemma4 uses the gemma4-aware GPU kernels (SWA / shared-KV / GeGLU / PLE).
    pub fn gpu_enabled(&self) -> bool {
        let dev_ok = !matches!(self.candle_device, Device::Cpu);
        dev_ok && std::env::var("JCROSS_GPU").map(|v| v != "0").unwrap_or(true)
    }

    pub fn execute_generation_loop(&self, prompt: &[u32], max_tokens: usize) -> Result<Vec<u32>, String> {
        if self.gpu_enabled() {
            match self.generate_gpu_batched(prompt, max_tokens) {
                Ok(v) => return Ok(v),
                Err(e) => eprintln!("[JCross GPU] generate failed ({}), falling back to CPU", e),
            }
        }
        let num_layers = self.num_layers;
        let num_heads = self.num_heads;
        let num_kv_heads = self.num_kv_heads;
        let head_dim = self.head_dim;
        let rope_theta = self.rope_theta;
        let mut generated = Vec::new();
        
        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, num_kv_heads, head_dim, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }
        
        let mut current_token = prompt[0];
        let mut pos = 0;
        
        // Prefill (consume all but last prompt token into KV; last is decoded in loop)
        for (i, &token) in prompt.iter().enumerate() {
            if i > 0 {
                let x = self.load_token_embed(current_token)?;
                let _ = self.forward_all_layers_token(x, current_token, pos, rope_theta)?;
                if i % 1 == 0 {
                    println!("[Prefill Token {}/{}] pos={}", i + 1, prompt.len(), pos);
                }
                current_token = token;
                pos += 1;
            }
        }
        
        for step in 0..max_tokens {
            println!("[Coder] Generating token {}/{} (pos: {})", step + 1, max_tokens, pos);
            use std::io::Write;
            let _ = std::io::stdout().flush();
            
            // 🔥 Temporal Lookahead Prefetching
            // Trigger background OS page-ins for the experts that were active in the previous token
            if let Ok(pc) = self.prefetch_cache.try_borrow() {
                for layer in 0..num_layers {
                    if let Some(experts) = pc.get(&(layer as usize)) {
                        for &expert_idx in experts {
                            let names = [
                                format!("model.layers.{}.mlp.experts.{}.gate_proj.weight", layer, expert_idx),
                                format!("model.layers.{}.mlp.experts.{}.up_proj.weight", layer, expert_idx),
                                format!("model.layers.{}.mlp.experts.{}.down_proj.weight", layer, expert_idx),
                            ];
                            for name in names.iter() {
                                if let Some(meta) = self.tensors.get(name) {
                                    crate::prefetch::prefetch_tensor_async(self.mmap.as_ptr() as usize, meta.offset, meta.byte_length, name.clone());
                                }
                            }
                        }
                    }
                }
            }
            

            let mut x = self.load_token_embed(current_token)?;
            x = self.forward_all_layers_token(x, current_token, pos, rope_theta)?;
            
            let norm_names = ["model.language_model.norm.weight", "model.norm.weight"];
            let mut final_norm_w = None;
            for name in norm_names.iter() {
                if let Ok(w) = self.project_vector(name, &x) {
                    final_norm_w = Some(w);
                    break;
                }
            }
            let final_norm_w = final_norm_w.ok_or("Final norm not found")?;
            
            let mut sum_sq = 0.0;
            for &val in x.iter() { sum_sq += val * val; }
            let rms = (sum_sq / (x.len() as f32) + 1e-6).sqrt();
            for (i, val) in x.iter_mut().enumerate() { *val = (*val / rms) * final_norm_w[i]; }
            
            let mut logits_vec = self.execute_dense_projection("lm_head", x.as_slice().unwrap())?;
            if let Some(ref g4) = self.gemma4 {
                softcap_logits(&mut logits_vec, g4.final_logit_softcapping);
            }
            if step % 10 == 0 && step > 0 {
                self.promote_hot_experts(5); // Promote if used 5 times or more
            }
            
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
            
            if self.eos_tokens.contains(&next_token) {
                break;
            }
        }
        
        Ok(generated)
    }
}

use std::ffi::CStr;
use std::os::raw::{c_char, c_float, c_void};

/// Exposes the engine creation over C-ABI
#[no_mangle]
pub extern "C" fn jcross_engine_create(path: *const c_char) -> *mut c_void {
    if path.is_null() { return std::ptr::null_mut(); }
    let c_str = unsafe { CStr::from_ptr(path) };
    let path_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return std::ptr::null_mut(),
    };

    match JCrossEngine::load_jgen(path_str) {
        Ok(engine) => Box::into_raw(Box::new(engine)) as *mut c_void,
        Err(e) => {
            eprintln!("[JCross] load_jgen failed for {}: {}", path_str, e);
            std::ptr::null_mut()
        },
    }
}

/// Exposes the SVD projection over C-ABI
#[no_mangle]
pub extern "C" fn jcross_engine_project(
    engine_ptr: *mut c_void,
    layer_name: *const c_char,
    input_ptr: *const c_float,
    input_len: usize,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || layer_name.is_null() || input_ptr.is_null() || out_ptr.is_null() {
        return -1; // Null pointer error
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    
    let c_str = unsafe { CStr::from_ptr(layer_name) };
    let layer_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -2, // Encoding error
    };

    let input_slice = unsafe { std::slice::from_raw_parts(input_ptr, input_len) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };

    match engine.execute_svd_projection(layer_str, input_slice) {
        Ok(result) => {
            if result.len() != out_len {
                return -3; // Out buffer size mismatch
            }
            out_slice.copy_from_slice(&result);
            0 // Success
        },
        Err(e) => {
            eprintln!("[Rust Engine] Projection execution error: {}", e);
            -4
        },
    }
}

#[no_mangle]
pub extern "C" fn jcross_engine_destroy(engine_ptr: *mut c_void) {
    if !engine_ptr.is_null() {
        unsafe {
            drop(Box::from_raw(engine_ptr as *mut JCrossEngine));
        }
    }
}

/// Resets the KV-cache so the engine can be reused for a fresh generation.
/// Must be called before each independent jcross_engine_generate invocation
/// (e.g. between Think and Speak phases, or between turns in a REPL).
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_reset(engine_ptr: *mut c_void) {
    if engine_ptr.is_null() { return; }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    *engine.kv_cache.borrow_mut()       = None;
    *engine.metal_kv_cache.borrow_mut() = None;
    let n = engine.num_layers;
    *engine.gpu_kv.borrow_mut() = vec![(None, None); n];
}

/// Releases all composed weight caches (CPU f32 + GPU) and the KV cache,
/// dropping the engine's RAM footprint back to ~mmap only. Weights are
/// recomposed lazily on next use. Call from Python between turns when the
/// MemoryGuard reports pressure.
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_trim(engine_ptr: *mut c_void) {
    if engine_ptr.is_null() { return; }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    *engine.kv_cache.borrow_mut()       = None;
    *engine.metal_kv_cache.borrow_mut() = None;
    let n = engine.num_layers;
    *engine.gpu_kv.borrow_mut() = vec![(None, None); n];
    engine.cpu_tensors_f32.borrow_mut().clear();
    engine.cpu_vectors_f32.borrow_mut().clear();
    *engine.cpu_cache_bytes.borrow_mut() = 0;
    engine.gpu_weight_cache.borrow_mut().clear();
    engine.gpu_cache_order.borrow_mut().clear();
    *engine.gpu_cache_bytes.borrow_mut() = 0;
    engine.l1_cache.borrow_mut().shrink_to_fit();
}

/// Exposes the SVD projection over C-ABI
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_resynthesize(
    engine_ptr: *mut c_void,
    layer_name: *const c_char,
    input_ptr: *const c_float,
    input_len: usize,
    temperature: c_float,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || layer_name.is_null() || input_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    
    let c_str = unsafe { CStr::from_ptr(layer_name) };
    let layer_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let input_slice = unsafe { std::slice::from_raw_parts(input_ptr, input_len) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };

    match engine.execute_telepathic_resonance(layer_str, input_slice, temperature) {
        Ok(result) => {
            if result.len() != out_len {
                return -3;
            }
            out_slice.copy_from_slice(&result);
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] Resonance error: {}", e);
            -4
        },
    }
}

/// Exposes the Puzzle Inference (Entropy lock) over C-ABI
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_puzzle_inference(
    engine_ptr: *mut c_void,
    layer_name: *const c_char,
    input_ptr: *const c_float,
    input_len: usize,
    out_token: *mut u32,
    out_entropy: *mut c_float,
) -> i32 {
    if engine_ptr.is_null() || layer_name.is_null() || input_ptr.is_null() || out_token.is_null() || out_entropy.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    
    let c_str = unsafe { CStr::from_ptr(layer_name) };
    let layer_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let input_slice = unsafe { std::slice::from_raw_parts(input_ptr, input_len) };

    match engine.execute_puzzle_inference(layer_str, input_slice) {
        Ok((token, entropy)) => {
            unsafe {
                *out_token = token;
                *out_entropy = entropy;
            }
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] Puzzle Inference error: {}", e);
            -4
        },
    }
}

/// Exposes the full top-K vocabulary distribution over C-ABI. Caller must
/// allocate `out_token_ids`/`out_probs` with capacity `k`; `out_count`
/// receives how many entries were actually written (<= k, e.g. if the
/// vocabulary itself is smaller than k).
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_topk_distribution(
    engine_ptr: *mut c_void,
    layer_name: *const c_char,
    input_ptr: *const c_float,
    input_len: usize,
    k: usize,
    out_token_ids: *mut u32,
    out_probs: *mut c_float,
    out_count: *mut usize,
) -> i32 {
    if engine_ptr.is_null() || layer_name.is_null() || input_ptr.is_null()
        || out_token_ids.is_null() || out_probs.is_null() || out_count.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };

    let c_str = unsafe { CStr::from_ptr(layer_name) };
    let layer_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let input_slice = unsafe { std::slice::from_raw_parts(input_ptr, input_len) };

    match engine.execute_topk_distribution(layer_str, input_slice, k) {
        Ok(result) => {
            if result.len() > k {
                return -3;
            }
            let out_ids = unsafe { std::slice::from_raw_parts_mut(out_token_ids, k) };
            let out_p = unsafe { std::slice::from_raw_parts_mut(out_probs, k) };
            for (i, (tok, prob)) in result.iter().enumerate() {
                out_ids[i] = *tok;
                out_p[i] = *prob;
            }
            unsafe { *out_count = result.len(); }
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] TopK distribution error: {}", e);
            -4
        },
    }
}

/// Exposes a single token's input-embedding row over C-ABI (for soft-token
/// sequence construction -- `dist_to_soft_sequence`-style callers need the
/// raw embedding row of arbitrary candidate token ids, not a forward pass).
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_embedding_row(
    engine_ptr: *mut c_void,
    token_id: u32,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };

    match engine.embedding_row(token_id) {
        Ok(row) => {
            if row.len() != out_len {
                return -3;
            }
            let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };
            out_slice.copy_from_slice(&row);
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] Embedding row error: {}", e);
            -4
        },
    }
}

/// Exposes the True Puzzle Inference (Latent Gradient Descent) over C-ABI
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_optimize_thought_in_place(
    engine_ptr: *mut c_void,
    layer_name: *const c_char,
    input_ptr: *mut c_float,
    input_len: usize,
    max_steps: usize,
    lr: c_float,
    temperature: c_float,
    out_entropy: *mut c_float,
) -> i32 {
    if engine_ptr.is_null() || layer_name.is_null() || input_ptr.is_null() || out_entropy.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    
    let c_str = unsafe { CStr::from_ptr(layer_name) };
    let layer_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let input_slice = unsafe { std::slice::from_raw_parts_mut(input_ptr, input_len) };

    match engine.optimize_thought_in_place(layer_str, input_slice, max_steps, lr, temperature) {
        Ok(entropy) => {
            unsafe {
                *out_entropy = entropy;
            }
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] Latent Gradient Descent error: {}", e);
            -4
        },
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_generate(
    engine_ptr: *mut c_void,
    prompt_ptr: *const u32,
    prompt_len: usize,
    max_tokens: usize,
    out_ptr: *mut u32,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || prompt_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    let prompt_slice = unsafe { std::slice::from_raw_parts(prompt_ptr, prompt_len) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };

    match engine.execute_generation_loop(prompt_slice, max_tokens) {
        Ok(generated) => {
            let copy_len = std::cmp::min(generated.len(), out_len);
            out_slice[..copy_len].copy_from_slice(&generated[..copy_len]);
            copy_len as i32
        },
        Err(e) => {
            eprintln!("[Rust Engine] Generation error: {}", e);
            -2
        },
    }
}

/// Vector-communication encode: prepends `n_soft` embedding-space vectors
/// (soft_ptr, row-major n_soft x hidden) as virtual tokens before the prompt.
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_encode_soft(
    engine_ptr: *mut c_void,
    soft_ptr: *const c_float,
    n_soft: usize,
    hidden: usize,
    tokens_ptr: *const u32,
    tokens_len: usize,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    let soft: Vec<Vec<f32>> = if n_soft > 0 && !soft_ptr.is_null() {
        let flat = unsafe { std::slice::from_raw_parts(soft_ptr, n_soft * hidden) };
        (0..n_soft).map(|i| flat[i * hidden..(i + 1) * hidden].to_vec()).collect()
    } else {
        Vec::new()
    };
    let tokens_slice = if tokens_len > 0 && !tokens_ptr.is_null() {
        unsafe { std::slice::from_raw_parts(tokens_ptr, tokens_len) }
    } else {
        &[]
    };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };
    match engine.execute_worker_forward_soft(&soft, tokens_slice) {
        Ok(vector) => {
            if vector.len() != out_len {
                eprintln!("[Rust Engine] Dimension mismatch: expected {}, got {}", out_len, vector.len());
                return -3;
            }
            out_slice.copy_from_slice(&vector);
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] Encode-soft error: {}", e);
            -2
        },
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_encode(
    engine_ptr: *mut c_void,
    tokens_ptr: *const u32,
    tokens_len: usize,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || tokens_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    let tokens_slice = unsafe { std::slice::from_raw_parts(tokens_ptr, tokens_len) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };

    match engine.execute_worker_forward(tokens_slice) {
        Ok(vector) => {
            if vector.len() != out_len {
                eprintln!("[Rust Engine] Dimension mismatch: expected {}, got {}", out_len, vector.len());
                return -3; // Output dimension mismatch
            }
            out_slice.copy_from_slice(&vector);
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] Encode error: {}", e);
            -2
        },
    }
}

/// Returns hidden dim (>0) or negative error.
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_hidden_dim(engine_ptr: *mut c_void) -> i32 {
    if engine_ptr.is_null() { return -1; }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    match engine.hidden_dim() {
        Ok(d) => d as i32,
        Err(_) => -2,
    }
}

/// Returns number of transformer layers.
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_num_layers(engine_ptr: *mut c_void) -> i32 {
    if engine_ptr.is_null() { return -1; }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    engine.num_layers as i32
}

/// Dump last-token hidden after each requested layer.
/// `layers_ptr` holds n_layers indices; index == num_layers means post-final-norm.
/// `out_ptr` must hold n_layers * hidden floats (row-major, same order as layers).
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_encode_layers(
    engine_ptr: *mut c_void,
    tokens_ptr: *const u32,
    tokens_len: usize,
    layers_ptr: *const u32,
    n_layers: usize,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || tokens_ptr.is_null() || layers_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }
    if n_layers == 0 { return -1; }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    let tokens = unsafe { std::slice::from_raw_parts(tokens_ptr, tokens_len) };
    let layers_u32 = unsafe { std::slice::from_raw_parts(layers_ptr, n_layers) };
    let layers: Vec<usize> = layers_u32.iter().map(|&x| x as usize).collect();
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };
    match engine.execute_worker_forward_layers(&[], tokens, &layers) {
        Ok(vecs) => {
            let hidden = match engine.hidden_dim() {
                Ok(h) => h,
                Err(_) => return -2,
            };
            if out_len != n_layers * hidden {
                eprintln!("[Rust Engine] encode_layers dim mismatch: expected {}, got {}",
                          n_layers * hidden, out_len);
                return -3;
            }
            for (i, v) in vecs.iter().enumerate() {
                if v.len() != hidden { return -3; }
                out_slice[i * hidden..(i + 1) * hidden].copy_from_slice(v);
            }
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] encode_layers error: {}", e);
            -2
        },
    }
}

/// Blend `inject` into residual before `inject_layer`, continue to final-norm last token.
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_inject_at_layer(
    engine_ptr: *mut c_void,
    tokens_ptr: *const u32,
    tokens_len: usize,
    inject_layer: u32,
    inject_ptr: *const c_float,
    inject_len: usize,
    alpha: c_float,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || tokens_ptr.is_null() || inject_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    let tokens = unsafe { std::slice::from_raw_parts(tokens_ptr, tokens_len) };
    let inject = unsafe { std::slice::from_raw_parts(inject_ptr, inject_len) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };
    match engine.execute_inject_at_layer(&[], tokens, inject_layer as usize, inject, alpha) {
        Ok(vector) => {
            if vector.len() != out_len {
                eprintln!("[Rust Engine] inject_at_layer dim mismatch: expected {}, got {}",
                          out_len, vector.len());
                return -3;
            }
            out_slice.copy_from_slice(&vector);
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] inject_at_layer error: {}", e);
            -2
        },
    }
}

/// Milestone P: blend MULTIPLE (layer, vector, alpha) injections into ONE
/// forward pass, and snapshot the last-token residual at each requested
/// observe layer. Flat-array convention, same shape as `jcross_engine_
/// encode_layers`: `inject_layers_ptr`/`inject_vecs_ptr` (n_inject ×
/// hidden, row-major)/`alphas_ptr` describe the injections; `observe_
/// layers_ptr` (n_observe indices) selects what to return, written to
/// `out_ptr` (n_observe × hidden, same order as observe_layers_ptr).
/// See `execute_inject_multi_layer`'s own doc comment for the inherited
/// pre-layer (inject) vs post-layer (observe) semantics.
#[unsafe(no_mangle)]
pub extern "C" fn jcross_engine_inject_multi_layer(
    engine_ptr: *mut c_void,
    tokens_ptr: *const u32,
    tokens_len: usize,
    inject_layers_ptr: *const u32,
    inject_vecs_ptr: *const c_float,
    alphas_ptr: *const c_float,
    n_inject: usize,
    observe_layers_ptr: *const u32,
    n_observe: usize,
    out_ptr: *mut c_float,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || tokens_ptr.is_null() || observe_layers_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }
    if n_inject > 0 && (inject_layers_ptr.is_null() || inject_vecs_ptr.is_null() || alphas_ptr.is_null()) {
        return -1;
    }
    if n_observe == 0 { return -1; }
    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    let hidden = match engine.hidden_dim() {
        Ok(h) => h,
        Err(_) => return -2,
    };

    let tokens = unsafe { std::slice::from_raw_parts(tokens_ptr, tokens_len) };
    let observe_layers_u32 = unsafe { std::slice::from_raw_parts(observe_layers_ptr, n_observe) };
    let observe_layers: Vec<usize> = observe_layers_u32.iter().map(|&x| x as usize).collect();

    let inject_layers: Vec<usize> = if n_inject > 0 {
        unsafe { std::slice::from_raw_parts(inject_layers_ptr, n_inject) }
            .iter().map(|&x| x as usize).collect()
    } else { Vec::new() };
    let alphas: Vec<f32> = if n_inject > 0 {
        unsafe { std::slice::from_raw_parts(alphas_ptr, n_inject) }.to_vec()
    } else { Vec::new() };
    let inject_vecs: Vec<Vec<f32>> = if n_inject > 0 {
        let flat = unsafe { std::slice::from_raw_parts(inject_vecs_ptr, n_inject * hidden) };
        (0..n_inject).map(|i| flat[i * hidden..(i + 1) * hidden].to_vec()).collect()
    } else { Vec::new() };

    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };
    if out_len != n_observe * hidden {
        eprintln!("[Rust Engine] inject_multi_layer dim mismatch: expected {}, got {}",
                  n_observe * hidden, out_len);
        return -3;
    }

    match engine.execute_inject_multi_layer(&[], tokens, &inject_layers, &inject_vecs, &alphas, &observe_layers) {
        Ok(snapshots) => {
            for (i, &l) in observe_layers.iter().enumerate() {
                match snapshots.get(&l) {
                    Some(v) if v.len() == hidden => {
                        out_slice[i * hidden..(i + 1) * hidden].copy_from_slice(v);
                    }
                    _ => return -3,
                }
            }
            0
        },
        Err(e) => {
            eprintln!("[Rust Engine] inject_multi_layer error: {}", e);
            -2
        },
    }
}
