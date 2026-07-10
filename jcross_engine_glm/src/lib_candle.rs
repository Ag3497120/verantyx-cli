use memmap2::{Mmap, MmapOptions};
use std::collections::HashMap;
use std::fs::File;
use std::io;
use std::path::Path;
use half::f16;
use candle_core::{Device, Tensor, DType};
use candle_nn::ops::softmax;

mod generation;
mod tokenizer_ffi;

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

use crate::generation::{apply_rope, AttentionState, swiglu};

pub struct JCrossEngine {
    mmap: Mmap,
    pub tensors: HashMap<String, JCrossTensorMeta>,
    pub candle_tensors: HashMap<String, Tensor>,
    pub device: Device,
    pub kv_cache: std::cell::RefCell<Option<AttentionState>>,
}

impl JCrossEngine {
    pub fn load_jgen<P: AsRef<Path>>(path: P) -> io::Result<Self> {
        let file = File::open(path)?;
        let mmap = unsafe { MmapOptions::new().map(&file)? };

        if mmap.len() < 12 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "File too small"));
        }

        let magic = &mmap[0..4];
        if magic != b"JGEN" {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Invalid magic"));
        }

        let version = u32::from_le_bytes(mmap[4..8].try_into().unwrap());
        let total_tensors = u32::from_le_bytes(mmap[8..12].try_into().unwrap());
        let mut tensors = HashMap::new();
        let mut offset = 12;

        for _ in 0..total_tensors {
            let name_len = u16::from_le_bytes(mmap[offset..offset+2].try_into().unwrap()) as usize;
            offset += 2;
            let name = String::from_utf8(mmap[offset..offset+name_len].to_vec()).unwrap();
            offset += name_len;
            let t_type = mmap[offset];
            offset += 1;

            match t_type {
                1 => {
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
                    tensors.insert(name, JCrossTensorMeta { tensor_type: TensorType::SVDLossless { rows, cols, rank }, offset, byte_length: total_bytes });
                    offset += total_bytes;
                },
                2 => {
                    let rows = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap());
                    let cols = u32::from_le_bytes(mmap[offset+4..offset+8].try_into().unwrap());
                    offset += 8;
                    let total_bytes = (rows * cols * 2) as usize;
                    tensors.insert(name, JCrossTensorMeta { tensor_type: TensorType::Dense2D { rows, cols }, offset, byte_length: total_bytes });
                    offset += total_bytes;
                },
                3 => {
                    let length = u32::from_le_bytes(mmap[offset..offset+4].try_into().unwrap());
                    offset += 4;
                    let total_bytes = (length * 2) as usize;
                    tensors.insert(name, JCrossTensorMeta { tensor_type: TensorType::Dense1D { length }, offset, byte_length: total_bytes });
                    offset += total_bytes;
                },
                _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "Unknown tensor type")),
            }
        }

        let device = Device::new_metal(0).unwrap_or(Device::Cpu);
        println!("[Candle] Uploading weights to Metal VRAM...");
        let mut candle_tensors = HashMap::new();

        for (name, meta) in &tensors {
            let start = meta.offset;
            let end = start + meta.byte_length;
            let raw_data = &mmap[start..end];
            let f16_slice = unsafe { std::slice::from_raw_parts(raw_data.as_ptr() as *const half::f16, meta.byte_length / 2) };

            let tensor = match meta.tensor_type {
                TensorType::Dense2D { rows, cols } => {
                    Tensor::from_slice(f16_slice, (rows as usize, cols as usize), &device).unwrap()
                },
                TensorType::Dense1D { length } => {
                    Tensor::from_slice(f16_slice, (length as usize,), &device).unwrap()
                },
                TensorType::SVDLossless { .. } => {
                    Tensor::from_slice(f16_slice, (f16_slice.len(),), &device).unwrap() // Keep flat for now
                }
            };
            candle_tensors.insert(name.clone(), tensor);
        }

        Ok(JCrossEngine { mmap, tensors, candle_tensors, device, kv_cache: std::cell::RefCell::new(None) })
    }

    pub fn project_vector(&self, layer_name: &str, input: &Tensor) -> Result<Tensor, String> {
        let t = self.candle_tensors.get(layer_name).ok_or_else(|| format!("Layer not found: {}", layer_name))?;
        let meta = self.tensors.get(layer_name).unwrap();

        match meta.tensor_type {
            TensorType::Dense2D { rows, cols } => {
                let input_col = input.reshape((cols as usize, 1)).unwrap();
                let y = t.matmul(&input_col).unwrap();
                Ok(y.reshape((rows as usize,)).unwrap())
            },
            TensorType::Dense1D { .. } => {
                Ok(t.clone())
            },
            _ => Err("Unsupported for now".to_string())
        }
    }

    pub fn rms_norm(&self, x: &Tensor, weight: &Tensor, eps: f64) -> Result<Tensor, String> {
        let x_sq = x.sqr().unwrap();
        let sum_sq = x_sq.sum_all().unwrap();
        let mean_sq = (sum_sq.to_scalar::<f32>().unwrap() / (x.elem_count() as f32)) as f64;
        let rms = (mean_sq + eps).sqrt() as f32;
        let rms_t = Tensor::new(rms, &self.device).unwrap().to_dtype(DType::F16).unwrap();
        
        let x_norm = x.broadcast_div(&rms_t).unwrap().broadcast_mul(weight).unwrap();
        Ok(x_norm)
    }
}
    pub fn forward_transformer_layer(
        &self, 
        layer: usize, 
        mut x: Tensor, 
        pos: usize, 
        rope_theta: f32
    ) -> Result<Tensor, String> {
        // Implement full forward pass here
        Ok(x)
    }
