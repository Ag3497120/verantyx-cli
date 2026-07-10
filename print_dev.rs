use candle_core::Device;
fn main() {
    let d = Device::new_cuda(0);
    println!("CUDA Device: {:?}", d);
}
