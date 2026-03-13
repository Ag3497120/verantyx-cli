#!/usr/bin/env python3
"""
JCross Storage Processors

.jcrossファイルをデータストレージとして使うためのプロセッサ

Spatial Positioning Integration:
- データは削除せず、6次元空間内で再配置
- 品質ベースの配置（FRONT/BACK, UP/DOWN, LEFT/RIGHT）
- 空間距離による検索
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import spatial positioning components
from .jcross_interpreter import SpatialDataManager, SpatialPositionCalculator


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

        # 6次元空間配置マネージャー
        self.spatial_manager = SpatialDataManager()

        # データ読み込み後、空間的に再配置
        self._reposition_all_data()

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
            # 問題: [^}]* は最初の } で止まる
            # 解決: ブラケットカウントで正しい終了位置を見つける
            pattern = rf'AXIS {axis}\s*\{{'
            match = re.search(pattern, content)

            if match:
                start_pos = match.end()  # { の直後
                brace_count = 1
                pos = start_pos

                # 対応する閉じ括弧を見つける
                while pos < len(content) and brace_count > 0:
                    if content[pos] == '{':
                        brace_count += 1
                    elif content[pos] == '}':
                        brace_count -= 1
                    pos += 1

                if brace_count == 0:
                    axis_content = content[start_pos:pos-1]  # 閉じ括弧の直前まで
                    # 各フィールドを抽出
                    memory[axis] = self._parse_axis_data(axis_content, axis)

        return memory

    def _parse_axis_data(self, axis_content: str, axis_name: str) -> Dict[str, Any]:
        """
        軸のデータを解析（簡潔版 - トップレベルフィールドのみ）

        問題: 正規表現でフィールドを探すと、JSON内のフィールドも誤検出する
        解決: インデントレベルで判定し、トップレベルのみ抽出
        """
        data = {}
        lines = axis_content.split('\n')

        current_field = None
        current_value_lines = []

        for i, line in enumerate(lines):
            # インデントレベルをチェック（トップレベルは8スペース）
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            # トップレベルフィールド（インデント8かつ `:` を含む）
            if indent == 8 and ':' in stripped:
                # 前のフィールドを保存
                if current_field:
                    self._parse_and_store_field(data, current_field, current_value_lines)

                # 新しいフィールド
                parts = stripped.split(':', 1)
                current_field = parts[0].strip()
                value_part = parts[1].strip() if len(parts) > 1 else ''
                current_value_lines = [value_part] if value_part else []

            elif current_field:
                # 継続行: indent > 8, indent == 8 (but no ':'), or indent == 0
                # 配列の終了括弧 `]` もindent=8だが `:` がないので継続行として扱う
                if indent >= 8 or indent == 0:
                    current_value_lines.append(stripped)

        # 最後のフィールドを保存
        if current_field:
            self._parse_and_store_field(data, current_field, current_value_lines)

        return data

    def _parse_and_store_field(self, data: Dict, field_name: str, value_lines: List[str]):
        """フィールド値をパースして保存"""
        if not value_lines:
            data[field_name] = None
            return

        # 値を結合（改行を保持）
        value_str = '\n'.join(value_lines)

        # 配列の場合
        if value_str.strip().startswith('['):
            # ブラケットカウントで配列全体を抽出
            bracket_count = 0
            brace_count = 0
            in_string = False
            escape_next = False
            array_end = 0

            for i, char in enumerate(value_str):
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"':
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            array_end = i + 1
                            break
                    elif char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1

            if array_end > 0:
                array_str = value_str[:array_end]
                try:
                    data[field_name] = json.loads(array_str)
                except json.JSONDecodeError as e:
                    # JSONパースエラー時のみ警告
                    print(f"⚠️  JSON parse error for {field_name}: {str(e)[:100]}")
                    data[field_name] = []
            else:
                # 配列終了が見つからない場合
                print(f"⚠️  Could not find array end for {field_name}")
                data[field_name] = []

        # 数値の場合
        elif value_str.strip().replace('-', '').isdigit():
            data[field_name] = int(value_str.strip())

        # その他
        else:
            try:
                data[field_name] = json.loads(value_str)
            except:
                data[field_name] = value_str.strip()

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

    def log_jcross_prompt(self, jcross_prompt: str):
        """JCrossプロンプトを記録"""
        # BACK軸に追加
        self.memory['BACK']['jcross_prompts'].append(jcross_prompt)

        # 自動保存
        self._save()

    def save(self):
        """保存処理（互換性のため）"""
        self._save()

    def get_cross_structure(self) -> Dict[str, Any]:
        """
        Cross構造を取得（claude_subprocess_engineとの互換性のため）

        Returns:
            Cross構造データ（self.cross_memoryと同等の形式）
        """
        # JCrossStorageEngineの内部形式をclaude_subprocess_engineの期待形式に変換
        return {
            'version': '1.0',
            'type': 'conversation',
            'created_at': datetime.now().isoformat(),
            'axes': {
                'FRONT': self.memory.get('FRONT', {}),
                'UP': self.memory.get('UP', {}),
                'DOWN': self.memory.get('DOWN', {}),
                'RIGHT': self.memory.get('RIGHT', {}),
                'LEFT': self.memory.get('LEFT', {}),
                'BACK': self.memory.get('BACK', {})
            }
        }

    @property
    def cross_structure(self) -> Dict[str, Any]:
        """
        cross_structure属性（_extract_and_convert_reasoningとの互換性のため）

        Returns:
            Cross構造データ
        """
        return self.get_cross_structure()

    def _get_timestamp(self) -> str:
        """
        現在のタイムスタンプを取得（_extract_and_convert_reasoningとの互換性のため）

        Returns:
            ISO形式のタイムスタンプ
        """
        return datetime.now().isoformat()

    def _reposition_all_data(self):
        """
        全データを6次元空間内で再配置

        重要: データは削除せず、品質に基づいて位置を変える
        - 高品質データ → FRONT, UP に配置
        - 低品質データ → BACK, DOWN に配置（削除しない）
        """
        try:
            # 空間的再配置を実行
            self.memory = self.spatial_manager.reposition_data_in_space(self.memory)
        except Exception as e:
            print(f"⚠️  Spatial repositioning failed: {e}")
            # エラーが発生しても処理を継続（元のデータを保持）

    def add_conversation_spatially(
        self,
        user_question: str,
        claude_response: str,
        timestamp: Optional[datetime] = None
    ):
        """
        新しい会話を空間的に追加

        既存データを上書きせず、品質に基づいて適切な位置に配置

        Args:
            user_question: ユーザーの質問
            claude_response: Claudeの応答
            timestamp: タイムスタンプ（省略時は現在時刻）
        """
        # 空間的に追加（削除なし、上書きなし）
        self.memory = self.spatial_manager.add_new_conversation(
            self.memory,
            user_question,
            claude_response,
            timestamp
        )

        # 自動保存
        self._save()

    def search_conversations_spatially(
        self,
        entity: str,
        intent: str = "definition",
        max_distance: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        6次元空間距離に基づいて会話を検索

        Args:
            entity: 検索実体（例: "openai", "claude max"）
            intent: 検索意図（"definition", "explanation", etc.）
            max_distance: 許容最大距離

        Returns:
            最も近い会話、見つからない場合はNone
        """
        # 全会話を集める
        all_conversations = []

        if "FRONT" in self.memory:
            if "current_conversation" in self.memory["FRONT"]:
                front_convs = self.memory["FRONT"]["current_conversation"]
                if isinstance(front_convs, list):
                    all_conversations.extend(front_convs)
            if "active_conversations" in self.memory["FRONT"]:
                all_conversations.extend(self.memory["FRONT"]["active_conversations"])

        if "BACK" in self.memory and "archived_conversations" in self.memory["BACK"]:
            all_conversations.extend(self.memory["BACK"]["archived_conversations"])

        # 空間的検索を実行
        result = self.spatial_manager.search_by_spatial_distance(
            user_question=f"{entity}とは",  # ダミー質問
            entity=entity,
            intent=intent,
            conversations=all_conversations,
            max_distance=max_distance
        )

        return result
