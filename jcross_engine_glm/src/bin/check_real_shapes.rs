use jcross_engine_glm::JCrossEngine;

fn main() {
    let engine = JCrossEngine::load_jgen("../../model_glm.jgen").unwrap();
    if let Some(meta) = engine.tensors.get("model.layers.0.self_attn.o_proj.weight") {
        println!("o_proj shape: {:?}", meta.tensor_type);
    }
    if let Some(meta) = engine.tensors.get("model.layers.0.self_attn.kv_a_proj_with_mqa.weight") {
        println!("kv_a_proj_with_mqa shape: {:?}", meta.tensor_type);
    }
    if let Some(meta) = engine.tensors.get("model.layers.0.self_attn.q_a_proj.weight") {
        println!("q_a_proj shape: {:?}", meta.tensor_type);
    }
    if let Some(meta) = engine.tensors.get("model.layers.0.self_attn.indexer.wq_b.weight") {
        println!("indexer wq_b shape: {:?}", meta.tensor_type);
    }
}
