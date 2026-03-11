#!/usr/bin/env python3
"""
Cross Simulator - 完全実装

Cross空間でのシミュレーション・推論を実行
Verantyx思想の核心部分
"""

from typing import Dict, List, Any, Optional, Tuple
from copy import deepcopy
import math


class CrossObject:
    """Cross空間のオブジェクト"""

    def __init__(self, obj_id: str, data: Any):
        self.obj_id = obj_id
        self.data = data

        # 6軸の位置・強度
        self.positions = {
            "UP": 0.0,      # 目的・目標
            "DOWN": 0.0,    # 前提条件・基盤
            "LEFT": 0.0,    # 代替・並行
            "RIGHT": 0.0,   # 次のステップ
            "FRONT": 0.0,   # 未来・予測
            "BACK": 0.0     # 過去・履歴
        }

        # 関連オブジェクト
        self.relations: Dict[str, List[str]] = {
            axis: [] for axis in self.positions.keys()
        }

    def set_position(self, axis: str, value: float):
        """軸上の位置を設定"""
        if axis in self.positions:
            self.positions[axis] = max(0.0, min(1.0, value))

    def add_relation(self, axis: str, related_id: str):
        """関連を追加"""
        if axis in self.relations:
            if related_id not in self.relations[axis]:
                self.relations[axis].append(related_id)

    def to_dict(self) -> Dict:
        """辞書に変換"""
        return {
            "obj_id": self.obj_id,
            "data": self.data,
            "positions": self.positions.copy(),
            "relations": {k: v.copy() for k, v in self.relations.items()}
        }


