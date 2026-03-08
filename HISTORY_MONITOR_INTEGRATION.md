# Claude History Monitor - 統合ガイド

## 概要

Claude Codeの`~/.claude/history.jsonl`を監視して、会話をVerantyx UIに表示する。

## アーキテクチャ

```
Claude Code（独立して実行）
    ↓ 会話を記録
~/.claude/history.jsonl
    ↓ 監視（tail -f）
ClaudeHistoryMonitor
    ↓ コールバック
SimpleChatUI.add_message()
    ↓
Verantyx UI に表示
```

## メリット

1. **Claude Codeをそのまま使える** - PTY不要、Wrapperスクリプト不要
2. **確実に取得できる** - ファイルに記録されるので取りこぼしなし
3. **シンプル** - ファイル監視だけ
4. **遅延なし** - 0.1秒間隔で監視

## TODO: history.jsonlの完全な構造解析

現在の`history.jsonl`は**ユーザー入力のみ**を記録している可能性があります。
Claude応答も記録されているか確認が必要です。

### 確認方法

1. Claude Codeで会話する
2. `tail -20 ~/.claude/history.jsonl` で最新エントリを確認
3. ユーザー入力とClaude応答の両方があるか確認

### もしClaude応答が別ファイルの場合

他のファイルも確認：
- `~/.claude/debug/` - デバッグログ
- `~/.claude/session-env/` - セッション情報

## 統合手順

### 1. terminal_ui.pyに統合

```python
from ..engine.claude_history_monitor import ClaudeHistoryMonitor

def start_chat_mode(project_path: Path, llm_provider: str = "claude"):
    # ... 既存のコード ...

    # History monitor起動
    def on_claude_message(msg: dict):
        if msg['type'] == 'assistant':
            ui.add_message('assistant', msg['content'])

    monitor = ClaudeHistoryMonitor(on_new_message=on_claude_message)
    monitor.start()

    # ... UI起動 ...
```

### 2. Claude Codeを別タブで起動

```python
# Claude Codeを普通に起動（タブ不要、ユーザーが手動で起動）
print("📌 別のターミナルでClaude Codeを起動してください:")
print("   $ claude")
print()
```

### 3. Verantyx UIでClaudeの応答を表示

自動的に表示されます！

## 制限事項

- Claude Code v2.0.55 のhistory.jsonl構造に依存
- 将来のバージョンで構造が変わる可能性あり
- ユーザー入力のみで応答がない場合は、別のアプローチが必要

## 次のステップ

1. history.jsonlの完全な構造を解析
2. Claude応答も含まれているか確認
3. 含まれていない場合、debug/ログから取得
4. または、画面キャプチャアプローチにフォールバック
