use jcross_engine_glm::JCrossEngine;

fn main() {
    let engine = JCrossEngine::load_jgen("../../model_glm.jgen").unwrap();
    let tensors = &engine.tensors;
    
    let to_check = [
        "model.layers.3.mlp.gate.weight",
        "model.layers.3.mlp.gate.e_score_correction_bias",
        "model.layers.3.mlp.shared_experts.gate_proj.weight",
        "model.layers.3.mlp.shared_experts.down_proj.weight",
        "model.layers.3.mlp.experts.0.gate_proj.weight",
    ];
    
    for name in &to_check {
        if let Some(meta) = tensors.get(*name) {
            println!("{}: {:?}", name, meta.tensor_type);
        } else {
            println!("{}: Not found", name);
        }
    }
}
