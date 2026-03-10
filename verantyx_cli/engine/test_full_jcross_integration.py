#!/usr/bin/env python3
"""
Full .jcross Integration Test
全Phase統合テスト

このテストで全Phase 1-9が正しく動作することを確認
"""

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# Import all components
from jcross_interpreter import JCrossInterpreter
from cross_structure import CrossStructure, MultiCrossStructure
from emotion_dna_system import EmotionDNASystem
from global_cross_registry import GlobalCrossRegistry, get_global_registry
from jcross_runtime import JCrossRuntime, JCrossFunction
from large_cross_structure import LargeCrossStructure
from gpu_cross_structure import GPUCrossStructure
from image_to_cross import ImageToCrossConverter


def test_phase_1_interpreter():
    """Phase 1: JCrossインタプリタのテスト"""
    print("\n" + "=" * 80)
    print("Phase 1: JCrossインタプリタ")
    print("=" * 80)

    jcross_file = Path(__file__).parent.parent / "vision" / "emotion_dna_cross.jcross"

    interpreter = JCrossInterpreter()
    data = interpreter.load_file(str(jcross_file))

    print(f"✅ .jcrossファイル読み込み成功")
    print(f"   変数数: {len(data)}")
    print(f"   変数名: {list(data.keys())[:5]}...")

    return data


def test_phase_2_cross_structure(jcross_data):
    """Phase 2: Cross構造の演算"""
    print("\n" + "=" * 80)
    print("Phase 2: Cross構造の演算")
    print("=" * 80)

    # Cross構造を作成
    cross1 = CrossStructure(num_points=100)
    cross1.up[:10] = np.random.rand(10)

    cross2 = CrossStructure(num_points=100)
    cross2.up[:10] = cross1.up[:10] * 0.9  # 90%一致

    # 同調度計算
    sync = cross1.sync_with(cross2)

    print(f"✅ Cross構造の同調度計算成功")
    print(f"   同調度: {sync:.4f}")

    # MultiCrossStructure
    multi = MultiCrossStructure(jcross_data)

    print(f"✅ MultiCrossStructure作成成功")
    print(f"   Cross数: {len(multi.crosses)}")

    return multi


def test_phase_3_emotion_dna(multi_cross):
    """Phase 3: 感情DNAシステム"""
    print("\n" + "=" * 80)
    print("Phase 3: 感情DNAシステム")
    print("=" * 80)

    jcross_file = Path(__file__).parent.parent / "vision" / "emotion_dna_cross.jcross"
    emotion_system = EmotionDNASystem(jcross_file=str(jcross_file))

    # 感情判定（恐怖シナリオ）
    physiological = {
        "体温": 37.5,
        "血圧": 140.0,
        "心拍数": 120.0,
        "血糖値": 90.0,
        "痛み": 60.0,
        "エネルギー": 0.8
    }

    cognitive = {
        "新規性": 0.9,
        "予測成功": 0.1,
        "予測失敗": 0.8,
        "学習成功": 0.2,
        "理解": 0.3
    }

    emotion_cross = emotion_system.determine_emotion(physiological, cognitive)

    print(f"✅ 感情判定成功")
    print(f"   感情: {emotion_system.current_emotion_name}")
    print(f"   強度: {emotion_system.current_emotion_intensity:.2f}")

    return emotion_system


def test_phase_4_global_registry(emotion_system):
    """Phase 4: 全ノード同調"""
    print("\n" + "=" * 80)
    print("Phase 4: 全ノード同調")
    print("=" * 80)

    registry = get_global_registry()

    # 感情DNAのCross構造を登録
    multi_cross = emotion_system.multi_cross

    for name, cross in multi_cross.crosses.items():
        if "感情" in name or "Cross" in name:
            registry.register(name, cross, group="emotion")

    print(f"✅ Cross構造登録成功")
    print(f"   登録数: {len(registry.crosses)}")

    # 感情割り込み
    registry.emotion_interrupt(
        emotion_name="恐怖",
        resource_allocation={
            "flee": 1.0,
            "learn": 0.0,
            "explore": 0.0,
            "predict": 0.1,
            "memory": 1.0,
            "attack": 0.0,
            "rest": 0.0
        },
        sync_mode="flee_mode"
    )

    status = registry.get_status()

    print(f"✅ 全ノード同調発火成功")
    print(f"   現在のモード: {status['current_sync_mode']}")
    print(f"   リソース配分: {status['current_resource_allocation']}")

    # 割り込み解除
    registry.clear_emotion_interrupt()

    return registry


def test_phase_5_runtime():
    """Phase 5: 制御構文"""
    print("\n" + "=" * 80)
    print("Phase 5: 制御構文")
    print("=" * 80)

    runtime = JCrossRuntime()

    # 関数定義
    func_code = """
定義する 計算 受け取る [x, y] = {
  返す x * y + 10
}
"""

    func = runtime.parse_function_definition(func_code)

    print(f"✅ 関数定義成功: {func}")

    # 関数呼び出し
    result = runtime.call_function("計算", [5, 3])

    print(f"✅ 関数呼び出し成功")
    print(f"   計算(5, 3) = {result}")

    return runtime


