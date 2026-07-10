use jcross_engine_glm::JCrossEngine;
fn main() {
    let engine = JCrossEngine::load_jgen("../../model_glm.jgen").unwrap();
    let mut count = 0;
    for (k, _) in &engine.tensors {
        if k.contains("self_attn") && k.contains("layer") && k.contains("0") {
            println!("{}", k);
            count += 1;
        }
    }
    println!("Total attn tensors: {}", count);
}
