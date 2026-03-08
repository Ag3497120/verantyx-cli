"""
JCross Dynamic Language Features - 動的言語機能

JCrossが実行時に自己変容する機能:

1. **メタプログラミング** - コードがコードを生成
2. **動的コンパイル** - 実行時にJCrossコードをコンパイル
3. **自己書き換え** - プログラムが自分自身を変更
4. **構造進化** - Cross構造が動的に成長

設計原則:
- JCross言語が主体
- Pythonは実行エンジンのみ
- Cross構造に全ての状態を保存
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

# kofdai_computerのパスを追加
kofdai_dir = Path(__file__).parent.parent.parent.parent / "kofdai_computer"
sys.path.insert(0, str(kofdai_dir))

from jcross_ir_compiler import compile_jcross_to_ir, CompileResult
from cross_ir_vm import CrossIRVM
from cross_ir import ProgramIR


class DynamicJCrossCompiler:
    """
    動的JCrossコンパイラ

    実行時にJCrossコードをコンパイルして実行
    """

    def __init__(self, kernel, processors):
        """
        Args:
            kernel: Cross Kernel
            processors: I/O processors
        """
        self.kernel = kernel
        self.processors = processors
        self.compiled_programs = {}  # コンパイル済みプログラムキャッシュ

    def compile_runtime(self, jcross_code: str, program_name: str) -> ProgramIR:
        """
        実行時にJCrossコードをコンパイル

        Args:
            jcross_code: JCrossソースコード
            program_name: プログラム名

        Returns:
            コンパイル済みIR
        """
        print(f"🔄 Compiling JCross at runtime: {program_name}")

        # JCross → CrossIR
        compile_result = compile_jcross_to_ir(jcross_code)

        # キャッシュに保存
        self.compiled_programs[program_name] = compile_result.program

        print(f"✅ Compiled: {len(compile_result.program.instructions)} instructions")

        return compile_result.program

    def execute_runtime(self, program_name: str, initial_vars: Dict[str, Any] = None) -> Any:
        """
        コンパイル済みプログラムを実行

        Args:
            program_name: プログラム名
            initial_vars: 初期変数

        Returns:
            実行結果
        """
        if program_name not in self.compiled_programs:
            raise ValueError(f"Program not found: {program_name}")

        ir_program = self.compiled_programs[program_name]

        # VM作成
        vm = CrossIRVM(ir_program, self.kernel, self.processors)

        # 初期変数設定
        if initial_vars:
            vm.variables.update(initial_vars)

        # 実行
        print(f"▶️  Executing: {program_name}")
        result = vm.run()

        return result


class MetaProgramming:
    """
    メタプログラミング機能

    JCrossコードがJCrossコードを生成
    """

    @staticmethod
    def generate_loop(loop_count: int, body: str) -> str:
        """
        ループコードを生成

        Args:
            loop_count: ループ回数
            body: ループ本体のコード

        Returns:
            生成されたJCrossコード
        """
        code_lines = [
            f"# Generated loop ({loop_count} times)",
            "0",
            "入れる counter",
            "",
            "ラベル LOOP_START",
            "  取り出す counter",
            f"  {loop_count}",
            "  >=",
            "  1ならジャンプ LOOP_END",
            "",
            "  # Loop body",
        ]

        # ループ本体を追加（インデント）
        for line in body.strip().split('\n'):
            code_lines.append(f"  {line}")

        code_lines.extend([
            "",
            "  # Increment counter",
            "  取り出す counter",
            "  1",
            "  +",
            "  入れる counter",
            "  捨てる",
            "",
            "  ジャンプ LOOP_START",
            "",
            "ラベル LOOP_END",
            "取り出す counter",
            "捨てる"
        ])

        return '\n'.join(code_lines)

    @staticmethod
    def generate_conditional(condition_var: str, true_code: str, false_code: str) -> str:
        """
        条件分岐コードを生成

        Args:
            condition_var: 条件変数名
            true_code: 真の場合のコード
            false_code: 偽の場合のコード

        Returns:
            生成されたJCrossコード
        """
        code_lines = [
            f"# Generated conditional: {condition_var}",
            f"取り出す {condition_var}",
            "0ならジャンプ FALSE_BRANCH",
            "",
            "# True branch",
        ]

        for line in true_code.strip().split('\n'):
            code_lines.append(line)

        code_lines.extend([
            "ジャンプ END_IF",
            "",
            "ラベル FALSE_BRANCH",
            "# False branch"
        ])

        for line in false_code.strip().split('\n'):
            code_lines.append(line)

        code_lines.extend([
            "",
            "ラベル END_IF"
        ])

        return '\n'.join(code_lines)

    @staticmethod
    def generate_function(func_name: str, param_names: List[str], body: str) -> str:
        """
        関数コードを生成

        Args:
            func_name: 関数名
            param_names: パラメータ名リスト
            body: 関数本体

        Returns:
            生成されたJCrossコード
        """
        code_lines = [
            f"# Function: {func_name}",
            f"ラベル {func_name}",
        ]

        # パラメータを取り出して変数に保存
        for param in reversed(param_names):
            code_lines.append(f"  入れる {param}")

        code_lines.append("")

        # 関数本体
        for line in body.strip().split('\n'):
            code_lines.append(f"  {line}")

        # 戻り値をスタックに残して終了
        code_lines.append(f"  # Return from {func_name}")

        return '\n'.join(code_lines)


class SelfModifyingProgram:
    """
    自己書き換えプログラム

    プログラムが実行中に自分自身のコードを変更
    """

    def __init__(self, dynamic_compiler: DynamicJCrossCompiler):
        self.compiler = dynamic_compiler
        self.program_versions = []  # プログラムの変遷履歴

    def modify_and_recompile(self, program_name: str, modifications: List[Dict[str, Any]]) -> ProgramIR:
        """
        プログラムを変更して再コンパイル

        Args:
            program_name: 元のプログラム名
            modifications: 変更内容のリスト
                [{"type": "add_line", "after_label": "LOOP", "code": "表示する"}]

        Returns:
            変更後のIRプログラム
        """
        # 元のプログラムを取得
        if program_name not in self.compiler.compiled_programs:
            raise ValueError(f"Program not found: {program_name}")

        # TODO: IR→JCrossの逆コンパイル（未実装）
        # 現在はソースコードを保持する必要がある

        print(f"⚠️  Self-modification requires source code preservation (not implemented)")
        return self.compiler.compiled_programs[program_name]

    def evolve_structure(self, base_program: str, fitness_func) -> str:
        """
        Cross構造を進化させる

        Args:
            base_program: 基本プログラム
            fitness_func: 適応度関数

        Returns:
            進化後のプログラム
        """
        print("🧬 Evolving Cross structure...")

        # 遺伝的アルゴリズムの簡易実装
        current = base_program
        best_fitness = fitness_func(current)

        for generation in range(10):
            # 変異: ランダムに行を追加/削除
            mutated = self._mutate_program(current)

            # 評価
            fitness = fitness_func(mutated)

            if fitness > best_fitness:
                current = mutated
                best_fitness = fitness
                print(f"  Generation {generation}: Fitness improved to {fitness}")

        return current

    def _mutate_program(self, program: str) -> str:
        """プログラムに変異を加える"""
        import random

        lines = program.split('\n')

        # ランダムに表示命令を追加
        mutation_point = random.randint(0, len(lines) - 1)
        lines.insert(mutation_point, '"Mutated!"')
        lines.insert(mutation_point + 1, '表示する')

        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════
# Dynamic I/O Processors - Cross構造から呼び出し可能
# ═══════════════════════════════════════════════════════════════

_DYNAMIC_COMPILER = None

def get_dynamic_compiler(kernel, processors):
    """動的コンパイラのシングルトン取得"""
    global _DYNAMIC_COMPILER
    if _DYNAMIC_COMPILER is None:
        _DYNAMIC_COMPILER = DynamicJCrossCompiler(kernel, processors)
    return _DYNAMIC_COMPILER


def dynamic_compile_jcross(params: dict) -> dict:
    """
    実行時JCrossコンパイルプロセッサ

    入力:
        {"code": str, "name": str, "__vm_vars__": {...}}

    出力:
        {"success": bool, "program_name": str}
    """
    vm_vars = params.get('__vm_vars__', {})
    kernel = vm_vars.get('__kernel__')
    processors = vm_vars.get('__processors__')

    if not kernel or not processors:
        return {"success": False, "error": "Kernel/Processors not available"}

    compiler = get_dynamic_compiler(kernel, processors)

    code = params.get('code', '')
    name = params.get('name', 'runtime_program')

    try:
        compiler.compile_runtime(code, name)
        return {"success": True, "program_name": name}
    except Exception as e:
        return {"success": False, "error": str(e)}


def dynamic_execute_program(params: dict) -> dict:
    """
    コンパイル済みプログラム実行プロセッサ

    入力:
        {"program_name": str, "vars": dict, "__vm_vars__": {...}}

    出力:
        {"success": bool, "result": Any}
    """
    vm_vars = params.get('__vm_vars__', {})
    kernel = vm_vars.get('__kernel__')
    processors = vm_vars.get('__processors__')

    if not kernel or not processors:
        return {"success": False, "error": "Kernel/Processors not available"}

    compiler = get_dynamic_compiler(kernel, processors)

    program_name = params.get('program_name', '')
    initial_vars = params.get('vars', {})

    try:
        result = compiler.execute_runtime(program_name, initial_vars)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def meta_generate_loop(params: dict) -> dict:
    """
    ループコード生成プロセッサ

    入力:
        {"count": int, "body": str}

    出力:
        {"code": str}
    """
    count = params.get('count', 1)
    body = params.get('body', '# Empty loop body')

    code = MetaProgramming.generate_loop(count, body)

    return {"code": code}


def meta_generate_conditional(params: dict) -> dict:
    """
    条件分岐コード生成プロセッサ

    入力:
        {"condition_var": str, "true_code": str, "false_code": str}

    出力:
        {"code": str}
    """
    condition_var = params.get('condition_var', 'condition')
    true_code = params.get('true_code', '# True branch')
    false_code = params.get('false_code', '# False branch')

    code = MetaProgramming.generate_conditional(condition_var, true_code, false_code)

    return {"code": code}


def get_dynamic_io_processors():
    """
    動的言語機能のI/Oプロセッサ

    Cross構造から呼び出し可能
    """
    return {
        'dynamic.compile': dynamic_compile_jcross,
        'dynamic.execute': dynamic_execute_program,
        'meta.generate_loop': meta_generate_loop,
        'meta.generate_conditional': meta_generate_conditional,
    }


if __name__ == "__main__":
    # テスト実行
    print("=" * 70)
    print("JCross Dynamic Features Test")
    print("=" * 70)
    print()

    # Test 1: メタプログラミング - ループ生成
    print("Test 1: Generate Loop Code")
    loop_code = MetaProgramming.generate_loop(3, '"Hello"\\n表示する')
    print(loop_code)
    print()

    # Test 2: 条件分岐生成
    print("Test 2: Generate Conditional Code")
    cond_code = MetaProgramming.generate_conditional(
        'check_value',
        '"Value is true"\\n表示する',
        '"Value is false"\\n表示する'
    )
    print(cond_code)
    print()

    print("=" * 70)
    print("✅ Dynamic Features Tests Complete")
    print("=" * 70)
