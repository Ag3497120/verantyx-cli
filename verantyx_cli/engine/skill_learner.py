#!/usr/bin/env python3
"""
Skill Learner - Cross構造にスキルを学習

Claude Codeからの操作を観察して技術を習得：
- ファイル操作パターン
- エージェント操作技術
- コード生成手法
- デバッグワークフロー
- 検索・分析手法
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class SkillLearner:
    """
    Claude Codeの操作から技術を学習

    学習対象:
    - Tool使用パターン (Write, Read, Edit, Bash, etc.)
    - ワークフロー (問題解決のステップ)
    - コーディング手法
    - エラー対処方法
    - 検索戦略
    """

    def __init__(self, cross_file: Path):
        """
        Args:
            cross_file: Cross構造ファイル
        """
        self.cross_file = cross_file
        self.cross_memory = self._load_cross_memory()

        # 学習したスキル
        self.learned_skills = {
            'tool_patterns': {},      # ツール使用パターン
            'workflows': [],          # ワークフロー
            'code_templates': {},     # コードテンプレート
            'error_solutions': {},    # エラー解決方法
            'search_strategies': []   # 検索戦略
        }

        self._extract_skills()

    def _load_cross_memory(self) -> Dict:
        """Cross構造を読み込む"""
        if not self.cross_file.exists():
            return {'axes': {}}

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
            print(f"⚠️  Failed to load Cross memory for skill learning: {e}")
            return {'axes': {}}

    def _extract_skills(self):
        """Cross構造からスキルを抽出"""
        axes = self.cross_memory.get('axes', {})

        # ツール使用パターンを学習
        self._learn_tool_patterns(axes.get('RIGHT', {}))

        # ワークフローを学習
        self._learn_workflows(axes.get('FRONT', {}))

        # コードテンプレートを学習
        self._learn_code_templates(axes.get('DOWN', {}))

        # エラー解決を学習
        self._learn_error_solutions(axes.get('BACK', {}))

    def _learn_tool_patterns(self, right_axis: Dict):
        """
        ツール使用パターンを学習

        例:
        - ファイル作成時: Write → Bash(確認) のパターン
        - テスト実行時: Bash(test) → Read(結果) のパターン
        """
        tool_calls = right_axis.get('tool_calls', [])

        if not tool_calls:
            return

        # ツールシーケンスを抽出
        sequences = []
        current_sequence = []

        for tool_call in tool_calls:
            if isinstance(tool_call, dict):
                tool_name = tool_call.get('tool', 'unknown')
                current_sequence.append(tool_name)

                # 3つ以上のシーケンス
                if len(current_sequence) >= 3:
                    seq_str = ' → '.join(current_sequence[-3:])
                    sequences.append(seq_str)

        # パターンをカウント
        for seq in sequences:
            self.learned_skills['tool_patterns'][seq] = \
                self.learned_skills['tool_patterns'].get(seq, 0) + 1

    def _learn_workflows(self, front_axis: Dict):
        """
        ワークフローを学習

        例:
        1. 問題分析 → ファイル読み込み → 修正 → テスト
        2. 検索 → 確認 → 実装 → 検証
        """
        conversations = front_axis.get('current_conversation', [])

        # 対話から問題解決フローを抽出
        for conv in conversations:
            if isinstance(conv, dict):
                role = conv.get('role', '')
                content = str(conv.get('content', ''))

                if role == 'user':
                    # ユーザーの要求からタスクタイプを推定
                    task_type = self._classify_task(content)

                    workflow = {
                        'task_type': task_type,
                        'request': content[:100],
                        'timestamp': conv.get('timestamp', time.time())
                    }

                    self.learned_skills['workflows'].append(workflow)

    def _classify_task(self, content: str) -> str:
        """タスクタイプを分類"""
        lower = content.lower()

        if any(w in lower for w in ['create', 'write', 'make', 'add']):
            return 'creation'
        elif any(w in lower for w in ['fix', 'debug', 'error', 'bug']):
            return 'debugging'
        elif any(w in lower for w in ['find', 'search', 'look', 'grep']):
            return 'search'
        elif any(w in lower for w in ['test', 'check', 'verify', 'run']):
            return 'testing'
        elif any(w in lower for w in ['update', 'modify', 'change', 'edit']):
            return 'modification'
        elif any(w in lower for w in ['explain', 'what', 'how', 'why']):
            return 'explanation'
        else:
            return 'other'

    def _learn_code_templates(self, down_axis: Dict):
        """
        コードテンプレートを学習

        Claude Codeの応答から再利用可能なコードパターンを抽出
        """
        responses = down_axis.get('claude_responses', [])

        for response in responses:
            if isinstance(response, str):
                # コードブロックを抽出
                code_blocks = re.findall(r'```(\w+)?\n(.*?)```', response, re.DOTALL)

                for lang, code in code_blocks:
                    if code.strip():
                        template_type = self._classify_code_template(code, lang)

                        if template_type not in self.learned_skills['code_templates']:
                            self.learned_skills['code_templates'][template_type] = []

                        self.learned_skills['code_templates'][template_type].append({
                            'language': lang or 'unknown',
                            'code': code.strip()[:500],  # 最初の500文字
                            'learned_at': datetime.now().isoformat()
                        })

    def _classify_code_template(self, code: str, lang: str) -> str:
        """コードテンプレートのタイプを分類"""
        code_lower = code.lower()

        if 'def ' in code_lower or 'function' in code_lower:
            return 'function'
        elif 'class ' in code_lower:
            return 'class'
        elif 'import ' in code_lower or 'from ' in code_lower:
            return 'imports'
        elif 'test' in code_lower or 'assert' in code_lower:
            return 'test'
        elif 'if __name__' in code_lower:
            return 'main'
        else:
            return 'snippet'

    def _learn_error_solutions(self, back_axis: Dict):
        """
        エラー解決方法を学習

        JCrossプロンプトやRaw interactionsからエラー対処法を抽出
        """
        raw_interactions = back_axis.get('raw_interactions', [])

        for interaction in raw_interactions:
            if isinstance(interaction, str):
                # エラーメッセージを検出
                if 'error' in interaction.lower() or 'exception' in interaction.lower():
                    error_type = self._extract_error_type(interaction)

                    if error_type:
                        if error_type not in self.learned_skills['error_solutions']:
                            self.learned_skills['error_solutions'][error_type] = []

                        self.learned_skills['error_solutions'][error_type].append({
                            'context': interaction[:200],
                            'learned_at': datetime.now().isoformat()
                        })

    def _extract_error_type(self, text: str) -> Optional[str]:
        """エラータイプを抽出"""
        # 一般的なエラーパターン
        patterns = [
            r'(\w+Error):',
            r'(\w+Exception):',
            r'Error: (\w+)',
            r'(\w+) error',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def get_skill_summary(self) -> Dict[str, Any]:
        """学習したスキルのサマリーを取得"""
        return {
            'tool_patterns_count': len(self.learned_skills['tool_patterns']),
            'top_patterns': sorted(
                self.learned_skills['tool_patterns'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'workflows_count': len(self.learned_skills['workflows']),
            'workflow_distribution': self._get_workflow_distribution(),
            'code_templates_count': sum(
                len(templates) for templates in self.learned_skills['code_templates'].values()
            ),
            'template_types': list(self.learned_skills['code_templates'].keys()),
            'error_solutions_count': len(self.learned_skills['error_solutions']),
            'known_errors': list(self.learned_skills['error_solutions'].keys())
        }

    def _get_workflow_distribution(self) -> Dict[str, int]:
        """ワークフローの分布を取得"""
        distribution = {}
        for workflow in self.learned_skills['workflows']:
            task_type = workflow['task_type']
            distribution[task_type] = distribution.get(task_type, 0) + 1
        return distribution

    def get_tool_pattern(self, task_type: str) -> Optional[List[str]]:
        """
        タスクタイプに適したツールパターンを取得

        Args:
            task_type: 'creation', 'debugging', 'search', etc.

        Returns:
            推奨ツールシーケンス
        """
        # タスクタイプに基づいてパターンを推薦
        recommendations = {
            'creation': ['Write', 'Bash', 'Read'],
            'debugging': ['Read', 'Grep', 'Edit', 'Bash'],
            'search': ['Grep', 'Glob', 'Read'],
            'testing': ['Bash', 'Read'],
            'modification': ['Read', 'Edit', 'Bash'],
        }

        # 学習したパターンを優先
        learned_pattern = self._find_learned_pattern_for_task(task_type)
        if learned_pattern:
            return learned_pattern

        # なければデフォルト
        return recommendations.get(task_type, ['Read'])

    def _find_learned_pattern_for_task(self, task_type: str) -> Optional[List[str]]:
        """タスクタイプに対する学習済みパターンを検索"""
        # 簡易版: 最も使用されているパターンを返す
        if self.learned_skills['tool_patterns']:
            top_pattern = max(
                self.learned_skills['tool_patterns'].items(),
                key=lambda x: x[1]
            )[0]
            return top_pattern.split(' → ')

        return None

    def get_code_template(self, template_type: str, language: str = None) -> Optional[str]:
        """
        コードテンプレートを取得

        Args:
            template_type: 'function', 'class', 'test', etc.
            language: プログラミング言語（オプション）

        Returns:
            コードテンプレート
        """
        templates = self.learned_skills['code_templates'].get(template_type, [])

        if not templates:
            return None

        # 言語指定があればフィルタ
        if language:
            templates = [t for t in templates if t['language'] == language]

        if templates:
            # 最新のテンプレートを返す
            return templates[-1]['code']

        return None

    def get_error_solution(self, error_type: str) -> Optional[List[str]]:
        """
        エラーの解決方法を取得

        Args:
            error_type: エラータイプ（例: 'SyntaxError'）

        Returns:
            解決方法のリスト
        """
        solutions = self.learned_skills['error_solutions'].get(error_type, [])

        if solutions:
            return [sol['context'] for sol in solutions]

        return None

    def save_learned_skills(self, output_path: Path):
        """学習したスキルを保存"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.learned_skills, f, indent=2, ensure_ascii=False)

    def load_learned_skills(self, input_path: Path):
        """保存されたスキルを読み込む"""
        if input_path.exists():
            with open(input_path, 'r', encoding='utf-8') as f:
                self.learned_skills = json.load(f)


