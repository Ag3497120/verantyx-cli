# 階層化マルチエージェントシステム (Hierarchical Multi-Agent System)

## 実装内容 (What Was Implemented)

**Crossルーティング層を最上位に配置し、主人エージェント（Agent 0）が他のエージェントを制御する階層化システムを実装しました。**

## アーキテクチャ (Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                   Cross Routing Layer                       │
│  - Parse input for agent references ("2番のエージェント")   │
│  - Detect command types (query, command, broadcast)        │
│  - Aggregate all agent progress from Cross structures      │
│  - Control what information goes to each agent             │
│  - Save routing history to cross_routing.json              │
└─────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────┴────────────────────┐
         │                                         │
┌────────▼────────┐                    ┌──────────▼──────────┐
│  Master Agent   │                    │   Sub-Agents        │
│   (Agent 0)     │ ──── commands ──→  │  Agent 1, 2, 3, ... │
│                 │                    │                     │
│ • Controls all  │                    │ • Execute tasks     │
│ • Gets progress │                    │ • Report progress   │
│   from all subs │                    │   via Cross files   │
│ • Coordinates   │ ←── progress ────  │                     │
└─────────────────┘                    └─────────────────────┘
         ↓                                      ↓
  ┌──────────────┐                    ┌──────────────────┐
  │ agent_0_     │                    │ agent_1_         │
  │ Master.      │                    │ Analyzer.        │
  │ cross.json   │                    │ cross.json       │
  │              │                    │                  │
  │ + progress   │                    │ + progress       │
  │ + task info  │                    │ + subtasks       │
  └──────────────┘                    └──────────────────┘
```

## 主要機能 (Key Features)

### 1. Crossルーティング層 (Cross Routing Layer)

**ファイル:** `verantyx_cli/engine/cross_routing_layer.py`

最上位の情報制御層。すべての入出力を統括します。

#### 機能:

**1.1 エージェント番号認識**
```python
# 以下のパターンを認識:
"2番のエージェント"
"エージェント2"
"agent #2"
"#2"
```

**1.2 コマンドタイプ検出**
- `query`: 進捗確認（"進捗", "status", "確認"）
- `command`: 命令実行（"やって", "実行", "do"）
- `broadcast`: 全員送信（"全員", "みんな", "all"）

**1.3 進捗情報集約**
```python
def get_agent_progress(agent_id, cross_file):
    """エージェントのCross構造から進捗を取得"""
    return {
        'agent_id': agent_id,
        'status': 'active',
        'total_messages': 10,
        'current_activity': 'working',
        'recent_messages': [...],
        'learned_patterns': [...],
        'topics': [...]
    }
```

**1.4 マスターコンテキスト生成**
```python
def create_master_context(user_input, routing_info, agent_cross_files):
    """
    マスターエージェント用のコンテキストを作成

    含まれる情報:
    - ユーザー入力
    - 参照されたエージェントの進捗
    - 全サブエージェントの状態
    """
