use memmap2::{Mmap, MmapOptions};
use std::collections::HashMap;
use std::fs::File;
use std::io;
use std::path::Path;
#[cfg(feature = "metal")]
extern crate blas_src;
use ndarray::{ArrayView2, ArrayView1, Array1};
use half::bf16;
use candle_core::{Device, Tensor, DType};

mod generation;
mod tokenizer_ffi;
mod gpu_ops;
mod puzzle_math;
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

use crate::generation::{sdpa_gqa, apply_rope_glm, apply_rope_chunked_glm, sdpa_chunked, AttentionState, swiglu};


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
}

impl JCrossEngine {

    pub fn get_candle_tensor(&self, name: &str, device: &Device) -> Result<Tensor, String> {
        if let Some(meta) = self.tensors.get(name) {
            let raw_data = self.get_raw_slice(name).ok_or_else(|| "Could not read tensor data".to_string())?;
            let f16_slice = unsafe {
                std::slice::from_raw_parts(raw_data.as_ptr() as *const half::bf16, meta.byte_length / 2)
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
                            std::slice::from_raw_parts(raw_data.as_ptr() as *const half::bf16, meta.byte_length / 2)
                        };
                        
                        let v_len = r * n;
                        let s_len = r;
                        let u_len = m * r;
                        let mod_x_len = n;
                        let mod_y_len = m;
                        let c_valve_len = r * r;
                        
                        return match suffix {
                            "V" => Tensor::from_slice(&f16_slice[0..v_len], (r, n), device).map_err(|e| e.to_string()),
                            "S" => Tensor::from_slice(&f16_slice[v_len..v_len+s_len], (r,), device).map_err(|e| e.to_string()),
                            "U" => Tensor::from_slice(&f16_slice[v_len+s_len..v_len+s_len+u_len], (m, r), device).map_err(|e| e.to_string()),
                            "mod_x" => Tensor::from_slice(&f16_slice[v_len+s_len+u_len..v_len+s_len+u_len+mod_x_len], (n,), device).map_err(|e| e.to_string()),
                            "mod_y" => Tensor::from_slice(&f16_slice[v_len+s_len+u_len+mod_x_len..v_len+s_len+u_len+mod_x_len+mod_y_len], (m,), device).map_err(|e| e.to_string()),
                            "c_valve" => Tensor::from_slice(&f16_slice[v_len+s_len+u_len+mod_x_len+mod_y_len..v_len+s_len+u_len+mod_x_len+mod_y_len+c_valve_len], (r, r), device).map_err(|e| e.to_string()),
                            _ => Err(format!("Unknown suffix: {}", suffix)),
                        };
                    }
                }
            }
        }
        
        Err(format!("Tensor missing (Streaming VRAM): {}", name))
    }

    /// Zero-copy mmap loader for the JGEN binary format.
    /// This is NOT a mock. It strictly parses the binary layout defined by `jcross_build_lossless_9b.py`.
    pub fn load_jgen<P: AsRef<Path>>(path: P) -> io::Result<Self> {
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

                    let u_len = (rows * rank * 2) as usize;
                    let s_len = (rank * 2) as usize;
                    let v_len = (cols * rank * 2) as usize;
                    let mod_x_len = (cols * 2) as usize;
                    let mod_y_len = (rows * 2) as usize;
                    let c_valve_len = (rank * rank * 2) as usize;

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

                    let total_bytes = (rows * cols * 2) as usize;
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

                    let total_bytes = (length * 2) as usize;
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

        #[cfg(feature = "cuda")]
        let candle_device = Device::new_cuda(0).unwrap_or(Device::Cpu);
        #[cfg(not(feature = "cuda"))]
        let candle_device = Device::new_metal(0).unwrap_or(Device::Cpu);
        
        println!("[JCross] Initializing GPU Device: {:?}", candle_device);
        let mut candle_tensors = HashMap::new();
        
        for name in tensors.keys() {
            if name.contains("layers.3.mlp") {
                println!("[JCross DEBUG] Found layer 3 tensor: {}", name);
            }
        }
        
        // Streaming architecture: no eager loading to VRAM.
        
        Ok(JCrossEngine { 
            mmap, 
            tensors, 
            candle_tensors, 
            candle_device, 
            kv_cache: std::cell::RefCell::new(None), 
            metal_kv_cache: std::cell::RefCell::new(None), 
            prefetch_cache: std::cell::RefCell::new(HashMap::new()),
            expert_usage_stats: std::cell::RefCell::new(HashMap::new()),
            l1_cache: std::cell::RefCell::new(HashMap::new()),
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

        let raw_data = self.get_raw_slice(layer_name).ok_or_else(|| "Could not read tensor data".to_string())?;
        let mut offset = 0;

        // Helper closure to read bf16 array and convert to f32 ndarray
        let mut read_f16_to_f32 = |length: usize| -> Vec<f32> {
            let mut result = Vec::with_capacity(length);
            for _ in 0..length {
                let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                let val = bf16::from_le_bytes(bytes);
                result.push(val.to_f32());
                offset += 2;
            }
            result
        };

        // Extract matrices according to JGEN layout: U, S, V, mod_x, mod_y, C_valve
        let u_vec = read_f16_to_f32(rows * rank);
        let s_vec = read_f16_to_f32(rank);
        let v_vec = read_f16_to_f32(cols * rank);
        let mod_x_vec = read_f16_to_f32(cols);
        let mod_y_vec = read_f16_to_f32(rows);
        let c_valve_vec = read_f16_to_f32(rank * rank);

        // Convert into ndarray structures
        // Note: jcross_build_lossless_9b saves U as (rows x rank) and V_trunc as (cols x rank)
        let u_mat = ndarray::Array2::from_shape_vec((rows, rank), u_vec).unwrap();
        let s_diag = ndarray::Array1::from_vec(s_vec);
        let v_mat = ndarray::Array2::from_shape_vec((cols, rank), v_vec).unwrap();
        let mod_x = ndarray::Array1::from_vec(mod_x_vec);
        let mod_y = ndarray::Array1::from_vec(mod_y_vec);
        let c_valve = ndarray::Array2::from_shape_vec((rank, rank), c_valve_vec).unwrap();

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
        let x_t = Tensor::from_slice(input_vector, (cols, 1), &self.candle_device).map_err(|e| e.to_string())?;
        let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
        let y_t = w_t.matmul(&x_t_f16).map_err(|e| e.to_string())?;
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
                let val = bf16::from_le_bytes(bytes);
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
                let val = bf16::from_le_bytes(bytes);
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
                let val = bf16::from_le_bytes(bytes);
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
        let input_slice = input.as_slice().unwrap();
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
                let x_t = Tensor::from_slice(input_slice, (cols as usize, 1), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                let y_t = w_t.matmul(&x_t_f16).map_err(|e| e.to_string())?;
                let y_t_f32 = y_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let y_vec = y_t_f32.to_vec2::<f32>().map_err(|e| e.to_string())?;
                Ok(ndarray::Array1::from_vec(y_vec.into_iter().flatten().collect()))
            },
            TensorType::Dense1D { .. } => {
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
                let w_t_f32 = w_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let w_vec = w_t_f32.to_vec1::<f32>().map_err(|e| e.to_string())?;
                Ok(ndarray::Array1::from_vec(w_vec))
            },
            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (cols as usize, 1), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                
                let t_mod_x = self.get_candle_tensor(&format!("{}.mod_x", layer_name), &self.candle_device).unwrap();
                let t_mod_x_f16 = t_mod_x.reshape((cols as usize, 1)).unwrap();
                let x_mod = x_t_f16.broadcast_mul(&t_mod_x_f16).unwrap();

                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                let t_c_valve = self.get_candle_tensor(&format!("{}.c_valve", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?;
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                let temp_locked = t_c_valve.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let temp3 = t_u.matmul(&temp_locked).map_err(|e| e.to_string())?;
                
                let t_mod_y = self.get_candle_tensor(&format!("{}.mod_y", layer_name), &self.candle_device).unwrap();
                let t_mod_y_f16 = t_mod_y.reshape((rows as usize, 1)).unwrap();
                let temp4 = temp3.broadcast_add(&t_mod_y_f16).unwrap();

                let out_f32 = temp4.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let out_vec = out_f32.to_vec2::<f32>().map_err(|e| e.to_string())?;
                Ok(ndarray::Array1::from_vec(out_vec.into_iter().flatten().collect()))
            }
        }
    }

    /// Executes a single complete Transformer layer (Forward Pass)
    
    pub fn project_matrix(&self, layer_name: &str, input: &ndarray::Array2<f32>) -> Result<ndarray::Array2<f32>, String> {
        let meta = self.tensors.get(layer_name).ok_or("Layer not found")?;
        let input_slice = input.as_slice().unwrap();
        let b = input.shape()[0];
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
                // input is (B, cols), so transpose it for matmul if w_t is (rows, cols)
                // wait, if W is (rows, cols) and x is (B, cols), 
                // w_t * x_t^T -> (rows, B), then transpose to (B, rows)
                let x_t = Tensor::from_slice(input_slice, (b, cols as usize), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                // w_t is (rows, cols). We want to compute x * W^T, which is exactly linear projection.
                // Or W * x^T.
                // In project_vector: x is (cols, 1), w_t is (rows, cols). w_t.matmul(x_t).
                // So if we have B tokens, x_t is (cols, B).
                let x_t_f16_t = x_t_f16.t().map_err(|e| e.to_string())?; // (cols, B)
                let y_t = w_t.matmul(&x_t_f16_t).map_err(|e| e.to_string())?; // (rows, B)
                let y_t_f32 = y_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let y_vec = y_t_f32.to_vec2::<f32>().map_err(|e| e.to_string())?;
                
                // y_vec is a Vec<Vec<f32>> of size rows x B.
                // We want to return an Array2 of shape (B, rows).
                let mut out = ndarray::Array2::<f32>::zeros((b, rows as usize));
                for r in 0..rows as usize {
                    for i in 0..b {
                        out[[i, r]] = y_vec[r][i];
                    }
                }
                Ok(out)
            },
            TensorType::Dense1D { .. } => {
                let w_t = self.get_candle_tensor(layer_name, &self.candle_device).map_err(|e| e.to_string())?;
                let w_t_f32 = w_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let w_vec = w_t_f32.to_vec1::<f32>().map_err(|e| e.to_string())?;
                Ok(ndarray::Array2::from_shape_fn((b, w_vec.len()), |(_, j)| w_vec[j]))
            },
            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (b, cols as usize), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                let x_t_f16_t = x_t_f16.t().map_err(|e| e.to_string())?; // (cols, B)
                
                let t_mod_x = self.get_candle_tensor(&format!("{}.mod_x", layer_name), &self.candle_device).unwrap();
                let t_mod_x_f16 = t_mod_x.reshape((cols as usize, 1)).unwrap();
                let x_mod = x_t_f16_t.broadcast_mul(&t_mod_x_f16).unwrap(); // (cols, 1) broadcast over (cols, B)

                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                let t_c_valve = self.get_candle_tensor(&format!("{}.c_valve", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?; // (r, B)
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?; // (r, B)
                let temp_locked = t_c_valve.matmul(&temp2).map_err(|e| e.to_string())?; // (r, B)
                
                let temp3 = t_u.matmul(&temp_locked).map_err(|e| e.to_string())?; // (rows, B)
                
                let t_mod_y = self.get_candle_tensor(&format!("{}.mod_y", layer_name), &self.candle_device).unwrap();
                let t_mod_y_f16 = t_mod_y.reshape((rows as usize, 1)).unwrap();
                let temp4 = temp3.broadcast_add(&t_mod_y_f16).unwrap();

                let out_f32 = temp4.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let out_vec = out_f32.to_vec2::<f32>().map_err(|e| e.to_string())?;
                
                let mut out = ndarray::Array2::<f32>::zeros((b, rows as usize));
                for r in 0..rows as usize {
                    for i in 0..b {
                        out[[i, r]] = out_vec[r][i];
                    }
                }
                Ok(out)
            }
        }
    }

    pub fn forward_transformer_layer(
        &self, 
        layer: usize, 
        mut x: Array1<f32>, 
        pos: usize, 
        rope_theta: f32
    ) -> Result<Array1<f32>, String> {
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

        // 2. QKV Projection (GLM-4 GQA)
        let qkv_names = [&format!("model.layers.{}.self_attn.query_key_value.weight", layer)[..]];
        let qkv_bias_names = [&format!("model.layers.{}.self_attn.query_key_value.bias", layer)[..]];
        
        if let Ok(mut qkv) = project_any(&qkv_names, &x_norm) {
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
                // max 80 layers, 2 kv heads, 128 head dim
                *cache_opt = Some(crate::generation::AttentionState::new(80, 2, 128, rope_theta));
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
        }

        // 6. Post-Attention RMSNorm
        let post_names = [&format!("model.language_model.layers.{}.post_attention_layernorm.weight", layer)[..], &format!("model.layers.{}.post_attention_layernorm.weight", layer)[..]];
        let post_norm_w = project_any(&post_names, &x)?;
        
        sum_sq = 0.0;
        for &val in x.iter() { sum_sq += val * val; }
        let rms2 = (sum_sq / (x.len() as f32) + norm_eps).sqrt();
        let mut x_post_norm = x.clone();
        for (i, val) in x_post_norm.iter_mut().enumerate() { *val = (*val / rms2) * post_norm_w[i]; }
        if layer == 3 || layer == 0 || layer == 78 {
            println!("[Layer {}] x_post_norm[0]={:?}", layer, x_post_norm[0]);
        }

        // 7. MLP Projections (GLM-5.2 Dense or MoE)
        let is_moe = layer >= 3; // first_k_dense_replace = 3

        if is_moe {
            let router_names = [&format!("model.layers.{}.mlp.gate.weight", layer)[..]];
            let router_w = project_any(&router_names, &x_post_norm)?; // Returns logits for 256 experts
            
            let bias_names = [&format!("model.layers.{}.mlp.gate.e_score_correction_bias", layer)[..]];
            let mut scores = router_w;
            if let Ok(bias) = project_any(&bias_names, &x_post_norm) {
                for i in 0..scores.len() {
                    scores[i] += bias[i];
                }
            }
            let k = 8;
            let mut experts_with_scores: Vec<(usize, f32)> = scores.iter().enumerate().map(|(i, &s)| (i, s)).collect();
            experts_with_scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            
            let top_k_experts: Vec<_> = experts_with_scores.into_iter().take(k).collect();
            
            // Save active experts to prefetch cache for next token
            if let Ok(mut pc) = self.prefetch_cache.try_borrow_mut() {
                let expert_ids: Vec<usize> = top_k_experts.iter().map(|&(idx, _)| idx).collect();
                pc.insert(layer as usize, expert_ids);
            }
            
            // Sigmoid scores and normalize
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
                if layer == 3 {
                    println!("[Layer 3] Shared expert gate[0]={:?}, up[0]={:?}", gate[0], up[0]);
                }
                for (j, val) in gate.iter_mut().enumerate() {
                    *val = swiglu(*val) * up[j];
                }
                if layer == 3 {
                    println!("[Layer 3] Shared expert gate_after_swiglu[0]={:?}", gate[0]);
                }
                if let Ok(down) = project_any(&shared_down_names, &gate) {
                    if layer == 3 {
                        println!("[Layer 3] Shared expert down[0]={:?}", down[0]);
                    }
                    for j in 0..moe_out.len() {
                        moe_out[j] += down[j];
                    }
                } else if layer == 3 {
                    println!("[Layer 3] Shared expert down_proj FAILED!");
                }
            } else if layer == 3 {
                println!("[Layer 3] Shared expert gate/up project FAILED!");
            }
            x = x + moe_out;
        } else {
            // Dense MLP fallback for layers 0..2
            let gate_names = [&format!("model.layers.{}.mlp.gate_proj.weight", layer)[..]];
            let up_names = [&format!("model.layers.{}.mlp.up_proj.weight", layer)[..]];
            let down_names = [&format!("model.layers.{}.mlp.down_proj.weight", layer)[..]];

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

        let head_dim = 64;
        
        let mut q_res = project_any(&q_names, &x_norm);
        let mut k_res = project_any(&k_names, &x_norm);
        let mut v_res = project_any(&v_names, &x_norm);
        
        if let Ok(ref mut q) = q_res {
            if q.shape()[1] == 8192 {
                *q = q.slice(ndarray::s![.., ..4096]).to_owned();
            }
        }

        if let (Ok(mut q), Ok(mut k), Ok(v)) = (q_res, k_res, v_res) {
            let num_heads = 14;
            let num_kv_heads = 2;

            // 3. Apply RoPE Chunked
            let q_slice = q.as_slice_mut().unwrap();
            let k_slice = k.as_slice_mut().unwrap();
            apply_rope_chunked_glm(q_slice, k_slice, start_pos, b, num_heads, num_kv_heads, head_dim, rope_theta);

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

        // 7. MLP Projections
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

        Ok(x)
    }

    pub fn execute_worker_forward(&self, tokens: &[u32]) -> Result<Vec<f32>, String> {
        if tokens.is_empty() { return Err("Empty token list".to_string()); }
        
        let num_layers = 79; 
        let num_heads = 64;
        let num_kv_heads = 64;
        let head_dim = 64; 
        let rope_theta = 8000000.0;
        
        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, 2, 64, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }
        
        let chunk_size = 1024;
        let mut x_final = Vec::new();
        let mut pos = 0;

        for chunk_start in (0..tokens.len()).step_by(chunk_size) {
            let chunk_end = std::cmp::min(chunk_start + chunk_size, tokens.len());
            let chunk_tokens = &tokens[chunk_start..chunk_end];
            let b = chunk_tokens.len();
            
            println!("[Rust Worker] Processing chunk {}/{} (tokens {} to {})", chunk_start / chunk_size + 1, (tokens.len() + chunk_size - 1) / chunk_size, chunk_start, chunk_end);
            
            let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
                .or_else(|| self.tensors.get("model.embed_tokens.weight"))
                .or_else(|| self.tensors.get("embed_tokens"))
                .ok_or_else(|| "embed_tokens not found".to_string())?;
                
            let c = match embed_meta.tensor_type {
                TensorType::Dense2D { cols, .. } => cols as usize,
                _ => return Err("embed_tokens must be Dense2D".to_string()),
            };

            let mut x_arr = ndarray::Array2::<f32>::zeros((b, c));
            
            for (i, &token) in chunk_tokens.iter().enumerate() {
                let row_offset = (token as usize) * c * 2;
                let raw_data = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + (c * 2)];
                let mut offset = 0;
                for j in 0..c {
                    let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                    x_arr[[i, j]] = bf16::from_le_bytes(bytes).to_f32();
                    offset += 2;
                }
            }

            for layer in 0..num_layers {
                x_arr = self.forward_transformer_layer_chunked(layer, x_arr, pos, rope_theta)?;
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
            
            if chunk_end == tokens.len() {
                let last_token_row = x_arr.slice(ndarray::s![b - 1, ..]).to_owned();
                x_final = last_token_row.into_raw_vec();
            }
            
            pos += b;
        }
        
        Ok(x_final)
    }

    pub fn execute_generation_loop(&self, prompt: &[u32], max_tokens: usize) -> Result<Vec<u32>, String> {
        let num_layers = 79;
        let num_heads = 64;
        let num_kv_heads = 64;
        let head_dim = 64;
        let rope_theta = 8000000.0;
        let mut generated = Vec::new();
        
        {
            let mut cache = self.kv_cache.borrow_mut();
            if cache.is_none() {
                *cache = Some(AttentionState::new(num_layers, 2, 64, rope_theta));
            }
            let mut mcache = self.metal_kv_cache.borrow_mut();
            if mcache.is_none() {
                *mcache = Some(MetalAttentionState::new(num_layers));
            }
        }
        
        let mut current_token = prompt[0];
        let mut pos = 0;
        
        // Prefill
        for (i, &token) in prompt.iter().enumerate() {
            if i > 0 {
                let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
                    .or_else(|| self.tensors.get("model.embed_tokens.weight"))
                    .or_else(|| self.tensors.get("embed_tokens"))
                    .ok_or_else(|| "embed_tokens not found in model".to_string())?;
                    
                let mut x = match embed_meta.tensor_type {
                    TensorType::Dense2D { rows: _, cols } => {
                        let c = cols as usize;
                        let row_offset = (current_token as usize) * c * 2;
                        let raw_data = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + (c * 2)];
                        
                        let mut emb = Vec::with_capacity(c);
                        let mut offset = 0;
                        for _ in 0..c {
                            let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                            emb.push(half::bf16::from_le_bytes(bytes).to_f32());
                            offset += 2;
                        }
                        ndarray::Array1::from_vec(emb)
                    },
                    _ => return Err("embed_tokens must be Dense2D".to_string()),
                };
                
                for layer in 0..num_layers {
                    x = self.forward_transformer_layer(layer as usize, x, pos, rope_theta)?;
                    if layer % 10 == 0 {
                        println!("[Prefill Token {}/{}] Finished layer {}", i+1, prompt.len(), layer);
                    }
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
            

            let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
                .or_else(|| self.tensors.get("model.embed_tokens.weight"))
                .or_else(|| self.tensors.get("embed_tokens"))
                .ok_or_else(|| "embed_tokens not found in model".to_string())?;
                
            let mut x = match embed_meta.tensor_type {
                TensorType::Dense2D { rows: _, cols } => {
                    let c = cols as usize;
                    let row_offset = (current_token as usize) * c * 2;
                    let raw_data = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + (c * 2)];
                    
                    let mut emb = Vec::with_capacity(c);
                    let mut offset = 0;
                    for _ in 0..c {
                        let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                        emb.push(half::bf16::from_le_bytes(bytes).to_f32());
                        offset += 2;
                    }
                    ndarray::Array1::from_vec(emb)
                },
                _ => return Err("embed_tokens must be Dense2D".to_string()),
            };

            for layer in 0..num_layers {
                x = self.forward_transformer_layer(layer as usize, x, pos, rope_theta)?;
            }
            
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
            
            let logits_vec = self.execute_dense_projection("lm_head", x.as_slice().unwrap())?;
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
            
            if next_token == 151643 || next_token == 151645 { // Qwen <|endoftext|> and <|im_end|>
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
        Err(_) => std::ptr::null_mut(),
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
    start_token: u32,
    max_tokens: usize,
    out_ptr: *mut u32,
    out_len: usize,
) -> i32 {
    if engine_ptr.is_null() || out_ptr.is_null() {
        return -1;
    }

    let engine = unsafe { &*(engine_ptr as *const JCrossEngine) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out_ptr, out_len) };

    match engine.execute_generation_loop_gpu(&[start_token], max_tokens) {
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
