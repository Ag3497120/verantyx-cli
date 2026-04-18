use ronin_core::memory_bridge::spatial_index::SpatialIndex;
use std::path::PathBuf;
use std::env;
use serde_json::json;

#[derive(serde::Deserialize)]
struct QueryRequest {
    queries: Vec<String>,
    domain: Option<String>,
    limit: Option<usize>,
}

#[tokio::main]
async fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: query_jcross '<json_request>'");
        eprintln!("Example: query_jcross '{{\"queries\": [\"bike\", \"car\"], \"domain\": \"personal\"}}'");
        std::process::exit(1);
    }
    
    let req: QueryRequest = match serde_json::from_str(&args[1]) {
        Ok(r) => r,
        Err(e) => {
            // Fallback for legacy simple string query
            QueryRequest {
                queries: vec![args[1].clone()],
                domain: None,
                limit: None,
            }
        }
    };
    
    let env_target = env::var("JCROSS_TARGET_DIR").unwrap_or_else(|_| "/Users/motonishikoudai/verantyx-cli/verantyx-browser/.ronin".to_string());
    let root_path = PathBuf::from(env_target); 
    let mut index = SpatialIndex::new(root_path);
    
    if let Err(e) = index.hydrate().await {
        eprintln!("Error hydrating index: {:?}", e);
        std::process::exit(1);
    }
    
    let limit = req.limit.unwrap_or(10);
    let nearest = index.query_v5(&req.queries, req.domain.as_deref(), limit);
    
    let results: Vec<_> = nearest.iter().map(|n| {
        json!({
            "key": n.key,
            "concept": n.concept,
            "domain": n.domain,
            "content": n.content,
            "kanji_tags": n.kanji_tags.iter().map(|tag| format!("[{}:{}]", tag.name, tag.weight)).collect::<Vec<_>>(),
        })
    }).collect();
    
    let output = json!({
        "results": results
    });
    
    println!("{}", serde_json::to_string(&output).unwrap());
}
