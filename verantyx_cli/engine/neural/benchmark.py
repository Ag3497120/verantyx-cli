"""
Performance Benchmark - VM vs Neural Engine

ノイマン型VM実行とNeural Engine実行の性能比較
"""

import time
import sys
from pathlib import Path
from typing import Dict
import numpy as np

# Neural engineコンポーネント
sys.path.insert(0, str(Path(__file__).parent))
from jcross_to_neural import compile_jcross_to_neural
from coreml_converter import CoreMLConverter

# VM実行
sys.path.insert(0, str(Path(__file__).parent.parent))
from cross_ir_vm import CrossIRVM

# kofdai_computer
kofdai_dir = Path(__file__).parent.parent.parent.parent.parent / "kofdai_computer"
sys.path.insert(0, str(kofdai_dir))

from kernel import KofdaiKernel
from jcross_ir_compiler import compile_jcross_to_ir


class Benchmark:
    """
    VM vs Neural Engine性能ベンチマーク
    """

    def __init__(self):
        self.results = {}

    def benchmark_vm_execution(self, jcross_source: str, iterations: int = 100) -> Dict:
        """
        従来のVM実行をベンチマーク

        Args:
            jcross_source: JCrossソース
            iterations: 実行回数

        Returns:
            Benchmark results
        """
        print("🔵 Benchmarking VM Execution (von Neumann)...")
        print(f"   Iterations: {iterations}")

        # コンパイル時間計測
        compile_start = time.time()
        compile_result = compile_jcross_to_ir(jcross_source)
        ir_program = compile_result.program
        compile_time = time.time() - compile_start

        print(f"   ✅ Compiled in {compile_time:.4f}s")

        # 実行時間計測
        kernel = KofdaiKernel()
        vm = CrossIRVM(ir_program, kernel, {})

        execution_times = []
        for i in range(iterations):
            # VM初期化
            vm.pc = 0
            vm.running = True
            vm.stack = []
            vm.variables = {}

            # 実行
            exec_start = time.time()
            try:
                result = vm.run()
            except:
                pass  # エラー無視
            exec_time = time.time() - exec_start

            execution_times.append(exec_time)

        avg_time = np.mean(execution_times)
        std_time = np.std(execution_times)

        print(f"   ✅ Average execution time: {avg_time:.6f}s (±{std_time:.6f}s)")

        return {
            'compile_time': compile_time,
            'avg_execution_time': avg_time,
            'std_execution_time': std_time,
            'total_time': compile_time + avg_time * iterations,
            'iterations': iterations,
            'architecture': 'von Neumann VM'
        }

    def benchmark_neural_engine(self, jcross_source: str, iterations: int = 100) -> Dict:
        """
        Neural Engine実行をベンチマーク

        Args:
            jcross_source: JCrossソース
            iterations: 実行回数

        Returns:
            Benchmark results
        """
        print("🟢 Benchmarking Neural Engine Execution (Non-von Neumann)...")
        print(f"   Iterations: {iterations}")

        # コンパイル時間計測
        compile_start = time.time()

        # JCross → Neural Model
        neural_model = compile_jcross_to_neural(jcross_source)

        # Neural Model → Core ML
        converter = CoreMLConverter()
        model_path = Path(__file__).parent / "benchmark_model.mlpackage"
        coreml_model = converter.convert(
            neural_model,
            output_path=str(model_path),
            compute_units="CPU_AND_NE"
        )

        compile_time = time.time() - compile_start

        print(f"   ✅ Compiled in {compile_time:.4f}s")

        # 実行時間計測
        batch_size = 1
        stack_size = 256
        feature_dim = 64
        memory_dims = (8, 8, 8)

        execution_times = []
        for i in range(iterations):
            # 入力準備
            inputs = {
                'state_id': np.array([0], dtype=np.int32),
                'stack': np.randn(batch_size, stack_size, feature_dim).astype(np.float32),
                'memory': np.randn(batch_size, *memory_dims, feature_dim).astype(np.float32)
            }

            # Neural Engineで実行
            exec_start = time.time()
            predictions = coreml_model.predict(inputs)
            exec_time = time.time() - exec_start

            execution_times.append(exec_time)

        avg_time = np.mean(execution_times)
        std_time = np.std(execution_times)

        print(f"   ✅ Average execution time: {avg_time:.6f}s (±{std_time:.6f}s)")

        return {
            'compile_time': compile_time,
            'avg_execution_time': avg_time,
            'std_execution_time': std_time,
            'total_time': compile_time + avg_time * iterations,
            'iterations': iterations,
            'architecture': 'Neural Engine (ANE)'
        }

    def run_benchmark(self, jcross_source: str, iterations: int = 100):
        """
        完全なベンチマーク実行

        Args:
            jcross_source: JCrossソース
            iterations: 実行回数
        """
        print()
        print("=" * 70)
        print("Performance Benchmark: VM vs Neural Engine")
        print("=" * 70)
        print()

        # VM実行
        vm_results = self.benchmark_vm_execution(jcross_source, iterations)
        print()

        # Neural Engine実行
        ne_results = self.benchmark_neural_engine(jcross_source, iterations)
        print()

        # 結果比較
        print("=" * 70)
        print("Benchmark Results")
        print("=" * 70)
        print()

        print(f"{'Metric':<30} {'VM':<20} {'Neural Engine':<20} {'Speedup':<10}")
        print("-" * 80)

        # コンパイル時間
        vm_compile = vm_results['compile_time']
        ne_compile = ne_results['compile_time']
        compile_speedup = vm_compile / ne_compile if ne_compile > 0 else 0
        print(f"{'Compile Time':<30} {vm_compile:<20.4f}s {ne_compile:<20.4f}s {compile_speedup:<10.2f}x")

        # 実行時間
        vm_exec = vm_results['avg_execution_time']
        ne_exec = ne_results['avg_execution_time']
        exec_speedup = vm_exec / ne_exec if ne_exec > 0 else 0
        print(f"{'Avg Execution Time':<30} {vm_exec:<20.6f}s {ne_exec:<20.6f}s {exec_speedup:<10.2f}x")

        # トータル
        vm_total = vm_results['total_time']
        ne_total = ne_results['total_time']
        total_speedup = vm_total / ne_total if ne_total > 0 else 0
        print(f"{'Total Time':<30} {vm_total:<20.4f}s {ne_total:<20.4f}s {total_speedup:<10.2f}x")

        print()
        print("=" * 70)

        # アーキテクチャ比較
        print()
        print("Architecture Comparison:")
        print()
        print(f"  VM (von Neumann):")
        print(f"    - Sequential execution")
        print(f"    - Program counter")
        print(f"    - Instruction fetch/decode cycle")
        print()
        print(f"  Neural Engine (Non-von Neumann):")
        print(f"    - Parallel state transitions")
        print(f"    - State vectors (no PC)")
        print(f"    - Data flow execution")
        print()
        print("=" * 70)

        self.results = {
            'vm': vm_results,
            'neural_engine': ne_results,
            'speedup': {
                'compile': compile_speedup,
                'execution': exec_speedup,
                'total': total_speedup
            }
        }

        return self.results


if __name__ == "__main__":
    # ベンチマーク用プログラム
    test_program = """
"開始"
表示する

ラベル STATE_A
  "状態A"
  表示する
  ジャンプ STATE_B

ラベル STATE_B
  "状態B"
  表示する
  ジャンプ STATE_C

ラベル STATE_C
  "状態C"
  表示する
  ジャンプ END

ラベル END
"終了"
表示する

終わる
"""

    # ベンチマーク実行
    benchmark = Benchmark()
    results = benchmark.run_benchmark(test_program, iterations=50)

    print()
    print("✅ Benchmark complete!")
