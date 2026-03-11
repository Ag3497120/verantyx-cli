#!/usr/bin/env python3
"""
Cross Tree Search (XTS) Processors

MCTS探索を実行するプロセッサ群
"""

from typing import Dict, List, Any, Optional
import math
import random


class TreeNode:
    """MCTSツリーノード"""

    def __init__(self, node_id: str, operation: Optional[str] = None, parent: Optional['TreeNode'] = None):
        self.node_id = node_id
        self.operation = operation
        self.parent = parent
        self.children: List['TreeNode'] = []

        # MCTS統計
        self.visits = 0
        self.value = 0.0

    def ucb_score(self, exploration_weight: float = 1.4) -> float:
        """UCBスコアを計算"""
        if self.visits == 0:
            return float('inf')

        if self.parent is None or self.parent.visits == 0:
            return self.value / self.visits

        exploitation = self.value / self.visits
        exploration = exploration_weight * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )

        return exploitation + exploration

    def is_leaf(self) -> bool:
        """葉ノードか"""
        return len(self.children) == 0

    def to_dict(self) -> Dict:
        """辞書に変換"""
        return {
            "node_id": self.node_id,
            "operation": self.operation,
            "visits": self.visits,
            "value": self.value,
            "children_count": len(self.children)
        }


class XTSProcessors:
    """XTS用プロセッサ群"""

    # グローバルノード管理
    nodes_db: Dict[str, TreeNode] = {}
    node_counter = 0

    @staticmethod
    def ノード初期化(node_id: str, task_info: str) -> Dict:
        """ノードを初期化"""
        node = TreeNode(node_id=node_id, operation=task_info)
        XTSProcessors.nodes_db[node_id] = node
        return node.to_dict()

    @staticmethod
    def 葉ノード判定(node_data: Dict) -> int:
        """葉ノードか判定"""
        node_id = node_data.get("node_id") if isinstance(node_data, dict) else str(node_data)
        node = XTSProcessors.nodes_db.get(node_id)

        if node and node.is_leaf():
            return 1
        return 0

    @staticmethod
    def 子ノード取得(node_data: Dict) -> List[Dict]:
        """子ノードを取得"""
        node_id = node_data.get("node_id") if isinstance(node_data, dict) else str(node_data)
        node = XTSProcessors.nodes_db.get(node_id)

        if not node:
            return []

        return [child.to_dict() for child in node.children]

    @staticmethod
    def UCBスコア各ノード(nodes: List[Dict], exploration_weight: float) -> List[float]:
        """各ノードのUCBスコアを計算"""
        scores = []

        for node_data in nodes:
            node_id = node_data.get("node_id")
            node = XTSProcessors.nodes_db.get(node_id)

            if node:
                score = node.ucb_score(exploration_weight)
                scores.append(score)
            else:
                scores.append(0.0)

        return scores

    @staticmethod
    def 最大取得(scores: List[float]) -> Dict:
        """スコア最大のノードを取得"""
        if not scores:
            return {}

        max_idx = scores.index(max(scores))

        # 対応するノードを返す
        node_ids = list(XTSProcessors.nodes_db.keys())
        if max_idx < len(node_ids):
            node = XTSProcessors.nodes_db[node_ids[max_idx]]
            return node.to_dict()

        return {}

    @staticmethod
    def 概念選択(concepts: List[str], node_data: Dict) -> str:
        """概念候補から1つ選択（P(concept|user)ベース）"""
        if not concepts:
            return "default_concept"

        # 簡易: ランダム選択（将来的にはP(concept|user)で重み付け）
        return random.choice(concepts)

    @staticmethod
    def ルール取得(concept: str) -> str:
        """概念からルールを取得"""
        # 簡易実装: デフォルトルール
        return "check → fix → verify"

    @staticmethod
    def ルール展開(rule: str) -> List[str]:
        """ルールを操作リストに展開"""
        # "check → fix → verify" → ["確認する", "修正する", "検証する"]
        rule_map = {
            "check": "確認する",
            "fix": "修正する",
            "verify": "検証する",
            "install": "インストールする",
            "configure": "設定する",
            "execute": "実行する"
        }

        operations = []
        for part in rule.split("→"):
            part = part.strip()
            operations.append(rule_map.get(part, f"{part}する"))

        return operations

    @staticmethod
    def 子ID生成(parent_data: Dict) -> str:
        """子ノードIDを生成"""
        XTSProcessors.node_counter += 1
        parent_id = parent_data.get("node_id", "root")
        return f"{parent_id}_child_{XTSProcessors.node_counter}"

    @staticmethod
    def 親子リンク(parent_data: Dict, child_data: Dict) -> bool:
        """親子関係を設定"""
        parent_id = parent_data.get("node_id")
        child_id = child_data.get("node_id")

        parent = XTSProcessors.nodes_db.get(parent_id)
        child = XTSProcessors.nodes_db.get(child_id)

        if parent and child:
            child.parent = parent
            parent.children.append(child)
            return True

        return False

    @staticmethod
    def visits更新(node_data: Dict) -> int:
        """visitsをincrement"""
        node_id = node_data.get("node_id")
        node = XTSProcessors.nodes_db.get(node_id)

        if node:
            node.visits += 1
            return node.visits

        return 0

    @staticmethod
    def value更新(node_data: Dict, reward: float) -> float:
        """valueを更新"""
        node_id = node_data.get("node_id")
        node = XTSProcessors.nodes_db.get(node_id)

        if node:
            node.value += reward
            return node.value

        return 0.0

    @staticmethod
    def 親ノード取得(node_data: Dict) -> str:
        """親ノードを取得"""
        node_id = node_data.get("node_id")
        node = XTSProcessors.nodes_db.get(node_id)

        if node and node.parent:
            return node.parent.to_dict()

        return "null"

    @staticmethod
    def 操作履歴取得(node_data: Dict) -> List[str]:
        """ノードのrootからの操作履歴を取得"""
        node_id = node_data.get("node_id")
        node = XTSProcessors.nodes_db.get(node_id)

        operations = []
        current = node

        while current:
            if current.operation:
                operations.insert(0, current.operation)
            current = current.parent

        return operations

    @staticmethod
    def jcrossコード生成(operations: List[str]) -> str:
        """.jcrossコードを生成"""
        code_lines = ["ラベル 生成プログラム"]

        for op in operations:
            code_lines.append(f"  実行する {op}")

        code_lines.append("  返す 結果")

        return "\n".join(code_lines)

    @staticmethod
    def jcross実行(program: str) -> Dict:
        """.jcrossプログラムを実行（簡易）"""
        # 実際にはVMで実行
        return {
            "executed": True,
            "success": True,
            "output": "simulation_result"
        }

    @staticmethod
    def エラーチェック(result: Dict) -> int:
        """エラーがあるかチェック"""
        if isinstance(result, dict):
            return 0 if result.get("success", False) else 1
        return 1

    @staticmethod
    def 成功判定(result: Dict) -> float:
        """成功スコアを計算"""
        if isinstance(result, dict) and result.get("success"):
            return 1.0
        return 0.0

    @staticmethod
    def 効率性計算(result: Dict) -> float:
        """効率性スコアを計算"""
        # 簡易: 常に0.8
        return 0.8

    @staticmethod
    def 加重平均(score1: float, score2: float, weight1: float, weight2: float) -> float:
        """加重平均を計算"""
        return score1 * weight1 + score2 * weight2

    @staticmethod
    def 葉ノード列挙(root_data: Dict) -> List[Dict]:
        """すべての葉ノードを列挙"""
        root_id = root_data.get("node_id")
        root = XTSProcessors.nodes_db.get(root_id)

        if not root:
            return []

        leaves = []

        def traverse(node: TreeNode):
            if node.is_leaf():
                leaves.append(node.to_dict())
            else:
                for child in node.children:
                    traverse(child)

        traverse(root)
        return leaves

    @staticmethod
    def ノードソート(nodes: List[Dict]) -> List[Dict]:
        """ノードをスコアでソート"""
        def score(node_data: Dict) -> float:
            visits = node_data.get("visits", 0)
            value = node_data.get("value", 0.0)
            return value / visits if visits > 0 else 0.0

        return sorted(nodes, key=score, reverse=True)

    @staticmethod
    def 先頭取得(sorted_nodes: List[Dict]) -> Dict:
        """先頭を取得"""
        return sorted_nodes[0] if sorted_nodes else {}

    @staticmethod
    def Concept空間検索(domain: str) -> List[str]:
        """Concept空間から関連概念を検索"""
        # 簡易: デフォルト概念
        return ["error_recovery", "build_process", "configuration"]

    @staticmethod
    def 概念ソート(concepts: List[str]) -> List[str]:
        """概念をP(concept|user)でソート"""
        # 簡易: そのまま返す
        return concepts


