# Verantyx Standalone Mode - 学習済みAIの単体テスト

## 🤖 概要

**Standalone Mode**は、Verantyxが学習した内容だけで動作する独立モードです。Claude Codeに接続せず、過去の会話パターンから学習したCross構造を使って応答を生成します。

### 目的

- 📊 **学習度の確認** - Verantyxがどれだけ成長したかを測定
- 🧪 **AIの独立性テスト** - Claude Code抜きで動作できるかを検証
- 🎓 **学習レベル評価** - Beginner/Intermediate/Advanced/Expert
- 💡 **パターン分析** - 学習したツール使用パターンを確認

---

## 🚀 使い方

### 基本起動

```bash
# スタンドアロンモード起動
python3 -m verantyx_cli standalone
```

### 前提条件

**学習データが必要です。**

最初に通常モードでClaude Codeと会話してデータを蓄積：

```bash
# 学習させる（通常モード）
python3 -m verantyx_cli chat

# 5〜10回ほど会話
# ...

# 学習をテスト（スタンドアロンモード）
python3 -m verantyx_cli standalone
```

---

## 📊 画面の見方

### 起動時

```
======================================================================
  🤖 Verantyx Standalone Mode - Learned AI
======================================================================

  Testing what Verantyx learned from Claude Code interactions
  This mode runs WITHOUT Claude Code connection

======================================================================

🚀 Initializing Verantyx Standalone AI...

📊 Learning Status:
   - Learned from: 25 interactions
   - Response patterns: 25
   - JCross patterns: 12
   - Cross memory size: 45.3 KB

🔧 Learned Tool Patterns:
   - write: 8 uses
   - bash: 5 uses
   - read: 4 uses
   - grep: 3 uses
   - edit: 2 uses

🎓 Learning Level: Intermediate

======================================================================
```

### 学習レベル

| レベル | 必要な会話数 | 特徴 |
|--------|-------------|------|
| **Beginner** | 0-19 | 基本的なパターンのみ |
| **Intermediate** | 20-49 | 多様な応答パターン |
| **Advanced** | 50-99 | 複雑なタスクに対応 |
| **Expert** | 100+ | 幅広い知識と経験 |

---

## 💬 チャット機能

### 通常の質問

```
🗣️  You: How do I create a new file?

🤖 Verantyx:
[Analyzing learned patterns...]

I detect you want to perform a file operation.

**Request:** How do I create a new file?

**Suggested tools:** write, read, edit

**From my learning:**
- I've observed 3 different tool usages
- Most used tools: {'write': 8, 'bash': 5, 'read': 4}

**What I would do (based on learning):**
1. Verify the file path exists
2. Use appropriate tool (write, read, edit)
3. Confirm the operation completed successfully

**Note:** I'm running in standalone mode. To actually execute file operations, please use:
```bash
python3 -m verantyx_cli chat
```
```

### 特別なコマンド

#### `stats` - 統計表示

```
🗣️  You: stats

📊 Current Learning Statistics:

   Total interactions learned: 25
   Response patterns: 25
   JCross patterns: 12
   Cross file size: 45.3 KB

   Learning level: Intermediate

   Tool usage patterns:
      - write: 8 times
      - bash: 5 times
      - read: 4 times
      - grep: 3 times
      - edit: 2 times
```

#### `train` - トレーニング推奨

```
🗣️  You: train

🎓 Training Recommendations:

   📈 Status: Building knowledge base

   You're making good progress!

   To improve further:
   - Continue varied conversations
   - Try complex multi-step tasks
   - Use different programming languages

   Goal: 50+ interactions for solid patterns
```

#### `exit` / `quit` / `bye` - 終了

```
🗣️  You: exit

👋 Goodbye!

📊 This session: 5 interactions

To continue learning and improve my responses:
  python3 -m verantyx_cli chat
```

---

## 🧠 動作の仕組み

### 1. Cross構造の読み込み

`.verantyx/conversation.cross.json` から学習データを読み込み：

