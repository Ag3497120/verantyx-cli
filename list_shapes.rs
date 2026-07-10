use std::fs::File;
use std::io::{Read, BufReader, Seek, SeekFrom};
use std::convert::TryInto;

fn main() {
    let mut file = BufReader::with_capacity(1024*1024*10, File::open("/home/ubuntu/model_glm.jgen").unwrap());
    let mut magic = [0u8; 4];
    file.read_exact(&mut magic).unwrap();
    assert_eq!(&magic, b"JGEN");
    let mut version = [0u8; 4];
    file.read_exact(&mut version).unwrap();
    
    loop {
        let mut name_len_bytes = [0u8; 4];
        if file.read_exact(&mut name_len_bytes).is_err() { break; }
        let name_len = u32::from_le_bytes(name_len_bytes) as usize;
        let mut name_bytes = vec![0u8; name_len];
        file.read_exact(&mut name_bytes).unwrap();
        let name = String::from_utf8(name_bytes).unwrap();
        
        let mut tensor_type_bytes = [0u8; 4];
        file.read_exact(&mut tensor_type_bytes).unwrap();
        let tensor_type = u32::from_le_bytes(tensor_type_bytes);
        
        if tensor_type == 1 {
            let mut meta = [0u8; 12];
            file.read_exact(&mut meta).unwrap();
            let rows = u32::from_le_bytes(meta[0..4].try_into().unwrap());
            let cols = u32::from_le_bytes(meta[4..8].try_into().unwrap());
            let rank = u32::from_le_bytes(meta[8..12].try_into().unwrap());
            if name.contains("layers.0") && name.contains("self_attn") {
                println!("{}: SVDLossless {}x{} (rank {})", name, rows, cols, rank);
            }
            let skip_bytes = (rows * rank * 2) + (rank * 2) + (rank * cols * 2) + (cols * 2) + (rows * 2) + (rank * rank * 2);
            file.seek(SeekFrom::Current(skip_bytes as i64)).unwrap();
        } else if tensor_type == 2 {
            let mut meta = [0u8; 8];
            file.read_exact(&mut meta).unwrap();
            let rows = u32::from_le_bytes(meta[0..4].try_into().unwrap());
            let cols = u32::from_le_bytes(meta[4..8].try_into().unwrap());
            if name.contains("layers.0") && name.contains("self_attn") {
                println!("{}: Dense2D {}x{}", name, rows, cols);
            }
            let skip_bytes = rows * cols * 2;
            file.seek(SeekFrom::Current(skip_bytes as i64)).unwrap();
        } else if tensor_type == 3 {
            let mut meta = [0u8; 4];
            file.read_exact(&mut meta).unwrap();
            let numel = u32::from_le_bytes(meta);
            if name.contains("layers.0") && name.contains("self_attn") {
                println!("{}: Dense1D {}", name, numel);
            }
            let skip_bytes = numel * 2;
            file.seek(SeekFrom::Current(skip_bytes as i64)).unwrap();
        }
    }
}
