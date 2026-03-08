"""
Claude Wrapper Neural Engine Version

従来のVM実行からNeural Engine実行へ移行
ノイマン型を排除したCross Native実行
"""

import sys
import os
from pathlib import Path
from typing import Dict, Optional
import numpy as np
import coremltools as ct

# Neural engineコンポーネントをインポート
sys.path.insert(0, str(Path(__file__).parent))
from jcross_to_neural import compile_jcross_to_neural
from coreml_converter import CoreMLConverter

# kofdai_computerのパスを追加
kofdai_dir = Path(__file__).parent.parent.parent.parent.parent / "kofdai_computer"
sys.path.insert(0, str(kofdai_dir))


class ClaudeWrapperNeuralEngine:
    """
    Claude Wrapper - Neural Engine版

    アーキテクチャ:
    1. JCross → Neural Model変換
    2. Neural Model → Core ML変換
    3. Neural Engineで状態遷移実行
    4. Python I/Oプロセッサとの連携
    """

    def __init__(self,
                 host: str = "localhost",
                 port: int = 52749,
                 project_path: str = "."):
        self.host = host
        self.port = port
        self.project_path = project_path

        self.neural_model = None
        self.coreml_model = None

        # 状態管理（Neural Engineと同期）
        self.current_state = 0
        self.stack = None
        self.memory = None

    def compile_wrapper(self) -> bool:
        """
        Claude WrapperをNeural Engine版にコンパイル

        Returns:
            True if successful
        """
        print("🔨 Compiling Claude Wrapper for Neural Engine...")
        print()

        # JCrossソースを読み込み
        jcross_file = Path(__file__).parent.parent / "claude_wrapper_simple.jcross"

        if not jcross_file.exists():
            print(f"❌ JCross wrapper not found: {jcross_file}")
            return False

        with open(jcross_file, 'r', encoding='utf-8') as f:
            jcross_source = f.read()

        print(f"📜 Loaded: {jcross_file.name}")

        try:
            # Step 1: JCross → Neural Model
            print()
            print("─" * 70)
            self.neural_model = compile_jcross_to_neural(jcross_source)

            # Step 2: Neural Model → Core ML
            print()
            print("─" * 70)
            print()

            converter = CoreMLConverter()
            model_path = Path(__file__).parent / "claude_wrapper_neural.mlpackage"

            self.coreml_model = converter.convert(
                self.neural_model,
                output_path=str(model_path),
                compute_units="CPU_AND_NE"  # Neural Engine使用
            )

            print()
            print("=" * 70)
            print("✅ Claude Wrapper compiled for Neural Engine!")
            print("=" * 70)

            return True

        except Exception as e:
            print()
            print("=" * 70)
            print(f"❌ Compilation failed: {e}")
            import traceback
            traceback.print_exc()
            print("=" * 70)
            return False

    def initialize_state(self):
        """Neural Engine用の初期状態を準備"""
        batch_size = 1
        stack_size = 256
        feature_dim = 64
        memory_dims = (8, 8, 8)

        # 初期状態
        self.current_state = 0

        # スタック初期化
        self.stack = np.zeros((batch_size, stack_size, feature_dim), dtype=np.float32)

        # メモリ初期化
        self.memory = np.zeros((batch_size, *memory_dims, feature_dim), dtype=np.float32)

        print(f"✅ Initialized Neural Engine state")
        print(f"   State: {self.current_state}")
        print(f"   Stack: {self.stack.shape}")
        print(f"   Memory: {self.memory.shape}")

    def run_step(self) -> Dict:
        """
        Neural Engineで1ステップ実行

        Returns:
            Prediction results
        """
        if self.coreml_model is None:
            raise RuntimeError("Model not compiled. Call compile_wrapper() first.")

        # Neural Engineで推論
        inputs = {
            'state_id': np.array([self.current_state], dtype=np.int32),
            'stack': self.stack,
            'memory': self.memory
        }

        predictions = self.coreml_model.predict(inputs)

        # 状態を更新
        self.current_state = int(predictions['var_46'][0])
        self.stack = predictions['stack']
        self.memory = predictions['memory']

        return predictions

    def run(self, max_steps: int = 100):
        """
        Neural Engineで実行ループ

        Args:
            max_steps: 最大ステップ数
        """
        print()
        print("🚀 Starting Neural Engine execution...")
        print()

        self.initialize_state()

        print()
        print("─" * 70)
        print()

        for step in range(max_steps):
            print(f"Step {step + 1}: State {self.current_state}", flush=True)

            # Neural Engineで1ステップ実行
            result = self.run_step()

            # 終了状態チェック（最後の状態は終了）
            if self.current_state >= self.neural_model.num_states - 1:
                print()
                print(f"✅ Reached end state after {step + 1} steps")
                break
        else:
            print()
            print(f"⚠️  Max steps ({max_steps}) reached")

        print()
        print("─" * 70)
        print(f"Final state: {self.current_state}")
        print("=" * 70)


def run_claude_wrapper_neural_engine(host: str, port: int, project_path: str):
    """
    Claude WrapperをNeural Engineで実行

    Args:
        host: Verantyx host
        port: Verantyx port
        project_path: Project directory
    """
    print()
    print("=" * 70)
    print("Claude Wrapper - Neural Engine Edition")
    print("=" * 70)
    print()
    print(f"🌐 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"📁 Project: {project_path}")
    print()
    print("Architecture: Non-von Neumann (Neural Engine)")
    print()
    print("=" * 70)

    # Wrapperを作成
    wrapper = ClaudeWrapperNeuralEngine(host, port, project_path)

    # コンパイル
    if not wrapper.compile_wrapper():
        sys.exit(1)

    # 実行
    wrapper.run(max_steps=20)


if __name__ == "__main__":
    # テスト実行
    if len(sys.argv) >= 3:
        host = sys.argv[1]
        port = int(sys.argv[2])
        project_path = sys.argv[3] if len(sys.argv) > 3 else "."
    else:
        host = "localhost"
        port = 52749
        project_path = "."

    run_claude_wrapper_neural_engine(host, port, project_path)
