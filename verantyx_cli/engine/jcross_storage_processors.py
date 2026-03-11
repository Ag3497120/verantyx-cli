#!/usr/bin/env python3
"""
JCross Storage Processors

.jcrossファイルをデータストレージとして使うためのプロセッサ
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class JCrossStorageEngine:
    """
    .jcrossファイルをデータベースとして使用

    特徴:
    - コードとデータを統合
    - CROSS構造をそのまま保存
    - 人間が読める形式
    """

    def __init__(self, jcross_file: Path):
        """
        Args:
            jcross_file: .jcrossファイルのパス
        """
        self.jcross_file = jcross_file
        self.memory = self._load_or_initialize()

    def _load_or_initialize(self) -> Dict[str, Any]:
        """
        .jcrossファイルを読み込むか初期化

        .jcrossファイルからCROSS構造のデータ部分を抽出
        """
        if not self.jcross_file.exists():
            return self._initialize_structure()

        try:
            content = self.jcross_file.read_text(encoding='utf-8')
            return self._parse_jcross_data(content)
        except Exception as e:
            print(f"⚠️  Failed to load .jcross file: {e}")
            return self._initialize_structure()

    def _initialize_structure(self) -> Dict[str, Any]:
        """初期Cross構造"""
        return {
            'UP': {
                'user_inputs': [],
                'total_messages': 0
            },
            'DOWN': {
                'claude_responses': []
            },
            'LEFT': {
                'timestamps': []
            },
            'RIGHT': {
                'tool_calls': []
            },
            'FRONT': {
                'current_conversation': []
            },
            'BACK': {
                'raw_interactions': [],
                'jcross_prompts': [],
                'jcross_programs': []
            }
        }

    def _parse_jcross_data(self, content: str) -> Dict[str, Any]:
        """
        .jcrossファイルからデータ部分を抽出

        AXIS UP { ... } のような定義を解析
        """
        memory = self._initialize_structure()

        # 各軸のデータを抽出
        axes = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'FRONT', 'BACK']

        for axis in axes:
            # AXIS UP { ... } のパターンを検索
            pattern = rf'AXIS {axis}\s*\{{([^}}]*)\}}'
            match = re.search(pattern, content, re.DOTALL)

            if match:
                axis_content = match.group(1)
                # 各フィールドを抽出
                memory[axis] = self._parse_axis_data(axis_content, axis)

        return memory

    def _parse_axis_data(self, axis_content: str, axis_name: str) -> Dict[str, Any]:
        """
        軸のデータを解析

        例:
            user_inputs: ["hello", "world"]
            total_messages: 2
        """
        data = {}

        # フィールド: 値 のパターンを検索
        # 配列パターン: field: [...]
        array_pattern = r'(\w+):\s*\[(.*?)\]'
        for match in re.finditer(array_pattern, axis_content, re.DOTALL):
            field_name = match.group(1)
            array_content = match.group(2).strip()

            if not array_content:
                data[field_name] = []
            else:
                # 配列要素を解析（簡易的なJSON解析）
                try:
                    # JSON配列として解析を試みる
                    data[field_name] = json.loads(f'[{array_content}]')
                except:
                    # 失敗したら空配列
                    data[field_name] = []

        # 数値パターン: field: 123
        number_pattern = r'(\w+):\s*(\d+)'
        for match in re.finditer(number_pattern, axis_content):
            field_name = match.group(1)
            if field_name not in data:  # 配列として既に解析されていない場合のみ
                data[field_name] = int(match.group(2))

        return data

    def _save(self):
        """
        .jcrossファイルに保存

        CROSS構造全体を.jcrossフォーマットで書き込み
        """
        try:
            # ディレクトリが存在しない場合は作成
            self.jcross_file.parent.mkdir(parents=True, exist_ok=True)

            # .jcross形式で出力
            jcross_content = self._generate_jcross_content()

            self.jcross_file.write_text(jcross_content, encoding='utf-8')

        except Exception as e:
            print(f"⚠️  Failed to save .jcross file: {e}")

    def _generate_jcross_content(self) -> str:
        """
        Cross構造から.jcross形式のコンテンツを生成
        """
        content = '''"""
