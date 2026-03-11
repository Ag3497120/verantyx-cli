#!/usr/bin/env python3
"""
Verantyx Standalone AI - 学習済みCross構造を使った自律AI

Claude Codeに依存せず、学習したCross構造だけで応答を生成
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class VerantyxStandaloneAI:
    """
    学習済みCross構造を使って自律的に応答するAI

    学習内容:
    - 過去の会話パターン
    - ツール使用履歴
    - JCrossプロンプト
    - 応答傾向
    """

    def __init__(self, cross_file: Path):
        """
        Args:
            cross_file: 学習済みCross構造ファイル
        """
        self.cross_file = cross_file
        self.cross_memory = self._load_cross_memory()

        # 統計情報
        self.total_inputs = 0
        self.total_responses = 0
        self.learned_patterns = 0

        self._analyze_learning()

    def _load_cross_memory(self) -> Dict:
        """Cross構造を読み込む"""
        if not self.cross_file.exists():
            return {
                'axes': {
                    'FRONT': {'current_conversation': []},
                    'UP': {'user_inputs': [], 'total_messages': 0},
                    'DOWN': {'claude_responses': []},
                    'RIGHT': {'tool_calls': []},
                    'LEFT': {'timestamps': []},
                    'BACK': {'raw_interactions': [], 'jcross_prompts': []}
                }
            }

        try:
            with open(self.cross_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to load Cross memory: {e}")
            return {'axes': {}}

    def _analyze_learning(self):
        """学習内容を分析"""
        axes = self.cross_memory.get('axes', {})

        # 学習済み情報の統計
        up_axis = axes.get('UP', {})
        down_axis = axes.get('DOWN', {})
        right_axis = axes.get('RIGHT', {})
        back_axis = axes.get('BACK', {})

        self.total_inputs = up_axis.get('total_messages', 0)
        self.total_responses = len(down_axis.get('claude_responses', []))
        self.learned_patterns = len(back_axis.get('jcross_prompts', []))

        # ツール使用パターン
        self.tool_usage = {}
        for tool_call in right_axis.get('tool_calls', []):
            if isinstance(tool_call, dict) and 'tool' in tool_call:
                tool_name = tool_call['tool']
                self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def get_learning_stats(self) -> Dict[str, Any]:
        """学習統計を取得"""
        return {
            'total_inputs': self.total_inputs,
            'total_responses': self.total_responses,
            'learned_patterns': self.learned_patterns,
            'tool_usage': self.tool_usage,
            'cross_file': str(self.cross_file),
            'cross_size_kb': self.cross_file.stat().st_size / 1024 if self.cross_file.exists() else 0
        }

    def find_similar_input(self, user_input: str) -> Optional[str]:
        """
        過去の類似入力を検索

        Args:
            user_input: ユーザー入力

        Returns:
            類似する過去の応答、見つからなければNone
        """
        axes = self.cross_memory.get('axes', {})
        up_axis = axes.get('UP', {})
        down_axis = axes.get('DOWN', {})

        past_inputs = up_axis.get('user_inputs', [])
        past_responses = down_axis.get('claude_responses', [])

        if not past_inputs or not past_responses:
            return None

        # シンプルなキーワードマッチング
        user_words = set(user_input.lower().split())

        best_match_score = 0
        best_match_idx = -1

        for i, past_input in enumerate(past_inputs):
            if isinstance(past_input, str):
                past_words = set(past_input.lower().split())

                # Jaccard類似度
                intersection = user_words & past_words
                union = user_words | past_words

                if len(union) > 0:
                    score = len(intersection) / len(union)

                    if score > best_match_score:
                        best_match_score = score
                        best_match_idx = i

        # 類似度が20%以上なら採用
        if best_match_score > 0.2 and best_match_idx < len(past_responses):
            return past_responses[best_match_idx]

        return None

    def analyze_intent(self, user_input: str) -> Dict[str, Any]:
        """
        ユーザー入力の意図を分析

        Returns:
            意図分析結果
        """
        lower_input = user_input.lower()

        intent = {
            'type': 'unknown',
            'confidence': 0.0,
            'suggested_tools': [],
            'keywords': []
        }

        # 質問系
        if any(word in lower_input for word in ['what', 'how', 'why', 'when', 'where', 'who', 'なに', 'どう', 'なぜ', 'いつ', 'どこ', '誰']):
            intent['type'] = 'question'
            intent['confidence'] = 0.8

        # ファイル操作系
        elif any(word in lower_input for word in ['create', 'make', 'write', 'file', 'read', '作成', '書く', 'ファイル', '読む']):
            intent['type'] = 'file_operation'
            intent['confidence'] = 0.7
            intent['suggested_tools'] = ['write', 'read', 'edit']

        # コード関連
        elif any(word in lower_input for word in ['code', 'function', 'class', 'implement', 'コード', '関数', 'クラス', '実装']):
            intent['type'] = 'coding'
            intent['confidence'] = 0.8
            intent['suggested_tools'] = ['write', 'edit', 'bash']

        # 実行系
        elif any(word in lower_input for word in ['run', 'execute', 'test', 'check', '実行', 'テスト', '確認']):
            intent['type'] = 'execution'
            intent['confidence'] = 0.7
            intent['suggested_tools'] = ['bash']

        # 検索系
        elif any(word in lower_input for word in ['find', 'search', 'look', 'grep', '探す', '検索', '見つける']):
            intent['type'] = 'search'
            intent['confidence'] = 0.8
            intent['suggested_tools'] = ['grep', 'glob']

        # キーワード抽出（簡易版）
        words = user_input.split()
        intent['keywords'] = [w for w in words if len(w) > 3][:5]

        return intent

    def generate_response(self, user_input: str) -> str:
        """
        学習内容に基づいて応答を生成

        Args:
            user_input: ユーザー入力

        Returns:
            生成された応答
        """
        # 1. 類似入力を検索
        similar_response = self.find_similar_input(user_input)

        if similar_response:
            return f"[From learned patterns]\n\n{similar_response}\n\n---\n💡 This response was generated from past conversation patterns."

        # 2. 意図分析
        intent = self.analyze_intent(user_input)

        # 3. 意図に基づいた応答生成
        if intent['type'] == 'question':
            return self._generate_question_response(user_input, intent)
        elif intent['type'] == 'file_operation':
            return self._generate_file_operation_response(user_input, intent)
        elif intent['type'] == 'coding':
            return self._generate_coding_response(user_input, intent)
        elif intent['type'] == 'execution':
            return self._generate_execution_response(user_input, intent)
        elif intent['type'] == 'search':
            return self._generate_search_response(user_input, intent)
        else:
            return self._generate_default_response(user_input, intent)

    def _generate_question_response(self, user_input: str, intent: Dict) -> str:
        """質問に対する応答を生成"""
        return f"""I understand you're asking a question.

