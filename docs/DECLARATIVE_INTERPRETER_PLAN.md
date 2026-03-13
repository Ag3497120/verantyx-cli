# 宣言型.jcrossインタープリタ実装計画

## 目標

現在のjcross_interpreter.pyを拡張し、宣言型構文（`$=`, `SPACE`, `~>`, `WHERE`）をサポートする。

## 実装フェーズ

### Phase 1: 等価宣言パーサー（`$=`演算子）

**目的**: `x $= expression` を解析し、等価関係として記録する。

**実装**:

```python
class DeclarativeJCrossInterpreter(JCrossInterpreter):
    def __init__(self):
        super().__init__()
        self.equivalences = []  # 等価関係のリスト
        self.spaces = {}        # SPACE宣言のリスト
        self.constraints = []   # WHERE制約のリスト

    def parse_equivalence(self, line: str):
        """
        x $= expression を解析

        例: pattern.position $= EQUILIBRIUM WHERE { ... }
        """
        match = re.match(r'([^\$]+)\$=\s*(.+)', line)
        if match:
            lhs = match.group(1).strip()  # 左辺
            rhs = match.group(2).strip()  # 右辺

            self.equivalences.append({
                'lhs': lhs,
                'rhs': rhs,
                'type': 'equality',
                'dependencies': self._extract_dependencies(rhs)
            })
```

**データ構造**:

```python
equivalence = {
    'lhs': 'x',
    'rhs': 'f(y, z)',
    'type': 'equality',
    'dependencies': ['y', 'z']
}
```

### Phase 2: 空間宣言パーサー（`SPACE`ブロック）

**目的**: `SPACE name { ... }` を解析し、空間として記録する。

**実装**:

```python
def parse_space_declaration(self, code: str):
    """
    SPACE patterns { ... } を解析

    空間内の全要素を同時に存在するものとして扱う
    """
    pattern = r'SPACE\s+(\w+)\s*\{(.*?)\}'
    matches = re.finditer(pattern, code, re.DOTALL)

    for match in matches:
        space_name = match.group(1)
        space_body = match.group(2)

        # 空間内の等価宣言を解析
        elements = self._parse_space_elements(space_body)

        self.spaces[space_name] = {
            'type': 'space',
            'elements': elements,
            'simultaneous': True  # 全要素が同時に存在
        }
```

**データ構造**:

```python
spaces = {
    'patterns': {
        'type': 'space',
        'elements': {
            'github': {...},
            'todo': {...},
            'question': {...}
        },
        'simultaneous': True
    }
}
```

### Phase 3: 空間変換パーサー（`~>`演算子）

**目的**: `A ~> B WHERE { ... }` を解析し、空間変換として記録する。

**実装**:

```python
def parse_spatial_transformation(self, line: str):
    """
    patterns ~> resonances WHERE { ... } を解析

    空間から空間への写像を表現
    """
    match = re.match(r'(\w+)\s*~>\s*(\w+)\s+WHERE\s*\{(.+)\}', line, re.DOTALL)
    if match:
        source_space = match.group(1)
        target_space = match.group(2)
        constraints = match.group(3)

        transformation = {
            'type': 'spatial_transformation',
            'source': source_space,
            'target': target_space,
            'constraints': self._parse_constraints(constraints)
        }

        self.transformations.append(transformation)
```

**データ構造**:

```python
transformation = {
    'type': 'spatial_transformation',
    'source': 'patterns',
    'target': 'resonances',
    'constraints': [
        {'lhs': 'resonance.score', 'rhs': 'DOT_PRODUCT(input, pattern)'}
    ]
}
```

### Phase 4: 制約充足ソルバー（CSP Solver）

**目的**: 等価関係と制約を同時に満たす解を見つける。

**実装**:

