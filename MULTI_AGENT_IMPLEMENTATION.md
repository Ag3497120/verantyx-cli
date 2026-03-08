# マルチエージェント機能実装 (Multi-Agent Implementation)

## 実装内容 (What Was Implemented)

**複数のClaudeエージェントを同時制御する機能を実装しました。**

ユーザーの性格や特徴をCross構造から読み取り、それに基づいてエージェントを協調制御できます。

## 機能 (Features)

### 1. 画像Cross変換 (既存機能)

画像をCross構造に変換して、CLIでも「視覚的」に認識できます。

**ファイル:** `verantyx_cli/vision/image_to_cross.py`

**使用例:**
```python
from verantyx_cli.vision.image_to_cross import ImageToCross

converter = ImageToCross(quality='high')  # 最大5000ポイント
cross_structure = converter.convert_image_file(Path('photo.jpg'))

# Cross構造に変換された画像データ
# - UP/DOWN: Y軸（垂直方向）
# - RIGHT/LEFT: X軸（水平方向）
# - FRONT/BACK: 明度（奥行き）
```

**品質プリセット:**
- `low`: 500ポイント
- `medium`: 1000ポイント
- `high`: 5000ポイント
- `ultra`: 10000ポイント
- `maximum`: 50000ポイント

### 2. マルチエージェント選択 (新機能)

セットアップウィザードで複数エージェントモードを選択できます。

**変更ファイル:** `verantyx_cli/ui/setup_wizard_safe.py`

**選択画面:**
```
═══════════════════════════════════════════════════════════════════════
  🤖 Agent Mode Selection
═══════════════════════════════════════════════════════════════════════

  1. Single Agent - Standard mode with one Claude instance
  2. Multi-Agent - Control multiple agents with personality awareness

  Select agent mode (1-2): 2

  🔢 Number of agents to launch (2-5): 3

  ✅ Will launch 3 agents
```

### 3. エージェント制御システム (新機能)

複数のClaudeインスタンスを制御するコントローラー。

**ファイル:** `verantyx_cli/engine/multi_agent_controller.py`

**主要クラス:**

#### `AgentInstance`
- 単一エージェントを管理
- ソケット通信でClaudeと接続
- エージェント専用のCross構造を生成

```python
class AgentInstance:
    def __init__(self, agent_id, agent_name, project_path, verantyx_dir, llm_command):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.cross_file = verantyx_dir / f"agent_{agent_id}_{agent_name}.cross.json"

    def start() -> bool:
        """エージェントを起動"""
        # ソケットサーバー作成
        # 新しいタブでClaude起動
        # Cross生成器起動

    def send_input(text: str):
        """エージェントに入力を送信"""
        # Crossに記録
```

#### `MultiAgentController`
- 全エージェントを統合管理
- ユーザー性格プロファイルの読み込み
- Cross構造の集約

```python
class MultiAgentController:
    def create_agents(agent_configs: List[Dict]) -> bool:
        """複数エージェントを作成"""

    def broadcast_input(text: str):
        """全エージェントに同時送信"""

    def send_to_agent(agent_id: int, text: str):
        """特定エージェントに送信"""

    def aggregate_cross_structures() -> Dict:
        """全エージェントのCross構造を集約"""

    def load_user_profile():
        """ユーザー性格プロファイルをCrossから読み込み"""

    def coordinate_agents(task: str) -> Dict[int, str]:
        """タスクに基づいてエージェントを協調制御"""
```

### 4. エージェントごとのCross構造生成 (新機能)

各エージェントが独自のCross構造を持ちます。

**生成されるファイル:**
```
.verantyx/
├── agent_0_Analyzer.cross.json
├── agent_1_Designer.cross.json
├── agent_2_Implementer.cross.json
└── multi_agent_aggregate.cross.json  ← 集約Cross
```

**個別Cross構造:**
```json
{
  "type": "verantyx_conversation_cross",
  "axes": {
    "up": {"user_intent": "...", "mode": "chat_interaction"},
    "down": {"total_user_messages": 5, ...},
    "front": {"recent_user_messages": [...], ...},
    "back": {"all_user_messages": [...], ...},
    "right": {"learned_patterns": [...], ...},
    "left": {"constraints": [...], ...}
  }
}
```

