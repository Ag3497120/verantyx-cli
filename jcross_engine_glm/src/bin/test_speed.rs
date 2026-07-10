use jcross_engine_glm::JCrossEngine;
use std::time::Instant;

fn main() {
    let mut engine = JCrossEngine::load_jgen("../qwen_0.5b_full.jgen").unwrap();
    
    println!("Starting generation...");
    let start = Instant::now();
    let tokens = engine.execute_generation_loop_gpu(&[1234], 100).unwrap();
    let duration = start.elapsed();
    
    println!("Generated 100 tokens in {:?}", duration);
    println!("Tokens/sec: {}", 100.0 / duration.as_secs_f64());
}