```

**1.5 ルーティング履歴保存**
```json
{
  "type": "verantyx_cross_routing",
  "routing_history": [
    {
      "timestamp": "2026-03-08T13:00:00",
      "user_input": "2番のエージェントの進捗は？",
      "routing_info": {
        "target_agent": 2,
        "command_type": "query",
        "extracted_agent_refs": [2]
      },
      "target_agents": [0, 2]
    }
  ],
  "statistics": {
    "total_routes": 15,
    "command_types": {"query": 5, "command": 8, "broadcast": 2},
    "agent_references": {2: 3, 1: 2}
  }
}
```

### 2. エージェント進捗Cross構造 (Agent Progress Cross Structure)

**変更ファイル:** `verantyx_cli/engine/cross_generator.py`

各エージェントのCross構造に進捗情報を追加。

#### 新しいフィールド:

```json
{
  "type": "verantyx_conversation_cross",
  "axes": {
    "up": {...},
    "down": {...},
    "front": {...},
    "back": {...},
    "right": {...},
    "left": {...}
  },
  "progress": {
    "agent_id": 1,
    "agent_role": "Analyzer",
    "current_task": "コードベースを分析",
    "task_status": "working",
    "task_progress_percent": 60,
    "subtasks": [
      {
        "name": "ファイル構造解析",
        "status": "completed",
        "created_at": "2026-03-08T13:00:00",
        "updated_at": "2026-03-08T13:05:00"
      },
      {
        "name": "依存関係分析",
        "status": "working",
        "created_at": "2026-03-08T13:05:00"
      },
      {
        "name": "パフォーマンス評価",
        "status": "pending",
        "created_at": "2026-03-08T13:05:00"
      }
    ],
    "last_update": "2026-03-08T13:10:00"
  },
  "metadata": {
    "format_version": "1.1",
    "multi_agent_enabled": true
  }
}
```

#### 進捗更新API:

```python
# タスク設定
cross_gen.set_task("コードベースを分析")

# 進捗更新
cross_gen.update_progress(60, "working")

# サブタスク追加
cross_gen.add_subtask("ファイル構造解析", "pending")
cross_gen.add_subtask("依存関係分析", "pending")

# サブタスク更新
cross_gen.update_subtask(0, "completed")
cross_gen.update_subtask(1, "working")

# タスク完了
cross_gen.complete_task()

# タスク失敗
cross_gen.fail_task("エラーが発生")
```

### 3. 主人エージェント制御 (Master Agent Control)

**変更ファイル:** `verantyx_cli/engine/multi_agent_controller.py`

マスターエージェント（Agent 0）が他のエージェントを制御。

#### 階層構造:

```
Agent 0 (Master)
  ├─ Agent 1 (Analyzer)
  ├─ Agent 2 (Designer)
  ├─ Agent 3 (Implementer)
  └─ Agent 4 (Tester)
```

#### インテリジェントルーティング:

```python
def send_with_routing(user_input):
    """
    Crossルーティング層を使用した送信

    1. 入力をパース（エージェント参照検出）
    2. 適切なエージェントにルーティング
    3. マスターには全サブエージェントの進捗を付与
    4. サブエージェントには元のメッセージを送信
    """
    routing_result = routing_layer.route_message(user_input, agent_cross_files)

    # マスターに送信（コンテキスト付き）
    if 0 in targets:
        agents[0].send_input(master_context)

    # サブエージェントに送信
    for agent_id in targets:
        if agent_id > 0:
            agents[agent_id].send_input(original_message)
```

### 4. インテリジェントUI (Intelligent UI)

**変更ファイル:** `verantyx_cli/ui/multi_agent_ui.py`

ルーティング機能を統合したUI。

#### 使用例:

```
> [INTELLIGENT ROUTING] 2番のエージェントの進捗は？

🔀 Detected agent reference: [2]
📍 Routing to: Agent(s) [0, 2]

# マスター（Agent 0）に送信:
User Input: 2番のエージェントの進捗は？

=== Referenced Agent Progress ===
Agent 2:
  Status: active
  Activity: working
  Messages: 5
  Topics: programming, design
  Recent activity:
    - コードベースを分析中...
    - 設計案を作成中...

=== All Sub-Agents Status ===
Agent 1: ✅ working (3 msgs)
Agent 2: ✅ working (5 msgs)
Agent 3: ✅ idle (0 msgs)

You are the master agent (Agent 0). You can:
- Answer questions about any sub-agent's progress
- Command sub-agents to perform tasks
- Coordinate work between sub-agents

# Agent 2にも送信:
2番のエージェントの進捗は？
```

## 使用例 (Usage Examples)

### シナリオ1: エージェント番号で呼び出し

```bash
verantyx chat
# Multi-Agent mode, 3 agents

> こんにちは
🎯 Routing to: Master (Agent 0)