**集約Cross構造:**
```json
{
  "type": "verantyx_multi_agent_cross",
  "num_agents": 3,
  "agents": [
    {
      "agent_id": 0,
      "agent_name": "Analyzer",
      "cross_structure": {...}
    },
    {
      "agent_id": 1,
      "agent_name": "Designer",
      "cross_structure": {...}
    },
    {
      "agent_id": 2,
      "agent_name": "Implementer",
      "cross_structure": {...}
    }
  ],
  "meta_axes": {
    "up": {"goal": "Multi-agent collaboration", ...},
    "down": {"total_agents": 3, "total_messages": 15, ...},
    "right": {
      "learned_patterns": ["multi_turn_conversation", "code_discussion"],
      "topics": ["programming", "design"]
    }
  }
}
```

### 5. マルチエージェントUI (新機能)

複数エージェントを制御するターミナルUI。

**ファイル:** `verantyx_cli/ui/multi_agent_ui.py`

**UI構造:**
```
═══════════════════════════════════════════════════════════════════════
  Verantyx Multi-Agent Control (3 agents)
═══════════════════════════════════════════════════════════════════════

  🤖 Agents:
    [0] Analyzer ✅ (5 msgs)
    [1] Designer ✅ (3 msgs)
    [2] Implementer ✅ (2 msgs)

  💡 Tips:
    - Tab: Switch target agent
    - Broadcast mode sends to all agents
    - Each agent has its own Cross structure

🤖 Agent 0 (Analyzer) [12:48:17]:

  分析結果を表示...

🤖 Agent 1 (Designer) [12:48:25]:

  設計案を表示...

────────────────────────────────────────────────────────────────────
Target: Agent 0 | Tab: Switch | Enter: Send | Esc: Cancel | Ctrl+C: Quit
> [Agent 0] 次の分析をお願い_
```

**操作方法:**
- **Tab**: エージェント切り替え（Broadcast → Agent 0 → Agent 1 → ...）
- **Enter**: 入力を送信
- **Esc**: 入力キャンセル
- **Ctrl+C**: 終了

**Broadcastモード:**
```
> [BROADCAST] この問題を解決して
→ 全エージェントに同時送信
```

**個別送信モード:**
```
> [Agent 0] この部分を分析して
→ Agent 0のみに送信
```

## アーキテクチャ (Architecture)

```
Verantyx-CLI
  ↓
┌─────────────────────────────────────────────────┐
│  セットアップウィザード                         │
│  ┌────────────────────────────────────────────┐ │
│  │ LLM選択: Claude / Gemini / Codex          │ │
│  │ モード選択:                                │ │
│  │   • Single Agent (標準)                   │ │
│  │   • Multi-Agent (複数エージェント)        │ │
│  │ エージェント数: 2-5                       │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
          ↓
    Multi-Agent?
          ↓
    ┌─────┴─────┐
    │           │
   Yes          No
    │           │
    ↓           ↓
Multi-Agent   Single Agent
   Mode          Mode
    │             │
    ↓             ↓
┌────────────┐  ┌──────────┐
│ Controller │  │  Socket  │
│            │  │  Server  │
│ Agent 0 ───┼──│  Claude  │
│ Agent 1 ───┼──└──────────┘
│ Agent 2 ───┤       │
└────────────┘       ↓
    │           Cross構造
    ↓           生成（1個）
┌────────────┐
│ Agent 0:   │
│  .cross    │
│ Agent 1:   │
│  .cross    │
│ Agent 2:   │
│  .cross    │
│ Aggregate: │
│  .cross    │
└────────────┘
```

## 使用例 (Usage Examples)

### シングルエージェントモード（既存）

```bash
verantyx chat

# セットアップウィザード
Select your LLM provider:
  1. Claude (Anthropic) - Subscription
  ...
Select (1-6): 1

# エージェントモード選択
Select agent mode:
  1. Single Agent - Standard mode with one Claude instance
  2. Multi-Agent - Control multiple agents with personality awareness
Select (1-2): 1

# Claude起動
✅ Claude Connected!

# チャット開始
> こんにちは
🤖 Claude: こんにちは！

# Cross構造生成
📌 Cross structure saved to: .verantyx/conversation.cross.json
```

