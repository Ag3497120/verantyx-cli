# Cross構造 マルチプロセッサアーキテクチャ

## 概要

Cross構造の6軸を3つのプロセッサタイプに分割して並列実行する複合アーキテクチャ。

## なぜNeural Engineだけでは不十分か

### 現在の問題

```python
# Neural Engineのみの実装（失敗例）
for step in range(max_steps):
    predictions = neural_engine.predict(current_state)
    next_state = predictions['state']  # ← 常に同じ状態を返す

    # I/O結果を見ていないため、正しい遷移ができない
```

**問題点**:
1. **静的グラフ学習**: 訓練時の固定遷移パターンしか学習できない
2. **実行時情報不足**: I/O結果（`has_data`など）を条件として使えない
3. **条件分岐不可**: `0ならジャンプ`のような動的分岐ができない

### JCrossの実際の制御フロー

```jcross
ラベル MAIN_LOOP
  # I/O実行
  実行する io.socket_recv_from_var = {}
  入れる recv_result

  # 結果を取得
  取り出す recv_result
  辞書から取り出す "has_data"

  # 動的な条件分岐 ← Neural Engineはここで失敗
  0ならジャンプ MAIN_LOOP  # has_data == 0 なら戻る

  # has_data == 1 なら次に進む
  # ... メッセージ処理 ...
```

この`0ならジャンプ`は**実行時にI/O結果を見て決定**する必要がある。

---

## 解決策: CPU/GPU/Neural Engine 複合アーキテクチャ

### 3軸×3プロセッサ = 9次元の並列実行空間

```
Cross構造の6軸を3つのプロセッサペアに分割：

RIGHT/LEFT軸  → CPU (制御フロー、条件分岐)
UP/DOWN軸     → Neural Engine (状態埋め込み、パターン認識)
FRONT/BACK軸  → GPU (並列データ処理、テンソル演算)
```

### アーキテクチャ図

```
┌──────────────────────────────────────────────────────────┐
│                Cross Structure Program                    │
│                  (JCross Source)                          │
└─────────────┬────────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────┐
    │   Cross Compiler    │
    │  (Multi-target IR)  │
    └─────────┬───────────┘
              │
    ┌─────────┴─────────┐
    │  RIGHT/LEFT Axis  │  ← CPU担当
    │  • 制御フロー      │
    │  • 条件分岐        │
    │  • I/O待機         │
    └─────────┬─────────┘
              │
    ┌─────────┴─────────┐
    │   UP/DOWN Axis    │  ← Neural Engine担当
    │  • 状態埋め込み    │
    │  • パターン学習    │
    │  • 状態類似度      │
    └─────────┬─────────┘
              │
    ┌─────────┴─────────┐
    │  FRONT/BACK Axis  │  ← GPU担当
    │  • データ並列処理  │
    │  • テンソル演算    │
    │  • バッチ処理      │
    └───────────────────┘
```

---

## 実装: Hybrid Multi-Processor Executor

### 1. CPU軸: 制御フロー実行

**役割**: I/O依存の条件分岐、状態遷移の決定

```python
class CPUControlFlowExecutor:
    """
    RIGHT/LEFT軸: CPU制御フロー

    - I/O結果に基づく条件分岐
    - 実行時の状態決定
    - ソケット/PTY待機
    """

    def execute_control_flow(self, current_state, io_result):
        """
        I/O結果を見て次の状態を決定

        これはCPUでしか実現できない（動的分岐）
        """
        if current_state == State.MAIN_LOOP:
            if io_result.get('has_data'):
                return State.PROCESS_MESSAGE  # データあり → 処理
            else:
                return State.MAIN_LOOP  # データなし → 待機継続

        elif current_state == State.PROCESS_MESSAGE:
            if io_result.get('is_input_message'):
                return State.SEND_TO_CLAUDE
            else:
                return State.MAIN_LOOP

        return current_state
```

### 2. Neural Engine軸: 状態埋め込み

**役割**: 状態の意味表現、パターン認識、類似状態の発見

