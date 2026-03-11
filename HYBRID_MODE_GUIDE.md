# ハイブリッドモード - 完全ガイド

## 🎯 設計思想

**ユーザーに見せる部分はPTY、内部処理とデータ保存はAPI傍受**

ユーザーの提案に基づき、最適なハイブリッド設計を実装しました。

---

## 📊 役割分担

### PTY（ユーザー体験）

| 役割 | 詳細 |
|------|------|
| **リアルタイム表示** | Claude の応答をストリーミング表示 |
| **インタラクティブ操作** | ユーザー入力、選択肢、プロンプト |
| **UI フィードバック** | `🗣️ You:` プロンプト、進捗表示 |
| **応答完了検出（UI用）** | パズル推論で `🗣️ You:` を即座に表示 |

### API 傍受（内部処理）

| 役割 | 詳細 |
|------|------|
| **正確な境界検出** | API レベルで応答の開始/終了を検出 |
| **Cross 構造保存** | 確実に1回のみ保存（重複なし） |
| **統計情報管理** | 入力数、応答数をカウント |
| **内部判定** | 応答の品質評価、分類など |

---

## 🏗️ アーキテクチャ

### データフロー

```
ユーザー入力
    ↓
PTY → Claude Code
    ↓
  【UI表示】リアルタイム出力（ユーザーが見る）
  【パズル推論】応答完了を検出 → 🗣️ You: を表示
    ↓
  API Request
    ↓
mitmproxy が傍受
    ↓
  /tmp/claude_responses.jsonl に記録
    ↓
ClaudeAPIInterceptor が監視
    ↓
  【内部処理】正確な応答を抽出
    ↓
  【データ保存】Cross構造に保存（1回のみ）
    ↓
  【統計表示】💾 Cross Memory: X inputs, Y responses
```

### コンポーネント図

```
┌─────────────────────────────────────────────────────────────┐
│                     Verantyx Hybrid Mode                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────┐        ┌─────────────────────┐    │
│  │   PTY (UI Layer)    │        │  API (Data Layer)   │    │
│  ├─────────────────────┤        ├─────────────────────┤    │
│  │                     │        │                     │    │
│  │ • リアルタイム表示   │        │ • 応答境界検出       │    │
│  │ • パズル推論         │        │ • Cross保存         │    │
│  │ • 🗣️ You: 表示     │        │ • 統計管理          │    │
│  │ • ユーザー入力       │        │ • 重複防止          │    │
│  │                     │        │                     │    │
│  └─────────────────────┘        └─────────────────────┘    │
│           ↓                              ↓                   │
│     ユーザーが見る                   内部処理                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 💡 なぜハイブリッド方式か？

### PTY のみの問題点

```
❌ Enterキー検出が不安定（54, 55, 56回も検出）
❌ プロンプト検出が曖昧（`>` が複数の意味を持つ）
❌ 応答境界が不明確（どこで終わったか判定困難）
❌ 重複記録が発生（1応答が複数回保存）
```

### API 傍受のみの問題点

```
❌ リアルタイム表示ができない（応答完了後に表示）
❌ ストリーミング体験が失われる
❌ インタラクティブな操作が困難
```

### ハイブリッドの利点

```
✅ PTY: リアルタイム表示、ストリーミング、インタラクティブ
✅ API: 正確な保存、重複なし、内部判定
✅ 両方の長所を組み合わせた最適解
```

---

## 🔄 動作フロー

### シナリオ: "GitHubとは" と質問

#### 1. ユーザー入力（PTY）

```
🗣️ You: GitHubとは [Enter]
```

#### 2. Claude 応答開始（PTY + API）

```
【PTY】リアルタイム表示開始
"GitHubとは、Gitを使った..."

【API】リクエスト送信
POST https://api.anthropic.com/v1/messages
{
  "model": "claude-3-5-sonnet-20241022",
  "messages": [
    {"role": "user", "content": "GitHubとは"}
  ]
}

【mitmproxy】傍受して /tmp/claude_responses.jsonl に記録
```

#### 3. Claude 応答完了（PTY + API）

```
【PTY - パズル推論】応答完了を検出
→ 🗣️ You: を即座に表示（ユーザー体験向上）

【API】レスポンス受信
{
  "content": [
    {"type": "text", "text": "GitHubとは、Gitを使った..."}
  ]
}

【API傍受】Cross構造に保存（1回のみ）
→ 💾 Cross Memory: 1 inputs, 1 responses
```

#### 4. 次の質問（PTY）

```
【PTY】ユーザーは既に 🗣️ You: を見ている
→ すぐに次の質問を入力可能
```

---

## 🚀 セットアップ

### ステップ1: mitmproxy をセットアップ

```bash
python3 setup_mitmproxy.py
```

### ステップ2: mitmproxy を起動

```bash
./start_mitmproxy.sh
```

### ステップ3: Verantyx を起動（プロキシ経由）

```bash
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080

