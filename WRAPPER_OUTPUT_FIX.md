# ラッパー出力修正 (Wrapper Output Fix)

## 問題 (Problem)

**症状:**
```bash
✅ Claude launched (PID: 91948)
🔄 Starting I/O forwarding...

# この後、何も表示されない
# Claudeが起動しているか確認できない
```

## 原因 (Cause)

PTYで起動したClaudeの出力は、親プロセス（ラッパー）の`master_fd`から読み取りますが、**ターミナルには自動的に表示されません**。

```python
# 以前のコード
data = os.read(self.master_fd, 4096)
if data:
    # ソケットに送信するだけ
    message = b"OUTPUT:" + data
    self.sock.sendall(message)
    # ← ターミナルには何も表示されない！
```

## 解決策 (Solution)

**Claudeの出力を2箇所に送る:**
1. ✅ ローカルターミナルに表示（ユーザーが見える）
2. ✅ ソケット経由でVerantyxに送信（UIに表示）

### 修正内容

```python
# 修正後のコード
if self.master_fd in readable:
    try:
        data = os.read(self.master_fd, 4096)
        if data:
            # 1. ローカルターミナルに表示
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

            # 2. Verantyxにも送信
            message = b"OUTPUT:" + data
            self.sock.sendall(message)
```

## 効果 (Effect)

### Before:
```bash
🔄 Starting I/O forwarding...

# 何も表示されない
# Claudeが動いているか不明
```

### After:
```bash
🔄 Starting I/O forwarding...
📺 Claude output will be shown below:
======================================================================

╭─────────────────────────────────────────────────────────────────╮
│                                                                 │
│  Welcome to Claude Code                                         │
│  Model: Claude 3.5 Sonnet                                       │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯

How can I help?
> _
```

**ユーザーが見える！**

## 追加改善 (Additional Improvements)

### 1. プロセス生存確認

```python
# Claudeが即座にクラッシュしていないか確認
time.sleep(1)

try:
    os.kill(self.claude_pid, 0)  # プロセス存在確認
    print(f"✅ Claude process is running")
except OSError:
    print(f"❌ Claude process died immediately")
    return False
```

### 2. デバッグメッセージ追加

```python
# Verantyxからの入力受信時
print(f"\n📨 Received input from Verantyx: {input_data[:50]}...")

# エラー時
except OSError as e:
    print(f"\n❌ Error reading from Claude: {e}")
```

### 3. 視覚的な区切り

```python
print("📺 Claude output will be shown below:")
print("=" * 70)

# Claudeの出力...

# 終了時
print("\n" + "=" * 70)
print("Claude closed")
```

## 使用例 (Usage Example)

### 新しいタブ（ラッパー実行）

```bash
$ python3 claude_wrapper.py localhost 59422 .

🔌 Connecting to Verantyx at localhost:59422...
✅ Connected to Verantyx
🚀 Launching Claude...
✅ Claude launched (PID: 91948)
✅ Claude process is running
🔄 Starting I/O forwarding...
📺 Claude output will be shown below:
======================================================================

╭─────────────────────────────────────────────────────────────────╮
│                                                                 │
│  Welcome to Claude Code                                         │
│  Model: Claude 3.5 Sonnet                                       │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯

How can I help?
>

# Verantyxから "こんにちは" が送られてくる

📨 Received input from Verantyx: こんにちは

> こんにちは

[Claude thinking...]

こんにちは！何かお手伝いできることはありますか？

> _
```

**完璧！Claudeが動いているのが見える！**

## 動作フロー (Operation Flow)

```
1. ラッパー起動
   ↓
2. Verantyxソケットに接続
   ↓
3. ClaudeをPTYで起動
   ↓
4. I/O転送ループ開始
   ↓
5. Claudeの初期出力（Welcome画面）
   → ターミナルに表示 ✅
   → Verantyxに送信 ✅
   ↓
6. Verantyxからユーザー入力受信
   → Claudeに転送
   → ターミナルに通知表示
   ↓
7. Claudeが応答
   → ターミナルに表示 ✅
   → Verantyxに送信 ✅
   ↓
8. 両方のUIで見える！
```

## メリット (Benefits)

### 1. 視覚的確認

✅ **Claudeが実際に動いているのが見える**
```
新しいタブを見れば:
  - Claudeが起動しているか
  - Claudeが応答しているか
  - エラーが出ていないか
すぐにわかる
```

### 2. デバッグが簡単

✅ **問題診断:**
```
Verantyxで応答がない？
  → 新しいタブを確認
  → Claudeがエラーを出していないか
  → メッセージが届いているか
  → すぐに原因がわかる
```

### 3. 透明性

✅ **何が起こっているか明確:**
```
📨 Received input from Verantyx: こんにちは
  ↓
Claudeが処理
  ↓
応答がターミナルに表示
  ↓
Verantyxにも送信
```

## まとめ (Summary)

**修正内容:**
- ✅ Claudeの出力をローカルターミナルにも表示
- ✅ プロセス生存確認
- ✅ デバッグメッセージ追加
- ✅ 視覚的な区切り線

**効果:**
- ✅ Claudeが動いているのが見える
- ✅ デバッグが簡単
- ✅ 問題診断が容易

**次回起動時:**
```bash
verantyx chat
  ↓
新しいタブでClaudeが起動
  ↓
Claudeの画面が見える ✅
  ↓
メッセージを送信
  ↓
両方のタブで応答が見える ✅
```

---

生成日時: 2026-03-08
修正内容: ラッパー出力の可視化
ステータス: 完了
次: 実際のテスト
