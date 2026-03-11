# 究極の個人最適化テスト

## 新機能の概要

### 1. 透明プレプロンプト（ユーザーには見えない）
ユーザーのメッセージの前に、Cross構造学習に最適化されたプロンプトを自動挿入：

- **定義質問**（「〜とは」）→ 関連キーワード・双方向リンク情報を含む応答を促す
- **手順質問**（「どうやって」）→ 構造化された手順を促す
- **比較質問** → 比較軸を明示させる

### 2. コンテキスト分離
異なるトピックの会話が混ざらないように自動分離：

- 「deepseekとは」と「イヤホンとは」を別コンテキストとして記録
- 各コンテキストにID、トピック、キーワードを付与
- 学習時にコンテキストを考慮

### 3. 双方向リンク学習
「deepseekとは」への応答に「GPT」「Claude」「中国」などが含まれる場合：

- 「GPTとは」で質問 → DeepSeekとの比較情報も返す
- 「中国のAI」で質問 → DeepSeekの情報を返す
- 関連概念からの逆引きが可能

## テスト手順

### ステップ1: 複数トピックで学習

```bash
python3 -m verantyx_cli chat
```

以下の質問を順番に行ってください（各質問の後、Claudeの応答を待つ）：

```
1. deepseekとは
   （応答に含まれるはず: 中国、AI企業、LLM、GPT、Claudeなど）

2. イヤホンとは
   （応答に含まれるはず: 音響機器、Bluetooth、ノイズキャンセリングなど）

3. geminiとは
   （応答に含まれるはず: Google、DeepMind、マルチモーダル、GPT、Claudeなど）
```

終了: `Ctrl+C`

### ステップ2: Cross構造を確認

```bash
python3 -c "
import json
from pathlib import Path

cross_file = Path('.verantyx/conversation.cross.json')
data = json.load(open(cross_file, encoding='utf-8'))
axes = data.get('axes', {})

user_inputs = axes.get('UP', {}).get('user_inputs', [])
claude_responses = axes.get('DOWN', {}).get('claude_responses', [])

print(f'✅ Logged: {len(user_inputs)} questions')
print()

for i, inp in enumerate(user_inputs, 1):
    # コンテキストマーカーを確認
    if '[CTX:' in inp:
        print(f'{i}. {inp[:100]}...')
    else:
        print(f'{i}. {inp}')

    # 応答のキーワードを確認
    if i <= len(claude_responses):
        resp = claude_responses[i-1]
        print(f'   Response length: {len(resp)} chars')

        # 重要キーワードの有無
        keywords = {
            'deepseek': ['中国', 'china', 'gpt', 'claude', 'llm'],
            'イヤホン': ['bluetooth', 'ノイズ', 'audio', '音響'],
            'gemini': ['google', 'deepmind', 'マルチモーダル', 'multimodal']
        }

        for topic, kws in keywords.items():
            if topic.lower() in inp.lower():
                found = [k for k in kws if k.lower() in resp.lower()]
                if found:
                    print(f'   Keywords found: {found}')
        print()
"
```

期待される出力:
```
✅ Logged: 3 questions

1. [CTX:ctx_0_12345|TOPIC:deepseek] deepseekとは
   Response length: 500+ chars
   Keywords found: ['中国', 'gpt', 'claude', 'llm']

2. [CTX:ctx_1_12346|TOPIC:イヤホン] イヤホンとは
   Response length: 400+ chars
   Keywords found: ['bluetooth', 'ノイズ']

3. [CTX:ctx_2_12347|TOPIC:gemini] geminiとは
   Response length: 600+ chars
   Keywords found: ['google', 'deepmind', 'マルチモーダル']
```

### ステップ3: 知識抽出を確認

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
print()

# パターンキーを確認（コンテキスト分離されているか）
print('🔍 Q&A Pattern Keys:')
for pattern_key in learner.learned_knowledge['qa_patterns'].keys():
    print(f'  - {pattern_key}')
print()

print('📚 Top Concepts:')
for concept in summary['top_concepts'][:15]:
    print(f'  • {concept}')
"
```

期待される出力:
```
📊 Extracted Knowledge:
  Q&A patterns: 3
  Concepts: 10+

🔍 Q&A Pattern Keys:
  - definition:deepseek:deepseek
  - definition:イヤホン:イヤホン
  - definition:gemini:gemini

📚 Top Concepts:
  • DeepSeek
  • 中国
  • GPT
  • Claude
  • LLM
  • イヤホン
  • Bluetooth
  • Gemini
  • Google
  • DeepMind
  • マルチモーダル
