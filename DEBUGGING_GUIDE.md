# 🔧 Verantyx-CLI デバッグガイド

## 問題の症状

### 1. Claudeにメッセージが届かない
- 画像変換は成功する
- "Waiting for Claude response..." が永遠に続く
- Claudeからの応答がない

### 2. Claudeプロセスが残る
- Verantyx終了後もClaudeプロセスが動いている
- `ps aux | grep claude` で多数のプロセスが表示される

## 🔍 診断ツール

### 1. ソケット通信テスト

```bash
cd /Users/motonishikoudai/verantyx_v6/verantyx-cli
python3 test_claude_connection.py
```

**期待される出力:**
```
✅ Socket server started on localhost:12345
✅ Claude wrapper connected!
✅ Sent: Hello from Verantyx test!
✅ Received 1 output(s)
```

**もし失敗したら:**
- Socket serverが起動しない → ポート競合の可能性
- Wrapper が接続しない → Wrapper が起動していない
- Outputsが0 → Claude-Wrapper間の通信が機能していない

### 2. デバッグモード

```bash
python3 -m verantyx_cli.ui.simple_debug_mode
```

**これで確認できること:**
- ソケットサーバーの起動状況
- Wrapperの接続状態
- メッセージの送受信

### 3. プロセスクリーンアップ

```bash
./cleanup_claude_processes.sh
```

**これで:**
- 残留Claudeプロセスを全て表示
- 確認後に一括削除

## 🔬 手動診断

### Step 1: ソケットサーバー確認

```bash
# Verantyxを起動
verantyx chat

# 別ターミナルで
netstat -an | grep LISTEN | grep <port番号>
```

サーバーが起動していれば表示される。

### Step 2: Wrapper確認

Claudeタブで以下が表示されるはず:

```
🔌 Connecting to Verantyx at localhost:12345...
✅ Connected to Verantyx
🚀 Launching Claude...
✅ Claude launched (PID: 12345)
✅ Claude process is running
```

**表示されない場合:**
- Wrapperが起動していない
- ソケット接続に失敗している

### Step 3: 通信確認

Verantyxで何かメッセージを送信:

```
> Hello
```

Claudeタブで `INPUT:` が表示されるはず。

**表示されない場合:**
- ソケット通信が機能していない
- Wrapperが入力を受信していない

## 🐛 よくある問題と解決策

### 問題1: "Waiting for Claude wrapper to connect..." から進まない

**原因:**
- Wrapperが起動していない
- ポート番号が一致していない
- ソケット接続に失敗

**解決策:**
1. Claudeタブを確認（Wrapper出力が表示されているか）
2. ポート番号を確認
3. Verantyxを再起動

### 問題2: メッセージを送っても応答がない

**原因:**
- Wrapper → Claude の通信が機能していない
- Claude → Wrapper の出力転送が機能していない
- OUTPUTプレフィックスの問題

**解決策:**

**方法A: Wrapperログを確認**

Claudeタブで以下が表示されているか:
```
OUTPUT: <Claude's response>
```

表示されていなければ、WrapperがClaude出力を取得できていない。

**方法B: デバッグモードで確認**

```bash
python3 -m verantyx_cli.ui.simple_debug_mode
```

Outputsが増えるか確認。

### 問題3: Claudeプロセスが残り続ける

**原因:**
- PID追跡が機能していない
- killシグナルが届いていない
- プロセスがゾンビ化

**解決策:**

**即座にクリーンアップ:**
```bash
./cleanup_claude_processes.sh
```

**または手動で:**
```bash
# 全Claudeプロセスを表示
ps aux | grep claude | grep -v grep

# 全て削除
pkill -9 -f claude
```

## 📊 通信フロー

### 正常な通信フロー

```
1. Verantyx: ソケットサーバー起動 (port 12345)
2. Wrapper: ソケット接続 (localhost:12345)
3. Wrapper: ハンドシェイク送信 "VERANTYX_CLAUDE_WRAPPER\n"
4. Wrapper: Claude起動 (PTY)
5. Verantyx: メッセージ送信 "INPUT:Hello\n"
6. Wrapper: INPUT受信 → Claude PTYに書き込み
7. Claude: 応答生成
8. Wrapper: Claude出力読み取り → "OUTPUT:<response>" を送信
9. Verantyx: OUTPUT受信 → UIに表示
```

### どこで止まっているか確認

**Step 1-2で止まる:**
- ソケット接続の問題
- ポート番号の不一致

**Step 3-4で止まる:**
- Wrapperの起動失敗
- Claudeコマンドが見つからない

**Step 5-6で止まる:**
- 送信は成功しているが、Wrapperが受信していない
- WrapperのINPUT処理が機能していない

**Step 7-9で止まる:**
- Claudeは起動しているが応答がない
- Wrapper → Verantyx の出力転送が機能していない

## 🔧 詳細ログの有効化

`~/.verantyx/debug.log` を確認:

```bash
tail -f ~/.verantyx/debug.log
```

**重要なログ:**
```
INFO: Socket server listening on port 12345
INFO: ✅ Claude wrapper connected from ('127.0.0.1', 54321)
INFO: Sending to Claude: Hello...
INFO: Tracked claude PID: 12345
```

## 🧪 最小限のテスト

### テスト1: ソケットだけ

```bash
# Terminal 1
python3 -c "
from verantyx_cli.engine.claude_socket_server import ClaudeSocketServer
server = ClaudeSocketServer()
host, port = server.start()
print(f'Server on {port}')
import time
while True: time.sleep(1)
"

# Terminal 2 (port番号を置き換え)
nc localhost <port番号>
VERANTYX_CLAUDE_WRAPPER
```

接続されれば、Terminal 1に「Connected」と表示される。

### テスト2: Wrapperだけ

```bash
# Terminal 1: ソケットサーバー
python3 test_claude_connection.py

# Terminal 2: Wrapper手動起動
python3 verantyx_cli/engine/claude_wrapper.py localhost <port> ~/verantyx_v6
```

Wrapperが接続すれば成功。

## ✅ 完全な診断チェックリスト

```
□ ソケットサーバーが起動している
□ Wrapperがソケットに接続している
□ Wrapperがハンドシェイクを送信している
□ Claudeプロセスが起動している
□ INPUT送信が機能している
□ Wrapper → Claude の書き込みが機能している
□ Claude → Wrapper の読み取りが機能している
□ OUTPUT送信が機能している
□ Verantyxが OUTPUT を受信している
□ UIに応答が表示されている
```

全てチェックできれば通信は正常。

## 🆘 それでもダメな場合

1. **Verantyxを完全再起動**
   ```bash
   pkill -9 -f claude
   pkill -9 -f verantyx
   # 再起動
   verantyx chat
   ```

2. **ログを全て確認**
   ```bash
   cat ~/.verantyx/debug.log
   cat ~/.verantyx/multi_agent.log
   ```

3. **Issue報告**
   https://github.com/Ag3497120/verantyx-cli/issues

   含めるべき情報:
   - OS/ターミナル種類
   - `ps aux | grep claude` の出力
   - `~/.verantyx/debug.log` の内容
   - エラーメッセージのスクリーンショット

---

**🎯 まず試すべきこと:**

1. `./cleanup_claude_processes.sh` で残留プロセスクリーンアップ
2. `python3 test_claude_connection.py` で接続テスト
3. `verantyx chat` で再起動

これで大抵の問題は解決します！
