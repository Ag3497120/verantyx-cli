#!/usr/bin/env python3
"""
JCross Condition Evaluator
JCross発火条件評価器

Stage 1: emotion_dna_cross.jcrossのFRONT軸の発火条件を実際に評価
"""

import re
from typing import Dict, Any, List, Optional
import operator


class ConditionEvaluator:
    """
    .jcrossの発火条件を評価

    例: "痛み > 50.0" → 実際のstate["痛み"]と比較
    """

    # 演算子マッピング
    OPERATORS = {
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le,
        '==': operator.eq,
        '!=': operator.ne,
        '=': operator.eq  # 日本語的な「等しい」
    }

    def __init__(self):
        """Initialize"""
        pass

    def evaluate(self, condition_str: str, state: Dict[str, Any]) -> bool:
        """
        発火条件を評価

        Args:
            condition_str: 条件文字列（例: "痛み > 50.0"）
            state: 現在の状態辞書

        Returns:
            条件が満たされているか
        """
        condition_str = condition_str.strip()

        # AND条件（「かつ」または「and」）
        if ' かつ ' in condition_str or ' and ' in condition_str:
            parts = re.split(r' かつ | and ', condition_str)
            return all(self.evaluate(part.strip(), state) for part in parts)

        # OR条件（「または」または「or」）
        if ' または ' in condition_str or ' or ' in condition_str:
            parts = re.split(r' または | or ', condition_str)
            return any(self.evaluate(part.strip(), state) for part in parts)

        # 単純な比較条件
        return self._evaluate_simple_condition(condition_str, state)

    def _evaluate_simple_condition(self, condition_str: str, state: Dict[str, Any]) -> bool:
        """
        単純な比較条件を評価

        Args:
            condition_str: 条件文字列
            state: 状態辞書

        Returns:
            条件が満たされているか
        """
        # パターン: 変数名 演算子 値
        # 例: "痛み > 50.0", "心拍数 >= 120"

        for op_str, op_func in self.OPERATORS.items():
            if op_str in condition_str:
                parts = condition_str.split(op_str, 1)
                if len(parts) != 2:
                    continue

                var_name = parts[0].strip()
                value_str = parts[1].strip()

                # 状態から変数の値を取得
                if var_name not in state:
                    # 変数が存在しない場合はFalse
                    return False

                var_value = state[var_name]

                # 比較値を解析
                try:
                    # 数値の場合
                    compare_value = float(value_str)
                except ValueError:
                    # 文字列の場合
                    compare_value = value_str.strip('"\'')

                # 比較実行
                try:
                    result = op_func(var_value, compare_value)
                    return bool(result)
                except Exception:
                    return False

        # 演算子が見つからない場合、真偽値として評価
        if condition_str.lower() in ['true', '真', 'はい']:
            return True
        if condition_str.lower() in ['false', '偽', 'いいえ']:
            return False

        # 変数名のみの場合、その値を真偽値として評価
        if condition_str in state:
            return bool(state[condition_str])

        return False

    def evaluate_multiple(
        self,
        conditions: List[str],
        state: Dict[str, Any],
        mode: str = "any"
    ) -> bool:
        """
        複数の条件を評価

        Args:
            conditions: 条件文字列のリスト
            state: 状態辞書
            mode: "any"（いずれか）または "all"（全て）

        Returns:
            条件が満たされているか
        """
        if not conditions:
            return False

        results = [self.evaluate(cond, state) for cond in conditions]

        if mode == "any":
            return any(results)
        elif mode == "all":
            return all(results)
        else:
            return any(results)