def test_skill_learner():
    """スキル学習のテスト"""
    print("\n" + "=" * 70)
    print("  🎓 Skill Learner Test")
    print("=" * 70)
    print()

    cross_file = Path(".verantyx/conversation.cross.json")

    if not cross_file.exists():
        print(f"⚠️  No Cross file found: {cross_file}")
        return

    learner = SkillLearner(cross_file)

    print("📊 Learned Skills Summary:")
    summary = learner.get_skill_summary()

    print(f"\n  Tool Patterns: {summary['tool_patterns_count']}")
    if summary['top_patterns']:
        print("  Top 5 patterns:")
        for pattern, count in summary['top_patterns']:
            print(f"    - {pattern}: {count} times")

    print(f"\n  Workflows: {summary['workflows_count']}")
    if summary['workflow_distribution']:
        print("  Distribution:")
        for task_type, count in summary['workflow_distribution'].items():
            print(f"    - {task_type}: {count}")

    print(f"\n  Code Templates: {summary['code_templates_count']}")
    if summary['template_types']:
        print(f"  Types: {', '.join(summary['template_types'])}")

    print(f"\n  Error Solutions: {summary['error_solutions_count']}")
    if summary['known_errors']:
        print(f"  Known errors: {', '.join(summary['known_errors'][:5])}")

    print()

    # スキルのテスト
    print("🧪 Testing Skill Retrieval:")
    print()

    pattern = learner.get_tool_pattern('creation')
    print(f"  Tool pattern for 'creation': {pattern}")

    template = learner.get_code_template('function', 'python')
    if template:
        print(f"  Code template for 'function':")
        print(f"    {template[:100]}...")

    print()


if __name__ == "__main__":
    test_skill_learner()