- **UP軸**: ユーザー入力パターン
- **DOWN軸**: 応答パターン
- **RIGHT軸**: ツール使用履歴
- **BACK軸**: JCrossプロンプト
- **FRONT軸**: 現在の会話フロー
- **LEFT軸**: タイムスタンプと統計

### 2. パターンマッチング

ユーザー入力を分析：

```python
# 類似入力検索（Jaccard類似度）
past_inputs = ["How to create file?", "Make a new file", ...]
user_input = "Create a new file"

# 最も類似する入力を検索 → 対応する応答を返す
```

### 3. 意図分析

キーワードベースの意図分析：

- **質問系**: what, how, why → `question`
- **ファイル操作**: create, write, file → `file_operation`
- **コード関連**: code, function, implement → `coding`
- **実行系**: run, execute, test → `execution`
- **検索系**: find, search, grep → `search`

### 4. 応答生成

学習したパターンに基づいて応答を構築：

```
[From learned patterns]
<過去の類似応答>
---
💡 This response was generated from past conversation patterns.
```

または

```
[Intent-based response]
<意図に基づいた構造化応答>
<学習統計の引用>
<推奨アクション>
```

---

## 🎯 使用例

### シナリオ1: 初学者（5会話後）

```bash
python3 -m verantyx_cli standalone
```

```
📊 Learning Status:
   - Learned from: 5 interactions
   - Response patterns: 5
   - JCross patterns: 2

🎓 Learning Level: Beginner

🗣️  You: How do I write code?

🤖 Verantyx:
I recognize this as a coding request.

**My learning data:**
- Code-related interactions: ~3
- Tool usages for coding: 1 writes, 0 edits

**Note:** I'm still learning. My responses will improve with more interactions.

Use full mode for better assistance:
  python3 -m verantyx_cli chat
```

### シナリオ2: 中級者（30会話後）

```
📊 Learning Status:
   - Learned from: 30 interactions
   - Response patterns: 30
   - JCross patterns: 15

🎓 Learning Level: Intermediate

🗣️  You: Find all Python files

🤖 Verantyx:
I detect a search request.

**Search tools I've learned:**
- Grep usage: 8 times
- Glob patterns: 6 times

**Search strategy (from learning):**
1. Identify search pattern/keywords
2. Choose appropriate tool (grep for content, glob for files)
3. Filter and present results

**Keywords:** Find, Python, files

For actual execution:
  python3 -m verantyx_cli chat
```

### シナリオ3: 上級者（100会話後）

```
📊 Learning Status:
   - Learned from: 100 interactions
   - Response patterns: 100
   - JCross patterns: 45

🎓 Learning Level: Expert

🗣️  You: Create a test file

🤖 Verantyx:
[From learned patterns]

I'll create a test file for you. Let me use the Write tool to create
a new file with test cases.

First, I'll check if a tests directory exists, then create the file
with appropriate structure.

---
💡 This response was generated from past conversation patterns.

For actual file creation:
  python3 -m verantyx_cli chat
```

---

## 📈 学習の進め方

### Step 1: 基礎学習（10会話）

```bash
python3 -m verantyx_cli chat
```

多様なトピック:
- ファイル作成・編集
- コード記述
- テスト実行
- エラー修正
- 検索・分析

### Step 2: 中間評価

```bash
python3 -m verantyx_cli standalone
```

`train`コマンドで推奨を確認：

```
🗣️  You: train

📚 Status: Just getting started

Next steps:
1. Use full mode for more conversations
2. Try diverse topics
   - File operations
   - Code writing
   - Search and analysis

Goal: 10+ interactions for basic patterns
```

### Step 3: 継続学習（50会話）

さらに複雑なタスク:
- 複数ファイルの操作
- デバッグワークフロー
- リファクタリング
- パフォーマンス最適化

### Step 4: エキスパート評価

```bash
python3 -m verantyx_cli standalone
```

```
🎓 Learning Level: Advanced

✨ Status: Well trained!

I can now recognize:
- Common question patterns
- Tool usage scenarios
- Task workflows

Keep using me to maintain and expand my knowledge!
```

