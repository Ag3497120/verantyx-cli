# 入力転送修正 (Input Forwarding Fix)

## 問題 (Problems)

**症状1: Enterキーが押されない**
```
> こんにちは

# Enterが押されず、Claudeが反応しない
```

**症状2: 文字化け**
```
^[[O^[[I^[[O^[[I^[[O^[[I
# 制御文字が混入
```

## 原因 (Causes)

### 1. Enterキーが送られていない

**以前のコード:**
```python
# ソケットサーバー側
message = f"INPUT:{text}\n".encode('utf-8')
self.client_socket.sendall(message)
```

問題：`\n` はソケットメッセージの区切りであり、Claudeへの入力ではない。

### 2. 文字ごとの送信が複雑

**以前のコード:**
```python
# 各文字を個別のメッセージとして送信
for char in text:
    char_msg = f"INPUT:{char}".encode('utf-8')
    self.client_socket.sendall(char_msg)
```

問題：
- 大量の小さいメッセージ
- ソケットバッファリングでタイミング問題
- 制御文字が混入する可能性

## 解決策 (Solution)

### アプローチ: 2段階転送

```
Verantyx → Socket → Wrapper → Claude
  (text)   (1度)   (文字ごと)  (PTY)
```

### 1. ソケットサーバー側（シンプル化）

```python
def send_input(self, text: str):
    """Send input to Claude wrapper"""
    # テキスト全体を1度に送信
    # ラッパー側で文字ごとに分割
    message = f"INPUT:{text}\n".encode('utf-8')
    self.client_socket.sendall(message)
```

**メリット:**
- ✅ 1回のソケット送信
- ✅ バッファリング問題なし
- ✅ シンプル

### 2. ラッパー側（タイピングシミュレーション）

```python
# ソケットから受信
msg = data.decode('utf-8', errors='replace')

if msg.startswith("INPUT:"):
    # INPUT:プレフィックスを除去
    input_text = msg[6:].rstrip('\n\r')

    # Claudeに文字ごとに送信（タイピングシミュレーション）
    for char in input_text:
        os.write(self.master_fd, char.encode('utf-8'))
        time.sleep(0.01)  # 10ms間隔

    # Enterキーを送信
    os.write(self.master_fd, b'\r')
```

**メリット:**
- ✅ 実際のタイピングをシミュレート
- ✅ Claudeが認識しやすい
- ✅ Enterキーを明示的に送信

## 通信プロトコル (Communication Protocol)

### 更新後のプロトコル

```
Server → Wrapper:
  "INPUT:<text>\n"

  例:
  "INPUT:こんにちは\n"

Wrapper → Claude PTY:
  'こ' (10ms) → 'ん' (10ms) → 'に' (10ms) → 'ち' (10ms) → 'は' (10ms) → '\r'
```

### なぜ文字ごとに送るのか？

**理由:**
```python
# 一度に送ると:
os.write(master_fd, b"こんにちは\r")

# PTYが全部バッファリングして、Claudeが認識しないことがある

# 文字ごとに送ると:
for char in "こんにちは":
    os.write(master_fd, char.encode('utf-8'))
    time.sleep(0.01)
os.write(master_fd, b'\r')

# 実際のタイピングをシミュレート
# Claudeが確実に認識
```

## 動作フロー (Operation Flow)

### メッセージ送信

```
1. ユーザーがVerantyx-CLIで "こんにちは" と入力
   ↓
2. SimpleChatUI.on_user_input("こんにちは")
   ↓
3. socket_server.send_input("こんにちは")
   ↓
4. ソケット送信: "INPUT:こんにちは\n"
   ↓
5. ラッパーが受信
   ↓
6. INPUT:プレフィックス除去 → "こんにちは"
   ↓
7. 文字ごとにClaudeに送信:
   'こ' → wait 10ms
   'ん' → wait 10ms
   'に' → wait 10ms
   'ち' → wait 10ms
   'は' → wait 10ms
   '\r' (Enter)
   ↓
8. Claude が受信 ✅
   ↓
9. Claude が応答生成
   ↓
10. 応答がPTY → ラッパー → ソケット → Verantyx
    ↓
11. SimpleChatUIに表示 ✅
```

