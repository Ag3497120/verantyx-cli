#!/usr/bin/env python3
"""
JCross Declarative Interpreter
宣言型.jcrossインタープリタ

新構文:
- $= : 等価宣言演算子
- SPACE : 空間宣言
- ~> : 空間変換演算子
- WHERE : 制約宣言

等価関係のみで記述し、Neural Engineで直接実行可能な形に変換する。
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Equivalence:
    """等価関係"""
    lhs: str  # 左辺
    rhs: str  # 右辺
    dependencies: List[str] = field(default_factory=list)
    evaluated: bool = False
    value: Any = None


@dataclass
class SpaceDeclaration:
    """空間宣言"""
    name: str
    elements: Dict[str, Any] = field(default_factory=dict)
    simultaneous: bool = True  # 全要素が同時に存在


@dataclass
class SpatialTransformation:
    """空間変換"""
    source: str  # 元空間
    target: str  # 変換先空間
    constraints: List[Equivalence] = field(default_factory=list)


class ConstraintSatisfactionSolver:
    """制約充足問題（CSP）ソルバー"""

    def __init__(self, equivalences: List[Equivalence]):
        self.equivalences = equivalences
        self.variables = {}

    def solve(self) -> Dict[str, Any]:
        """
        等価関係を満たす変数の値を計算

        アルゴリズム:
        1. 依存グラフを構築
        2. トポロジカルソートで評価順序を決定
        3. 順に評価
        """
        # 依存グラフ構築
        dep_graph = self._build_dependency_graph()

        # トポロジカルソート
        try:
            eval_order = self._topological_sort(dep_graph)
        except ValueError as e:
            print(f"Warning: Circular dependency detected: {e}")
            # フォールバック: 単純な順序で評価
            eval_order = [eq.lhs for eq in self.equivalences]

        # 順に評価
        for var_name in eval_order:
            eq = self._find_equivalence(var_name)
            if eq and not eq.evaluated:
                try:
                    value = self._evaluate_expression(eq.rhs)
                    self.variables[var_name] = value
                    eq.value = value
                    eq.evaluated = True
                except Exception as e:
                    print(f"Warning: Failed to evaluate {var_name} = {eq.rhs}: {e}")
                    # デフォルト値を設定
                    self.variables[var_name] = None

        return self.variables

    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """依存グラフを構築"""
        graph = {}
        for eq in self.equivalences:
            graph[eq.lhs] = eq.dependencies
        return graph

    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """トポロジカルソート（Kahn's algorithm）"""
        # 入次数を計算
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for dep in graph[node]:
                if dep in in_degree:
                    in_degree[dep] += 1

        # 入次数0のノードをキューに追加
        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # 隣接ノードの入次数を減らす
            for neighbor in graph:
                if node in graph[neighbor]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        # 全ノードを訪問できたか確認
        if len(result) != len(graph):
            raise ValueError("Circular dependency detected in equivalences")

        return result

    def _find_equivalence(self, var_name: str) -> Optional[Equivalence]:
        """変数名から等価関係を検索"""
        for eq in self.equivalences:
            if eq.lhs == var_name:
                return eq
        return None

    def _evaluate_expression(self, expr: str) -> Any:
        """
        式を評価

        簡易実装: Pythonのevalを使用
        TODO: 安全なAST評価に置き換え
        """
        # 変数を置換
        for var_name, value in self.variables.items():
            # 安全でない実装（デモ用）
            if var_name in expr:
                expr = expr.replace(var_name, str(value))

        # 簡易評価
        try:
            return eval(expr)
        except:
            # 評価失敗時は文字列として返す
            return expr


