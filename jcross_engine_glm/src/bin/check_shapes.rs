use jcross_engine_glm::JCrossEngine;

fn main() {
    let engine = JCrossEngine::load_jgen("../model_glm.jgen").unwrap();
    for key in engine.tensors.keys() {
        if key.contains("layers.0.") {
            let meta = engine.tensors.get(key).unwrap();
            println!("{}: {:?}", key, meta.tensor_type);
        }
    }
}