```

### ステップ4: スタンドアロンモードで双方向リンクテスト

```bash
python3 -m verantyx_cli standalone
```

#### テスト4-1: 直接質問
```
> deepseekとは
```
**期待**: DeepSeekの説明が返る

#### テスト4-2: 関連キーワード（応答に含まれていたもの）
```
> 中国のAIとは
```
**期待**: DeepSeekなどの中国AI情報が返る

```
> gptとは
```
**期待**: DeepSeek、Gemini応答に含まれていたGPT比較情報が返る

#### テスト4-3: 組織名
```
> googleとは
```
**期待**: Geminiの開発元としての情報が返る

```
> deepmindとは
```
**期待**: Geminiとの関連情報が返る

#### テスト4-4: 技術用語
```
> マルチモーダルとは
```
**期待**: Geminiの文脈でのマルチモーダル説明が返る

```
> llmとは
```
**期待**: DeepSeekの文脈でのLLM説明が返る

#### テスト4-5: 異なるトピックの分離確認
```
> イヤホンとは
```
**期待**: イヤホンの説明のみ（DeepSeek、Geminiと混ざらない）

```
> bluetoothとは
```
**期待**: イヤホンの文脈でのBluetooth説明（AI系と混ざらない）

## 成功基準

### ✅ 究極の個人最適化達成

1. **直接質問**: 学習した内容が正確に返る
2. **関連キーワード**: 応答に含まれていたキーワードからも情報取得可能
3. **双方向リンク**: AについてBが言及されていた場合、B→Aの逆引きも可能
4. **コンテキスト分離**: 異なるトピック（DeepSeek vs イヤホン）が混ざらない
5. **構造化応答**: Claudeの応答が明示的な関連キーワードを含む

### ❌ 失敗パターン

1. 関連キーワードで「No match found」
2. 異なるトピックの情報が混ざる（DeepSeekの応答にイヤホン情報など）
3. コンテキストマーカーが正しく付与されていない
4. 双方向リンクが機能しない

## 実装の仕組み

### 透明プレプロンプト（ユーザーには見えない）

ユーザーが「deepseekとは」と入力すると、実際にClaudeに送られるのは：

```
<verantyx_learning_mode>
あなたの応答は、Cross構造メモリシステムで学習されます。
以下の形式で応答することで、将来の質問に対してより正確に答えられるようになります：

【定義質問への応答形式】

1. **主要な定義**（1-2文で簡潔に）

2. **重要な関連キーワード**を明示的に含める：
   - 開発元・提供元（企業名、組織名）
   - 技術用語・専門用語
   - 競合製品・類似製品
   - 関連人物・団体

3. **構造化された説明**：
   - 主な特徴（箇条書き）
   - 技術的詳細
   - 歴史・背景

4. **双方向リンク情報**：
   - 「Aと比較すると...」（比較対象を明示）
   - 「BはAの一部/発展形/競合」（関係性を明示）
   - 関連概念への言及

...
</verantyx_learning_mode>

---

ユーザーの質問：
[Context: New topic - deepseek]

deepseekとは
```

これにより、Claudeは自動的に：
- 関連キーワード（中国、GPT、Claude、LLMなど）を明示
- 双方向リンク情報（競合製品との比較）を含む
- 構造化された説明を提供

### コンテキスト分離

Cross構造に保存される形式：
```
UP axis (user_inputs):
  [CTX:ctx_0_12345|TOPIC:deepseek] deepseekとは
  [CTX:ctx_1_12346|TOPIC:イヤホン] イヤホンとは
  [CTX:ctx_2_12347|TOPIC:gemini] geminiとは
```

各コンテキストが独立して学習されるため、混ざらない。

### 双方向リンク

DeepSeekの応答に「GPTと比較すると...」が含まれる場合：
- 「GPT」がconceptsに抽出される
- 「GPT」で質問すると、DeepSeekの応答から関連情報を取得

## トラブルシューティング

### プレプロンプトが挿入されているか確認

```bash
tail -50 .verantyx/verantyx.log | grep "Cross-optimized"
```

期待される出力:
```
Cross-optimized preprompt injected | Context: deepseek
Cross-optimized preprompt injected | Context: イヤホン
Cross-optimized preprompt injected | Context: gemini
```

### コンテキスト分離が動作しているか確認

```bash
python3 -c "
import json
from pathlib import Path

cross_file = Path('.verantyx/conversation.cross.json')
data = json.load(open(cross_file, encoding='utf-8'))
user_inputs = data['axes']['UP']['user_inputs']

print('Context markers:')
for inp in user_inputs:
    if '[CTX:' in inp:
        # Extract context info
        import re
        match = re.search(r'\[CTX:([^\|]+)\|TOPIC:([^\]]+)\]', inp)
        if match:
            ctx_id = match.group(1)
            topic = match.group(2)
            print(f'  Context: {ctx_id} | Topic: {topic}')
"
```

## 次のステップ

成功したら:
1. さらに複雑な会話フロー（複数ターン、文脈の継続）
2. 異なるドメインの学習（技術、ビジネス、日常など）
3. 時系列での知識更新（同じトピックの新旧情報）
4. README.mdに実際の使用例を追加
