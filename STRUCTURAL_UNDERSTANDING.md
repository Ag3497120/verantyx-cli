# 構造的理解 vs 確率的理解

## Verantyxの言語理解アプローチ

### LLMとの根本的な違い

```
┌─────────────────────────────────────────────────────────┐
│                    LLM (Claude, GPT)                     │
├─────────────────────────────────────────────────────────┤
│  "りんごを右に動かして"                                   │
│         ↓                                                │
│  Token化 → 確率計算 → 曖昧な理解                         │
│         ↓                                                │
│  P(動かす|りんご,右) = 0.87                              │
│         ↓                                                │
│  不確実な実行 (確率的)                                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               Verantyx (Cross Structure)                 │
├─────────────────────────────────────────────────────────┤
│  "りんごを右に動かして"                                   │
│         ↓                                                │
│  Cross軸マッピング → 決定的理解                          │
│         ↓                                                │
│  りんご: Entity (UP=0.3)                                 │
│  右:     Direction (RIGHT=1.0)                           │
│  動かす: Action (RIGHT=0.5)                              │
│         ↓                                                │
│  Vector: (1.5, 0, 0.3, 0, 0, 0)                         │
│         ↓                                                │
│  確実な実行 (決定的)                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 実装: 強化された語彙システム

### 1. 語彙のCross構造マッピング

**ファイル**: `jcross_enhanced_vocabulary.py`

#### Cross構造の6軸

```python
class CrossAxis(Enum):
    RIGHT = "RIGHT"  # 移動・変換の正方向
    LEFT = "LEFT"    # 移動・変換の負方向
    UP = "UP"        # 抽象化・上位概念
    DOWN = "DOWN"    # 具体化・下位概念
    FRONT = "FRONT"  # 未来・次・前方
    BACK = "BACK"    # 過去・記憶・後方
```

#### 語彙マッピング例

```python
# 方向語彙
"右": CrossMapping(
    word="右",
    category=DIRECTION,
    axis=RIGHT,
    vector=(1, 0, 0, 0, 0, 0),  # RIGHT軸に+1
    operations=["移動", "向く", "見る"]
)

# 実体語彙
"りんご": CrossMapping(
    word="りんご",
    category=ENTITY,
    axis=UP,
    vector=(0, 0, 0.3, 0, 0, 0),  # UP軸に+0.3 (物理的実体)
    operations=["取る", "置く", "食べる"]
)

# 動作語彙
"動かす": CrossMapping(
    word="動かす",
    category=ACTION,
    axis=RIGHT,
    vector=(0.5, 0, 0, 0, 0, 0),  # RIGHT軸に+0.5
    operations=["実行"]
)

# 抽象語彙
"考え": CrossMapping(
    word="考え",
    category=ENTITY,
    axis=UP,
    vector=(0, 0, 0.8, 0, 0, 0),  # UP軸に+0.8 (抽象概念)
    operations=["思考", "整理", "共有"]
)

# 時間語彙
"記憶": CrossMapping(
    word="記憶",
    category=ENTITY,
    axis=BACK,
    vector=(0, 0, 0, 0, -0.9, 0),  # BACK軸に-0.9 (過去)
    operations=["思い出す", "保存", "忘れる"]
)
```

---

### 2. 構造的理解エンジン

```python
class StructuralUnderstanding:
    """
    確率的予測ではなく、幾何学的・構造的理解
    """

    def understand(self, japanese_text: str) -> Dict[str, Any]:
        """
        日本語を構造的に理解

        LLMとの違い:
        - Token確率ではなく、Cross軸ベクトルで表現
        - 曖昧性なし、決定的マッピング
        - 意味を幾何学的に表現
        """
        # 文を単語に分解
        mappings = self.vocab.parse_sentence(japanese_text)

        # 各単語のベクトルを合成
        vector = self.vocab.sentence_to_vector(japanese_text)

        # 主要軸を決定（最大成分）
        primary_axis = self._get_primary_axis(vector)

        return {
            "text": japanese_text,
            "vector": vector,  # 6次元ベクトル
            "primary_axis": primary_axis,
            "understanding_type": "structural"  # NOT probabilistic
        }
```

#### 実行例

```python
# 例1: 基本動作
result = engine.understand("りんごを右に動かす")
# 出力:
{
    "text": "りんごを右に動かす",
    "vector": (1.5, 0.0, 0.3, 0.0, 0.0, 0.0),
    # RIGHT=1.5 (右+動かす), UP=0.3 (りんご)
    "primary_axis": "RIGHT",
    "understanding_type": "structural"
}

# 例2: 抽象概念
result = engine.understand("考えを整理する")
# 出力:
{
    "text": "考えを整理する",
    "vector": (0.0, 0.0, 0.8, 0.0, 0.0, 0.0),
    # UP=0.8 (考え=抽象概念)
    "primary_axis": "UP",
    "understanding_type": "structural"
}