### マルチエージェントモード（新機能）

```bash
verantyx chat

# セットアップウィザード
Select your LLM provider:
  1. Claude (Anthropic) - Subscription
Select (1-6): 1

# エージェントモード選択
Select agent mode:
  1. Single Agent - Standard mode with one Claude instance
  2. Multi-Agent - Control multiple agents with personality awareness
Select (1-2): 2

# エージェント数入力
Number of agents to launch (2-5): 3
✅ Will launch 3 agents

# 3つのエージェント起動
🚀 Creating 3 agents...
✅ Agent 0 (Analyzer) started successfully
✅ Agent 1 (Designer) started successfully
✅ Agent 2 (Implementer) started successfully

✅ All 3 Agents Connected!

# マルチエージェントUI起動
═══════════════════════════════════════════════════
  Verantyx Multi-Agent Control (3 agents)
═══════════════════════════════════════════════════

  🤖 Agents:
    [0] Analyzer ✅ (0 msgs)
    [1] Designer ✅ (0 msgs)
    [2] Implementer ✅ (0 msgs)

# ブロードキャスト送信
> [BROADCAST] このコードをレビューして

# 全エージェントが応答
🤖 Agent 0 (Analyzer) [12:48:17]:
  コードを分析しました...

🤖 Agent 1 (Designer) [12:48:25]:
  設計の観点から...

🤖 Agent 2 (Implementer) [12:48:30]:
  実装の観点から...

# Tabキーでエージェント切り替え
> [Agent 0] もっと詳しく分析して

# Agent 0のみが応答
🤖 Agent 0 (Analyzer) [12:49:10]:
  詳細な分析結果...

# 終了時
Ctrl+C

📌 Aggregate Cross structure saved to: .verantyx/multi_agent_aggregate.cross.json
📌 3 agents stopped
📌 Individual Cross structures saved:
   • Agent 0 (Analyzer): .verantyx/agent_0_Analyzer.cross.json
   • Agent 1 (Designer): .verantyx/agent_1_Designer.cross.json
   • Agent 2 (Implementer): .verantyx/agent_2_Implementer.cross.json
```

## ユーザー性格認識と協調制御 (Personality-Aware Coordination)

### 1. 性格プロファイルの読み込み

既存の会話Cross構造から、ユーザーの性格特徴を読み込みます。

```python
controller.load_user_profile()

# 読み込まれる情報:
{
  'interaction_style': 'concise',  # or 'moderate', 'detailed'
  'learned_patterns': ['multi_turn_conversation', 'code_discussion'],
  'topics': ['programming', 'debugging']
}
```

### 2. エージェント協調制御

ユーザー性格に基づいて、各エージェントに適切な指示を与えます。

```python
instructions = controller.coordinate_agents("新機能を実装")

# 例: 2エージェントの場合
{
  0: "Agent 0 (Research): Research and analyze this task: 新機能を実装",
  1: "Agent 1 (Implementation): Implement solutions for: 新機能を実装"
}

# 例: 3エージェントの場合
{
  0: "Agent 0 (Analysis): Analyze requirements for: 新機能を実装",
  1: "Agent 1 (Design): Design solution for: 新機能を実装",
  2: "Agent 2 (Implementation): Implement: 新機能を実装"
}
```

### 3. 性格認識の活用例

**簡潔型ユーザー (interaction_style: 'concise')**
- エージェントに簡潔な回答を指示
- 要点のみを返すように制御

**詳細型ユーザー (interaction_style: 'detailed')**
- エージェントに詳細な説明を指示
- 背景情報も含めて返すように制御

**コード重視ユーザー (topics: ['programming', 'code_discussion'])**
- Implementerエージェントを優先
- コード例を多く含めるように制御

## Cross構造の活用 (Using Cross Structures)

### 個別エージェントのCross確認

