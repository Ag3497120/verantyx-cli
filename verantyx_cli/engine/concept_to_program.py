#!/usr/bin/env python3
"""
Concept to Program Generator

概念から.jcrossプログラムを生成
"""

from typing import Dict, List, Optional


class ConceptToProgramGenerator:
    """概念 → .jcrossプログラム変換器"""

    # アクション → .jcross操作マッピング
    ACTION_TO_OPERATION = {
        "check": "確認する",
        "fix": "修正する",
        "verify": "検証する",
        "install": "インストールする",
        "configure": "設定する",
        "execute": "実行する",
        "test": "テストする",
        "debug": "デバッグする",
        "restart": "再起動する",
        "update": "更新する",
        "delete": "削除する",
        "add": "追加する"
    }

    # ドメイン別の具体的な操作
    DOMAIN_OPERATIONS = {
        "docker": {
            "check": "Dockerfile確認",
            "fix": "Dockerfile修正",
            "execute": "docker_build実行",
            "verify": "イメージ検証"
        },
        "git": {
            "check": "git_status確認",
            "fix": "コンフリクト解決",
            "execute": "git_commit実行",
            "verify": "変更確認"
        },
        "python": {
            "check": "モジュール確認",
            "install": "pip_install実行",
            "execute": "Pythonスクリプト実行",
            "verify": "動作確認"
        },
        "database": {
            "check": "接続文字列確認",
            "fix": "認証情報修正",
            "execute": "接続実行",
            "verify": "接続テスト"
        },
        "api": {
            "check": "エンドポイント確認",
            "fix": "リクエスト修正",
            "execute": "API呼び出し",
            "verify": "レスポンス検証"
        }
    }

    def generate(self, concept: Dict, context: Optional[Dict] = None) -> str:
        """
        概念から.jcrossプログラムを生成

        Args:
            concept: 概念データ
            context: コンテキスト情報 (optional)

        Returns:
            .jcrossプログラム文字列
        """
        if not concept:
            return self._generate_default_program()

        domain = concept.get('domain', 'general')
        rule = concept.get('rule', 'check')
        name = concept.get('name', 'generated_program')

        # ルールをステップに分解
        steps = rule.split(" → ") if " → " in rule else [rule]

        # .jcrossプログラムを生成
        program_lines = [f"ラベル {name}"]

        # コンテキストから入力を取得
        if context:
            program_lines.append(f"  取り出す input_data")
            program_lines.append(f"  記憶する context input_data front")

        # 各ステップを操作に変換
        for i, step in enumerate(steps):
            step = step.strip()
            operation = self._step_to_operation(step, domain)

            if operation:
                program_lines.append(f"  実行する {operation} context")
                program_lines.append(f"  記憶する step_{i}_result 結果 front")

        # 結果を返す
        program_lines.append(f"  取り出す step_{len(steps)-1}_result")
        program_lines.append(f"  返す 結果")

        return "\n".join(program_lines)

    def _step_to_operation(self, step: str, domain: str) -> str:
        """ステップを.jcross操作に変換"""
        step_lower = step.lower()

        # ドメイン固有の操作を優先
        if domain in self.DOMAIN_OPERATIONS:
            domain_ops = self.DOMAIN_OPERATIONS[domain]
            for action, operation in domain_ops.items():
                if action in step_lower:
                    return operation

        # 一般的な操作にフォールバック
        for action, operation in self.ACTION_TO_OPERATION.items():
            if action in step_lower:
                return operation

        # デフォルト
        return f"{step}する"

    def _generate_default_program(self) -> str:
        """デフォルトプログラムを生成"""
        return """ラベル default_program
  取り出す input
  実行する 問題分析 input
  記憶する analysis 結果 front
  実行する 解決策生成 analysis
  記憶する solution 結果 front
  取り出す solution
  返す 結果"""

    def generate_batch(self, concepts: List[Dict], context: Optional[Dict] = None) -> Dict[str, str]:
        """
        複数概念から一括でプログラム生成

        Args:
            concepts: 概念リスト
            context: コンテキスト

        Returns:
            {concept_name: program} の辞書
        """
        programs = {}

        for concept in concepts:
            name = concept.get('name', f'concept_{len(programs)}')
            program = self.generate(concept, context)
            programs[name] = program

        return programs

    def generate_adaptive_program(self, concept: Dict, success_history: List[bool]) -> str:
        """
        過去の成功/失敗履歴に基づいて適応的にプログラムを生成

        Args:
            concept: 概念
            success_history: 過去の成功/失敗履歴 [True, False, True, ...]

        Returns:
            適応的に調整された.jcrossプログラム
        """
        base_program = self.generate(concept)

        if not success_history:
            return base_program

        success_rate = sum(success_history) / len(success_history)

        # 成功率が低い場合、より慎重なステップを追加
        if success_rate < 0.5:
            lines = base_program.split("\n")

            # "返す" の前に検証ステップを追加
            insert_idx = len(lines) - 1
            lines.insert(insert_idx, "  実行する 追加検証 context")
            lines.insert(insert_idx + 1, "  記憶する verification 結果 front")

            return "\n".join(lines)

        return base_program


def register_to_vm(vm):
    """VMにConcept→Program変換器を登録"""
    generator = ConceptToProgramGenerator()

    vm.register_processor("概念からプログラム生成", generator.generate)
    vm.register_processor("バッチプログラム生成", generator.generate_batch)
    vm.register_processor("適応的プログラム生成", generator.generate_adaptive_program)

    print("✓ Concept-to-Program generator registered")

    return generator
