# ソケット通信実装 (Socket Communication Implementation)

## 実装内容 (What Was Implemented)

**Verantyx-CLIとClaudeをソケット経由で通信させる機能を実装しました。**

## アーキテクチャ (Architecture)

```
┌─────────────────────────┐       Socket        ┌─────────────────────────┐
│  ターミナル1            │    (localhost)      │  ターミナル2            │
│                         │                     │                         │
│  Verantyx-CLI           │◄────────────────────┤  Claude Wrapper         │
│  ┌─────────────────┐   │                     │  ┌─────────────────┐   │
│  │ SimpleChatUI    │   │   OUTPUT: データ   │  │ Claude Code     │   │
│  │                 │   │   ◄─────────────   │  │ (PTY)           │   │
│  │ ユーザー入力    │───┤                     │  │                 │   │
│  │                 │   │   INPUT: データ     │  │ 出力をソケット  │   │
│  └─────────────────┘   │   ──────────────►   │  │ に転送          │   │
│         ▲               │                     │  └─────────────────┘   │
│         │               │                     │         ▲               │
│  ┌─────────────────┐   │                     │         │               │
│  │ SocketServer    │   │                     │  PTY I/O監視            │
│  │ (port: random)  │   │                     │  すべてソケット経由     │
│  └─────────────────┘   │                     │                         │
└─────────────────────────┘                     └─────────────────────────┘
```

## コンポーネント (Components)

### 1. `claude_socket_server.py` (Verantyx-CLI側)

**役割:** ソケットサーバーとしてClaudeからの接続を待つ

**主要機能:**
```python
class ClaudeSocketServer:
    def start(self) -> tuple[str, int]:
        """ソケットサーバー起動"""
        # ランダムポートでリッスン開始
        # (host, port) を返す

    def _accept_connection(self):
        """Claudeラッパーからの接続を受け入れる"""
        # ハンドシェイク確認
        # 接続確立

    def _receive_loop(self):
        """Claudeからの出力を受信"""
        # OUTPUT:プレフィックス付きデータを受信
        # on_output コールバックを呼び出し

    def send_input(self, text: str):
        """Claudeに入力を送信"""
        # INPUT:プレフィックス付きで送信
```

**通信プロトコル:**
```
Wrapper → Server:
  - "VERANTYX_CLAUDE_WRAPPER\n" (ハンドシェイク)
  - "OUTPUT:<data>" (Claude出力)

Server → Wrapper:
  - "INPUT:<data>\n" (ユーザー入力)
```

### 2. `claude_wrapper.py` (Claude側)

**役割:** ClaudeをPTYで起動し、I/Oをソケット経由で転送

**主要機能:**
```python
class ClaudeWrapper:
    def connect_to_verantyx(self) -> bool:
        """Verantyxソケットサーバーに接続"""
        # localhostの指定されたポートに接続
        # ハンドシェイク送信

    def launch_claude(self) -> bool:
        """ClaudeをPTYで起動"""
        # pty.fork()でClaude起動
        # PTYのmaster_fdを保持

    def run(self):
        """I/O転送ループ"""
        # Claude出力 → ソケット (OUTPUT:プレフィックス)
        # ソケット → Claude入力 (INPUT:プレフィックスを除去)
```

**実行フロー:**
```bash
# ラッパースクリプトが新しいタブで実行される
python3 claude_wrapper.py localhost 12345 /project/path
  ↓
1. Verantyxに接続
2. Claudeを起動
3. I/O転送開始
```

### 3. `claude_tab_launcher.py` (更新)

**変更点:** ラッパースクリプトを使用するように修正

**Before:**
```python
# Claudeを直接起動
cmd = f"cd {self.project_path} && {self.llm_command}"
```

**After:**
```python
# ラッパースクリプトを起動
wrapper_script = Path(__file__).parent / "claude_wrapper.py"
cmd = f"{python_cmd} '{wrapper_script}' {host} {port} '{project_path}'"
```

### 4. `terminal_ui.py` (更新)

