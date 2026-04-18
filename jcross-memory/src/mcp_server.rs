use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::io::{AsyncBufReadExt, BufReader};
use std::collections::HashMap;

#[derive(Serialize, Deserialize, Debug)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: Option<Value>,
    pub method: String,
    pub params: Option<Value>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
}

pub struct McpServer {
    tools: HashMap<String, Box<dyn Fn(Value) -> anyhow::Result<Value> + Send + Sync>>,
}

impl McpServer {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
        }
    }

    pub fn register_tool<F>(&mut self, name: &str, handler: F)
    where
        F: Fn(Value) -> anyhow::Result<Value> + Send + Sync + 'static,
    {
        self.tools.insert(name.to_string(), Box::new(handler));
    }

    pub async fn run_stdio(&self) -> anyhow::Result<()> {
        let stdin = tokio::io::stdin();
        let mut reader = BufReader::new(stdin);
        
        loop {
            let mut line = String::new();
            let bytes_read = reader.read_line(&mut line).await?;
            if bytes_read == 0 { break; } // EOF

            let line = line.trim();
            if line.is_empty() { continue; }

            // MCP over stdio uses line-delimited JSON, not headers.
            if let Ok(req) = serde_json::from_str::<JsonRpcRequest>(line) {
                self.handle_request(req).await;
            }
        }
        Ok(())
    }

    async fn handle_request(&self, req: JsonRpcRequest) {
        if let Some(id) = req.id {
            let mut response = JsonRpcResponse {
                jsonrpc: "2.0".to_string(),
                id: id.clone(),
                result: None,
                error: None,
            };

            // MCP Initialize handshake
            if req.method == "initialize" {
                response.result = Some(serde_json::json!({
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "jcross-memory",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": { "listChanged": true }
                    }
                }));
            } 
            else if req.method == "tools/list" {
                // Return schema definition for our tools
                response.result = Some(serde_json::json!({
                    "tools": [
                        {
                            "name": "read_jcross_node",
                            "description": "Read a specific JCross node or context region",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": { "type": "string" },
                                    "depth": { "type": "integer" }
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "inject_jcross_memory",
                            "description": "Inject new memory or observation into the spatial graph",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "node_type": { "type": "string" },
                                    "content": { "type": "string" },
                                    "parent_links": { "type": "array", "items": { "type": "string" } }
                                },
                                "required": ["node_type", "content"]
                            }
                        },
                        {
                            "name": "get_active_tensions",
                            "description": "List all active Tension Voids (missing knowledge/tasks) demanding resolution",
                            "inputSchema": {
                                "type": "object",
                                "properties": {}
                            }
                        },
                        {
                            "name": "resolve_tension",
                            "description": "Submit a JCross resolution payload to fill an active Tension Void",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "tension_id": { "type": "string" },
                                    "resolution_jcross": { "type": "string" }
                                },
                                "required": ["tension_id", "resolution_jcross"]
                            }
                        }
                    ]
                }));
            }
            else if req.method == "tools/call" {
                if let Some(params) = req.params {
                    if let Some(name) = params.get("name").and_then(|v| v.as_str()) {
                        let arguments = params.get("arguments").cloned().unwrap_or(serde_json::json!({}));
                        if let Some(handler) = self.tools.get(name) {
                            match handler(arguments) {
                                Ok(content) => {
                                    response.result = Some(serde_json::json!({
                                        "content": [{ "type": "text", "text": content.as_str().unwrap_or_default() }]
                                    }));
                                },
                                Err(e) => {
                                    response.error = Some(JsonRpcError {
                                        code: -32000,
                                        message: e.to_string(),
                                    });
                                }
                            }
                        } else {
                            response.error = Some(JsonRpcError { code: -32601, message: "Tool not found".to_string() });
                        }
                    }
                }
            } else {
                // Not supported
                response.error = Some(JsonRpcError { code: -32601, message: "Method not supported".to_string() });
            }

            // Send response back as single-line JSON
            if let Ok(res_str) = serde_json::to_string(&response) {
                println!("{}", res_str);
            }
        }
    }
}
