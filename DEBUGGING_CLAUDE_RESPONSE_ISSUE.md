# Claudeが応答しない問題のデバッグ (Debugging Claude No Response Issue)

## 問題 (Problem)

**症状:**
- メッセージを送信しても、Claudeから応答が返ってこない
- ローディングアニメーションは動作している
- Cross構造ファイルが空 (0 bytes)

**原因の可能性:**
1. ClaudeプロセスがPTY経由でメッセージを受信していない
2. Claudeが応答を生成しているが、PTYから読み取れていない
3. 出力フィルターが強すぎて全てをスキップしている
4. Claudeプロセスが起動後にクラッシュしている

## 実施したデバッグ改善 (Debug Improvements)

### 1. 詳細なログ追加

**`claude_monitor.py`の変更:**

#### I/O監視ループのログ強化
```python
def _io_monitor_loop(self):
    logger.info("Starting I/O monitor loop (monitor-only mode)")  # ← 追加

    if self.master_fd in readable:
        try:
            data = os.read(self.master_fd, 4096)
            if data:
                decoded = data.decode('utf-8', errors='replace')
                self._record_claude_output(decoded)

                # 詳細なログ出力
                logger.info(f"📥 Received {len(data)} bytes from LLM")
                logger.info(f"   Content: {decoded[:200]}...")  # ← 追加
```

**効果:** PTYから実際にデータを受信しているか確認できる

#### メッセージ送信のログ強化
```python
def send_to_llm(self, text: str):
    # プロセスヘルスチェック
    if not self.is_llm_alive():
        logger.error("❌ Cannot send: LLM process has died")
        logger.error(f"   Process exit code: {self.process.returncode}")
        return

    logger.info(f"📤 Sending message to LLM: {text[:50]}...")
    logger.info(f"   LLM process status: PID={self.process.pid}, alive={self.is_llm_alive()}")

    # ... メッセージ送信 ...

    logger.info(f"✅ Message sent successfully ({len(text)} chars)")
```

**効果:**
- メッセージが実際に送信されたか確認
- プロセスが生きているか確認
- 送信エラーの詳細を確認

#### プロセスヘルスチェック関数追加
```python
def is_llm_alive(self) -> bool:
    """Check if LLM process is still running"""
    if not self.process:
        return False
    return self.process.poll() is None
```

**効果:** Claudeプロセスがクラッシュしていないか確認

### 2. ファイルベースのデバッグログ

**`terminal_ui.py`の変更:**

```python
def start_chat_mode(project_path: Path, llm_provider: str = "claude"):
    # デバッグログ設定 (ファイルのみ - UIに干渉しない)
    verantyx_dir = project_path / '.verantyx'
    verantyx_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(verantyx_dir / 'debug.log')
        ]
    )
    logger.info("=== Verantyx Chat Mode Starting ===")
```

**効果:**
- UIに干渉せずにデバッグログを記録
- `.verantyx/debug.log` に全ての詳細ログが保存される

### 3. テストスクリプト作成

**`test_debug_monitor.py`:**

Claudeの起動から通信までを単独でテストするスクリプト。

**使用方法:**
```bash
cd /Users/motonishikoudai/verantyx_v6/verantyx-cli
python3 test_debug_monitor.py
```

**何をテストするか:**
1. Claude起動の成功/失敗
2. プロセスPIDとFDの確認
3. 初期出力のキャプチャ
4. テストメッセージの送信
5. 応答の受信確認
6. Cross構造ファイルの生成確認

## デバッグ手順 (Debug Steps)

### Step 1: デバッグログを確認

```bash
# Verantyxを起動
verantyx chat

# メッセージを送信
# (こんにちは、と入力してEnter)

# 別ターミナルでログを確認
tail -f /Users/motonishikoudai/verantyx_v6/verantyx-cli/.verantyx/debug.log
```

**確認すべきログ:**

✅ **正常な場合:**
```
[claude_monitor] INFO: Starting I/O monitor loop (monitor-only mode)
[claude_monitor] INFO: 📤 Sending message to LLM: こんにちは
[claude_monitor] INFO:    LLM process status: PID=12345, alive=True
[claude_monitor] INFO: ✅ Message sent successfully (5 chars)
[claude_monitor] INFO: 📥 Received 234 bytes from LLM
[claude_monitor] INFO:    Content: こんにちは！何かお手伝い...
```

❌ **問題がある場合:**
```
[claude_monitor] ERROR: ❌ Cannot send: LLM process has died
[claude_monitor] ERROR:    Process exit code: -9
```

または

