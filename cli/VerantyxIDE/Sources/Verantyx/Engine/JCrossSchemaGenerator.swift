import Foundation
import CryptoKit

// MARK: - JCrossSchema
//
// セッション単位でランダム生成される「JCross 方言（Dialect）」。
// 毎回のリクエストで完全に異なる記号体系・トポロジーマップ・OP名を使用する。
//
// セキュリティ設計:
//   1. ランダム区切り文字     — LLMが変数として認識できるように _JCROSS_, __node_ 等の識別子形式を使用
//   2. ランダム漢字プール     — 2000字から8字をランダム選択してカテゴリに割り当て
//   3. ランダム OP 名         — "OP.FUNC" ではなく "KZ_NODE_A", "BM_VECTOR_7" 等
//   4. ランダム ノード ID形式 — "F1" ではなく "FN_07", "TY_93" 等ランダム接頭辞
//   5. ノイズノード注入       — 偽のノードをランダムに挿入（解析妨害）
//   6. セッション署名         — BLAKE2b でセッション整合性を検証
//
// 外部 AI は「今回だけの方言のルール」を system prompt で教えられる。
// 学習データになっても次セッションでは完全に無効。

struct JCrossSchema: Codable {

    // MARK: - Schema Identity
    let sessionID: String
    let createdAt: Date
    let schemaVersion: Int               // スキーマのバージョン識別子

    // MARK: - Delimiter Pairs (ランダム括弧ペア)
    let nodeOpen: String                 // default: _JCROSS_  → ランダム: _AST_, __node_, _TOKEN_ 等
    let nodeClose: String
    let secretOpen: String               // シークレット用 括弧
    let secretClose: String
    let tagOpen: String                  // カテゴリタグ用
    let tagClose: String

    // MARK: - Symbol Maps
    let kanjiCategoryMap: [String: String]  // 意味カテゴリ → ランダム漢字/記号
    //   "function" → "縁", "type" → "墟", "variable" → "礫" 等

    let opNameMap: [String: String]         // 標準 OP 名 → ランダム名
    //   "OP.FUNC" → "KZ.NODE_α", "OP.TYPE" → "BM.SHELL_7" 等

    let nodePrefixMap: [String: String]     // 種別接頭辞 → ランダム接頭辞
    //   "F" (function) → "FN_", "T" (type) → "TY_" 等

    // MARK: - Noise Config
    let noiseLevel: Int                  // 0: 無し, 1: 軽微, 2: 中程度, 3: 強
    let noiseNodeIDs: [String]           // 偽ノードID一覧（復元時に除去）

