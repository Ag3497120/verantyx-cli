#!/usr/bin/env python3
"""
XTS Puzzle Reasoning - 完全実装

MCTS (Monte Carlo Tree Search) を使った
パズル推論・プログラム探索
"""

from typing import Dict, List, Any, Optional, Tuple
import random
import math
from verantyx_cli.engine.xts_processors import TreeNode, XTSProcessors


class XTSPuzzleReasoning:
    """XTSパズル推論システム"""

    def __init__(self, cross_simulator=None, dynamic_generator=None, evaluator=None):
        self.cross_simulator = cross_simulator
        self.dynamic_generator = dynamic_generator
        self.evaluator = evaluator

        self.xts_processors = XTSProcessors()
        self.search_history: List[Dict] = []

    def solve_problem_with_xts(
        self,
        problem: str,
        concepts: List[Dict],
        max_iterations: int = 50,
        exploration_weight: float = 1.4
    ) -> Dict:
        """
        XTSを使って問題を解決

        複数の候補プログラムを探索して最適解を選択
        """
        print(f"\n{'='*60}")
        print(f"XTS Puzzle Reasoning: {problem[:40]}...")
        print(f"{'='*60}\n")

        # ルートノードを作成
        root_id = f"root_{hash(problem) % 10000}"
        root = self.xts_processors.ノード初期化(root_id, problem)

        print(f"[Step 1] Root node created: {root_id}")
        print(f"  Concepts available: {len(concepts)}")
        print(f"  Max iterations: {max_iterations}")
        print()

        # MCTS iterations
        best_node = None
        best_score = -1.0

        for iteration in range(max_iterations):
            # 1. Selection (UCB)
            current_node_id = root_id
            current = self.xts_processors.nodes_db[current_node_id]

            while not current.is_leaf():
                children_data = [c.to_dict() for c in current.children]
                scores = self.xts_processors.UCBスコア各ノード(
                    children_data,
                    exploration_weight
                )

                if not scores:
                    break

                best_child_idx = scores.index(max(scores))
                current = current.children[best_child_idx]
                current_node_id = current.node_id

            # 2. Expansion
            if current.visits > 0:  # 訪問済みなら展開
                expanded = self._expand_node(current, concepts)
                if expanded:
                    current = expanded
                    current_node_id = current.node_id

            # 3. Simulation
            reward = self._simulate(current, problem)

            # 4. Backpropagation
            self._backpropagate(current, reward)

            # ベストノードを更新
            if current.visits > 0:
                avg_value = current.value / current.visits
                if avg_value > best_score:
                    best_score = avg_value
                    best_node = current

            # 進捗表示 (10回ごと)
            if (iteration + 1) % 10 == 0:
                print(f"  Iteration {iteration + 1}/{max_iterations}: Best score = {best_score:.2f}")

        print()
        print(f"[Step 2] Search completed")
        print(f"  Total iterations: {max_iterations}")
        print(f"  Best score: {best_score:.2f}")
        print()

        # 最良解を取得
        if best_node:
            solution = self._extract_solution(best_node)
        else:
            solution = self._get_default_solution(problem, concepts)

        print(f"[Step 3] Solution extracted")
        print(f"  Program length: {len(solution['program'].split(chr(10)))} lines")
        print(f"  Confidence: {solution['confidence']:.2f}")
        print()

        # 検索履歴に追加
        self.search_history.append({
            "problem": problem,
            "iterations": max_iterations,
            "best_score": best_score,
            "solution": solution
        })

        return solution

    def _expand_node(self, node: TreeNode, concepts: List[Dict]) -> Optional[TreeNode]:
        """ノードを展開 (子ノードを生成)"""
        if not concepts:
            return None

        # 概念を選択 (ランダムまたはヒューリスティック)
        concept = random.choice(concepts)

        # 子ノードIDを生成
        child_id = f"{node.node_id}_c{len(node.children)}_{concept['name'][:10]}"

        # 子ノードを作成
        child = TreeNode(
            node_id=child_id,
            operation=concept['name'],
            parent=node
        )

        child.parent = node
        node.children.append(child)

        self.xts_processors.nodes_db[child_id] = child

        return child

    def _simulate(self, node: TreeNode, problem: str) -> float:
        """
        シミュレーション

        ノードからプログラムを生成して評価
        """
        # ノードからプログラムを生成
        program = self._generate_program_from_node(node)

        if not self.evaluator:
            # Evaluatorがない場合: ランダムスコア
            return random.uniform(0.3, 0.9)

        # プログラムを評価
        try:
            evaluation = self.evaluator.evaluate(
                program=program,
                program_name=node.node_id,
                context={"problem": problem}
            )

            return evaluation.get("score", 0.5)

        except Exception:
            return 0.3  # エラー時は低スコア

    def _generate_program_from_node(self, node: TreeNode) -> str:
        """ノードからプログラムを生成"""
        # ルートから現在ノードまでのパスを取得
        path = []
        current = node

        while current:
            if current.operation:
                path.insert(0, current.operation)
            current = current.parent

        # パスからプログラムを生成
        if path:
            program_lines = [f"ラベル {node.node_id}"]
            program_lines.append("  取り出す input")

            for i, operation in enumerate(path):
                program_lines.append(f"  実行する {operation} input")
                program_lines.append(f"  記憶する step_{i}_result 結果")

            program_lines.append(f"  取り出す step_{len(path)-1}_result")
            program_lines.append("  返す 結果")

            return "\n".join(program_lines)
        else:
            # デフォルトプログラム
            return f"""ラベル {node.node_id}
  取り出す input
  実行する 標準処理 input
  返す 結果"""

    def _backpropagate(self, node: TreeNode, reward: float):
        """バックプロパゲーション"""
        current = node

        while current:
            current.visits += 1
            current.value += reward
            current = current.parent

    def _extract_solution(self, best_node: TreeNode) -> Dict:
        """最良ノードから解を抽出"""
        # ルートからのパスを取得
        path = []
        current = best_node

        while current:
            if current.operation:
                path.insert(0, current.operation)
            current = current.parent

        # プログラムを生成
        program = self._generate_program_from_node(best_node)

        # 信頼度を計算
        confidence = best_node.value / best_node.visits if best_node.visits > 0 else 0.5

        return {
            "program": program,
            "path": path,
            "confidence": confidence,
            "visits": best_node.visits,
            "node_id": best_node.node_id
        }

    def _get_default_solution(self, problem: str, concepts: List[Dict]) -> Dict:
        """デフォルト解を取得 (探索失敗時)"""
        if concepts:
            concept = concepts[0]
            program = f"""ラベル default_solution
  取り出す input
  実行する {concept['name']} input
  返す 結果"""
        else:
            program = """ラベル fallback
  取り出す input
  実行する 標準処理 input
  返す 結果"""

        return {
            "program": program,
            "path": [concepts[0]['name']] if concepts else [],
            "confidence": 0.3,
            "visits": 0,
            "node_id": "default"
        }

    def compare_solutions(
        self,
        problem: str,
        solutions: List[Dict]
    ) -> Dict:
        """
        複数の解を比較

        Returns:
            最良解
        """
        if not solutions:
            return {}

        # 各解を評価
        evaluated_solutions = []

        for solution in solutions:
            if self.evaluator:
                try:
                    eval_result = self.evaluator.evaluate(
                        program=solution['program'],
                        program_name=solution.get('node_id', 'solution'),
                        context={"problem": problem}
                    )
                    solution['eval_score'] = eval_result.get('score', 0)
                except Exception:
                    solution['eval_score'] = 0

            else:
                solution['eval_score'] = solution.get('confidence', 0)

            evaluated_solutions.append(solution)

        # 最良解を選択
        best = max(evaluated_solutions, key=lambda s: s['eval_score'])

        return {
            "best_solution": best,
            "all_solutions": evaluated_solutions,
            "comparison": self._create_comparison_table(evaluated_solutions)
        }

    def _create_comparison_table(self, solutions: List[Dict]) -> List[Dict]:
        """比較テーブルを作成"""
        table = []

        for i, sol in enumerate(solutions):
            table.append({
                "rank": i + 1,
                "node_id": sol.get('node_id', 'unknown'),
                "confidence": sol.get('confidence', 0),
                "eval_score": sol.get('eval_score', 0),
                "visits": sol.get('visits', 0)
            })

        # スコアでソート
        table.sort(key=lambda x: x['eval_score'], reverse=True)

        # ランクを再割り当て
        for i, entry in enumerate(table):
            entry['rank'] = i + 1

        return table

    def get_statistics(self) -> Dict:
        """統計を取得"""
        if not self.search_history:
            return {}

        total_searches = len(self.search_history)
        avg_score = sum(h['best_score'] for h in self.search_history) / total_searches
        avg_iterations = sum(h['iterations'] for h in self.search_history) / total_searches

        return {
            "total_searches": total_searches,
            "average_best_score": avg_score,
            "average_iterations": avg_iterations,
            "recent_searches": [
                {
                    "problem": h['problem'][:40],
                    "score": h['best_score'],
                    "iterations": h['iterations']
                }
                for h in self.search_history[-5:]
            ]
        }


def register_to_vm(vm, cross_simulator=None, dynamic_generator=None, evaluator=None):
    """VMにXTS Puzzle Reasoningを登録"""
    xts = XTSPuzzleReasoning(
        cross_simulator=cross_simulator,
        dynamic_generator=dynamic_generator,
        evaluator=evaluator
    )

    vm.register_processor("XTS問題解決", xts.solve_problem_with_xts)
    vm.register_processor("XTS解比較", xts.compare_solutions)
    vm.register_processor("XTS統計", xts.get_statistics)

    print("✓ XTS Puzzle Reasoning registered")

    return xts