```python
class ConstraintSatisfactionSolver:
    """制約充足問題（CSP）ソルバー"""

    def __init__(self, equivalences, constraints):
        self.equivalences = equivalences
        self.constraints = constraints
        self.variables = {}

    def solve(self):
        """
        等価関係と制約を同時に満たす変数の値を計算

        アルゴリズム:
        1. 依存グラフを構築
        2. トポロジカルソートで解決順序を決定
        3. 順に評価していく
        """
        # 依存グラフ構築
        dep_graph = self._build_dependency_graph()

        # トポロジカルソート
        eval_order = self._topological_sort(dep_graph)

        # 順に評価
        for var_name in eval_order:
            eq = self._find_equivalence(var_name)
            if eq:
                value = self._evaluate_expression(eq['rhs'], self.variables)
                self.variables[var_name] = value

        return self.variables

    def _build_dependency_graph(self):
        """等価関係の依存グラフを構築"""
        graph = {}
        for eq in self.equivalences:
            lhs = eq['lhs']
            deps = eq['dependencies']
            graph[lhs] = deps
        return graph

    def _topological_sort(self, graph):
        """トポロジカルソート（Kahn's algorithm）"""
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for dep in graph[node]:
                if dep in in_degree:
                    in_degree[dep] += 1

        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result
```

### Phase 5: Neural Engine バックエンド（行列演算）

**目的**: 空間変換をNumPy行列演算に変換し、Neural Engineで実行する。

**実装**:

```python
class NeuralEngineBackend:
    """Neural Engine（M1 Max NPU）バックエンド"""

    def __init__(self):
        import numpy as np
        self.np = np

    def compile_spatial_transformation(self, transformation):
        """
        空間変換をNumPy行列演算にコンパイル

        例:
          patterns ~> resonances WHERE {
              score $= DOT_PRODUCT(input, pattern.keywords)
          }

        → NumPy:
          pattern_matrix = np.array([p.keywords_vector for p in patterns])
          resonances = pattern_matrix @ input_vector
        """
        source_space = transformation['source']
        target_space = transformation['target']
        constraints = transformation['constraints']

        # パターンベクトル化
        if 'DOT_PRODUCT' in str(constraints):
            # 行列積として実装
            def execute(source_data, input_vector):
                # source_data: List[Pattern]
                # input_vector: np.array

                # パターンをベクトル化
                pattern_vectors = self.np.array([
                    self._vectorize_keywords(p['keywords'])
                    for p in source_data
                ])

                # 行列積で全パターンの共鳴度を一度に計算
                resonances = pattern_vectors @ input_vector

                return resonances

            return execute

    def _vectorize_keywords(self, keywords):
        """キーワードリストをベクトルに変換"""
        # 簡易実装: キーワードの文字列長さの合計をベクトル化
        # 実際にはTF-IDFやword2vecを使う
        vector = [len(k) for k in keywords]
        return self.np.array(vector)
```

### Phase 6: Cross空間物理シミュレーション（Metal Performance Shaders）

**目的**: Cross空間をGPUで物理シミュレーションする。

**実装**（コンセプト）:

```python
class CrossSpacePhysicsSimulator:
    """Cross空間の物理シミュレーター（GPU実行）"""

    def __init__(self):
        # Metal Performance Shadersバックエンド
        self.use_gpu = True

    def simulate_equilibrium(self, cross_space):
        """
        Cross空間のエネルギー最小化を物理シミュレーション

        手法:
        1. 各パターンを格子ノードとして配置
        2. エネルギー関数を定義
        3. 勾配降下法で位置を更新
        4. 収束するまで反復
        """
        # 初期位置
        positions = {
            pattern_name: pattern['position']
            for pattern_name, pattern in cross_space.items()
        }

        # エネルギー最小化（GPU並列処理）
        if self.use_gpu:
            positions = self._gpu_gradient_descent(positions)
        else:
            positions = self._cpu_gradient_descent(positions)

        return positions

    def _energy_function(self, position, pattern):
        """
        位置のエネルギー関数

        理想位置からの距離^2
        """
        ideal_front_back = pattern['success_count'] / max(pattern['usage_count'], 1)
        ideal_up_down = min(pattern['usage_count'] / 100.0, 1.0)
        ideal_left_right = max(1.0 - (pattern['age_days'] / 365.0), 0.0)

        ideal_position = {
            'front_back': ideal_front_back,
            'up_down': ideal_up_down,
            'left_right': ideal_left_right
        }

        # ユークリッド距離の2乗
        energy = sum(
            (position[axis] - ideal_position[axis]) ** 2
            for axis in ['front_back', 'up_down', 'left_right']
        )

        return energy

    def _gpu_gradient_descent(self, positions):
        """GPU並列勾配降下法（Metal Performance Shaders）"""
        # TODO: Metal Performance Shadersとの統合
        # 現在はCPUフォールバック
        return self._cpu_gradient_descent(positions)

    def _cpu_gradient_descent(self, positions):
        """CPU勾配降下法"""
        learning_rate = 0.01
        max_iterations = 1000
        tolerance = 1e-6

        for iteration in range(max_iterations):
            total_energy = 0
            new_positions = {}

            for pattern_name, position in positions.items():
                # 勾配計算
                gradient = self._compute_gradient(pattern_name, position)

                # 位置更新
                new_position = {
                    axis: position[axis] - learning_rate * gradient[axis]
                    for axis in position
                }

                new_positions[pattern_name] = new_position
                total_energy += self._energy_function(new_position, ...)

            # 収束判定
            if total_energy < tolerance:
                break

            positions = new_positions

        return positions
```

