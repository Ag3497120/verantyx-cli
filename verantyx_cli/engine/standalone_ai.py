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

from .skill_learner import SkillLearner
from .skill_executor import SkillExecutor
from .knowledge_learner import KnowledgeLearner
from .kofdai_resonance_engine import KofdaiResonanceEngine


class VerantyxStandaloneAI:
    """
    学習済みCross構造を使って自律的に応答するAI

    学習内容:
    - 過去の会話パターン
    - ツール使用履歴
    - JCrossプロンプト
    - 応答傾向
    """

    def __init__(self, cross_file: Path, project_path: Path = None, enable_skills: bool = True):
        """
        Args:
            cross_file: 学習済みCross構造ファイル
            project_path: プロジェクトディレクトリ
            enable_skills: スキル実行を有効化するか
        """
        self.cross_file = cross_file
        self.project_path = project_path or Path(".")
        self.cross_memory = self._load_cross_memory()

        # 統計情報
        self.total_inputs = 0
        self.total_responses = 0
        self.learned_patterns = 0

        self._analyze_learning()

        # スキル学習・実行
        self.skills_enabled = enable_skills
        self.skill_learner = None
        self.skill_executor = None

        if enable_skills:
            self.skill_learner = SkillLearner(cross_file)
            self.skill_executor = SkillExecutor(self.skill_learner, self.project_path)

        # 一般知識学習
        self.knowledge_learner = KnowledgeLearner(cross_file)

        # Kofdai型全同調エンジン
        resonance_file = Path.home() / '.verantyx' / 'resonance_patterns.json'
        self.kofdai_engine = KofdaiResonanceEngine(resonance_file)

        # Cross空間位置管理（逆引きクエリ用）
        from .cross_space_manager import CrossSpaceManager
        space_file = Path(str(cross_file).replace('.jcross', '.space.jcross'))
        self.cross_space = CrossSpaceManager(space_file)

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
            # .jcrossファイルを読み込む
            if str(self.cross_file).endswith('.jcross'):
                from .jcross_storage_processors import JCrossStorageEngine
                storage = JCrossStorageEngine(self.cross_file)
                # memory構造をaxes形式に変換
                return {'axes': storage.memory}
            else:
                # 従来の.json形式
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
        stats = {
            'total_inputs': self.total_inputs,
            'total_responses': self.total_responses,
            'learned_patterns': self.learned_patterns,
            'tool_usage': self.tool_usage,
            'cross_file': str(self.cross_file),
            'cross_size_kb': self.cross_file.stat().st_size / 1024 if self.cross_file.exists() else 0
        }

        # スキル学習統計を追加
        if self.skills_enabled and self.skill_learner:
            skill_summary = self.skill_learner.get_skill_summary()
            stats['skills'] = skill_summary

        # 一般知識統計を追加
        if self.knowledge_learner:
            knowledge_summary = self.knowledge_learner.get_knowledge_summary()
            stats['knowledge'] = knowledge_summary

        return stats

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

    def _try_reverse_query(self, user_input: str) -> Optional[str]:
        """
        Cross空間での逆引きクエリを試行

        例:
        - 「バラ科の果物は？」→ カテゴリ=バラ科 → りんご
        - 「学名がMalus domesticaの果物は？」→ 属性=学名, 値=Malus domestica → りんご
        """
        import re

        # パターン1: 「〜科の〜は？」（カテゴリ検索）
        match = re.search(r'(.+科)の(.+?)(?:は|って)', user_input)
        if match:
            category = match.group(1)
            entities = self.cross_space.query_by_category(category)

            if entities:
                result = f"""[Cross空間逆引き検索]

質問: {user_input}
検索条件: カテゴリ={category}

結果:
{', '.join(sorted(entities))}

---
🔍 **Cross空間位置ベース推論**

この応答はCross空間での逆引きクエリにより生成されました。
同じ会話内の単語は近い位置に配置され、カテゴリから実体を逆引きできます。

Cross空間統計:
- 総単語数: {len(self.cross_space.word_layer)}
- カテゴリ数: {len(self.cross_space.category_index)}
"""
                return result

        # パターン2: 「〜属の〜は？」（カテゴリ検索）
        match = re.search(r'(.+属)の(.+?)(?:は|って)', user_input)
        if match:
            category = match.group(1)
            entities = self.cross_space.query_by_category(category)

            if entities:
                result = f"""[Cross空間逆引き検索]

質問: {user_input}
検索条件: カテゴリ={category}

結果:
{', '.join(sorted(entities))}

---
🔍 **Cross空間位置ベース推論**
"""
                return result

        # パターン3: 「学名が〜の〜は？」（属性検索）
        match = re.search(r'(.+?)が(.+?)の(.+?)(?:は|って)', user_input)
        if match:
            attr = match.group(1)
            value = match.group(2)

            entity = self.cross_space.query_by_attribute(attr, value)

            if entity:
                result = f"""[Cross空間逆引き検索]

質問: {user_input}
検索条件: 属性={attr}, 値={value}

結果:
{entity}

---
🔍 **Cross空間位置ベース推論**

この応答はCross空間での属性逆引きにより生成されました。
"""
                return result

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

        # 質問系（日本語の「〜とは」「〜って何」パターンを追加）
        if any(word in lower_input for word in ['what', 'how', 'why', 'when', 'where', 'who', 'なに', 'どう', 'なぜ', 'いつ', 'どこ', '誰']) or \
           'とは' in user_input or 'って何' in user_input or 'って' in user_input:
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

        Kofdai型全同調処理:
        1. 入力をエネルギー波として処理
        2. 全パターンが同時に共鳴
        3. 最大共鳴が自然に選ばれる
        4. 適切なアクションを実行

        Args:
            user_input: ユーザー入力（エネルギー波）

        Returns:
            生成された応答
        """
        # 0. Kofdai型全同調処理
        resonance_result = self.kofdai_engine.process_input_wave(user_input, execute=False)
        best_pattern = resonance_result['best_pattern']
        confidence = resonance_result['confidence']
        action = resonance_result['action']
        score = resonance_result['score']

        # 共鳴結果をログ
        print(f"🌊 Resonance: pattern={best_pattern}, score={score:.1%}, confidence={confidence}, action={action}")

        # 1. 【新機能】Cross空間逆引きクエリ
        reverse_query_result = self._try_reverse_query(user_input)
        if reverse_query_result:
            # パターン成功を記録
            self.kofdai_engine.update_pattern_position(best_pattern, success=True)
            return reverse_query_result

        # 2. セマンティック検索（definition_query, explanation_requestアクションの場合）
        if action == "semantic_search" and self.knowledge_learner:
            # セマンティック検索（操作コマンド付き）
            semantic_result = self.knowledge_learner.execute_semantic_search_with_operations(user_input)
        else:
            semantic_result = None

            if semantic_result and semantic_result["response"]:
                # パターン成功を記録
                self.kofdai_engine.update_pattern_position(best_pattern, success=True)

                # 操作コマンドをフォーマット
                operations_text = "\n".join([f"  • {op}" for op in semantic_result["operations"]])

                # 共鳴情報を追加
                resonance_info = "\n".join([
                    f"  • {r['pattern']}: {r['score']:.1%} ({r['confidence']})"
                    for r in resonance_result['all_resonances'][:3]
                ])

                return f"""[Kofdai型全同調 → Semantic Search]

