//! JCross v4 6-Axis Semantic Engine (Kanji Spatial Ontology)
//!
//! Upgraded from v3 JSON graphs to flat text `.jcross` semantic documents with a 
//! lightweight `.jidx` indexing layer. Memories are driven by symbolic Kanji operators.

use crate::domain::error::{Result, RoninError};
use crate::domain::types::MemoryZone;
use crate::memory_bridge::kanji_ontology::{KanjiOp, KanjiTag, TypedRelation, RelationType};
use chrono::{DateTime, Utc, TimeZone};
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use tokio::fs;
use tracing::info;

// ─────────────────────────────────────────────────────────────────────────────
// Spatial Memory Node (JCross V4)
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MemoryNode {
    pub key: String,
    
    // Core Kanji Semantic Engine Tensors
    pub kanji_tags: Vec<KanjiTag>,
    pub relations: Vec<TypedRelation>,
    
    // 6-Axis Contextual Dimensions
    pub concept: String,
    pub domain: String,
    pub time_stamp: f64,
    pub abstract_level: f64,
    
    // Core payload (V6 Layered Cortex)
    pub l1_content: String, // High-density Cache
    pub l2_raw: String,     // Lossless Archive
    pub content: String,    // Legacy compat (points to l1_content)
    
    // Temporary variables matching legacy compat
    pub zone: MemoryZone,
    pub confidence: f64,
    pub utility: f64,
    pub created_at: DateTime<Utc>,
    pub weight: f32,
    
    // Reflex Engine (Muscle Memory)
    pub reflex_action: Option<String>,
    pub env_hash: Option<String>,
}

impl Default for MemoryNode {
    fn default() -> Self {
        Self {
            key: "UNCLASSIFIED".to_string(),
            kanji_tags: vec![],
            relations: vec![],
            concept: String::new(),
            domain: "unclassified".to_string(),
            time_stamp: Utc::now().timestamp() as f64,
            abstract_level: 0.5,
            l1_content: String::new(),
            l2_raw: String::new(),
            content: String::new(),
            zone: MemoryZone::Mid,
            confidence: 1.0,
            utility: 1.0,
            created_at: Utc::now(),
            weight: 1.0,
            reflex_action: None,
            env_hash: None,
        }
    }
}

impl MemoryNode {
    pub fn new_v4(key: &str, content: &str) -> Self {
        Self {
            key: key.to_string(),
            content: content.to_string(),
            ..Default::default()
        }
    }

    pub fn new_front(key: &str, content: &str) -> Self {
        let mut node = Self::new_v4(key, content);
        node.zone = MemoryZone::Front;
        node
    }