```
[claude_monitor] INFO: 📤 Sending message to LLM: こんにちは
[claude_monitor] INFO: ✅ Message sent successfully (5 chars)
# ← この後に "📥 Received" がない = PTYから応答が来ていない
```

### Step 2: テストスクリプトで診断

```bash
cd /Users/motonishikoudai/verantyx_v6/verantyx-cli
python3 test_debug_monitor.py
```

**期待される出力:**
```
INFO: Project path: /Users/motonishikoudai/verantyx_v6/verantyx-cli
INFO: Creating ClaudeMonitor...
INFO: Launching Claude...
INFO: Claude launched successfully!
INFO: Process PID: 12345
INFO: Master FD: 3
INFO: Waiting 3 seconds for Claude to initialize...
INFO: Claude process alive: True
INFO: Number of outputs captured: 15
INFO: Recent outputs:
  Output 0: ╭─────────────────────...
  Output 1: Welcome to Claude Code...
  ...
INFO: Sending test message: 'こんにちは'
[claude_monitor] INFO: 📤 Sending message to LLM: こんにちは
[claude_monitor] INFO: ✅ Message sent successfully (5 chars)
INFO: Waiting 5 seconds for response...
INFO: Number of outputs after message: 28
INFO: Latest outputs:
  Output 0: こんにちは！何かお手伝い...
```

### Step 3: Claudeプロセスの確認

```bash
# Verantyx起動中に別ターミナルで
ps aux | grep claude

# 期待される出力:
# user  12345  ... claude
```

Claudeプロセスが見つからない場合 → 起動に失敗している

### Step 4: PTYの確認

```bash
# Verantyx起動中に別ターミナルで
lsof -p <Claude PID> | grep pty

# 期待される出力:
# claude  12345  ...  /dev/ptys001
```

PTYが見つからない場合 → PTY接続に問題がある

## 考えられる原因と対処 (Possible Causes and Solutions)

### 原因1: Claudeプロセスがクラッシュしている

**症状:**
```
[claude_monitor] ERROR: ❌ Cannot send: LLM process has died
```

**対処:**
1. Claudeを単独で起動して動作確認
   ```bash
   claude
   ```
2. Claudeのバージョン確認
   ```bash
   claude --version
   ```
3. 必要に応じてClaude再インストール

### 原因2: PTYから応答が読み取れていない

**症状:**
- メッセージ送信成功のログはある
- でも `📥 Received` ログがない

**対処:**
1. `select.select()` のタイムアウトを長くしてみる

   `claude_monitor.py` line 174-179:
   ```python
   readable, _, _ = select.select(
       [self.master_fd],
       [],
       [],
       1.0  # 0.1秒 → 1.0秒に変更
   )
   ```

2. Claudeの出力バッファリングを無効化

   `claude_monitor.py` line 131-139:
   ```python
   env = os.environ.copy()
   env['PYTHONUNBUFFERED'] = '1'  # 追加

   self.process = subprocess.Popen(
       [self.llm_command],
       ...
       env=env,  # 変更
       ...
   )
   ```

### 原因3: 出力フィルターが強すぎる

**症状:**
- PTYから応答は受信している
- でもUIに表示されない

**対処:**
1. `output_filter.py` のフィルター条件を緩和
2. 一時的にフィルターを無効化してテスト

### 原因4: メッセージが正しく送信されていない

**症状:**
```
[claude_monitor] ERROR: ❌ Failed to send to LLM: Broken pipe
```

**対処:**
1. 文字ごとの送信間隔を長くする

   `claude_monitor.py` line 515:
   ```python
   time.sleep(0.05)  # 0.01秒 → 0.05秒に変更
   ```

2. Enter キーを別の方法で送信

   `claude_monitor.py` line 518:
   ```python
   # 変更前: os.write(self.master_fd, b'\r\n')
   # 変更後:
   os.write(self.master_fd, b'\n')  # LFのみ
   ```

## 次のステップ (Next Steps)

1. **デバッグログを有効化して実行**
   ```bash
   verantyx chat
   ```

2. **ログを確認**
   ```bash
   tail -f .verantyx/debug.log
   ```

3. **どのログが出ているか報告**
   - メッセージ送信のログは出る？
   - 応答受信のログは出る？
   - エラーログは出る？

4. **テストスクリプトを実行**
   ```bash
   python3 test_debug_monitor.py
   ```

5. **結果に基づいて次の対処を決定**

---

生成日時: 2026-03-08
目的: Claude応答なし問題のデバッグ
状態: デバッグツール準備完了
次: ログ確認と原因特定
