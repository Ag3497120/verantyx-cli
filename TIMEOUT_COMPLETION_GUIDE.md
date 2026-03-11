# タイムアウトベース応答完成検出 - 実装ガイド

## 🎯 解決した問題

### 問題: Hugging Faceの説明が保存されない

ユーザーからの報告:
```
Hugging Face（ハギングフェイス）は、オープンソースの機械学習・AI分野におい
て世界最大級のプラットフォームを提供する...
[長い応答が表示される]

保存は表示されていません
```

**原因:**
- パズル推論だけでは不完全な文末を検出できない
- 応答の途中で出力が止まる場合に対応できない
- 文末が「。」などで終わらない応答を検出できない

---

## ✅ 解決策: ハイブリッド検出

### 2つの完成検出方式を実装

#### 方式A: パズル推論ベース（既存）
```
条件:
1. 完成度スコア >= 0.8
2. 必須ピースが全て揃っている
3. テキストが100文字以上
4. 文末が適切（。や改行で終わる）
```

**利点:** 高精度、構造的な理解
**欠点:** 不完全な文末を検出できない

#### 方式B: タイムアウトベース（新規）
```
条件:
1. 応答処理中である
2. 最後のチャンクから3秒経過
3. テキストが50文字以上
```

**利点:** どんな応答でも検出できる
**欠点:** 時間がかかる（3秒待つ）

### ハイブリッド方式
```
条件A (パズル完成) OR 条件B (タイムアウト)
→ どちらかを満たせば保存
```

**利点:**
- 完全な応答はすぐ保存（パズル検出）
- 不完全な応答も確実に保存（タイムアウト検出）
- 柔軟で堅牢

---

## 📊 動作フロー

### 1. チャンク受信時
```python
# チャンクを受信
self.last_chunk_time = time.time()  # タイマー更新

# パズル推論
prediction = self.completion_predictor.add_chunk(chunk)

if prediction['is_complete']:
    # 方式A: パズル完成で即座に保存
    save_response()
```

### 2. タイムアウト監視
```python
# 0.1秒ごとにチェック（専用ループ内）
def _check_response_timeout(self):
    if self.processing_response:
        elapsed = time.time() - self.last_chunk_time

        if elapsed >= 3.0:  # 3秒経過
            if len(assembled_text) >= 50:
                # 方式B: タイムアウトで保存
                save_response()
```

### 3. 保存タイミング

```
ケース1: 完全な応答（GitHubの説明）
├─ チャンク1-7を受信
├─ パズル完成検出
└─ → 即座に保存（0.7秒）✅

ケース2: 不完全な応答（Hugging Face）
├─ チャンク1-7を受信
├─ パズル未完成（スコア53%）
├─ 3秒待機...
└─ → タイムアウトで保存（3.7秒）✅

ケース3: 短すぎる応答（「こんにちは」のみ）
├─ チャンク1を受信（5文字）
├─ 3秒待機...
└─ → 保存しない（50文字未満）❌
```

---

## 🧪 テスト結果

### テスト1: タイムアウトシミュレーション
```bash
python3 test_timeout_completion.py
```

**結果:**
```
[Chunk 1-7] Hugging Faceの説明を段階的に追加
  Completion: 26% → 53%
  Puzzle complete? ❌ NO

⏱️  Waiting for timeout...
  Elapsed: 3.1s / 3.0s
  ✅ Timeout detected after 3.1s
  Text length: 209 chars
  → Would save to Cross structure

✅ Test PASSED
```

### テスト2: 組み合わせテスト

**ケースA: 完全な応答（GitHub）**
```
GitHubとは、Gitを使った...
[完全な説明]
→ ✅ Detected by puzzle completion
```

**ケースB: 不完全な応答（Rust）**
```
Rustとは、システムプログラミング言語で...
- ゼロコスト抽象化
- 所有権システム
[途中で終了]

Puzzle complete? False (スコア60%)
Assembled length: 74 chars
→ ✅ Would be detected by timeout
```

---

## ⚙️ 設定パラメータ

### タイムアウト秒数（調整可能）
```python
# claude_subprocess_engine.py
self.response_timeout_seconds = 3.0  # デフォルト: 3秒
```