{semantic_result["response"]}

---
🌊 **Resonance Analysis:**
{resonance_info}
  → Selected: {best_pattern} ({confidence} confidence)

🔍 **Semantic Operations Executed:**
{operations_text}

📊 **Analysis:**
  • Entity: {semantic_result["entity"]}
  • Intent: {semantic_result["intent"]}
  • Match Score: {semantic_result["score"]:.2f}

---
💡 **Kofdai Principle Applied:**
  • 全パターンが同時に共鳴
  • 最大共鳴が自然に選ばれる
  • パターンがCross空間でFRONT-UPへ移動

To expand my knowledge, continue using:
```bash
python3 -m verantyx_cli chat
```
"""

        # 2. 類似入力を検索（パターンマッチング）
        similar_response = self.find_similar_input(user_input)

        if similar_response:
            return f"[From learned patterns]\n\n{similar_response}\n\n---\n💡 This response was generated from past conversation patterns."

        # 3. 意図分析
        intent = self.analyze_intent(user_input)

        # 4. スキル実行モード（有効な場合）
        if self.skills_enabled and self.skill_executor:
            skill_result = self.skill_executor.execute_task(user_input)

            if skill_result['success']:
                return self._format_skill_response(user_input, intent, skill_result)

        # 5. 意図に基づいた応答生成（一般知識を活用）
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

    def _format_skill_response(self, user_input: str, intent: Dict, skill_result: Dict) -> str:
        """スキル実行結果をフォーマット"""
        steps_summary = "\n".join([
            f"   {i+1}. {step.get('action', 'unknown')}: {step.get('file', step.get('command', step.get('pattern', '...')))}"
            for i, step in enumerate(skill_result.get('steps', [])[:5])
        ])

        return f"""[Skill Execution Result]

**Request:** {user_input}

**Task Type:** {skill_result.get('task_type', 'unknown')}

**Learned Tools Used:** {', '.join(skill_result.get('tools_used', [])[:5])}

**Execution Steps:**
{steps_summary}

**Result:**
{skill_result.get('output', 'No output')}

---
🎓 **Skill Learning Active**

This response was generated using operational skills learned from Claude Code:
- Tool patterns: Learned from observing Claude's tool usage
- Workflows: Extracted from past problem-solving sequences
- Code templates: Reused from successful past implementations

