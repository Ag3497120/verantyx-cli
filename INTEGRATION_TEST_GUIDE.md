# 実際の学習統合テスト - Gemini学習検証

## 目的
JCrossベースのCross構造記録が、実際のClaude Codeとの会話から正しく学習し、関連キーワードでも応答できることを検証する。

## テストシナリオ

### 1. Claude Codeモードで学習
```bash
python3 -m verantyx_cli chat
```

会話内容:
```
You: geminiとは

Claude: Geminiは、Googleが開発した大規模マルチモーダルAIモデルです。

主な特徴:
1. テキスト、画像、音声、動画を統合処理
2. Google DeepMindが開発
3. 複数のバージョン（Ultra, Pro, Nano）

技術的特徴:
- Transformer architecture
- Chain-of-thought reasoning
- Multimodal understanding

開発組織:
- Google DeepMind
- Google AI Research

競合製品との比較:
- GPT-4: OpenAI
- Claude: Anthropic
- Gemini: Google
```

### 2. Cross構造確認
```bash
python3 -c "
import json
from pathlib import Path

cross_file = Path('.verantyx/conversation.cross.json')
data = json.load(open(cross_file, encoding='utf-8'))
axes = data.get('axes', {})

user_inputs = axes.get('UP', {}).get('user_inputs', [])
claude_responses = axes.get('DOWN', {}).get('claude_responses', [])

print(f'UP axis: {len(user_inputs)} inputs')
for i, inp in enumerate(user_inputs, 1):
    print(f'  {i}. {inp}')

print(f'\\nDOWN axis: {len(claude_responses)} responses')
for i, resp in enumerate(claude_responses, 1):
    print(f'  {i}. {resp[:100]}...')
"
```

期待される出力:
```
UP axis: 1 inputs
  1. geminiとは

DOWN axis: 1 responses
  1. Geminiは、Googleが開発した大規模マルチモーダルAIモデルです...
```

### 3. 知識抽出確認
```bash
python3 -c "
from pathlib import Path
from verantyx_cli.engine.knowledge_learner import KnowledgeLearner

cross_file = Path('.verantyx/conversation.cross.json')
learner = KnowledgeLearner(cross_file)

summary = learner.get_knowledge_summary()

print('📊 Extracted Knowledge:')
print(f'  Q&A patterns: {summary[\"qa_patterns_count\"]}')
print(f'  Concepts: {summary[\"concepts_count\"]}')
print(f'  Top concepts: {summary[\"top_concepts\"]}')
"
```

期待される出力:
```
📊 Extracted Knowledge:
  Q&A patterns: 1
  Concepts: 5+
  Top concepts: ['Gemini', 'Google', 'DeepMind', 'GPT-4', 'Claude']
```

### 4. スタンドアロンモードで検証

#### テスト1: 直接質問
```bash
python3 -m verantyx_cli standalone

> geminiとは
```

期待される応答:
```
[From learned Q&A patterns]

Geminiは、Googleが開発した大規模マルチモーダルAIモデルです。

主な特徴:
1. テキスト、画像、音声、動画を統合処理
2. Google DeepMindが開発
3. 複数のバージョン（Ultra, Pro, Nano）
...
```

#### テスト2: 関連キーワード（Google）
```bash
> googleとは
```

期待される応答:
```
[From learned concepts]

Googleに関連する学習済み情報:
- Geminiの開発元
- Google DeepMind組織
...
```

#### テスト3: 関連キーワード（DeepMind）
```bash
> deepmindとは
```

期待される応答:
```
[From learned concepts]

DeepMindに関連する学習済み情報:
- Google DeepMindがGeminiを開発
...
```

#### テスト4: 関連キーワード（マルチモーダル）
```bash
> マルチモーダルとは
```

期待される応答:
```
[From learned technical knowledge]

マルチモーダルに関する情報:
- テキスト、画像、音声、動画を統合処理
- Geminiの主要機能
...
```

## 検証ポイント

### ✅ 成功基準

1. **直接質問**: "geminiとは" → Geminiの説明が返る
2. **関連組織**: "google" / "deepmind" → Geminiとの関連が返る
3. **技術用語**: "マルチモーダル" → Geminiの文脈での説明が返る
4. **競合製品**: "gpt-4" / "claude" → 比較情報が返る

### ❌ 失敗パターン

1. ハードコードされた応答が返る
2. "Skill Execution Result" が表示される
3. 関連キーワードで "No match found"
4. Cross構造が空

## JCross統合確認

### conversation_logger.jcross が使用されているか

```bash
python3 -c "
from pathlib import Path
from verantyx_cli.engine.claude_subprocess_engine import ClaudeSubprocessEngine

# _record_to_cross メソッドがCrossConversationLoggerを使用しているか確認
import inspect
source = inspect.getsource(ClaudeSubprocessEngine._record_to_cross)
print('JCross-based logging:')
print('CrossConversationLogger' in source)
print('conversation_logger.jcross' in source or 'JCross' in source)
"
```

## 実行手順

1. テストデータをクリア
```bash
rm -f .verantyx/conversation.cross.json
```

2. Chat modeで実際にClaude Codeと会話
```bash
python3 -m verantyx_cli chat
# "geminiとは" と質問
# Claudeの応答を確認
# Ctrl+C で終了
```

3. Cross構造を確認（上記スクリプト使用）

4. Standalone modeで検証（上記テスト実行）

5. 結果をドキュメント化

## トラブルシューティング

### 問題: Cross構造が空
→ ClaudeSubprocessEngine._record_to_cross が呼ばれていない
→ on_claude_response callback が動作していない

### 問題: 知識抽出が0件
→ knowledge_learner._classify_question が日本語パターンを検出していない
→ データ形式が文字列ではなくオブジェクト

### 問題: 関連キーワードで応答なし
→ concept extraction が動作していない
→ Jaccard similarity threshold が高すぎる

## 成功時の次のステップ

1. README.mdに実際の使用例を追加
2. より複雑な会話での学習テスト（会話の流れ、文脈）
3. 複数トピックでの学習（Gemini + Claude + ChatGPT）
4. 学習内容のマージ・更新ロジック