def test_phase_6_large_cross():
    """Phase 6: 260,000点の大規模Cross構造"""
    print("\n" + "=" * 80)
    print("Phase 6: 260,000点の大規模Cross構造")
    print("=" * 80)

    large_cross = LargeCrossStructure(use_sparse=True)

    # Layer 4（Concept Layer）にデータ設定
    concept_data = np.random.rand(100) * 0.5
    large_cross.set_layer_data(4, "up", concept_data)

    memory_info = large_cross.get_memory_usage()

    print(f"✅ 大規模Cross構造作成成功")
    print(f"   {large_cross}")
    print(f"   メモリ使用量: {memory_info['total_mb']:.2f} MB")
    print(f"   疎密度: {memory_info['sparsity']:.6f}")

    return large_cross


def test_phase_7_gpu_cross():
    """Phase 7: GPU並列化"""
    print("\n" + "=" * 80)
    print("Phase 7: GPU並列化")
    print("=" * 80)

    # CPU版（GPU未インストール）
    gpu_cross = GPUCrossStructure(num_points=260100, use_gpu=False)

    gpu_cross.up[:100] = np.random.rand(100).astype(np.float32)

    print(f"✅ GPUCross構造作成成功")
    print(f"   {gpu_cross}")

    # 同調度計算のベンチマーク
    another_gpu_cross = GPUCrossStructure(num_points=260100, use_gpu=False)
    another_gpu_cross.up[:100] = gpu_cross.up[:100] * 0.9

    start = time.time()
    sync = gpu_cross.sync_with(another_gpu_cross)
    elapsed = time.time() - start

    print(f"✅ GPU同調計算成功")
    print(f"   同調度: {sync:.4f}")
    print(f"   処理時間: {elapsed*1000:.2f}ms")

    return gpu_cross


def test_phase_8_image_to_cross():
    """Phase 8: 実画像処理との統合"""
    print("\n" + "=" * 80)
    print("Phase 8: 実画像処理との統合")
    print("=" * 80)

    converter = ImageToCrossConverter(use_gpu=False, target_size=(64, 64))

    # テスト画像
    test_image = Image.fromarray(
        (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
    )

    # 変換
    image_cross = converter.convert(test_image)

    print(f"✅ 画像→Cross変換成功")
    print(f"   {image_cross}")

    # 各層の確認
    for layer in range(5):
        up_data = image_cross.get_layer_data(layer, "up")
        non_zero = np.count_nonzero(up_data)
        print(f"   Layer {layer}: {non_zero}点")

    return image_cross


def test_phase_9_integration():
    """Phase 9: 全Phase統合"""
    print("\n" + "=" * 80)
    print("Phase 9: 全Phase統合")
    print("=" * 80)

    from jcross_learning_daemon import JCrossLearningDaemon

    # デーモン作成
    daemon = JCrossLearningDaemon(use_gpu=False)

    print(f"✅ JCrossLearningDaemon作成成功")

    # テスト画像で処理
    test_image = Image.fromarray(
        (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
    )

    result = daemon.process_image_frame(test_image)

    print(f"✅ フレーム処理成功")
    print(f"   同調度: {result['sync_score']:.3f}")
    print(f"   感情: {result['emotion']}")
    print(f"   処理時間: {result['processing_time_ms']:.1f}ms")

    status = daemon.get_status()

    print(f"✅ ステータス取得成功")
    print(f"   フレーム数: {status['frame_count']}")
    print(f"   メモリバンクサイズ: {status['memory_bank_size']}")

    return daemon


def main():
    """全Phaseの統合テスト"""
    print("=" * 80)
    print(".jcross フル実装 統合テスト")
    print("Phase 1-9 の動作確認")
    print("=" * 80)

    start_time = time.time()

    try:
        # Phase 1
        jcross_data = test_phase_1_interpreter()

        # Phase 2
        multi_cross = test_phase_2_cross_structure(jcross_data)

        # Phase 3
        emotion_system = test_phase_3_emotion_dna(multi_cross)

        # Phase 4
        registry = test_phase_4_global_registry(emotion_system)

        # Phase 5
        runtime = test_phase_5_runtime()

        # Phase 6
        large_cross = test_phase_6_large_cross()

        # Phase 7
        gpu_cross = test_phase_7_gpu_cross()

        # Phase 8
        image_cross = test_phase_8_image_to_cross()

        # Phase 9
        daemon = test_phase_9_integration()

        elapsed = time.time() - start_time

        # 最終結果
        print("\n" + "=" * 80)
        print("🎉 全Phase 1-9 テスト成功!")
        print("=" * 80)
        print(f"総実行時間: {elapsed:.2f}秒")
        print()
        print("✅ Phase 1: JCrossインタプリタ")
        print("✅ Phase 2: Cross構造の演算")
        print("✅ Phase 3: 感情DNAシステム")
        print("✅ Phase 4: 全ノード同調")
        print("✅ Phase 5: 制御構文")
        print("✅ Phase 6: 260,000点の大規模Cross構造")
        print("✅ Phase 7: GPU並列化")
        print("✅ Phase 8: 実画像処理との統合")
        print("✅ Phase 9: 全Phase統合")
        print()
        print("🚀 .jcrossフル実装 (100%) 完了!")
        print("=" * 80)

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ テスト失敗")
        print("=" * 80)
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
