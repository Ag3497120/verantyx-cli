use jcross_engine_glm::JCrossEngine;
use std::env;

fn main() {
    let engine = JCrossEngine::load_jgen("../../model_glm.jgen").unwrap();
    let tensors = &engine.tensors;
    
    let to_check = [
        "model.layers.0.self_attn.q_a_proj.weight",
        "model.layers.0.self_attn.q_b_proj.weight",
        "model.layers.0.self_attn.kv_a_proj_with_mqa.weight",
        "model.layers.0.self_attn.kv_b_proj.weight",
        "model.layers.0.self_attn.o_proj.weight",
        "model.layers.0.self_attn.core_attention.wo.weight",
        "model.layers.0.self_attn.core_attention.wq.weight",
        "model.layers.0.self_attn.core_attention.wk.weight",
        "model.layers.0.self_attn.core_attention.wv.weight",
        "model.layers.0.input_layernorm.weight",
        "model.layers.79.input_layernorm.weight",
        "model.layers.40.input_layernorm.weight",
    ];
    
    for name in &to_check {
        if let Some(meta) = tensors.get(*name) {
            println!("{}: {:?}", name, meta.tensor_type);
        } else {
            println!("{}: Not found", name);
        }
    }
    
    // Count layers
    let mut layer_count = 0;
    while tensors.contains_key(&format!("model.layers.{}.input_layernorm.weight", layer_count)) {
        layer_count += 1;
    }
    println!("Total layers found: {}", layer_count);
}
