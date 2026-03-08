# Verantyx Native Mode - 完全ガイド

## 概要

**Verantyx Native Mode**は、Claude Codeのエージェント機能をサブプロセスとして活用し、Cross構造で個人ごとに進化する記憶を持つAIアシスタントです。

### コンセプト

```
ユーザー
   ↓
Verantyx CLI（独自UI）
   ↓
JCross動的プロンプト生成（Cross記憶から関連情報を抽出）
   ↓
Claude Code（サブプロセス、エージェント機能そのまま）
   ↓
応答をパース＆Cross構造に記録
   ↓
次回の会話で記憶として活用
```

## アーキテクチャ

### 3つの核心要素

1. **Claude Subprocess Engine**
   - Claude Codeをサブプロセスとして完全制御
   - PTYベースの双方向通信
   - リアルタイム出力パース

2. **JCross Dynamic Prompt Generator**
   - Cross記憶から関連情報を自動抽出
   - プロンプトを動的に拡張
   - コンテキストを失わない会話

3. **Cross 6-Axis Memory**
   - FRONT: 会話履歴（時系列）
   - UP: ユーザー入力のみ
   - DOWN: Claude応答のみ
   - RIGHT: ツール呼び出し・アクション履歴
   - LEFT: タイムスタンプ情報
   - BACK: JCross拡張プロンプト＋生データ

## 使い方

### 🚀 基本的な使用

```bash
# Verantyx Native Chatを起動
verantyx chat

# Cross構造の成長を表示しながら会話
verantyx chat --show-cross

# 特定プロジェクトで起動
verantyx chat --project /path/to/project
```

### 🔧 レガシーモード

従来のLLMプロバイダーを使いたい場合：

```bash
# レガシーモード
verantyx chat --legacy --llm claude
verantyx chat --legacy --llm gemini
```

## 動作の流れ

### 初回起動

```bash
$ verantyx chat
=======================================================================
  🌟 Verantyx-CLI - Autonomous AI with Cross Memory
=======================================================================

  Powered by Claude Code + Cross Structure
  Your personal AI that evolves with every conversation

=======================================================================

🚀 Initializing Verantyx Engine...

✅ Verantyx Engine Started!

⏳ Waiting for engine to be ready...

=======================================================================

💡 Usage:
   - Type your message and press Enter
   - JCross will automatically enhance prompts with Cross memory
   - All conversations are saved to Cross structure
   - Press Ctrl+C to exit

📂 Cross Memory:  /path/to/project/.verantyx/conversation.cross.json

=======================================================================

🗣️  You: _
```

### 会話例

```bash
🗣️  You: Hello! What can you help me with?

🤖 Verantyx Agent: Hello! I'm Verantyx, your autonomous AI assistant with Cross memory.
I can help you with:
- Code generation and debugging
- File operations and project management
- Terminal commands
- And much more!

Plus, I remember our conversations, so I can provide personalized assistance
based on our history together.

🗣️  You: Create a hello.py file that prints "Hello, Verantyx!"

🤖 Verantyx Agent: I'll create that file for you.

[Claude Codeのツール呼び出しが実行される]

✅ Created hello.py with the following content:
```python
print("Hello, Verantyx!")
```

Would you like me to run it?

🗣️  You: Yes, please run it

🤖 Verantyx Agent:
[実行結果]
Hello, Verantyx!

Done! The script executed successfully.
```

### Cross記憶の成長（--show-cross使用時）

```bash
🗣️  You: Create a hello.py file

🤖 Verantyx Agent: ...

  💾 Cross Memory: 1 inputs, 1 responses

🗣️  You: Now create a world.py file

🤖 Verantyx Agent: ...

  💾 Cross Memory: 2 inputs, 2 responses
```

## JCross動的プロンプト生成

### 仕組み

ユーザーが入力したプロンプト：
```
Create a new test file
```

JCrossが自動拡張したプロンプト：
```
Create a new test file

<!-- Cross Context:
[Context from Cross Memory]
- user: Create a hello.py file that prints "Hello, Verantyx!"...
- assistant: I'll create that file for you...
- user: Yes, please run it...
- assistant: Hello, Verantyx! Done! The script executed successfully...

[Recent Actions]
- Write (created hello.py)
- Bash (executed python3 hello.py)
-->
```

### メリット

✅ **コンテキスト維持**: 過去の会話を自動的に参照
✅ **パーソナライズ**: 個人の会話履歴から学習
✅ **シームレス**: ユーザーは意識する必要なし
✅ **進化**: 会話を重ねるごとに賢くなる

## Cross構造の詳細

### ファイル構造

```
.verantyx/
├── conversation.cross.json  # Cross記憶
├── verantyx.log             # ログ
└── mitmproxy_config/        # mitmproxy設定（intercept mode用）
```

### Cross JSON例

