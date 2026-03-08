# Cross構造生成実装 (Cross Structure Implementation)

## 実装内容 (What Was Implemented)

**会話履歴からCross 6軸構造を自動生成する機能を実装しました。**

## Cross構造とは (What is Cross Structure)

Cross構造は、情報を6つの軸で整理する知識表現システムです：

```
       UP (上)
        ↑
        │
LEFT ← · → RIGHT
        │
        ↓
      DOWN (下)

    FRONT (前)
      ↕
    BACK (後)
```

### 6つの軸 (Six Axes)

1. **UP (上)**: 目標・意図 - ユーザーが達成したいこと
2. **DOWN (下)**: 事実・基盤 - 具体的なデータ、メッセージ数
3. **FRONT (前)**: 現在の焦点 - 最近のメッセージ
4. **BACK (後)**: 歴史 - 過去のメッセージ
5. **RIGHT (右)**: 拡張・可能性 - 学習パターン、トピック
6. **LEFT (左)**: 制約・限界 - システムの制限

## アーキテクチャ (Architecture)

```
Verantyx-CLI
  ↓
┌──────────────────────────────┐
│  CrossGenerator              │
│  ┌────────────────────────┐ │
│  │ User Messages          │ │  ← ユーザー入力を記録
│  │ Assistant Messages     │ │  ← Claude応答を記録
│  └────────────────────────┘ │
│          ↓                   │
│  ┌────────────────────────┐ │
│  │ _generate_cross_       │ │  ← 3秒ごとに実行
│  │  structure()           │ │
│  └────────────────────────┘ │
│          ↓                   │
│  conversation.cross.json     │  ← ファイルに保存
└──────────────────────────────┘
```

## 実装ファイル (Implementation Files)

### 1. `cross_generator.py` (新規作成)

**主要クラス:**
```python
class CrossGenerator:
    def __init__(self, output_file: Path, update_interval: float = 3.0):
        """Cross構造生成器"""

    def add_user_message(self, content: str):
        """ユーザーメッセージを記録"""

    def add_assistant_message(self, content: str):
        """アシスタントメッセージを記録"""

    def _generate_cross_structure(self) -> Dict[str, Any]:
        """Cross構造を生成"""
```

**生成される構造:**
```json
{
  "type": "verantyx_conversation_cross",
  "timestamp": "2026-03-08T13:00:00",
  "session_start": "2026-03-08T12:50:00",
  "session_duration_seconds": 600,
  "axes": {
    "up": {
      "goal": "Interactive conversation with Claude",
      "user_intent": "greeting",
      "mode": "chat_interaction"
    },
    "down": {
      "total_user_messages": 5,
      "total_assistant_messages": 4,
      "session_duration_seconds": 600,
      "average_message_length": 25.4
    },
    "front": {
      "recent_user_messages": ["こんにちは", "..."],
      "recent_assistant_messages": ["こんにちは！...", "..."],
      "current_activity": "active_conversation",
      "last_interaction": "2026-03-08T13:05:30"
    },
    "back": {
      "all_user_messages": ["...", "..."],
      "all_assistant_messages": ["...", "..."],
      "session_history": {
        "start": "2026-03-08T12:50:00",
        "duration_seconds": 600
      }
    },
    "right": {
      "learned_patterns": ["multi_turn_conversation", "extended_session"],
      "conversation_topics": ["general"],
      "interaction_style": "concise"
    },
    "left": {
      "constraints": [
        "socket_based_communication",
        "text_only_interface",
        "local_processing"
      ],
      "system_info": {
        "update_interval_seconds": 3.0,
        "max_history_messages": 50
      }
    }
  },
  "metadata": {
    "format_version": "1.0",
    "cross_native": true,
    "auto_generated": true,
    "generator": "verantyx_cross_generator",
    "verantyx_cli_version": "1.0.0"
  }
}
```

### 2. `terminal_ui.py` の統合

**変更点:**

```python
# Cross生成器を作成
cross_file = verantyx_dir / "conversation.cross.json"
cross_gen = CrossGenerator(output_file=cross_file, update_interval=3.0)
cross_gen.start()

# ユーザー入力時にCrossに記録
def on_user_input(text: str):
    socket_server.send_input(text)
    cross_gen.add_user_message(text)  # ← 追加

# Claude応答時にCrossに記録
def output_relay():
    ...
    ui.add_remote_output(output_buffer)
    cross_gen.add_assistant_message(output_buffer)  # ← 追加
```

## 機能 (Features)

### 1. 自動意図推論

```python
def _infer_user_intent(self) -> str:
    """ユーザーの意図を推論"""
    # キーワードベースの推論
    if 'fix' in messages or 'bug' in messages:
        return "debugging"
    elif 'implement' in messages:
        return "feature_development"
    elif 'explain' in messages:
        return "learning"
    ...
```

**検出可能な意図:**
- `debugging`: バグ修正
- `feature_development`: 機能開発
- `learning`: 学習・質問
- `greeting`: 挨拶
- `general_conversation`: 一般会話

### 2. パターン抽出

