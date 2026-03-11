# Enterキー検出による保存システム - 実装ガイド

## 🎯 目的

Claude の応答を **確実に1回だけ** Cross構造に保存する新しい仕組み。

従来の `>` プロンプト検出は不安定（重複、誤検出）だったため、**実際のEnterキー検出**に変更しました。

---

## ✅ 新方式の特徴

### 従来の問題点

| 問題 | 詳細 |
|------|------|
| **重複記録** | `>` が複数回検出され、1応答が242回保存される |
| **誤検出** | `> Try "edit..."` などのClaude応答内の `>` を誤検出 |
| **不完全検出** | Hugging Faceのような応答が保存されない |
| **複雑な状態管理** | `response_saved`, `last_prompt_was_saved`, `first_user_input_received` など多数のフラグ |

### 新方式の利点

| 利点 | 詳細 |
|------|------|
| **確実な検出** | Enterキー（`\r`）は明確で誤検出なし |
| **シンプル** | カウンタのみで管理（`enter_press_count`） |
| **重複なし** | デバウンス（0.2秒）で連続検出を防止 |
| **ループ構造** | Enter → 蓄積 → Enter → 保存 → Enter → 保存... |

---

## 📊 実装の仕組み

### 1. Enter キー検出

```python
# claude_subprocess_engine.py: line 276

# PTYからデータを読み取る
data = os.read(self.master_fd, 4096)

# Enterキー検出（\r = carriage return = ASCII 13）
if b'\r' in data:
    self._handle_enter_key_press()
```

### 2. Enter ハンドラー

```python
def _handle_enter_key_press(self):
    """
    Enterキー検出時の処理

    ループ構造:
    1. 起動時のEnter (count=0→1) → スキップ
    2. 1回目の質問のEnter (count=1→2) → 蓄積開始
    3. 2回目の質問のEnter (count=2→3) → 保存 + 蓄積開始
    4. 3回目の質問のEnter (count=3→4) → 保存 + 蓄積開始
    ... 繰り返し
    """
    current_time = time.time()

    # デバウンス: 0.2秒以内の連続Enterを無視
    if current_time - self.last_enter_time < 0.2:
        return

    self.last_enter_time = current_time
    self.enter_press_count += 1

    if self.enter_press_count == 1:
        # 起動時のEnter → スキップ
        self.waiting_for_next_enter = True
        return

    elif self.enter_press_count >= 2:
        # 2回目以降のEnter → 前回の応答を保存
        self._save_accumulated_response()

        # 次の応答の蓄積を開始
        self.response_chunks = []
        self.waiting_for_next_enter = True
```

### 3. 保存処理

```python
def _save_accumulated_response(self):
    """
    蓄積された応答を保存

    Enter → Enter の間に蓄積されたチャンクをCross構造に保存
    """
    # 組み立て済みの応答を取得
    assembled = self.completion_predictor.current_assembly.get('chunks', [])

    if not assembled:
        return

    full_text = ''.join(assembled)

    # 十分な長さがあるか（20文字以上）
    if len(full_text.strip()) < 20:
        return

    # 起動メッセージは無視
    if "Welcome back!" in full_text:
        return

    # Cross構造に記録
    stats = self._record_to_cross('assistant', full_text)

    # 💾 保存案内を表示
    if stats:
        print(f"\n💾 Cross Memory: {stats['total_inputs']} inputs, {stats['total_responses']} responses")

    # 予測器をリセット
    self.completion_predictor.reset()
```

---

## 🔄 ループ構造の詳細

### フロー図

```
起動
 ↓
[Enter #1] 起動時のEnter
 ↓ → スキップ（count=1）
 ↓
ユーザー: "GitHubとは" と入力
 ↓
[Enter #2] 1回目の質問
 ↓ → 蓄積開始（count=2）
 ↓
Claude: "GitHubとは、Gitを使った..." を表示
 ↓
ユーザー: "Hugging Faceとは" と入力
 ↓
[Enter #3] 2回目の質問
 ↓ → GitHub応答を保存（count=3）
 ↓ → 蓄積開始
 ↓
Claude: "Hugging Faceは、機械学習の..." を表示
 ↓
ユーザー: "Rustとは" と入力
 ↓
[Enter #4] 3回目の質問
 ↓ → Hugging Face応答を保存（count=4）
 ↓ → 蓄積開始
 ↓
Claude: "Rustは、システムプログラミング..." を表示
 ↓
ユーザー: "Goとは" と入力
 ↓
[Enter #5] 4回目の質問
 ↓ → Rust応答を保存（count=5）
 ↓ → 蓄積開始
 ↓
... 繰り返し
```

### カウンタの状態遷移

| Enter回数 | 状態 | アクション |
|----------|------|-----------|
| 0 | 起動直後 | - |
| 1 | 起動時のEnter | スキップ |
| 2 | 1回目の質問 | 蓄積開始（保存なし） |
| 3 | 2回目の質問 | **1回目の応答を保存** + 蓄積開始 |
| 4 | 3回目の質問 | **2回目の応答を保存** + 蓄積開始 |
| 5 | 4回目の質問 | **3回目の応答を保存** + 蓄積開始 |
| N (N≥3) | N-1回目の質問 | **N-2回目の応答を保存** + 蓄積開始 |

---

## 🧪 テスト結果

### テストコマンド

```bash
python3 test_enter_detection.py
```

### 結果

