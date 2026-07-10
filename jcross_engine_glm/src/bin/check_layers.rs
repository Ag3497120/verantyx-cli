use jcross_engine_glm::JCrossEngine;

fn main() {
    let engine = JCrossEngine::load_jgen("../model_glm.jgen").unwrap();
    let mut max_layer = 0;
    for key in engine.tensors.keys() {
        if key.contains("model.layers.") {
            let parts: Vec<&str> = key.split('.').collect();
            for i in 0..parts.len() {
                if parts[i] == "layers" && i + 1 < parts.len() {
                    if let Ok(layer_idx) = parts[i+1].parse::<usize>() {
                        if layer_idx > max_layer {
                            max_layer = layer_idx;
                        }
                    }
                }
            }
        }
    }
    println!("Max layer index: {}", max_layer);
    println!("Total layers: {}", max_layer + 1);
}
