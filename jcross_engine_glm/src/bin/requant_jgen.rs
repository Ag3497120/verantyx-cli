//! Requantize an f16 JGEN into quantized-block JGEN (tensor type 4).
//!
//! Why this exists: the GGUF converter dequantizes to f16, which turned a
//! 16.6 GB q4_k_m 27B into a 50 GB file. A 50 GB file cannot be resident on
//! a 24 GB Mac, so every token re-streamed weights from disk on the CPU.
//! Requantizing recovers roughly the original size, and the engine then runs
//! the blocks directly through candle's QMatMul — Metal included.
//!
//! Fidelity note, stated honestly: this quantizes the *dequantized* f16, so
//! it is a second quantization, not a bit-exact recovery of the original GGUF
//! blocks. q4_k→f16→q4_k re-derives scales from values that are already on
//! the q4_k grid, so nearly every block snaps back losslessly; the safety
//! margin is that attention V and the head go to q6_k, same as llama.cpp's
//! own q4_k_m recipe.
//!
//! Usage: requant_jgen <in.jgen> <out.jgen>
//!
//! What gets quantized (the same shape rule k-quants impose):
//!   - Dense2D, cols % 256 == 0, at least 1M elements  → q4_k
//!   - lm_head / output_layer / *.v_proj               → q6_k
//!   - embed_tokens                                    → kept f16 (the CPU
//!     embedding path reads single rows from mmap; quantized rows would need
//!     a block-decode per lookup for no residency win — the table is never
//!     uploaded)
//!   - everything else (norms, biases, conv1d, A_log…) → copied verbatim

use std::env;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;

use candle_core::quantized::{GgmlDType, QTensor};
use candle_core::{Device, Tensor};
use memmap2::MmapOptions;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: requant_jgen <in.jgen> <out.jgen>");
        std::process::exit(2);
    }
    if let Err(e) = run(&args[1], &args[2]) {
        eprintln!("requant failed: {}", e);
        std::process::exit(1);
    }
}

fn ggml_id(dt: GgmlDType) -> u8 {
    match dt {
        GgmlDType::Q4K => 12,
        GgmlDType::Q6K => 14,
        GgmlDType::Q8_0 => 8,
        _ => unreachable!("only k-quants are emitted here"),
    }
}

/// Which quantization a tensor gets, or None to copy it verbatim.
fn plan(name: &str, rows: usize, cols: usize) -> Option<GgmlDType> {
    if cols % 256 != 0 || rows * cols < (1 << 20) {
        return None;
    }
    if name.contains("embed_tokens") {
        return None; // row-lookup path stays mmap f16
    }
    if name.contains("lm_head") || name.contains("output_layer") || name.contains("v_proj") {
        return Some(GgmlDType::Q6K);
    }
    Some(GgmlDType::Q4K)
}

