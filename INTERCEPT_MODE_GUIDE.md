# Verantyx Intercept Mode - 完全ガイド

## 概要

Claude CodeのAPI通信を傍受して、Verantyxで会話を表示 + Cross構造に記録する。

**Claude Codeの操作感はそのまま、すべての会話を自動的にキャプチャ！**

## アーキテクチャ

```
Claude Code（普通に使用）
    ↓ HTTPS通信
mitmproxy（傍受）
    ↓ responses.jsonl
Verantyx Interceptor
    ├─ UIに表示
    └─ Cross構造に記録
```

## セットアップ（初回のみ）

### 1. mitmproxyインストール

```bash
pip3 install mitmproxy
```

### 2. 証明書インストール（HTTPS傍受のため）

```bash
# mitmproxyを一度起動
mitmproxy

# ブラウザで http://mitm.it にアクセス
# macOS用証明書をダウンロード＆インストール

# キーチェーンアクセスで「mitmproxy」を検索
# → 信頼設定を「常に信頼」に変更
```

## 使い方

### 🚀 自動モード（推奨）

**一発起動！**

```bash
cd /path/to/your/project
verantyx intercept
```

これだけで：
- ✅ mitmproxyがバックグラウンドで起動
- ✅ Claude Codeが新しいタブで起動（プロキシ設定済み）
- ✅ Verantyx UIが起動

すべて自動です！

### 🔧 手動モード

細かく制御したい場合：

```bash
verantyx intercept --manual
```

指示が表示されるので、手動で起動：

#### ターミナル1: mitmproxy起動

```bash
mitmproxy -s /tmp/claude_mitm.py -p 8080
```

#### ターミナル2: Claude Code起動

```bash
HTTPS_PROXY=http://localhost:8080 claude
```

#### ターミナル3: Verantyx（Enterで起動）

準備ができたらEnter押下

## 動作確認

1. **Claude Codeで会話する**
   - 普通にプロンプトを入力
   - Claudeが応答

2. **Verantyxで確認**
   - 自動的にメッセージが表示される
   - ユーザー入力とClaude応答が両方表示

3. **Cross構造確認**
   ```bash
   cat .verantyx/conversation.cross.json
   ```

## Cross構造の詳細

```json
{
  "axes": {
    "FRONT": {
      "current_conversation": [
        {"role": "user", "content": "...", "timestamp": 123456},
        {"role": "assistant", "content": "...", "timestamp": 123457}
      ]
    },
    "UP": {
      "user_inputs": [...],
      "total_messages": 10
    },
    "DOWN": {
      "claude_responses": [...],
      "total_tokens": 5000
    },
    "RIGHT": {
      "api_metadata": [...],
      "request_count": 20
    },
    "LEFT": {
      "timestamps": [...],
      "session_duration": 3600
    },
    "BACK": {
      "raw_api_data": [...]
    }
  }
}
```

### 6軸の意味

- **FRONT**: 現在の会話（時系列）
- **UP**: ユーザー入力のみ抽出
- **DOWN**: Claude応答のみ抽出
- **RIGHT**: APIメタデータ（URL、method等）
- **LEFT**: タイムスタンプ情報
- **BACK**: 生のAPIデータ（デバッグ用）

## トラブルシューティング

### 証明書エラー

```
SSL handshake failed
```

→ mitmproxyの証明書をインストールしてください

### Claude Codeが接続できない

```
Failed to connect to Claude API
```

→ `HTTPS_PROXY` 環境変数を確認してください

### mitmproxyに通信が表示されない

→ Claude Codeを `HTTPS_PROXY` 付きで起動したか確認

### Verantyxに応答が表示されない

1. mitmproxyで通信が見えているか確認
2. `/tmp/claude_responses.jsonl` にデータが書き込まれているか確認
   ```bash
   tail -f /tmp/claude_responses.jsonl
   ```
3. Verantyxのログ確認
   ```bash
   tail -f .verantyx/interceptor.log
   ```

## メリット

✅ **Claude Codeをそのまま使える** - PTY/Wrapper不要
✅ **すべての会話を記録** - Cross構造に自動保存
✅ **リアルタイム表示** - 0.1秒間隔で監視
✅ **API詳細も取得** - トークン数、メタデータ等
✅ **デバッグしやすい** - 生のAPI通信が見える

## 高度な使い方

### カスタムフィルタ

mitmproxyスクリプトを編集して特定のリクエストのみ記録：

```python
# /tmp/claude_mitm.py を編集

def response(flow: http.HTTPFlow) -> None:
    # messages APIのみ記録
    if "/v1/messages" in flow.request.pretty_url:
        # ... 記録処理
```

### 複数プロジェクト

プロジェクトごとにCross構造を分ける：

```bash
cd project1
verantyx intercept  # → .verantyx/conversation.cross.json

cd project2
verantyx intercept  # → 別のconversation.cross.json
```

## 今後の拡張

- [ ] ストリーミング応答のリアルタイム表示
- [ ] トークン数カウント
- [ ] コスト計算
- [ ] 会話の検索/フィルタ
- [ ] Cross構造のビジュアライズ

## まとめ

Intercept Modeで、Claude Codeの会話を**完全に**Verantyxで管理できます！

```bash
# 起動するだけ
verantyx intercept
```

すべて自動化されています 🚀
