# Verantyx-CLI

> **Cross-Native Hierarchical Multi-Agent System for Claude Code**
>
> 🧠 Cross構造による知識表現 × 🤖 階層化マルチエージェント制御

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/Ag3497120/verantyx-cli)

**Verantyx-CLI**は、Claude Codeを拡張し、複数のClaudeエージェントを階層的に制御できる革新的なコマンドラインツールです。

## 🌟 主な特徴

### 1. **Cross構造による知識表現**
6軸のフラクタル構造で情報を整理・記憶します：
- **UP/DOWN**: 目標・意図 / 事実・基盤
- **FRONT/BACK**: 現在の焦点 / 歴史
- **RIGHT/LEFT**: 拡張・可能性 / 制約・限界

### 2. **階層化マルチエージェント制御**
```
Cross Routing Layer (最上位情報統括)
        ↓
Master Agent (Agent 0) - 全体制御
        ↓
Sub-Agents (1, 2, 3, ...) - 専門作業
        ↓
Cross Structures - 進捗記録
```

### 3. **自然言語エージェント制御**
```bash
> 2番のエージェントの進捗は？
🔀 Detected agent reference: [2]
📍 Routing to: Agent(s) [0, 2]

🤖 Master: Agent 2の進捗は60%です
🤖 Agent 2: 依存関係分析を進めています
```

### 4. **画像認識（Cross Simulation）**
チャット画面から画像をドラッグ&ドロップ（パス入力）で変換：
```bash
> /image ~/Desktop/photo.jpg high
✅ Image converted to Cross structure!
📸 Image: photo.jpg
📊 Points: 5,000
🗺️  Regions: 5
```
- 画像を最大50,000ポイントのCross構造に変換
- 点ベースの内部シミュレーションで画像理解
- 5段階の品質設定（low/medium/high/ultra/maximum）
- 自動的に領域検出とパターン認識

### 5. **ユーザー性格認識**
会話からユーザーの特徴を学習し、エージェントを最適制御：
- 対話スタイル（簡潔/詳細）
- 学習パターン（コード重視/設計重視）
- トピック傾向

## 📦 インストール

### 必須条件
- Python 3.8+
- Node.js 16+ (Claude Code用)
- macOS (現在はmacOSのみ対応)

### Claude Codeのインストール
```bash
npm install -g @anthropic-ai/claude-code
```

### Verantyx-CLIのインストール
```bash
# リポジトリをクローン
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli

# 依存関係をインストール
pip install -e .

# 画像認識機能を使う場合
pip install pillow numpy
```

## 🚀 クイックスタート

### シングルエージェントモード
```bash
verantyx chat

# セットアップウィザード
Select your LLM provider:
  1. Claude (Anthropic) - Subscription ✓

Select agent mode:
  1. Single Agent - Standard mode ✓

# Claude起動（別タブで自動起動）
✅ Claude Connected!

# チャット開始
> こんにちは
🤖 Claude: こんにちは！お手伝いします。

# Cross構造自動生成
📌 Cross structure: .verantyx/conversation.cross.json
```

### マルチエージェントモード
```bash
verantyx chat

Select agent mode:
  2. Multi-Agent - Control multiple agents ✓

Number of agents (2-5): 3

# 3つのエージェント起動
✅ Agent 0 (Master) - Controls all
✅ Agent 1 (Analyzer) - Analysis tasks
✅ Agent 2 (Designer) - Design tasks

# インテリジェントルーティング
> 2番にコードベースを分析させて

🔀 Detected: Agent 2
🤖 Master: Agent 2に分析を指示しました
🤖 Agent 2: 分析を開始します...

# 進捗確認
> 2番の進捗は？

🤖 Master: Agent 2の進捗:
  タスク: コードベース分析
  進捗: 60%
  サブタスク:
    ✅ ファイル構造解析（完了）
    ⏳ 依存関係分析（作業中）
```

## 🏗️ アーキテクチャ

