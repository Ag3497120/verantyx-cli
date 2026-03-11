# クイックテスト: Gemini学習検証

## 準備
```bash
# 現在のディレクトリ確認
pwd
# → /Users/motonishikoudai/verantyx_v6/verantyx-cli

# 古いデータをクリア（既に実行済み）
rm -f .verantyx/conversation.cross.json
```

## ステップ1: Claude Codeと会話して学習

```bash
python3 -m verantyx_cli chat
```

会話:
```
You: geminiとは

（Claudeの応答を待つ - Googleが開発したマルチモーダルAI、DeepMindなどの情報が含まれるはず）

（応答が来たら Ctrl+C で終了）
```

## ステップ2: Cross構造を確認

```bash
python3 -c "
import json
from pathlib import Path

cross_file = Path('.verantyx/conversation.cross.json')
if not cross_file.exists():
    print('❌ Cross file not found!')
    exit(1)

data = json.load(open(cross_file, encoding='utf-8'))
axes = data.get('axes', {})

user_inputs = axes.get('UP', {}).get('user_inputs', [])
claude_responses = axes.get('DOWN', {}).get('claude_responses', [])

print(f'✅ UP axis: {len(user_inputs)} user inputs')
print(f'✅ DOWN axis: {len(claude_responses)} Claude responses')

if user_inputs:
    print(f'\\n📝 Question: {user_inputs[0]}')

if claude_responses:
    response_preview = claude_responses[0][:200]
    print(f'\\n💬 Response preview:')
    print(response_preview)
    print('...')

    # キーワードチェック
    keywords = ['google', 'deepmind', 'gemini', 'マルチモーダル']
    found_keywords = [k for k in keywords if k.lower() in claude_responses[0].lower()]
    print(f'\\n🔍 Found keywords: {found_keywords}')
"
```

期待される出力例:
```
✅ UP axis: 1 user inputs
✅ DOWN axis: 1 Claude responses

📝 Question: geminiとは

💬 Response preview:
Geminiは、Googleが開発した大規模マルチモーダルAIモデルです。

主な特徴:
1. テキスト、画像、音声、動画を統合処理
2. Google DeepMindが開発
3. 複数のバージョン（Ultra, Pro, Nano）
...

🔍 Found keywords: ['google', 'deepmind', 'gemini', 'マルチモーダル']
```

## ステップ3: 知識抽出を確認

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
print(f'  Technical knowledge: {summary[\"technical_knowledge_count\"]}')
print()

if summary['top_concepts']:
    print('📚 Top Concepts:')
    for concept in summary['top_concepts'][:10]:
        print(f'  • {concept}')
"
```

期待される出力:
```
📊 Extracted Knowledge:
  Q&A patterns: 1
  Concepts: 5+
  Technical knowledge: 1+

📚 Top Concepts:
  • Gemini
  • Google
  • DeepMind
  • マルチモーダル
  • GPT-4（比較に出てきた場合）
  • Claude（比較に出てきた場合）
```

## ステップ4: スタンドアロンモードでテスト

```bash
python3 -m verantyx_cli standalone
```

### テスト1: 直接質問
```
> geminiとは
```

**期待**: Geminiの説明が返る（学習した内容）

### テスト2: 関連キーワード - Google
```
> googleとは
```

**期待**: Googleに関する情報（Geminiの開発元として）

### テスト3: 関連キーワード - DeepMind
```
> deepmindとは
```

**期待**: DeepMindに関する情報（Geminiとの関連）

### テスト4: 技術用語
```
> マルチモーダルとは
```

**期待**: マルチモーダルの説明（Geminiの文脈で）

## 成功基準

✅ **全てのテストで関連情報が返る**
- 直接質問: 学習した回答が返る
- 関連キーワード: Cross構造から関連情報を抽出して返す

❌ **失敗パターン**
- "Skill Execution Result" が表示される
- "No matching Q&A found"
- 応答がハードコードされたテストデータ

## トラブルシューティング

### Cross構造が空の場合
```bash
# ClaudeSubprocessEngineのログを確認
tail -50 .verantyx/verantyx.log
```

### 知識が抽出されない場合
```bash
# knowledge_learnerのパターン検出を確認
python3 -c "
from verantyx_cli.engine.knowledge_learner import KnowledgeLearner

learner = KnowledgeLearner(None)
test_question = 'geminiとは'
question_type = learner._classify_question(test_question)
print(f'Question type: {question_type}')
print(f'Expected: definition')
"
```

### スタンドアロンモードで応答が返らない場合
```bash
# AIの応答生成フローをデバッグ
python3 -c "
from pathlib import Path
from verantyx_cli.engine.standalone_ai import VerantyxStandaloneAI

cross_file = Path('.verantyx/conversation.cross.json')
ai = VerantyxStandaloneAI(cross_file, enable_skills=True)

test_input = 'geminiとは'
print(f'Testing: {test_input}')

# ステップバイステップ確認
if ai.knowledge_learner:
    result = ai.knowledge_learner.find_similar_qa(test_input)
    print(f'find_similar_qa: {\"Found\" if result else \"Not found\"}')

intent = ai.analyze_intent(test_input)
print(f'Intent type: {intent[\"type\"]}')

response = ai.generate_response(test_input)
print(f'\\nResponse preview:')
print(response[:200])
"
```

## 次のステップ

成功したら:
1. 複数のトピックで学習テスト（Gemini + Claude + ChatGPT + GPT-4）
2. 会話の流れでの学習（複数ターン）
3. README.mdに実際の使用例を追加
4. GitHubにコミット