**Note:** Running in skill execution mode (dry run). To actually execute operations, use:
```bash
python3 -m verantyx_cli chat
```

Every interaction with Claude Code teaches me more operational techniques!
"""

    def get_learned_knowledge_summary(self) -> str:
        """学習した一般知識のサマリーを取得"""
        if not self.knowledge_learner:
            return "Knowledge learning is disabled."

        summary = self.knowledge_learner.get_knowledge_summary()

        output = "📚 **Learned Knowledge Summary**\n\n"

        output += f"**Q&A Patterns:** {summary['qa_patterns_count']}\n"
        if summary['qa_types']:
            output += f"Question types: {', '.join(summary['qa_types'])}\n\n"

        output += f"**Concepts:** {summary['concepts_count']}\n"
        if summary['top_concepts']:
            output += "Top concepts:\n"
            for concept in summary['top_concepts'][:5]:
                output += f"  - {concept}\n"
            output += "\n"

        output += f"**Technical Knowledge:** {summary['technical_knowledge_count']}\n"
        if summary['technical_categories']:
            output += f"Categories: {', '.join(summary['technical_categories'])}\n\n"

        output += f"**Reasoning Patterns:** {summary['reasoning_patterns_count']}\n"
        output += f"**Advice Patterns:** {summary['advice_patterns_count']}\n"
        if summary['advice_categories']:
            output += f"Categories: {', '.join(summary['advice_categories'])}\n"

        return output

    def get_learned_skills_summary(self) -> str:
        """学習したスキルのサマリーを取得"""
        if not self.skills_enabled or not self.skill_learner:
            return "Skill learning is disabled."

        summary = self.skill_learner.get_skill_summary()

        output = "🎓 **Learned Skills Summary**\n\n"

        output += f"**Tool Patterns:** {summary['tool_patterns_count']}\n"
        if summary['top_patterns']:
            output += "Top 5 patterns:\n"
            for pattern, count in summary['top_patterns'][:5]:
                output += f"  - {pattern}: {count} times\n"
            output += "\n"

        output += f"**Workflows:** {summary['workflows_count']}\n"
        if summary['workflow_distribution']:
            output += "Distribution:\n"
            for task_type, count in summary['workflow_distribution'].items():
                output += f"  - {task_type}: {count}\n"
            output += "\n"

        output += f"**Code Templates:** {summary['code_templates_count']}\n"
        if summary['template_types']:
            output += f"Types: {', '.join(summary['template_types'])}\n\n"

        output += f"**Error Solutions:** {summary['error_solutions_count']}\n"
        if summary['known_errors']:
            output += f"Known errors: {', '.join(summary['known_errors'][:5])}\n"

        return output

    def _generate_question_response(self, user_input: str, intent: Dict) -> str:
        """質問に対する応答を生成"""
        response_parts = []

        response_parts.append(f"**Your question:** {user_input}\n")

        # 一般知識から関連概念を探す
        if self.knowledge_learner:
            # キーワードから概念を検索
            keywords = intent.get('keywords', [])
            concept_found = False

            for keyword in keywords[:3]:
                explanation = self.knowledge_learner.get_concept_explanation(keyword)
                if explanation:
                    response_parts.append(f"\n📚 **Learned concept: {keyword}**\n")
                    response_parts.append(f"{explanation}\n")
                    concept_found = True
                    break

            # 技術知識を追加
            if not concept_found:
                best_practices = self.knowledge_learner.get_technical_knowledge('best_practices')
                if best_practices:
                    response_parts.append("\n💡 **Related best practices I've learned:**\n")
                    response_parts.append(f"{best_practices[0][:300]}...\n")

            # アドバイスを追加
            advice = self.knowledge_learner.get_advice('general')
            if advice:
                response_parts.append("\n🎯 **General advice from my learning:**\n")
                response_parts.append(f"{advice[0][:300]}...\n")

        if len(response_parts) == 1:
            # 学習した知識がない場合
            response_parts.append(f"""
**Analysis:**
- Intent: {intent['type']} (confidence: {intent['confidence']:.1%})
- Keywords: {', '.join(intent['keywords'])}

**My learning status:**
- Total conversations: {self.total_inputs}
- Response patterns: {self.total_responses}
- Learned techniques: {self.learned_patterns}

I don't have specific learned knowledge for this question yet.

**Suggestion:** For accurate responses, use Verantyx with Claude Code:
```bash
python3 -m verantyx_cli chat
```

Every interaction helps me learn!
""")
        else:
            # 学習した知識がある場合
            response_parts.append(f"""
---
📚 **This response includes learned knowledge from {self.total_inputs} past interactions**

For more comprehensive answers, use full mode:
```bash
python3 -m verantyx_cli chat
```
""")

        return '\n'.join(response_parts)

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
