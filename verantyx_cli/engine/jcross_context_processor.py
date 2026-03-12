#!/usr/bin/env python3
"""
.jcross文脈プロセッサ - context_understanding.jcrossを実行

機能:
1. .jcross定義ファイルから操作仕様を読み込み
2. 操作コマンドを解析して実行
3. 文脈推論パターンを適用
4. 実行履歴を.jcross形式で保存
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class JCrossContextProcessor:
    """
    .jcross形式の文脈理解定義を処理

    .jcrossファイルはコードでありデータでもある：
    - OPERATION定義 = 操作コマンドの仕様（コード）
    - AXIS OPERATION_HISTORY = 実行履歴（データ）
    - PATTERN = 推論パターン（コード）
    """

    def __init__(self, jcross_definition_file: Path):
        """
        Args:
            jcross_definition_file: context_understanding.jcross
        """
        self.definition_file = jcross_definition_file

        # 操作定義
        self.operations = {}  # {operation_name: {signature, params, logic}}

        # パターン定義
        self.patterns = {}  # {pattern_name: {trigger, sequence}}

        # 実行履歴
        self.execution_history = []

        # 焦点スタック
        self.focus_stack = []

        # QAペア
        self.qa_pairs = []

        # 依存関係グラフ
        self.dependency_graph = {}

        # 定義を読み込み
        self._load_definitions()

    def _load_definitions(self):
        """
        .jcross定義ファイルを読み込む

        【重要】.jcrossはPythonコードではなく宣言的定義
        ここでは簡易パーサーで読み込む
        """
        if not self.definition_file.exists():
            print(f"⚠️  Definition file not found: {self.definition_file}")
            return

        # 操作定義を登録（ハードコード版）
        self.operations = {
            '参照解決': {
                'signature': '参照解決 代名詞={pronoun} 参照先={referent} コンテキスト={ctx} 信頼度={confidence}',
                'params': ['代名詞', '参照先', 'コンテキスト', '信頼度'],
                'handler': self._execute_pronoun_resolution
            },
            'QA対応': {
                'signature': 'QA対応 質問ID={q_id} 質問内容={question} 応答ID={a_id} 焦点実体={entity} コンテキスト={ctx}',
                'params': ['質問ID', '質問内容', '応答ID', '焦点実体', 'コンテキスト'],
                'handler': self._execute_qa_correspondence
            },
            '依存関係': {
                'signature': '依存関係 質問ID={q_id} 依存先={dep_id} 依存タイプ={type} 理由={reason}',
                'params': ['質問ID', '依存先', '依存タイプ', '理由'],
                'handler': self._execute_dependency
            },
            '焦点更新': {
                'signature': '焦点更新 実体={entity} コンテキスト={ctx} 優先度={priority}',
                'params': ['実体', 'コンテキスト', '優先度'],
                'handler': self._execute_focus_update
            }
        }

        # パターン定義を登録
        self.patterns = {
            'pronoun_resolution_flow': {
                'trigger_pronouns': ['それ', 'これ', 'あれ', 'その', 'この', 'あの'],
                'operations': [
                    '参照解決 代名詞={pronoun} 参照先={referent} コンテキスト={prev_ctx}',
                    'QA対応 質問ID={qa_id} 質問内容={question} 応答ID={a_id} 焦点実体={entity} コンテキスト={ctx}',
                    '依存関係 質問ID={qa_id} 依存先={prev_qa} 依存タイプ=追加質問 理由=代名詞{pronoun}使用'
                ]
            },
            'new_topic_flow': {
                'trigger_condition': 'no_pronoun',
                'operations': [
                    'QA対応 質問ID={qa_id} 質問内容={question} 応答ID={a_id} 焦点実体={entity} コンテキスト={ctx}',
                    '焦点更新 実体={entity} コンテキスト={ctx} 優先度=8'
                ]
            }
        }

    def execute_operation(self, command: str, position: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        .jcross操作コマンドを実行

        Args:
            command: "参照解決 代名詞=それ 参照先=りんご..."
            position: Cross空間上の位置

        Returns:
            実行結果
        """
        # コマンドをパース
        parsed = self._parse_command(command)

        if not parsed:
            return {'error': 'Failed to parse command'}

        operation_type = parsed['operation']
        params = parsed['params']

        # 操作定義を取得
        if operation_type not in self.operations:
            return {'error': f'Unknown operation: {operation_type}'}

        operation_def = self.operations[operation_type]

        # ハンドラーを実行
        handler = operation_def.get('handler')

        if not handler:
            return {'error': 'No handler defined'}

        result = handler(params)

        # 実行履歴に記録
        self.execution_history.append({
            'id': f"op_{len(self.execution_history)}",
            'type': operation_type,
            'command': command,
            'timestamp': datetime.now().isoformat(),
            'position': position or [0.5] * 6,
            'result': result
        })

        return result

    def _parse_command(self, command: str) -> Optional[Dict]:
        """
        操作コマンドをパース

        例: "参照解決 代名詞=それ 参照先=りんご コンテキスト=ctx_0"
        → {operation: '参照解決', params: {...}}
        """
        parts = command.split(maxsplit=1)

        if len(parts) < 2:
            return None

        operation = parts[0]
        params_str = parts[1]

        # パラメータを抽出
        params = {}
        param_pattern = r'(\S+?)=(\S+)'
        matches = re.findall(param_pattern, params_str)

        for key, value in matches:
            params[key] = value

        return {
            'operation': operation,
            'params': params
        }

    def _execute_pronoun_resolution(self, params: Dict) -> Dict:
        """参照解決を実行"""
        pronoun = params.get('代名詞')
        referent = params.get('参照先')
        context = params.get('コンテキスト')
        confidence = float(params.get('信頼度', 1.0))

        result = {
            'action': 'pronoun_resolved',
            'pronoun': pronoun,
            'referent': referent,
            'source_context': context,
            'confidence': confidence
        }

        return result

    def _execute_qa_correspondence(self, params: Dict) -> Dict:
        """QA対応を実行"""
        qa_id = params.get('質問ID')
        question = params.get('質問内容')
        answer_id = params.get('応答ID')
        focus_entity = params.get('焦点実体')
        context = params.get('コンテキスト')

        qa_pair = {
            'question_id': qa_id,
            'question': question,
            'answer_id': answer_id,
            'focus_entity': focus_entity,
            'context_id': context,
            'timestamp': datetime.now().isoformat()
        }

        self.qa_pairs.append(qa_pair)

        return {
            'action': 'qa_recorded',
            'qa_id': qa_id,
            'focus_entity': focus_entity
        }

    def _execute_dependency(self, params: Dict) -> Dict:
        """依存関係を実行"""
        qa_id = params.get('質問ID')
        depends_on = params.get('依存先')
        dep_type = params.get('依存タイプ')
        reason = params.get('理由', '')

        self.dependency_graph[qa_id] = {
            'depends_on': depends_on,
            'type': dep_type,
            'reason': reason
        }

        return {
            'action': 'dependency_recorded',
            'from': qa_id,
            'to': depends_on,
            'type': dep_type
        }

    def _execute_focus_update(self, params: Dict) -> Dict:
        """焦点更新を実行"""
        entity = params.get('実体')
        context = params.get('コンテキスト')
        priority = int(params.get('優先度', 5))

        # 既存の同じ実体を削除
        self.focus_stack = [f for f in self.focus_stack if f['entity'] != entity]

        # 新しい焦点を追加
        self.focus_stack.append({
            'entity': entity,
            'context_id': context,
            'priority': priority,
            'timestamp': datetime.now().isoformat()
        })

        # 最大5つまで
        if len(self.focus_stack) > 5:
            self.focus_stack.pop(0)

        return {
            'action': 'focus_updated',
            'entity': entity,
            'stack_size': len(self.focus_stack)
        }

    def apply_pattern(self, pattern_name: str, context: Dict) -> List[str]:
        """
        推論パターンを適用

        Args:
            pattern_name: 'pronoun_resolution_flow' など
            context: パターン実行に必要な変数

        Returns:
            生成された操作コマンドのリスト
        """
        if pattern_name not in self.patterns:
            return []

        pattern = self.patterns[pattern_name]
        operation_templates = pattern.get('operations', [])

        # テンプレートに変数を埋め込む
        commands = []
        for template in operation_templates:
            command = template
            for key, value in context.items():
                command = command.replace(f"{{{key}}}", str(value))
            commands.append(command)

        return commands

    def export_to_jcross(self, output_file: Path):
        """
        実行履歴を.jcross形式で出力

        【重要】.jcrossはコードでありデータでもある
        実行履歴も.jcross形式で保存される
        """
        lines = []

        lines.append('"""')
        lines.append('文脈理解実行履歴 - 自動生成')
        lines.append(f'生成日時: {datetime.now().isoformat()}')
        lines.append(f'総操作数: {len(self.execution_history)}')
        lines.append('"""')
        lines.append('')
        lines.append('CROSS context_execution_history {')
        lines.append('')

        # 操作履歴
        lines.append('    AXIS OPERATION_HISTORY {')
        lines.append('        operations: [')
        for op in self.execution_history:
            lines.append('            {')
            lines.append(f'                id: "{op["id"]}",')
            lines.append(f'                type: "{op["type"]}",')
            lines.append(f'                command: "{op["command"]}",')
            lines.append(f'                timestamp: "{op["timestamp"]}",')
            lines.append(f'                position: {op["position"]}')
            lines.append('            },')
        lines.append('        ]')
        lines.append('    }')
        lines.append('')

        # QAペア
        lines.append('    AXIS QA_PAIRS {')
        lines.append('        pairs: [')
        for qa in self.qa_pairs:
            lines.append('            {')
            lines.append(f'                question_id: "{qa["question_id"]}",')
            lines.append(f'                question: "{qa["question"]}",')
            lines.append(f'                focus_entity: "{qa["focus_entity"]}",')
            lines.append(f'                context_id: "{qa["context_id"]}"')
            lines.append('            },')
        lines.append('        ]')
        lines.append('    }')
        lines.append('')

        # 焦点スタック
        lines.append('    AXIS FOCUS_STACK {')
        lines.append('        entities: [')
        for focus in self.focus_stack:
            lines.append(f'            {{entity: "{focus["entity"]}", '
                        f'context: "{focus["context_id"]}"}},')
        lines.append('        ]')
        lines.append('    }')
        lines.append('')

        # 依存関係
        lines.append('    AXIS DEPENDENCY_GRAPH {')
        lines.append('        edges: [')
        for qa_id, dep in self.dependency_graph.items():
            lines.append(f'            {{from: "{qa_id}", '
                        f'to: "{dep["depends_on"]}", '
                        f'type: "{dep["type"]}"}},')
        lines.append('        ]')
        lines.append('    }')
        lines.append('')

        lines.append('}')

        # ファイルに書き込み
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'total_operations': len(self.execution_history),
            'total_qa_pairs': len(self.qa_pairs),
            'focus_stack_size': len(self.focus_stack),
            'total_dependencies': len(self.dependency_graph),
            'current_focus': self.focus_stack[-1]['entity'] if self.focus_stack else None
        }