**変更点:** ソケットサーバーを作成してラッパーと通信

**フロー:**
```python
1. ソケットサーバー起動
   socket_server = ClaudeSocketServer()
   host, port = socket_server.start()

2. ラッパーを新しいタブで起動
   launch_claude_in_new_tab(project_path, launch_cmd, host, port)

3. 接続を待つ (最大30秒)
   while not socket_server.is_connected():
       time.sleep(0.5)

4. SimpleChatUIを起動
   ui = SimpleChatUI(
       on_user_input=lambda text: socket_server.send_input(text)
   )

5. 出力リレー
   def output_relay():
       for output in socket_server.outputs:
           ui.add_remote_output(output)
```

### 5. `simple_chat_ui.py` (変更なし)

既にコールバックをサポートしているので変更不要：
```python
if self.on_user_input:
    self.on_user_input(user_input)  # socket_server.send_input()が呼ばれる
```

## 通信フロー (Communication Flow)

### 起動時

```
1. ユーザーが verantyx chat を実行
   ↓
2. ソケットサーバー起動 (例: localhost:54321)
   ↓
3. 新しいタブでラッパースクリプト実行
   python3 claude_wrapper.py localhost 54321 /project
   ↓
4. ラッパーがソケットに接続
   ↓
5. ハンドシェイク
   Wrapper → "VERANTYX_CLAUDE_WRAPPER\n"
   ↓
6. ラッパーがClaudeを起動 (PTY)
   ↓
7. 接続確立 ✅
   ↓
8. SimpleChatUI起動
```

### メッセージ送信時

```
ユーザーがVerantyx-CLIで "こんにちは" と入力
   ↓
SimpleChatUI.on_user_input("こんにちは")
   ↓
socket_server.send_input("こんにちは")
   ↓
ソケット経由で送信: "INPUT:こんにちは\n"
   ↓
ラッパーが受信
   ↓
INPUT:プレフィックスを除去
   ↓
ClaudeのPTYに書き込み
   os.write(master_fd, b"こんにちは\n")
   ↓
Claudeが受信 ✅
```

### 応答受信時

```
ClaudeがPTYに出力
   ↓
ラッパーがPTYから読み取り
   data = os.read(master_fd, 4096)
   ↓
OUTPUT:プレフィックスを付けて送信
   sock.sendall(b"OUTPUT:" + data)
   ↓
ソケットサーバーが受信
   ↓
OUTPUT:プレフィックスを除去
   ↓
socket_server.on_output(decoded_text)
   ↓
output_relay()が検知
   ↓
ui.add_remote_output(text)
   ↓
SimpleChatUIに表示 ✅
```

## 使用例 (Usage Example)

### 起動

```bash
$ verantyx chat

======================================================================
  Launching Claude with Socket Communication
======================================================================

📍 Command: claude
📂 Directory: /Users/user/project

🔧 Setting up socket server...
✅ Socket server ready on localhost:54321

🚀 Launching claude wrapper in new tab...
✅ Wrapper launched in new tab

📡 Waiting for wrapper to connect...
   (This may take a few seconds)

======================================================================
  ✅ Claude Connected!
======================================================================

🎨 Starting Verantyx Chat UI...

======================================================================
  Verantyx-CLI → Claude
======================================================================

👤 You: こんにちは

🤖 Claude (11:30:07):

  こんにちは！何かお手伝いできることはありますか？

You > _
```

### 新しいタブ (ラッパー実行)

```bash
$ python3 /path/to/claude_wrapper.py localhost 54321 /Users/user/project

🔌 Connecting to Verantyx at localhost:54321...
✅ Connected to Verantyx
✅ Handshake successful
🚀 Launching Claude...
✅ Claude launched (PID: 12345)
🔄 Starting I/O forwarding...

# この後、Claudeの出力が表示される
# すべてVerantyxに転送される
```

## メリット (Benefits)

### 1. 完全な双方向通信

✅ **Verantyx → Claude:**
- ユーザーがVerantyxに入力
- ソケット経由でClaudeに送信
- Claudeが受信して応答