---

## 🔧 技術詳細

### 実装ファイル

```
verantyx_cli/engine/
├── standalone_ai.py              # 学習済みAIエンジン
│   ├── VerantyxStandaloneAI     # メインクラス
│   ├── _load_cross_memory()      # Cross構造読み込み
│   ├── find_similar_input()      # 類似入力検索
│   ├── analyze_intent()          # 意図分析
│   └── generate_response()       # 応答生成

verantyx_cli/ui/
└── standalone_chat_mode.py       # スタンドアロンUI
    └── start_standalone_chat_mode()
```

### アルゴリズム

#### 類似度計算（Jaccard）

```python
def jaccard_similarity(set1, set2):
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if len(union) > 0 else 0

# 例
user_words = {"how", "create", "file"}
past_words = {"how", "make", "new", "file"}

similarity = jaccard_similarity(user_words, past_words)
# = 2 / 5 = 0.4 (40%)

# 閾値20%以上で「類似」と判定
```

#### 意図分類

```python
intent_keywords = {
    'question': ['what', 'how', 'why', 'when', 'where', 'who'],
    'file_operation': ['create', 'make', 'write', 'file', 'read'],
    'coding': ['code', 'function', 'class', 'implement'],
    'execution': ['run', 'execute', 'test', 'check'],
    'search': ['find', 'search', 'look', 'grep']
}

def classify_intent(user_input):
    for intent_type, keywords in intent_keywords.items():
        if any(kw in user_input.lower() for kw in keywords):
            return intent_type
    return 'unknown'
```

---

## 💡 制限事項

### できること ✅

- 過去の会話パターンから類似応答を検索
- ユーザー入力の意図を分析
- 学習したツール使用パターンを提示
- 統計情報の表示
- トレーニング推奨の提供

### できないこと ❌

- 実際のツール実行（Write, Bash, etc.）
- Claude Codeへの接続
- ファイルの作成・編集
- コードの実行
- リアルタイムの情報取得

### なぜ制限があるか

スタンドアロンモードは**学習度のテスト**が目的です：

- Verantyxがどれだけ学習したかを可視化
- パターンマッチングの精度を確認
- 独立性の検証

実際の作業には通常モードを使用してください。

---

## 🎓 FAQ

### Q: 学習データがない場合は？

**A:** 以下のメッセージが表示されます：

```
⚠️  No learning data found!

Verantyx needs to learn from interactions first.

To train Verantyx, run:
  python3 -m verantyx_cli chat

Have at least a few conversations, then come back to test.
```

### Q: どれくらい学習すればいい？

**A:** 最低10会話を推奨：

- 10会話: 基本パターン形成
- 30会話: 中級レベル
- 50会話: 高度な応答
- 100会話: エキスパート

### Q: 応答精度を上げるには？

**A:** 多様な会話を重ねること：

1. 様々なトピック
2. 異なるツール使用
3. 複雑なワークフロー
4. エラー処理の経験

### Q: 学習データはどこに保存される？

**A:** `.verantyx/conversation.cross.json`

このファイルが大きいほど、学習が進んでいます。

---

## 🌟 まとめ

**Standalone Mode**は、Verantyxの成長を確認できる特別なモードです。

### 使い分け

| モード | 目的 | Claude Code |
|--------|------|-------------|
| **通常モード** | 実際の作業 | ✅ 接続 |
| **スタンドアロン** | 学習度テスト | ❌ 独立 |

### ワークフロー

```
1. 通常モードで学習
   python3 -m verantyx_cli chat
   ↓
2. スタンドアロンでテスト
   python3 -m verantyx_cli standalone
   ↓
3. 統計・推奨を確認
   stats, train コマンド
   ↓
4. さらに学習
   通常モードに戻る
```

---

**実装日時**: 2026-03-11
**新規ファイル**: 2個
**総追加行数**: ~700行

🤖 **Verantyxがどれだけ成長したか、試してみてください！**