# 例3: 時間的表現
result = engine.understand("前の記憶を思い出す")
# 出力:
{
    "vector": (0.0, 0.0, 0.0, 0.0, 0.0, -0.9),
    # BACK=-0.9 (記憶=過去)
    "primary_axis": "BACK",
    "understanding_type": "structural"
}
```

---

## 実装: 操作コマンド体系

**ファイル**: `jcross_operation_commands.py`

### 71の決定的操作コマンド

#### 軸別分類

```
RIGHT軸: 25コマンド  (移動・変換)
LEFT軸:  0コマンド   (RIGHT軸の負方向)
UP軸:    6コマンド   (抽象化)
DOWN軸:  17コマンド  (具体化・階層)
FRONT軸: 3コマンド   (未来・計画)
BACK軸:  20コマンド  (記憶・過去)
```

#### カテゴリ別分類

```
movement:       15コマンド  (移動操作)
transformation: 10コマンド  (変換操作)
abstraction:    12コマンド  (抽象化操作)
hierarchy:      11コマンド  (階層操作)
temporal:       12コマンド  (時間操作)
memory:         11コマンド  (記憶操作)
```

---

### コマンド例

#### RIGHT/LEFT軸 (移動・変換)

```
移動系:
- 右に移動 (move_right)
- 左に移動 (move_left)
- 右にスライド (slide_right)
- 右にジャンプ (jump_right)
- 右に回転 (rotate_right)
- 左右反転 (flip_horizontal)

変換系:
- 文字列に変換 (to_string)
- 数値に変換 (to_number)
- JSONに変換 (to_json)
- JSONから変換 (from_json)
- UTF-8にエンコード (encode_utf8)
```

#### UP/DOWN軸 (抽象化・階層)

```
抽象化系 (UP):
- 一般化 (generalize)
- カテゴリ化 (categorize)
- パターン抽出 (extract_pattern)
- 上位概念を取得 (get_superclass)
- 最上位概念を取得 (get_root_concept)

具体化系 (DOWN):
- 具体化 (concretize)
- インスタンス化 (instantiate)
- 例を生成 (generate_example)
- 下位概念を取得 (get_subclass)

階層系:
- 階層を作る (create_hierarchy)
- 親を取得 (get_parent)
- 子を取得 (get_children)
- 葉を全取得 (get_leaves)
- 上に登る (climb_up)
- 下に降りる (climb_down)
```

#### FRONT/BACK軸 (時間・記憶)

```
未来系 (FRONT):
- 次を取得 (get_next)
- 予測 (predict)
- 計画 (plan)
- 先を見る (look_ahead)
- シミュレート (simulate)

過去系 (BACK):
- 前を取得 (get_previous)
- 思い出す (recall)
- 歴史を取得 (get_history)
- 過去を見る (look_back)
- 分析 (analyze)

記憶系:
- 記憶する (memorize)
- 長期記憶に保存 (save_long_term)
- 短期記憶に保存 (save_short_term)
- 記憶を検索 (search_memory)
- 類似記憶を検索 (find_similar_memory)
- 記憶を整理 (organize_memory)
```

---

## LLMとの比較

### 例: "赤いりんごを箱の上に置く"

#### LLMの理解 (確率的)

```
Input: "赤いりんごを箱の上に置く"
       ↓ Tokenize
Token IDs: [1234, 5678, 9012, 3456, 7890, ...]
       ↓ Transformer
Hidden states: [0.234, -0.567, 0.891, ...]
       ↓ Probability
P(置く|赤い,りんご,箱,上) = 0.92
P(入れる|赤い,りんご,箱,上) = 0.05
P(載せる|赤い,りんご,箱,上) = 0.02
       ↓ Sample
Action: "置く" (確率92%)
```

**問題点**:
- 確率なので不確実
- 内部表現が不透明
- 幾何学的意味なし
- 操作が曖昧

#### Verantyxの理解 (構造的)

```
Input: "赤いりんごを箱の上に置く"
       ↓ Cross Mapping
Components:
  赤い:   Property  (RIGHT=0.8)
  りんご: Entity    (UP=0.3)
  箱:     Entity    (UP=0.4)
  の上に: Relation  (UP=0.6)
  置く:   Action    (DOWN=-0.5)
       ↓ Vector Synthesis
Total Vector: (0.8, 0, 1.3-0.5, 0, 0, 0)
            = (0.8, 0, 0.8, 0, 0, 0)
       ↓ Interpretation
Primary Axis: UP (抽象度0.8)
Action: 置く (DOWN方向, 具体化)
Target: りんご (UP=0.3) → 箱の上 (UP=0.4+0.6=1.0)
       ↓ Execute