    pub fn parse_jcross(raw: &str) -> Option<Self> {
        use std::sync::OnceLock;
        let mut node = Self::default();
        
        static ID_RE: OnceLock<regex::Regex> = OnceLock::new();
        let id_re = ID_RE.get_or_init(|| regex::Regex::new(r"■ JCROSS_NODE_([^\s]+)").unwrap());
        if let Some(cap) = id_re.captures(raw) {
            node.key = cap[1].trim().to_string();
        } else {
            return None; // Invalid file format lacking strict header
        }

        static TAGS_RE: OnceLock<regex::Regex> = OnceLock::new();
        let tags_re = TAGS_RE.get_or_init(|| regex::Regex::new(r"【空間座相】\s*([^\r\n]+)").unwrap());
        if let Some(cap) = tags_re.captures(raw) {
            let tags_str = &cap[1];
            for p in tags_str.split("] [") {
                let resolved_tags = KanjiTag::resolve(p.trim());
                node.kanji_tags.extend(resolved_tags);
            }
        }

        static CONCEPT_RE: OnceLock<regex::Regex> = OnceLock::new();
        let concept_re = CONCEPT_RE.get_or_init(|| regex::Regex::new(r"【次元概念】\s*([^\r\n]+)").unwrap());
        if let Some(cap) = concept_re.captures(raw) {
            node.concept = cap[1].trim().to_string();
        }

        static DOMAIN_RE: OnceLock<regex::Regex> = OnceLock::new();
        let domain_re = DOMAIN_RE.get_or_init(|| regex::Regex::new(r"【領域】\s*([^\r\n]+)").unwrap());
        if let Some(cap) = domain_re.captures(raw) {
            node.domain = cap[1].trim().to_string();
        }

        static TIME_RE: OnceLock<regex::Regex> = OnceLock::new();
        let time_re = TIME_RE.get_or_init(|| regex::Regex::new(r"【時間刻印】\s*([^\r\n]+)").unwrap());
        if let Some(cap) = time_re.captures(raw) {
            if let Ok(dt) = DateTime::parse_from_rfc3339(cap[1].trim()) {
                node.time_stamp = dt.timestamp() as f64;
            }
        }

        static ENV_RE: OnceLock<regex::Regex> = OnceLock::new();
        let env_re = ENV_RE.get_or_init(|| regex::Regex::new(r"【環境刻印】\s*([^\r\n]+)").unwrap());
        if let Some(cap) = env_re.captures(raw) {
            node.env_hash = Some(cap[1].trim().to_string());
        }

        static ABS_RE: OnceLock<regex::Regex> = OnceLock::new();
        let abs_re = ABS_RE.get_or_init(|| regex::Regex::new(r"【抽象度】\s*([\d\.]+)").unwrap());
        if let Some(cap) = abs_re.captures(raw) {
            node.abstract_level = cap[1].trim().parse::<f64>().unwrap_or(0.5);
        }

        static REL_BLOCK_RE: OnceLock<regex::Regex> = OnceLock::new();
        let rel_block_re = REL_BLOCK_RE.get_or_init(|| regex::Regex::new(r"【連帯】\s*([\s\S]*?)(?:【|\[)").unwrap());
        if raw.contains("【連帯】") {
            if let Some(cap) = rel_block_re.captures(raw) {
                for line in cap[1].lines() {
                    let ln = line.trim();
                    let r_parts: Vec<&str> = ln.split(':').collect();
                    if r_parts.len() >= 2 {
                        let target = r_parts[0].trim().to_string();
                        let r_type = RelationType::from_str(r_parts[1].trim());
                        let str_val = if r_parts.len() > 2 { r_parts[2].parse::<f32>().unwrap_or(0.5) } else { 0.5 };
                        node.relations.push(TypedRelation { target_id: target, rel_type: r_type, strength: str_val });
                    }
                }
            }
        }

        static REFLEX_RE: OnceLock<regex::Regex> = OnceLock::new();
        let reflex_re = REFLEX_RE.get_or_init(|| regex::Regex::new(r"【反射】\s*([\s\S]*?)\s*===").unwrap());
        if raw.contains("【反射】") {
            if let Some(cap) = reflex_re.captures(raw) {
                node.reflex_action = Some(cap[1].trim().to_string());
            }
        }

        static L1_RE: OnceLock<regex::Regex> = OnceLock::new();
        let l1_re = L1_RE.get_or_init(|| regex::Regex::new(r"\[L1_Cache\]\s*([\s\S]*?)(?:\s*\[|==|---)").unwrap());
        if raw.contains("[L1_Cache]") {
            if let Some(cap) = l1_re.captures(raw) {
                node.l1_content = cap[1].trim().to_string();
                node.content = node.l1_content.clone();
            }
        }

        static L2_RE: OnceLock<regex::Regex> = OnceLock::new();
        let l2_re = L2_RE.get_or_init(|| regex::Regex::new(r"\[L2_Archive\]\s*([\s\S]*?)\s*===").unwrap());
        if raw.contains("[L2_Archive]") {
            if let Some(cap) = l2_re.captures(raw) {
                node.l2_raw = cap[1].trim().to_string();
            }
        }

        static CONTENT_RE: OnceLock<regex::Regex> = OnceLock::new();
        let content_re = CONTENT_RE.get_or_init(|| regex::Regex::new(r"\[本質記憶\]\s*([\s\S]*?)\s*===").unwrap());
        if raw.contains("[本質記憶]") {
            if let Some(cap) = content_re.captures(raw) {
                let body = cap[1].trim().to_string();
                if node.l1_content.is_empty() {
                    node.l1_content = body.clone();
                    node.content = body;
                }
                if node.l2_raw.is_empty() {
                    node.l2_raw = cap[1].trim().to_string();
                }
            }
        }

        if node.key == "UNCLASSIFIED" { return None; }
        
        Some(node)
    }

