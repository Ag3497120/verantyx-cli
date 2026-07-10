use jcross_engine_glm::JCrossEngine;
fn main() {
    let engine = JCrossEngine::load_jgen("../../model_glm.jgen").unwrap();
    let mut indexer_layers = std::collections::BTreeSet::new();
    for (k, _) in &engine.tensors {
        if k.contains("indexer") {
            let parts: Vec<&str> = k.split('.').collect();
            if let Some(layer) = parts.get(2) {
                if let Ok(l) = layer.parse::<usize>() {
                    indexer_layers.insert(l);
                }
            }
        }
    }
    println!("Indexer layers: {:?}", indexer_layers);
}
