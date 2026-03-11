#!/usr/bin/env python3
"""
Dynamic Code Generator from Cross Structures

Cross構造から動的に.jcrossコードを生成
パターン発見 → 新しい操作の発見 → コード生成
"""

from typing import Dict, List, Any, Optional, Tuple
import re


class DynamicCodeGenerator:
    """Cross構造から動的にコードを生成"""

    def __init__(self, cross_simulator=None):
        self.cross_simulator = cross_simulator
        self.discovered_patterns: Dict[str, Dict] = {}
        self.discovered_operations: Dict[str, str] = {}

    def generate_from_cross_structure(
        self,
        cross_obj_id: str,
        goal: str,
        context: Optional[Dict] = None
    ) -> str:
        """
        Cross構造から動的にプログラムを生成

        従来: テンプレート的生成
        今回: Cross空間のパターンを分析して動的生成
        """
        if not self.cross_simulator:
            return self._generate_fallback(cross_obj_id, goal)

        # 1. Cross構造からパターンを抽出
        patterns = self.analyze_cross_patterns(cross_obj_id)

        # 2. パターンから新しい操作を発見
        operations = self.discover_operations(patterns)

        # 3. 操作からプログラムを生成
        program = self.generate_dynamic_program(
            cross_obj_id,
            goal,
            operations,
            context
        )

        return program

    def analyze_cross_patterns(self, obj_id: str) -> Dict:
        """
        Cross構造のパターンを分析

        6軸の位置・関連から「パターン」を発見
        """
        if not self.cross_simulator or obj_id not in self.cross_simulator.objects:
            return {}

        obj = self.cross_simulator.objects[obj_id]

        patterns = {
            "obj_id": obj_id,
            "axis_strengths": obj.positions.copy(),
            "relations": obj.relations.copy(),
            "discovered_patterns": []
        }

        # パターン1: 強い上昇軌道 (UP high, FRONT high)
        if obj.positions["UP"] > 0.7 and obj.positions["FRONT"] > 0.6:
            patterns["discovered_patterns"].append({
                "name": "strong_upward_trajectory",
                "confidence": (obj.positions["UP"] + obj.positions["FRONT"]) / 2,
                "implication": "High success probability, can use aggressive strategies"
            })

        # パターン2: 弱い基盤 (DOWN low)
        if obj.positions["DOWN"] < 0.4:
            patterns["discovered_patterns"].append({
                "name": "weak_foundation",
                "confidence": 1.0 - obj.positions["DOWN"],
                "implication": "Need to strengthen preconditions first"
            })

        # パターン3: 長いチェーン (RIGHT high, many relations)
        if obj.positions["RIGHT"] > 0.6 and len(obj.relations["RIGHT"]) > 2:
            patterns["discovered_patterns"].append({
                "name": "complex_process",
                "confidence": obj.positions["RIGHT"],
                "implication": "Multi-step process, need careful orchestration"
            })

        # パターン4: 豊富な履歴 (BACK high)
        if obj.positions["BACK"] > 0.7:
            patterns["discovered_patterns"].append({
                "name": "well_established",
                "confidence": obj.positions["BACK"],
                "implication": "Can rely on historical patterns"
            })

        # パターン5: バランスの取れた状態
        avg_position = sum(obj.positions.values()) / 6
        variance = sum((v - avg_position) ** 2 for v in obj.positions.values()) / 6

        if variance < 0.05:
            patterns["discovered_patterns"].append({
                "name": "balanced_state",
                "confidence": 1.0 - variance,
                "implication": "Stable, can proceed normally"
            })

        return patterns

    def discover_operations(self, patterns: Dict) -> List[Dict]:
        """
        パターンから新しい操作を発見

        従来: 固定された操作 (check, fix, verify)
        今回: パターンに基づいて動的に操作を生成
        """
        operations = []

        for pattern in patterns.get("discovered_patterns", []):
            pattern_name = pattern["name"]
            confidence = pattern["confidence"]

            if pattern_name == "strong_upward_trajectory":
                # 積極的な操作
                operations.append({
                    "type": "aggressive_execution",
                    "operation": "高速実行する",
                    "confidence": confidence,
                    "rationale": "High confidence allows aggressive approach"
                })

            elif pattern_name == "weak_foundation":
                # 基盤強化操作
                operations.append({
                    "type": "foundation_strengthening",
                    "operation": "基盤を強化する",
                    "confidence": confidence,
                    "rationale": "Weak foundation needs reinforcement"
                })
                operations.append({
                    "type": "validation",
                    "operation": "前提条件を検証する",
                    "confidence": confidence,
                    "rationale": "Validate preconditions before proceeding"
                })

            elif pattern_name == "complex_process":
                # 段階的操作
                operations.append({
                    "type": "step_by_step",
                    "operation": "段階的に実行する",
                    "confidence": confidence,
                    "rationale": "Complex process needs careful steps"
                })
                operations.append({
                    "type": "checkpoint",
                    "operation": "チェックポイント保存",
                    "confidence": confidence,
                    "rationale": "Save checkpoints for recovery"
                })

            elif pattern_name == "well_established":
                # 履歴ベース操作
                operations.append({
                    "type": "historical",
                    "operation": "過去の成功例を適用する",
                    "confidence": confidence,
                    "rationale": "Can leverage historical success"
                })

            elif pattern_name == "balanced_state":
                # 標準操作
                operations.append({
                    "type": "standard",
                    "operation": "標準手順を実行する",
                    "confidence": confidence,
                    "rationale": "Stable state allows standard approach"
                })

        # 操作を発見データベースに保存
        for op in operations:
            op_name = op["operation"]
            if op_name not in self.discovered_operations:
                self.discovered_operations[op_name] = op["type"]

        return operations

    def generate_dynamic_program(
        self,
        obj_id: str,
        goal: str,
        operations: List[Dict],
        context: Optional[Dict]
    ) -> str:
        """
        発見した操作から動的にプログラムを生成

        従来: テンプレート
        今回: 操作の組み合わせを動的に決定
        """
        lines = [f"ラベル {obj_id}_dynamic"]

        # コンテキスト取得
        lines.append("  取り出す input_context")
        lines.append("  記憶する context input_context front")

        # Cross空間シミュレーションを実行
        lines.append(f"  # Cross空間でシミュレーション")
        lines.append(f"  実行する Cross操作シミュレート \"{obj_id}\" \"pre_check\" context")
        lines.append(f"  記憶する simulation_result 結果 front")

        # 発見した操作を適用
        for i, op in enumerate(operations):
            op_name = op["operation"]
            confidence = op["confidence"]

            # 信頼度チェック
            lines.append(f"  # Operation {i+1}: {op_name} (confidence: {confidence:.2f})")

            if confidence > 0.7:
                # 高信頼度 → 直接実行
                lines.append(f"  実行する {op_name} context")
                lines.append(f"  記憶する op_{i}_result 結果 front")

            else:
                # 低信頼度 → 条件付き実行
                lines.append(f"  実行する シミュレート確認 \"{op_name}\" context")
                lines.append(f"  記憶する sim_check 結果")
                lines.append(f"  取り出す sim_check")
                lines.append(f"  条件分岐 安全")
                lines.append(f"    実行する {op_name} context")
                lines.append(f"    記憶する op_{i}_result 結果 front")
                lines.append(f"  それ以外")
                lines.append(f"    実行する 代替手順 context")
                lines.append(f"    記憶する op_{i}_result 結果 front")
                lines.append(f"  終わり")

        # 結果を統合
        lines.append("  # 結果統合")
        lines.append("  実行する 結果統合 context")
        lines.append("  記憶する final_result 結果 front")

        # Cross空間に保存
        lines.append("  # Cross空間に保存")
        lines.append(f"  実行する Cross空間オブジェクト追加 \"{obj_id}_result\" final_result")

        # 返す
        lines.append("  取り出す final_result")
        lines.append("  返す 結果")

        return "\n".join(lines)

    def _generate_fallback(self, obj_id: str, goal: str) -> str:
        """フォールバック: シミュレータがない場合"""
        return f"""ラベル {obj_id}_fallback
  取り出す input
  実行する 標準処理 input
  記憶する result 結果 front
  取り出す result
  返す 結果"""

    def evolve_program(
        self,
        program: str,
        evaluation_result: Dict
    ) -> str:
        """
        評価結果に基づいてプログラムを進化させる

        低スコア → プログラムを変異
        高スコア → そのまま
        """
        score = evaluation_result.get("score", 0)

        if score >= 0.8:
            # 高スコア: 変更不要
            return program

        # 低スコア: 変異を適用
        mutated = self._mutate_program(program, evaluation_result)

        return mutated

    def _mutate_program(self, program: str, evaluation_result: Dict) -> str:
        """プログラムを変異"""
        lines = program.split("\n")

        mutations = []

        # エラーがあった場合
        if evaluation_result.get("error"):
            # エラーハンドリングを追加
            mutations.append(("error_handling", self._add_error_handling))

        # スコアが低い場合
        if evaluation_result.get("score", 0) < 0.5:
            # 検証ステップを追加
            mutations.append(("validation", self._add_validation_steps))

        # 実行時間が長い場合
        if evaluation_result.get("execution_time", 0) > 2.0:
            # 最適化を追加
            mutations.append(("optimization", self._add_optimization))

        # 変異を適用
        for mutation_type, mutation_func in mutations:
            lines = mutation_func(lines)

        return "\n".join(lines)

    def _add_error_handling(self, lines: List[str]) -> List[str]:
        """エラーハンドリングを追加"""
        # "返す" の前にエラーチェックを追加
        for i, line in enumerate(lines):
            if "返す" in line:
                lines.insert(i, "  実行する エラーチェック result")
                lines.insert(i+1, "  条件分岐 エラー")
                lines.insert(i+2, "    実行する エラー回復 result")
                lines.insert(i+3, "    記憶する result 結果")
                lines.insert(i+4, "  終わり")
                break

        return lines

    def _add_validation_steps(self, lines: List[str]) -> List[str]:
        """検証ステップを追加"""
        # "実行する" の後に検証を追加
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if "実行する" in line and "検証" not in line:
                new_lines.append("  実行する 結果検証 結果")

        return new_lines

    def _add_optimization(self, lines: List[str]) -> List[str]:
        """最適化を追加"""
        # 並列実行可能な部分を特定
        # (簡易実装: コメント追加のみ)
        new_lines = []
        for line in lines:
            if "実行する" in line:
                new_lines.append("  # 最適化: 並列実行検討")
            new_lines.append(line)

        return new_lines

    def get_discovered_operations(self) -> Dict[str, str]:
        """発見した操作を取得"""
        return self.discovered_operations.copy()

    def get_statistics(self) -> Dict:
        """統計を取得"""
        return {
            "total_patterns_discovered": len(self.discovered_patterns),
            "total_operations_discovered": len(self.discovered_operations),
            "operations": list(self.discovered_operations.keys())
        }


def register_to_vm(vm, cross_simulator=None):
    """VMにDynamic Code Generatorを登録"""
    generator = DynamicCodeGenerator(cross_simulator=cross_simulator)

    vm.register_processor("Cross構造から生成", generator.generate_from_cross_structure)
    vm.register_processor("Crossパターン分析", generator.analyze_cross_patterns)
    vm.register_processor("操作発見", generator.discover_operations)
    vm.register_processor("プログラム進化", generator.evolve_program)
    vm.register_processor("発見操作取得", generator.get_discovered_operations)

    print("✓ Dynamic Code Generator registered")

    return generator
