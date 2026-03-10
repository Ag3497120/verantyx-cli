#!/usr/bin/env python3
"""
Test Zero Year Old Model (JCross Version)
0歳児モデルのテスト（JCross版）

全てのロジックはJCrossで実装。
Pythonは表示とI/Oのみ。
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image

from verantyx_cli.engine.jcross_bootstrap import ZeroYearOldJCross
from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter


def create_test_image(color: tuple, size: tuple = (64, 64)) -> Image.Image:
    """テスト用の画像を作成"""
    return Image.new('RGB', size, color=color)


def test_zero_year_old_jcross():
    """0歳児モデル（JCross版）のテスト"""

    print()
    print("=" * 80)
    print("👶 0歳児モデル - JCross完全実装版テスト")
    print("=" * 80)
    print()
    print("【重要】")
    print("  全てのロジックはJCrossで実装されています。")
    print("  Pythonは表示とI/Oのみ。")
    print()
    print("【シナリオ】")
    print("  1. 赤ちゃんはお腹が空いて不快")
    print("  2. 母親の顔（特定の視覚パターン）を見る")
    print("  3. 授乳される → エネルギー回復 → 不快感減少")
    print("  4. これが繰り返される")
    print("  5. 赤ちゃんは母親の顔と「安心」を関連付ける")
    print("  6. 教師信号なし、不快感の変化だけで学習")
    print()
    print("=" * 80)
    print()

    # ========================================
    # Phase 1: 0歳児モデル初期化（JCross版）
    # ========================================
    print("Phase 1: 0歳児モデル初期化（JCross版）")
    print("-" * 80)
    print()

    baby = ZeroYearOldJCross()

    # Cross構造変換器
    converter = MultiLayerCrossConverter(quality="fast")

    print()

    # ========================================
    # Phase 2: 母親の顔のCross構造を作成
    # ========================================
    print("Phase 2: 母親の顔のCross構造を作成")
    print("-" * 80)
    print()

    print("母親の顔（ピンク色）を作成...")
    mother_face = create_test_image(color=(255, 192, 203))  # Pink

    print("Cross構造に変換中...")
    mother_cross = converter.convert(mother_face)
    print(f"✅ Cross構造作成完了: {mother_cross['metadata']['total_points']:,} 点")
    print()

    # ========================================
    # Phase 3: 学習シミュレーション
    # ========================================
    print("Phase 3: 学習シミュレーション（10回の経験）")
    print("-" * 80)
    print()

    for i in range(10):
        print(f"【経験 {i + 1}】")
        print()

        # Step 1: お腹が空く（エネルギー低下）
        energy_level = 20.0 + np.random.randn() * 5.0
        baby.change_homeostasis("エネルギー", energy_level)

        status_before = baby.get_status()
        discomfort_before = status_before["生理"]["不快感"]

        print(f"  1. お腹が空く")
        print(f"     エネルギー: {energy_level:.1f}")
        print(f"     不快感: {discomfort_before['総不快感']:.3f}")

        reflex = status_before["生理"]["反射"]
        if reflex:
            print(f"     反射: {reflex}")
        print()

        # Step 2: 母親の顔を見る（不快な状態で）
        print(f"  2. 母親の顔を見る（不快な状態）")
        experience_result_1 = baby.experience(
            cross_structure=mother_cross,
            context={"visual": "mother_face_hungry"}
        )
        print(f"     Cross構造を記憶に保存")
        print()

        # Step 3: 授乳される（エネルギー回復）
        energy_recovered = 100.0
        baby.change_homeostasis("エネルギー", energy_recovered)

        status_after = baby.get_status()
        discomfort_after = status_after["生理"]["不快感"]

        print(f"  3. 授乳される（解決）")
        print(f"     エネルギー: {energy_recovered:.1f}")
        print(f"     不快感: {discomfort_after['総不快感']:.3f}")
        print(f"     不快感の変化: {discomfort_before['総不快感'] - discomfort_after['総不快感']:.3f} (改善)")
        print()

        # Step 4: 再度母親の顔を見る（満腹状態）- 学習が起こる
        print(f"  4. もう一度母親の顔を見る（満腹状態）")
        experience_result_2 = baby.experience(
            cross_structure=mother_cross,
            context={"visual": "mother_face_fed"}
        )

        learning_event = experience_result_2.get("学習イベント")
        if learning_event:
            print(f"     🎓 学習発生!")
            print(f"        不快感の改善: {learning_event['改善']:.3f}")
            print(f"        重みの変化: {learning_event['重み変化']:.6f}")
        else:
            print(f"     学習なし（不快感変化が小さい）")

        print()
        print("-" * 40)
        print()

    # ========================================
    # Phase 4: 学習結果の確認
    # ========================================
    print("Phase 4: 学習結果の確認")
    print("-" * 80)
    print()

    final_status = baby.get_status()

    print("【0歳児の状態】")
    print()

    alive = final_status["生理"]["生存"]
    print(f"生存: {'✅ 生きている' if alive else '❌ 死亡'}")
    print()

    print("恒常性:")
    for var, value in final_status["生理"]["状態"].items():
        print(f"  {var}: {value:.1f}")
    print()

    print("記憶統計:")
    memory_stats = final_status["記憶"]
    print(f"  総経験数: {memory_stats['総経験数']}")
    print(f"  クラスタ数: {memory_stats['クラスタ数']}")
    print(f"  解決ペア数: {memory_stats['解決ペア数']}")
    print()

    print("学習統計:")
    learning_stats = final_status["学習"]
    print(f"  学習イベント数: {learning_stats['総イベント数']}")
    if learning_stats['最新イベント']:
        print(f"  最新イベント:")
        for event in learning_stats['最新イベント'][-3:]:
            print(f"    - 改善: {event['改善']:.3f}, 重み変化: {event['重み変化']:.6f}")
    print()

    # ========================================
    # まとめ
    # ========================================
    print("=" * 80)
    print("🎉 0歳児モデル（JCross版）テスト完了")
    print("=" * 80)
    print()
    print("【実装の特徴】")
    print()
    print("1. 全てJCrossで実装")
    print("   - 遺伝子公理: genetic_axioms.jcross")
    print("   - 未定義バッファ: undefined_buffer.jcross")
    print("   - 経験的学習: experiential_learning.jcross")
    print("   - 統合モデル: zero_year_old_complete.jcross")
    print()
    print("2. Pythonは表示のみ")
    print("   - ロジックは全てJCross")
    print("   - PythonはI/Oとブートストラップのみ")
    print()
    print("3. 教師信号なし")
    print("   - ラベルを与えていない")
    print("   - 不快感の変化だけで学習")
    print()
    print("4. DNA-encoded homeostasis")
    print("   - 恒常性維持は遺伝子に刻まれている")
    print("   - 学習では変わらない")
    print()
    print("5. 未解釈の記憶")
    print(f"   - {memory_stats['総経験数']} 個の経験をCross構造として保存")
    print("   - 意味はまだない（後から付く）")
    print()
    print("6. 自動的に学習")
    print(f"   - {learning_stats['総イベント数']} 回の学習イベント")
    print("   - 不快感-解決の共起で重みが更新")
    print()
    print("=" * 80)
    print()


def main():
    """メイン関数"""
    try:
        test_zero_year_old_jcross()
        return 0

    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
