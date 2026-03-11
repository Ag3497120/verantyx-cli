#!/usr/bin/env python3
"""
Cross Conversation Logger - JCrossベースの会話記録システム

全ての会話内容をCross構造（6軸）に記録：
- FRONT: 現在の会話
- UP: ユーザー入力
- DOWN: Claude応答
- RIGHT: ツール呼び出し
- LEFT: タイムスタンプ
- BACK: 生の相互作用、JCrossプロンプト
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class CrossConversationLogger:
    """
    JCrossベースのCross構造会話記録システム

    conversation_logger.jcrossを実行して会話を6軸に記録
    """

    def __init__(self, cross_file: Path):
        """
        Args:
            cross_file: Cross構造ファイルのパス
        """
        self.cross_file = cross_file
        self.cross_structure = self._load_or_initialize()

    def _load_or_initialize(self) -> Dict:
        """Cross構造を読み込むか初期化"""
        if self.cross_file.exists():
            try:
                with open(self.cross_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load Cross structure: {e}")
                return self._initialize_structure()
        else:
            return self._initialize_structure()

    def _initialize_structure(self) -> Dict:
        """Cross構造を初期化（JCrossロジックと同等）"""
        return {
            'axes': {
                'FRONT': {
                    'current_conversation': []
                },
                'UP': {
                    'user_inputs': [],
                    'total_messages': 0
                },
                'DOWN': {
                    'claude_responses': []
                },
                'RIGHT': {
                    'tool_calls': []
                },
                'LEFT': {
                    'timestamps': []
                },
                'BACK': {
                    'raw_interactions': [],
                    'jcross_prompts': []
                }
            }
        }

    def log_user_input(self, user_input: str) -> None:
        """
        ユーザー入力を記録

        Args:
            user_input: ユーザーの入力テキスト
        """
        timestamp = datetime.now().isoformat()

        # UP軸に追加
        self.cross_structure['axes']['UP']['user_inputs'].append(user_input)
        self.cross_structure['axes']['UP']['total_messages'] += 1

        # LEFT軸にタイムスタンプ追加
        self.cross_structure['axes']['LEFT']['timestamps'].append(timestamp)

        # FRONT軸に会話として追加
        conversation_item = {
            'role': 'user',
            'content': user_input,
            'timestamp': timestamp
        }
        self.cross_structure['axes']['FRONT']['current_conversation'].append(conversation_item)

    def log_claude_response(self, claude_response: str) -> None:
        """
        Claude応答を記録

        Args:
            claude_response: Claudeの応答テキスト
        """
        timestamp = datetime.now().isoformat()

        # DOWN軸に追加
        self.cross_structure['axes']['DOWN']['claude_responses'].append(claude_response)

        # LEFT軸にタイムスタンプ追加
        self.cross_structure['axes']['LEFT']['timestamps'].append(timestamp)

        # FRONT軸に会話として追加
        conversation_item = {
            'role': 'assistant',
            'content': claude_response,
            'timestamp': timestamp
        }
        self.cross_structure['axes']['FRONT']['current_conversation'].append(conversation_item)

    def log_tool_call(self, tool_name: str, tool_params: Dict, tool_result: Any) -> None:
        """
        ツール呼び出しを記録

        Args:
            tool_name: ツール名
            tool_params: ツールパラメータ
            tool_result: ツール実行結果
        """
        timestamp = datetime.now().isoformat()

        # RIGHT軸に追加
        tool_call = {
            'tool': tool_name,
            'params': tool_params,
            'result': str(tool_result)[:500],  # 結果は最初の500文字のみ
            'timestamp': timestamp
        }
        self.cross_structure['axes']['RIGHT']['tool_calls'].append(tool_call)

    def log_jcross_prompt(self, jcross_prompt: str) -> None:
        """
        JCrossプロンプトを記録

        Args:
            jcross_prompt: JCrossプロンプト
        """
        # BACK軸に追加
        self.cross_structure['axes']['BACK']['jcross_prompts'].append(jcross_prompt)

    def log_raw_interaction(self, raw_interaction: str) -> None:
        """
        生の相互作用を記録

        Args:
            raw_interaction: 生の相互作用テキスト
        """
        timestamp = datetime.now().isoformat()

        # BACK軸に追加
        self.cross_structure['axes']['BACK']['raw_interactions'].append({
            'content': raw_interaction,
            'timestamp': timestamp
        })

    def log_conversation_turn(self, user_input: str, claude_response: str) -> None:
        """
        1回の会話ターン（ユーザー入力 → Claude応答）を記録

        Args:
            user_input: ユーザー入力
            claude_response: Claude応答
        """
        self.log_user_input(user_input)
        self.log_claude_response(claude_response)

    def save(self) -> None:
        """Cross構造をファイルに保存"""
        try:
            # ディレクトリが存在しない場合は作成
            self.cross_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.cross_file, 'w', encoding='utf-8') as f:
                json.dump(self.cross_structure, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Failed to save Cross structure: {e}")

    def get_statistics(self) -> Dict[str, int]:
        """統計情報を取得"""
        axes = self.cross_structure.get('axes', {})

        return {
            'total_inputs': axes.get('UP', {}).get('total_messages', 0),
            'total_responses': len(axes.get('DOWN', {}).get('claude_responses', [])),
            'total_tools': len(axes.get('RIGHT', {}).get('tool_calls', [])),
            'total_jcross': len(axes.get('BACK', {}).get('jcross_prompts', [])),
            'conversation_length': len(axes.get('FRONT', {}).get('current_conversation', []))
        }

    def get_cross_structure(self) -> Dict:
        """Cross構造全体を取得"""
        return self.cross_structure


def test_cross_logger():
    """Cross会話記録のテスト"""
    print("\n" + "=" * 70)
    print("  📝 Cross Conversation Logger Test")
    print("=" * 70)
    print()

    test_file = Path(".verantyx/test_conversation.cross.json")

    logger = CrossConversationLogger(test_file)

    print("✅ Logger initialized")
    print()

    # テスト会話を記録
    logger.log_user_input("What is Cross structure?")
    logger.log_claude_response("Cross structure is a 6-dimensional knowledge representation...")

    logger.log_user_input("How do I use JCross?")
    logger.log_claude_response("JCross is a Japanese-based domain-specific language...")

    # ツール呼び出しを記録
    logger.log_tool_call("read", {"file": "test.py"}, "file content...")

    # 保存
    logger.save()

    # 統計表示
    stats = logger.get_statistics()
    print("📊 Statistics:")
    print(f"   - Total inputs: {stats['total_inputs']}")
    print(f"   - Total responses: {stats['total_responses']}")
    print(f"   - Total tool calls: {stats['total_tools']}")
    print(f"   - Conversation length: {stats['conversation_length']}")
    print()

    print(f"✅ Cross structure saved to: {test_file}")
    print()


if __name__ == "__main__":
    test_cross_logger()
