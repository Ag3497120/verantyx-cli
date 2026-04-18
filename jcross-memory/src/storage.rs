use std::path::{Path, PathBuf};
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct TensionNode {
    pub id: String,
    pub description: String,
    pub created_at: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct JCrossGraph {
    pub nodes: Vec<String>, // Raw strings for now
    pub active_tensions: Vec<TensionNode>,
}

pub struct MemoryStorage {
    file_path: PathBuf,
    graph: JCrossGraph,
}

impl MemoryStorage {
    pub fn new(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        let file_path = path.as_ref().to_path_buf();
        if let Some(parent) = file_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        
        let graph = if file_path.exists() {
            let data = std::fs::read_to_string(&file_path)?;
            serde_json::from_str(&data).unwrap_or_default()
        } else {
            JCrossGraph::default()
        };
        
        Ok(Self { file_path, graph })
    }

    pub fn save(&self) -> anyhow::Result<()> {
        let data = serde_json::to_string_pretty(&self.graph)?;
        std::fs::write(&self.file_path, data)?;
        Ok(())
    }

    pub fn inject_node(&mut self, content: String) -> anyhow::Result<()> {
        self.graph.nodes.push(content);
        self.save()?;
        Ok(())
    }
    
    pub fn read_context(&self, query: &str) -> String {
        // Improved RAG: Split query into keywords and check for any matches (OR logic)
        // Also ensure we handle lowercase and handle noise words
        let keywords: Vec<&str> = query.split_whitespace()
            .filter(|w| w.len() > 2) // Ignore tiny words like 'a', 'in', 'to'
            .map(|w| w.trim_matches(|c: char| !c.is_alphanumeric()))
            .collect();
            
        if keywords.is_empty() {
             // Fallback to literal if no significant keywords
             let matches: Vec<&String> = self.graph.nodes.iter()
                .filter(|n| n.contains(query))
                .collect();
             return if matches.is_empty() { "No relevant information found.".to_string() } else { matches.into_iter().map(|s| s.as_str()).collect::<Vec<&str>>().join("\n---\n") };
        }

        let mut matched_nodes = Vec::new();
        for node in &self.graph.nodes {
            let node_lower = node.to_lowercase();
            // Rank by how many keywords match
            let mut match_count = 0;
            for kw in &keywords {
                if node_lower.contains(&kw.to_lowercase()) {
                    match_count += 1;
                }
            }
            
            if match_count > 0 {
                matched_nodes.push((match_count, node));
            }
        }
        
        // Sort by match count (descending)
        matched_nodes.sort_by(|a, b| b.0.cmp(&a.0));
            
        if matched_nodes.is_empty() {
            return format!("No relevant JCross memory found for keywords: {:?}.", keywords);
        }
        
        // Take top 5 nodes to avoid context overflow
        matched_nodes.into_iter()
            .take(5)
            .map(|(_, s)| s.as_str())
            .collect::<Vec<&str>>()
            .join("\n---\n")
    }

    pub fn add_tension(&mut self, description: String) -> anyhow::Result<String> {
        let id = format!("ts_{}", uuid::Uuid::new_v4().simple());
        self.graph.active_tensions.push(TensionNode {
            id: id.clone(),
            description,
            created_at: chrono::Utc::now().to_rfc3339(),
        });
        self.save()?;
        Ok(id)
    }

    pub fn resolve_tension(&mut self, tension_id: &str, resolution: String) -> anyhow::Result<bool> {
        let initial_len = self.graph.active_tensions.len();
        self.graph.active_tensions.retain(|t| t.id != tension_id);
        if self.graph.active_tensions.len() < initial_len {
            self.inject_node(format!("<< RESOLUTION FOR {} >>\n{}", tension_id, resolution))?;
            return Ok(true);
        }
        Ok(false)
    }
    
    pub fn get_tensions(&self) -> Vec<TensionNode> {
        self.graph.active_tensions.clone()
    }
}
