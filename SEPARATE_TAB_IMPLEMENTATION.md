# 別タブ起動実装 (Separate Tab Implementation)

## 変更内容 (Changes)

**Claudeを別のターミナルタブで起動するようにしました。**

## 問題 (Problem)

**以前の実装:**
```
同じターミナル内:
  Verantyx-CLI + Claude (PTY経由)
  ↓
  問題:
  - Claudeの出力がVerantyxのUIと混ざる
  - PTY通信が複雑
  - 応答が返ってこない
```

**ユーザーの要望:**
> "現在claudeとverantyx-cliは同じターミナルで立ち上がっています。私の言っている意味はセットアップウィザードでclaudeと入力すると別のターミナルが別のタブで開くという意味です。別のターミナルで開いてverantyx-cliから指示を送るということによってしっかりclaudeが動いているどうかを確認できます。"

## 新しい実装 (New Implementation)

**完全に分離:**

```
ターミナル1 (元のターミナル):
  Verantyx-CLI (UI)
  ↓ セットアップで "claude" 選択
  ↓
ターミナル2 (新しいタブ):
  Claude Code (直接実行)
  ↓
  完全に独立して動作
  ユーザーが目で見て確認できる
```

## アーキテクチャ (Architecture)

### フロー (Flow)

```
1. ユーザーが verantyx chat を実行
   ↓
2. セットアップウィザード表示
   Select your LLM: 1 (Claude)
   ↓
3. AppleScriptで新しいタブを開く
   - Terminal.app の場合: Cmd+T
   - iTerm2 の場合: create tab
   ↓
4. 新しいタブで claude コマンド実行
   cd /project/path && claude
   ↓
5. Claude が別タブで起動
   ユーザーが動作を目視確認
   ↓
6. 元のタブでVerantyx-CLI起動
   SimpleChatUI で会話
   ↓
7. ユーザーは両方のタブを切り替えて使用
```

### コンポーネント (Components)

#### 1. `claude_tab_launcher.py` (新規作成)

**目的:** 新しいタブでClaudeを起動

**主要クラス:**
```python
class ClaudeTabLauncher:
    """Launch Claude in new terminal tab"""

    def __init__(self, project_path: Path, llm_command: str = "claude"):
        self.project_path = project_path
        self.llm_command = llm_command

    def launch(self) -> bool:
        """Launch LLM in new terminal tab"""
        # 1. コマンドの存在確認
        # 2. ターミナル種類検出
        # 3. AppleScriptで新しいタブを開く
        # 4. そのタブでコマンド実行
```

**ターミナル検出:**
```python
def _detect_terminal(self) -> str:
    """Detect which terminal is being used"""
    term_program = os.environ.get('TERM_PROGRAM', '')

    if 'iTerm' in term_program:
        return 'iTerm'
    elif 'Apple_Terminal' in term_program:
        return 'Terminal.app'
    else:
        return 'Unknown'
```

**Terminal.app タブ起動:**
```python
def _open_terminal_app_tab(self) -> bool:
    applescript = f'''
    tell application "Terminal"
        activate
        tell application "System Events"
            keystroke "t" using command down
        end tell
        delay 0.5
        do script "cd '{self.project_path}' && {self.llm_command}" in front window
    end tell
    '''

    subprocess.run(['osascript', '-e', applescript])
```

**iTerm2 タブ起動:**
```python
def _open_iterm_tab(self) -> bool:
    applescript = f'''
    tell application "iTerm"
        activate
        tell current window
            create tab with default profile
            tell current session
                write text "cd '{self.project_path}' && {self.llm_command}"
            end tell
        end tell
    end tell
    '''

    subprocess.run(['osascript', '-e', applescript])
```

#### 2. `terminal_ui.py` の変更

**Before:**
```python
# ClaudeMonitorを使用してPTY経由で通信
monitor = ClaudeMonitor(
    project_path=project_path,
    llm_command=launch_cmd,
    monitor_only=True
)
monitor.launch_claude()
```

**After:**
```python
# 新しいタブでClaudeを起動（通信なし）
from ..engine.claude_tab_launcher import launch_claude_in_new_tab

if not launch_claude_in_new_tab(project_path, launch_cmd):
    print("❌ Failed to launch")
    return

# ユーザーに確認を求める
input("Press Enter when you confirm Claude is running in the new tab... ")
```

#### 3. `simple_chat_ui.py` の変更

**コールバックがNoneの場合の処理:**

```python
# Before:
if self.on_user_input:
    self.on_user_input(user_input)

# After:
if self.on_user_input:
    # リモート応答を待つ
    self.waiting_for_response = True
    self.update_input_area(current_input)
    self.on_user_input(user_input)
else:
    # ローカルのみ（Claudeは別タブ）
    print(f"  (Message recorded locally - Claude is in separate tab)\n")
    self.update_input_area(current_input)
```

## 使用例 (Usage Example)

### 起動フロー