def register_to_vm(vm):
    """VMにXTSプロセッサを登録"""
    processors = XTSProcessors()

    # ノード管理
    vm.register_processor("ノード初期化", processors.ノード初期化)
    vm.register_processor("葉ノード判定", processors.葉ノード判定)
    vm.register_processor("子ノード取得", processors.子ノード取得)
    vm.register_processor("UCBスコア各ノード", processors.UCBスコア各ノード)
    vm.register_processor("最大取得", processors.最大取得)
    vm.register_processor("子ID生成", processors.子ID生成)
    vm.register_processor("親子リンク", processors.親子リンク)
    vm.register_processor("visits更新", processors.visits更新)
    vm.register_processor("value更新", processors.value更新)
    vm.register_processor("親ノード取得", processors.親ノード取得)

    # 概念関連
    vm.register_processor("概念候補取得", processors.Concept空間検索)
    vm.register_processor("概念選択", processors.概念選択)
    vm.register_processor("ルール取得", processors.ルール取得)
    vm.register_processor("ルール展開", processors.ルール展開)
    vm.register_processor("概念ソート", processors.概念ソート)

    # プログラム生成・実行
    vm.register_processor("操作履歴取得", processors.操作履歴取得)
    vm.register_processor("jcrossコード生成", processors.jcrossコード生成)
    vm.register_processor("jcross実行", processors.jcross実行)
    vm.register_processor("エラーチェック", processors.エラーチェック)

    # 評価
    vm.register_processor("成功判定", processors.成功判定)
    vm.register_processor("効率性計算", processors.効率性計算)
    vm.register_processor("加重平均", processors.加重平均)

    # ベスト選択
    vm.register_processor("葉ノード列挙", processors.葉ノード列挙)
    vm.register_processor("ノードソート", processors.ノードソート)
    vm.register_processor("先頭取得", processors.先頭取得)

    print("✓ XTS processors registered")