🤖 Agent 0 (Master): こんにちは！私はマスターエージェントです。
サブエージェントを制御できます。

> 2番のエージェントにコードベースを分析させて

🔀 Detected agent reference: [2]
📍 Routing to: Agent(s) [0, 2]

# マスターがAgent 2に指示
🤖 Agent 0 (Master): Agent 2にコードベース分析を指示しました。

# Agent 2が作業開始
🤖 Agent 2 (Analyzer): 分析を開始します...
```

### シナリオ2: 進捗確認

```bash
> 2番の進捗は？

🔀 Detected agent reference: [2]
📍 Routing to: Agent(s) [0, 2]

# マスターがAgent 2のCross構造を読んで回答
🤖 Agent 0 (Master): Agent 2の進捗:
  タスク: コードベースを分析
  状態: 作業中
  進捗: 60%
  サブタスク:
    ✅ ファイル構造解析（完了）
    ⏳ 依存関係分析（作業中）
    ⏸  パフォーマンス評価（待機中）

# Agent 2も応答
🤖 Agent 2 (Analyzer): 現在60%完了しています。
依存関係分析を進めています。
```

### シナリオ3: ブロードキャスト

```bash
> 全員でこの問題を解決して

📢 Broadcasting to all agents

🤖 Agent 0 (Master): 全エージェントに指示を出します。
🤖 Agent 1 (Analyzer): 問題を分析します。
🤖 Agent 2 (Designer): 設計案を考えます。
🤖 Agent 3 (Implementer): 実装を準備します。
```

### シナリオ4: マスターへの直接質問

```bash
> 今の状況を教えて

🎯 Routing to: Master (Agent 0)

🤖 Agent 0 (Master): 現在の状況:

  Agent 1 (Analyzer): ✅ 作業中 (5メッセージ)
    - タスク: 問題分析
    - 進捗: 80%

  Agent 2 (Designer): ✅ 作業中 (3メッセージ)
    - タスク: 設計案作成
    - 進捗: 40%

  Agent 3 (Implementer): ⏸ 待機中 (0メッセージ)
    - タスク: なし
```

## Cross構造の活用 (Using Cross Structures)

### ルーティング履歴の確認

```bash
cat .verantyx/cross_routing.json | jq '.statistics'

# 出力:
{
  "total_routes": 15,
  "command_types": {
    "query": 5,
    "command": 8,
    "broadcast": 2
  },
  "agent_references": {
    "1": 2,
    "2": 5,
    "3": 1
  }
}
```

### エージェント進捗の確認

```bash
# Agent 2の進捗
cat .verantyx/agent_2_Analyzer.cross.json | jq '.progress'

# 出力:
{
  "agent_id": 2,
  "agent_role": "Analyzer",
  "current_task": "コードベースを分析",
  "task_status": "working",
  "task_progress_percent": 60,
  "subtasks": [
    {
      "name": "ファイル構造解析",
      "status": "completed",
      "created_at": "2026-03-08T13:00:00",
      "updated_at": "2026-03-08T13:05:00"
    },
    {
      "name": "依存関係分析",
      "status": "working",
      "created_at": "2026-03-08T13:05:00"
    }
  ]
}
```

### 集約Cross構造

```bash
cat .verantyx/multi_agent_aggregate.cross.json | jq '.meta_axes.down'

