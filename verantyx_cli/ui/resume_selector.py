#!/usr/bin/env python3
"""
Resume Selector - Claude Code の会話履歴から再開を選択

claude --resume の機能を統合し、矢印キーで選択できるようにする
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .interactive_selector import select_with_index


def get_claude_conversations_dir() -> Path:
    """Claude Codeの会話履歴ディレクトリを取得"""
    # macOS/Linux: ~/.claude/conversations
    # Windows: %USERPROFILE%/.claude/conversations
    home = Path.home()
    conversations_dir = home / '.claude' / 'conversations'

    if not conversations_dir.exists():
        # 代替パス
        alt_dir = home / '.config' / 'claude-code' / 'conversations'
        if alt_dir.exists():
            return alt_dir

    return conversations_dir


def list_claude_conversations() -> List[Dict]:
    """
    Claude Codeの会話履歴を取得

    Returns:
        会話のリスト [{"id": "...", "title": "...", "timestamp": ..., "path": ...}]
    """
    conversations_dir = get_claude_conversations_dir()

    if not conversations_dir.exists():
        return []

    conversations = []

    # 各会話フォルダを走査
    for conv_dir in conversations_dir.iterdir():
        if not conv_dir.is_dir():
            continue

        # メタデータファイルを探す
        meta_file = conv_dir / 'metadata.json'
        if not meta_file.exists():
            # 代替: conversation.json
            meta_file = conv_dir / 'conversation.json'

        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 会話情報を抽出
                conv_id = conv_dir.name
                title = data.get('title', conv_id[:20])
                timestamp = data.get('created_at', data.get('timestamp', 0))

                # タイムスタンプを日時に変換
                if isinstance(timestamp, (int, float)):
                    dt = datetime.fromtimestamp(timestamp)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    date_str = "Unknown date"

                conversations.append({
                    'id': conv_id,
                    'title': title,
                    'timestamp': timestamp,
                    'date_str': date_str,
                    'path': conv_dir
                })

            except Exception as e:
                # パースエラーは無視
                continue

    # タイムスタンプでソート（新しい順）
    conversations.sort(key=lambda x: x['timestamp'], reverse=True)

    return conversations


def select_conversation_to_resume() -> Optional[str]:
    """
    矢印キーで会話を選択して再開

    Returns:
        選択された会話ID、キャンセル時はNone
    """
    print("\n" + "=" * 70)
    print("  📝 Resume Claude Code Conversation")
    print("=" * 70)
    print()
    print("  Loading conversation history...")
    print()

    conversations = list_claude_conversations()

    if not conversations:
        print("  ⚠️  No conversation history found")
        print()
        print(f"  Searched in: {get_claude_conversations_dir()}")
        print()
        return None

    print(f"  ✅ Found {len(conversations)} conversation(s)")
    print()

    # 選択肢を構築
    options = []
    descriptions = []

    for conv in conversations:
        # タイトルを短縮（50文字まで）
        title = conv['title']
        if len(title) > 50:
            title = title[:47] + "..."

        options.append(f"{title}")
        descriptions.append(f"{conv['date_str']} • ID: {conv['id'][:8]}")

    # キャンセルオプション
    options.append("🚫 Cancel (start new conversation)")
    descriptions.append("Return to main menu")

    # 選択
    selected_idx = select_with_index(
        "Select a conversation to resume:",
        options,
        descriptions
    )

    if selected_idx is None or selected_idx == len(conversations):
        # キャンセルまたは最後のオプション（新規会話）
        return None

    selected_conv = conversations[selected_idx]

    print()
    print(f"  ✅ Selected: {selected_conv['title']}")
    print()

    return selected_conv['id']


def resume_claude_conversation(conversation_id: str, project_path: Path) -> bool:
    """
    claude --resume で会話を再開

    Args:
        conversation_id: 会話ID
        project_path: プロジェクトディレクトリ

    Returns:
        成功したかどうか
    """
    try:
        print(f"  🔄 Resuming conversation {conversation_id[:8]}...")
        print()

        # claude --resume <id> を実行
        result = subprocess.run(
            ['claude', '--resume', conversation_id],
            cwd=project_path,
            check=False
        )

        return result.returncode == 0

    except FileNotFoundError:
        print("  ❌ Error: 'claude' command not found")
        print()
        print("  Please install Claude Code:")
        print("    npm install -g @anthropic-ai/claude-code")
        print()
        return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        print()
        return False


if __name__ == "__main__":
    # テスト
    print("🧪 Resume Selector Test\n")

    conv_id = select_conversation_to_resume()

    if conv_id:
        print(f"Would resume conversation: {conv_id}")
    else:
        print("No conversation selected")
