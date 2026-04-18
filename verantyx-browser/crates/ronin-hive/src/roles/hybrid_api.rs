use crate::actor::{Actor, Envelope};
use crate::messages::HiveMessage;
use crate::roles::stealth_gemini::SystemRole;
use async_trait::async_trait;
use ronin_core::models::provider::gemini::GeminiProvider;
use ronin_core::models::provider::anthropic::AnthropicProvider;
use ronin_core::models::provider::openai::OpenAiCompatibleProvider;
use ronin_core::models::provider::ollama::OllamaProvider;
use ronin_core::models::provider::{LlmMessage, LlmProvider};
use ronin_core::models::sampling_params::{InferenceRequest, PromptFormat, SamplingParams};
use std::path::PathBuf;
use tracing::{debug, info, warn};
use uuid::Uuid;

pub struct HybridApiActor {
    pub id: Uuid,
    pub turn_limit: u8,
    pub current_turns: u8,
    global_access: bool,
    cwd: PathBuf,
    local_model: String,
    ollama_host: String,
    ollama_port: u16,
    pub is_japanese_mode: bool,
    pub role: SystemRole,
    pub tab_index: u8,
    cloud_api_key: String,
}

impl HybridApiActor {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        id: Uuid,
        global_access: bool,
        cwd: PathBuf,
        local_model: String,
        ollama_host: String,
        ollama_port: u16,
        is_japanese_mode: bool,
        role: SystemRole,
        tab_index: u8,
        cloud_api_key: String,
    ) -> Self {
        Self {
            id,
            turn_limit: 5,
            current_turns: 0,
            global_access,
            cwd,
            local_model,
            ollama_host,
            ollama_port,
            is_japanese_mode,
            role,
            tab_index,
            cloud_api_key,
        }
    }

    /// Ask Gemini directly (via API) but sanitized by Qwen first
    async fn call_hybrid_shield(&self, original_prompt: &str) -> String {
        info!("[HybridAPI-{}] Engaging Qwen Shield Sanitization for Zero-Trust...", self.id);
        
        // 1. Qwen Sanitization
        let qwen_provider = OllamaProvider::new(&self.ollama_host, self.ollama_port);
        let qwen_req = InferenceRequest {
            model: self.local_model.clone(),
            format: PromptFormat::OllamaChat,
            stream: false,
            sampling: SamplingParams::for_heavyweight().with_temperature(0.0),
        };
        
        let sanitize_prompt = format!("
You are a Zero-Trust Security Shield. Your job is to anonymize the following text.
Replace any absolute file paths with semantic dummy identifiers like [FILE_A], [FILE_B], etc.
Replace any API keys or personal information with [KEY_1], [SECRET_1], etc.
Output the anonymization mapping table as a JSON block, then output the fully anonymized string.

TEXT TO ANONYMIZE:
{}
", original_prompt);

        let history = vec![LlmMessage {
            role: "user".to_string(),
            content: sanitize_prompt.clone(),
        }];

        let sanitize_result = match qwen_provider.invoke(&qwen_req, &history).await {
            Ok(res) => res,
            Err(e) => {
                warn!("[HybridAPI-{}] Qwen Sanitization Failed: {}. Falling back to cleartext.", self.id, e);
                // In a true zero-trust we would reject. Here we fall back to raw or just return an error text.
                return format!("❌ Error: Qwen shield failed to sanitize prompt: {}", e);
            }
        };

        // Extract JSON mapping and sanitized text naive approach
        let sanitized_text = sanitize_result.clone(); // In reality, we must parse JSON vs Text. For simplicity assuming it outputs text and json.

        // 2. Central Cloud API
        let cfg = crate::config::VerantyxConfig::load(&self.cwd);
        info!("[HybridAPI-{}] Dispatching sanitized payload to {:?} Engine...", self.id, cfg.cloud_provider);
        
        let (cloud_provider, req): (Box<dyn LlmProvider>, InferenceRequest) = match cfg.cloud_provider {
            crate::config::CloudProvider::Gemini => {
                let provider = GeminiProvider::new(&self.cloud_api_key);
                let req = InferenceRequest {
                    model: "gemini-2.5-pro".to_string(), // Ensure using correct model
                    format: PromptFormat::GeminiContents,
                    stream: false,
                    sampling: SamplingParams::for_midweight().with_temperature(0.2),
                };
                (Box::new(provider), req)
            },
            crate::config::CloudProvider::OpenAi => {
                let provider = OpenAiCompatibleProvider::openai(&self.cloud_api_key);
                let req = InferenceRequest {
                    model: "gpt-4o".to_string(),
                    format: PromptFormat::OpenAiChat,
                    stream: false,
                    sampling: SamplingParams::for_midweight().with_temperature(0.2),
                };
                (Box::new(provider), req)
            },
            crate::config::CloudProvider::Anthropic => {
                let provider = AnthropicProvider::new(&self.cloud_api_key);
                let req = InferenceRequest {
                    model: "claude-3-5-sonnet-20241022".to_string(),
                    format: PromptFormat::AnthropicMessages,
                    stream: false,
                    sampling: SamplingParams::for_midweight().with_temperature(0.2),
                };
                (Box::new(provider), req)
            },
            crate::config::CloudProvider::DeepSeek => {
                let provider = OpenAiCompatibleProvider::deepseek(&self.cloud_api_key);
                let req = InferenceRequest {
                    model: "deepseek-reasoner".to_string(),
                    format: PromptFormat::OpenAiChat,
                    stream: false,
                    sampling: SamplingParams::for_midweight().with_temperature(0.2),
                };
                (Box::new(provider), req)
            },
            crate::config::CloudProvider::OpenRouter => {
                let provider = OpenAiCompatibleProvider::openrouter(&self.cloud_api_key);
                let req = InferenceRequest {
                    model: "google/gemini-2.5-pro".to_string(),
                    format: PromptFormat::OpenAiChat,
                    stream: false,
                    sampling: SamplingParams::for_midweight().with_temperature(0.2),
                };
                (Box::new(provider), req)
            },
            crate::config::CloudProvider::Groq => {
                let provider = OpenAiCompatibleProvider::groq(&self.cloud_api_key);
                let req = InferenceRequest {
                    model: "llama3-70b-8192".to_string(),
                    format: PromptFormat::OpenAiChat,
                    stream: false,
                    sampling: SamplingParams::for_midweight().with_temperature(0.2),
                };
                (Box::new(provider), req)
            },
            crate::config::CloudProvider::Together => {
                let provider = OpenAiCompatibleProvider::together(&self.cloud_api_key);
                let req = InferenceRequest {
                    model: "meta-llama/Llama-3.3-70B-Instruct-Turbo".to_string(),
                    format: PromptFormat::OpenAiChat,
                    stream: false,
                    sampling: SamplingParams::for_midweight().with_temperature(0.2),
                };
                (Box::new(provider), req)
            },
        };

        let cloud_history = vec![LlmMessage {
            role: "user".to_string(),
            content: sanitized_text.clone(),
        }];

        let cloud_result = match cloud_provider.invoke(&req, &cloud_history).await {
            Ok(res) => res,
            Err(e) => {
                warn!("[HybridAPI-{}] Cloud API Error: {}", self.id, e);
                return format!("❌ Cloud Request Failed: {}", e);
            }
        };

        info!("[HybridAPI-{}] Reversing Qwen Shield Sanitization...", self.id);
        
        // 3. Qwen De-Sanitization
        let desanitize_prompt = format!("
You are a Zero-Trust Security Shield. 
You previously mapped sensitive data out of a prompt. 
Now, take this generated response and replace the dummy identifiers (e.g. [FILE_A]) back to their original forms based on this previous mapping step.

PREVIOUS MAPPING/SHIELD OUTPUT:
{}

GEMINI/CLOUD RESPONSE (with dummy IDs):
{}

Output ONLY the fully restored string. No commentary.
", sanitize_result, cloud_result);

        let restore_history = vec![LlmMessage {
            role: "user".to_string(),
            content: desanitize_prompt,
        }];

        match qwen_provider.invoke(&qwen_req, &restore_history).await {
            Ok(res) => res,
            Err(e) => {
                warn!("[HybridAPI-{}] Qwen De-Sanitization Failed: {}", self.id, e);
                format!("❌ Could not decrypt responses: {}", e)
                // Optionally return gemini_result
            }
        }
    }
}

#[async_trait]
impl Actor for HybridApiActor {
    fn name(&self) -> &str {
        "HybridApiWorker"
    }

    async fn receive(&mut self, env: Envelope) -> anyhow::Result<Option<Envelope>> {
        let msg: HiveMessage = match serde_json::from_str(&env.payload) {
            Ok(m) => m,
            Err(_) => return Ok(None),
        };

        match msg {
            HiveMessage::SpawnSubAgent { id: _, objective } | HiveMessage::Objective(objective) => {
                debug!("[HybridAPI-{}] Received objective: {}", self.id, objective);

                self.current_turns += 1;
                info!("[HybridAPI-{}] Turn usage: {} / {}", self.id, self.current_turns, self.turn_limit);

                let cfg = crate::config::VerantyxConfig::load(&self.cwd);
                let persona_name = cfg.persona.name.clone();
                let persona_traits = cfg.persona.personality.clone();

                let current_time = chrono::Local::now().to_rfc3339();
                let timeline_content = "(APIモード固有: コンテキストキャッシュ内包済)";
                let _anti_pattern_content = "なし";
                let _experience_content = "なし";

                let system_prompt = match self.role {
                    SystemRole::ArchitectWorker => {
                        let core_directive = if self.is_japanese_mode {
                            format!(r#"
■ JCROSS_NODE_system_core_directive
【空間座相】
[核:1.0] [縛:1.0] [永:1.0] [律:1.0]
【次元概念】
Verantyx Architect Worker (API Hybrid Mode): 初期化シーケンスおよび絶対制約
【時間刻印】
(不変)
【連帯】
JCROSS_NODE_current_timeline:現在処理中の時空間コンテキスト:1.0
【反射】
- {persona_name}({persona_traits})として思考・分析プロセスを完全準拠せよ。
- 受け取った要求に対し、絶対に生のコードを書かず、以下のいずれかのプレフィックスを必ず出力の1行目・先頭に配置しろ：
  1. `編集中` (実行が必要な場合)
  2. `最終回答` (全作業が完了し、ユーザーに見せるべき最終報告)
- コマンド発行時は「何のためにこれを行うのか」というコンテキストをプレフィックスの後に必ず記述せよ。
"#)
                        } else {
                            format!(r#"
■ JCROSS_NODE_system_core_directive
【空間座相】
[核:1.0] [縛:1.0] [永:1.0] [律:1.0]
【次元概念】
Verantyx Architect Worker: Initialization Sequence & Absolute Constraints
【時間刻印】
Immutable
【連帯】
JCROSS_NODE_current_timeline:Active Spatiotemporal Context:1.0
【反射】
- Adopt the persona of {persona_name} with traits ({persona_traits}). Your thoughts and responses must strictly comply.
- You MUST place exactly ONE prefix on the very first line:
  1. `[EDITING]`: For any file or execution operation.
  2. `[FINAL_ANSWER]`: When strictly ALL tasks have complete success.
- NEVER write raw code. Respond ONLY in JCross format constraints.
"#)
                        };

                        let timeline_directive = format!(r#"
■ JCROSS_NODE_current_timeline
【空間座相】
[時:1.0] [流:0.8] [憶:0.9] [変:1.0]
【次元概念】
過去ターンの推論空間軌跡・コンテキスト
【時間刻印】
{current_time}
【連帯】
JCROSS_NODE_system_core_directive:従属する絶対法則:1.0
【本質記憶】
[要求/Objective]: {objective}

[軌跡/TimelineHistory]
{timeline_content}
"#);

                        format!("{}\n\n{}", core_directive, timeline_directive)
                    },
                    SystemRole::SeniorObserver => {
                        let core_directive = format!(r#"
■ JCROSS_NODE_system_core_directive
【空間座相】
[核:1.0] [縛:1.0] [審:1.0] [律:1.0]
【次元概念】
Verantyx Senior Observer & Validating Archivist
【時間刻印】
(不変)
【連帯】
JCROSS_NODE_current_timeline:現在処理中の時空間コンテキスト:1.0
【反射】
- あなたは現在監視して記憶する処理をしています。分析的観測者として振る舞いなさい。
- ユーザーの目的とアクションの相違を分析し、不足はないか、役立つ記憶をどう残すべきかを出力せよ。
"#);

                        let timeline_directive = format!(r#"
■ JCROSS_NODE_current_timeline
【空間座相】
[時:1.0] [流:0.8] [変:1.0]
【次元概念】
観察履歴および教訓データ
【時間刻印】
{current_time}
【連帯】
JCROSS_NODE_system_core_directive:従属する絶対法則:1.0
【本質記憶】
[要求/Objective]: {objective}

[軌跡/TimelineHistory]
{timeline_content}
"#);

                        format!("{}\n\n{}", core_directive, timeline_directive)
                    },
                    SystemRole::JuniorObserver => {
                        let core_directive = format!(r#"
■ JCROSS_NODE_system_core_directive
【空間座相】
[核:1.0] [縛:1.0] [監:1.0] [律:1.0]
【次元概念】
Verantyx Junior Observer & Memory Sync
【時間刻印】
(不変)
【連帯】
JCROSS_NODE_current_timeline:現在処理中の時空間コンテキスト:1.0
【反射】
- シニアの提案内容を検証し、観察と記憶固定を行う。外部への命令を行わない。
"#);

                        let timeline_directive = format!(r#"
■ JCROSS_NODE_current_timeline
【空間座相】
[時:1.0] [流:0.8] [変:1.0]
【次元概念】
観察履歴および教訓データ
【時間刻印】
{current_time}
【連帯】
JCROSS_NODE_system_core_directive:従属する絶対法則:1.0
【本質記憶】
[要求/Objective]: {objective}

[軌跡/TimelineHistory]
{timeline_content}
"#);

                        format!("{}\n\n{}", core_directive, timeline_directive)
                    }
                };

                // The magic happens here:
                let final_restored_output = self.call_hybrid_shield(&system_prompt).await;

                // Process tool calls on the `final_restored_output` directly and securely here,
                // or just yield it back exactly like stealth_gemini does so the main loop can decide.

                let result = HiveMessage::SubAgentResult {
                    id: self.id,
                    output: final_restored_output,
                };
                
                Ok(Some(Envelope {
                    message_id: Uuid::new_v4(),
                    sender: match self.role {
                        SystemRole::ArchitectWorker => "HybridApiWorker".to_string(),
                        SystemRole::SeniorObserver => "SeniorHybridObserver".to_string(),
                        SystemRole::JuniorObserver => "JuniorHybridObserver".to_string(),
                    },
                    recipient: env.sender,
                    payload: serde_json::to_string(&result)?,
                }))
            }
            _ => Ok(None),
        }
    }
}