**推奨値:**
- **1秒**: 高速だが、遅い応答を切り捨てるリスク
- **3秒**: バランスが良い（デフォルト）
- **5秒**: 安全だが、待ち時間が長い

### 最小テキスト長（調整可能）
```python
# _check_response_timeout() 内
if len(full_text.strip()) >= 50:  # デフォルト: 50文字
```

**推奨値:**
- **20文字**: 短い応答も保存（ノイズが増える）
- **50文字**: バランスが良い（デフォルト）
- **100文字**: 長い応答のみ保存（短い応答を切り捨て）

---

## 📈 パフォーマンス比較

### 従来の方式（waiting_for_input検出）
```
問題:
- 242回も誤検出
- 不安定
- 重複記録

結果: ❌ 使用不可
```

### パズル推論のみ
```
利点:
- 高精度
- 即座に検出

欠点:
- 不完全な文末を検出できない
- Hugging Faceの説明が保存されない

結果: △ 部分的に有効
```

### パズル推論 + タイムアウト（新方式）
```
利点:
- 高精度（パズル推論）
- 確実性（タイムアウト）
- 柔軟性（両方の利点）

欠点:
- タイムアウト時は3秒待つ

結果: ✅ 最適解
```

---

## 🔍 実装詳細

### 追加されたフィールド
```python
# claude_subprocess_engine.py __init__()
self.response_timeout_seconds = 3.0
self.last_chunk_time = time.time()
```

### 追加されたメソッド
```python
def _check_response_timeout(self):
    """
    タイムアウトチェック: 出力が途絶えたら応答完成と判定

    条件:
    1. 応答処理中である
    2. 組み立て済みの応答がある
    3. 最後のチャンクから指定秒数経過している
    4. 応答が十分な長さ（50文字以上）
    """
    if not self.processing_response:
        return

    elapsed = time.time() - self.last_chunk_time

    if elapsed >= self.response_timeout_seconds:
        assembled = self.completion_predictor.current_assembly.get('chunks', [])
        if assembled:
            full_text = ''.join(assembled)

            if len(full_text.strip()) >= 50:
                # 保存処理
                self._record_to_cross('assistant', full_text)
```

### 統合箇所
```python
# _output_parser_loop() 内
while self.running:
    # 出力読み取り
    readable, _, _ = select.select([self.master_fd], [], [], 0.1)

    if self.master_fd in readable:
        # データ処理
        ...

    # タイムアウトチェック（0.1秒ごと）
    self._check_response_timeout()
```

---

## 🚀 次のステップ

### 実機テスト
```bash
# ステップ1: チャットモード
python3 -m verantyx_cli chat

# 質問例
Hugging Faceとは

# 期待される動作:
# 1. 応答が表示される
# 2. 3秒後に「💾 Cross Memory: X inputs, Y responses」が表示
# 3. 応答が保存される
```

### 検証
```bash
# Cross構造を確認
python3 verify_learning.py

# 期待される出力:
# ✅ DOWN Axis (Claude Responses): 1 (重複なし)
# ✅ 応答内容が完全に記録されている
```

### スタンドアロンモード
```bash
python3 -m verantyx_cli standalone

# 質問例
Hugging Faceとは

# 期待される動作:
# 学習した内容から応答を生成
# [No match found] ではない
```

---

## 📝 まとめ

### 実装された機能
1. ✅ パズル推論ベースの完成検出（既存）
2. ✅ タイムアウトベースの完成検出（新規）
3. ✅ 両方を組み合わせたハイブリッド検出

### 保存条件
```
条件A: パズル完成（スコア >= 0.8, 必須ピース完備, 適切な文末）
条件B: タイムアウト（3秒間出力なし & 50文字以上）

→ A OR B で保存
```

### 期待される改善
- ✅ Hugging Faceのような長い応答も保存される
- ✅ 不完全な文末でも確実に保存される
- ✅ 重複記録なし（1応答 = 1エントリ）
- ✅ スタンドアロンモードで知識を活用可能

### テスト状況
```
✅ Timeout Simulation - 3秒後に正しく検出
✅ Combined Detection - パズルとタイムアウトの両立
✅ All tests PASSED
```

**実装完了。実機テストを推奨します。**