    /// Serializes back into human-readable `.jcross` format
    pub fn to_jcross(&self) -> String {
        let stamps_str = self.kanji_tags.iter().map(|t| format!("[{}:{}]", t.name, t.weight)).collect::<Vec<_>>().join(" ");
        let relations_str = self.relations.iter()
            .map(|r| {
                let r_name = match &r.rel_type {
                    RelationType::Derived => "派生",
                    RelationType::Base => "基底",
                    RelationType::Similar => "類似",
                    RelationType::Opposite => "対立",
                    RelationType::Prev => "前項",
                    RelationType::Next => "次項",
                    RelationType::Cause => "因果",
                    RelationType::Fix => "訂正",
                    RelationType::Context => "補足",
                    RelationType::Unknown(name) => name.as_str()
                };
                format!("{}:{}:{}", r.target_id, r_name, r.strength)
            })
            .collect::<Vec<_>>().join("\n");
        let dt = Utc.timestamp_opt(self.time_stamp as i64, 0).unwrap();

        let mut out = format!(
r#"■ JCROSS_NODE_{}

【空間座相】
{}

【次元概念】
{}

【領域】
{}

【時間刻印】
{}

【連帯】
{}

【抽象度】
{}
"#,
            self.key, stamps_str, self.concept, self.domain, dt.to_rfc3339(), relations_str, self.abstract_level
        );

        if let Some(ref env) = self.env_hash {
            out.push_str("\n【環境刻印】\n");
            out.push_str(env);
            out.push_str("\n");
        }

        if let Some(ref reflex) = self.reflex_action {
            out.push_str("\n【反射】\n");
            out.push_str(reflex);
            out.push_str("\n===\n");
        }

        out.push_str("\n---\n[L1_Cache]\n");
        out.push_str(&self.l1_content);
        out.push_str("\n\n[L2_Archive]\n");
        out.push_str(&self.l2_raw);
        out.push_str("\n===\n");
        
        out
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Token Overlap (Bi-gram String Similarity for English & Japanese)
// ─────────────────────────────────────────────────────────────────────────────

fn token_overlap(a: &str, b: &str) -> f64 {
    fn bigrams(text: &str) -> HashSet<String> {
        let chars: Vec<char> = text.chars().filter(|c| !c.is_whitespace()).collect();
        let mut set = HashSet::new();
        if chars.len() < 2 {
            if chars.len() == 1 { set.insert(chars[0].to_string()); }
            return set;
        }
        for i in 0..chars.len() - 1 {
            let mut s = String::new();
            s.push(chars[i]);
            s.push(chars[i+1]);
            set.insert(s);
        }
        set
    }
    
    let set_a = bigrams(a);
    let set_b = bigrams(b);
    if set_a.is_empty() || set_b.is_empty() { return 0.0; }
    let intersection = set_a.intersection(&set_b).count() as f64;
    let union = set_a.union(&set_b).count() as f64;
    intersection / union
}

fn keyword_score(text: &str, query: &str) -> f64 {
    let query_words: HashSet<String> = query.to_lowercase().split_whitespace().map(|s| s.to_string()).collect();
    let text_lower = text.to_lowercase();
    
    if query_words.is_empty() { return 0.0; }
    
    let mut hits = 0;
    for qw in &query_words {
        if text_lower.contains(qw) {
            hits += 1;
        }
    }
    
    (hits as f64) / (query_words.len() as f64)
}

// ─────────────────────────────────────────────────────────────────────────────
// Spatial Index (V4 Indexing Layer)
// ─────────────────────────────────────────────────────────────────────────────

pub struct SpatialIndex {
    pub root: PathBuf,
    pub nodes: HashMap<String, MemoryNode>,
    pub ontology: HashMap<String, KanjiOp>,
    pub doc_freqs: HashMap<String, usize>, // Global term frequencies for IDF
    pub total_docs: usize,
}

impl SpatialIndex {
    pub fn new(root: PathBuf) -> Self {
        Self { 
            root, 
            nodes: HashMap::new(),
            ontology: KanjiOp::standard_ontology(),
            doc_freqs: HashMap::new(),
            total_docs: 0,
        }
    }

    pub fn read_node(&self, key: &str) -> Option<MemoryNode> {
        self.nodes.get(key).cloned()
    }

    pub fn list_all_keys(&self) -> Vec<String> {
        self.nodes.keys().cloned().collect()
    }

    pub fn calculate_structural_tension(&self) -> (f64, Option<String>) {
        let mut base_tensions: std::collections::HashMap<String, f64> = std::collections::HashMap::new();

        // Pass 1: Local Inherent Tension Calculation
        for node in self.nodes.values() {
            let mut inherent_tension = 0.0;
            
            if node.abstract_level > 0.7 {
                let connected_count = node.relations.len();
                if connected_count < 2 {
                    let mut thirst_multiplier = 1.0;
                    for tag in &node.kanji_tags {
                        if tag.name == "探" || tag.name == "渇" {
                            thirst_multiplier += 1.5;
                        }
                    }
                    inherent_tension = (node.utility * node.abstract_level * thirst_multiplier * 10.0) / ((connected_count as f64) + 0.1);
                }
            }
            base_tensions.insert(node.key.clone(), inherent_tension);
        }

        // Pass 2: Network Propagation (1-Hop Adjacency Diffusion)
        let mut final_tensions = base_tensions.clone();
        for node in self.nodes.values() {
            let node_base_tension = *base_tensions.get(&node.key).unwrap_or(&0.0);
            
            for rel in &node.relations {
                // If the target exists in our space, apply mutual tension bleed (50% transfer coefficient)
                if let Some(&target_base) = base_tensions.get(&rel.target_id) {
                    let transfer_rate = 0.5 * (rel.strength as f64);
                    
                    // Node receives tension from Target
                    *final_tensions.entry(node.key.clone()).or_insert(0.0) += target_base * transfer_rate;
                    // Target receives tension from Node
                    *final_tensions.entry(rel.target_id.clone()).or_insert(0.0) += node_base_tension * transfer_rate;
                }
            }
        }

        // Pass 3: Resolve MAX Tension
        let mut max_tension = 0.0;
        let mut critical_void_id = None;

        for (id, tension) in final_tensions {
            if tension > max_tension {
                max_tension = tension;
                critical_void_id = Some(id);
            }
        }

        (max_tension, critical_void_id)
    }


    /// Hydrates isolated `.jcross` text nodes utilizing `.jidx` caches
    pub async fn hydrate(&mut self) -> Result<usize> {
        let mut total = 0;
        let root = &self.root;
        let versions = vec!["jcross_v7"];

        for v in versions {
            let dir = root.join(v);
            if !dir.exists() {
                continue;
            }

            let mut entries = fs::read_dir(&dir).await.map_err(RoninError::Io)?;
            while let Some(entry) = entries.next_entry().await.map_err(RoninError::Io)? {
                let path = entry.path();
                if path.extension().and_then(|e| e.to_str()) == Some("jcross") {
                    if let Ok(content) = fs::read_to_string(&path).await {
                        if let Some(mut node) = MemoryNode::parse_jcross(&content) {
                            // Extract actual filesystem Z-Depth (modified time)
                            if let Ok(metadata) = fs::metadata(&path).await {
                                if let Ok(mtime) = metadata.modified() {
                                    node.time_stamp = chrono::DateTime::<chrono::Utc>::from(mtime).timestamp() as f64;
                                }
                            }
                            self.nodes.insert(node.key.clone(), node);
                            total += 1;
                        }
                    }
                }
            }
            info!("[SpatialIndex] Hydrated {} nodes from {}", total, dir.display());
        }

        self.total_docs = total;
        self.recompute_idf();

        Ok(total)
    }

    fn recompute_idf(&mut self) {
        let mut freqs = HashMap::new();
        for node in self.nodes.values() {
            let terms: HashSet<String> = node.l1_content.to_lowercase()
                .split(|c: char| !c.is_alphanumeric())
                .filter(|s| !s.is_empty())
                .map(|s| s.to_string())
                .collect();
            for term in terms {
                *freqs.entry(term).or_insert(0) += 1;
            }
        }
        self.doc_freqs = freqs;
    }

    /// V5 Scoring Algorithm: Merges multi-query tokens with Domain Anti-Gravity
    pub fn query_v5(&self, queries: &[String], target_domain: Option<&str>, limit: usize) -> Vec<&MemoryNode> {
        let now = Utc::now().timestamp() as f64;
        
        let mut scored_nodes: Vec<(f64, &MemoryNode)> = self.nodes.values().filter_map(|n| {
            // 1. Calculate MAX string similarity across all queries (Cognitive Expansion)
            let mut base_score = 0.0;
            for q in queries {
                // Combine Bi-gram overlap with Keyword presence
                let bi_score = token_overlap(&n.concept, q);
                
                // V6 IDF-Weighted Keyword Score
                let query_words: HashSet<String> = q.to_lowercase().split_whitespace().map(|s| s.to_string()).collect();
                let text_lower = n.l1_content.to_lowercase();
                
                let mut weighted_hits = 0.0;
                let mut total_weight = 0.0;
                
                for qw in &query_words {
                    // Calculate IDF for each query word
                    let n_docs = *self.doc_freqs.get(qw).unwrap_or(&0) as f64;
                    let idf = ((self.total_docs as f64 - n_docs + 0.5) / (n_docs + 0.5) + 1.0).ln().max(0.1);
                    
                    total_weight += idf;
                    if text_lower.contains(qw) {
                        weighted_hits += idf;
                    }
                }
                
                let kw_score = if total_weight > 0.0 { weighted_hits / total_weight } else { 0.0 };
                
                let s = (bi_score * 0.3) + (kw_score * 0.7); 
                if s > base_score { base_score = s; }
            }

            // 2. Extrapolate physics modifier from Kanji Tags
            let mut gravity = 1.0;
            let mut decay_rate = 0.05;
            let mut should_purge = false;
            let mut is_system_core = false;

            for tag in &n.kanji_tags {
                if tag.name == "核" { is_system_core = true; }
                if let Some(op) = self.ontology.get(&tag.name) {
                    if op.is_purge_flag { should_purge = true; }
                    gravity += op.gravity_mod * tag.weight;
                    decay_rate *= 1.0 - (1.0 - op.decay_mod) * tag.weight;
                }
            }

            if should_purge { return None; } 

            // 3. APPLY ANTI-GRAVITY (Domain Isolation Protocol)
            // If the user specifies a domain (e.g. personal_memory) and the node is System Core, 
            // we collapse its gravity to 0 to prevent it from hogging the results.
            if let Some(target) = target_domain {
                if n.domain != target && is_system_core {
                    gravity = 0.01; // Not zero to keep it visible if perfectly matched, but effectively suppressed
                } else if n.domain == target {
                    gravity *= 1.5; // Boost matches in target domain
                }
            }

            // 4. Time delay projection (Z-Depth Exponential Decay)
            let age_minutes = ((now - n.time_stamp) / 60.0).max(0.0);
            let decay_factor = f64::exp(-decay_rate as f64 * age_minutes);
            
            // 5. Transform Score
            let final_score = ((base_score * gravity as f64) 
                            + (n.confidence * 0.2) 
                            + (n.utility * 0.2)) * decay_factor;
                      
            Some((final_score, n))
        }).collect();

        scored_nodes.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        scored_nodes.into_iter().take(limit).map(|(_s, n)| n).collect()
    }

    /// Legacy wrapper for V4 compat
    pub fn query_nearest(&self, query_concept: &str, limit: usize) -> Vec<&MemoryNode> {
        self.query_v5(&[query_concept.to_string()], None, limit)
    }

    /// Writes a V4 JCross Graph Node to physical disk
    pub async fn write_node(&mut self, mut node: MemoryNode) -> Result<()> {
        let v4_dir = self.root.parent().unwrap_or(&self.root).join("jcross_v4");
        fs::create_dir_all(&v4_dir).await.map_err(RoninError::Io)?;

        if node.time_stamp == 0.0 {
            node.time_stamp = Utc::now().timestamp() as f64;
        }
        
        let path = v4_dir.join(format!("{}.jcross", node.key));
        let custom_markup = node.to_jcross();
        fs::write(&path, custom_markup).await.map_err(RoninError::Io)?;

        self.nodes.insert(node.key.clone(), node);
        Ok(())
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // Legacy Compat Hooks (Will deprecate slowly)
    // ─────────────────────────────────────────────────────────────────────────────

    pub fn front_nodes(&self) -> Vec<&MemoryNode> {
        self.nodes.values()
            .filter(|n| n.zone == MemoryZone::Front || n.utility > 0.8)
            .collect()
    }
    
    pub async fn write_front(&mut self, key: &str, content: &str) -> Result<()> {
        let node = MemoryNode::new_front(key, content);
        self.write_node(node).await
    }

    pub fn front_content_string(&self) -> String {
        self.front_nodes()
            .iter()
            .map(|n| format!("[{}]: {}", n.key, n.content))
            .collect::<Vec<_>>()
            .join("\n")
    }
}
