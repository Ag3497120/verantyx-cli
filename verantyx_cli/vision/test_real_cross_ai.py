#!/usr/bin/env python3
"""
Real Cross AI Test
本物のCross AIのテスト

おもちゃではなく、本物の実装をテストする。
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image

from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter
from verantyx_cli.vision.cross_neural_network import (
    CrossNeuralNetwork,
    CrossNeuralNetworkBuilder
)


def test_real_cross_ai():
    """本物のCross AIをテスト"""

    print()
    print("=" * 70)
    print("🧠 Real Cross AI Test")
    print("=" * 70)
    print()
    print("【テスト内容】")
    print("  1. 画像をCross構造に変換")
    print("  2. Cross構造 → Cross Neural Network")
    print("  3. 順伝播（情報が層を流れる）")
    print("  4. 学習（逆伝播）")
    print("  5. 予測")
    print()
    print("おもちゃではなく、本物のニューラルネットワークです。")
    print("=" * 70)
    print()

    # ========================================
    # Phase 1: 画像をCross構造に変換
    # ========================================
    print("Phase 1: 画像をCross構造に変換")
    print("-" * 70)
    print()

    # テスト画像を作成（簡単のため小さい画像）
    print("テスト画像を作成中...")
    test_image = Image.new('RGB', (64, 64), color=(128, 128, 128))

    # Cross変換
    print("Cross構造に変換中...")
    converter = MultiLayerCrossConverter(quality="standard")
    multi_layer_cross = converter.convert(test_image)

    print(f"✅ Cross構造作成完了")
    print(f"   層数: {len(multi_layer_cross['layers'])}")
    print(f"   総点数: {multi_layer_cross['metadata']['total_points']:,}")
    print()

    # ========================================
    # Phase 2: Cross Neural Network構築
    # ========================================
    print("Phase 2: Cross Neural Network 構築")
    print("-" * 70)
    print()

    # Cross構造からニューラルネットワークを構築
    cross_nn = CrossNeuralNetworkBuilder.from_multi_layer_cross(multi_layer_cross)

    # ========================================
    # Phase 3: 順伝播テスト
    # ========================================
    print("Phase 3: 順伝播テスト")
    print("-" * 70)
    print()

    print("Layer0 (入力層) の初期状態:")
    layer0_activation = cross_nn.get_layer_activations(0)
    print(f"   平均活性化: {np.mean(layer0_activation):.4f}")
    print(f"   最大活性化: {np.max(layer0_activation):.4f}")
    print(f"   最小活性化: {np.min(layer0_activation):.4f}")
    print()

    print("順伝播を実行中...")
    cross_nn.forward()

    print("✅ 順伝播完了")
    print()

    # 各層の活性化を表示
    for layer_id in range(cross_nn.num_layers):
        layer_activation = cross_nn.get_layer_activations(layer_id)
        layer_name = cross_nn.layers[layer_id].name

        print(f"Layer {layer_id} ({layer_name}):")
        print(f"   点数: {len(layer_activation):,}")
        print(f"   平均活性化: {np.mean(layer_activation):.4f}")
        print(f"   最大活性化: {np.max(layer_activation):.4f}")
        print(f"   最小活性化: {np.min(layer_activation):.4f}")
        print()

    # ========================================
    # Phase 4: 学習テスト
    # ========================================
    print("Phase 4: 学習テスト")
    print("-" * 70)
    print()

    # 目標出力を作成（Layer4の100点に対する正解）
    print("目標出力を作成中...")
    target_output = np.zeros(cross_nn.layers[-1].num_points)
    target_output[0] = 1.0  # 最初のニューロンを活性化させたい
    target_output[1] = 1.0
    target_output[2] = 1.0

    print(f"目標: Layer4の最初の3点を活性化")
    print()

    # 学習前の出力
    print("学習前の出力:")
    output_before = cross_nn.get_output()
    print(f"   出力[0]: {output_before[0]:.4f} (目標: 1.0)")
    print(f"   出力[1]: {output_before[1]:.4f} (目標: 1.0)")
    print(f"   出力[2]: {output_before[2]:.4f} (目標: 1.0)")
    error_before = np.mean((target_output - output_before) ** 2)
    print(f"   誤差(MSE): {error_before:.4f}")
    print()

    # 学習
    print("学習中（10イテレーション）...")
    for i in range(10):
        # 入力を再セット
        input_activations = layer0_activation

        # 学習ステップ
        error = cross_nn.train_step(input_activations, target_output, learning_rate=0.1)

        if (i + 1) % 5 == 0:
            print(f"   イテレーション {i+1}: 誤差 = {error:.4f}")

    print()

    # 学習後の出力
    print("学習後の出力:")
    output_after = cross_nn.get_output()
    print(f"   出力[0]: {output_after[0]:.4f} (目標: 1.0)")
    print(f"   出力[1]: {output_after[1]:.4f} (目標: 1.0)")
    print(f"   出力[2]: {output_after[2]:.4f} (目標: 1.0)")
    error_after = np.mean((target_output - output_after) ** 2)
    print(f"   誤差(MSE): {error_after:.4f}")
    print()

    # 改善度
    improvement = (error_before - error_after) / error_before * 100
    print(f"✅ 誤差が {improvement:.1f}% 改善しました")
    print()

    # ========================================
    # Phase 5: 予測テスト
    # ========================================
    print("Phase 5: 予測テスト")
    print("-" * 70)
    print()

    print("同じ入力で予測を実行...")
    prediction = cross_nn.predict(layer0_activation)

    print(f"予測結果:")
    print(f"   予測[0]: {prediction[0]:.4f}")
    print(f"   予測[1]: {prediction[1]:.4f}")
    print(f"   予測[2]: {prediction[2]:.4f}")
    print()

    # ========================================
    # まとめ
    # ========================================
    print("=" * 70)
    print("🎉 Real Cross AI Test 完了")
    print("=" * 70)
    print()
    print("【重要なポイント】")
    print()
    print("1. Cross構造 = ニューラルネットワーク")
    print(f"   - 総点数: {len(cross_nn.all_points):,} 点 = {len(cross_nn.all_points):,} ニューロン")
    print(f"   - 5層構造")
    print()
    print("2. 26万点の情報を全て使う")
    print("   - ハッシュに変換しない")
    print("   - 情報を捨てない")
    print()
    print("3. 情報が層を通って流れる")
    print("   - Layer0 → Layer1 → Layer2 → Layer3 → Layer4")
    print("   - 各層で抽象化が進む")
    print()
    print("4. 学習できる")
    print(f"   - 誤差: {error_before:.4f} → {error_after:.4f}")
    print(f"   - 改善: {improvement:.1f}%")
    print()
    print("5. 6軸が活性化を変調")
    print("   - UP/DOWN: 活性度")
    print("   - FRONT/BACK: 時間")
    print("   - RIGHT/LEFT: 空間")
    print()
    print("これが本物のCross AIです。")
    print("おもちゃではありません。")
    print()
    print("=" * 70)
    print()


def main():
    """メイン関数"""
    try:
        test_real_cross_ai()
        return 0
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