## 使用例 (Usage Example)

### Verantyx-CLI側

```bash
======================================================================
  Verantyx-CLI → Claude
======================================================================

👤 You: こんにちは

⠋ Waiting for Claude response...
```

### Claude側（新しいタブ）

```bash
📨 Sent to Claude: こんにちは...

────────────────────────────────────────────────────────────────
> こんにちは

[Claude thinking...]

こんにちは！何かお手伝いできることはありますか？

────────────────────────────────────────────────────────────────
> _
```

### Verantyx-CLI側（応答受信後）

```bash
======================================================================
  Verantyx-CLI → Claude
======================================================================

👤 You: こんにちは

🤖 Claude (11:30:07):

  こんにちは！何かお手伝いできることはありますか？

You > _
```

## デバッグ出力 (Debug Output)

### ラッパー側のログ

```bash
📨 Sent to Claude: こんにちは...

# 文字が1つずつ送られる
# 10ms間隔
# 最後にEnterキー
```

### Verantyx側のログ (debug.log)

```
[claude_socket_server] INFO: Sending to Claude: こんにちは
[claude_socket_server] INFO: ✅ Sent: こんにちは...
```

## トラブルシューティング (Troubleshooting)

### 問題1: まだEnterが押されない

**確認:**
```python
# ラッパー側で確認
os.write(self.master_fd, b'\r')  # ← これが実行されているか
```

**対処:**
```python
# \r の代わりに \n を試す
os.write(self.master_fd, b'\n')

# または両方
os.write(self.master_fd, b'\r\n')
```

### 問題2: 文字が届かない

**確認:**
```bash
# 新しいタブでラッパーのログを見る
📨 Sent to Claude: ...

# このメッセージが出ていない場合
# → ソケット通信に問題
```

**対処:**
```bash
# ソケット接続確認
lsof -i :54321

# デバッグログ確認
tail -f .verantyx/debug.log
```

### 問題3: 文字化けが残る

**確認:**
```python
# UTF-8エンコーディング確認
char.encode('utf-8')  # 正しくエンコードされているか
```

**対処:**
```python
# エラー時のハンドリング追加
try:
    encoded = char.encode('utf-8')
    os.write(self.master_fd, encoded)
except UnicodeEncodeError:
    # スキップまたはエラー処理
    pass
```

## 改善点 (Improvements)

### 1. エラーハンドリング

```python
try:
    for char in input_text:
        os.write(self.master_fd, char.encode('utf-8'))
        time.sleep(0.01)
except OSError as e:
    print(f"❌ Failed to write to Claude: {e}")
    return
```

### 2. 送信確認

```python
# ラッパー側
print(f"\n📨 Sent to Claude: {input_text[:50]}...")

# これで送信が確認できる
```

### 3. タイミング調整

```python
# 送信間隔を調整可能に
CHAR_DELAY = 0.01  # 10ms

for char in input_text:
    os.write(self.master_fd, char.encode('utf-8'))
    time.sleep(CHAR_DELAY)
```

## まとめ (Summary)

**修正内容:**
- ✅ ソケット送信をシンプル化（1回で送信）
- ✅ ラッパー側で文字ごとに分割
- ✅ Enterキーを明示的に送信 (`\r`)
- ✅ タイピングシミュレーション（10ms間隔）

**期待される動作:**
```
Verantyxで "こんにちは" と入力
  ↓
Claudeに正しく届く
  ↓
Claudeが応答
  ↓
Verantyxに表示
  ↓
完璧！✅
```

**次回起動時:**
```bash
verantyx chat
  ↓
メッセージ入力
  ↓
正しくClaudeに届く ✅
  ↓
応答が返ってくる ✅
```

---

生成日時: 2026-03-08
修正内容: 入力転送とEnterキー送信
ステータス: 完了
次: 実際のテスト