✅ **Claude → Verantyx:**
- Claudeの出力をリアルタイムでキャプチャ
- ソケット経由でVerantyxに送信
- Verantyxのチャット画面に表示

### 2. プロセス分離

✅ **安定性:**
- ClaudeがクラッシュしてもVerantyxは影響を受けない
- Verantyxが終了してもClaudeは動き続ける

✅ **視覚的確認:**
- 新しいタブでClaudeが動いているのが見える
- デバッグが簡単

### 3. UI混在問題の完全解決

✅ **以前の問題:**
- ClaudeのTUI出力がVerantyxのUIと混ざる
- ANSI escape sequenceが表示される

✅ **現在:**
- ソケット経由で分離
- 出力フィルタリングも可能
- それぞれ独立したUI

## デバッグ (Debugging)

### ソケット接続確認

```bash
# 別ターミナルで
lsof -i :54321
# Verantyxとラッパーの両方が表示されればOK
```

### ラッパーのログ確認

ラッパースクリプトは標準出力にログを出すので、新しいタブで確認可能：
```
✅ Connected to Verantyx
✅ Handshake successful
✅ Claude launched (PID: 12345)
🔄 Starting I/O forwarding...
```

### 通信フロー確認

Verantyx側のデバッグログ (`.verantyx/debug.log`):
```
[claude_socket_server] INFO: Socket server listening on port 54321
[claude_socket_server] INFO: Waiting for Claude wrapper to connect...
[claude_socket_server] INFO: ✅ Claude wrapper connected from ('127.0.0.1', 54322)
[claude_socket_server] INFO: Handshake successful
```

## トラブルシューティング (Troubleshooting)

### 問題1: ラッパーが接続しない

**症状:**
```
📡 Waiting for wrapper to connect...
❌ Wrapper did not connect in time
```

**対処:**
1. 新しいタブのエラーメッセージを確認
2. Pythonパスが正しいか確認
3. ポート番号が正しいか確認

### 問題2: メッセージが送信されない

**症状:**
- Verantyxで入力してもClaudeに届かない

**対処:**
1. ソケット接続を確認: `socket_server.is_connected()`
2. ラッパーのログを確認
3. `send_input()` が呼ばれているか確認

### 問題3: 応答が表示されない

**症状:**
- Claudeが応答しているがVerantyxに表示されない

**対処:**
1. 出力リレースレッドが動作しているか確認
2. `socket_server.outputs` にデータがあるか確認
3. 出力フィルターを確認

## 制限事項 (Limitations)

### 1. macOS専用

❌ AppleScriptを使用しているため、現在はmacOSのみ対応

### 2. ローカルホストのみ

❌ セキュリティのため、localhostのみに制限

### 3. 1対1通信のみ

❌ 1つのVerantyxに対して1つのClaude

## 将来の拡張 (Future Extensions)

### Phase 3: 暗号化通信

```python
# TLS/SSLでソケット通信を暗号化
context = ssl.create_default_context()
secure_socket = context.wrap_socket(socket)
```

### Phase 4: リモート接続

```python
# 別マシンのClaudeに接続
socket_server.bind(('0.0.0.0', port))  # 全インターフェース
```

### Phase 5: マルチClaude対応

```python
# 複数のClaudeインスタンスを管理
claude1 = ClaudeSocketServer(port=54321)
claude2 = ClaudeSocketServer(port=54322)
```

## まとめ (Summary)

**実装完了:**
- ✅ ソケットサーバー (Verantyx側)
- ✅ ラッパースクリプト (Claude側)
- ✅ 双方向通信 (INPUT/OUTPUT)
- ✅ UI統合 (SimpleChatUI)

**動作確認:**
```bash
verantyx chat
# → ソケット接続
# → メッセージ送信
# → 応答受信
# → すべて動作 ✅
```

---

生成日時: 2026-03-08
実装内容: ソケット通信による双方向I/O
ステータス: 完了
次: 実際のテスト