```python
class NeuralEngineStateEmbedding:
    """
    UP/DOWN軸: Neural Engine状態埋め込み

    - 状態をベクトル空間に埋め込み
    - 状態間の類似度計算
    - パターンマッチング
    """

    def __init__(self):
        # Core MLモデル: State → 128次元ベクトル
        self.embedding_model = self.load_coreml_embedding()

    def embed_state(self, state_id, context):
        """
        状態を高次元ベクトル空間に埋め込む

        Args:
            state_id: 状態ID
            context: 実行コンテキスト（スタック、メモリ）

        Returns:
            state_vector: 128次元の状態ベクトル
        """
        inputs = {
            'state_id': np.array([state_id], dtype=np.int32),
            'stack_summary': self._summarize_stack(context['stack']),
            'memory_summary': self._summarize_memory(context['memory'])
        }

        result = self.embedding_model.predict(inputs)
        return result['state_vector']

    def find_similar_states(self, current_vector, threshold=0.8):
        """
        類似状態を発見

        Neural Engineの強み: ベクトル類似度計算
        """
        similarities = self.embedding_model.predict({
            'query': current_vector,
            'candidates': self.all_state_vectors
        })

        return [s for s in similarities if s['score'] > threshold]
```

### 3. GPU軸: 並列データ処理

**役割**: メッセージのバッチ処理、テンソル演算

```python
class GPUDataParallelProcessor:
    """
    FRONT/BACK軸: GPU並列データ処理

    - メッセージバッチ処理
    - 画像変換並列化
    - テンソル演算
    """

    def __init__(self):
        import torch
        self.device = torch.device('mps')  # Apple Metal GPU

    def batch_process_messages(self, messages):
        """
        複数メッセージを並列処理

        GPUの強み: 大量データの並列処理
        """
        # メッセージをテンソルに変換
        message_tensors = torch.stack([
            self._message_to_tensor(msg) for msg in messages
        ]).to(self.device)

        # GPU上で並列処理
        processed = self.processing_model(message_tensors)

        return processed.cpu().numpy()

    def parallel_image_conversion(self, images):
        """
        画像→Cross変換を並列化

        Example: 100枚の画像を一度に処理
        """
        image_batch = torch.stack([
            self._load_image(img) for img in images
        ]).to(self.device)

        # GPU並列変換
        cross_structures = self.image_to_cross_model(image_batch)

        return cross_structures
```

---

## 統合実行エンジン

### Hybrid Multi-Processor Executor

```python
class CrossMultiProcessorExecutor:
    """
    CPU/GPU/Neural Engineを統合した実行エンジン

    各軸を最適なプロセッサに割り当て
    """

    def __init__(self):
        # 3つのプロセッサを初期化
        self.cpu_executor = CPUControlFlowExecutor()
        self.neural_engine = NeuralEngineStateEmbedding()
        self.gpu_processor = GPUDataParallelProcessor()

    def run(self, jcross_program):
        """
        マルチプロセッサ実行
        """
        current_state = 0
        context = self._initialize_context()

        while True:
            # 【CPU】制御フロー: 現在の状態でI/O実行
            io_result = self._execute_io(current_state, context)

            # 【Neural Engine】状態埋め込み: 状態の意味を理解
            state_vector = self.neural_engine.embed_state(
                current_state, context
            )

            # 【Neural Engine】パターン認識: 類似状態を検索
            similar_states = self.neural_engine.find_similar_states(
                state_vector
            )

            # 【CPU】条件分岐: I/O結果で次の状態を決定
            next_state = self.cpu_executor.execute_control_flow(
                current_state, io_result
            )

            # 【GPU】データ処理: メッセージがある場合は並列処理
            if io_result.get('messages'):
                processed = self.gpu_processor.batch_process_messages(
                    io_result['messages']
                )
                context['processed_messages'] = processed

            # 状態更新
            current_state = next_state

            # 終了判定
            if current_state == State.END:
                break

        return context
```

---

## 各プロセッサの役割分担