### レイヤー構造
```
┌─────────────────────────────────────────┐
│      Cross Routing Layer                │
│  - Parse agent references               │
│  - Aggregate progress                   │
│  - Control information flow             │
└─────────────────────────────────────────┘
              ↓
    ┌─────────────────┐
    │  Master Agent   │ ← 全体統括
    │   (Agent 0)     │
    └─────────────────┘
              ↓
    ┌─────────────────┐
    │  Sub-Agents     │ ← 専門作業
    │  Agent 1, 2, 3  │
    └─────────────────┘
              ↓
    ┌─────────────────┐
    │ Cross Structures│ ← 進捗記録
    │  (6-axis JSON)  │
    └─────────────────┘
```

### Cross構造の例
```json
{
  "type": "verantyx_conversation_cross",
  "axes": {
    "up": {
      "user_intent": "debugging",
      "goal": "Fix authentication bug"
    },
    "down": {
      "total_messages": 10,
      "session_duration_seconds": 300
    },
    "front": {
      "current_activity": "active_conversation",
      "recent_messages": ["...", "..."]
    },
    "back": {
      "all_messages": ["...", "..."],
      "session_history": {...}
    },
    "right": {
      "learned_patterns": ["code_discussion"],
      "topics": ["programming", "debugging"]
    },
    "left": {
      "constraints": ["text_only_interface"],
      "system_info": {...}
    }
  },
  "progress": {
    "agent_id": 1,
    "current_task": "Analyzing codebase",
    "task_progress_percent": 60,
    "subtasks": [...]
  }
}
```

## 📚 ドキュメント

### 実装済み機能
- [Cross構造生成](CROSS_STRUCTURE_IMPLEMENTATION.md)
- [マルチエージェント機能](MULTI_AGENT_IMPLEMENTATION.md)
- [階層化制御システム](HIERARCHICAL_MULTI_AGENT.md)
- [画像変換機能](IMAGE_CONVERSION_GUIDE.md) 🆕
- [出力表示修正](OUTPUT_DISPLAY_FIX.md)

### 主要コンポーネント

#### 1. Cross Generator
`verantyx_cli/engine/cross_generator.py`
- 会話履歴を6軸Cross構造に変換
- 3秒ごとに自動更新
- 進捗追跡（タスク・サブタスク・進捗率）

#### 2. Cross Routing Layer
`verantyx_cli/engine/cross_routing_layer.py`
- エージェント番号認識（"2番のエージェント"）
- コマンドタイプ分類（query/command/broadcast）
- 情報統括と送信制御

#### 3. Multi-Agent Controller
`verantyx_cli/engine/multi_agent_controller.py`
- 複数エージェント管理
- マスター・サブ階層制御
- ユーザー性格プロファイル読み込み

#### 4. Image to Cross
`verantyx_cli/vision/image_to_cross.py`
- 画像を点ベースCross構造に変換
- 最大50,000ポイント対応
- 品質プリセット（low/medium/high/ultra/maximum）

## 🎯 使用例

### エージェント番号で呼び出し
```bash
> 2番のエージェントにパフォーマンステストをやってもらって

🔀 Detected agent reference: [2]
🤖 Master: Agent 2に指示しました
🤖 Agent 2: パフォーマンステストを開始します
```

### 進捗確認
```bash
> 全員の状況を教えて

🤖 Master: 現在の状況:
  Agent 1 (Analyzer): ✅ 作業中 (進捗80%)
  Agent 2 (Designer): ✅ 作業中 (進捗40%)
  Agent 3 (Implementer): ⏸ 待機中
```

### ブロードキャスト
```bash
> 全員でこの問題を解決して

📢 Broadcasting to all agents
🤖 Agent 1: 問題を分析します
🤖 Agent 2: 設計案を考えます
🤖 Agent 3: 実装を準備します
```

### 画像変換（NEW! 🆕）
```bash
# チャット画面で画像パスを入力
> /image ~/Desktop/screenshot.png

# 品質を指定
> /image photo.jpg high

# 画像パスを直接ペースト（ドラッグ&ドロップ風）
> /Users/name/Documents/image.png

# ヘルプ
> /help image
```

