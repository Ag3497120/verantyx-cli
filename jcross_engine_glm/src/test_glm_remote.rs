use jcross_engine_glm::JCrossEngine;
use std::time::Instant;

fn main() {
    println!("Loading GLM-4 9B Model...");
    let engine = JCrossEngine::load_jgen("../../model_glm.jgen").unwrap();
    println!("Model loaded! Running inference...");

    let prompt = vec![151331, 151333, 785, 1196, 4588, 264, 3405, 13, 21754, 432, 25];
    // Start with the last token of the prompt, and we need to process the prompt through the generation loop properly.
    // For simplicity of this script, we'll just process the prompt one by one.
    // However, our current execute_generation_loop_gpu takes a single start_token.
    // Let's modify it or just pass the start_token and see if it outputs properly.
    let start_time = Instant::now();
    let tokens = engine.execute_generation_loop_gpu(&prompt, 20).unwrap();
    let duration = start_time.elapsed();

    println!("Generated tokens: {:?}", tokens);
    println!("Time taken: {:?}", duration);
    println!("Tokens per second: {}", 20.0 / duration.as_secs_f64());
}