# 出力:
{
  "total_agents": 3,
  "total_messages": 15,
  "active_agents": 3
}
```

## 生成されるファイル (Generated Files)

```
.verantyx/
├── cross_routing.json                  # ← NEW: ルーティング履歴
├── agent_0_Master.cross.json           # ← Agent 0 (Master)
├── agent_1_Analyzer.cross.json         # ← Agent 1 (Sub)
├── agent_2_Designer.cross.json         # ← Agent 2 (Sub)
├── agent_3_Implementer.cross.json      # ← Agent 3 (Sub)
├── multi_agent_aggregate.cross.json    # ← 集約Cross
└── multi_agent.log                     # ← ログ
```

各エージェントのCross構造には`progress`フィールドが含まれます。

## メリット (Benefits)

### 1. 階層化された制御

✅ **マスターエージェントが全体を統括:**
- サブエージェントの進捗を把握
- 適切なエージェントに指示
- 全体の調整

### 2. インテリジェントルーティング

✅ **自然言語でエージェント指定:**
- "2番のエージェント" → Agent 2にルーティング
- "全員で" → ブロードキャスト
- 自動検出でユーザーが明示的に指定不要

### 3. 進捗の可視化

✅ **各エージェントの状態を追跡:**
- タスク名
- 進捗率（%）
- サブタスクの状態
- Cross構造に自動保存

### 4. 情報統括

✅ **Crossルーティング層で全制御:**
- どのエージェントが何回参照されたか
- どのコマンドタイプが多いか
- ルーティング履歴を完全記録

## 動作フロー (Operation Flow)

```
ユーザー入力
  ↓
Crossルーティング層
  ├─ エージェント番号検出
  ├─ コマンドタイプ分類
  ├─ 進捗情報集約
  └─ ルーティング決定
  ↓
┌─────┴─────┐
│           │
マスター    サブ
(Agent 0)  (Agent 1+)
  │           │
  ├─ コンテキスト付き入力
  │  （全サブの進捗含む）
  │
  └─ 元の入力
  ↓
Cross構造更新
  ├─ progress更新
  ├─ メッセージ記録
  └─ ルーティング履歴保存
```

## 拡張可能性 (Future Extensions)

### Phase 2: エージェント間直接通信

```python
# Agent 0がAgent 2にタスクを委譲
controller.delegate_task(from_agent=0, to_agent=2, task="分析")

# Agent 2が完了をAgent 0に報告
controller.report_completion(from_agent=2, to_agent=0, result="...")
```

### Phase 3: 動的タスク割り当て

```python
# タスクを自動的に最適なエージェントに割り当て
controller.auto_assign_task(task="新機能実装")
# → Analyzer: 要件分析
# → Designer: 設計
# → Implementer: 実装
```

### Phase 4: Cross構造による学習

```python
# ルーティング履歴から最適なパターンを学習
routing_layer.learn_patterns()

# "2番のエージェント"を頻繁に呼ぶ
# → 次回から自動的に優先度を上げる
```

## まとめ (Summary)

**実装完了機能:**
- ✅ Crossルーティング層（最上位情報制御）
- ✅ エージェント番号認識（"2番のエージェント"）
- ✅ コマンドタイプ検出（query/command/broadcast）
- ✅ 進捗情報Cross構造（タスク・サブタスク・進捗率）
- ✅ マスター・サブ階層構造
- ✅ インテリジェントルーティング
- ✅ 進捗集約と送信
- ✅ ルーティング履歴保存

**アーキテクチャ:**
```
Cross Routing Layer (最上位)
        ↓
Master Agent (Agent 0) ← 全体統括
        ↓
Sub-Agents (Agent 1, 2, 3, ...) ← 実作業
        ↓
Cross Structures (進捗記録)
```

**次回起動時:**
```bash
verantyx chat
  ↓
Multi-Agent選択
  ↓
3エージェント起動
  ↓
Hierarchy:
  Agent 0 (Master) ← Controls all
  Agent 1 (Analyzer) ← Controlled by Master
  Agent 2 (Designer) ← Controlled by Master
  ↓
"2番のエージェントの進捗は？"
  ↓
Crossルーティング層が検出 ✅
  ↓
Agent 0に進捗情報付きで送信 ✅
Agent 2にも送信 ✅
  ↓
両方が応答 ✅
```

---

生成日時: 2026-03-08
実装内容: 階層化マルチエージェント + Crossルーティング層
ステータス: 完了
新機能: マスター制御、番号認識、進捗追跡、情報統括
