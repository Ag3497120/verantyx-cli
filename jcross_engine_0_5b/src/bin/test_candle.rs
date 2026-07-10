use candle_core::{Device, Tensor};
use half::f16;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let device = Device::new_metal(0)?;
    println!("Using device: {:?}", device);

    let data: Vec<f16> = vec![f16::from_f32(1.0), f16::from_f32(2.0), f16::from_f32(3.0), f16::from_f32(4.0)];
    let tensor = Tensor::from_slice(&data, (2, 2), &device)?;
    
    let x_data: Vec<f16> = vec![f16::from_f32(1.0), f16::from_f32(1.0)];
    let x = Tensor::from_slice(&x_data, (2, 1), &device)?;

    let y = tensor.matmul(&x)?;
    
    println!("y: {:?}", y.to_vec2::<f16>()?);

    Ok(())
}
