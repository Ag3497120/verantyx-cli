"""
Core ML Converter - CrossNeuralModelをCore MLに変換してNeural Engineで実行

Apple Neural Engine (ANE)でネイティブ実行
"""

import torch
import coremltools as ct
from pathlib import Path
from typing import Dict, Tuple
import sys

# Cross Neural Modelをインポート
sys.path.insert(0, str(Path(__file__).parent))
from cross_neural_model import CrossNeuralModel


class CoreMLConverter:
    """
    CrossNeuralModelをCore ML形式に変換

    Apple Neural Engineで実行可能な.mlmodelを生成
    """

    def __init__(self):
        pass

    def convert(self,
                model: CrossNeuralModel,
                output_path: str = "cross_structure.mlpackage",
                compute_units: str = "ALL") -> ct.models.MLModel:
        """
        PyTorchモデルをCore MLに変換

        Args:
            model: CrossNeuralModel instance
            output_path: 出力ファイルパス (.mlpackage)
            compute_units: "CPU_ONLY", "CPU_AND_GPU", "CPU_AND_NE", "ALL"

        Returns:
            Core ML model
        """
        print("🔄 Converting to Core ML...")
        print()

        # Step 1: モデルをevalモードに
        model.eval()
        print(f"  [1/5] Model set to eval mode")

        # Step 2: 例示入力を準備
        print(f"  [2/5] Preparing example inputs...")
        batch_size = 1
        stack_size = 256
        feature_dim = 64
        memory_dims = (8, 8, 8)

        example_inputs = (
            torch.tensor([0], dtype=torch.long),  # state_id
            torch.randn(batch_size, stack_size, feature_dim),  # stack
            torch.randn(batch_size, *memory_dims, feature_dim)  # memory
        )
        print(f"        State: {example_inputs[0].shape}")
        print(f"        Stack: {example_inputs[1].shape}")
        print(f"        Memory: {example_inputs[2].shape}")

        # Step 3: TorchScript tracing
        print(f"  [3/5] Tracing model with TorchScript...")
        with torch.no_grad():
            traced_model = torch.jit.trace(model, example_inputs)
        print(f"        ✅ Model traced")

        # Step 4: Core ML変換
        print(f"  [4/5] Converting to Core ML...")

        # 入力の定義
        import numpy as np
        inputs = [
            ct.TensorType(
                name="state_id",
                shape=(1,),
                dtype=np.int32
            ),
            ct.TensorType(
                name="stack",
                shape=(batch_size, stack_size, feature_dim),
                dtype=np.float32
            ),
            ct.TensorType(
                name="memory",
                shape=(batch_size, *memory_dims, feature_dim),
                dtype=np.float32
            )
        ]

        # Compute Unitsの設定
        compute_units_map = {
            "CPU_ONLY": ct.ComputeUnit.CPU_ONLY,
            "CPU_AND_GPU": ct.ComputeUnit.CPU_AND_GPU,
            "CPU_AND_NE": ct.ComputeUnit.CPU_AND_NE,
            "ALL": ct.ComputeUnit.ALL
        }

        selected_compute = compute_units_map.get(compute_units, ct.ComputeUnit.ALL)

        # 変換
        coreml_model = ct.convert(
            traced_model,
            inputs=inputs,
            compute_units=selected_compute,
            minimum_deployment_target=ct.target.macOS14
        )

        print(f"        ✅ Converted to Core ML")
        print(f"        Compute units: {compute_units}")

        # Step 5: 保存
        print(f"  [5/5] Saving model...")
        coreml_model.save(output_path)
        print(f"        ✅ Saved to: {output_path}")

        print()
        print("✅ Core ML conversion complete!")

        return coreml_model

    def test_inference(self, coreml_model: ct.models.MLModel):
        """
        Core MLモデルで推論テスト

        Args:
            coreml_model: Core ML model
        """
        print()
        print("🧪 Testing inference...")
        print()

        # テスト入力
        test_inputs = {
            'state_id': torch.tensor([0], dtype=torch.int32).numpy(),
            'stack': torch.randn(1, 256, 64).numpy(),
            'memory': torch.randn(1, 8, 8, 8, 64).numpy()
        }

        # 推論
        print(f"  Running inference on Neural Engine...")
        predictions = coreml_model.predict(test_inputs)

        print(f"  ✅ Inference complete!")
        print(f"  Output keys: {list(predictions.keys())}")

        # 結果を表示
        for key, value in predictions.items():
            if hasattr(value, 'shape'):
                print(f"    {key}: shape={value.shape}, dtype={value.dtype}")
            else:
                print(f"    {key}: {type(value)}")

        return predictions


def convert_jcross_to_coreml(jcross_source: str,
                            output_path: str = "cross_structure.mlpackage") -> ct.models.MLModel:
    """
    JCrossソースから直接Core MLモデルを生成

    Args:
        jcross_source: JCrossソースコード
        output_path: 出力パス

    Returns:
        Core ML model
    """
    from jcross_to_neural import compile_jcross_to_neural

    print("=" * 70)
    print("JCross → Core ML Compilation Pipeline")
    print("=" * 70)
    print()

    # Step 1: JCross → Neural Model
    neural_model = compile_jcross_to_neural(jcross_source)

    print()
    print("─" * 70)
    print()

    # Step 2: Neural Model → Core ML
    converter = CoreMLConverter()
    coreml_model = converter.convert(neural_model, output_path, compute_units="ALL")

    print()
    print("=" * 70)

    return coreml_model


if __name__ == "__main__":
    # テスト用JCrossプログラム
    test_program = """
# Neural Engine Test Program

"開始"
表示する

ラベル STATE_A
  "状態A"
  表示する
  ジャンプ STATE_B

ラベル STATE_B
  "状態B"
  表示する
  ジャンプ END

ラベル END
"終了"
表示する

終わる
"""

    print()
    print("=" * 70)
    print("Core ML Converter - Test")
    print("=" * 70)
    print()

    try:
        # JCross → Core ML変換
        coreml_model = convert_jcross_to_coreml(
            test_program,
            output_path="test_cross_structure.mlpackage"
        )

        # 推論テスト
        converter = CoreMLConverter()
        converter.test_inference(coreml_model)

        print()
        print("=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)

    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 70)
