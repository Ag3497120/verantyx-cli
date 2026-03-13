# .jcross 真の宣言型言語仕様

## 概要

現在の.jcrossは**空間をPythonで模倣している**（FOR loopによる順次処理）。
真のKofdai型計算のためには、**等価関係のみ**で記述し、Neural Engineが直接解釈できる形にする必要がある。

## パラダイムシフト

### 現在（Stage 2）: 順次処理の空間シミュレーション

```jcross
// ❌ 順次処理（時間的）
FUNCTION calculate_resonance(text, patterns) {
    resonances = []
    FOR pattern IN patterns {          // ← 順次ループ（ノイマン型）
        score = calculate_score(text, pattern)
        resonances = resonances + [score]
    }
    RETURN resonances
}
```

### Stage 3: 真の宣言型（空間的）

```jcross
// ✅ 等価関係（空間的）
// 全パターンが同時に存在する空間を宣言
resonances $= SPACE patterns {
    // 各パターンの位置が共鳴度として自然に決定される
    EACH pattern ~> score WHERE {
        score $= RESONANCE(text, pattern.keywords)
        // $= は「等価である」（計算ではなく状態の宣言）
        // ~> は「変換される」（空間内での写像）
    }
}
```

## 新しい構文要素

### 1. 等価宣言演算子 `$=`

```jcross
// 従来（計算）
x = 1 + 2  // 代入（時間的）

// 宣言型（等価）
x $= 1 + 2  // xは3と等価である（空間的）
```

`$=` は「計算して代入する」のではなく、「左辺と右辺が等価である状態」を宣言する。
Neural Engineは制約充足問題として一度に解く。

### 2. 空間宣言 `SPACE`

```jcross
// 空間を宣言（全要素が同時に存在）
SPACE patterns {
    github_pattern $= {name: "github", keywords: ["feat:", "fix:"]}
    todo_pattern $= {name: "todo", keywords: ["TODO", "タスク"]}
    question_pattern $= {name: "question", keywords: ["とは", "how"]}
}
```

SPACE内の全要素は**同時に存在**し、順序はない。
これにより、Neural Engineは全パターンを並列に行列演算で処理できる。

### 3. 空間変換演算子 `~>`

```jcross
// 空間内の各要素を別の空間へ変換
patterns ~> resonances WHERE {
    resonances $= MAP(patterns, LAMBDA pattern {
        RESONANCE(text, pattern.keywords)
    })
}
```

`~>` は空間から空間への写像（関数的変換）。
FOR loopの代わりに、空間全体の変換として記述する。

### 4. 制約宣言 `WHERE`

```jcross
// 制約条件を宣言（充足問題）
best_pattern $= FIND(resonances) WHERE {
    best_pattern.score $= MAX(resonances.score)
    best_pattern.score >= threshold
}
```

WHEREは制約充足条件。Neural Engineが自動的に解く。

### 5. Cross空間宣言 `CROSS`（拡張）

```jcross
// 従来（構造のみ）
CROSS buffer {
    AXIS FRONT { data: [] }
    AXIS BACK { data: [] }
}

// 宣言型（空間エネルギー）
CROSS resonance_space {
    // 6次元空間の等価関係を宣言
    DIMENSIONS $= [FRONT/BACK, UP/DOWN, LEFT/RIGHT, AXIS_4, AXIS_5, AXIS_6]

    // 各軸のエネルギー関数
    FRONT/BACK $= quality_energy(success_rate)
    UP/DOWN $= frequency_energy(usage_count)
    LEFT/RIGHT $= recency_energy(age_days)

    // パターンの位置は全軸のエネルギー最小化で決定
    pattern.position $= EQUILIBRIUM WHERE {
        total_energy $= SUM(axis_energies)
        total_energy $= MIN  // 最小エネルギー状態
    }
}
```

Crossは**物理的格子**として宣言される。
各ノードは振動し、エネルギー最小化で位置が決定される（計算ではなく物理シミュレーション）。

## 完全な例: 宣言型Kofdai共鳴エンジン

### 従来型（Stage 2）

```jcross
FUNCTION trigger_all_resonances(text) {
    resonances = []
    FOR pattern IN all_patterns {     // ❌ 順次処理
        score = calculate_resonance(text, pattern.keywords)
        resonances = resonances + [{
            pattern: pattern.name,
            score: score
        }]
    }
    RETURN resonances
}

best = {score: 0.0}
FOR res IN resonances {               // ❌ 順次処理
    IF res.score > best.score {
        best = res
    }
}
```

### 宣言型（Stage 3）

