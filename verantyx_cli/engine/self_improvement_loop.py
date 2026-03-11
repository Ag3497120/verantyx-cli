#!/usr/bin/env python3
"""
Self-Improvement Loop - 完全実装

Claudeログから学習し、自己改善するループ
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path


class SelfImprovementLoop:
    """自己改善ループ"""

    def __init__(self, vm, miner, generator, evaluator):
        """
        Args:
            vm: JCrossVM
            miner: RealConceptMiner
            generator: ConceptToProgramGenerator
            evaluator: ProgramEvaluator
        """
        self.vm = vm
        self.miner = miner
        self.generator = generator
        self.evaluator = evaluator

        self.improvement_history: List[Dict] = []
        self.cycle_count = 0

    def run_single_cycle(
        self,
        user_input: str,
        claude_response: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        1サイクルの自己改善を実行

        流れ:
        1. Claudeログから概念を抽出
        2. 概念からプログラムを生成
        3. プログラムを実行・評価
        4. 評価結果を概念にフィードバック
        5. 改善

        Args:
            user_input: ユーザー入力
            claude_response: Claude応答
            context: 実行コンテキスト

        Returns:
            サイクル結果 {
                "cycle_id": int,
                "concept": Dict,
                "program": str,
                "evaluation": Dict,
                "improvement": Dict,
                "timestamp": str
            }
        """
        self.cycle_count += 1
        cycle_id = self.cycle_count

        print(f"\n{'='*60}")
        print(f"Self-Improvement Cycle #{cycle_id}")
        print(f"{'='*60}")

        result = {
            "cycle_id": cycle_id,
            "user_input": user_input[:50] + "...",
            "timestamp": datetime.now().isoformat()
        }

        # === Step 1: 概念抽出 ===
        print("\n[Step 1] Concept Mining...")
        concept, is_new = self.miner.mine(user_input, claude_response)

        result["concept"] = {
            "name": concept['name'],
            "domain": concept['domain'],
            "rule": concept['rule'],
            "confidence": concept['confidence'],
            "is_new": is_new
        }

        print(f"  {'✅ New concept' if is_new else '🔄 Strengthened'}: {concept['name']}")
        print(f"  Rule: {concept['rule']}")
        print(f"  Confidence: {concept['confidence']:.2f}")

        # === Step 2: プログラム生成 ===
        print("\n[Step 2] Program Generation...")
        program = self.generator.generate(concept, context)

        result["program"] = program
        print(f"  Generated: {len(program.split(chr(10)))} lines")

        # === Step 3: プログラム実行・評価 ===
        print("\n[Step 3] Program Execution & Evaluation...")
        evaluation = self.evaluator.evaluate(
            program=program,
            program_name=concept['name'],
            context=context
        )

        result["evaluation"] = {
            "success": evaluation['success'],
            "score": evaluation['score'],
            "execution_time": evaluation['execution_time']
        }

        print(f"  Success: {evaluation['success']}")
        print(f"  Score: {evaluation['score']:.2f}")

        # === Step 4: フィードバック ===
        print("\n[Step 4] Feedback to Concept...")
        improvement = self._apply_feedback(concept, evaluation)

        result["improvement"] = improvement
        print(f"  Confidence: {improvement['old_confidence']:.2f} → {improvement['new_confidence']:.2f}")
        print(f"  Use Count: {improvement['old_use_count']} → {improvement['new_use_count']}")

        # === Step 5: 改善提案 ===
        suggestions = self.evaluator.suggest_improvements(evaluation)
        result["suggestions"] = suggestions

        if suggestions:
            print("\n[Step 5] Improvement Suggestions:")
            for suggestion in suggestions[:3]:
                print(f"  • {suggestion}")

        # 履歴に追加
        self.improvement_history.append(result)

        print(f"\n{'='*60}")
        print(f"✅ Cycle #{cycle_id} Complete")
        print(f"{'='*60}\n")

        return result

    def _apply_feedback(self, concept: Dict, evaluation: Dict) -> Dict:
        """
        評価結果を概念にフィードバック

        Args:
            concept: 概念
            evaluation: 評価結果

        Returns:
            改善情報
        """
        old_confidence = concept['confidence']
        old_use_count = concept['use_count']

        # 使用回数を増やす
        concept['use_count'] += 1

        # スコアに基づいて信頼度を更新
        score = evaluation.get('score', 0)

        if score >= 0.8:
            # 高スコア: 大幅に信頼度を上げる
            concept['confidence'] = min(1.0, concept['confidence'] + 0.15)
        elif score >= 0.5:
            # 中スコア: 少し信頼度を上げる
            concept['confidence'] = min(1.0, concept['confidence'] + 0.05)
        else:
            # 低スコア: 信頼度を下げる
            concept['confidence'] = max(0.1, concept['confidence'] - 0.1)

        return {
            "old_confidence": old_confidence,
            "new_confidence": concept['confidence'],
            "old_use_count": old_use_count,
            "new_use_count": concept['use_count'],
            "confidence_delta": concept['confidence'] - old_confidence
        }

    def run_multiple_cycles(
        self,
        dialogues: List[Tuple[str, str]],
        context: Optional[Dict] = None
    ) -> Dict:
        """
        複数サイクルを連続実行

        Args:
            dialogues: [(user_input, claude_response), ...]
            context: 共通コンテキスト

        Returns:
            全体結果 {
                "total_cycles": int,
                "concepts_created": int,
                "concepts_strengthened": int,
                "average_score": float,
                "improvement_trend": List[float]
            }
        """
        print("\n" + "="*80)
        print("SELF-IMPROVEMENT: Multiple Cycles")
        print("="*80)

        concepts_created = 0
        concepts_strengthened = 0
        scores = []

        for i, (user_input, claude_response) in enumerate(dialogues, 1):
            print(f"\n--- Dialogue {i}/{len(dialogues)} ---")

            result = self.run_single_cycle(user_input, claude_response, context)

            if result['concept']['is_new']:
                concepts_created += 1
            else:
                concepts_strengthened += 1

            scores.append(result['evaluation']['score'])

        # 統計
        print("\n" + "="*80)
        print("OVERALL STATISTICS")
        print("="*80)

        total_cycles = len(dialogues)
        avg_score = sum(scores) / len(scores) if scores else 0.0

        stats = {
            "total_cycles": total_cycles,
            "concepts_created": concepts_created,
            "concepts_strengthened": concepts_strengthened,
            "average_score": avg_score,
            "score_trend": scores,
            "miner_stats": self.miner.get_statistics(),
            "evaluator_stats": self.evaluator.get_statistics()
        }

        print(f"\nTotal Cycles: {total_cycles}")
        print(f"Concepts Created: {concepts_created}")
        print(f"Concepts Strengthened: {concepts_strengthened}")
        print(f"Average Score: {avg_score:.2f}")
        print(f"Score Trend: {' → '.join(f'{s:.2f}' for s in scores[:5])}{'...' if len(scores) > 5 else ''}")

        # 改善トレンドを分析
        if len(scores) >= 3:
            early_avg = sum(scores[:3]) / 3
            late_avg = sum(scores[-3:]) / 3
            improvement = late_avg - early_avg

            print(f"\nImprovement: {early_avg:.2f} → {late_avg:.2f} ({improvement:+.2f})")

            if improvement > 0.1:
                print("✅ Significant improvement detected!")
            elif improvement > 0:
                print("✅ Slight improvement detected")
            else:
                print("⚠️  No improvement (may need more data)")

        print("\n" + "="*80)

        return stats

    def get_best_concepts(self, top_n: int = 5) -> List[Dict]:
        """
        信頼度の高い概念を取得

        Args:
            top_n: 上位何個を取得するか

        Returns:
            上位概念のリスト
        """
        concepts = list(self.miner.concepts.values())
        concepts.sort(key=lambda c: c['confidence'], reverse=True)
        return concepts[:top_n]

    def export_learned_knowledge(self, output_path: Path) -> None:
        """
        学習した知識をエクスポート

        Args:
            output_path: 出力先パス
        """
        import json

        knowledge = {
            "export_date": datetime.now().isoformat(),
            "total_cycles": self.cycle_count,
            "concepts": self.miner.concepts,
            "statistics": self.miner.get_statistics(),
            "improvement_history": self.improvement_history
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge, f, indent=2, ensure_ascii=False)

        print(f"✓ Knowledge exported to: {output_path}")

    def visualize_progress(self) -> str:
        """進捗を可視化"""
        if not self.improvement_history:
            return "No data yet"

        lines = ["Progress Visualization:", "="*60]

        # スコアトレンド
        lines.append("\nScore Trend:")
        scores = [h['evaluation']['score'] for h in self.improvement_history]

        for i, score in enumerate(scores, 1):
            bar_length = int(score * 40)
            bar = "█" * bar_length + "░" * (40 - bar_length)
            lines.append(f"  Cycle {i:2d}: {bar} {score:.2f}")

        # 概念統計
        stats = self.miner.get_statistics()
        lines.append(f"\nTotal Concepts: {stats['total_concepts']}")
        lines.append(f"Average Confidence: {stats['avg_confidence']:.2f}")

        lines.append("\nDomains:")
        for domain, count in stats['by_domain'].items():
            lines.append(f"  {domain}: {count}")

        return "\n".join(lines)


def register_to_vm(vm, miner, generator, evaluator):
    """VMに自己改善ループを登録"""
    loop = SelfImprovementLoop(
        vm=vm,
        miner=miner,
        generator=generator,
        evaluator=evaluator
    )

    vm.register_processor("自己改善サイクル", loop.run_single_cycle)
    vm.register_processor("複数サイクル実行", loop.run_multiple_cycles)
    vm.register_processor("ベスト概念取得", loop.get_best_concepts)
    vm.register_processor("知識エクスポート", loop.export_learned_knowledge)

    print("✓ Self-Improvement Loop registered")

    return loop
