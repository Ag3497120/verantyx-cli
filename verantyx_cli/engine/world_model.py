#!/usr/bin/env python3
"""
World Model - 完全実装

概念間の関係・因果関係・物理法則を構築
予測・計画を可能にする
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict
import math


class WorldModel:
    """世界モデル"""

    def __init__(self):
        # 概念データベース
        self.concepts: Dict[str, Dict] = {}

        # 概念間の関係
        self.relations: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
        # format: {concept_id: [(related_id, relation_type, strength), ...]}

        # 因果関係
        self.causality: Dict[Tuple[str, str], Dict] = {}
        # format: {(cause_id, effect_id): {"probability": 0.8, "observations": 10}}

        # 物理法則 (ルール)
        self.physics: List[Dict] = []

        # 予測履歴
        self.prediction_history: List[Dict] = []

    def add_concept(self, concept: Dict):
        """概念を追加"""
        concept_id = concept.get('name') or concept.get('id')
        self.concepts[concept_id] = concept

    def build_relations(self):
        """概念間の関係を構築"""
        print("\n[World Model] Building relations...")

        concepts_list = list(self.concepts.values())

        for i, concept1 in enumerate(concepts_list):
            id1 = concept1.get('name') or concept1.get('id')

            for concept2 in concepts_list[i+1:]:
                id2 = concept2.get('name') or concept2.get('id')

                # 関係を特定
                relations = self._identify_relations(concept1, concept2)

                for rel_type, strength in relations:
                    self.relations[id1].append((id2, rel_type, strength))
                    self.relations[id2].append((id1, rel_type, strength))

        print(f"  Relations built: {sum(len(v) for v in self.relations.values())} total")

    def _identify_relations(self, concept1: Dict, concept2: Dict) -> List[Tuple[str, float]]:
        """2つの概念の関係を特定"""
        relations = []

        # 1. ドメインが同じ → "same_domain"
        if concept1.get('domain') == concept2.get('domain'):
            relations.append(("same_domain", 0.8))

        # 2. 問題タイプが同じ → "same_problem_type"
        if concept1.get('problem_type') == concept2.get('problem_type'):
            relations.append(("same_problem_type", 0.9))

        # 3. ルールが類似 → "similar_approach"
        rule1 = concept1.get('rule', '')
        rule2 = concept2.get('rule', '')
        if rule1 and rule2:
            similarity = self._calculate_rule_similarity(rule1, rule2)

            if similarity > 0.3:  # より低い閾値
                relations.append(("similar_approach", similarity))

        # 4. 入力が共通 → "shared_input"
        inputs1 = set(concept1.get('inputs', []))
        inputs2 = set(concept2.get('inputs', []))
        input_overlap = len(inputs1 & inputs2) / max(len(inputs1 | inputs2), 1)

        if input_overlap > 0.3:
            relations.append(("shared_input", input_overlap))

        return relations

    def _calculate_rule_similarity(self, rule1: str, rule2: str) -> float:
        """ルールの類似度を計算"""
        if not rule1 or not rule2:
            return 0.0

        steps1 = set(rule1.split(' → '))
        steps2 = set(rule2.split(' → '))

        if not steps1 or not steps2:
            return 0.0

        intersection = steps1 & steps2
        union = steps1 | steps2

        return len(intersection) / len(union)

    def learn_causality(self, cause_concept: str, effect_concept: str, observed: bool):
        """
        因果関係を学習

        Args:
            cause_concept: 原因の概念ID
            effect_concept: 結果の概念ID
            observed: 実際に因果関係が観測されたか
        """
        key = (cause_concept, effect_concept)

        if key not in self.causality:
            self.causality[key] = {
                "probability": 0.5,
                "observations": 0,
                "successes": 0
            }

        causality = self.causality[key]
        causality["observations"] += 1

        if observed:
            causality["successes"] += 1

        # 確率を更新 (ベイズ的)
        causality["probability"] = causality["successes"] / causality["observations"]

    def infer_causality(self, event_a: str, event_b: str) -> Dict:
        """
        因果関係を推論

        Args:
            event_a: イベントA (原因候補)
            event_b: イベントB (結果候補)

        Returns:
            推論結果
        """
        key = (event_a, event_b)

        if key in self.causality:
            # 直接の因果関係がある
            return {
                "type": "direct",
                "probability": self.causality[key]["probability"],
                "observations": self.causality[key]["observations"],
                "confidence": "high" if self.causality[key]["observations"] > 5 else "medium"
            }

        # 間接的な因果関係を探索
        path = self._find_causal_path(event_a, event_b)

        if path:
            # 間接的な因果関係
            prob = 1.0
            for i in range(len(path) - 1):
                key_i = (path[i], path[i+1])
                if key_i in self.causality:
                    prob *= self.causality[key_i]["probability"]

            return {
                "type": "indirect",
                "probability": prob,
                "path": path,
                "confidence": "medium" if len(path) < 4 else "low"
            }

        # 因果関係なし
        return {
            "type": "none",
            "probability": 0.0,
            "confidence": "low"
        }

    def _find_causal_path(self, start: str, end: str, max_depth: int = 5) -> Optional[List[str]]:
        """因果関係のパスを探索 (BFS)"""
        if start == end:
            return [start]

        visited = set()
        queue = [(start, [start])]

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            if current in visited:
                continue

            visited.add(current)

            # 隣接ノードを探索
            for (cause, effect), _ in self.causality.items():
                if cause == current:
                    new_path = path + [effect]

                    if effect == end:
                        return new_path

                    queue.append((effect, new_path))

        return None

    def add_physics_rule(self, rule_name: str, condition: str, consequence: str, confidence: float = 0.9):
        """
        物理法則を追加

        例: "ファイルがなければアクセスできない"
        """
        self.physics.append({
            "name": rule_name,
            "condition": condition,
            "consequence": consequence,
            "confidence": confidence
        })

    def check_physics(self, situation: Dict) -> List[Dict]:
        """
        物理法則をチェック

        Args:
            situation: 現在の状況

        Returns:
            適用される法則のリスト
        """
        applicable_rules = []

        for rule in self.physics:
            # 条件をチェック (簡易実装)
            if self._check_condition(rule["condition"], situation):
                applicable_rules.append(rule)

        return applicable_rules

    def _check_condition(self, condition: str, situation: Dict) -> bool:
        """条件をチェック (簡易実装)"""
        # 簡易: キーワードマッチ
        for key, value in situation.items():
            if key.lower() in condition.lower():
                if isinstance(value, bool) and value:
                    return True
                if isinstance(value, str) and value.lower() in condition.lower():
                    return True

        return False

    def predict(self, situation: Dict, horizon: int = 3) -> Dict:
        """
        状況から結果を予測

        Args:
            situation: 現在の状況
            horizon: 予測する先の深さ

        Returns:
            予測結果
        """
        print(f"\n[World Model] Predicting (horizon={horizon})...")

        # 現在の状況を分析
        current_concepts = self._identify_concepts_in_situation(situation)

        print(f"  Identified concepts: {current_concepts}")

        # 因果関係から次の状態を予測
        predictions = []

        for concept_id in current_concepts:
            # この概念から派生する結果を探索
            effects = self._predict_effects(concept_id, horizon)
            predictions.extend(effects)

        # 物理法則を適用
        physics_predictions = self.check_physics(situation)

        print(f"  Predictions: {len(predictions)} causal, {len(physics_predictions)} physics")

        prediction = {
            "current_situation": situation,
            "predicted_effects": predictions[:5],  # Top 5
            "physics_rules": physics_predictions,
            "confidence": self._calculate_prediction_confidence(predictions)
        }

        self.prediction_history.append(prediction)

        return prediction

    def _identify_concepts_in_situation(self, situation: Dict) -> List[str]:
        """状況から概念を特定"""
        identified = []

        for concept_id, concept in self.concepts.items():
            domain = concept.get('domain', '')
            problem_type = concept.get('problem_type', '')

            # 状況とマッチするか
            if domain in str(situation) or problem_type in str(situation):
                identified.append(concept_id)

        return identified

    def _predict_effects(self, concept_id: str, horizon: int) -> List[Dict]:
        """概念から効果を予測"""
        effects = []

        for (cause, effect), causality_data in self.causality.items():
            if cause == concept_id:
                effects.append({
                    "effect_concept": effect,
                    "probability": causality_data["probability"],
                    "depth": 1
                })

                # 再帰的に予測 (horizonまで)
                if horizon > 1:
                    sub_effects = self._predict_effects(effect, horizon - 1)
                    for sub_effect in sub_effects:
                        sub_effect["depth"] += 1
                        sub_effect["probability"] *= causality_data["probability"]
                        effects.append(sub_effect)

        return effects

    def _calculate_prediction_confidence(self, predictions: List[Dict]) -> float:
        """予測の信頼度を計算"""
        if not predictions:
            return 0.0

        avg_prob = sum(p.get("probability", 0) for p in predictions) / len(predictions)
        return avg_prob

    def plan(self, goal: str, current_situation: Dict) -> Dict:
        """
        目標を達成するための計画を生成

        Args:
            goal: 目標
            current_situation: 現在の状況

        Returns:
            計画
        """
        print(f"\n[World Model] Planning for goal: {goal}...")

        # ゴールに関連する概念を特定
        goal_concepts = self._find_concepts_for_goal(goal)

        print(f"  Goal concepts: {goal_concepts}")

        # 現在の状況から開始
        current_concepts = self._identify_concepts_in_situation(current_situation)

        # A*的な探索でパスを見つける
        plan_path = self._find_plan_path(current_concepts, goal_concepts)

        if plan_path:
            print(f"  Plan found: {len(plan_path)} steps")

            # パスから計画を生成
            plan = self._generate_plan_from_path(plan_path)
        else:
            print(f"  No plan found, using default")
            plan = self._generate_default_plan(goal)

        return plan

    def _find_concepts_for_goal(self, goal: str) -> List[str]:
        """ゴールに関連する概念を検索"""
        related = []

        for concept_id, concept in self.concepts.items():
            # ゴールとマッチ
            if goal.lower() in concept_id.lower():
                related.append(concept_id)
            elif goal.lower() in concept.get('domain', '').lower():
                related.append(concept_id)

        return related

    def _find_plan_path(
        self,
        start_concepts: List[str],
        goal_concepts: List[str],
        max_steps: int = 10
    ) -> Optional[List[str]]:
        """開始から目標までのパスを探索"""
        if not start_concepts or not goal_concepts:
            return None

        # BFS
        for start in start_concepts:
            visited = set()
            queue = [(start, [start])]

            while queue:
                current, path = queue.pop(0)

                if len(path) > max_steps:
                    continue

                if current in goal_concepts:
                    return path

                if current in visited:
                    continue

                visited.add(current)

                # 関連概念を探索
                for related_id, rel_type, strength in self.relations.get(current, []):
                    if strength > 0.5:
                        new_path = path + [related_id]
                        queue.append((related_id, new_path))

        return None

    def _generate_plan_from_path(self, path: List[str]) -> Dict:
        """パスから計画を生成"""
        steps = []

        for i, concept_id in enumerate(path):
            concept = self.concepts.get(concept_id, {})
            steps.append({
                "step": i + 1,
                "concept": concept_id,
                "action": concept.get('rule', 'execute'),
                "domain": concept.get('domain', 'general')
            })

        return {
            "total_steps": len(steps),
            "steps": steps,
            "estimated_success": self._estimate_plan_success(path)
        }

    def _estimate_plan_success(self, path: List[str]) -> float:
        """計画の成功確率を推定"""
        if not path:
            return 0.0

        # 各ステップの信頼度を乗算
        prob = 1.0

        for i in range(len(path) - 1):
            key = (path[i], path[i+1])
            if key in self.causality:
                prob *= self.causality[key]["probability"]
            else:
                prob *= 0.7  # デフォルト

        return prob

    def _generate_default_plan(self, goal: str) -> Dict:
        """デフォルト計画を生成"""
        return {
            "total_steps": 1,
            "steps": [
                {
                    "step": 1,
                    "concept": "unknown",
                    "action": "analyze_and_proceed",
                    "domain": "general"
                }
            ],
            "estimated_success": 0.5
        }

    def get_statistics(self) -> Dict:
        """統計を取得"""
        return {
            "total_concepts": len(self.concepts),
            "total_relations": sum(len(v) for v in self.relations.values()),
            "total_causality": len(self.causality),
            "total_physics_rules": len(self.physics),
            "total_predictions": len(self.prediction_history),
            "average_prediction_confidence": sum(
                p.get("confidence", 0) for p in self.prediction_history
            ) / len(self.prediction_history) if self.prediction_history else 0.0
        }


def register_to_vm(vm):
    """VMにWorld Modelを登録"""
    world_model = WorldModel()

    vm.register_processor("世界モデル概念追加", world_model.add_concept)
    vm.register_processor("世界モデル関係構築", world_model.build_relations)
    vm.register_processor("因果関係学習", world_model.learn_causality)
    vm.register_processor("因果関係推論", world_model.infer_causality)
    vm.register_processor("物理法則追加", world_model.add_physics_rule)
    vm.register_processor("物理法則チェック", world_model.check_physics)
    vm.register_processor("世界モデル予測", world_model.predict)
    vm.register_processor("世界モデル計画", world_model.plan)
    vm.register_processor("世界モデル統計", world_model.get_statistics)

    print("✓ World Model registered")

    return world_model