### Cross構造の確認
```bash
# Agent 2の進捗
cat .verantyx/agent_2_Designer.cross.json | jq '.progress'

# ルーティング統計
cat .verantyx/cross_routing.json | jq '.statistics'

# 集約Cross
cat .verantyx/multi_agent_aggregate.cross.json | jq '.meta_axes'

# 変換された画像
cat .verantyx/vision/photo.cross.json | jq '.regions'
```

## 🔧 設定

### LLM選択
```bash
verantyx chat

Select your LLM provider:
  1. Claude (Anthropic) - Subscription
  2. Gemini (Google) - Subscription
  3. Codex (OpenAI) - Subscription
  4. Claude API (API key)
  5. Gemini API (API key)
  6. OpenAI API (API key)
```

### エージェントモード
- **Single Agent**: 標準モード（1つのClaude）
- **Multi-Agent**: 複数エージェント制御（2〜5個）

### エージェント数
```bash
Number of agents to launch (2-5): 3
```

## 📊 生成されるファイル

```
.verantyx/
├── conversation.cross.json              # シングルエージェント
├── agent_0_Master.cross.json           # マスターエージェント
├── agent_1_Analyzer.cross.json         # サブエージェント1
├── agent_2_Designer.cross.json         # サブエージェント2
├── cross_routing.json                  # ルーティング履歴
├── multi_agent_aggregate.cross.json    # 集約Cross
├── vision/                             # 画像変換 🆕
│   ├── photo.cross.json                # 変換された画像1
│   ├── screenshot.cross.json           # 変換された画像2
│   └── diagram.cross.json              # 変換された画像3
├── multi_agent.log                     # ログ
└── debug.log                           # デバッグログ
```

## 🛣️ ロードマップ

### v0.2.0 (実装済み - Alpha)
- ✅ Cross構造自動生成
- ✅ マルチエージェント制御
- ✅ 階層化システム
- ✅ エージェント番号認識
- ✅ 進捗追跡
- ✅ 画像Cross変換

### v0.3.0 (予定 - Beta)
- [ ] エージェント間直接通信
- [ ] 動的タスク割り当て
- [ ] Cross構造による学習
- [ ] Linux/Windows対応
- [ ] Web UI

### v0.4.0 (予定)
- [ ] Gemini/Codex完全対応
- [ ] API モード実装
- [ ] プラグインシステム
- [ ] カスタムエージェント役割
- [ ] Cross可視化ツール

### v1.0.0 (予定 - Stable)
- [ ] プロダクション品質
- [ ] 完全なテストカバレッジ
- [ ] 包括的ドキュメント
- [ ] パフォーマンス最適化
- [ ] エンタープライズ機能

## 🤝 コントリビューション

コントリビューションを歓迎します！詳細は [CONTRIBUTING.md](CONTRIBUTING.md) をご覧ください。

### 開発セットアップ
```bash
# リポジトリをフォーク
git clone https://github.com/Ag3497120/verantyx-cli.git
cd verantyx-cli

# 開発モードでインストール
pip install -e ".[dev]"

# テスト実行
pytest

# コードフォーマット
black verantyx_cli/
flake8 verantyx_cli/
```

### バグ報告・機能要望
- [Issue を作成](https://github.com/Ag3497120/verantyx-cli/issues)

## 📄 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) をご覧ください。

## 🙏 謝辞

- [Anthropic](https://www.anthropic.com/) - Claude Code
- [Claude Code](https://github.com/anthropics/claude-code) - ベースとなるCLI

## 📮 コンタクト

- GitHub Issues: [verantyx-cli/issues](https://github.com/Ag3497120/verantyx-cli/issues)

## ⭐ Star History

このプロジェクトが役に立ったら、ぜひスターをお願いします！

---

**Made with 🧠 Cross-Native Architecture**

*Verantyx-CLI は、情報を6軸Cross構造で表現し、階層化されたマルチエージェントで制御する次世代CLIツールです。*