```python
def _extract_patterns(self) -> List[str]:
    """会話パターンを抽出"""
    # 3メッセージ以上で複数ターン会話
    if len(self.user_messages) > 3:
        patterns.append("multi_turn_conversation")

    # コード関連の議論
    if 'code' in all_text or 'コード' in all_text:
        patterns.append("code_discussion")

    # 長時間セッション
    if len(self.user_messages) > 10:
        patterns.append("extended_session")
```

### 3. トピック抽出

```python
def _extract_topics(self) -> List[str]:
    """会話トピックを抽出"""
    topic_keywords = {
        'programming': ['code', 'function', 'class'],
        'debugging': ['bug', 'error', 'fix'],
        'design': ['design', 'architecture'],
        'testing': ['test']
    }
```

### 4. インタラクションスタイル分析

```python
def _analyze_interaction_style(self) -> str:
    """ユーザーの対話スタイルを分析"""
    avg_length = self._calculate_avg_message_length()

    if avg_length < 20:
        return "concise"  # 簡潔
    elif avg_length < 100:
        return "moderate"  # 適度
    else:
        return "detailed"  # 詳細
```

## 使用例 (Usage Example)

### 会話フロー

```bash
$ verantyx chat

# ユーザー: "こんにちは"
# → cross_gen.add_user_message("こんにちは")

# Claude: "こんにちは！Claude Codeです。..."
# → cross_gen.add_assistant_message("こんにちは！...")

# 3秒後、Cross構造が自動更新される
```

### 生成されるCrossファイル

```bash
.verantyx/
├── conversation.cross.json  ← 会話のCross構造
└── debug.log               ← デバッグログ
```

### Cross構造の内容例

```json
{
  "axes": {
    "up": {
      "goal": "Interactive conversation with Claude",
      "user_intent": "greeting",
      "mode": "chat_interaction"
    },
    "down": {
      "total_user_messages": 1,
      "total_assistant_messages": 1,
      "average_message_length": 5.0
    },
    "front": {
      "recent_user_messages": ["こんにちは"],
      "recent_assistant_messages": ["こんにちは！Claude Codeです。..."],
      "current_activity": "active_conversation"
    },
    "right": {
      "learned_patterns": [],
      "conversation_topics": ["general"],
      "interaction_style": "concise"
    }
  }
}
```

## 利用シーン (Use Cases)

### 1. 会話の振り返り

```bash
# Cross構造を読む
cat .verantyx/conversation.cross.json | jq '.axes.back.all_user_messages'

# 過去のメッセージ一覧が表示される
```

### 2. 学習パターンの分析

```bash
# 学習したパターンを確認
cat .verantyx/conversation.cross.json | jq '.axes.right.learned_patterns'

# 出力例:
# ["multi_turn_conversation", "code_discussion", "extended_session"]
```

### 3. セッション統計

```bash
# セッション情報を確認
cat .verantyx/conversation.cross.json | jq '.axes.down'

# 出力例:
# {
#   "total_user_messages": 15,
#   "total_assistant_messages": 14,
#   "session_duration_seconds": 1200,
#   "average_message_length": 45.3
# }
```

### 4. 現在の焦点

```bash
# 最近のメッセージを確認
cat .verantyx/conversation.cross.json | jq '.axes.front.recent_user_messages'
```

## メリット (Benefits)

### 1. 会話の構造化

✅ **会話が6軸で整理される:**
- 目標、事実、焦点、歴史、可能性、制約
- それぞれの軸で情報を把握できる

### 2. 自動学習

✅ **会話から自動的にパターンを学習:**
- ユーザーの意図
- 会話のトピック
- 対話スタイル

### 3. リアルタイム更新

✅ **3秒ごとに自動更新:**
- 常に最新の会話状態を反映
- セッション統計がリアルタイムで更新

### 4. 拡張性

✅ **他のシステムと連携可能:**
- JSON形式で保存
- 他のツールから読み取り可能
- API経由でアクセス可能

## 今後の拡張 (Future Extensions)

### Phase 2: 感情分析

```python
def _analyze_sentiment(self) -> str:
    """感情分析を追加"""
    # ポジティブ/ネガティブ/ニュートラル
```

### Phase 3: 関連性分析

```python
def _analyze_relationships(self) -> Dict:
    """メッセージ間の関連性を分析"""
    # トピックの遷移
    # 質問と回答のペアリング
```

### Phase 4: 要約生成

```python
def _generate_summary(self) -> str:
    """会話の要約を生成"""
    # 重要なポイントの抽出
    # 自動要約
```

## まとめ (Summary)

**実装完了:**
- ✅ Cross構造生成器 (`cross_generator.py`)
- ✅ terminal_ui.pyとの統合
- ✅ 自動意図推論
- ✅ パターン・トピック抽出
- ✅ リアルタイム更新（3秒間隔）

**生成されるファイル:**
```
.verantyx/conversation.cross.json
```

**次回起動時:**
```bash
verantyx chat
  ↓
会話開始
  ↓
Cross構造が自動生成される ✅
  ↓
3秒ごとに更新 ✅
```

---

生成日時: 2026-03-08
実装内容: Cross構造自動生成
ステータス: 完了
ファイル: .verantyx/conversation.cross.json
