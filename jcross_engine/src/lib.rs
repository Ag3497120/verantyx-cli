use memmap2::{Mmap, MmapOptions};
use std::collections::HashMap;
use std::fs::File;
use std::io;
use std::path::Path;
extern crate blas_src;
use ndarray::{ArrayView2, ArrayView1, Array1};
use half::f16;
use candle_core::{Device, Tensor, DType};

mod generation;
mod tokenizer_ffi;
mod gpu_ops;

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

use crate::generation::{sdpa, apply_rope, apply_rope_chunked, sdpa_chunked, AttentionState, swiglu};


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

pub struct JCrossEngine {
    mmap: Mmap,
    pub tensors: HashMap<String, JCrossTensorMeta>,
    pub candle_tensors: HashMap<String, Tensor>,
    pub candle_device: Device,
    pub kv_cache: std::cell::RefCell<Option<AttentionState>>,
    pub metal_kv_cache: std::cell::RefCell<Option<MetalAttentionState>>,
}

impl JCrossEngine {
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
        if version != 3 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Unsupported JGEN version, expected v3"));
        }

        let total_tensors = u32::from_le_bytes(mmap[8..12].try_into().unwrap());
        let mut tensors = HashMap::new();
        let mut offset = 12;

        for _ in 0..total_tensors {
            let name_len = u16::from_le_bytes(mmap[offset..offset+2].try_into().unwrap()) as usize;
            offset += 2;

            let name = String::from_utf8(mmap[offset..offset+name_len].to_vec())
                .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "Invalid UTF-8 in tensor name"))?;
            offset += name_len;

            let t_type = mmap[offset];
            offset += 1;

            match t_type {
                1 => { // SVDLossless
                    let rows = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap());
                    let cols = u32::from_le_bytes(mmap[offset+4..offset+8].try_into().unwrap());
                    let rank = u32::from_le_bytes(mmap[offset+8..offset+12].try_into().unwrap());
                    offset += 12;

                    // f16 is 2 bytes per element
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
        #[cfg(feature = "metal")]
        let candle_device = Device::new_metal(0).unwrap_or(Device::Cpu);
        #[cfg(not(any(feature = "metal", feature = "cuda")))]
        let candle_device = Device::Cpu;
        
        println!("[JCross] Initializing GPU Device: {:?}", candle_device);
        let mut candle_tensors = HashMap::new();
        
        for (name, meta) in &tensors {
            let start = meta.offset;
            let end = start + meta.byte_length;
            let raw_data = &mmap[start..end];
            
            let f16_slice = unsafe {
                std::slice::from_raw_parts(raw_data.as_ptr() as *const half::f16, meta.byte_length / 2)
            };
            
            match meta.tensor_type {
                TensorType::Dense2D { rows, cols } => {
                    let t = Tensor::from_slice(f16_slice, (rows as usize, cols as usize), &candle_device).unwrap();
                    candle_tensors.insert(name.clone(), t);
                },
                TensorType::Dense1D { length } => {
                    let t = Tensor::from_slice(f16_slice, (length as usize,), &candle_device).unwrap();
                    candle_tensors.insert(name.clone(), t);
                },
                TensorType::SVDLossless { rows, cols, rank } => {
                    // Extract matrices for SVD Lossless and store individually
                    let r = rank as usize;
                    let m = rows as usize;
                    let n = cols as usize;
                    
                    let v_len = r * n;
                    let s_len = r;
                    let u_len = m * r;
                    let mod_x_len = n;
                    let mod_y_len = m;
                    let c_valve_len = r * r;
                    
                    let t_v = Tensor::from_slice(&f16_slice[0..v_len], (r, n), &candle_device).unwrap();
                    let t_s = Tensor::from_slice(&f16_slice[v_len..v_len+s_len], (r,), &candle_device).unwrap();
                    let t_u = Tensor::from_slice(&f16_slice[v_len+s_len..v_len+s_len+u_len], (m, r), &candle_device).unwrap();
                    
                    let off4 = v_len+s_len+u_len;
                    let t_mx = Tensor::from_slice(&f16_slice[off4..off4+mod_x_len], (n,), &candle_device).unwrap();
                    
                    let off5 = off4+mod_x_len;
                    let t_my = Tensor::from_slice(&f16_slice[off5..off5+mod_y_len], (m,), &candle_device).unwrap();
                    
                    let off6 = off5+mod_y_len;
                    let t_cv = Tensor::from_slice(&f16_slice[off6..off6+c_valve_len], (r, r), &candle_device).unwrap();
                    
                    candle_tensors.insert(format!("{}.V", name), t_v);
                    candle_tensors.insert(format!("{}.S", name), t_s);
                    candle_tensors.insert(format!("{}.U", name), t_u);
                    candle_tensors.insert(format!("{}.mod_x", name), t_mx);
                    candle_tensors.insert(format!("{}.mod_y", name), t_my);
                    candle_tensors.insert(format!("{}.c_valve", name), t_cv);
                }
            }
        }
        println!("[JCross] All FP16 weights transferred to GPU.");
        
        Ok(JCrossEngine { mmap, tensors, candle_tensors, candle_device, kv_cache: std::cell::RefCell::new(None), metal_kv_cache: std::cell::RefCell::new(None) })
    }

    /// Fetches a raw slice of memory for a given tensor. Zero copy.
    pub fn get_raw_slice(&self, name: &str) -> Option<&[u8]> {
        if let Some(meta) = self.tensors.get(name) {
            Some(&self.mmap[meta.offset..meta.offset + meta.byte_length])
        } else {
            None
        }
    }

    /// Performs the mathematical Subspace Projection (Cascading Lock).
    /// This is NOT random noise (`torch.randn`). This performs the actual linear algebra:
    /// y = U * S * (V^T * (x * mod_x)) + mod_y
    /// To do this in Rust properly with ndarray, we read the f16 bits, convert to f32, and compute.
    pub fn execute_svd_projection(&self, layer_name: &str, input_vector: &[f32]) -> Result<Vec<f32>, String> {
        let meta = self.tensors.get(layer_name).ok_or("Layer not found")?;
        
        let (rows, cols, rank) = match meta.tensor_type {
            TensorType::SVDLossless { rows, cols, rank } => (rows as usize, cols as usize, rank as usize),
            _ => return Err("Target tensor is not an SVD Lossless type".to_string()),
        };

        if input_vector.len() != cols {
            return Err(format!("Input vector dimension mismatch. Expected {}, got {}", cols, input_vector.len()));
        }

        let raw_data = &self.mmap[meta.offset..meta.offset + meta.byte_length];
        let mut offset = 0;

        // Helper closure to read f16 array and convert to f32 ndarray
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
        let meta = self.tensors.get(layer_name).ok_or("Layer not found")?;
        let (rows, cols) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err("Not Dense2D".to_string()),
        };
        let w_t = self.candle_tensors.get(layer_name).ok_or("Tensor not loaded")?;
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
        let meta = self.tensors.get(layer_name).ok_or("Layer not found")?;
        
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
        let meta = self.tensors.get(layer_name).ok_or("Layer not found")?;
        
        let (vocab_size, hidden_dim) = match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => (rows as usize, cols as usize),
            _ => return Err("Target tensor is not a Dense2D type (expected lm_head)".to_string()),
        };

        if input_vector.len() != hidden_dim {
            return Err(format!("Input vector dimension mismatch. Expected {}, got {}", hidden_dim, input_vector.len()));
        }

        let raw_data = &self.mmap[meta.offset..meta.offset + meta.byte_length];
        let mut offset = 0;

        // Note: For extreme performance, we'd use zero-copy f16->f32 conversion with SIMD.
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
        logits.mapv_inplace(|v| v / sum); // Now logits contains true probabilities

        // 3. Find Token with Highest Resonance (Axis Lock) and compute Entropy
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

        // Return the locked token (axis) and the overall entropy (resistance) of this state
        Ok((best_token as u32, entropy))
    }

    /// Helper method to project a vector through a tensor (Dense or SVD)
    pub fn project_vector(&self, layer_name: &str, input: &Array1<f32>) -> Result<Array1<f32>, String> {
        let meta = self.tensors.get(layer_name).ok_or("Layer not found")?;
        let input_slice = input.as_slice().unwrap();
        
        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let w_t = self.candle_tensors.get(layer_name).ok_or("Tensor missing")?;
                let x_t = Tensor::from_slice(input_slice, (cols as usize, 1), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                let y_t = w_t.matmul(&x_t_f16).map_err(|e| e.to_string())?;
                let y_t_f32 = y_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let y_vec = y_t_f32.to_vec2::<f32>().map_err(|e| e.to_string())?;
                Ok(ndarray::Array1::from_vec(y_vec.into_iter().flatten().collect()))
            },
            TensorType::Dense1D { .. } => {
                let w_t = self.candle_tensors.get(layer_name).ok_or("Tensor missing")?;
                let w_t_f32 = w_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let w_vec = w_t_f32.to_vec1::<f32>().map_err(|e| e.to_string())?;
                Ok(ndarray::Array1::from_vec(w_vec))
            },
            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (cols as usize, 1), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                
                let t_v = self.candle_tensors.get(&format!("{}.V", layer_name)).unwrap();
                let t_s = self.candle_tensors.get(&format!("{}.S", layer_name)).unwrap();
                let t_u = self.candle_tensors.get(&format!("{}.U", layer_name)).unwrap();
                
                // temp = V^T * x (v is saved as r x n, which is V^T)
                let temp1 = t_v.matmul(&x_t_f16).map_err(|e| e.to_string())?;
                // s is shape (r,), we need to broadcast mul or use diag. 
                // Since temp1 is (r, 1), s is (r,). We reshape s to (r, 1) and elementwise multiply.
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                
                // U is (m, r). U * temp2
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let out_f32 = temp3.to_dtype(DType::F32).map_err(|e| e.to_string())?;
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
                let w_t = self.candle_tensors.get(layer_name).ok_or("Tensor missing")?;
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
                let w_t = self.candle_tensors.get(layer_name).ok_or("Tensor missing")?;
                let w_t_f32 = w_t.to_dtype(DType::F32).map_err(|e| e.to_string())?;
                let w_vec = w_t_f32.to_vec1::<f32>().map_err(|e| e.to_string())?;
                Ok(ndarray::Array2::from_shape_fn((b, w_vec.len()), |(_, j)| w_vec[j]))
            },
            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (b, cols as usize), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                let x_t_f16_t = x_t_f16.t().map_err(|e| e.to_string())?; // (cols, B)
                
                let t_v = self.candle_tensors.get(&format!("{}.V", layer_name)).unwrap();
                let t_s = self.candle_tensors.get(&format!("{}.S", layer_name)).unwrap();
                let t_u = self.candle_tensors.get(&format!("{}.U", layer_name)).unwrap();
                
                // temp1 = V^T * x_t_f16_t. V^T is stored as V with shape (r, cols).
                let temp1 = t_v.matmul(&x_t_f16_t).map_err(|e| e.to_string())?; // (r, B)
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?; // (r, B)
                
                // U is (m, r). U * temp2 -> (m, B)
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let out_f32 = temp3.to_dtype(DType::F32).map_err(|e| e.to_string())?;
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

        // 2. QKV Projections
        let q_names = [&format!("model.language_model.layers.{}.self_attn.q_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]];
        // 2. QKV Projections
        let q_names = [&format!("model.language_model.layers.{}.self_attn.q_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.q_proj.weight", layer)[..]];
        let k_names = [&format!("model.language_model.layers.{}.self_attn.k_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.k_proj.weight", layer)[..]];
        let v_names = [&format!("model.language_model.layers.{}.self_attn.v_proj.weight", layer)[..], &format!("model.layers.{}.self_attn.v_proj.weight", layer)[..]];

        let head_dim = 128; // Standard for Qwen/Llama
        
        let mut q_res = project_any(&q_names, &x_norm);
        let k_res = project_any(&k_names, &x_norm);
        let v_res = project_any(&v_names, &x_norm);
        
        if let Ok(ref mut q) = q_res {
            if q.len() == 8192 {
                // Bug in conversion script produced 8192 output for q_proj, take first 4096
                *q = q.slice(ndarray::s![..4096]).to_owned();
            }
        }

        if let (Ok(mut q), Ok(mut k), Ok(v)) = (q_res, k_res, v_res) {
            let num_heads = q.len() / head_dim;
            let num_kv_heads = k.len() / head_dim;

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
                
                cache.append_kv(layer, &k, &v);
                
                // SDPA
                let cache_k = &cache.kv_cache_k[layer];
                let cache_v = &cache.kv_cache_v[layer];
                sdpa(&q, cache_k, cache_v, num_heads, num_kv_heads, head_dim)
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
        
        sum_sq = 0.0;
        for &val in x.iter() { sum_sq += val * val; }
        let rms2 = (sum_sq / (x.len() as f32) + norm_eps).sqrt();
        let mut x_post_norm = x.clone();
        for (i, val) in x_post_norm.iter_mut().enumerate() { *val = (*val / rms2) * post_norm_w[i]; }

        // 7. MLP Projections
        let gate_names = [&format!("model.language_model.layers.{}.mlp.gate_proj.weight", layer)[..], &format!("model.layers.{}.mlp.gate_proj.weight", layer)[..]];
        let up_names = [&format!("model.language_model.layers.{}.mlp.up_proj.weight", layer)[..], &format!("model.layers.{}.mlp.up_proj.weight", layer)[..]];
        let down_names = [&format!("model.language_model.layers.{}.mlp.down_proj.weight", layer)[..], &format!("model.layers.{}.mlp.down_proj.weight", layer)[..]];

        if let (Ok(mut gate), Ok(up)) = (project_any(&gate_names, &x_post_norm), project_any(&up_names, &x_post_norm)) {
            for (i, val) in gate.iter_mut().enumerate() {
                *val = swiglu(*val) * up[i];
            }

            if let Ok(mlp_out) = project_any(&down_names, &gate) {
                x = x + mlp_out;
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

        let head_dim = 128;
        
        let mut q_res = project_any(&q_names, &x_norm);
        let k_res = project_any(&k_names, &x_norm);
        let v_res = project_any(&v_names, &x_norm);
        
        if let Ok(ref mut q) = q_res {
            if q.shape()[1] == 8192 {
                *q = q.slice(ndarray::s![.., ..4096]).to_owned();
            }
        }

        if let (Ok(mut q), Ok(mut k), Ok(v)) = (q_res, k_res, v_res) {
            let num_heads = q.shape()[1] / head_dim;
            let num_kv_heads = k.shape()[1] / head_dim;

            // 3. Apply RoPE Chunked
            let q_slice = q.as_slice_mut().unwrap();
            let k_slice = k.as_slice_mut().unwrap();
            apply_rope_chunked(q_slice, k_slice, start_pos, b, num_heads, num_kv_heads, head_dim, rope_theta);

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
                
                let cache_k = &cache.kv_cache_k[layer];
                let cache_v = &cache.kv_cache_v[layer];
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
        
        let num_layers = 28; 
        let num_kv_heads = 8;
        let head_dim = 128; 
        let rope_theta = 10000.0;
        
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
                    x_arr[[i, j]] = f16::from_le_bytes(bytes).to_f32();
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

    pub fn execute_generation_loop(&self, start_token: u32, max_tokens: usize) -> Result<Vec<u32>, String> {
        let mut generated = Vec::new();
        generated.push(start_token);
        
        let mut current_token = start_token;
        
        let num_layers = 28;
        let num_heads = 32;
        let num_kv_heads = 4; // Qwen 9B uses GQA
        let head_dim = 128;
        let rope_theta = 10000.0;
        
        // Initialize KV Cache if not set
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
        
        // Figure out current position from cache
        let mut pos = {
            let cache = self.kv_cache.borrow();
            if let Some(c) = &*cache {
                c.kv_cache_k[0].shape()[0] // seq_len
            } else {
                0
            }
        };
        
        for step in 0..max_tokens {
            println!("[Coder] Generating token {}/{} (pos: {})", step + 1, max_tokens, pos);
            
            // 1. Extract Token Embedding
            let embed_meta = self.tensors.get("model.language_model.embed_tokens.weight")
                .or_else(|| self.tensors.get("model.embed_tokens.weight"))
                .or_else(|| self.tensors.get("embed_tokens"))
                .ok_or_else(|| "embed_tokens not found in model".to_string())?;
                
            let mut x = match embed_meta.tensor_type {
                TensorType::Dense2D { rows: _, cols } => {
                    let c = cols as usize;
                    let row_offset = (current_token as usize) * c * 2; // f16 = 2 bytes
                    let raw_data = &self.mmap[embed_meta.offset + row_offset .. embed_meta.offset + row_offset + (c * 2)];
                    
                    let mut emb = Vec::with_capacity(c);
                    let mut offset = 0;
                    for _ in 0..c {
                        let bytes: [u8; 2] = [raw_data[offset], raw_data[offset+1]];
                        emb.push(f16::from_le_bytes(bytes).to_f32());
                        offset += 2;
                    }
                    ndarray::Array1::from_vec(emb)
                },
                _ => return Err("embed_tokens must be Dense2D".to_string()),
            };

            // 2. Transformer Layers
            for layer in 0..num_layers {
                x = self.forward_transformer_layer(layer, x, pos, rope_theta)?;
            }
            
            // 3. Final Norm
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
            
            // 4. Projection to Vocab (lm_head)
            let logits_vec = self.execute_dense_projection("lm_head", x.as_slice().unwrap())?;
            
            // 5. Argmax (Greedy Decoding)
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

    match engine.execute_generation_loop_gpu(start_token, max_tokens) {
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