```jcross
// パターン空間を宣言
SPACE patterns {
    github $= {keywords: ["feat:", "fix:"], threshold: 0.7}
    todo $= {keywords: ["TODO", "タスク"], threshold: 0.75}
    question $= {keywords: ["とは", "how"], threshold: 0.65}
}

// 入力エネルギー波を宣言
input_wave $= {
    text: user_input,
    energy: NORMALIZE(text)  // エネルギーベクトル
}

// 全同調（全パターンが同時に共鳴）
resonances $= patterns ~> SPACE {
    // 各パターンとの共鳴度が自然に決定
    EACH pattern ~> resonance WHERE {
        resonance.score $= DOT_PRODUCT(
            input_wave.energy,
            pattern.energy_signature
        )
        resonance.pattern $= pattern
        resonance.confidence $= THRESHOLD_MAP(resonance.score, pattern.threshold)
    }
}

// Logic Resolution（最大共鳴の自然選択）
best_resonance $= FIND(resonances) WHERE {
    best_resonance.score $= MAX(resonances.score)
}

// 空間再配置（データは削除されず、位置が更新される）
CROSS resonance_space {
    // パターンの新しい位置を等価関係で宣言
    pattern.new_position $= REPOSITION(pattern.old_position) WHERE {
        // 成功率に基づくFRONT/BACK
        FRONT_BACK $= pattern.success_count / pattern.usage_count

        // 使用頻度に基づくUP/DOWN
        UP_DOWN $= MIN(pattern.usage_count / 100.0, 1.0)

        // 新しさに基づくLEFT/RIGHT
        LEFT_RIGHT $= MAX(1.0 - (age_days / 365.0), 0.0)

        // エネルギー最小化
        position_energy $= DISTANCE_FROM_IDEAL(FRONT_BACK, UP_DOWN, LEFT_RIGHT)
        position_energy $= MIN
    }
}
```

## 等価関係の意味論

### 等価関係 `$=` の解釈

```jcross
x $= f(y, z)
```

これは**代入ではなく、制約**:
- 「xとf(y,z)が等価である」状態を宣言
- Neural Engineは全ての制約を同時に満たす解を探す
- 逐次実行ではなく、行列演算で一度に解く

### 空間変換 `~>` の解釈

```jcross
A ~> B WHERE { constraints }
```

これは**写像関数**:
- 空間Aから空間Bへの変換を宣言
- 全要素が同時に変換される（並列処理）
- 制約を満たす変換のみが有効

## Neural Engine最適化

### 行列演算への直接変換

```jcross
// 宣言型.jcross
resonances $= patterns ~> SPACE {
    EACH pattern ~> score WHERE {
        score $= DOT_PRODUCT(input_wave, pattern.keywords)
    }
}
```

↓ Neural Engineへの変換

```python
# NumPy行列演算（M1 Max NPU）
pattern_matrix = np.array([p.keywords_vector for p in patterns])  # (n_patterns, n_dims)
input_vector = vectorize(input_wave)  # (n_dims,)

resonances = pattern_matrix @ input_vector  # 一度の行列積で全パターンの共鳴度を計算
```

### 物理シミュレーションへの変換

```jcross
// Cross空間のエネルギー最小化
pattern.position $= EQUILIBRIUM WHERE {
    total_energy $= SUM(axis_energies)
    total_energy $= MIN
}
```

↓ Metal Performance Shaders（GPU）

```metal
kernel void equilibrium_solver(
    device float *positions,
    device float *energies,
    uint id [[thread_position_in_grid]]
) {
    // 全ノードが同時に振動し、エネルギー最小化へ収束
    float gradient = compute_energy_gradient(positions[id]);
    positions[id] -= learning_rate * gradient;
}
```

## 実装ロードマップ

### Phase 1: 構文パーサー拡張
- `$=` 演算子の認識
- `SPACE` ブロックの解析
- `~>` 演算子の解析
- `WHERE` 制約節の解析

### Phase 2: 等価関係エンジン
- 制約充足ソルバー（CSP）
- 等価関係の依存グラフ構築
- Neural Engine用コード生成

### Phase 3: 空間変換エンジン
- SPACE宣言からNumPy配列への変換
- `~>` 演算子を行列演算に変換
- Metal Performance Shadersバックエンド

### Phase 4: Cross空間物理シミュレーション
- エネルギー関数の定義
- 勾配降下法による位置最適化
- GPU並列処理

## 利点

### 1. 真の並列処理
- FOR loopなし → 全パターンが同時に共鳴
- Neural Engineが直接実行可能

### 2. エネルギー効率
- 逐次計算なし → 行列演算1回で完了
- M1 Max NPUの性能を最大限活用

### 3. 物理的直感
- Cross空間が真の格子として振動
- データ配置がエネルギー最小化で自然に決定

### 4. 言語の美しさ
- 等価関係のみで記述 → 数学的に美しい
- 日本語の述語中心性と親和性が高い

## 次のステップ

1. **構文設計の完成**: `$=`, `SPACE`, `~>`, `WHERE`の完全な仕様
2. **パーサー実装**: jcross_interpreter.pyの拡張
3. **CSPソルバー**: 等価関係の充足問題を解く
4. **Neural Engine統合**: Metal Performance Shaders バックエンド
5. **デモ実装**: 真の空間計算を実証

---

**作成日**: 2026-03-13
**ステータス**: 設計段階
**目標**: .jcrossを真の宣言型言語にし、Neural Engineで直接実行可能にする