python3 -m verantyx_cli chat
```

### ステップ4: 確認

質問を入力:

```
🗣️ You: GitHubとは
```

**期待される動作:**

1. 応答がリアルタイムで表示される（PTY）
2. 応答完了時に `🗣️ You:` が即座に表示される（PTY - パズル推論）
3. `💾 Cross Memory: 1 inputs, 1 responses` が表示される（API傍受）
4. Cross構造に確実に1回のみ保存される（API傍受）

---

## 📈 パフォーマンス比較

| 方式 | リアルタイム表示 | 応答完了検出 | 重複記録 | 保存精度 | ユーザー体験 | 総合評価 |
|------|----------------|------------|---------|---------|------------|---------|
| **PTY のみ** | ✅ 優秀 | ❌ 不安定 | ❌ 多発 | ❌ 低い | ✅ 良い | ❌ 使用不可 |
| **API のみ** | ❌ なし | ✅ 完璧 | ✅ なし | ✅ 完璧 | ❌ 悪い | △ 部分的 |
| **ハイブリッド（新）** | ✅ 優秀 | ✅ 完璧 | ✅ なし | ✅ 完璧 | ✅ 最高 | ✅ **最適解** |

---

## 🔧 実装詳細

### PTY レイヤー（claude_subprocess_engine.py）

```python
# パズル推論による応答完了検出（UI表示のみ）
if prediction['is_complete'] and not self.waiting_for_next_enter:
    logger.info(f"[PTY-UI] Response complete | score={prediction['completion_score']:.2%}")

    # 🗣️ You: プロンプトを即座に表示（ユーザー体験向上）
    self.waiting_for_next_enter = True
    print(f"\n🗣️  You: ", end='', flush=True)

    # 注: 保存はしない（API傍受が正確に保存）
```

### API レイヤー（claude_subprocess_engine.py）

```python
def _on_api_message(self, api_data: Dict[str, Any]):
    """
    【ハイブリッド方式】API傍受で検出されたメッセージを処理

    役割: データ保存、判定（内部処理）
    - 正確な応答境界検出（APIレベル）
    - Cross構造への確実な保存（重複なし）
    - 統計情報の表示

    UI表示はPTYが担当（リアルタイム、インタラクティブ）
    """
    # ユーザーメッセージを抽出
    user_text = extract_user_message(api_data['request'])
    self._record_to_cross('user', user_text)

    # アシスタントメッセージを抽出
    assistant_text = extract_assistant_message(api_data['response'])
    stats = self._record_to_cross('assistant', assistant_text)

    # 💾 保存案内を表示（ユーザーフィードバック）
    print(f"\n💾 Cross Memory: {stats['total_inputs']} inputs, {stats['total_responses']} responses")
```

---

## 🧪 テスト

### 手動テスト

```bash
# Terminal 1: mitmproxy
./start_mitmproxy.sh

# Terminal 2: Verantyx
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
python3 -m verantyx_cli chat
```

**テストシナリオ:**

1. 質問1: "GitHubとは"
   - ✅ リアルタイム表示
   - ✅ `🗣️ You:` が即座に表示
   - ✅ `💾 Cross Memory: 1 inputs, 1 responses`

2. 質問2: "Hugging Faceとは"
   - ✅ リアルタイム表示
   - ✅ `🗣️ You:` が即座に表示
   - ✅ `💾 Cross Memory: 2 inputs, 2 responses`

3. Cross構造を確認
   ```bash
   python3 verify_learning.py
   ```
   - ✅ Total responses: 2（重複なし）

---

## 📝 まとめ

### 実装された機能

1. ✅ **PTY レイヤー（UI）**
   - リアルタイム出力表示
   - パズル推論による応答完了検出
   - `🗣️ You:` プロンプトの即座表示
   - ストリーミング体験

2. ✅ **API レイヤー（データ）**
   - mitmproxy による API 傍受
   - 正確な応答境界検出
   - Cross構造への確実な保存（1回のみ）
   - 統計情報管理

3. ✅ **ハイブリッド統合**
   - PTY と API の役割分担
   - 両方の長所を組み合わせ
   - 最適なユーザー体験とデータ精度

### 期待される改善

- ✅ リアルタイム表示（PTY）
- ✅ ストリーミング体験（PTY）
- ✅ 重複記録なし（API）
- ✅ 正確な保存（API）
- ✅ 即座のUI フィードバック（PTY + API）
- ✅ 最高のユーザー体験（ハイブリッド）

**ハイブリッドモードが最終形です！**
