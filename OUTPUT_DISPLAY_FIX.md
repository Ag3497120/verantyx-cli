# 出力表示修正 (Output Display Fix)

## 問題 (Problem)

**症状:**

Claude側（新しいタブ）:
```
⏺ こんにちは！Claude Codeへようこそ。
  （応答が表示されている）
```

Verantyx側:
```
⠸ Waiting for Claude response...
（応答が表示されない）
```

## 原因 (Causes)

### 1. 出力フィルターが強すぎる

**以前のコード:**
```python
cleaned = filter_llm_output(text)  # 厳しいフィルター
if cleaned:
    self.add_message('assistant', cleaned)
```

問題：
- `filter_llm_output()` が応答を除外
- 絵文字や装飾文字を除外
- 実際の応答テキストも除外される可能性

### 2. 出力が細切れに届く

```
OUTPUT:⏺
OUTPUT: こん
OUTPUT:にち
OUTPUT:は！
...
```

問題：
- 各出力が個別にフィルター処理される
- 短いテキストがフィルターで除外される
- 完全な応答が表示されない

## 解決策 (Solutions)

### 1. シンプルなフィルター

```python
def add_remote_output(self, text: str):
    """Add output from remote LLM"""
    import re

    # ANSI escape sequencesのみ除去
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    cleaned = ansi_escape.sub('', text)

    # 制御文字を除去（改行とタブは残す）
    cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', cleaned)

    # 意味のあるテキストがあれば表示
    if cleaned.strip():
        self.add_message('assistant', cleaned)
```

**改善点:**
- ✅ ANSIエスケープシーケンスのみ除去
- ✅ 絵文字や装飾文字は保持
- ✅ 実際の応答テキストを保持

### 2. バッファリング付き出力リレー

```python
def output_relay():
    """Relay socket outputs to UI with buffering"""
    displayed_count = 0
    output_buffer = ""
    last_output_time = time.time()

    while ui.running and socket_server.is_connected():
        current_count = len(socket_server.outputs)

        # 新しい出力を蓄積
        if current_count > displayed_count:
            for i in range(displayed_count, current_count):
                output = socket_server.outputs[i]
                output_buffer += output  # バッファに追加
            displayed_count = current_count
            last_output_time = time.time()

        # 0.5秒間新しいデータがなければ送信
        if output_buffer and (time.time() - last_output_time) > 0.5:
            ui.add_remote_output(output_buffer)
            output_buffer = ""

        time.sleep(0.1)
```

**メリット:**
- ✅ 細切れの出力をまとめる
- ✅ 完全な応答としてフィルター処理
- ✅ 表示が自然

### 3. デバッグログ追加

```python
logger.info(f"📥 Raw output ({len(text)} chars): {text[:200]}...")
logger.info(f"✨ Cleaned output ({len(cleaned)} chars): {cleaned[:200]}...")

if cleaned.strip():
    logger.info(f"✅ Adding to chat: {cleaned.strip()[:100]}...")
    self.add_message('assistant', cleaned)
else:
    logger.warning(f"❌ Filtered out (empty after cleaning)")
```

**効果:**
- `.verantyx/debug.log` で何が起こっているか確認できる

## 動作フロー (Operation Flow)

### Before（細切れ処理）

```
Claude出力:
  ⏺ こんにちは！Claude Codeへようこそ。
    ↓
PTY → ラッパー（細切れで送信）:
  OUTPUT:⏺
  OUTPUT: こん
  OUTPUT:にち
  OUTPUT:は！
  OUTPUT:Claude
  OUTPUT: Code
  ...
    ↓
ソケットサーバー（個別に受信）:
  outputs[0] = "⏺"
  outputs[1] = " こん"
  outputs[2] = "にち"
  ...
    ↓
出力リレー（個別に処理）:
  filter("⏺") → 除外（短すぎる）
  filter(" こん") → 除外（短すぎる）
  ...
    ↓
結果: 何も表示されない ❌
```

### After（バッファリング）