```bash
# Agent 0の意図
cat .verantyx/agent_0_Analyzer.cross.json | jq '.axes.up.user_intent'
# → "debugging"

# Agent 1の学習パターン
cat .verantyx/agent_1_Designer.cross.json | jq '.axes.right.learned_patterns'
# → ["multi_turn_conversation", "design_discussion"]

# Agent 2のメッセージ数
cat .verantyx/agent_2_Implementer.cross.json | jq '.axes.down.total_user_messages'
# → 5
```

### 集約Crossの確認

```bash
# 全エージェント統計
cat .verantyx/multi_agent_aggregate.cross.json | jq '.meta_axes.down'
# → {"total_agents": 3, "total_messages": 15, "active_agents": 3}

# 全エージェントで学習したパターン（重複なし）
cat .verantyx/multi_agent_aggregate.cross.json | jq '.meta_axes.right.learned_patterns'
# → ["multi_turn_conversation", "code_discussion", "design_discussion"]

# 各エージェントのCross構造
cat .verantyx/multi_agent_aggregate.cross.json | jq '.agents[0].agent_name'
# → "Analyzer"
```

## メリット (Benefits)

### 1. 並列処理

✅ **複数の視点から同時に問題解決:**
- Analyzerが分析している間に、Designerが設計を考える
- 待ち時間なく、複数の作業を並行実行

### 2. 専門化

✅ **各エージェントが特定の役割に特化:**
- Analyzer: 問題分析・要件抽出
- Designer: 設計・アーキテクチャ
- Implementer: コード実装
- Tester: テスト・検証
- Reviewer: レビュー・改善提案

### 3. Cross構造による学習

✅ **各エージェントが独立して学習:**
- エージェントごとの会話履歴
- エージェントごとの学習パターン
- 集約によるメタ分析

### 4. 性格認識

✅ **ユーザーの特徴に合わせた制御:**
- 簡潔型 → 要点のみ返答
- 詳細型 → 背景情報も含めて返答
- コード重視 → 実装例を多く

## 拡張可能性 (Future Extensions)

### Phase 2: エージェント間通信

```python
# エージェント同士が協調
controller.enable_inter_agent_communication()

# Agent 0の分析結果をAgent 1が受け取る
# Agent 1の設計をAgent 2が実装
```

### Phase 3: 動的役割割り当て

```python
# タスクに応じて自動的に役割を割り当て
controller.auto_assign_roles(task="新機能を実装")

# → Agent 0: 要件定義担当
# → Agent 1: 設計担当
# → Agent 2: 実装担当
```

### Phase 4: Cross構造の高度な活用

```python
# 全エージェントのCrossを統合してメタ認知
meta_analysis = controller.perform_meta_analysis()

# ユーザーの隠れた意図を推測
# 最適なエージェント構成を提案
```

## まとめ (Summary)

**実装完了機能:**
- ✅ 画像Cross変換（既存・50000ポイントまで対応）
- ✅ マルチエージェント選択（セットアップウィザード）
- ✅ エージェント制御システム（MultiAgentController）
- ✅ エージェントごとのCross構造生成
- ✅ マルチエージェントUI（タブ切り替え・ブロードキャスト）
- ✅ ユーザー性格プロファイル読み込み
- ✅ Cross構造集約

**生成されるファイル:**
```
.verantyx/
├── conversation.cross.json          # シングルエージェント
├── agent_0_Analyzer.cross.json      # マルチエージェント個別
├── agent_1_Designer.cross.json      # マルチエージェント個別
├── agent_2_Implementer.cross.json   # マルチエージェント個別
├── multi_agent_aggregate.cross.json # マルチエージェント集約
└── multi_agent.log                  # マルチエージェントログ
```

**次回起動時:**
```bash
verantyx chat
  ↓
セットアップウィザード
  ↓
Multi-Agent選択（2-5エージェント）
  ↓
全エージェント起動
  ↓
マルチエージェントUI
  ↓
Tabキーで切り替え・Broadcast送信
  ↓
各エージェントのCross構造生成 ✅
  ↓
集約Cross構造生成 ✅
```

---

生成日時: 2026-03-08
実装内容: マルチエージェント機能
ステータス: 完了
新機能: 複数エージェント制御、性格認識、Cross集約