class CrossSimulator:
    """Cross空間シミュレータ"""

    def __init__(self):
        self.objects: Dict[str, CrossObject] = {}
        self.simulation_history: List[Dict] = []

    def add_object(self, obj_id: str, data: Any, positions: Optional[Dict] = None) -> CrossObject:
        """オブジェクトを追加"""
        obj = CrossObject(obj_id, data)

        if positions:
            for axis, value in positions.items():
                obj.set_position(axis, value)

        self.objects[obj_id] = obj
        return obj

    def create_from_concept(self, concept: Dict) -> CrossObject:
        """
        概念からCrossオブジェクトを作成

        概念のルール "check → fix → verify" を
        Cross空間に配置
        """
        obj_id = concept['name']

        # 位置を計算
        positions = self._calculate_positions_from_concept(concept)

        obj = self.add_object(obj_id, concept, positions)

        # ルールから関連を構築
        self._build_relations_from_rule(obj, concept.get('rule', ''))

        return obj

    def _calculate_positions_from_concept(self, concept: Dict) -> Dict[str, float]:
        """概念から6軸位置を計算"""
        positions = {}

        # UP: 目的 (問題解決の程度)
        confidence = concept.get('confidence', 0.5)
        positions['UP'] = confidence

        # DOWN: 前提条件 (use_countが多いほど基盤として確立)
        use_count = concept.get('use_count', 0)
        positions['DOWN'] = min(1.0, use_count / 10.0)

        # RIGHT: 次のステップ (ルールの長さ)
        rule = concept.get('rule', '')
        steps = rule.split(' → ')
        positions['RIGHT'] = min(1.0, len(steps) / 5.0)

        # FRONT: 未来予測 (confidenceが高いほど予測可能)
        positions['FRONT'] = confidence * 0.8

        # BACK: 過去履歴 (use_countが多いほど歴史がある)
        positions['BACK'] = min(1.0, use_count / 15.0)

        # LEFT: 代替 (ドメインの多様性)
        positions['LEFT'] = 0.5  # デフォルト

        return positions

    def _build_relations_from_rule(self, obj: CrossObject, rule: str):
        """ルールから関連を構築"""
        if not rule or ' → ' not in rule:
            return

        steps = rule.split(' → ')

        # 各ステップをRIGHT方向に配置
        for i, step in enumerate(steps):
            step_id = f"{obj.obj_id}_step_{i}_{step}"

            # ステップオブジェクトを作成
            step_obj = self.add_object(
                step_id,
                {"step": step, "order": i},
                {"RIGHT": i / len(steps), "DOWN": 0.7}
            )

            # 親オブジェクトとの関連
            obj.add_relation("RIGHT", step_id)
            step_obj.add_relation("BACK", obj.obj_id)

    def simulate_operation(
        self,
        obj_id: str,
        operation: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Cross構造に操作を適用してシミュレート

        "もし〜なら?" のシミュレーション
        """
        if obj_id not in self.objects:
            return {"success": False, "error": "Object not found"}

        obj = self.objects[obj_id]

        # 現在の状態を保存
        initial_state = obj.to_dict()

        # 操作を適用
        result = self._apply_operation(obj, operation, context)

        # 結果を予測
        prediction = self._predict_outcome(obj, result)

        # シミュレーション履歴に追加
        self.simulation_history.append({
            "obj_id": obj_id,
            "operation": operation,
            "initial_state": initial_state,
            "result": result,
            "prediction": prediction
        })

        return {
            "success": True,
            "result": result,
            "prediction": prediction,
            "final_state": obj.to_dict()
        }

    def _apply_operation(self, obj: CrossObject, operation: str, context: Optional[Dict]) -> Dict:
        """操作を適用"""
        # 操作タイプを判定
        if "check" in operation.lower() or "確認" in operation:
            return self._apply_check(obj, context)
        elif "fix" in operation.lower() or "修正" in operation:
            return self._apply_fix(obj, context)
        elif "verify" in operation.lower() or "検証" in operation:
            return self._apply_verify(obj, context)
        else:
            return self._apply_generic(obj, operation, context)

    def _apply_check(self, obj: CrossObject, context: Optional[Dict]) -> Dict:
        """チェック操作"""
        # DOWN (前提条件) を確認
        down_strength = obj.positions["DOWN"]

        if down_strength > 0.6:
            return {
                "operation": "check",
                "status": "passed",
                "message": "Preconditions satisfied"
            }
        else:
            return {
                "operation": "check",
                "status": "failed",
                "message": "Preconditions not satisfied",
                "missing": down_strength
            }

    def _apply_fix(self, obj: CrossObject, context: Optional[Dict]) -> Dict:
        """修正操作"""
        # DOWN (前提条件) を強化
        obj.set_position("DOWN", obj.positions["DOWN"] + 0.2)

        # UP (目的達成度) も少し向上
        obj.set_position("UP", obj.positions["UP"] + 0.1)

        return {
            "operation": "fix",
            "status": "applied",
            "message": "Fix applied",
            "new_down": obj.positions["DOWN"],
            "new_up": obj.positions["UP"]
        }

    def _apply_verify(self, obj: CrossObject, context: Optional[Dict]) -> Dict:
        """検証操作"""
        # UP (目的達成度) を確認
        up_strength = obj.positions["UP"]

        if up_strength > 0.7:
            # 成功 → FRONT (未来予測) を強化
            obj.set_position("FRONT", up_strength * 0.9)
            return {
                "operation": "verify",
                "status": "success",
                "message": "Verification passed",
                "confidence": up_strength
            }
        else:
            return {
                "operation": "verify",
                "status": "partial",
                "message": "Partial success",
                "confidence": up_strength
            }

    def _apply_generic(self, obj: CrossObject, operation: str, context: Optional[Dict]) -> Dict:
        """汎用操作"""
        # RIGHT方向に進む
        obj.set_position("RIGHT", obj.positions["RIGHT"] + 0.15)

        return {
            "operation": operation,
            "status": "executed",
            "message": f"Operation '{operation}' executed"
        }

    def _predict_outcome(self, obj: CrossObject, operation_result: Dict) -> Dict:
        """結果を予測"""
        positions = obj.positions

        # 成功確率を計算
        success_prob = (
            positions["UP"] * 0.4 +      # 目的達成度
            positions["DOWN"] * 0.3 +    # 前提条件
            positions["FRONT"] * 0.3     # 未来予測
        )

        # 予測
        if success_prob > 0.7:
            prediction = "high_success"
        elif success_prob > 0.4:
            prediction = "moderate_success"
        else:
            prediction = "low_success"

        return {
            "prediction": prediction,
            "success_probability": success_prob,
            "risk_factors": self._identify_risks(obj),
            "recommendations": self._generate_recommendations(obj, success_prob)
        }

    def _identify_risks(self, obj: CrossObject) -> List[str]:
        """リスク要因を特定"""
        risks = []

        if obj.positions["DOWN"] < 0.5:
            risks.append("Weak preconditions")

        if obj.positions["UP"] < 0.6:
            risks.append("Low goal achievement")

        if obj.positions["BACK"] > 0.8:
            risks.append("Over-reliance on past patterns")

        return risks

    def _generate_recommendations(self, obj: CrossObject, success_prob: float) -> List[str]:
        """推奨事項を生成"""
        recommendations = []

        if success_prob < 0.5:
            recommendations.append("Strengthen preconditions (DOWN axis)")

        if obj.positions["RIGHT"] < 0.3:
            recommendations.append("Add more steps to the process")

        if obj.positions["FRONT"] < 0.4:
            recommendations.append("Improve predictive model")

        return recommendations

    def spatial_reasoning(self, query: str) -> Dict:
        """
        空間的推論

        Cross空間内のオブジェクト間の関係を推論
        """
        results = []

        if "related" in query.lower():
            # 関連オブジェクトを検索
            results = self._find_related_objects()

        elif "similar" in query.lower():
            # 類似オブジェクトを検索
            results = self._find_similar_objects()

        elif "path" in query.lower():
            # パスを検索
            results = self._find_paths()

        return {
            "query": query,
            "results": results,
            "reasoning": "Spatial analysis in Cross space"
        }

    def _find_related_objects(self) -> List[Dict]:
        """関連オブジェクトを検索"""
        related = []

        for obj_id, obj in self.objects.items():
            for axis, related_ids in obj.relations.items():
                if related_ids:
                    related.append({
                        "object": obj_id,
                        "axis": axis,
                        "related": related_ids
                    })

        return related

    def _find_similar_objects(self) -> List[Dict]:
        """類似オブジェクトを検索"""
        similar_pairs = []

        obj_list = list(self.objects.values())

        for i, obj1 in enumerate(obj_list):
            for obj2 in obj_list[i+1:]:
                similarity = self._calculate_similarity(obj1, obj2)

                if similarity > 0.6:
                    similar_pairs.append({
                        "object1": obj1.obj_id,
                        "object2": obj2.obj_id,
                        "similarity": similarity
                    })

        return similar_pairs

    def _calculate_similarity(self, obj1: CrossObject, obj2: CrossObject) -> float:
        """2つのオブジェクトの類似度を計算"""
        # 6軸の位置の差を計算
        total_diff = 0.0

        for axis in obj1.positions.keys():
            diff = abs(obj1.positions[axis] - obj2.positions[axis])
            total_diff += diff

        # 0-1の範囲に正規化 (差が小さいほど類似)
        similarity = 1.0 - (total_diff / 6.0)

        return similarity

    def _find_paths(self) -> List[Dict]:
        """オブジェクト間のパスを検索"""
        paths = []

        for obj_id, obj in self.objects.items():
            # RIGHT方向のパスを探索
            if obj.relations["RIGHT"]:
                path = self._explore_path(obj_id, "RIGHT", [])
                if len(path) > 1:
                    paths.append({
                        "start": obj_id,
                        "direction": "RIGHT",
                        "path": path
                    })

        return paths

    def _explore_path(self, obj_id: str, direction: str, visited: List[str]) -> List[str]:
        """パスを探索 (再帰)"""
        if obj_id in visited or obj_id not in self.objects:
            return []

        visited.append(obj_id)
        path = [obj_id]

        obj = self.objects[obj_id]

        if direction in obj.relations:
            for related_id in obj.relations[direction]:
                sub_path = self._explore_path(related_id, direction, visited.copy())
                if sub_path:
                    path.extend(sub_path)

        return path

    def visualize_cross_space(self) -> str:
        """Cross空間を可視化"""
        lines = ["Cross Space Visualization:", "=" * 60]

        for obj_id, obj in self.objects.items():
            lines.append(f"\n[{obj_id}]")

            # 6軸の位置
            for axis, value in obj.positions.items():
                bar_length = int(value * 20)
                bar = "█" * bar_length + "░" * (20 - bar_length)
                lines.append(f"  {axis:6s}: {bar} {value:.2f}")

            # 関連
            for axis, related_ids in obj.relations.items():
                if related_ids:
                    lines.append(f"  → {axis}: {', '.join(related_ids[:3])}")

        return "\n".join(lines)


def register_to_vm(vm):
    """VMにCross Simulatorを登録"""
    simulator = CrossSimulator()

    vm.register_processor("Cross空間オブジェクト追加", simulator.add_object)
    vm.register_processor("概念からCross作成", simulator.create_from_concept)
    vm.register_processor("Cross操作シミュレート", simulator.simulate_operation)
    vm.register_processor("Cross空間推論", simulator.spatial_reasoning)
    vm.register_processor("Cross空間可視化", simulator.visualize_cross_space)

    print("✓ Cross Simulator registered")

    return simulator