fn run(inp: &str, outp: &str) -> Result<(), String> {
    let file = File::open(inp).map_err(|e| e.to_string())?;
    let mmap = unsafe { MmapOptions::new().map(&file).map_err(|e| e.to_string())? };
    if &mmap[0..4] != b"JGEN" {
        return Err("not a JGEN file".into());
    }
    let version = u32::from_le_bytes(mmap[4..8].try_into().unwrap());
    if version != 3 {
        return Err(format!("only JGEN v3 is supported (got v{})", version));
    }
    let total = u32::from_le_bytes(mmap[8..12].try_into().unwrap());

    // Write to a scratch name and rename at the end: the IDE's inventory
    // sweep deletes any .jgen without a .meta.json sidecar, and a 17 GB
    // write is a long time to be a deletable-looking file.
    let partial = format!("{}.partial", outp);
    let out_file = File::create(&partial).map_err(|e| e.to_string())?;
    let mut w = BufWriter::with_capacity(1 << 22, out_file);
    w.write_all(b"JGEN").map_err(|e| e.to_string())?;
    w.write_all(&3u32.to_le_bytes()).map_err(|e| e.to_string())?;
    w.write_all(&total.to_le_bytes()).map_err(|e| e.to_string())?;

    let dev = Device::Cpu;
    let mut offset = 12usize;
    let (mut quantized, mut copied) = (0usize, 0usize);
    let (mut in_bytes, mut out_bytes) = (0u64, 0u64);

    for i in 0..total {
        let name_len = u16::from_le_bytes(mmap[offset..offset + 2].try_into().unwrap()) as usize;
        offset += 2;
        let name = std::str::from_utf8(&mmap[offset..offset + name_len])
            .map_err(|e| e.to_string())?
            .to_string();
        offset += name_len;
        let t_type = mmap[offset];
        offset += 1;

        // Record header + payload extents for the source record.
        let (header_bytes, payload_bytes, dims) = match t_type {
            1 => {
                let r = u32::from_le_bytes(mmap[offset..offset + 4].try_into().unwrap()) as usize;
                let c = u32::from_le_bytes(mmap[offset + 4..offset + 8].try_into().unwrap()) as usize;
                let k = u32::from_le_bytes(mmap[offset + 8..offset + 12].try_into().unwrap()) as usize;
                let payload = (r * k + k + c * k + c + r + k * k) * 2;
                (12usize, payload, None)
            }
            2 => {
                let r = u32::from_le_bytes(mmap[offset..offset + 4].try_into().unwrap()) as usize;
                let c = u32::from_le_bytes(mmap[offset + 4..offset + 8].try_into().unwrap()) as usize;
                (8usize, r * c * 2, Some((r, c)))
            }
            3 => {
                let l = u32::from_le_bytes(mmap[offset..offset + 4].try_into().unwrap()) as usize;
                (4usize, l * 2, None)
            }
            4 => {
                let payload =
                    u64::from_le_bytes(mmap[offset + 9..offset + 17].try_into().unwrap()) as usize;
                (17usize, payload, None)
            }
            other => return Err(format!("tensor {} ({}): unknown type {}", i, name, other)),
        };
        in_bytes += (header_bytes + payload_bytes) as u64;

        let target = dims.and_then(|(r, c)| plan(&name, r, c));
        if let (Some(dt), Some((rows, cols))) = (target, dims) {
            let raw = &mmap[offset + header_bytes..offset + header_bytes + payload_bytes];
            // f16 → f32. Chunked in rows to keep the peak at |W| f32, nothing more.
            let mut f32s = Vec::with_capacity(rows * cols);
            for ch in raw.chunks_exact(2) {
                f32s.push(half::f16::from_le_bytes([ch[0], ch[1]]).to_f32());
            }
            let t = Tensor::from_vec(f32s, (rows, cols), &dev).map_err(|e| e.to_string())?;
            let qt = QTensor::quantize(&t, dt).map_err(|e| e.to_string())?;
            let data = qt.data().map_err(|e| e.to_string())?;

            let nb = name.as_bytes();
            w.write_all(&(nb.len() as u16).to_le_bytes()).map_err(|e| e.to_string())?;
            w.write_all(nb).map_err(|e| e.to_string())?;
            w.write_all(&[4u8]).map_err(|e| e.to_string())?;
            w.write_all(&(rows as u32).to_le_bytes()).map_err(|e| e.to_string())?;
            w.write_all(&(cols as u32).to_le_bytes()).map_err(|e| e.to_string())?;
            w.write_all(&[ggml_id(dt)]).map_err(|e| e.to_string())?;
            w.write_all(&(data.len() as u64).to_le_bytes()).map_err(|e| e.to_string())?;
            w.write_all(&data).map_err(|e| e.to_string())?;
            out_bytes += (2 + nb.len() + 1 + 17 + data.len()) as u64;
            quantized += 1;
            if quantized % 32 == 0 {
                eprintln!(
                    "  … {} quantized / {} copied, {:.1} → {:.1} GB",
                    quantized, copied,
                    in_bytes as f64 / (1u64 << 30) as f64,
                    out_bytes as f64 / (1u64 << 30) as f64
                );
            }
        } else {
            // Verbatim: name + type byte + original header + payload.
            let nb = name.as_bytes();
            w.write_all(&(nb.len() as u16).to_le_bytes()).map_err(|e| e.to_string())?;
            w.write_all(nb).map_err(|e| e.to_string())?;
            w.write_all(&[t_type]).map_err(|e| e.to_string())?;
            w.write_all(&mmap[offset..offset + header_bytes + payload_bytes])
                .map_err(|e| e.to_string())?;
            out_bytes += (2 + nb.len() + 1 + header_bytes + payload_bytes) as u64;
            copied += 1;
        }
        offset += header_bytes + payload_bytes;
    }
    w.flush().map_err(|e| e.to_string())?;
    drop(w);
    std::fs::rename(&partial, outp).map_err(|e| e.to_string())?;

    // Sidecars travel with the model: meta.json (marked), tokenizer dir.
    let meta_in = format!("{}.meta.json", inp);
    if let Ok(txt) = std::fs::read_to_string(&meta_in) {
        let marked = if let Some(stripped) = txt.trim_end().strip_suffix('}') {
            format!("{},\n  \"quantized\": true\n}}", stripped.trim_end().trim_end_matches(','))
        } else {
            txt
        };
        std::fs::write(format!("{}.meta.json", outp), marked).map_err(|e| e.to_string())?;
    }
    let tok_in = format!("{}.tokenizer", inp);
    let tok_out = format!("{}.tokenizer", outp);
    if Path::new(&tok_in).is_dir() && !Path::new(&tok_out).exists() {
        copy_dir(&tok_in, &tok_out).map_err(|e| e.to_string())?;
    }

    println!(
        "done: {} tensors quantized, {} copied — {:.1} GB → {:.1} GB",
        quantized, copied,
        in_bytes as f64 / (1u64 << 30) as f64,
        out_bytes as f64 / (1u64 << 30) as f64
    );
    Ok(())
}

fn copy_dir(from: &str, to: &str) -> std::io::Result<()> {
    std::fs::create_dir_all(to)?;
    for entry in std::fs::read_dir(from)? {
        let entry = entry?;
        let dst = Path::new(to).join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir(entry.path().to_str().unwrap(), dst.to_str().unwrap())?;
        } else {
            std::fs::copy(entry.path(), dst)?;
        }
    }
    Ok(())
}