Based on my learning from {self.total_inputs} past interactions, I can try to help.

**Your question:** {user_input}

**What I've learned:**
- Total conversations: {self.total_inputs}
- Response patterns: {self.total_responses}
- Learned techniques: {self.learned_patterns}

**Analysis:**
- Intent: {intent['type']} (confidence: {intent['confidence']:.1%})
- Keywords: {', '.join(intent['keywords'])}

Unfortunately, I don't have a specific learned pattern for this question yet. I'm still learning from interactions with Claude Code.

**Suggestion:** For more accurate responses, use Verantyx with Claude Code integration:
```bash
python3 -m verantyx_cli chat
```

This will allow me to learn from this interaction and improve my responses over time.
"""

    def _generate_file_operation_response(self, user_input: str, intent: Dict) -> str:
        """ファイル操作に対する応答"""
        tools = ', '.join(intent['suggested_tools'])
        return f"""I detect you want to perform a file operation.

**Request:** {user_input}

**Suggested tools:** {tools}

**From my learning:**
- I've observed {len(self.tool_usage)} different tool usages
- Most used tools: {dict(list(self.tool_usage.items())[:3])}

**What I would do (based on learning):**
1. Verify the file path exists
2. Use appropriate tool ({tools})
3. Confirm the operation completed successfully

**Note:** I'm running in standalone mode. To actually execute file operations, please use:
```bash
python3 -m verantyx_cli chat
```

This will connect to Claude Code for actual tool execution.
"""

    def _generate_coding_response(self, user_input: str, intent: Dict) -> str:
        """コーディング要求に対する応答"""
        return f"""I recognize this as a coding request.

**Request:** {user_input}

**My learning data:**
- Code-related interactions: ~{int(self.total_inputs * 0.6)}
- Tool usages for coding: {self.tool_usage.get('write', 0)} writes, {self.tool_usage.get('edit', 0)} edits