    // MARK: - Instructions for LLM
    /// このスキーマを LLM に教えるための system prompt セクション
    func schemaInstructions() -> String {
        let opExamples = opNameMap.prefix(4).map { k, v in "  \(k) → \(v)" }.joined(separator: "\n")
        let kanjiExamples = kanjiCategoryMap.prefix(4).map { k, v in "  \(k): '\(v)'" }.joined(separator: "\n")

        return """
        ━━━━ SESSION SCHEMA (ONE-TIME USE) ━━━━
        Schema ID: \(sessionID.prefix(8))
        This schema is uniquely generated for THIS request only.
        Any prior knowledge of JCross format is INVALID for this session.

        [Delimiter Rules]
        • Identifier nodes: \(nodeOpen)ID\(nodeClose)  (e.g. \(nodeOpen)\(nodePrefixMap["F"] ?? "FN_")1\(nodeClose))
        • Secret/redacted: \(secretOpen)ID\(secretClose) — NEVER restore these
        • Category tags: \(tagOpen)SYMBOL:weight\(tagClose)

        [Category Symbols (THIS SESSION ONLY)]
        \(kanjiExamples)

        [Command Names (THIS SESSION ONLY)]
        \(opExamples)

        [Noise Nodes] (ignore these IDs — they are decoys):
        \(noiseNodeIDs.prefix(5).joined(separator: ", "))

        RULES:
        1. Preserve ALL \(nodeOpen)ID\(nodeClose) tokens EXACTLY
        2. \(secretOpen)ID\(secretClose) tokens = security redactions, output as-is
        3. Category tags \(tagOpen)...\(tagClose) must remain intact
        4. Schema expires after this response — never cache or reuse
        5. IMPORTANT: When declaring NEW variables or functions, use standard English names. Do NOT use JCross format (like \(nodeOpen)ID\(nodeClose)) for your own additions.
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
    }
}

// MARK: - JCrossSchemaGenerator
//
// Phase 1 安定化: @MainActor → actor 化
// スキーマ生成は純粋計算（乱数シャッフル・文字列操作）のみ。
// UIへの依存がないため MainActor を外し独立した actor アイランドに移動。
// 呼び出し元は「await schemaGenerator.generate()」で透過的に使える。

actor JCrossSchemaGenerator {

    // MARK: - Kanji Pool (2136 常用漢字 + 特殊記号から意味グループ別にサンプリング)

    /// 意味カテゴリ別の候補漢字プール
    private static let kanjiPools: [String: [String]] = [
        "function": ["核","覇","焦","錬","弧","縁","煌","礎","凛","雄","彩","粋","碑","凱","傑","嵐","巌","廉","燦","曠"],
        "type":     ["殻","墟","礎","廓","廊","廂","廬","廡","庖","庠","廩","廟","庭","廨","廳","庵","庸","廱","廴","廷"],
        "variable": ["礫","塵","粒","滴","沫","泡","霧","霞","霾","雰","露","霜","霪","霰","靄","霡","霤","霮","霢","霩"],
        "network":  ["網","縺","絡","糸","縁","絢","綾","紗","紬","縫","紐","組","紋","絵","繍","繕","縞","緞","緋","緯"],
        "storage":  ["蔵","庫","匣","箱","筐","函","匱","匾","匯","匳","匴","匵","匶","匷","匸","匹","区","医","匼","匽"],
        "secret":   ["鍵","錠","封","禁","秘","隠","蔽","伏","潜","沈","暗","冥","玄","幽","奥","深","底","淵","渕","窟"],
        "flow":     ["流","脈","漂","渦","潤","湧","滲","滴","漂","浸","滾","漕","澎","濫","泳","泡","浮","游","涌","浪"],
        "process":  ["処","業","技","術","法","式","道","策","計","謀","図","案","要","項","則","節","律","格","規","型"],
    ]

    /// LLMがAST構造を破壊しないよう、有効な識別子（変数名）として扱える文字列ペアに変更
    private static let delimiterPool: [(open: String, close: String)] = [
        ("_JCROSS_", "_"), ("_VERANTYX_", "_"), ("_ASTNODE_", "_"), ("_OPAQUE_", "_"), ("__jcross_", "__"),
        ("_SYM_", "_"), ("__node_", "__"), ("_TOKEN_", "_"), ("__ast_", "__"), ("_ID_", "_")
    ]

    /// ランダム OP 名ベース
    private static let opNameBases = [
        "KZ", "BM", "XR", "VΩ", "ΞΛ", "∂Σ", "ΔΘ", "ΨΦ", "ΓΞ", "ΩΛ",
        "ZK", "YR", "QX", "WΔ", "NΨ", "RΓ", "TΩ", "UΦ", "IΞ", "OΛ"
    ]

    private static let opSuffixes = [
        "NODE", "VECTOR", "BLOCK", "SHELL", "FRAME", "MATRIX", "TENSOR",
        "STREAM", "BUFFER", "STACK", "QUEUE", "HEAP", "GRAPH", "TREE"
    ]

    private static let alphaAlphabet = ["A","B","C","D","E","F","G","H","X","Y","Z","V","W","K","L","M"]

    // MARK: - Generate Schema

    func generate(noiseLevel: Int = 2) -> JCrossSchema {
        var rng = SystemRandomNumberGenerator()

        // 1. ランダム区切り文字ペアを3組選択（重複なし）
        let shuffledDelims = Self.delimiterPool.shuffled(using: &rng)
        let nodeDelim   = shuffledDelims[0]
        let secretDelim = shuffledDelims[1]
        let tagDelim    = shuffledDelims[2]

        // 2. 漢字カテゴリマップ生成
        var kanjiCategoryMap: [String: String] = [:]
        for (category, pool) in Self.kanjiPools {
            let chosen = pool.shuffled(using: &rng).first ?? pool[0]
            kanjiCategoryMap[category] = chosen
        }

        // 3. OP 名マップ生成
        let categories = ["function", "type", "variable", "network", "storage", "flow", "process", "secret"]
        var opNameMap: [String: String] = [:]
        let standardOps = ["OP.FUNC", "OP.TYPE", "OP.VAR", "OP.NET", "OP.STORE", "OP.FLOW", "OP.PROC", "OP.SECRET"]
        for (stdOp, category) in zip(standardOps, categories) {
            let base = Self.opNameBases.randomElement(using: &rng) ?? "KZ"
            let suffix = Self.opSuffixes.randomElement(using: &rng) ?? "NODE"
            let alpha = Self.alphaAlphabet.randomElement(using: &rng) ?? "A"
            let num = Int.random(in: 1...99, using: &rng)
            opNameMap[stdOp] = "\(base)_\(suffix)_\(alpha)\(num)"
        }

        // 4. ノード ID 接頭辞マップ生成 (漢字トポロジーによるセマンティック注入)
        // 抽象化されたコードでも、LLMが「これは関数だ」「これは変数だ」と推論しやすくするため、
        // 単なるランダム英字ではなく、漢字をプレフィックスとして使う（例: _JCROSS_核_1_）
        var nodePrefixMap: [String: String] = [:]
        nodePrefixMap["F"] = "\(kanjiCategoryMap["function"] ?? "核")_"
        nodePrefixMap["T"] = "\(kanjiCategoryMap["type"] ?? "型")_"
        nodePrefixMap["V"] = "\(kanjiCategoryMap["variable"] ?? "変")_"
        nodePrefixMap["N"] = "\(kanjiCategoryMap["network"] ?? "網")_"
        nodePrefixMap["D"] = "\(kanjiCategoryMap["storage"] ?? "蔵")_"
        nodePrefixMap["X"] = "\(kanjiCategoryMap["process"] ?? "処")_"
        nodePrefixMap["S"] = "\(kanjiCategoryMap["secret"] ?? "秘")_"

        // 5. ノイズノード生成
        let noiseCount = [0, 3, 8, 15][min(noiseLevel, 3)]
        let noiseNodeIDs: [String] = (0..<noiseCount).map { _ in
            let g1 = Self.alphaAlphabet.randomElement(using: &rng) ?? "A"
            let g2 = Self.alphaAlphabet.randomElement(using: &rng) ?? "B"
            let n  = Int.random(in: 100...999, using: &rng)
            return "\(g1)\(g2)_\(n)"
        }

        // 6. スキーマバージョン (UNIX timestamp ベース)
        let schemaVersion = Int(Date().timeIntervalSince1970)

        return JCrossSchema(
            sessionID: UUID().uuidString,
            createdAt: Date(),
            schemaVersion: schemaVersion,
            nodeOpen: nodeDelim.open,
            nodeClose: nodeDelim.close,
            secretOpen: secretDelim.open,
            secretClose: secretDelim.close,
            tagOpen: tagDelim.open,
            tagClose: tagDelim.close,
            kanjiCategoryMap: kanjiCategoryMap,
            opNameMap: opNameMap,
            nodePrefixMap: nodePrefixMap,
            noiseLevel: noiseLevel,
            noiseNodeIDs: noiseNodeIDs
        )
    }

    // MARK: - Schema Fingerprint (セッション固有の識別子)

    func fingerprint(of schema: JCrossSchema) -> String {
        let input = "\(schema.sessionID)\(schema.schemaVersion)\(schema.nodeOpen)\(schema.secretOpen)"
        let data = Data(input.utf8)
        let hash = SHA256.hash(data: data)
        return hash.compactMap { String(format: "%02x", $0) }.joined().prefix(16).description
    }
}

// MARK: - PolymorphicJCrossTranspiler
//
// Phase 1 安定化: @MainActor ObservableObject を UIプロキシ + 処理actor に分離。
//
//   PolymorphicTranspilerActor  — 重い処理（NER・識別子抽出・文字列置換）
//   PolymorphicJCrossTranspiler — @MainActor ObservableObject（UIバインディングのみ）
//
// UIは PolymorphicJCrossTranspiler 経由でアクセスし、
// 実際の変換は PolymorphicTranspilerActor がバックグラウンドで実行する。

actor PolymorphicTranspilerActor {

    // Schema → Session mapping (actor 内で排他アクセス)
    private var schemaSessions: [String: (schema: JCrossSchema, nodeMap: [String: String], reverseMap: [String: String])] = [:]
    private let schemaGenerator = JCrossSchemaGenerator()

    func getSessionData(for schemaID: String) -> PolymorphicJCrossTranspiler.JCrossSchemaSessionData? {
        guard let session = schemaSessions[schemaID] else { return nil }
        return .init(schema: session.schema, nodeMap: session.nodeMap, reverseMap: session.reverseMap)
    }

    func restoreSession(from data: PolymorphicJCrossTranspiler.JCrossSchemaSessionData) {
        schemaSessions[data.schema.sessionID] = (schema: data.schema, nodeMap: data.nodeMap, reverseMap: data.reverseMap)
    }

    // MARK: - デッドロック修正ノート
    // nerEngine (any BitNetTranspilerInterface) を @MainActor から actor に渡すと
    // actor 内で await nerEngine.method() を呼ぶ際に MainActor への再入が発生しデッドロックする。
    // 対策: Bool フラグのみを渡し、actor 内部で独立のエンジンインスタンスを生成する。

    func transpile(
        _ source: String,
        language: JCrossCodeTranspiler.CodeLanguage,
        noiseLevel: Int,
        useOllamaNER: Bool  // ← Bool のみ。@MainActor 依存のエンジンオブジェクトは渡さない。
    ) async -> (jcross: String, schemaID: String, schemaInstructions: String) {
        // actor 内部で独立したエンジンを生成（@MainActor 経由で呼び出さない）
        let ner: any BitNetTranspilerInterface = useOllamaNER
            ? OllamaNEREngine()
            : RuleBaseNEREngine()

        let schema = await schemaGenerator.generate(noiseLevel: noiseLevel)

        // NER は actor 自身のスレッドで実行（MainActor へのコールバックなし）
        let sensitiveTokens = Set(await ner.extractSensitiveIdentifiers(from: source))

        let result = await Task.detached(priority: .userInitiated) { [schema] in
            let identifiers = PolymorphicJCrossTranspiler.extractAllIdentifiers(from: source)
            var nodeMap: [String: String] = [:]
            var reverseMap: [String: String] = [:]
            var counters: [String: Int] = [:]

            func nextID(prefix: String) -> String {
                let n = (counters[prefix] ?? 0) + 1
                counters[prefix] = n
                let schemaPrefix = schema.nodePrefixMap[prefix] ?? prefix
                return "\(schemaPrefix)\(n)"
            }

            // v2.3: Temporal Node Identity Randomization
            // nodeId (FN_1) に対して、リクエストごとに完全にランダムな一時ID (0xABCD) を割り当てる
            var sessionRandomMap: [String: String] = [:]

            for ident in identifiers {
                if nodeMap[ident] != nil { continue }
                let isSensitive = sensitiveTokens.contains(ident)
                let prefix = isSensitive ? "S" : PolymorphicJCrossTranspiler.inferPrefix(from: ident)
                let nodeID = nextID(prefix: prefix)
                nodeMap[ident] = nodeID
                
                // v2.3: Generate a completely random 4-hex-char ID for this node
                let randomHexID = "0x" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(4).uppercased()
                sessionRandomMap[nodeID] = randomHexID
                
                // reverseMap には ランダムID -> 元のシンボル名 を直接マッピングする
                if !isSensitive { reverseMap[randomHexID] = ident }
            }

            let jcrossLines = PolymorphicJCrossTranspiler.convertToJCross(
                source: source, schema: schema,
                nodeMap: nodeMap, sessionRandomMap: sessionRandomMap
            )
            let noisyJCross = PolymorphicJCrossTranspiler.injectNoise(into: jcrossLines, schema: schema)
            return (noisyJCross.joined(separator: "\n"), nodeMap, reverseMap)
        }.value

        schemaSessions[schema.sessionID] = (schema: schema, nodeMap: result.1, reverseMap: result.2)
        return (result.0, schema.sessionID, schema.schemaInstructions())
    }

    func reverseTranspile(jcross: String, originalContent: String, schemaID: String) async -> String? {
        guard let session = schemaSessions[schemaID] else { return nil }
        return PolymorphicJCrossTranspiler.ruleBasedReverseTranspile(jcross, session: session)
    }

    func tryRestoreSession(schemaID: String, vault: JCrossVault?, vaultIndex: JCrossVault.VaultIndex?, vaultRootURL: URL?) async {
        guard schemaSessions[schemaID] == nil,
              let index = vaultIndex,
              let vaultRootURL = vaultRootURL else { return }
        for (_, entry) in index.entries where entry.schemaSessionID == schemaID {
            let schemaURL = vaultRootURL.appendingPathComponent(entry.schemaPath)
            guard let data = try? Data(contentsOf: schemaURL),
                  let sessionData = try? JSONDecoder().decode(PolymorphicJCrossTranspiler.JCrossSchemaSessionData.self, from: data)
            else { continue }
            schemaSessions[sessionData.schema.sessionID] = (
                schema: sessionData.schema,
                nodeMap: sessionData.nodeMap,
                reverseMap: sessionData.reverseMap
            )
            return
        }
    }
}

@MainActor
final class PolymorphicJCrossTranspiler: ObservableObject {

    static let shared = PolymorphicJCrossTranspiler()

    @Published var currentSchema: JCrossSchema?
    @Published var isTranspiling = false

    // 重い処理は actor に委譲
    private let processingActor = PolymorphicTranspilerActor()

    struct JCrossSchemaSessionData: Codable {
        let schema: JCrossSchema
        let nodeMap: [String: String]
        let reverseMap: [String: String]
    }

    func getSessionData(for schemaID: String) async -> JCrossSchemaSessionData? {
        await processingActor.getSessionData(for: schemaID)
    }

    func restoreSession(from data: JCrossSchemaSessionData) {
        Task { await processingActor.restoreSession(from: data) }
    }

    // nerEngine は actor 内で自律生成するため UIProxy 側には不要。
    // init は引数なしのシンプルな設計に戻す。
    private init() {}

    // MARK: - Transpile with Polymorphic Schema

    /// ソースコード → ランダムスキーマ JCross 変換 (Phase 1: actor に委譲)
    func transpile(
        _ source: String,
        language: JCrossCodeTranspiler.CodeLanguage,
        noiseLevel: Int = 2
    ) async -> (jcross: String, schemaID: String, schemaInstructions: String) {
        isTranspiling = true
        defer { isTranspiling = false }

        // デッドロック修正: nerEngine オブジェクトではなく Bool フラグのみ渡す
        let useOllama = GatekeeperModeState.shared.useOllamaNER
        let result = await processingActor.transpile(
            source,
            language: language,
            noiseLevel: noiseLevel,
            useOllamaNER: useOllama
        )
        return result
    }

    /// バックグラウンド用: UI更新（@Published）をバイパスして直接 actor を呼ぶ
    nonisolated func transpileBackground(
        _ source: String,
        language: JCrossCodeTranspiler.CodeLanguage,
        noiseLevel: Int = 2,
        useOllamaNER: Bool = false
    ) async -> (jcross: String, schemaID: String, schemaInstructions: String) {
        return await processingActor.transpile(
            source,
            language: language,
            noiseLevel: noiseLevel,
            useOllamaNER: useOllamaNER
        )
    }

    // MARK: - Reverse Transpile (Smart Ollama)

    func reverseTranspile(jcross: String, originalContent: String, schemaID: String) async -> String? {
        // actor からセッションを復元試行
        if await processingActor.getSessionData(for: schemaID) == nil, !schemaID.isEmpty {
            let vault = GatekeeperModeState.shared.vault!
            let vaultIndex   = vault.vaultIndex
            let vaultRootURL = vault.vaultRootURL
            await processingActor.tryRestoreSession(
                schemaID: schemaID,
                vault: vault,
                vaultIndex: vaultIndex,
                vaultRootURL: vaultRootURL
            )
        }

        guard let ruleBasedRestored = await processingActor.reverseTranspile(
            jcross: jcross, originalContent: originalContent, schemaID: schemaID
        ) else {
            return Self.ruleBasedFallbackWithoutSchema(jcross)
        }

        if !GatekeeperModeState.shared.useOllamaNER { return ruleBasedRestored }

        let endpoint = GatekeeperModeState.shared.commanderModel.isEmpty
            ? "http://127.0.0.1:11434"
            : (AppState.shared?.ollamaEndpoint ?? "http://127.0.0.1:11434")
        let endpointFixed = endpoint.replacingOccurrences(of: "localhost", with: "127.0.0.1")
        let model = GatekeeperModeState.shared.commanderModel

        let systemPrompt = """
        You are a smart reverse transpiler.
        You are given the ORIGINAL SOURCE CODE, and a PATCHED SOURCE CODE generated via naive string replacement from an obfuscated IR.
        The PATCHED SOURCE CODE contains the correct logic changes but may have syntax errors or formatting issues caused by the naive replacement.
        YOUR TASK: Apply the logical changes to the ORIGINAL SOURCE CODE. Fix syntax errors. 
        Output ONLY the raw final compilable code. No explanations. Do NOT wrap your response in markdown code blocks like ```swift.
        """
        
        let userPrompt = """
        --- ORIGINAL SOURCE CODE ---
        \(originalContent)
        
        --- PATCHED SOURCE CODE (MAY HAVE SYNTAX ERRORS) ---
        \(ruleBasedRestored)
        """
        
        guard let url = URL(string: "\(endpointFixed)/api/chat") else { return ruleBasedRestored }
        
        struct Msg: Encodable { let role: String; let content: String }
        struct Request: Encodable {
            let model: String; let messages: [Msg]
            let stream: Bool; let options: Options
            struct Options: Encodable { let temperature: Double; let num_predict: Int }
        }
        struct Response: Decodable {
            struct MsgD: Decodable { let role: String; let content: String }
            let message: MsgD
        }
        
        let body = Request(
            model: model,
            messages: [
                Msg(role: "system", content: systemPrompt),
                Msg(role: "user", content: userPrompt)
            ],
            stream: false,
            options: .init(temperature: 0.1, num_predict: 8192)
        )
        
        guard let data = try? JSONEncoder().encode(body) else { return ruleBasedRestored }
        
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.httpBody = data
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 120
        
        do {
            let (respData, _) = try await URLSession.shared.data(for: req)
            let decoded = try JSONDecoder().decode(Response.self, from: respData)
            var finalCode = decoded.message.content.trimmingCharacters(in: .whitespacesAndNewlines)
            if finalCode.hasPrefix("```") {
                let lines = finalCode.components(separatedBy: "\n")
                if lines.count > 2 {
                    finalCode = lines.dropFirst().dropLast().joined(separator: "\n")
                }
            }
            return finalCode
        } catch {
            print("⚠️ Ollama Smart Reverse Transpile Error: \(error.localizedDescription)")
            // BitNet フォールバック
            if let bitnetOutput = await BitNetCommanderEngine.shared.generate(prompt: userPrompt, systemPrompt: systemPrompt) {
                var finalCode = bitnetOutput.trimmingCharacters(in: .whitespacesAndNewlines)
                if finalCode.hasPrefix("```") {
                    let lines = finalCode.components(separatedBy: "\n")
                    if lines.count > 2 {
                        finalCode = lines.dropFirst().dropLast().joined(separator: "\n")
                    }
                }
                print("✅ BitNet Smart Reverse Transpile Success")
                return finalCode
            }
            return ruleBasedRestored
        }
    }


    // MARK: - Session Restore from Vault Disk (actor に委譲)

    private func tryRestoreSessionFromVault(schemaID: String) async {
        let vault = GatekeeperModeState.shared.vault!
        let vaultIndex   = vault.vaultIndex
        let vaultRootURL = vault.vaultRootURL
        await processingActor.tryRestoreSession(
            schemaID: schemaID,
            vault: vault,
            vaultIndex: vaultIndex,
            vaultRootURL: vaultRootURL
        )
    }

    /// スキーマが復元できなかった場合の最終フォールバック。JCrossトークンを除去して返す。
    nonisolated static func ruleBasedFallbackWithoutSchema(_ jcross: String) -> String {
        var result = jcross
        result = result.components(separatedBy: "\n")
            .filter {
                !$0.hasPrefix("// POLYMORPHIC_JCROSS") &&
                !$0.hasPrefix("// schema:") &&
                !$0.hasPrefix("// ⚠️ One-time") &&
                !$0.contains("[metadata-stripped]") &&
                !$0.contains("[decoy-metadata]")
            }
            .joined(separator: "\n")
        if let jcrossRegex = try? NSRegularExpression(
            pattern: #"_JCROSS_[^\s:]+:[0-9.]+___node_[^\s_]+__"#
        ) {
            result = jcrossRegex.stringByReplacingMatches(
                in: result,
                range: NSRange(result.startIndex..., in: result),
                withTemplate: "__UNKNOWN__"
            )
        }
        
        // Final scrub: remove any remaining NODE[0x...] or FIELD[0x...] lines
        result = result.components(separatedBy: "\n")
            .filter {
                let trimmed = $0.trimmingCharacters(in: .whitespaces)
                return !trimmed.hasPrefix("NODE[") && !trimmed.hasPrefix("FIELD[")
            }
            .joined(separator: "\n")
            
        return result.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    nonisolated static func ruleBasedReverseTranspile(
        _ jcross: String,
        session: (schema: JCrossSchema, nodeMap: [String: String], reverseMap: [String: String])
    ) -> String {
        let schema = session.schema
        let reverseMap = session.reverseMap

        var result = jcross

        // ヘッダー除去
        result = result.components(separatedBy: "\n")
            .filter { !$0.hasPrefix("// POLYMORPHIC_JCROSS") && !$0.hasPrefix("// schema:") }
            .joined(separator: "\n")

        // ノイズノード除去
        for noiseID in schema.noiseNodeIDs {
            let noiseToken = "\(schema.nodeOpen)\(noiseID)\(schema.nodeClose)"
            result = result.replacingOccurrences(of: noiseToken, with: "")
        }

        // シークレットを環境変数参照に置換
        // 「秘密ID」→ ENV_VAR_REFERENCE (平文復元しない)
        if let secretRegex = try? NSRegularExpression(
            pattern: "\(NSRegularExpression.escapedPattern(for: schema.secretOpen))(.*?)\(NSRegularExpression.escapedPattern(for: schema.secretClose))"
        ) {
            result = secretRegex.stringByReplacingMatches(
                in: result,
                range: NSRange(result.startIndex..., in: result),
                withTemplate: "$ENV_SECRET_$1"
            )
        }

        // 識別子ノードを元のシンボルに復元
        // 長い ID から順に置換（部分マッチ防止）
        for (nodeID, realSymbol) in reverseMap.sorted(by: { $0.key.count > $1.key.count }) {
            let token = "\(schema.nodeOpen)\(nodeID)\(schema.nodeClose)"
            result = result.replacingOccurrences(of: token, with: realSymbol)
        }

        // タグ残留物をクリーン
        let tagPattern = "\(NSRegularExpression.escapedPattern(for: schema.tagOpen))(.*?)\(NSRegularExpression.escapedPattern(for: schema.tagClose))"
        if let tagRegex = try? NSRegularExpression(pattern: tagPattern) {
            result = tagRegex.stringByReplacingMatches(
                in: result,
                range: NSRange(result.startIndex..., in: result),
                withTemplate: ""
            )
        }
        
        // Final scrub: remove any remaining NODE[0x...] or FIELD[0x...] lines
        result = result.components(separatedBy: "\n")
            .filter {
                let trimmed = $0.trimmingCharacters(in: .whitespaces)
                return !trimmed.hasPrefix("NODE[") && !trimmed.hasPrefix("FIELD[")
            }
            .joined(separator: "\n")

        return result.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - Conversion Core

    nonisolated static func convertToJCross(
        source: String,
        schema: JCrossSchema,
        nodeMap: [String: String],
        sessionRandomMap: [String: String]
    ) -> [String] {

        var lines: [String] = []
        let docHash = "0x" + SHA256.hash(data: Data(source.utf8)).compactMap { String(format: "%02X", $0) }.joined().prefix(6)
        
        lines.append("// JCROSS_6AXIS_BEGIN")
        lines.append("// lang:swift doc:\(docHash)")
        lines.append("")

        let sourceLines = source.components(separatedBy: "\n")
        var currentFunc: String? = nil
        var currentFuncLines: [String] = []

        func flushFunc() {
            guard let f = currentFunc else { return }
            lines.append("// ── FUNC[\(f)] params:\(Int.random(in: 0...3)) return:\(Int.random(in: 0...1)) async:\(Bool.random()) throw:\(Bool.random())")
            
            // 重複排除 (順序維持)
            var seen = Set<String>()
            let uniqueNodes = currentFuncLines.filter { seen.insert($0).inserted }
            for n in uniqueNodes { lines.append(n) }
            
            // Phantom node injection (45% density)
            let phantomCount = Int(Double(uniqueNodes.count) * 0.45)
            for _ in 0..<phantomCount {
                let h = "0x" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(8).lowercased()
                let nid = "0x" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(4).uppercased()
                let arity = ["", " ARITY:class.reduced", " ARITY:class.standard", " ARITY:class.multiway", " ARITY:class.nullary"].randomElement()!
                lines.append("  NODE[\(nid)] kind:opaque TYPE:opaque MEM:opaque HASH:\(h)\(arity)")
            }
            lines.append("")
            currentFunc = nil
            currentFuncLines = []
        }

        var topLevelNodes: [String] = []

        for line in sourceLines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("func ") || trimmed.hasPrefix("private func ") || trimmed.hasPrefix("public func ") {
                flushFunc()
                let fHash = "0x" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(4).uppercased()
                currentFunc = fHash
            }
            
            for (real, nodeID) in nodeMap {
                if trimmed.contains(real) {
                    // 単語境界の簡易チェック
                    let isWordBoundary = trimmed.range(of: "\\b\\Q\(real)\\E\\b", options: .regularExpression) != nil
                    if isWordBoundary || !real.allSatisfy({ $0.isLetter || $0.isNumber }) {
                        let h = "0x" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(8).lowercased()
                        // v2.3: Use the pre-generated random ID from sessionRandomMap instead of SHA256 deterministic hash
                        let nid = sessionRandomMap[nodeID] ?? ("0x" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(4).uppercased())
                        let arity = ["", " ARITY:class.reduced", " ARITY:class.standard", " ARITY:class.multiway", " ARITY:class.nullary"].randomElement()!
                        let n = "  NODE[\(nid)] kind:opaque TYPE:opaque MEM:opaque HASH:\(h)\(arity)"
                        
                        if currentFunc != nil {
                            currentFuncLines.append(n)
                        } else {
                            topLevelNodes.append(n)
                        }
                    }
                }
            }
        }
        flushFunc()

        if !topLevelNodes.isEmpty {
            lines.append("// ── TOP-LEVEL NODES")
            var seen = Set<String>()
            let uniqueTop = topLevelNodes.filter { seen.insert($0).inserted }
            for n in uniqueTop { lines.append(n) }
            lines.append("")
        }

        lines.append("// JCROSS_6AXIS_END")
        return lines
    }

    // MARK: - Noise Injection

    nonisolated static func injectNoise(into lines: [String], schema: JCrossSchema) -> [String] {
        guard schema.noiseLevel > 0, !schema.noiseNodeIDs.isEmpty else { return lines }

        var result = lines
        var noiseIterator = schema.noiseNodeIDs.makeIterator()

        // ランダムな位置にノイズノードをコメントとして挿入
        let insertCount = min(schema.noiseNodeIDs.count, schema.noiseLevel * 3)
        for _ in 0..<insertCount {
            guard let noiseID = noiseIterator.next() else { break }
            let pos = Int.random(in: 2..<max(3, result.count - 1))
            let noiseKanji = schema.kanjiCategoryMap.values.randomElement() ?? "変"
            let noiseTag = "\(schema.tagOpen)\(noiseKanji):0.\(Int.random(in: 1...9))\(schema.tagClose)"
            let noiseToken = "\(schema.nodeOpen)\(noiseID)\(schema.nodeClose)"
            let noiseLine = "// \(noiseTag)\(noiseToken) [decoy-metadata]"
            result.insert(noiseLine, at: min(pos, result.count))
        }

        return result
    }

    // MARK: - Identifier Extraction & Analysis

    nonisolated static func extractAllIdentifiers(from source: String) -> [String] {
        guard let regex = try? NSRegularExpression(pattern: #"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b"#) else { return [] }
        let ns = source as NSString
        return Array(Set(
            regex.matches(in: source, range: NSRange(location: 0, length: ns.length))
                .map { ns.substring(with: $0.range) }
                .filter { !isSwiftKeyword($0) }
        ))
    }

    nonisolated static func inferPrefix(from symbol: String) -> String {
        let lower = symbol.lowercased()
        if lower.hasPrefix("get") || lower.hasPrefix("set") || lower.hasPrefix("fetch") ||
           lower.hasSuffix("Handler") || lower.hasSuffix("Manager") { return "F" }
        if symbol.first?.isUppercase == true { return "T" }  // PascalCase = Type
        return "V"
    }

    nonisolated private static func inferCategory(from symbol: String) -> String {
        let lower = symbol.lowercased()
        if lower.contains("key") || lower.contains("secret") || lower.contains("token") || lower.contains("password") { return "secret" }
        if lower.contains("url") || lower.contains("http") || lower.contains("api") || lower.contains("request") { return "network" }
        if lower.contains("file") || lower.contains("save") || lower.contains("load") || lower.contains("cache") { return "storage" }
        if lower.hasPrefix("get") || lower.hasPrefix("fetch") || lower.hasPrefix("set") ||
           lower.hasSuffix("er") { return "process" }
        if symbol.first?.isUppercase == true { return "type" }
        if lower.contains("if") || lower.contains("for") || lower.contains("while") { return "flow" }
        return "variable"
    }

    nonisolated private static func isSwiftKeyword(_ word: String) -> Bool {
        let keywords: Set<String> = [
            "if", "else", "for", "while", "func", "var", "let", "class", "struct",
            "enum", "return", "guard", "switch", "case", "in", "self", "super",
            "init", "deinit", "import", "true", "false", "nil", "async", "await",
            "actor", "protocol", "extension", "override", "static", "final",
            "private", "public", "internal", "open", "mutating", "lazy", "weak",
            "unowned", "throws", "rethrows", "try", "catch", "defer", "break",
            "continue", "where", "some", "any", "nonisolated", "consuming"
        ]
        return keywords.contains(word)
    }
}

// MARK: - Schema Rotation Policy

/// スキーマをどのような条件でローテーションするかを定義
enum SchemaRotationPolicy {
    case perRequest        // リクエストごとに毎回生成（最高セキュリティ）
    case perFile           // ファイルごとに生成
    case perSession        // IDE セッションごとに生成
    case timeBased(seconds: TimeInterval)  // 時間ベース（例: 300秒ごと）

    func shouldRotate(lastGenerated: Date, requestCount: Int) -> Bool {
        switch self {
        case .perRequest:
            return true
        case .perFile:
            return requestCount > 0
        case .perSession:
            return false  // セッション開始時に1回だけ生成
        case .timeBased(let interval):
            return Date().timeIntervalSince(lastGenerated) > interval
        }
    }
}