Conversation Memory - Cross構造によるデータストレージ

.jcrossファイル自体がデータベース
コードとデータを統合
"""

CROSS conversation_memory {
    // 6軸Cross構造

'''

        # 各軸のデータを出力
        for axis_name, axis_data in self.memory.items():
            content += f'    AXIS {axis_name} {{\n'

            for field_name, field_value in axis_data.items():
                if isinstance(field_value, list):
                    # 配列はJSON形式で
                    json_value = json.dumps(field_value, ensure_ascii=False, indent=8)
                    # インデントを調整
                    json_value = json_value.replace('\n', '\n        ')
                    content += f'        {field_name}: {json_value}\n'
                else:
                    # 数値などはそのまま
                    content += f'        {field_name}: {field_value}\n'

            content += '    }\n\n'

        # 関数定義は省略（テンプレートから読み込む場合は別途追加）
        content += '}\n'

        return content

    def log_user_input(self, user_input: str) -> Dict[str, int]:
        """ユーザー入力を記録"""
        timestamp = datetime.now().isoformat()

        # UP軸に追加
        self.memory['UP']['user_inputs'].append(user_input)
        self.memory['UP']['total_messages'] += 1

        # LEFT軸にタイムスタンプ
        self.memory['LEFT']['timestamps'].append(timestamp)

        # FRONT軸に会話として追加
        conversation_item = {
            'role': 'user',
            'content': user_input,
            'timestamp': timestamp
        }
        self.memory['FRONT']['current_conversation'].append(conversation_item)

        # 自動保存
        self._save()

        return {
            'total_inputs': self.memory['UP']['total_messages'],
            'total_responses': len(self.memory['DOWN']['claude_responses'])
        }

    def log_claude_response(self, claude_response: str) -> Dict[str, int]:
        """Claude応答を記録"""
        timestamp = datetime.now().isoformat()

        # DOWN軸に追加
        self.memory['DOWN']['claude_responses'].append(claude_response)

        # LEFT軸にタイムスタンプ
        self.memory['LEFT']['timestamps'].append(timestamp)

        # FRONT軸に会話として追加
        conversation_item = {
            'role': 'assistant',
            'content': claude_response,
            'timestamp': timestamp
        }
        self.memory['FRONT']['current_conversation'].append(conversation_item)

        # 自動保存
        self._save()

        return {
            'total_inputs': self.memory['UP']['total_messages'],
            'total_responses': len(self.memory['DOWN']['claude_responses'])
        }

    def log_tool_call(self, tool_name: str, tool_params: Dict, tool_result: Any):
        """ツール呼び出しを記録"""
        timestamp = datetime.now().isoformat()

        tool_call = {
            'tool': tool_name,
            'params': tool_params,
            'result': str(tool_result)[:500],
            'timestamp': timestamp
        }

        # RIGHT軸に追加
        self.memory['RIGHT']['tool_calls'].append(tool_call)

        # 自動保存
        self._save()

    def get_statistics(self) -> Dict[str, int]:
        """統計情報を取得"""
        return {
            'total_inputs': self.memory['UP']['total_messages'],
            'total_responses': len(self.memory['DOWN']['claude_responses']),
            'total_tool_calls': len(self.memory['RIGHT']['tool_calls']),
            'total_conversation_items': len(self.memory['FRONT']['current_conversation'])
        }

    def get_conversation_history(self) -> List[Dict]:
        """会話履歴を取得"""
        return self.memory['FRONT']['current_conversation']

    def get_all_responses(self) -> List[str]:
        """Claude応答を全て取得"""
        return self.memory['DOWN']['claude_responses']

    def get_recent_responses(self, n: int) -> List[str]:
        """最新のN件の応答を取得"""
        responses = self.memory['DOWN']['claude_responses']
        total = len(responses)

        if total <= n:
            return responses

        return responses[-n:]
