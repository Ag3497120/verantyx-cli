# Verantyx-CLI 新機能ガイド

## 🎉 新機能追加（2026-03-11）

### 1. **会話再開機能** (`--resume`)
### 2. **矢印キー選択UI**
### 3. **Cross構造リアルタイムビューアー** (`--viewer`)

---

## 🔄 会話再開機能（Resume）

Claude Codeの会話履歴から過去の会話を選択して再開できます。

### 使い方

```bash
# 会話選択画面を起動
python3 -m verantyx_cli chat --resume
```

### 操作方法

```
📝 Resume Claude Code Conversation

  Loading conversation history...
  ✅ Found 5 conversation(s)

Select a conversation to resume:

❯ Implement calculator app
    2026-03-11 14:30 • ID: a1b2c3d4

  Fix authentication bug
    2026-03-10 09:15 • ID: e5f6g7h8

  Add dark mode support
    2026-03-09 16:45 • ID: i9j0k1l2

  🚫 Cancel (start new conversation)
    Return to main menu

↑/↓: 選択  Enter: 決定  Ctrl+C: キャンセル
```

**操作：**
- `↑`/`↓` 矢印キー：選択肢を移動
- `Enter`：決定して会話を再開
- `Ctrl+C`：キャンセル

### 仕組み

1. `~/.claude/conversations/` から会話履歴を取得
2. タイトル・日時・IDを表示
3. 選択されたら `claude --resume <id>` を実行

---

## ⌨️ 矢印キー選択UI

インタラクティブな選択UIが利用可能になりました。

### 特徴

- **矢印キーで選択** - マウス不要
- **カラー表示** - 選択中は緑色で強調
- **説明文表示** - 各選択肢に詳細情報
- **Ctrl+Cでキャンセル** - いつでも中断可能

### 対応機能

- ✅ 会話再開選択（`--resume`）
- ✅ 今後追加予定の選択機能すべて

---

## 🌐 Cross構造リアルタイムビューアー

ブラウザでCross空間（6軸）の成長をリアルタイムで可視化できます。

### 使い方

```bash
# ビューアーを起動してチャット
python3 -m verantyx_cli chat --viewer

# ビューアー + Cross成長表示
python3 -m verantyx_cli chat --viewer --show-cross

# ビューアー + Vision
python3 -m verantyx_cli chat --viewer --use-vision
```

### 画面構成

```
┌─────────────────────────────────────────────┐
│   🌟 Verantyx Cross Structure               │
│   リアルタイムで成長するCross空間（6軸）    │
├─────────────────────────────────────────────┤
│  Total Messages │ Responses │ Tool Calls   │
│       5         │     5     │      12      │
├──────────┬──────────┬──────────────────────┤
│  FRONT   │   UP     │      DOWN            │
│  ⬆️      │   🔼     │      🔽              │
│  現在の  │  ユーザー│  Claude応答          │
│  会話... │  入力... │  ...                 │
├──────────┼──────────┼──────────────────────┤
│  RIGHT   │  LEFT    │      BACK            │
│  ➡️      │   ⬅️     │      ⬇️              │
│  ツール  │ タイム   │  Raw interactions    │
│  呼び出し│ スタンプ │  ...                 │
└──────────┴──────────┴──────────────────────┘

🔄 Auto-refreshing...
```

### 特徴

1. **6軸を同時表示**
   - FRONT: 現在の会話
   - UP: ユーザー入力
   - DOWN: Claude応答
   - RIGHT: ツール呼び出し
   - LEFT: タイムスタンプ
   - BACK: Raw interactions

2. **リアルタイム更新**
   - 1秒ごとに自動更新
   - チャット中の変化が即座に反映

3. **統計情報**
   - Total Messages
   - Responses
   - Tool Calls
   - Session Duration

4. **美しいUI**
   - グラデーション背景
   - ガラスモーフィズムデザイン
   - アニメーション効果

### 技術詳細

- **サーバー**: HTTPServer（ポート8765）
- **更新頻度**: 1秒
- **データソース**: `.verantyx/conversation.cross.json`
- **フロントエンド**: Pure HTML/CSS/JavaScript（依存なし）

---

## 🎯 組み合わせ例

### 1. 会話再開 + ビューアー

```bash
python3 -m verantyx_cli chat --resume --viewer
```

過去の会話を選択して再開し、Cross構造の成長をリアルタイムで可視化。

