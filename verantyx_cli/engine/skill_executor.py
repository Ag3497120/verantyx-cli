#!/usr/bin/env python3
"""
Skill Executor - 学習したスキルを実行

スタンドアロンモードで学習した技術を実際に使用：
- ファイル操作の実行
- コード生成
- エラー対処
- 検索実行
"""

import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from .skill_learner import SkillLearner


class SkillExecutor:
    """
    学習したスキルを実行するエンジン

    機能:
    - ファイル読み書き
    - コマンド実行
    - コード生成
    - パターン適用
    """

    def __init__(self, skill_learner: SkillLearner, project_path: Path):
        """
        Args:
            skill_learner: スキル学習器
            project_path: プロジェクトディレクトリ
        """
        self.learner = skill_learner
        self.project_path = project_path

        # 実行履歴
        self.execution_history = []

    def execute_task(self, user_request: str) -> Dict[str, Any]:
        """
        ユーザーリクエストに基づいてタスクを実行

        Args:
            user_request: ユーザーの要求

        Returns:
            実行結果
        """
        # タスクタイプを分類
        task_type = self.learner._classify_task(user_request)

        # ツールパターンを取得
        tool_pattern = self.learner.get_tool_pattern(task_type)

        result = {
            'task_type': task_type,
            'tools_used': tool_pattern or [],
            'steps': [],
            'success': False,
            'output': None,
            'error': None
        }

        try:
            # タスクタイプに応じた実行
            if task_type == 'creation':
                result = self._execute_creation(user_request, result)
            elif task_type == 'search':
                result = self._execute_search(user_request, result)
            elif task_type == 'testing':
                result = self._execute_testing(user_request, result)
            elif task_type == 'modification':
                result = self._execute_modification(user_request, result)
            elif task_type == 'debugging':
                result = self._execute_debugging(user_request, result)
            else:
                result['output'] = "Task type recognized, but execution pattern not yet learned."

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
            result['success'] = False

        # 履歴に追加
        self.execution_history.append(result)

        return result

    def _execute_creation(self, request: str, result: Dict) -> Dict:
        """ファイル作成タスクを実行"""
        # ファイル名を抽出
        filename = self._extract_filename(request)

        if not filename:
            result['output'] = "Could not determine filename. Please specify explicitly."
            return result

        # コードテンプレートを取得
        language = self._detect_language(filename)
        template_type = 'function' if 'function' in request.lower() else 'main'

        code_template = self.learner.get_code_template(template_type, language)

        result['steps'].append({
            'action': 'detect_language',
            'language': language
        })

        result['steps'].append({
            'action': 'get_template',
            'template_type': template_type
        })

        # ファイルを作成
        file_path = self.project_path / filename

        if code_template:
            # 学習したテンプレートを使用
            content = code_template
            result['steps'].append({
                'action': 'use_learned_template',
                'template': content[:100]
            })
        else:
            # デフォルトテンプレート
            content = self._get_default_template(language)
            result['steps'].append({
                'action': 'use_default_template'
            })

        # ファイル書き込み（ドライラン）
        result['output'] = f"""
Would create file: {file_path}

Content:
```{language}
{content}
```

Note: Running in skill execution mode (dry run).
To actually create the file, the content is ready above.
"""

        result['steps'].append({
            'action': 'dry_run_complete',
            'file': str(file_path)
        })

        return result

    def _execute_search(self, request: str, result: Dict) -> Dict:
        """検索タスクを実行"""
        # 検索キーワードを抽出
        keywords = self._extract_keywords(request)

        result['steps'].append({
            'action': 'extract_keywords',
            'keywords': keywords
        })

        # 検索パターンを構築
        search_pattern = '|'.join(keywords) if keywords else '.*'

        result['steps'].append({
            'action': 'build_pattern',
            'pattern': search_pattern
        })

        # 検索実行（ドライラン）
        result['output'] = f"""
Would search for: {search_pattern}

Recommended command:
  grep -r "{search_pattern}" {self.project_path}

Or:
  find {self.project_path} -name "*{keywords[0] if keywords else ''}*"

Note: Running in skill execution mode (dry run).
The search command is prepared above.
"""

        result['steps'].append({
            'action': 'dry_run_complete',
            'command': f'grep -r "{search_pattern}"'
        })

        return result

    def _execute_testing(self, request: str, result: Dict) -> Dict:
        """テストタスクを実行"""
        # テストコマンドを推定
        test_commands = [
            'pytest',
            'python -m pytest',
            'python -m unittest',
            'npm test',
            'cargo test'
        ]

        # プロジェクトタイプを検出
        if (self.project_path / 'package.json').exists():
            command = 'npm test'
        elif (self.project_path / 'Cargo.toml').exists():
            command = 'cargo test'
        elif list(self.project_path.glob('test_*.py')):
            command = 'pytest'
        else:
            command = 'pytest'  # デフォルト

        result['steps'].append({
            'action': 'detect_test_framework',
            'command': command
        })

        result['output'] = f"""
Would run tests with: {command}

Recommended:
  cd {self.project_path}
  {command}

Note: Running in skill execution mode (dry run).
The test command is prepared above.
"""

        result['steps'].append({
            'action': 'dry_run_complete',
            'command': command
        })

        return result

    def _execute_modification(self, request: str, result: Dict) -> Dict:
        """ファイル修正タスクを実行"""
        # ファイル名を抽出
        filename = self._extract_filename(request)

        if not filename:
            result['output'] = "Could not determine which file to modify."
            return result

        file_path = self.project_path / filename

        result['steps'].append({
            'action': 'identify_file',
            'file': str(file_path)
        })

        if not file_path.exists():
            result['output'] = f"File does not exist: {file_path}"
            return result

        # 修正内容を推定
        modification_type = self._detect_modification_type(request)

        result['steps'].append({
            'action': 'detect_modification_type',
            'type': modification_type
        })

        result['output'] = f"""
Would modify file: {file_path}
Modification type: {modification_type}

Recommended steps:
1. Read current content
2. Apply modification ({modification_type})
3. Write updated content
4. Verify changes

Note: Running in skill execution mode (dry run).
"""

        result['steps'].append({
            'action': 'dry_run_complete',
            'file': str(file_path)
        })

        return result

    def _execute_debugging(self, request: str, result: Dict) -> Dict:
        """デバッグタスクを実行"""
        # エラータイプを抽出
        error_type = self._extract_error_type(request)

        result['steps'].append({
            'action': 'identify_error',
            'error_type': error_type or 'unknown'
        })

        # 学習した解決方法を取得
        solutions = None
        if error_type:
            solutions = self.learner.get_error_solution(error_type)

        if solutions:
            result['steps'].append({
                'action': 'retrieve_learned_solution',
                'solutions_found': len(solutions)
            })

            result['output'] = f"""
Error type: {error_type}

Learned solutions ({len(solutions)}):

{chr(10).join(f'{i+1}. {sol[:200]}...' for i, sol in enumerate(solutions[:3]))}

Recommended approach:
1. Read error message carefully
2. Check file/line mentioned
3. Apply learned solution
4. Re-run to verify fix

Note: Based on {len(solutions)} similar cases learned from Claude Code.
"""
        else:
            result['output'] = f"""
Error type: {error_type or 'unknown'}

No learned solution yet for this error.

General debugging approach:
1. Read the full error message
2. Check the file and line number
3. Review recent changes
4. Test potential fixes

Recommendation: Use full mode to learn this error solution:
  python3 -m verantyx_cli chat
"""

        result['steps'].append({
            'action': 'provide_guidance'
        })

        return result

    def _extract_filename(self, text: str) -> Optional[str]:
        """テキストからファイル名を抽出"""
        # パターン: "create file.py", "modify test.js", etc.
        patterns = [
            r'(?:create|make|write|modify|edit|update)\s+(\S+\.\w+)',
            r'file\s+(?:named|called)\s+(\S+\.\w+)',
            r'(\w+\.\w+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _detect_language(self, filename: str) -> str:
        """ファイル名から言語を検出"""
        ext = Path(filename).suffix.lower()

        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.rb': 'ruby',
            '.php': 'php',
        }

        return language_map.get(ext, 'text')

    def _get_default_template(self, language: str) -> str:
        """デフォルトのコードテンプレートを取得"""
        templates = {
            'python': '#!/usr/bin/env python3\n"""\nDescription\n"""\n\ndef main():\n    pass\n\nif __name__ == "__main__":\n    main()\n',
            'javascript': '// Description\n\nfunction main() {\n    // TODO\n}\n\nif (require.main === module) {\n    main();\n}\n',
            'rust': 'fn main() {\n    println!("Hello, world!");\n}\n',
        }

        return templates.get(language, '// TODO: Implement\n')

    def _extract_keywords(self, text: str) -> List[str]:
        """検索キーワードを抽出"""
        # "find", "search" などの後の単語を抽出
        patterns = [
            r'(?:find|search|look for|grep)\s+(?:for\s+)?["\']?(\w+)["\']?',
            r'files?\s+(?:with|containing)\s+["\']?(\w+)["\']?',
        ]

        keywords = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            keywords.extend(matches)

        # 一般的な単語をフィルタ
        stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'for', 'to', 'of'}
        keywords = [kw for kw in keywords if kw.lower() not in stop_words]

        return keywords[:5]  # 最大5個

    def _detect_modification_type(self, text: str) -> str:
        """修正タイプを検出"""
        lower = text.lower()

        if 'add' in lower or 'insert' in lower:
            return 'addition'
        elif 'remove' in lower or 'delete' in lower:
            return 'deletion'
        elif 'replace' in lower or 'change' in lower:
            return 'replacement'
        elif 'refactor' in lower:
            return 'refactoring'
        else:
            return 'general_edit'

    def _extract_error_type(self, text: str) -> Optional[str]:
        """エラータイプを抽出"""
        patterns = [
            r'(\w+Error)',
            r'(\w+Exception)',
            r'error:\s+(\w+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def get_execution_summary(self) -> Dict[str, Any]:
        """実行履歴のサマリーを取得"""
        total = len(self.execution_history)
        successful = sum(1 for ex in self.execution_history if ex['success'])

        task_types = {}
        for ex in self.execution_history:
            task_type = ex['task_type']
            task_types[task_type] = task_types.get(task_type, 0) + 1

        return {
            'total_executions': total,
            'successful': successful,
            'success_rate': successful / total if total > 0 else 0,
            'task_distribution': task_types
        }


if __name__ == "__main__":
    print("Skill Executor - Use via standalone_ai.py with skill execution enabled")