### CPU (RIGHT/LEFT軸)
| タスク | 理由 |
|--------|------|
| I/O待機 | `select()`などのシステムコール必須 |
| 条件分岐 | 実行時データに依存 |
| 状態遷移決定 | `if has_data then ...` |
| ソケット/PTY制御 | OS APIアクセス |

**Claude Wrapperの例**:
```python
# CPUでないと実現できない
if socket_has_data():  # ← 実行時チェック
    message = read_socket()
    if message.startswith("INPUT:"):  # ← 実行時分岐
        send_to_claude(message)
```

### Neural Engine (UP/DOWN軸)
| タスク | 理由 |
|--------|------|
| 状態埋め込み | 高速ベクトル演算 |
| パターン認識 | 学習済みモデル推論 |
| 状態類似度計算 | 並列ベクトル演算 |
| 意味理解 | 埋め込み空間での距離計算 |

**活用例**:
```python
# Neural Engineの強み: 意味的類似度
state_vector = embed("MAIN_LOOP")
similar = find_similar_states(state_vector)
# → ["WAIT_INPUT", "IDLE", "LISTENING"] など意味的に近い状態
```

### GPU (FRONT/BACK軸)
| タスク | 理由 |
|--------|------|
| メッセージバッチ処理 | 大量並列演算 |
| 画像変換 | テンソル演算 |
| データ前処理 | 並列マップ/フィルタ |
| テンソル演算 | 行列演算の高速化 |

**活用例**:
```python
# GPUの強み: 100個のメッセージを一度に処理
messages = receive_batch(100)
processed = gpu.parallel_process(messages)  # 並列実行
```

---

## Claude Wrapperへの適用

### 修正版アーキテクチャ

```python
class ClaudeWrapperMultiProcessor:
    """
    CPU/GPU/Neural Engineを適材適所で使う
    """

    def run(self):
        # 【CPU】初期化: I/O設定
        claude_fd = cpu_fork_claude()
        socket_fd = cpu_connect_socket()

        while True:
            # 【CPU】I/O待機: ソケット受信
            io_result = cpu_wait_for_data(socket_fd, timeout=0.1)

            if io_result.has_data:
                # 【Neural Engine】パターン認識: メッセージ分類
                message_type = neural_engine.classify_message(
                    io_result.data
                )

                # 【GPU】データ処理: メッセージ変換
                processed = gpu.process_message(io_result.data)

                # 【CPU】条件分岐: メッセージタイプで分岐
                if message_type == "INPUT":
                    cpu_send_to_claude(claude_fd, processed)

            # 【Neural Engine】状態埋め込み: 現在の状態を理解
            state_embedding = neural_engine.embed_current_state(
                socket_fd, claude_fd, context
            )

            # 【CPU】終了判定
            if cpu_should_exit(context):
                break
```

---

## 実装計画

### Phase 1: CPU制御フロー（現在）
- ✅ VM実行エンジン
- ✅ I/O依存条件分岐
- ✅ Claude Wrapper動作

### Phase 2: Neural Engine埋め込み
- [ ] 状態→ベクトル埋め込みモデル
- [ ] 状態類似度計算
- [ ] パターン認識

### Phase 3: GPU並列処理
- [ ] メッセージバッチ処理
- [ ] 画像変換GPU化
- [ ] テンソル演算最適化

### Phase 4: 統合
- [ ] 3プロセッサ同時実行
- [ ] Cross軸の動的割り当て
- [ ] 負荷バランシング

---

## まとめ

### Neural Engineが不適格だった理由
❌ **単独使用**: I/O依存の条件分岐ができない
✅ **複合使用**: 状態埋め込み・パターン認識に特化

### 複合アーキテクチャの利点

```
CPU           : 制御フロー、条件分岐 (必須)
Neural Engine : 状態理解、パターン認識 (効率化)
GPU           : データ並列処理 (高速化)
```

この3つを**Cross構造の6軸に配置**することで：
1. **CPUが制御** - I/O依存の分岐を正しく実行
2. **Neural Engineが理解** - 状態の意味を埋め込み空間で表現
3. **GPUが処理** - 大量データを並列処理

これが**真のNon-von Neumann + Cross構造**の実現です。