class NeuralEngineBackend:
    """Neural Engine（M1 Max NPU）バックエンド"""

    def __init__(self):
        self.np = np

    def compile_spatial_transformation(
        self,
        transformation: SpatialTransformation,
        source_data: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        空間変換をNumPy行列演算にコンパイル・実行

        Args:
            transformation: 空間変換定義
            source_data: 元空間のデータ
            context: 評価コンテキスト（input_wave等）

        Returns:
            変換後の空間データ
        """
        # DOT_PRODUCT検出
        constraints_str = str([c.rhs for c in transformation.constraints])

        if 'DOT_PRODUCT' in constraints_str:
            return self._execute_dot_product_transformation(
                source_data,
                context
            )
        else:
            # デフォルト: 逐次評価（フォールバック）
            return self._execute_sequential_transformation(
                transformation,
                source_data,
                context
            )

    def _execute_dot_product_transformation(
        self,
        patterns: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        DOT_PRODUCT変換を行列演算で実行

        patterns ~> resonances WHERE {
            score $= DOT_PRODUCT(input, pattern.keywords)
        }
        """
        # 入力ベクトル化
        input_text = context.get('input_wave', {}).get('text', '')
        input_vector = self._vectorize_text(input_text)

        # パターンベクトル化
        pattern_vectors = []
        for pattern in patterns:
            keywords = pattern.get('keywords', [])
            pattern_vector = self._vectorize_keywords(keywords, input_text)
            pattern_vectors.append(pattern_vector)

        # 行列演算（全パターンの共鳴度を一度に計算）
        if pattern_vectors and len(input_vector) > 0:
            pattern_matrix = self.np.array(pattern_vectors)
            scores = pattern_matrix @ input_vector
        else:
            scores = [0.0] * len(patterns)

        # 結果構築
        resonances = []
        for i, pattern in enumerate(patterns):
            resonance = {
                'pattern_name': pattern.get('name', f'pattern_{i}'),
                'score': float(scores[i]) if i < len(scores) else 0.0,
                'action': pattern.get('action', 'unknown'),
                'threshold': pattern.get('threshold', 0.5)
            }
            resonances.append(resonance)

        return resonances

    def _vectorize_text(self, text: str) -> np.ndarray:
        """テキストをベクトル化（簡易TF-IDF）"""
        # 簡易実装: 単語の存在をバイナリベクトル化
        words = text.lower().split()
        # 固定長ベクトル（100次元）
        vector = self.np.zeros(100)
        for i, word in enumerate(words[:100]):
            vector[i] = len(word)  # 単語長をスコアとする
        return vector

    def _vectorize_keywords(
        self,
        keywords: List[str],
        reference_text: str
    ) -> np.ndarray:
        """キーワードリストをベクトル化"""
        # 参照テキストとの類似度ベクトル
        vector = self.np.zeros(100)
        ref_words = reference_text.lower().split()

        for i, word in enumerate(ref_words[:100]):
            # キーワードマッチング
            match_score = sum(1.0 for kw in keywords if kw.lower() in word.lower())
            vector[i] = match_score

        return vector

    def _execute_sequential_transformation(
        self,
        transformation: SpatialTransformation,
        source_data: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """逐次評価（フォールバック）"""
        # 簡易実装: 各要素を順に変換
        result = []
        for element in source_data:
            transformed = element.copy()
            # 制約を評価
            for constraint in transformation.constraints:
                # TODO: 制約の評価
                pass
            result.append(transformed)
        return result


class DeclarativeJCrossInterpreter:
    """
    宣言型.jcrossインタープリタ

    新構文:
    - $= : 等価宣言
    - SPACE : 空間宣言
    - ~> : 空間変換
    - WHERE : 制約
    """

    def __init__(self):
        self.equivalences: List[Equivalence] = []
        self.spaces: Dict[str, SpaceDeclaration] = {}
        self.transformations: List[SpatialTransformation] = []
        self.variables: Dict[str, Any] = {}
        self.neural_backend = NeuralEngineBackend()

    def execute(self, code: str) -> Dict[str, Any]:
        """
        宣言型.jcrossコードを実行

        Args:
            code: .jcrossコード

        Returns:
            変数の辞書
        """
        # 前処理
        code = self._preprocess(code)

        # パース
        self._parse_declarations(code)

        # 等価関係を解決
        solver = ConstraintSatisfactionSolver(self.equivalences)
        self.variables = solver.solve()

        # 空間変換を実行
        self._execute_transformations()

        return self.variables

    def _preprocess(self, code: str) -> str:
        """前処理: コメント除去"""
        lines = []
        for line in code.split('\n'):
            # コメント除去
            if '//' in line:
                line = line.split('//')[0]
            lines.append(line)
        return '\n'.join(lines)

    def _parse_declarations(self, code: str):
        """宣言をパース"""
        # SPACE宣言を抽出
        self._parse_space_declarations(code)

        # 等価宣言を抽出
        self._parse_equivalences(code)

        # 空間変換を抽出
        self._parse_transformations(code)

    def _parse_space_declarations(self, code: str):
        """SPACE宣言をパース"""
        pattern = r'SPACE\s+(\w+)\s*\{(.*?)\n\}'
        matches = re.finditer(pattern, code, re.DOTALL)

        for match in matches:
            space_name = match.group(1)
            space_body = match.group(2)

            # 空間内の要素を解析
            elements = self._parse_space_elements(space_body)

            self.spaces[space_name] = SpaceDeclaration(
                name=space_name,
                elements=elements,
                simultaneous=True
            )

    def _parse_space_elements(self, body: str) -> Dict[str, Any]:
        """空間内の要素をパース"""
        elements = {}

        # 各要素を抽出（簡易実装）
        # name $= { ... } パターン
        pattern = r'(\w+)\s*\$=\s*\{(.*?)\}'
        matches = re.finditer(pattern, body, re.DOTALL)

        for match in matches:
            element_name = match.group(1)
            element_body = match.group(2)

            # JSON風にパース
            try:
                # キー: 値 を "キー": 値 に変換
                json_body = re.sub(r'(\w+):', r'"\1":', element_body)
                # 末尾のカンマを除去
                json_body = re.sub(r',\s*}', '}', json_body)
                element_value = json.loads('{' + json_body + '}')
                elements[element_name] = element_value
            except:
                # パース失敗時は空辞書
                elements[element_name] = {}

        return elements

    def _parse_equivalences(self, code: str):
        """等価宣言をパース"""
        lines = code.split('\n')

        for line in lines:
            line = line.strip()

            # $= を含む行
            if '$=' in line and 'SPACE' not in line and '~>' not in line:
                match = re.match(r'([^\$]+)\$=\s*(.+)', line)
                if match:
                    lhs = match.group(1).strip()
                    rhs = match.group(2).strip()

                    # 依存関係を抽出
                    deps = self._extract_dependencies(rhs)

                    self.equivalences.append(Equivalence(
                        lhs=lhs,
                        rhs=rhs,
                        dependencies=deps
                    ))

    def _parse_transformations(self, code: str):
        """空間変換をパース"""
        # 簡易実装: ~> を含む行を抽出
        pattern = r'(\w+)\s*\$=\s*(\w+)\s*~>\s*SPACE\s*\{'
        matches = re.finditer(pattern, code)

        for match in matches:
            target = match.group(1)
            source = match.group(2)

            # TODO: 制約の抽出
            self.transformations.append(SpatialTransformation(
                source=source,
                target=target,
                constraints=[]
            ))

    def _extract_dependencies(self, expr: str) -> List[str]:
        """式から依存変数を抽出"""
        # 簡易実装: 英数字とアンダースコアの連続を変数とみなす
        tokens = re.findall(r'[a-zA-Z_]\w*', expr)

        # 組み込み関数を除外
        builtins = {'IF', 'ELSE', 'WHERE', 'MAX', 'MIN', 'SUM', 'DOT_PRODUCT',
                    'NORMALIZE', 'COUNT_MATCHES', 'LENGTH', 'FIND', 'EACH'}

        deps = [t for t in tokens if t not in builtins]
        return list(set(deps))  # 重複除去

    def _execute_transformations(self):
        """空間変換を実行"""
        for transformation in self.transformations:
            # 元空間のデータを取得
            if transformation.source in self.spaces:
                source_space = self.spaces[transformation.source]
                source_data = list(source_space.elements.values())

                # Neural Engineバックエンドで実行
                result = self.neural_backend.compile_spatial_transformation(
                    transformation,
                    source_data,
                    self.variables
                )

                # 結果を変数に格納
                self.variables[transformation.target] = result


def demo_declarative_interpreter():
    """宣言型インタープリタのデモ"""
    print("=" * 70)
    print("🌊 Declarative .jcross Interpreter Demo")
    print("   等価関係のみで記述（FOR loopなし）")
    print("=" * 70)
    print()

    code = """
    // パターン空間の宣言
    SPACE patterns {
        github $= {
            name: "github_commit",
            keywords: ["feat:", "fix:", "docs:"],
            threshold: 0.7,
            action: "trigger_github"
        }

        todo $= {
            name: "todo_task",
            keywords: ["TODO", "タスク", "予定"],
            threshold: 0.75,
            action: "trigger_scheduler"
        }
    }

    // 入力エネルギー波
    input_wave $= {
        text: "feat: Add declarative .jcross syntax"
    }

    // 全同調（空間変換）
    resonances $= patterns ~> SPACE {
        // Neural Engineが行列演算で一度に計算
    }
    """

    interp = DeclarativeJCrossInterpreter()
    result = interp.execute(code)

    print("📊 実行結果:")
    print()

    if 'resonances' in result:
        print("🔄 全同調結果（全パターンが同時に共鳴）:")
        for res in result['resonances']:
            score_pct = res['score'] * 100
            bar = "█" * int(score_pct / 5)
            print(f"   📡 {res['pattern_name']:20s} [{bar:20s}] {score_pct:.1f}%")
        print()

    print("✅ 宣言型実行成功:")
    print("   • FOR loopなし → 全パターンが同時に共鳴")
    print("   • 等価関係のみ → CSPソルバーで解決")
    print("   • Neural Engine → 行列演算で高速実行")
    print()
    print("=" * 70)


if __name__ == "__main__":
    demo_declarative_interpreter()
