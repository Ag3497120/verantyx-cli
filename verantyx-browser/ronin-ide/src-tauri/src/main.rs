// Prevents additional console window on Windows in release
#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use ronin_core::memory_bridge::spatial_index::MemoryNode;
use ronin_core::memory_bridge::kanji_ontology::{KanjiOp, KanjiTag, TypedRelation, RelationType};

/// A custom Tauri command that queries the JCross V4 Spatial Engine directly in-memory!
/// Zero MCP overhead. Zero JSON-RPC outside the process boundaries.
#[tauri::command]
fn query_jcross(search_text: &str) -> String {
    println!("🧠 [Ronin Limbic System] Received Reflex Search: {}", search_text);
    
    // In the future, this will link your massive spatial graph.
    // For now, we simulate a Native Graph Hit to prove UI -> Rust connection.
    let root_node = MemoryNode::new_front("ROOT", &format!("JCross Found Match for: {}", search_text));
    
    // Simulate a native memory response
    format!("[Native Core] Absolute Truth: {}", root_node.content)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![query_jcross])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
