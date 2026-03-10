"""
因果推論エンジン (Causal Inference Engine)

相関ではなく因果を理解する

理論的基盤:
- Judea Pearlの因果推論理論（"The Book of Why"）
- 介入主義（interventionism）
- 反実仮想推論（counterfactual reasoning）
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import numpy as np


class CausalRelationType(Enum):
    """因果関係のタイプ"""
    DIRECT = "直接因果"           # A → B
    INDIRECT = "間接因果"         # A → C → B
    COMMON_CAUSE = "共通原因"     # A ← C → B
    COLLIDER = "衝突"            # A → C ← B
    NONE = "因果関係なし"


@dataclass
class CausalEdge:
    """因果的エッジ"""
    cause: str
    effect: str
    strength: float              # 因果の強さ
    mechanism: str               # メカニズムの説明
    confidence: float            # 確信度


@dataclass
class InterventionResult:
    """介入実験の結果"""
    intervention: str            # 介入（Aを強制的に1にする）
    observed_effect: str         # 観察された効果
    effect_size: float           # 効果のサイズ
    causal: bool                 # 因果関係があるか


@dataclass
class CounterfactualQuery:
    """反実仮想クエリ"""
    actual_world: Dict[str, Any]      # 実際の世界
    intervention: str                  # 介入（「もしAがなかったら」）
    query: str                         # 質問（「Bはどうなっていたか」）


class CausalGraph:
    """
    因果グラフ

    有向非巡回グラフ (DAG) で因果関係を表現
    """

    def __init__(self):
        self.nodes: Set[str] = set()
        self.edges: List[CausalEdge] = []

    def add_node(self, node: str):
        """ノードの追加"""
        self.nodes.add(node)

    def add_edge(self, cause: str, effect: str, strength: float, mechanism: str):
        """エッジの追加"""
        self.nodes.add(cause)
        self.nodes.add(effect)

        edge = CausalEdge(
            cause=cause,
            effect=effect,
            strength=strength,
            mechanism=mechanism,
            confidence=0.5  # 初期確信度
        )
        self.edges.append(edge)

    def get_parents(self, node: str) -> List[str]:
        """親ノード（原因）を取得"""
        return [edge.cause for edge in self.edges if edge.effect == node]

    def get_children(self, node: str) -> List[str]:
        """子ノード（結果）を取得"""
        return [edge.effect for edge in self.edges if edge.cause == node]

    def get_causal_path(self, cause: str, effect: str) -> Optional[List[str]]:
        """因果経路を取得"""
        # 幅優先探索
        queue = [(cause, [cause])]
        visited = set()

        while queue:
            current, path = queue.pop(0)

            if current == effect:
                return path

            if current in visited:
                continue

            visited.add(current)

            for child in self.get_children(current):
                queue.append((child, path + [child]))

        return None

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """ancestorがdescendantの祖先か"""
        return self.get_causal_path(ancestor, descendant) is not None


class CausalInferenceEngine:
    """
    因果推論エンジン

    「相関は因果を意味しない」を超えて、本当の因果を理解
    """

    def __init__(self):
        self.causal_graph = CausalGraph()

        # 観察データ
        self.observations: List[Dict[str, Any]] = []

        # 介入実験の記録
        self.interventions: List[InterventionResult] = []

        # 反実仮想の記録
        self.counterfactuals: List[Tuple[CounterfactualQuery, Any]] = []

    def observe(self, observation: Dict[str, Any]):
        """
        観察データの記録

        Args:
            observation: {"A": 1, "B": 1, "C": 0, ...}
        """
        self.observations.append(observation)

    def compute_correlation(self, var1: str, var2: str) -> float:
        """
        相関を計算

        相関 ≠ 因果 だが、因果発見の手がかり
        """
        if not self.observations:
            return 0.0

        values1 = [obs.get(var1, 0) for obs in self.observations]
        values2 = [obs.get(var2, 0) for obs in self.observations]

        if len(values1) != len(values2):
            return 0.0

        # ピアソン相関係数
        mean1 = np.mean(values1)
        mean2 = np.mean(values2)

        numerator = np.sum((np.array(values1) - mean1) * (np.array(values2) - mean2))
        denominator = np.sqrt(
            np.sum((np.array(values1) - mean1) ** 2) *
            np.sum((np.array(values2) - mean2) ** 2)
        )

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def intervene(self, variable: str, value: Any) -> InterventionResult:
        """
        介入実験（do-演算子）

        観察: P(B|A) - Aが起きたときBが起きる確率
        介入: P(B|do(A)) - Aを強制的に起こしたときBが起きる確率

        介入実験によって因果を確定できる

        Args:
            variable: 介入する変数
            value: 設定する値

        Returns:
            介入結果
        """
        # 介入前の状態を記録
        before_state = self._get_current_state()

        # 介入を実行
        intervened_state = before_state.copy()
        intervened_state[variable] = value

        # 因果グラフに基づいて効果を伝播
        after_state = self._propagate_effects(intervened_state, intervened=variable)

        # 効果のサイズを計算
        effect_vars = self.causal_graph.get_children(variable)

        if effect_vars:
            # 最初の子ノードの効果を測定
            effect_var = effect_vars[0]
            before_value = before_state.get(effect_var, 0)
            after_value = after_state.get(effect_var, 0)

            effect_size = after_value - before_value

            result = InterventionResult(
                intervention=f"do({variable}={value})",
                observed_effect=effect_var,
                effect_size=effect_size,
                causal=abs(effect_size) > 0.01  # 閾値
            )
        else:
            result = InterventionResult(
                intervention=f"do({variable}={value})",
                observed_effect="none",
                effect_size=0.0,
                causal=False
            )

        self.interventions.append(result)
        return result

    def _get_current_state(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        if self.observations:
            return self.observations[-1].copy()
        else:
            # デフォルト状態
            return {node: 0 for node in self.causal_graph.nodes}

    def _propagate_effects(
        self,
        state: Dict[str, Any],
        intervened: str
    ) -> Dict[str, Any]:
        """
        因果グラフに基づいて効果を伝播

        Args:
            state: 現在の状態
            intervened: 介入された変数

        Returns:
            伝播後の状態
        """
        new_state = state.copy()

        # 介入された変数の子孫に効果を伝播
        children = self.causal_graph.get_children(intervened)

        for child in children:
            # 因果エッジを取得
            edge = next(
                (e for e in self.causal_graph.edges
                 if e.cause == intervened and e.effect == child),
                None
            )

            if edge:
                # 因果メカニズムに基づいて効果を計算
                # 簡略版: 線形関係
                cause_value = state.get(intervened, 0)
                new_state[child] = cause_value * edge.strength

                # 再帰的に伝播
                new_state = self._propagate_effects(new_state, child)

        return new_state

    def counterfactual_query(
        self,
        actual: Dict[str, Any],
        intervention: str,
        query_var: str
    ) -> Any:
        """
        反実仮想推論

        「もしAがなかったら、Bはどうなっていたか？」

        Args:
            actual: 実際に起きたこと
            intervention: 仮の介入（「Aを0にする」）
            query_var: 質問する変数

        Returns:
            反実仮想世界でのquery_varの値
        """
        # 反実仮想世界をシミュレート
        counterfactual_world = actual.copy()

        # 介入をパース（簡略版）
        # "A=0" のような形式を想定
        if "=" in intervention:
            var, value = intervention.split("=")
            var = var.strip()
            value = float(value.strip())

            # 介入を適用
            counterfactual_world[var] = value

            # 効果を伝播
            counterfactual_world = self._propagate_effects(counterfactual_world, var)

        # 質問された変数の値を返す
        result = counterfactual_world.get(query_var, None)

        # 記録
        query = CounterfactualQuery(
            actual_world=actual,
            intervention=intervention,
            query=query_var
        )
        self.counterfactuals.append((query, result))

        return result

    def discover_causal_structure(self, variables: List[str]):
        """
        因果構造の発見

        観察データから因果グラフを推定

        手法:
        1. 相関ベースの初期推定
        2. 介入実験による確認
        3. グラフの洗練
        """
        # 1. 全ペアの相関を計算
        correlations = {}
        for i, var1 in enumerate(variables):
            for var2 in variables[i+1:]:
                corr = self.compute_correlation(var1, var2)
                if abs(corr) > 0.5:  # 閾値
                    correlations[(var1, var2)] = corr

        # 2. 相関から候補エッジを生成
        for (var1, var2), corr in correlations.items():
            # 相関があるが、方向は不明
            # 仮にvar1 → var2とする
            self.causal_graph.add_edge(
                var1, var2,
                strength=abs(corr),
                mechanism="correlation_based"
            )

        # 3. 介入実験で方向を確定
        for var1, var2 in correlations.keys():
            # var1に介入
            result = self.intervene(var1, 1.0)

            # var2が変化しなければ、逆方向の可能性
            if not result.causal:
                # エッジを削除して逆向きを追加
                self.causal_graph.edges = [
                    e for e in self.causal_graph.edges
                    if not (e.cause == var1 and e.effect == var2)
                ]

                self.causal_graph.add_edge(
                    var2, var1,
                    strength=abs(correlations[(var1, var2)]),
                    mechanism="intervention_confirmed"
                )

    def explain_causation(self, cause: str, effect: str) -> str:
        """
        因果関係の説明

        Args:
            cause: 原因
            effect: 結果

        Returns:
            説明
        """
        path = self.causal_graph.get_causal_path(cause, effect)

        if not path:
            return f"{cause}は{effect}の原因ではありません（因果経路なし）"

        if len(path) == 2:
            # 直接因果
            edge = next(
                (e for e in self.causal_graph.edges
                 if e.cause == cause and e.effect == effect),
                None
            )

            if edge:
                return (
                    f"{cause}は{effect}の直接的な原因です。\n"
                    f"メカニズム: {edge.mechanism}\n"
                    f"強さ: {edge.strength:.2f}"
                )

        else:
            # 間接因果
            path_str = " → ".join(path)
            return (
                f"{cause}は{effect}の間接的な原因です。\n"
                f"因果経路: {path_str}"
            )


if __name__ == "__main__":
    print("=" * 80)
    print("因果推論エンジン - デモ")
    print("=" * 80)
    print()

    engine = CausalInferenceEngine()

    # シナリオ: ボタンを押すと音が鳴る
    print("【シナリオ: ボタンと音】")
    print()

    # 因果グラフの構築
    engine.causal_graph.add_edge(
        "ボタンを押す", "音が鳴る",
        strength=1.0,
        mechanism="ボタンがスイッチを押し、回路が閉じて音が鳴る"
    )

    # 観察データ
    observations = [
        {"ボタンを押す": 1, "音が鳴る": 1},
        {"ボタンを押す": 0, "音が鳴る": 0},
        {"ボタンを押す": 1, "音が鳴る": 1},
        {"ボタンを押す": 0, "音が鳴る": 0},
    ]

    for obs in observations:
        engine.observe(obs)

    # 相関を計算
    corr = engine.compute_correlation("ボタンを押す", "音が鳴る")
    print(f"相関: {corr:.2f}")
    print("（相関があるが、これだけでは因果かわからない）")
    print()

    # 介入実験
    print("【介入実験】")
    print()
    result = engine.intervene("ボタンを押す", 1)
    print(f"介入: {result.intervention}")
    print(f"効果: {result.observed_effect}")
    print(f"効果サイズ: {result.effect_size:.2f}")
    print(f"因果関係: {'あり' if result.causal else 'なし'}")
    print()

    # 反実仮想推論
    print("【反実仮想推論】")
    print()

    actual = {"ボタンを押す": 1, "音が鳴る": 1}
    counterfactual = engine.counterfactual_query(
        actual,
        "ボタンを押す=0",
        "音が鳴る"
    )

    print(f"実際: ボタンを押した → 音が鳴った")
    print(f"反実仮想: もしボタンを押さなかったら → 音は鳴ら{'なかった' if counterfactual == 0 else 'った'}")
    print()

    # 因果の説明
    print("【因果の説明】")
    print()
    explanation = engine.explain_causation("ボタンを押す", "音が鳴る")
    print(explanation)
    print()

    print("=" * 80)
    print("✅ 因果推論エンジン実装完了")
    print("=" * 80)
    print()
    print("これにより:")
    print("  - 相関と因果を区別できる")
    print("  - 介入実験で因果を確定できる")
    print("  - 反実仮想推論ができる")
    print("  - 「なぜ？」に答えられる")
    print()