```json
{
  "version": "1.0",
  "type": "conversation",
  "created_at": "2026-03-08T18:30:00",
  "axes": {
    "FRONT": {
      "current_conversation": [
        {
          "role": "user",
          "content": "Create a hello.py file",
          "timestamp": 1234567890.123
        },
        {
          "role": "assistant",
          "content": "I'll create that file for you...",
          "timestamp": 1234567891.456
        }
      ],
      "active_session": true
    },
    "UP": {
      "user_inputs": [
        {
          "content": "Create a hello.py file",
          "timestamp": 1234567890.123
        }
      ],
      "total_messages": 1
    },
    "DOWN": {
      "claude_responses": [
        {
          "content": "I'll create that file for you...",
          "timestamp": 1234567891.456
        }
      ],
      "total_tokens": 0
    },
    "RIGHT": {
      "tool_calls": [],
      "actions_taken": []
    },
    "LEFT": {
      "timestamps": [1234567890.123, 1234567891.456],
      "session_duration": 0
    },
    "BACK": {
      "raw_interactions": [],
      "jcross_prompts": [
        {
          "original": "Create a hello.py file",
          "jcross_enhanced": "Create a hello.py file\n\n<!-- Cross Context:\n...\n-->",
          "timestamp": 1234567890.123
        }
      ]
    }
  }
}
```

## プロジェクトの目的

### なぜこのアーキテクチャか？

1. **Claude Codeのエージェント機能を活用**
   - 自前でエージェント機能を実装する必要なし
   - Claude Codeの高度なツール使用をそのまま利用
   - OpenClaw等のように複雑な実装不要

2. **JCross言語による柔軟性**
   - 動的なコード生成で指示を柔軟に
   - Cross記憶から自動的にコンテキスト抽出
   - ユーザーは意識せず恩恵を受ける

3. **Cross構造でコンテキスト維持**
   - 現在のエージェントの課題「コンテキスト喪失」を解決
   - 6軸立体構造で高密度に情報保持
   - 個人個人のverantyx-cliが進化

4. **将来的な単体動作**
   - 十分に学習したら、Claude Code不要に
   - Cross記憶だけで動作するAIに進化
   - 完全にパーソナライズされたエージェント

## 技術詳細

### Claude Subprocess Engine

**ファイル**: `verantyx_cli/engine/claude_subprocess_engine.py`

**主要機能**:
- `start()`: Claude Codeをサブプロセスで起動
- `send_prompt()`: プロンプト送信（JCross拡張あり）
- `_parse_claude_response()`: 応答パース
- `_generate_jcross_prompt()`: JCross動的生成
- `_record_to_cross()`: Cross構造に記録

### Verantyx Chat Mode

**ファイル**: `verantyx_cli/ui/verantyx_chat_mode.py`

**主要機能**:
- `start_verantyx_chat_mode()`: チャットループ
- `on_claude_response()`: Claude応答のコールバック
- Cross成長の表示（オプション）

### CLI統合

**ファイル**: `verantyx_cli/__main__.py`

**コマンド**:
```bash
verantyx chat                  # Native mode（デフォルト）
verantyx chat --show-cross     # Cross成長を表示
verantyx chat --legacy         # レガシーモード
verantyx intercept             # Intercept mode（別アプローチ）
```

## トラブルシューティング

### Claude Codeが見つからない

```
❌ Failed to start Verantyx Engine

Make sure Claude Code is installed:
  npm install -g @anthropic-ai/claude-code
```

→ Claude Codeをインストールしてください

### エンジンが起動しない

ログを確認：
```bash
cat .verantyx/verantyx.log
```

### Cross記憶が保存されない

権限を確認：
```bash
ls -la .verantyx/
chmod 755 .verantyx/
```

## 比較: Native Mode vs Intercept Mode

### Native Mode（このドキュメント）

**メリット**:
- ✅ 完全な制御
- ✅ JCross動的プロンプト生成
- ✅ Cross記憶との統合
- ✅ シンプルな起動

**デメリット**:
- ❌ PTY制御の複雑さ
- ❌ 出力パースの難しさ

### Intercept Mode

**メリット**:
- ✅ Claude Codeを普通に使える
- ✅ API通信を直接傍受
- ✅ 正確なデータ取得

**デメリット**:
- ❌ mitmproxyのセットアップ
- ❌ プロンプト拡張が難しい

## 今後の拡張

- [ ] より高度なJCross動的生成
- [ ] ツール呼び出しの詳細記録（RIGHT軸）
- [ ] Cross記憶の検索・フィルタ
- [ ] Cross記憶のビジュアライズ
- [ ] 完全自律動作（Claude Code不要）
- [ ] マルチプロジェクト対応
- [ ] Cross記憶のエクスポート/インポート

## まとめ

Verantyx Native Modeは：

🎯 **Claude Codeのエージェント機能**をそのまま活用
🧠 **Cross構造**で個人ごとに進化する記憶
🚀 **JCross動的生成**でコンテキストを維持
✨ **使用感を損なわない**シームレスな設計

これにより、真に進化し続けるパーソナルAIアシスタントを実現します。

```bash
# 今すぐ試す
verantyx chat
```

あなたのVerantyx Agentが、あなたと共に成長します 🌱