JCross Code:
  取り出す りんご  # UP軸エンティティ
  取り出す 箱      # UP軸エンティティ
  # 箱のUP方向(+0.6)に配置
  # DOWN動作(-0.5)で設置
```

**利点**:
- 決定的 (100%確実)
- 内部表現が明確 (6軸ベクトル)
- 幾何学的意味あり
- 操作が明確

---

## 実用例: Claude との対話

### シナリオ: Claudeが指示を送る

```
Claude: "前の会話を思い出して、3個のアイデアを上位概念にまとめて"
```

#### LLMベースの実装 (従来)

```python
# 曖昧な理解
llm_output = llm.predict("前の会話を思い出して、3個のアイデアを上位概念にまとめて")
# → 確率的に「まとめる」操作を推測
# → 実行が不確実
```

#### Verantyxの実装 (構造的)

```python
# 1. 構造的理解
result = engine.understand("前の会話を思い出して、3個のアイデアを上位概念にまとめて")

# 出力:
{
    "vector": (0, 0, 0.8, 0, 0, -0.9),
    # BACK=-0.9 (前の会話=過去記憶)
    # UP=0.8 (上位概念=抽象化)
    "primary_axis": "BACK",
    "components": {
        "前の": BACK軸,
        "会話": BACK軸,
        "思い出して": BACK軸操作,
        "3個": 数量,
        "アイデア": UP軸エンティティ,
        "上位概念": UP軸,
        "まとめて": UP軸操作
    }
}

# 2. コマンド実行
commands = [
    "思い出す",           # BACK軸: 記憶検索
    "get_history",        # 会話履歴取得
    "filter_by_count",    # 3個選択
    "一般化",             # UP軸: 抽象化
    "categorize"          # 上位概念化
]

# 3. JCrossコード生成
jcross_code = '''
# BACK軸: 記憶から取得
実行する memory.search = {"query": "前の会話"}
入れる conversation_history
捨てる

# 3個のアイデアを抽出
取り出す conversation_history
実行する filter.top_n = {"n": 3, "type": "アイデア"}
入れる ideas
捨てる

# UP軸: 上位概念化
取り出す ideas
実行する abstraction.generalize = {}
入れる abstract_concept
捨てる

# 結果を表示
取り出す abstract_concept
表示する
'''

# 4. 確実な実行
execute_jcross(jcross_code)
```

---

## まとめ

### Verantyxの強み

| 項目 | LLM | Verantyx |
|------|-----|----------|
| **理解方式** | 確率的 | 構造的 |
| **内部表現** | Hidden states | 6軸ベクトル |
| **実行** | 不確実 | 決定的 |
| **透明性** | ブラックボックス | 完全透明 |
| **拡張性** | モデル再訓練必要 | 語彙追加のみ |
| **語彙数** | 50k+ tokens | **現在71コマンド** |

### 語彙強化の成果

```
語彙カテゴリ数: 8
- Entity (実体)
- Action (動作)
- Direction (方向)
- Property (属性)
- Relation (関係)
- Quantity (数量)
- State (状態)
- Temporal (時間)

操作コマンド数: 71
- Movement (15)
- Transformation (10)
- Abstraction (12)
- Hierarchy (11)
- Temporal (12)
- Memory (11)
```

### 次のステップ

1. **語彙拡張**: 71 → 300+ コマンド
2. **複合操作**: コマンド組み合わせ
3. **学習機能**: 新語彙の自動マッピング
4. **Neural Engine統合**: 状態埋め込みで高速化

---

## 使用方法

```python
# 構造的理解エンジン
from jcross_enhanced_vocabulary import StructuralUnderstanding

engine = StructuralUnderstanding()

# 日本語を構造的に理解
result = engine.understand("りんごを右に動かす")

print(result)
# {
#   "text": "りんごを右に動かす",
#   "vector": (1.5, 0.0, 0.3, 0.0, 0.0, 0.0),
#   "primary_axis": "RIGHT",
#   "understanding_type": "structural"  # NOT probabilistic!
# }
```

```python
# 操作コマンドライブラリ
from jcross_operation_commands import OperationCommandLibrary

lib = OperationCommandLibrary()

# コマンド検索
cmd = lib.get_command("一般化")
print(cmd.description)  # "具体例から一般概念を抽出"
print(cmd.jcross_code)  # JCrossコード

# 軸別コマンド
right_cmds = lib.get_commands_by_axis(CrossAxis.RIGHT)
# → 25コマンド (移動・変換系)

up_cmds = lib.get_commands_by_axis(CrossAxis.UP)
# → 6コマンド (抽象化系)

back_cmds = lib.get_commands_by_axis(CrossAxis.BACK)
# → 20コマンド (記憶系)
```

---

**結論**: Verantyxは確率的予測ではなく、**構造的理解**により言語を扱います。これにより決定的で透明性の高い操作が可能になります。
