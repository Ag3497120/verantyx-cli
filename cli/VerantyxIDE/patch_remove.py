import re

with open('Sources/Verantyx/AppState.swift', 'r') as f:
    content = f.read()

target = """    // MARK: - Pipeline Intent Classifier

    /// チャット入力がパイプラインタスク (変換・生成・ビルド系) かどうかを判定する。
    /// BitNet が使える場合は1.58bモデルで高速分類。
    /// BitNet 未インストールの場合はキーワードルールで判定。
    private func isPipelineIntent(text: String) async -> Bool {
        let lower = text.lowercased()
        
        // ── 強い否定キーワード（チャット/情報検索タスク） ──
        let nonPipelineKeywords = ["ニュース", "news", "教えて", "検索", "search", "what", "how", "why", "天候", "天気", "weather", "株価"]
        if nonPipelineKeywords.contains(where: { lower.contains($0) }) { 
            // 変換系の強いキーワードが含まれていない限りチャットとみなす
            let strongPipeline = ["変換", "書き換え", "convert", "transpile", "migrate", "一括変換"]
            if !strongPipeline.contains(where: { lower.contains($0) }) {
                return false 
            }
        }

        // LanguageDetector が言語非依存で判定 (BitNet 優先 → ルールベースフォールバック)
        if LanguageDetector.isPipelineIntent(text) { return true }
        
        // BitNet による追加分類
        if BitNetConfig.load()?.isValid == true {
            let classifyPrompt = \"\"\"
            ### Instruction:
            Classify this user message. Reply ONLY with "pipeline" or "chat".
            "pipeline" = code transpilation, conversion, build, generate/port files from one language to another
            "chat" = question, explanation, review, discussion, anything else
            Message: \\(text.prefix(200))
            ### Response:
            \"\"\"
            if let result = await BitNetCommanderEngine.shared.generate(
                prompt: classifyPrompt, systemPrompt: ""
            ) {
                return result.lowercased().contains("pipeline")
            }
        }
        return false
    }"""

if target in content:
    content = content.replace(target, "    // Pipeline Intent Classifier removed (Routing is now strictly UI-based)")
    print("Replaced Pipeline Intent Classifier")
else:
    print("Failed to find Pipeline Intent Classifier block")

with open('Sources/Verantyx/AppState.swift', 'w') as f:
    f.write(content)
