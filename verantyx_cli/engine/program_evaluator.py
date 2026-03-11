#!/usr/bin/env python3
"""
Program Evaluator

生成されたプログラムを実行して評価
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


class ProgramEvaluator:
    """プログラム評価器"""

    def __init__(self, vm=None):
        self.vm = vm
        self.evaluation_history: List[Dict] = []

    def evaluate(
        self,
        program: str,
        program_name: str,
        context: Optional[Dict] = None,
        expected_outcome: Optional[Dict] = None
    ) -> Dict:
        """
        プログラムを実行して評価

        Args:
            program: .jcrossプログラム
            program_name: プログラム名/ラベル名
            context: 実行コンテキスト
            expected_outcome: 期待される結果

        Returns:
            評価結果 {
                "success": bool,
                "score": float (0.0-1.0),
                "execution_time": float,
                "error": str or None,
                "result": Any,
                "metrics": Dict
            }
        """
        start_time = datetime.now()

        evaluation = {
            "program_name": program_name,
            "success": False,
            "score": 0.0,
            "execution_time": 0.0,
            "error": None,
            "result": None,
            "metrics": {}
        }

        try:
            # VMがない場合は簡易評価
            if not self.vm:
                evaluation["success"] = True
                evaluation["score"] = 0.5
                evaluation["result"] = "simulated_success"
                evaluation["metrics"] = {"simulated": True}
                return evaluation

            # プログラムをロード
            self.vm.load_program(program)

            # 実行
            result = self.vm.execute_label(program_name, context)

            # 実行時間計算
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # 基本評価
            evaluation["success"] = True
            evaluation["result"] = result
            evaluation["execution_time"] = execution_time

            # スコア計算
            score = self._calculate_score(
                result=result,
                expected_outcome=expected_outcome,
                execution_time=execution_time
            )
            evaluation["score"] = score

            # メトリクス
            evaluation["metrics"] = self._collect_metrics(result, execution_time)

        except Exception as e:
            evaluation["success"] = False
            evaluation["error"] = str(e)
            evaluation["score"] = 0.0
            evaluation["metrics"] = {"error_type": type(e).__name__}

        # 履歴に追加
        self.evaluation_history.append({
            **evaluation,
            "timestamp": datetime.now().isoformat()
        })

        return evaluation

    def _calculate_score(
        self,
        result: Any,
        expected_outcome: Optional[Dict],
        execution_time: float
    ) -> float:
        """スコアを計算"""
        score = 0.0

        # 1. 実行成功 (基本点 0.3)
        if result is not None:
            score += 0.3

        # 2. 期待結果との一致 (0.5)
        if expected_outcome:
            match_score = self._calculate_outcome_match(result, expected_outcome)
            score += match_score * 0.5
        else:
            # 期待結果がない場合は結果があれば加点
            if result:
                score += 0.4

        # 3. 効率性 (0.2)
        efficiency_score = self._calculate_efficiency(execution_time)
        score += efficiency_score * 0.2

        return min(1.0, score)

    def _calculate_outcome_match(self, result: Any, expected: Dict) -> float:
        """期待結果との一致度を計算"""
        if not expected:
            return 0.5

        # 簡易的な一致判定
        if isinstance(result, dict) and isinstance(expected, dict):
            matches = 0
            total = len(expected)

            for key, expected_value in expected.items():
                if key in result and result[key] == expected_value:
                    matches += 1

            return matches / total if total > 0 else 0.0

        # 完全一致
        if result == expected:
            return 1.0

        # 部分一致（文字列の場合）
        if isinstance(result, str) and isinstance(expected, str):
            if expected.lower() in str(result).lower():
                return 0.7

        return 0.0

    def _calculate_efficiency(self, execution_time: float) -> float:
        """効率性を計算"""
        # 実行時間が短いほど高スコア
        if execution_time < 0.1:
            return 1.0
        elif execution_time < 0.5:
            return 0.8
        elif execution_time < 1.0:
            return 0.6
        elif execution_time < 2.0:
            return 0.4
        else:
            return 0.2

    def _collect_metrics(self, result: Any, execution_time: float) -> Dict:
        """メトリクスを収集"""
        metrics = {
            "execution_time": execution_time,
            "result_type": type(result).__name__,
            "result_size": len(str(result)) if result else 0
        }

        # VMからメトリクスを取得
        if self.vm:
            metrics["cross_space_objects"] = len(self.vm.cross_space.objects)
            metrics["instructions_executed"] = getattr(self.vm, 'pc', 0)

        return metrics

    def evaluate_batch(
        self,
        programs: Dict[str, str],
        contexts: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, Dict]:
        """
        複数プログラムを一括評価

        Args:
            programs: {program_name: program_code}
            contexts: {program_name: context}

        Returns:
            {program_name: evaluation_result}
        """
        results = {}

        for name, program in programs.items():
            context = contexts.get(name) if contexts else None
            evaluation = self.evaluate(program, name, context)
            results[name] = evaluation

        return results

    def compare_programs(self, evaluations: List[Dict]) -> Dict:
        """
        複数の評価結果を比較

        Args:
            evaluations: 評価結果のリスト

        Returns:
            比較結果 {
                "best": Dict,
                "worst": Dict,
                "average_score": float,
                "success_rate": float
            }
        """
        if not evaluations:
            return {}

        # 成功したもののみ
        successful = [e for e in evaluations if e.get("success")]

        if not successful:
            return {
                "best": None,
                "worst": None,
                "average_score": 0.0,
                "success_rate": 0.0
            }

        # ベスト・ワーストを特定
        best = max(successful, key=lambda e: e.get("score", 0))
        worst = min(successful, key=lambda e: e.get("score", 0))

        # 平均スコア
        avg_score = sum(e.get("score", 0) for e in evaluations) / len(evaluations)

        # 成功率
        success_rate = len(successful) / len(evaluations)

        return {
            "best": best,
            "worst": worst,
            "average_score": avg_score,
            "success_rate": success_rate,
            "total_evaluated": len(evaluations),
            "total_successful": len(successful)
        }

    def get_statistics(self) -> Dict:
        """評価統計を取得"""
        if not self.evaluation_history:
            return {}

        total = len(self.evaluation_history)
        successful = [e for e in self.evaluation_history if e.get("success")]

        return {
            "total_evaluations": total,
            "successful_evaluations": len(successful),
            "success_rate": len(successful) / total if total > 0 else 0.0,
            "average_score": sum(e.get("score", 0) for e in self.evaluation_history) / total if total > 0 else 0.0,
            "average_execution_time": sum(e.get("execution_time", 0) for e in self.evaluation_history) / total if total > 0 else 0.0
        }

    def suggest_improvements(self, evaluation: Dict) -> List[str]:
        """
        評価結果から改善提案を生成

        Args:
            evaluation: 評価結果

        Returns:
            改善提案のリスト
        """
        suggestions = []

        score = evaluation.get("score", 0)
        error = evaluation.get("error")
        execution_time = evaluation.get("execution_time", 0)

        # スコアが低い
        if score < 0.5:
            suggestions.append("プログラムの成功率が低いです。ルールを見直してください。")

        # エラーがある
        if error:
            suggestions.append(f"実行エラー: {error}")
            suggestions.append("プログラムの構文またはロジックを確認してください。")

        # 実行時間が長い
        if execution_time > 2.0:
            suggestions.append("実行時間が長いです。より効率的なアルゴリズムを検討してください。")

        # 成功しているが改善余地あり
        if 0.5 <= score < 0.8:
            suggestions.append("部分的に成功しています。期待結果との一致度を高めてください。")

        # 完璧
        if score >= 0.9:
            suggestions.append("優れたプログラムです！")

        return suggestions if suggestions else ["評価できません。"]


def register_to_vm(vm):
    """VMにProgram Evaluatorを登録"""
    evaluator = ProgramEvaluator(vm=vm)

    vm.register_processor("プログラム評価", evaluator.evaluate)
    vm.register_processor("バッチ評価", evaluator.evaluate_batch)
    vm.register_processor("プログラム比較", evaluator.compare_programs)
    vm.register_processor("改善提案", evaluator.suggest_improvements)

    print("✓ Program Evaluator registered")

    return evaluator
