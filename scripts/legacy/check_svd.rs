fn main() {
    let bytes = std::fs::read("qwen_0.5b_full.jgen").unwrap();
    let mut offset = 8;
    let mut has_svd = false;
    while offset < bytes.len() {
        let name_len = u32::from_le_bytes(bytes[offset..offset+4].try_into().unwrap()) as usize;
        offset += 4;
        offset += name_len;
        let tensor_type = u32::from_le_bytes(bytes[offset..offset+4].try_into().unwrap());
        offset += 4;
        if tensor_type == 1 {
            has_svd = true;
            break;
        } else if tensor_type == 2 {
            let rows = u32::from_le_bytes(bytes[offset..offset+4].try_into().unwrap());
            let cols = u32::from_le_bytes(bytes[offset+4..offset+8].try_into().unwrap());
            offset += 8;
            offset += (rows * cols * 2) as usize;
        } else if tensor_type == 3 {
            let length = u32::from_le_bytes(bytes[offset..offset+4].try_into().unwrap());
            offset += 4;
            offset += (length * 2) as usize;
        }
    }
    println!("Has SVDLossless: {}", has_svd);
}
