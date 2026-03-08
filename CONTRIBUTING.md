# Contributing to Verantyx-CLI

まず、Verantyx-CLIへのコントリビューションを検討していただきありがとうございます！

## 🌟 コントリビューション方法

### バグ報告

バグを見つけた場合は、[Issue](https://github.com/Ag3497120/verantyx-cli/issues)を作成してください。

**含めるべき情報:**
- バグの説明
- 再現手順
- 期待される動作
- 実際の動作
- 環境情報（OS、Pythonバージョンなど）
- エラーメッセージやログ

### 機能要望

新機能のアイデアがある場合は、Issueで提案してください。

**含めるべき情報:**
- 機能の説明
- ユースケース
- 期待される動作
- 参考になる実装例（あれば）

### プルリクエスト

コードのコントリビューションは大歓迎です！

**手順:**

1. **リポジトリをフォーク**
   ```bash
   # GitHubでフォークボタンをクリック
   ```

2. **ローカルにクローン**
   ```bash
   git clone https://github.com/Ag3497120/verantyx-cli.git
   cd verantyx-cli
   ```

3. **ブランチを作成**
   ```bash
   git checkout -b feature/your-feature-name
   # または
   git checkout -b fix/your-bug-fix
   ```

4. **開発環境をセットアップ**
   ```bash
   # 仮想環境を作成
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   # venv\Scripts\activate  # Windows

   # 開発依存関係をインストール
   pip install -e ".[dev]"
   ```

5. **変更を実装**
   - コードを変更
   - テストを追加/更新
   - ドキュメントを更新

6. **テストを実行**
   ```bash
   # 全テスト
   pytest

   # カバレッジ付き
   pytest --cov=verantyx_cli

   # コードフォーマット
   black verantyx_cli/
   flake8 verantyx_cli/
   ```

7. **コミット**
   ```bash
   git add .
   git commit -m "feat: Add feature X"

   # コミットメッセージ形式:
   # feat: 新機能
   # fix: バグ修正
   # docs: ドキュメント更新
   # style: コードフォーマット
   # refactor: リファクタリング
   # test: テスト追加/修正
   # chore: その他
   ```

8. **プッシュ**
   ```bash
   git push origin feature/your-feature-name
   ```

9. **プルリクエストを作成**
   - GitHubでプルリクエストを作成
   - 変更内容を説明
   - 関連するIssueをリンク

## 📝 コーディング規約

### Python スタイル

- **PEP 8**に準拠
- **Black**でフォーマット
- **Flake8**でリント
- **Type hints**を使用

```python
def process_message(message: str, agent_id: int) -> Dict[str, Any]:
    """
    Process a message for a specific agent.

    Args:
        message: Message content
        agent_id: Target agent ID

    Returns:
        Processed result dictionary
    """
    # Implementation
    pass
```

### ドキュメント

- すべての公開関数/クラスにdocstringを記述
- Google形式のdocstring
- 使用例を含める

### テスト

- 新機能には必ずテストを追加
- テストカバレッジ80%以上を目指す
- `pytest`を使用

```python
def test_process_message():
    """Test message processing"""
    result = process_message("test", 0)
    assert result['status'] == 'success'
```

### コミットメッセージ

**Conventional Commits形式:**

```
<type>(<scope>): <subject>

<body>

<footer>
```

**例:**
```
feat(routing): Add agent number recognition

Implement regex patterns to detect agent references like "2番のエージェント"

Closes #123
```

## 🏗️ プロジェクト構造

```
verantyx-cli/
├── verantyx_cli/           # メインパッケージ
│   ├── engine/            # コアエンジン
│   ├── ui/                # ユーザーインターフェース
│   ├── vision/            # 画像処理
│   └── utils/             # ユーティリティ
├── tests/                 # テスト
├── docs/                  # ドキュメント
├── README.md              # プロジェクト概要
└── setup.py               # セットアップスクリプト
```

## 🧪 テスト

### テストの実行

```bash
# 全テスト
pytest

# 特定のテスト
pytest tests/test_routing.py

# カバレッジレポート
pytest --cov=verantyx_cli --cov-report=html
```

### テストの書き方

```python
import pytest
from verantyx_cli.engine.cross_routing_layer import CrossRoutingLayer

def test_parse_agent_reference():
    """Test agent reference parsing"""
    routing = CrossRoutingLayer(Path(".verantyx"))

    result = routing.parse_input("2番のエージェントの進捗は？")

    assert result['target_agent'] == 2
    assert 2 in result['extracted_agent_refs']
    assert result['command_type'] == 'query'
```

## 📚 ドキュメント

### ドキュメントの更新

- 新機能を追加した場合、READMEを更新
- 使用例を追加
- 関連ドキュメント（.md）を更新

### ドキュメント作成

```bash
# 新しいドキュメントを作成
# docs/NEW_FEATURE.md
```

## 🐛 デバッグ

### ログの確認

```bash
# シングルエージェント
tail -f .verantyx/debug.log

# マルチエージェント
tail -f .verantyx/multi_agent.log
```

### デバッグモード

```python
# コード内でデバッグログを有効化
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 💡 開発のヒント

### Cross構造の理解

- [CROSS_STRUCTURE_IMPLEMENTATION.md](CROSS_STRUCTURE_IMPLEMENTATION.md)
- 6軸の意味を理解する
- `.verantyx/*.cross.json`を確認

### マルチエージェントの理解

- [HIERARCHICAL_MULTI_AGENT.md](HIERARCHICAL_MULTI_AGENT.md)
- ルーティング層の動作を理解
- マスター・サブ階層を把握

### 新しいエージェント役割の追加

```python
# terminal_ui.py
sub_agent_roles = ["Analyzer", "Designer", "Implementer", "Tester", "YourNewRole"]
```

## 🤝 コミュニティ

### コミュニケーション

- GitHub Issues: バグ報告・機能要望
- GitHub Discussions: 議論・質問
- Pull Requests: コードレビュー

### 行動規範

- 尊重: 他の貢献者を尊重する
- 包括性: すべての人を歓迎する
- 建設的: 建設的なフィードバックを提供する
- 協力的: チームで協力する

## 📋 チェックリスト

プルリクエストを作成する前に:

- [ ] コードがPEP 8に準拠している
- [ ] Blackでフォーマットした
- [ ] Flake8でリントした
- [ ] テストを追加/更新した
- [ ] すべてのテストが通る
- [ ] ドキュメントを更新した
- [ ] コミットメッセージが規約に従っている
- [ ] 変更内容をREADMEに追加した（必要な場合）

## 🚀 リリースプロセス

### バージョニング

Semantic Versioning (SemVer)に従います:
- MAJOR: 互換性のない変更
- MINOR: 後方互換性のある機能追加
- PATCH: 後方互換性のあるバグ修正

例: `v0.2.0` → `v0.3.0` (新機能追加)

### リリース手順

1. バージョン番号を更新
2. CHANGELOGを更新
3. タグを作成
4. GitHubリリースを作成
5. PyPIに公開（将来）

## 🙏 謝辞

コントリビューターの皆様に感謝します！

- すべてのコントリビューターは[CONTRIBUTORS.md](CONTRIBUTORS.md)に記載されます
- 初めての方も大歓迎です！

## 📞 質問

質問がある場合:
- [Issue](https://github.com/Ag3497120/verantyx-cli/issues)を作成
- [Discussions](https://github.com/Ag3497120/verantyx-cli/discussions)で議論

---

**Happy Contributing! 🎉**