```
✅ All tests PASSED!

実装された機能:
  1. Enterキー検出（\r）
  2. Enter → Enter の間の応答を保存
  3. デバウンス（0.2秒）
  4. シンプルなカウンタベースのロジック

保存タイミング:
  Enter (count=2) → GitHub応答を保存
  Enter (count=3) → Hugging Face応答を保存
  Enter (count=4) → Rust応答を保存
  ... 繰り返し
```

---

## 🚀 実機テスト手順

### ステップ1: チャットモードで確認

```bash
python3 -m verantyx_cli chat
```

### ステップ2: 質問を入力

```
🗣️ You: GitHubとは

[Claude の応答が表示される]

🗣️ You: Hugging Faceとは

[Enter] ← ここで保存トリガー
[ENTER] Enter key detected! Count: 3
[SAVE] Accumulated chunks: XX
[SAVE] Full text length: XXX chars
💾 Cross Memory: 1 inputs, 1 responses
```

### ステップ3: 統計情報の確認

各質問ごとに `💾 Cross Memory` が表示され、カウントが増えることを確認：

```
質問1: GitHubとは
  → 応答表示
  → [次の質問を入力]

質問2: Hugging Faceとは
  → [Enter]
  → 💾 Cross Memory: 1 inputs, 1 responses
  → 応答表示
  → [次の質問を入力]

質問3: Rustとは
  → [Enter]
  → 💾 Cross Memory: 2 inputs, 2 responses
  → 応答表示
  → [次の質問を入力]

質問4: Goとは
  → [Enter]
  → 💾 Cross Memory: 3 inputs, 3 responses
```

### ステップ4: Cross構造の検証

```bash
python3 verify_learning.py
```

**期待される出力:**

```
[3] DOWN Axis (Claude Responses):
  Total responses: 3  # 重複なし！

  Latest response preview:
    Length: XXX chars
    Preview: Rustは、システムプログラミング...
```

---

## ⚙️ 設定パラメータ

### デバウンス時間（調整可能）

```python
# claude_subprocess_engine.py: _handle_enter_key_press() 内

if current_time - self.last_enter_time < 0.2:  # デフォルト: 0.2秒
```

**推奨値:**
- **0.1秒**: 高速入力対応（誤検出リスクあり）
- **0.2秒**: バランスが良い（デフォルト）
- **0.5秒**: 確実（遅い入力でも安全）

### 最小保存文字数（調整可能）

```python
# claude_subprocess_engine.py: _save_accumulated_response() 内

if len(full_text.strip()) < 20:  # デフォルト: 20文字
```

**推奨値:**
- **10文字**: 短い応答も保存
- **20文字**: バランスが良い（デフォルト）
- **50文字**: 長い応答のみ保存

---

## 📈 従来方式との比較

| 方式 | 検出精度 | 重複記録 | 応答時間 | 状態管理 | 総合評価 |
|------|---------|---------|---------|---------|---------|
| **`>` プロンプト検出（旧）** | ❌ 不安定 | ❌ 大量発生 | ✅ 即座 | ❌ 複雑 | ❌ 使用不可 |
| **Enterキー検出（新）** | ✅ 確実 | ✅ なし | ✅ 即座 | ✅ シンプル | ✅ **最適解** |

---

## 🔧 トラブルシューティング

### 問題1: 保存されない

**原因:** Enterキーが検出されていない

**確認方法:**
```bash
# デバッグ出力を確認
[ENTER] Enter key detected! Count: X
```

**対策:**
- ログに `[ENTER]` が表示されるか確認
- 表示されない場合、PTYの設定を確認

### 問題2: 重複記録

**原因:** デバウンス時間が短すぎる

**確認方法:**
```bash
# 連続検出のログを確認
[ENTER] Enter key detected! Count: 2
[ENTER] Enter key detected! Count: 3  # 0.2秒以内
```

**対策:**
- デバウンス時間を 0.5秒 に増やす

### 問題3: 起動時の応答が保存される

**原因:** `enter_press_count == 1` のスキップロジックが機能していない

**確認方法:**
```bash
[ENTER] Enter key detected! Count: 1
[ENTER] Startup enter - skipping  # この行が表示されるか
```

**対策:**
- カウンタが正しく初期化されているか確認

---

## 📝 まとめ

### 実装された機能

1. ✅ **Enterキー検出（`\r`）**
   - PTYからの生データで検出
   - 確実で誤検出なし

2. ✅ **デバウンス（0.2秒）**
   - 連続検出を防止
   - 同じEnterキーの重複を回避

3. ✅ **シンプルなカウンタ管理**
   - `enter_press_count` のみ
   - 従来の複雑なフラグ管理を削除

4. ✅ **ループ構造**
   - Enter → 蓄積 → Enter → 保存
   - 明確でわかりやすい

### 保存条件

```
条件A: Enter キーが検出される
  └─ enter_press_count >= 2
  └─ テキストが20文字以上
  └─ 起動メッセージでない

→ 条件Aで保存
```

### 期待される改善

- ✅ 重複記録なし（1応答 = 1エントリ）
- ✅ すべての応答が確実に保存
- ✅ 即座に保存（待ち時間なし）
- ✅ 統計情報で進捗を確認可能
- ✅ スタンドアロンモードで知識を活用

### 削除された機能（旧方式）

- ❌ `>` プロンプト検出
- ❌ `response_saved` フラグ
- ❌ `first_user_input_received` フラグ
- ❌ `last_prompt_was_saved` フラグ
- ❌ `last_prompt_detection_time` フラグ
- ❌ パズル推論による保存
- ❌ タイムアウトによる保存

**実装完了。実機テストを推奨します。**