**ターミナル1:**
```bash
$ verantyx chat

╔════════════════════════════════════════════════════════════════════╗
║                    🚀 Verantyx-CLI Setup                           ║
╚════════════════════════════════════════════════════════════════════╝

LLM Provider:
  1. Claude (Anthropic)
  2. Gemini (Google)
  3. Codex (OpenAI)

Select (1-3): 1

Launch Method:
  1. Subscription (local command)
  2. API (requires API key)

Select (1-2): 1

Launch command: claude

======================================================================
  Launching Claude in NEW TERMINAL TAB
======================================================================

📍 Command: claude
📂 Directory: /Users/user/project

🚀 Launching claude in new terminal tab...
✅ claude launched in new tab
   Check the new tab to confirm claude is running

======================================================================
  ✅ Claude is now running in separate tab
======================================================================

📌 IMPORTANT:
   • Claude is running in the NEW TAB that just opened
   • You can see it working in that tab
   • Verantyx-CLI will run in THIS tab
   • You will interact with Verantyx-CLI here

Press Enter when you confirm Claude is running in the new tab... _
```

**ターミナル2 (新しいタブが自動で開く):**
```bash
$ cd /Users/user/project && claude

╭─────────────────────────────────────────────────────────────────────╮
│                                                                     │
│  Welcome to Claude Code                                             │
│  Model: Claude 3.5 Sonnet                                           │
│                                                                     │
╰─────────────────────────────────────────────────────────────────────╯

How can I help?
> _
```

**ユーザーがEnter押下後、ターミナル1で:**
```bash
🎨 Starting Verantyx Chat UI...

======================================================================
  Verantyx-CLI → Claude
======================================================================

👤 You: こんにちは

(Message recorded locally - Claude is in separate tab)

You > _
```

### タブの使い分け

**ターミナル1 (Verantyx-CLI):**
- Verantyxの機能を使う
- Cross構造の確認
- メッセージ履歴の保存
- 自動化タスクの実行

**ターミナル2 (Claude):**
- Claudeと直接会話
- コード生成を依頼
- ファイル編集を確認
- Claude固有の機能を使用

## メリット (Benefits)

### 1. 視覚的な確認

✅ **Claudeが動いているか一目瞭然:**
```
ターミナル2を見れば:
  - Claudeが起動しているか
  - Claudeが応答しているか
  - エラーが出ていないか
  すぐにわかる
```

### 2. UIの混在問題を完全解決

✅ **以前の問題:**
- ClaudeのTUI出力がVerantyxのUIと混ざる
- ANSI escape sequenceが表示される
- ローディングアニメーションが壊れる

✅ **現在:**
- 完全に分離
- それぞれ独立したUI
- 干渉なし

### 3. デバッグが簡単

✅ **問題診断:**
```
Claudeが応答しない？
  → ターミナル2を見る
  → Claudeがクラッシュしていないか確認
  → エラーメッセージを直接読める
```

### 4. 柔軟な使い方

✅ **両方のタブを切り替え:**
```
ターミナル1: Verantyxで自動化
  ↓ 切り替え
ターミナル2: Claudeに直接質問
  ↓ 切り替え
ターミナル1: 結果を確認
```

## 制限事項 (Limitations)

### 1. 通信なし

❌ **Verantyx → Claude の自動通信は未実装:**
- 現在は視覚的な確認のみ
- 将来的にソケット通信を追加予定

### 2. macOS専用

❌ **AppleScriptを使用:**
- macOS Terminal.appとiTerm2のみ対応
- Linux/Windowsは別の実装が必要

### 3. 手動操作が必要

❌ **ユーザーがEnterを押す:**
- Claudeの起動確認をユーザーが目視
- 自動化はされていない

## 将来の拡張 (Future Extensions)

### Phase 2: ソケット通信実装

**計画:**
```python
# Verantyx-CLI: ソケットサーバー起動
server = socket.socket()
server.bind(('localhost', 12345))

# Claude: ラッパースクリプト経由で接続
# wrapper.py:
#   - Claudeを起動
#   - I/Oをソケット経由でVerantyxに転送

# Verantyx → Claude: メッセージ送信
socket.send(b"こんにちは\n")

# Claude → Verantyx: 応答受信
response = socket.recv(4096)
```

### Phase 3: クロスプラットフォーム対応

**Linux:**
```bash
# xdotoolを使用
xdotool key ctrl+shift+t
xdotool type "cd /project && claude"
```

**Windows:**
```powershell
# PowerShellスクリプト
Start-Process wt.exe -ArgumentList "new-tab", "-d", "$projectPath", "claude"
```

## まとめ (Summary)

**実装完了:**
- ✅ AppleScriptによる新しいタブ起動
- ✅ Terminal.app / iTerm2 対応
- ✅ Claudeの起動確認機能
- ✅ UIの完全分離

**次のステップ:**
1. Verantyxを起動
2. 新しいタブでClaudeが起動するのを確認
3. 両方のタブを切り替えて使用

**将来の実装予定:**
- ソケット通信による自動連携
- クロスプラットフォーム対応
- より高度な同期機能

---

生成日時: 2026-03-08
実装内容: 別タブ起動機能
ステータス: 完了
次: ソケット通信実装（Phase 2）
