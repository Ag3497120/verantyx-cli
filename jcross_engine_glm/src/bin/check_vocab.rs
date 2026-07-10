use jcross_engine_glm::JCrossEngine;
fn main() {
    let engine = JCrossEngine::load_jgen("../../model_glm.jgen").unwrap();
    let meta = engine.tensors.get("model.embed_tokens.weight").unwrap();
    println!("{:?}", meta.tensor_type);
}