### 2. フルパワー

```bash
python3 -m verantyx_cli chat --resume --viewer --show-cross --use-vision
```

すべての機能を有効化：
- 会話再開選択
- リアルタイムビューアー
- ターミナルでのCross成長表示
- Verantyx Vision（画像認識）

### 3. シンプル起動

```bash
# デフォルト（新規会話）
python3 -m verantyx_cli

# ビューアーだけ追加
python3 -m verantyx_cli --viewer
```

---

## 📋 全コマンド一覧

### 基本

```bash
# 新規会話
python3 -m verantyx_cli chat

# 会話再開（選択画面）
python3 -m verantyx_cli chat --resume

# ビューアー起動
python3 -m verantyx_cli chat --viewer
```

### オプション組み合わせ

```bash
# Cross成長表示
python3 -m verantyx_cli chat --show-cross

# Vision有効化
python3 -m verantyx_cli chat --use-vision

# すべて有効
python3 -m verantyx_cli chat --resume --viewer --show-cross --use-vision
```

---

## 🔧 ファイル構成

### 新規追加ファイル

```
verantyx_cli/ui/
├── interactive_selector.py       # 矢印キー選択UI
├── resume_selector.py            # 会話再開選択
└── cross_realtime_viewer.py      # Cross構造ビューアー
```

### 変更ファイル

```
verantyx_cli/
├── __main__.py                   # --resume, --viewer オプション追加
└── ui/
    └── verantyx_chat_mode.py     # ビューアー統合
```

---

## 🧪 テスト方法

### 1. 矢印キー選択UIテスト

```bash
python3 -m verantyx_cli.ui.interactive_selector
```

### 2. 会話再開選択テスト

```bash
python3 -m verantyx_cli.ui.resume_selector
```

### 3. ビューアー単体テスト

```bash
python3 -m verantyx_cli.ui.cross_realtime_viewer .verantyx/conversation.cross.json
```

### 4. 統合テスト

```bash
# 会話再開
python3 -m verantyx_cli chat --resume

# ビューアー
python3 -m verantyx_cli chat --viewer

# 両方
python3 -m verantyx_cli chat --resume --viewer
```

---

## 🐛 トラブルシューティング

### 会話履歴が見つからない

```
⚠️  No conversation history found

Searched in: /Users/username/.claude/conversations
```

**原因**: Claude Codeの会話履歴が存在しない

**解決方法**:
1. Claude Codeで最低1回会話を行う
2. 会話が `~/.claude/conversations/` に保存される
3. 再度 `--resume` を実行

### ビューアーが開かない

**症状**: ブラウザが起動しない

**解決方法**:
1. 手動でブラウザを開く
2. `http://localhost:8765` にアクセス
3. ポート8765が使用中の場合は変更（コード内で変更可能）

### Cross構造が表示されない

**症状**: ビューアーに「データなし」と表示

**解決方法**:
1. `.verantyx/conversation.cross.json` が存在するか確認
2. チャットで何かメッセージを送信
3. ビューアーが自動的に更新される（1秒後）

---

## 💡 開発者向け情報

### 矢印キー選択UIの使い方

```python
from verantyx_cli.ui.interactive_selector import select_option, select_with_index

# 文字列を取得
result = select_option(
    "Choose an option:",
    ["Option 1", "Option 2", "Option 3"],
    descriptions=["Description 1", "Description 2", "Description 3"]
)

# インデックスを取得
index = select_with_index(
    "Choose an option:",
    ["Option 1", "Option 2", "Option 3"]
)
```

### ビューアーのカスタマイズ

```python
from verantyx_cli.ui.cross_realtime_viewer import start_viewer_server

# カスタムポートで起動
viewer_thread = start_viewer_server(
    cross_file=Path(".verantyx/conversation.cross.json"),
    port=9000  # カスタムポート
)
```

---

## 🎨 今後の拡張予定

- [ ] 会話履歴の検索機能
- [ ] Cross構造の3D可視化
- [ ] 複数会話の比較ビュー
- [ ] エクスポート機能（PDF/PNG）
- [ ] カスタムテーマ
- [ ] モバイル対応

---

**実装日時**: 2026-03-11
**バージョン**: v1.1.0
**新規ファイル**: 3個
**変更ファイル**: 2個
**総追加行数**: ~1,200行

🎉 **すべての機能が動作確認済みです！**