## 実装ロードマップ

### Week 1: パーサー実装
- [x] Phase 1: `$=` パーサー
- [ ] Phase 2: `SPACE` パーサー
- [ ] Phase 3: `~>` パーサー
- [ ] Phase 4: `WHERE` パーサー

### Week 2: ソルバー実装
- [ ] Phase 4: CSPソルバー基本実装
- [ ] 依存グラフ構築
- [ ] トポロジカルソート
- [ ] 制約充足アルゴリズム

### Week 3: バックエンド実装
- [ ] Phase 5: NumPyバックエンド
- [ ] 行列演算への変換
- [ ] DOT_PRODUCT実装
- [ ] MAP/REDUCE実装

### Week 4: 物理シミュレーション
- [ ] Phase 6: Cross空間シミュレーター
- [ ] エネルギー関数定義
- [ ] 勾配降下法実装
- [ ] Metal Performance Shaders統合（オプション）

## テスト戦略

### Unit Tests

```python
def test_equivalence_parsing():
    """等価宣言のパースをテスト"""
    interp = DeclarativeJCrossInterpreter()
    code = "x $= 1 + 2"
    interp.parse_equivalence(code)
    assert len(interp.equivalences) == 1
    assert interp.equivalences[0]['lhs'] == 'x'
    assert interp.equivalences[0]['rhs'] == '1 + 2'

def test_space_declaration():
    """SPACE宣言のパースをテスト"""
    interp = DeclarativeJCrossInterpreter()
    code = """
    SPACE patterns {
        github $= {name: "github"}
        todo $= {name: "todo"}
    }
    """
    interp.parse_space_declaration(code)
    assert 'patterns' in interp.spaces
    assert len(interp.spaces['patterns']['elements']) == 2

def test_csp_solver():
    """CSPソルバーをテスト"""
    equivalences = [
        {'lhs': 'x', 'rhs': '1 + 2', 'dependencies': []},
        {'lhs': 'y', 'rhs': 'x * 2', 'dependencies': ['x']},
        {'lhs': 'z', 'rhs': 'y + x', 'dependencies': ['x', 'y']}
    ]
    solver = ConstraintSatisfactionSolver(equivalences, [])
    result = solver.solve()
    assert result['x'] == 3
    assert result['y'] == 6
    assert result['z'] == 9
```

### Integration Tests

```python
def test_full_declarative_execution():
    """宣言型.jcrossの完全実行をテスト"""
    interp = DeclarativeJCrossInterpreter()
    code = """
    SPACE patterns {
        github $= {keywords: ["feat:", "fix:"]}
    }

    input_wave $= {text: "feat: Add new feature"}

    resonances $= patterns ~> SPACE {
        EACH pattern ~> resonance WHERE {
            resonance.score $= COUNT_MATCHES(input_wave.text, pattern.keywords)
        }
    }
    """

    result = interp.execute(code)
    assert 'resonances' in result
    assert result['resonances'][0]['score'] > 0
```

## 期待される成果

1. **真の宣言型言語**: FOR loopなし、等価関係のみ
2. **Neural Engine統合**: 行列演算で高速実行
3. **物理シミュレーション**: Cross空間が真の格子として振動
4. **エネルギー効率**: 逐次処理なし、並列計算のみ

---

**作成日**: 2026-03-13
**ステータス**: 設計完了、実装開始準備中