```
Claude出力:
  ⏺ こんにちは！Claude Codeへようこそ。
    ↓
PTY → ラッパー（細切れで送信）:
  OUTPUT:⏺
  OUTPUT: こん
  OUTPUT:にち
  OUTPUT:は！
  OUTPUT:Claude
  OUTPUT: Code
  ...
    ↓
ソケットサーバー（個別に受信）:
  outputs[0] = "⏺"
  outputs[1] = " こん"
  outputs[2] = "にち"
  ...
    ↓
出力リレー（バッファリング）:
  buffer = "⏺"
  buffer += " こん"
  buffer += "にち"
  buffer += "は！"
  buffer += "Claude"
  buffer += " Code"
  ...
  ↓
  0.5秒間新しいデータなし
  ↓
  filter("⏺ こんにちは！Claude Codeへようこそ。")
  → ANSIのみ除去
  → "⏺ こんにちは！Claude Codeへようこそ。"
    ↓
結果: 完全な応答が表示される ✅
```

## 使用例 (Usage Example)

### Verantyx-CLI側

**Before:**
```
👤 You: こんにちは

⠸ Waiting for Claude response...
（永遠に待機）
```

**After:**
```
👤 You: こんにちは

⠸ Waiting for Claude response...
（0.5秒後）

🤖 Claude (12:48:17):

  ⏺ こんにちは！Claude Codeへようこそ。

  ソフトウェア開発やコード編集、バグ修正、機能追加などをお手伝いします。

You > _
```

## デバッグログ確認 (Debug Logs)

```bash
tail -f .verantyx/debug.log
```

**出力例:**
```
[simple_chat_ui] INFO: 📥 Raw output (156 chars): ⏺ こんにちは！Claude Codeへようこそ。...
[simple_chat_ui] INFO: ✨ Cleaned output (156 chars): ⏺ こんにちは！Claude Codeへようこそ。...
[simple_chat_ui] INFO: ✅ Adding to chat: ⏺ こんにちは！Claude Codeへようこそ。...
```

**問題がある場合:**
```
[simple_chat_ui] WARNING: ❌ Filtered out (empty after cleaning)
```

## トラブルシューティング (Troubleshooting)

### 問題1: まだ応答が表示されない

**確認:**
```bash
# デバッグログを見る
tail -f .verantyx/debug.log

# "📥 Raw output" が出ているか？
# → 出ていない = ソケット通信の問題
# → 出ている = フィルターの問題
```

**対処:**
```python
# フィルターを完全に無効化してテスト
def add_remote_output(self, text: str):
    # フィルターなし
    if text.strip():
        self.add_message('assistant', text)
```

### 問題2: 応答が途切れる

**確認:**
```python
# バッファリング時間を延長
if output_buffer and (time.time() - last_output_time) > 1.0:  # 0.5秒 → 1.0秒
```

### 問題3: ANSIエスケープシーケンスが表示される

**確認:**
```python
# 正規表現パターンを強化
ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')  # ?を追加
```

## 改善点 (Improvements)

### 1. 応答完了検出

```python
# Claudeの応答完了マーカーを検出
if "────────" in output_buffer:
    # 応答完了
    ui.add_remote_output(output_buffer)
    output_buffer = ""
```

### 2. ストリーミング表示

```python
# バッファリングせず、リアルタイム表示
# （フィルターは緩くする）
def output_relay():
    for output in socket_server.outputs[displayed_count:]:
        ui.add_remote_output(output, streaming=True)
```

### 3. フィルターレベル設定

```python
# ユーザーがフィルターレベルを選択
FILTER_LEVEL = "minimal"  # minimal, normal, strict

if FILTER_LEVEL == "minimal":
    # ANSIのみ除去
elif FILTER_LEVEL == "normal":
    # ANSI + 制御文字
elif FILTER_LEVEL == "strict":
    # 高度なフィルタリング
```

## まとめ (Summary)

**修正内容:**
- ✅ シンプルなフィルター（ANSIのみ除去）
- ✅ バッファリング付き出力リレー（0.5秒）
- ✅ デバッグログ追加

**効果:**
```
Before:
  Claude応答 → 細切れ → フィルター除外 → 何も表示されない ❌

After:
  Claude応答 → バッファリング → まとめてフィルター → 完全表示 ✅
```

**次回起動時:**
```bash
verantyx chat
  ↓
メッセージ送信
  ↓
Claude応答
  ↓
Verantyxに完全表示 ✅
```

---

生成日時: 2026-03-08
修正内容: 出力フィルターとバッファリング
ステータス: 完了
次: 実際のテスト
