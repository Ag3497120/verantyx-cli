use std::thread;

pub fn prefetch_tensor_async(mmap_ptr: usize, offset: usize, length: usize, name: String) {
    thread::spawn(move || {
        let mut dummy: u64 = 0;
        let start = mmap_ptr + offset;
        let end = start + length;
        let mut ptr = start;
        while ptr < end {
            unsafe {
                dummy = dummy.wrapping_add(*(ptr as *const u8) as u64);
            }
            ptr += 4096;
        }
        std::hint::black_box(dummy);
        // Only print for layer 3 gate_proj to avoid spam
        if name.contains("layer.3") && name.contains("gate_proj") {
            println!("[Prefetch] Background load finished for {}", name);
        }
    });
}
