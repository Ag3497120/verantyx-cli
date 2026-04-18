mod mcp_server;
mod storage;

use std::sync::{Arc, Mutex};
use mcp_server::McpServer;
use storage::MemoryStorage;
use serde_json::Value;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();
    
    // Store graph in local data/jcross_mcp.json for reliability
    let db_path = "/Users/motonishikoudai/verantyx-cli/jcross-memory/data/jcross_mcp.json";
    let storage = Arc::new(Mutex::new(MemoryStorage::new(db_path)?));
    
    let mut server = McpServer::new();

    // Check if empty and inject initial dummy tension for testing
    {
        let mut guard = storage.lock().unwrap();
        if guard.get_tensions().is_empty() {
            let _ = guard.add_tension("SYSTEM_BOOTSTRAP_VOID: The JCross memory space is initialized but lacks core architectural mappings. Please read the documentation and inject the basic structure.".to_string());
        }
    }

    // Tool 1: read_jcross_node
    let storage_clone = storage.clone();
    server.register_tool("read_jcross_node", move |args: Value| {
        let query = args.get("query").and_then(|q| q.as_str()).unwrap_or("").to_string();
        let guard = storage_clone.lock().unwrap();
        let result = guard.read_context(&query);
        Ok(serde_json::json!(result))
    });

    // Tool 2: inject_jcross_memory
    let storage_clone = storage.clone();
    server.register_tool("inject_jcross_memory", move |args: Value| {
        let content = args.get("content").and_then(|c| c.as_str()).unwrap_or("").to_string();
        let node_type = args.get("node_type").and_then(|c| c.as_str()).unwrap_or("Unknown").to_string();
        
        let mut guard = storage_clone.lock().unwrap();
        let injection_str = format!("[{}] {}", node_type, content);
        guard.inject_node(injection_str)?;
        
        Ok(serde_json::json!("Successfully injected JCross Node"))
    });

    // Tool 3: get_active_tensions
    let storage_clone = storage.clone();
    server.register_tool("get_active_tensions", move |_args: Value| {
        let guard = storage_clone.lock().unwrap();
        let tensions = guard.get_tensions();
        
        if tensions.is_empty() {
            return Ok(serde_json::json!("No active tensions in the JCross graph. System is stable."));
        }
        
        let report: Vec<String> = tensions.into_iter().map(|t| {
            format!("ID: {} | Created: {} | Void: {}", t.id, t.created_at, t.description)
        }).collect();
        
        Ok(serde_json::json!(report.join("\n")))
    });

    // Tool 4: resolve_tension
    let storage_clone = storage.clone();
    server.register_tool("resolve_tension", move |args: Value| {
        let tension_id = args.get("tension_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let resolution = args.get("resolution_jcross").and_then(|v| v.as_str()).unwrap_or("").to_string();
        
        let mut guard = storage_clone.lock().unwrap();
        if guard.resolve_tension(&tension_id, resolution)? {
            Ok(serde_json::json!(format!("Tension {} fully resolved and sealed.", tension_id)))
        } else {
            Ok(serde_json::json!(format!("Tension {} not found across local graph.", tension_id)))
        }
    });

    // Tool 5: (Admin) create_test_tension
    let storage_clone = storage.clone();
    server.register_tool("create_test_tension", move |args: Value| {
        let desc = args.get("description").and_then(|v| v.as_str()).unwrap_or("A standard system tension void generated for testing").to_string();
        let mut guard = storage_clone.lock().unwrap();
        let id = guard.add_tension(desc)?;
        Ok(serde_json::json!(format!("Created new tension void: {}", id)))
    });

    // Start listening on STDIO
    server.run_stdio().await?;

    Ok(())
}