class EmotionTriggerEvaluator:
    """
    感情DNA Cross構造のFRONT軸発火条件を評価
    """

    def __init__(self):
        """Initialize"""
        self.condition_evaluator = ConditionEvaluator()

    def extract_trigger_conditions(self, emotion_cross: 'CrossStructure') -> List[str]:
        """
        感情CrossのFRONT軸から発火条件を抽出

        Args:
            emotion_cross: 感情Cross構造

        Returns:
            発火条件の文字列リスト
        """
        conditions = []

        # FRONT軸のデータを取得
        # CrossStructureのfrontはnp.arrayなので、元の.jcross定義を見る必要がある
        # ここでは、CrossStructureに元データを保持していると仮定

        if hasattr(emotion_cross, 'metadata') and 'FRONT' in emotion_cross.metadata:
            front_data = emotion_cross.metadata['FRONT']

            for point in front_data:
                if isinstance(point, dict):
                    # 発火条件を探す
                    for key in ['発火条件', 'trigger', 'condition']:
                        if key in point:
                            conditions.append(point[key])

        return conditions

    def evaluate_emotion_trigger(
        self,
        emotion_cross: 'CrossStructure',
        physiological_state: Dict[str, Any],
        cognitive_state: Dict[str, Any]
    ) -> bool:
        """
        感情の発火条件を評価

        Args:
            emotion_cross: 感情Cross構造
            physiological_state: 生理的状態
            cognitive_state: 認知的状態

        Returns:
            感情が発火するか
        """
        # 発火条件を抽出
        conditions = self.extract_trigger_conditions(emotion_cross)

        if not conditions:
            return False

        # 状態を統合
        combined_state = {**physiological_state, **cognitive_state}

        # いずれかの条件が満たされれば発火
        return self.condition_evaluator.evaluate_multiple(
            conditions,
            combined_state,
            mode="any"
        )

    def calculate_trigger_intensity(
        self,
        emotion_cross: 'CrossStructure',
        physiological_state: Dict[str, Any],
        cognitive_state: Dict[str, Any]
    ) -> float:
        """
        発火条件の満たされ度合いを計算

        Args:
            emotion_cross: 感情Cross構造
            physiological_state: 生理的状態
            cognitive_state: 認知的状態

        Returns:
            発火強度 (0.0-1.0)
        """
        conditions = self.extract_trigger_conditions(emotion_cross)

        if not conditions:
            return 0.0

        combined_state = {**physiological_state, **cognitive_state}

        # 各条件の満たされ具合を計算
        satisfied_count = 0
        for condition in conditions:
            if self.condition_evaluator.evaluate(condition, combined_state):
                satisfied_count += 1

        # 満たされた条件の割合
        intensity = satisfied_count / len(conditions)

        return intensity


def main():
    """テスト用メイン関数"""
    print("=" * 80)
    print("JCross発火条件評価器テスト")
    print("=" * 80)
    print()

    evaluator = ConditionEvaluator()

    # テスト1: 単純な比較
    print("テスト1: 単純な比較")
    state = {"痛み": 60.0, "心拍数": 130.0, "体温": 37.5}

    conditions = [
        "痛み > 50.0",
        "心拍数 >= 120",
        "体温 < 38.0"
    ]

    for cond in conditions:
        result = evaluator.evaluate(cond, state)
        print(f"  {cond}: {result}")

    print()

    # テスト2: AND条件
    print("テスト2: AND条件")
    cond = "痛み > 50.0 かつ 心拍数 >= 120"
    result = evaluator.evaluate(cond, state)
    print(f"  {cond}: {result}")
    print()

    # テスト3: OR条件
    print("テスト3: OR条件")
    cond = "痛み > 100.0 または 心拍数 >= 120"
    result = evaluator.evaluate(cond, state)
    print(f"  {cond}: {result}")
    print()

    # テスト4: 感情発火条件
    print("テスト4: 感情発火条件評価")

    from cross_structure import CrossStructure

    # 恐怖Crossのダミー（実際にはemotion_dna_cross.jcrossから読み込む）
    fear_cross = CrossStructure(num_points=10)
    fear_cross.metadata = {
        'FRONT': [
            {"点": 0, "発火条件": "痛み > 50.0"},
            {"点": 1, "発火条件": "心拍数 > 120"}
        ]
    }

    emotion_evaluator = EmotionTriggerEvaluator()

    physiological = {"痛み": 60.0, "心拍数": 130.0, "体温": 37.5}
    cognitive = {"新規性": 0.8, "予測失敗": 0.7}

    should_trigger = emotion_evaluator.evaluate_emotion_trigger(
        fear_cross,
        physiological,
        cognitive
    )

    intensity = emotion_evaluator.calculate_trigger_intensity(
        fear_cross,
        physiological,
        cognitive
    )

    print(f"  恐怖の発火: {should_trigger}")
    print(f"  発火強度: {intensity:.2f}")
    print()

    print("✅ 全テスト完了")


if __name__ == "__main__":
    main()
