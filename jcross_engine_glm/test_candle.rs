use candle_core::{Tensor, DType, Device};
fn main() {
    let device = Device::Cpu;
    let x = Tensor::ones(&[6144], DType::F32, &device).unwrap();
    let w = Tensor::ones(&[4096], DType::F32, &device).unwrap();
    let res = x.broadcast_mul(&w);
    println!("Result: {:?}", res);
}