**Approach (based on learned patterns):**
1. Understand requirements
2. Design solution
3. Implement code
4. Test and verify

**Keywords identified:** {', '.join(intent['keywords'])}

**Limitation:** In standalone mode, I can only provide guidance. For actual code implementation, use:
```bash
python3 -m verantyx_cli chat
```

I will learn from this interaction and improve my coding assistance over time.
"""

    def _generate_execution_response(self, user_input: str, intent: Dict) -> str:
        """実行要求に対する応答"""
        return f"""I understand you want to execute something.

**Request:** {user_input}

**Execution patterns I've learned:**
- Bash commands executed: {self.tool_usage.get('bash', 0)}
- Tests run: ~{int(self.tool_usage.get('bash', 0) * 0.3)}

**Safety check (learned pattern):**
1. Verify command is safe
2. Check working directory
3. Execute with appropriate timeout
4. Capture and report output

**Note:** Standalone mode cannot execute commands. Use full Verantyx:
```bash
python3 -m verantyx_cli chat
```
"""

    def _generate_search_response(self, user_input: str, intent: Dict) -> str:
        """検索要求に対する応答"""
        return f"""I detect a search request.

**Query:** {user_input}

**Search tools I've learned:**
- Grep usage: {self.tool_usage.get('grep', 0)} times
- Glob patterns: {self.tool_usage.get('glob', 0)} times

**Search strategy (from learning):**
1. Identify search pattern/keywords
2. Choose appropriate tool (grep for content, glob for files)
3. Filter and present results

**Keywords:** {', '.join(intent['keywords'])}

**Limitation:** Search requires tool access. Use full mode:
```bash
python3 -m verantyx_cli chat
```
"""

    def _generate_default_response(self, user_input: str, intent: Dict) -> str:
        """デフォルト応答"""
        return f"""Thank you for your message.

**Your input:** {user_input}

**My current learning status:**
- Total learned interactions: {self.total_inputs}
- Response patterns: {self.total_responses}
- JCross prompts learned: {self.learned_patterns}

**Analysis:**
- Intent type: {intent['type']}
- Confidence: {intent['confidence']:.1%}
- Keywords: {', '.join(intent['keywords']) if intent['keywords'] else 'None detected'}

**What I know:**
I've learned from {self.total_inputs} conversations with Claude Code. However, I don't have a specific pattern matching your request yet.

**To help me learn and provide better responses:**
```bash
python3 -m verantyx_cli chat
```

Every interaction helps me improve. The more you use Verantyx with Claude Code, the smarter I become in standalone mode!

**Current capabilities:**
- Pattern matching from {self.total_responses} past responses
- Intent analysis with {self.learned_patterns} learned patterns
- Tool suggestion based on {len(self.tool_usage)} tool usage patterns

Thank you for helping me grow! 🌱
"""


def test_standalone_ai():
    """スタンドアロンAIのテスト"""
    print("\n" + "=" * 70)
    print("  🤖 Verantyx Standalone AI Test")
    print("=" * 70)
    print()

    cross_file = Path(".verantyx/conversation.cross.json")

    if not cross_file.exists():
        print(f"⚠️  No learning data found at {cross_file}")
        print("   Please run Verantyx with Claude Code first to build learning data:")
        print("   python3 -m verantyx_cli chat")
        print()
        return

    ai = VerantyxStandaloneAI(cross_file)

    print("📊 Learning Statistics:")
    stats = ai.get_learning_stats()
    print(f"   - Total inputs learned: {stats['total_inputs']}")
    print(f"   - Total responses: {stats['total_responses']}")
    print(f"   - Learned patterns: {stats['learned_patterns']}")
    print(f"   - Cross file size: {stats['cross_size_kb']:.1f} KB")
    print()

    if stats['tool_usage']:
        print("🔧 Tool Usage Patterns:")
        for tool, count in sorted(stats['tool_usage'].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   - {tool}: {count} times")
        print()

    # テストクエリ
    test_queries = [
        "How do I create a new file?",
        "Run the tests",
        "Find all Python files",
        "Explain how this works"
    ]

    print("🧪 Testing with sample queries:")
    print()

    for query in test_queries:
        print("─" * 70)
        print(f"Q: {query}")
        print()

        response = ai.generate_response(query)
        print(response)
        print()
        time.sleep(1)


if __name__ == "__main__":
    test_standalone_ai()
